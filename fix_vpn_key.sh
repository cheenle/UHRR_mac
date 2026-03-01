#!/usr/bin/env bash
set -euo pipefail

DOMAIN="www.vlsc.net"
LIVE_DIR="/etc/letsencrypt/live/${DOMAIN}"
SRC_KEY="${LIVE_DIR}/privkey.pem"
SRC_CERT="${LIVE_DIR}/fullchain.pem"
DST_KEY="/etc/ipsec.d/private/serverKey.pem"
DST_CERT="/etc/ipsec.d/certs/serverCert.pem"

echo "[+] Copy certificate and convert private key to PKCS#8 (unencrypted)"
install -m 644 "${SRC_CERT}" "${DST_CERT}"
install -m 600 /dev/null "${DST_KEY}"

# Convert to a generic PKCS#8 key (works for RSA/ECDSA)
openssl pkey -in "${SRC_KEY}" -out "${DST_KEY}"
chmod 600 "${DST_KEY}"
chown root:root "${DST_KEY}" "${DST_CERT}"

echo "[+] Detect key type (RSA/ECDSA) and write ipsec.secrets"
KEY_INFO=$(openssl pkey -in "${DST_KEY}" -text -noout 2>/dev/null | head -n 2 || true)
TYPE="RSA"
echo "${KEY_INFO}" | grep -qi "EC Private-Key" && TYPE="ECDSA"

install -m 600 /dev/null /etc/ipsec.secrets
echo 'cheenle : EAP "CheenleVPN2025!"' >> /etc/ipsec.secrets
if [[ "${TYPE}" == "ECDSA" ]]; then
  echo ": ECDSA ${DST_KEY}" >> /etc/ipsec.secrets
else
  echo ": RSA ${DST_KEY}" >> /etc/ipsec.secrets
fi
chmod 600 /etc/ipsec.secrets
chown root:root /etc/ipsec.secrets

echo "[+] Relax AppArmor for strongSwan charon to read /etc/ipsec.d/private/*"
mkdir -p /etc/apparmor.d/local
if ! grep -q "local/usr.lib.ipsec.charon" /etc/apparmor.d/usr.lib.ipsec.charon; then
  echo "#include <local/usr.lib.ipsec.charon>" >> /etc/apparmor.d/usr.lib.ipsec.charon
fi
echo "/etc/ipsec.d/private/* r," > /etc/apparmor.d/local/usr.lib.ipsec.charon
systemctl reload apparmor || true
apparmor_parser -r /etc/apparmor.d/usr.lib.ipsec.charon || true

echo "[+] Restart strongSwan and show status"
ipsec rereadsecrets || true
ipsec restart || systemctl restart strongswan-starter || true

echo "--- LISTCERTS (expect has private key) ---"
ipsec listcerts | sed -n '1,200p' | sed -n "/${DOMAIN}/,+8p" || true

echo "--- STATUSALL ---"
ipsec statusall | sed -n '1,140p' || true

echo "--- SYSLOG (tail) ---"
grep -iE 'charon|ike|eap' /var/log/syslog | tail -n 80 || true

echo "[+] Done"


#!/usr/bin/env bash
set -euo pipefail

DOMAIN="www.vlsc.net"
LIVE_DIR="/etc/letsencrypt/live/${DOMAIN}"
DST_KEY="/etc/ipsec.d/private/serverKey.pem"
DST_CERT="/etc/ipsec.d/certs/serverCert.pem"

echo "[1/6] Copy cert and key as regular files"
install -m 644 "${LIVE_DIR}/fullchain.pem" "${DST_CERT}"
install -m 600 "${LIVE_DIR}/privkey.pem"   "${DST_KEY}"
chown root:root "${DST_CERT}" "${DST_KEY}"

echo "[2/6] Normalize private key format"
# Try PKCS#8 generic conversion
tmpkey=$(mktemp)
openssl pkey -in "${DST_KEY}" -out "${tmpkey}"
install -m 600 "${tmpkey}" "${DST_KEY}"
rm -f "${tmpkey}"

echo "[3/6] Detect key type"
TYPE="RSA"
if openssl pkey -in "${DST_KEY}" -text -noout 2>/dev/null | head -n1 | grep -qi "EC Private-Key"; then
  TYPE="ECDSA"
fi
echo "Detected TYPE=${TYPE}"

echo "[4/6] Write /etc/ipsec.secrets"
install -m 600 /dev/null /etc/ipsec.secrets
echo 'cheenle : EAP "CheenleVPN2025!"' >> /etc/ipsec.secrets
if [[ "${TYPE}" == "ECDSA" ]]; then
  echo ": ECDSA ${DST_KEY}" >> /etc/ipsec.secrets
else
  echo ": RSA ${DST_KEY}" >> /etc/ipsec.secrets
fi
chmod 600 /etc/ipsec.secrets; chown root:root /etc/ipsec.secrets
sed -n '1,20p' /etc/ipsec.secrets

echo "[5/6] AppArmor allow charon to read /etc/ipsec.d/private/*"
mkdir -p /etc/apparmor.d/local
grep -q 'local/usr.lib.ipsec.charon' /etc/apparmor.d/usr.lib.ipsec.charon || echo '#include <local/usr.lib.ipsec.charon>' >> /etc/apparmor.d/usr.lib.ipsec.charon
echo '/etc/ipsec.d/private/* r,' > /etc/apparmor.d/local/usr.lib.ipsec.charon
systemctl reload apparmor || true
apparmor_parser -r /etc/apparmor.d/usr.lib.ipsec.charon || true

echo "[6/6] Restart strongSwan and show status"
ipsec rereadsecrets || true
ipsec restart || systemctl restart strongswan-starter || true

echo "--- CERT SECTION (expect has private key) ---"
ipsec listcerts | sed -n "/${DOMAIN}/,+8p" || true
echo "--- STATUSALL ---"
ipsec statusall | sed -n '1,140p' || true


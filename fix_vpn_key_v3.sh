#!/usr/bin/env bash
set -euo pipefail

DOMAIN="www.vlsc.net"
LIVE_DIR="/etc/letsencrypt/live/${DOMAIN}"
SRC_KEY="${LIVE_DIR}/privkey.pem"
SRC_CERT="${LIVE_DIR}/fullchain.pem"
DST_KEY="/etc/ipsec.d/private/serverKey.pem"
DST_CERT="/etc/ipsec.d/certs/serverCert.pem"

echo "[1/5] Copy cert and key as regular files (no conversion)"
install -m 644 "${SRC_CERT}" "${DST_CERT}"
install -m 600 "${SRC_KEY}"  "${DST_KEY}"
chown root:root "${DST_CERT}" "${DST_KEY}"
ls -l "${DST_KEY}" "${DST_CERT}"

echo "[2/5] Detect key type via openssl"
HDR=$(openssl pkey -in "${DST_KEY}" -text -noout 2>/dev/null | head -n1 || true)
echo "KEY_HDR=${HDR}"
TYPE="RSA"
echo "${HDR}" | grep -qi 'EC Private-Key' && TYPE="ECDSA"
echo "Detected TYPE=${TYPE}"

echo "[3/5] Write /etc/ipsec.secrets (EAP + private key entry)"
install -m 600 /dev/null /etc/ipsec.secrets
echo 'cheenle : EAP "CheenleVPN2025!"' >> /etc/ipsec.secrets
echo ": ${TYPE} ${DST_KEY}" >> /etc/ipsec.secrets
chmod 600 /etc/ipsec.secrets; chown root:root /etc/ipsec.secrets
sed -n '1,20p' /etc/ipsec.secrets

echo "[4/5] Allow AppArmor to read /etc/ipsec.d/private/*"
mkdir -p /etc/apparmor.d/local
grep -q 'local/usr.lib.ipsec.charon' /etc/apparmor.d/usr.lib.ipsec.charon || echo '#include <local/usr.lib.ipsec.charon>' >> /etc/apparmor.d/usr.lib.ipsec.charon
echo '/etc/ipsec.d/private/* r,' > /etc/apparmor.d/local/usr.lib.ipsec.charon
systemctl reload apparmor || true
apparmor_parser -r /etc/apparmor.d/usr.lib.ipsec.charon || true

echo "[5/5] Restart strongSwan and show status"
ipsec rereadsecrets || true
ipsec restart || systemctl restart strongswan-starter || true
echo '--- LISTCERTS (expect has private key) ---'
ipsec listcerts | sed -n "/${DOMAIN}/,+10p" || true
echo '--- STATUSALL ---'
ipsec statusall | sed -n '1,160p' || true


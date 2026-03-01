#!/usr/bin/env bash
set -euo pipefail

DOMAIN="www.vlsc.net"
ARCH_DIR="/etc/letsencrypt/archive/${DOMAIN}"
DST_KEY="/etc/ipsec.d/private/serverKey.pem"
DST_CERT="/etc/ipsec.d/certs/serverCert.pem"

echo "[1/6] Find latest archive key/cert"
KEY=$(ls -1 ${ARCH_DIR}/privkey*.pem | sort -V | tail -n1)
CERT=$(ls -1 ${ARCH_DIR}/fullchain*.pem | sort -V | tail -n1)
echo "KEY=$KEY"
echo "CERT=$CERT"

echo "[2/6] Copy as regular files (no conversion)"
install -m 644 "$CERT" "$DST_CERT"
install -m 600 "$KEY"  "$DST_KEY"
chown root:root "$DST_CERT" "$DST_KEY"
ls -l "$DST_KEY" "$DST_CERT"

echo "[3/6] Detect key type"
HDR=$(openssl pkey -in "$DST_KEY" -text -noout 2>/dev/null | head -n1 || true)
echo "KEY_HDR=$HDR"
KEYTYPE=RSA
echo "$HDR" | grep -qi 'EC Private-Key' && KEYTYPE=ECDSA
echo "KEYTYPE=$KEYTYPE"

echo "[4/6] Write /etc/ipsec.secrets"
install -m 600 /dev/null /etc/ipsec.secrets
echo 'cheenle : EAP "CheenleVPN2025!"' >> /etc/ipsec.secrets
echo ": $KEYTYPE $DST_KEY" >> /etc/ipsec.secrets
chmod 600 /etc/ipsec.secrets
chown root:root /etc/ipsec.secrets
sed -n '1,20p' /etc/ipsec.secrets

echo "[5/6] AppArmor allow read private keys"
mkdir -p /etc/apparmor.d/local
grep -q 'local/usr.lib.ipsec.charon' /etc/apparmor.d/usr.lib.ipsec.charon || echo '#include <local/usr.lib.ipsec.charon>' >> /etc/apparmor.d/usr.lib.ipsec.charon
echo '/etc/ipsec.d/private/* r,' > /etc/apparmor.d/local/usr.lib.ipsec.charon
systemctl reload apparmor || true
apparmor_parser -r /etc/apparmor.d/usr.lib.ipsec.charon || true

echo "[6/6] Restart strongSwan and show status"
ipsec rereadsecrets || true
ipsec restart || systemctl restart strongswan-starter || true
echo '--- LISTCERTS (expect has private key) ---'
ipsec listcerts | sed -n "/${DOMAIN}/,+12p" || true
echo '--- STATUSALL ---'
ipsec statusall | sed -n '1,160p' || true
echo '--- SYSLOG TAIL ---'
grep -iE 'charon|ike|eap|private key' /var/log/syslog | tail -n 120 || true


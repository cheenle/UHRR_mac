#!/usr/bin/env bash
set -euo pipefail

DOMAIN="www.vlsc.net"
ARCH_DIR="/etc/letsencrypt/archive/${DOMAIN}"
CUR_CERT="/etc/ipsec.d/certs/serverCert.pem"
DST_KEY="/etc/ipsec.d/private/serverKey.pem"

echo "[1/6] Compute current certificate public key fingerprint"
CERT_FP=$(openssl x509 -in "${CUR_CERT}" -pubkey -noout | openssl sha256 | awk '{print $2}')
echo "CERT_FP=${CERT_FP}"

echo "[2/6] Search matching private key in ${ARCH_DIR}"
MATCH_KEY=""
for k in "${ARCH_DIR}"/privkey*.pem; do
  [[ -f "$k" ]] || continue
  KEY_FP=$(openssl pkey -in "$k" -pubout 2>/dev/null | openssl sha256 | awk '{print $2}') || KEY_FP=""
  if [[ -n "${KEY_FP}" && "${KEY_FP}" == "${CERT_FP}" ]]; then
    MATCH_KEY="$k"
    echo "Matched key: $MATCH_KEY"
    break
  fi
done

if [[ -z "${MATCH_KEY}" ]]; then
  echo "[FATAL] No matching private key found in archive for current certificate" >&2
  exit 1
fi

echo "[3/6] Install matching key as regular file"
install -m 600 "$MATCH_KEY" "$DST_KEY"
chown root:root "$DST_KEY"
ls -l "$DST_KEY"

echo "[4/6] Write ipsec.secrets with ECDSA (LE ECDSA certs typical)"
install -m 600 /dev/null /etc/ipsec.secrets
echo 'cheenle : EAP "CheenleVPN2025!"' >> /etc/ipsec.secrets
echo ": ECDSA ${DST_KEY}" >> /etc/ipsec.secrets
chmod 600 /etc/ipsec.secrets
chown root:root /etc/ipsec.secrets
sed -n '1,20p' /etc/ipsec.secrets

echo "[5/6] Ensure AppArmor allows reading private key and restart"
mkdir -p /etc/apparmor.d/local
grep -q 'local/usr.lib.ipsec.charon' /etc/apparmor.d/usr.lib.ipsec.charon || echo '#include <local/usr.lib.ipsec.charon>' >> /etc/apparmor.d/usr.lib.ipsec.charon
echo '/etc/ipsec.d/private/* r,' > /etc/apparmor.d/local/usr.lib.ipsec.charon
systemctl reload apparmor || true
apparmor_parser -r /etc/apparmor.d/usr.lib.ipsec.charon || true

echo "[6/6] Restart strongSwan and verify"
ipsec rereadsecrets || true
ipsec restart || systemctl restart strongswan-starter || true
echo '--- LISTCERTS (expect has private key) ---'
ipsec listcerts | sed -n "/${DOMAIN}/,+12p" || true
echo '--- STATUSALL ---'
ipsec statusall | sed -n '1,160p' || true


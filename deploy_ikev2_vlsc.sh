#!/usr/bin/env bash

set -euo pipefail

# One-key IKEv2 (strongSwan) server setup for domain www.vlsc.net
# - IKEv2 + EAP-MSCHAPv2
# - Let's Encrypt certificate (HTTP-01 on port 80)
# - NAT + IP forwarding, UFW opening 500/udp and 4500/udp
# - Works on Ubuntu/Debian

DOMAIN="www.vlsc.net"
VPN_POOL_V4="10.99.0.0/24"
EAP_USER="${EAP_USER:-}"
EAP_PASS="${EAP_PASS:-}"

require_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "[FATAL] 请以 root 身份运行 (sudo -i / sudo bash)" >&2
    exit 1
  fi
}

detect_os() {
  if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS_ID=${ID:-}
  fi
  case "${OS_ID}" in
    ubuntu|debian)
      ;;
    *)
      echo "[FATAL] 仅支持 Ubuntu/Debian。检测到: ${OS_ID:-unknown}" >&2
      exit 1
      ;;
  esac
}

ensure_packages() {
  apt-get update
  # strongSwan + EAP-MSCHAPv2 plugin
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    strongswan strongswan-pki libcharon-extra-plugins \
    certbot \
    iptables \
    ufw jq curl
}

obtain_certificate() {
  # Ensure 80/tcp open temporarily for HTTP-01
  ufw allow 80/tcp || true
  systemctl stop nginx || true
  systemctl stop apache2 || true
  # Acquire/renew certificate
  if [[ -d "/etc/letsencrypt/live/${DOMAIN}" ]]; then
    certbot renew --quiet || certbot renew || true
  else
    certbot certonly --standalone -d "${DOMAIN}" --agree-tos -m "admin@${DOMAIN}" --non-interactive || {
      echo "[FATAL] 申请证书失败，请确认域名解析到本机并 80 端口可访问。" >&2
      exit 1
    }
  fi
}

link_cert_for_strongswan() {
  mkdir -p /etc/ipsec.d/certs /etc/ipsec.d/private
  local live="/etc/letsencrypt/live/${DOMAIN}"
  if [[ ! -f "${live}/fullchain.pem" || ! -f "${live}/privkey.pem" ]]; then
    echo "[FATAL] 缺少证书文件 ${live}/fullchain.pem 或 privkey.pem" >&2
    exit 1
  fi
  ln -sf "${live}/fullchain.pem" /etc/ipsec.d/certs/serverCert.pem
  ln -sf "${live}/privkey.pem" /etc/ipsec.d/private/serverKey.pem
  chmod 600 /etc/ipsec.d/private/serverKey.pem || true
}

generate_credentials() {
  if [[ -z "${EAP_USER}" ]]; then
    EAP_USER="cheenle"
  fi
  if [[ -z "${EAP_PASS}" ]]; then
    # generate a 20-char random base64 (strip non-alnum)
    EAP_PASS=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20)
  fi
  echo "[INFO] 将创建 EAP 账户: ${EAP_USER}"
}

configure_ipsec() {
  cat >/etc/ipsec.conf <<EOF
config setup
  uniqueids=never

conn ikev2-eap
  auto=add
  type=tunnel
  keyexchange=ikev2
  ike=aes256-sha256-modp2048,aes256-sha256-ecp256!
  esp=aes256-sha256,aes256gcm16!
  fragmentation=yes
  rekey=no
  dpdaction=clear
  dpddelay=300s
  compress=no

  left=%any
  leftid=@${DOMAIN}
  leftcert=serverCert.pem
  leftsendcert=always
  leftauth=pubkey
  leftsubnet=0.0.0.0/0

  right=%any
  rightauth=eap-mschapv2
  rightsourceip=${VPN_POOL_V4}
  rightsendcert=never
  eap_identity=%identity
EOF

  # EAP credentials
  # Format: username : EAP "password"
  # Preserve other lines if exist
  if ! grep -q "^${EAP_USER} : EAP" /etc/ipsec.secrets 2>/dev/null; then
    sed -i '/: EAP "/d' /etc/ipsec.secrets 2>/dev/null || true
    echo "${EAP_USER} : EAP \"${EAP_PASS}\"" >> /etc/ipsec.secrets
  else
    sed -i "s#^${EAP_USER} : EAP \".*\"#${EAP_USER} : EAP \"${EAP_PASS}\"#" /etc/ipsec.secrets
  fi
  chmod 600 /etc/ipsec.secrets || true
}

enable_forwarding_and_nat() {
  # IP forwarding via sysctl
  cat >/etc/sysctl.d/99-ikev2.conf <<EOF
net.ipv4.ip_forward=1
net.ipv4.conf.all.accept_redirects=0
net.ipv4.conf.all.send_redirects=0
net.ipv4.conf.default.rp_filter=0
EOF
  sysctl --system >/dev/null

  # Determine default interface
  local iface
  iface=$(ip route show default 2>/dev/null | awk '/default/ {print $5; exit}')
  if [[ -z "${iface:-}" ]]; then
    echo "[FATAL] 无法自动检测默认出口网卡" >&2
    exit 1
  fi

  # Configure UFW for NAT and forwarding persistently
  sed -i 's/^#\?DEFAULT_FORWARD_POLICY=.*/DEFAULT_FORWARD_POLICY="ACCEPT"/' /etc/default/ufw

  # Insert NAT section in /etc/ufw/before.rules if not present
  if ! grep -q "# BEGIN VLSC IKEv2 NAT" /etc/ufw/before.rules 2>/dev/null; then
    tmpfile=$(mktemp)
    {
      echo "# BEGIN VLSC IKEv2 NAT"
      echo "*nat"
      echo ":POSTROUTING ACCEPT [0:0]"
      echo "-A POSTROUTING -s ${VPN_POOL_V4} -o ${iface} -j MASQUERADE"
      echo "COMMIT"
      echo "# END VLSC IKEv2 NAT"
      cat /etc/ufw/before.rules
    } >"${tmpfile}"
    mv "${tmpfile}" /etc/ufw/before.rules
  fi

  # Ensure forwarding rules in /etc/ufw/before.rules
  if ! grep -q "-A ufw-before-forward -s ${VPN_POOL_V4} -j ACCEPT" /etc/ufw/before.rules; then
    sed -i "/^# End required lines/a -A ufw-before-forward -s ${VPN_POOL_V4} -j ACCEPT\n-A ufw-before-forward -d ${VPN_POOL_V4} -m state --state ESTABLISHED,RELATED -j ACCEPT" /etc/ufw/before.rules
  fi

  # UFW open required ports and enable
  ufw allow 500/udp || true
  ufw allow 4500/udp || true
  yes | ufw enable || true
  ufw reload || true
}

restart_strongswan() {
  systemctl enable strongswan --now
  ipsec restart || systemctl restart strongswan || true
}

print_summary() {
  echo "\n===== IKEv2 服务器就绪 ====="
  echo "域名: ${DOMAIN}"
  echo "证书: /etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
  echo "EAP 用户名: ${EAP_USER}"
  echo "EAP 密码: ${EAP_PASS}"
  echo "地址池: ${VPN_POOL_V4}"
  echo "UDP 500/4500 已放行，已启用 NAT 与转发"
  echo "客户端建议: IKEv2 + EAP-MSCHAPv2，远程 ID ${DOMAIN}，发送所有流量"
}

main() {
  require_root
  detect_os
  ensure_packages
  obtain_certificate
  link_cert_for_strongswan
  generate_credentials
  configure_ipsec
  enable_forwarding_and_nat
  restart_strongswan
  print_summary
}

main "$@"



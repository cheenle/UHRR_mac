#!/usr/bin/env bash
set -euo pipefail

# WireGuard server on UDP 6655 with one client, full-tunnel

PORT=6655
SUBNET_V4=10.77.0.0/24
SERVER_IP_V4=10.77.0.1
CLIENT_IP_V4=10.77.0.2
DNS_V4=1.1.1.1

require_root() { [ "$(id -u)" -eq 0 ] || { echo "Run as root" >&2; exit 1; }; }

detect_iface() {
  IFACE=$(ip -4 route show default 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}')
  [ -n "${IFACE:-}" ] || { echo "Cannot detect WAN iface" >&2; exit 1; }
}

install_packages() {
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y wireguard wireguard-tools iproute2 ufw
}

setup_sysctl_nat() {
  echo 'net.ipv4.ip_forward=1' >/etc/sysctl.d/99-wireguard.conf
  sysctl --system >/dev/null || true
  ufw allow ${PORT}/udp || true
}

generate_keys() {
  umask 077
  mkdir -p /etc/wireguard
  if [ ! -f /etc/wireguard/server_privatekey ]; then
    wg genkey | tee /etc/wireguard/server_privatekey | wg pubkey >/etc/wireguard/server_publickey
  fi
  SERVER_PRIV=$(cat /etc/wireguard/server_privatekey)
  SERVER_PUB=$(cat /etc/wireguard/server_publickey)
  CLIENT_PRIV=$(wg genkey)
  CLIENT_PUB=$(printf '%s' "$CLIENT_PRIV" | wg pubkey)
}

write_server_config() {
  cat >/etc/wireguard/wg0.conf <<CFG
[Interface]
Address = ${SERVER_IP_V4}/24
ListenPort = ${PORT}
PrivateKey = ${SERVER_PRIV}
PostUp   = iptables -t nat -A POSTROUTING -s ${SUBNET_V4} -o ${IFACE} -j MASQUERADE
PostDown = iptables -t nat -D POSTROUTING -s ${SUBNET_V4} -o ${IFACE} -j MASQUERADE

[Peer]
# client-1
PublicKey = ${CLIENT_PUB}
AllowedIPs = ${CLIENT_IP_V4}/32
PersistentKeepalive = 25
CFG
}

write_client_config() {
  cat >/root/vlsc-wg-client.conf <<CC
[Interface]
PrivateKey = ${CLIENT_PRIV}
Address = ${CLIENT_IP_V4}/24
DNS = ${DNS_V4}

[Peer]
PublicKey = ${SERVER_PUB}
Endpoint = www.vlsc.net:${PORT}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
CC
}

start_service() {
  systemctl enable wg-quick@wg0 --now || (systemctl restart wg-quick@wg0 || true)
  wg show || true
}

main() {
  require_root
  detect_iface
  install_packages
  setup_sysctl_nat
  generate_keys
  write_server_config
  write_client_config
  start_service
  echo "Client config at /root/vlsc-wg-client.conf"
}

main "$@"



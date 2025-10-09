#!/usr/bin/env bash
set -euo pipefail

WG_CONF_SRC="/Users/cheenle/UHRR/UHRR_mac/vlsc-wg-client.conf"
WG_DIR="/usr/local/etc/wireguard"
WG_NAME="wg0"

if ! command -v wg >/dev/null 2>&1 || ! command -v wg-quick >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    brew install wireguard-tools
  else
    echo "未检测到 Homebrew，请先安装 Homebrew 后重试" >&2
    exit 1
  fi
fi

sudo mkdir -p "$WG_DIR"
sudo cp -f "$WG_CONF_SRC" "$WG_DIR/$WG_NAME.conf"
sudo chmod 600 "$WG_DIR/$WG_NAME.conf"

sudo wg-quick up "$WG_NAME" || true

echo "=== wg status ==="
sudo wg show || true

echo "=== IPv4 egress ==="
curl -4 -m 5 ifconfig.me 2>/dev/null || true


#!/usr/bin/env bash
set -euo pipefail

CONFIG_SRC="/Users/cheenle/UHRR/UHRR_mac/vlsc-wg-client.conf"
WG_DIR="/usr/local/etc/wireguard"
WG_NAME="wg0"

echo "[1/4] 检查并安装 wireguard-tools"
if ! command -v wg >/dev/null 2>&1 || ! command -v wg-quick >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    brew install wireguard-tools
  else
    echo "未检测到 Homebrew，请先安装 Homebrew 再重试：/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"" >&2
    exit 1
  fi
fi

echo "[2/4] 准备配置目录并复制客户端配置"
sudo mkdir -p "${WG_DIR}"
if [ ! -f "${CONFIG_SRC}" ]; then
  echo "找不到配置文件：${CONFIG_SRC}" >&2
  exit 1
fi
sudo cp -f "${CONFIG_SRC}" "${WG_DIR}/${WG_NAME}.conf"
sudo chmod 600 "${WG_DIR}/${WG_NAME}.conf"

echo "[3/4] 启动 WireGuard 隧道 (${WG_NAME})"
if sudo wg-quick down "${WG_NAME}" >/dev/null 2>&1; then
  echo "已关闭旧会话"
fi
sudo wg-quick up "${WG_NAME}"

echo "[4/4] 验证状态"
sudo wg show || true
echo "出口IP(IPv4)："
curl -4 -m 5 ifconfig.me 2>/dev/null || echo "curl 失败"
echo
echo "默认路由(前20行)："
netstat -rn | head -n 20 || true
echo "如需断开：sudo wg-quick down ${WG_NAME}"



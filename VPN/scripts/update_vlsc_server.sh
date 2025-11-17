#!/usr/bin/env bash
# 服务器端配置更新脚本
# 将WireGuard端口从9100更新为9200

set -euo pipefail

SERVER_HOST="www.vlsc.net"
SERVER_USER="cheenle"
SERVER_PORT_SSH="22"

echo "=== 更新VLSC服务器配置 ==="
echo "服务器: $SERVER_HOST"
echo "用户: $SERVER_USER"
echo

# 检查SSH连接
echo "[1/5] 检查SSH连接..."
if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "$SERVER_USER@$SERVER_HOST" "echo 'SSH连接成功'"; then
    echo "SSH连接失败，请检查网络连接和服务器状态"
    exit 1
fi

# 备份当前配置
echo "[2/5] 备份当前WireGuard配置..."
ssh "$SERVER_USER@$SERVER_HOST" "sudo cp /etc/wireguard/wg0.conf /etc/wireguard/wg0.conf.backup.\$(date +%Y%m%d_%H%M%S)"

# 更新服务器端配置文件
echo "[3/5] 更新服务器端配置文件..."
ssh "$SERVER_USER@$SERVER_HOST" "sudo sed -i 's/ListenPort = 9100/ListenPort = 9200/g' /etc/wireguard/wg0.conf"

# 更新防火墙规则
echo "[4/5] 更新防火墙规则..."
ssh "$SERVER_USER@$SERVER_HOST" "sudo ufw delete allow 9100/udp 2>/dev/null || true"
ssh "$SERVER_USER@$SERVER_HOST" "sudo ufw allow 9200/udp"

# 重启WireGuard服务
echo "[5/5] 重启WireGuard服务..."
ssh "$SERVER_USER@$SERVER_HOST" "sudo systemctl restart wg-quick@wg0"

# 验证配置
echo "=== 验证配置 ==="
echo "WireGuard状态:"
ssh "$SERVER_USER@$SERVER_HOST" "sudo wg show"
echo
echo "监听端口:"
ssh "$SERVER_USER@$SERVER_HOST" "sudo netstat -tuln | grep 9200 || echo '端口9200未在监听'"
echo
echo "服务器配置更新完成！"

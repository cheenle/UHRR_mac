#!/usr/bin/env bash
# OpenWrt设备配置更新脚本
# 将WireGuard端点端口从8989更新为9093

set -euo pipefail

OPENWRT_IP="192.168.1.6"
OPENWRT_USER="root"
OPENWRT_PASS="xy.cheenle"

echo "=== 更新OpenWrt设备配置 ==="
echo "设备IP: $OPENWRT_IP"
echo "用户: $OPENWRT_USER"
echo

# 检查设备是否在线
echo "[1/6] 检查设备在线状态..."
if ! ping -c 1 -W 10 "$OPENWRT_IP" >/dev/null 2>&1; then
    echo "错误: 无法连接到OpenWrt设备 $OPENWRT_IP"
    exit 1
fi

echo "设备在线"

# 检查SSH连接
echo "[2/6] 检查SSH连接..."
if ! sshpass -p "$OPENWRT_PASS" ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$OPENWRT_USER@$OPENWRT_IP" "echo 'SSH连接成功'"; then
    echo "SSH连接失败，请检查凭据和网络连接"
    exit 1
fi

# 备份当前配置
echo "[3/6] 备份当前网络配置..."
sshpass -p "$OPENWRT_PASS" ssh "$OPENWRT_USER@$OPENWRT_IP" "cp /etc/config/network /etc/config/network.backup.\$(date +%Y%m%d_%H%M%S)"

# 更新WireGuard端点端口
echo "[4/6] 更新WireGuard端点端口..."
sshpass -p "$OPENWRT_PASS" ssh "$OPENWRT_USER@$OPENWRT_IP" "uci set network.wg0_peer.endpoint_port='9100'"
sshpass -p "$OPENWRT_PASS" ssh "$OPENWRT_USER@$OPENWRT_IP" "uci commit network"

# 更新路由表
echo "[5/6] 更新路由表..."
sshpass -p "$OPENWRT_PASS" ssh "$OPENWRT_USER@$OPENWRT_IP" "ip route del default 2>/dev/null || true"
sshpass -p "$OPENWRT_PASS" ssh "$OPENWRT_USER@$OPENWRT_IP" "sleep 2"
sshpass -p "$OPENWRT_PASS" ssh "$OPENWRT_USER@$OPENWRT_IP" "ip route add default dev wg0"

# 重启网络接口
echo "[6/6] 重启网络接口..."
sshpass -p "$OPENWRT_PASS" ssh "$OPENWRT_USER@$OPENWRT_IP" "ifdown wg0 2>/dev/null || true"
sshpass -p "$OPENWRT_PASS" ssh "$OPENWRT_USER@$OPENWRT_IP" "sleep 2"
sshpass -p "$OPENWRT_PASS" ssh "$OPENWRT_USER@$OPENWRT_IP" "ifup wg0"

# 验证配置
echo "=== 验证配置 ==="
echo "WireGuard状态:"
sshpass -p "$OPENWRT_PASS" ssh "$OPENWRT_USER@$OPENWRT_IP" "wg show"
echo
echo "路由表:"
sshpass -p "$OPENWRT_PASS" ssh "$OPENWRT_USER@$OPENWRT_IP" "ip route show | grep wg0 || echo '未找到wg0相关路由'"
echo
echo "OpenWrt设备配置更新完成！"

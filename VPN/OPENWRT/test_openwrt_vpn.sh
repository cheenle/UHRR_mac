#!/bin/bash
# OpenWrt VPN 完整测试脚本

set -euo pipefail

OPENWRT_IP="192.168.1.6"
OPENWRT_PASS="xy.cheenle"

echo "=== OpenWrt VPN 完整测试 ==="

# 等待设备上线
echo "[1/6] 等待 OpenWrt 设备上线..."
for i in {1..10}; do
    if ping -c 1 -W 1 $OPENWRT_IP >/dev/null 2>&1; then
        echo "设备已上线"
        break
    fi
    echo "等待中... ($i/10)"
    sleep 2
done

if ! ping -c 1 -W 1 $OPENWRT_IP >/dev/null 2>&1; then
    echo "错误: 无法连接到 OpenWrt 设备 $OPENWRT_IP"
    exit 1
fi

echo "[2/6] 检查 VPN 连接状态..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
echo '--- WireGuard 状态 ---'
wg show

echo '--- 路由表 ---'
ip route show

echo '--- 网络接口 ---'
ip addr show wg0
ip addr show br-lan
"

echo "[3/6] 测试基础连接..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
echo '--- 测试 VPN 服务器连接 ---'
ping -c 2 10.77.0.1

echo '--- 测试外网连接 ---'
ping -c 2 8.8.8.8

echo '--- 测试 DNS 解析 ---'
nslookup google.com 10.77.0.1
"

echo "[4/6] 测试 HTTP/HTTPS 访问..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
echo '--- 测试 HTTP 访问 ---'
wget -q --timeout=10 -O - http://www.google.com 2>/dev/null | head -c 200 && echo ''

echo '--- 测试 HTTPS 访问 ---'
wget -q --timeout=10 -O - https://www.google.com 2>/dev/null | head -c 200 && echo ''

echo '--- 测试出口 IP ---'
wget -q --timeout=10 -O - http://ifconfig.me 2>/dev/null || echo '无法获取出口 IP'
"

echo "[5/6] 检查 NAT 和防火墙..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
echo '--- NAT 规则 ---'
nft list table nat

echo '--- 转发规则 ---'
nft list table filter

echo '--- IP 转发状态 ---'
cat /proc/sys/net/ipv4/ip_forward
"

echo "[6/6] 测试手机连接建议..."
echo "=== 手机连接测试指南 ==="
echo "1. 手机连接到 OpenWrt WiFi (SSID: 请查看路由器设置)"
echo "2. 检查手机获得的 IP 地址:"
echo "   - 应该是 10.1.1.x 格式"
echo "   - 网关应该是 10.1.1.1"
echo "3. 在手机上测试:"
echo "   - 打开浏览器访问 www.google.com"
echo "   - 检查出口 IP 是否为 VPN 服务器 IP"
echo "4. 如果无法访问，请检查手机 DNS 设置:"
echo "   - 建议设置为 10.77.0.1 或 8.8.8.8"

echo ""
echo "=== 测试完成 ==="
echo "如果所有测试都通过，手机等设备现在应该可以通过 OpenWrt 的 VPN 访问外网了！"

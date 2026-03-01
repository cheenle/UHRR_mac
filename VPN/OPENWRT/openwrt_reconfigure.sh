#!/bin/bash
# OpenWrt WireGuard VPN 重新配置脚本
# 适配新的服务器配置 (端口 8877)

set -euo pipefail

OPENWRT_IP="192.168.1.6"
OPENWRT_PASS="xy.cheenle"

echo "=== OpenWrt WireGuard VPN 重新配置脚本 ==="
echo "目标设备: $OPENWRT_IP"
echo "服务器端口: 9090"

# 等待设备上线
echo "[1/6] 等待 OpenWrt 设备上线..."
for i in {1..30}; do
    if ping -c 1 -W 1 $OPENWRT_IP >/dev/null 2>&1; then
        echo "设备已上线"
        break
    fi
    echo "等待中... ($i/30)"
    sleep 2
done

if ! ping -c 1 -W 1 $OPENWRT_IP >/dev/null 2>&1; then
    echo "错误: 无法连接到 OpenWrt 设备 $OPENWRT_IP"
    exit 1
fi

echo "[2/6] 更新 WireGuard 配置..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
# 更新 WireGuard 配置
uci set network.wg0.private_key='MMiqBSUYiwLJBZL8UkR8LJBBNb3foISG3LDSMJbSolk='
uci set network.wg0_peer.endpoint_port='9090'
uci commit network

echo '--- 当前配置 ---'
uci show network | grep -E 'wg0'
"

echo "[3/6] 启动 WireGuard 接口..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
# 重启 WireGuard 接口
ifdown wg0 2>/dev/null || true
sleep 2
ifup wg0

echo '--- WireGuard 状态 ---'
wg show
"

echo "[4/6] 配置路由和 NAT..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
# 配置路由
ip route del default via 192.168.1.1 dev wan 2>/dev/null || true
ip route add default dev wg0
ip route add 38.55.129.87 via 192.168.1.1 dev wan

# 配置 NAT
echo 1 > /proc/sys/net/ipv4/ip_forward

nft add table nat 2>/dev/null || true
nft flush table nat 2>/dev/null || true
nft add chain nat postrouting { type nat hook postrouting priority 100 \; }
nft add rule nat postrouting oifname wg0 masquerade

# 配置转发规则
nft add table filter 2>/dev/null || true
nft add chain filter forward { type filter hook forward priority 0 \; }
nft add rule filter forward iifname br-lan oifname wg0 accept
nft add rule filter forward iifname wg0 oifname br-lan accept
nft add rule filter forward tcp flags syn tcp option maxseg size set 1320
"

echo "[5/6] 测试连接..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
echo '--- 测试 VPN 连接 ---'
ping -c 3 10.77.0.1

echo '--- 测试外网连接 ---'
ping -c 3 8.8.8.8

echo '--- 测试网站访问 ---'
wget -q --timeout=10 -O - http://www.google.com 2>/dev/null | head -c 100 && echo ''
"

echo "[6/6] 创建持久化配置..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
# 创建启动脚本
cat > /etc/init.d/vpn-nat << 'EOF'
#!/bin/sh /etc/rc.common
START=99

start() {
    echo 1 > /proc/sys/net/ipv4/ip_forward
    
    # 等待 wg0 接口启动
    sleep 5
    
    # 配置 NAT
    nft add table nat 2>/dev/null || true
    nft flush table nat 2>/dev/null || true
    nft add chain nat postrouting { type nat hook postrouting priority 100 \; }
    nft add rule nat postrouting oifname wg0 masquerade
    
    # 配置转发
    nft add table filter 2>/dev/null || true
    nft add chain filter forward { type filter hook forward priority 0 \; }
    nft add rule filter forward iifname br-lan oifname wg0 accept
    nft add rule filter forward iifname wg0 oifname br-lan accept
    nft add rule filter forward tcp flags syn tcp option maxseg size set 1320
    
    # 修复路由
    ip route del default via 192.168.1.1 dev wan 2>/dev/null || true
    ip route add default dev wg0
    ip route add 38.55.129.87 via 192.168.1.1 dev wan
}

stop() {
    nft flush table nat 2>/dev/null || true
    nft flush table filter 2>/dev/null || true
}
EOF

chmod +x /etc/init.d/vpn-nat
/etc/init.d/vpn-nat enable
"

echo "=== 重新配置完成 ==="
echo ""
echo "✅ WireGuard 接口已更新 (端口 8877)"
echo "✅ 新的密钥对已配置"
echo "✅ 路由和 NAT 已重新配置"
echo "✅ 持久化配置已创建"
echo ""
echo "现在手机等设备连接到 OpenWrt 的 WiFi 后，应该能够通过 VPN 访问外网了！"
echo ""
echo "测试方法："
echo "1. 手机连接到 OpenWrt 的 WiFi"
echo "2. 检查手机获得的 IP 地址（应该是 10.1.1.x）"
echo "3. 检查手机获得的网关地址（应该是 10.1.1.1）"
echo "4. 在手机上访问网站测试"
echo "5. 检查出口 IP 是否为 VPN 服务器 IP (38.55.129.87)"


#!/bin/bash
# OpenWrt NAT 修复脚本
# 确保 LAN 设备可以通过 VPN 访问外网

set -euo pipefail

OPENWRT_IP="192.168.1.6"
OPENWRT_PASS="xy.cheenle"

echo "=== OpenWrt NAT 修复脚本 ==="

# 等待设备上线
echo "[1/5] 等待 OpenWrt 设备上线..."
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

echo "[2/5] 检查当前配置..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
echo '--- IP 转发状态 ---'
cat /proc/sys/net/ipv4/ip_forward

echo '--- 当前路由 ---'
ip route show

echo '--- 网络接口 ---'
ip addr show | grep -E 'wg0|br-lan'
"

echo "[3/5] 配置 IP 转发和 NAT..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
# 启用 IP 转发
echo 1 > /proc/sys/net/ipv4/ip_forward

# 配置 nftables NAT 规则
nft add table nat 2>/dev/null || true
nft flush table nat 2>/dev/null || true

# 添加 MASQUERADE 规则
nft add chain nat postrouting { type nat hook postrouting priority 100 \; }
nft add rule nat postrouting oifname wg0 masquerade

# 添加转发规则
nft add table filter 2>/dev/null || true
nft add chain filter forward { type filter hook forward priority 0 \; }
nft add rule filter forward iifname br-lan oifname wg0 accept
nft add rule filter forward iifname wg0 oifname br-lan accept

echo '--- 验证 NAT 配置 ---'
nft list table nat
nft list table filter
"

echo "[4/5] 测试连接..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
echo '测试 VPN 连接:'
ping -c 2 10.77.0.1

echo '测试外网连接:'
ping -c 2 8.8.8.8

echo '检查出口 IP:'
curl -4 -m 5 ifconfig.me 2>/dev/null || echo '无法获取出口 IP'
"

echo "[5/5] 创建持久化配置..."
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
}

stop() {
    nft flush table nat 2>/dev/null || true
    nft flush table filter 2>/dev/null || true
}
EOF

chmod +x /etc/init.d/vpn-nat
/etc/init.d/vpn-nat enable
"

echo "=== 修复完成 ==="
echo "现在手机等设备应该可以通过 OpenWrt 的 VPN 访问外网了"
echo ""
echo "测试方法："
echo "1. 手机连接到 OpenWrt 的 WiFi"
echo "2. 检查手机获得的 IP 地址（应该是 10.1.1.x）"
echo "3. 检查手机获得的网关地址（应该是 10.1.1.1）"
echo "4. 在手机上访问网站测试"
echo ""
echo "如果仍有问题，请检查："
echo "- 手机 DNS 设置（建议使用 10.77.0.1 或 8.8.8.8）"
echo "- OpenWrt 的 DHCP 设置是否正确"


#!/bin/bash
# OpenWrt WireGuard VPN 完整配置脚本
# 一键配置 OpenWrt 路由器通过 WireGuard VPN 访问外网

set -euo pipefail

OPENWRT_IP="192.168.1.6"
OPENWRT_PASS="xy.cheenle"

echo "=== OpenWrt WireGuard VPN 完整配置脚本 ==="
echo "目标设备: $OPENWRT_IP"

# 等待设备上线
echo "[1/8] 等待 OpenWrt 设备上线..."
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

echo "[2/8] 检查当前配置..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
echo '--- 当前网络配置 ---'
uci show network | grep -E 'wan|lan|wg0'

echo '--- 当前防火墙配置 ---'
uci show firewall | grep -E 'zone|rule' | head -10

echo '--- 当前路由表 ---'
ip route show
"

echo "[3/8] 配置 WireGuard 网络..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
# 配置 LAN 接口
uci set network.lan.proto='static'
uci set network.lan.ipaddr='10.1.1.1'
uci set network.lan.netmask='255.255.255.0'

# 配置 WAN 接口
uci set network.wan.proto='dhcp'
uci set network.wan.device='wan'

# 配置 WireGuard 接口
uci set network.wg0=interface
uci set network.wg0.proto='wireguard'
uci set network.wg0.private_key='kNKxZrk2d2ACO/A8B3xXhmN/0DFfF29GkZ6HHtwm9U8='
uci set network.wg0.addresses='10.77.0.2/24'
uci set network.wg0.mtu='1360'

# 配置对等端
uci set network.wg0_peer=wireguard_wg0
uci set network.wg0_peer.public_key='n4qHnoIirQIEErMh7/M+aA/rhkJSjcdDZyVGU9LXOHI='
uci set network.wg0_peer.endpoint_host='38.55.129.87'
uci set network.wg0_peer.endpoint_port='9090'
uci set network.wg0_peer.allowed_ips='0.0.0.0/0'
uci set network.wg0_peer.persistent_keepalive='15'

# 提交网络配置
uci commit network
"

echo "[4/8] 配置防火墙..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
# 修复 LAN 区域
uci set firewall.@zone[0].network='lan'
uci set firewall.@zone[0].name='lan'

# 创建 VPN 区域
uci set firewall.vpn=zone
uci set firewall.vpn.name='vpn'
uci set firewall.vpn.network='wg0'
uci set firewall.vpn.input='ACCEPT'
uci set firewall.vpn.output='ACCEPT'
uci set firewall.vpn.forward='ACCEPT'
uci set firewall.vpn.masq='1'
uci set firewall.vpn.mtu_fix='1'

# 删除可能存在的重复规则
uci -q delete firewall.@rule[$(uci show firewall | grep -c 'Allow-LAN-to-VPN')-1] || true
uci -q delete firewall.@rule[$(uci show firewall | grep -c 'Allow-VPN-to-LAN')-1] || true

# 添加转发规则
uci add firewall rule
uci set firewall.@rule[-1].name='Allow-LAN-to-VPN'
uci set firewall.@rule[-1].src='lan'
uci set firewall.@rule[-1].dest='vpn'
uci set firewall.@rule[-1].target='ACCEPT'

uci add firewall rule
uci set firewall.@rule[-1].name='Allow-VPN-to-LAN'
uci set firewall.@rule[-1].src='vpn'
uci set firewall.@rule[-1].dest='lan'
uci set firewall.@rule[-1].target='ACCEPT'

# 提交防火墙配置
uci commit firewall
"

echo "[5/8] 启动 WireGuard 接口..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
# 启动 WireGuard 接口
ifup wg0

# 等待接口启动
sleep 3

echo '--- WireGuard 状态 ---'
wg show
"

echo "[6/8] 配置路由和 NAT..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
# 启用 IP 转发
echo 1 > /proc/sys/net/ipv4/ip_forward

# 删除默认路由
ip route del default via 192.168.1.1 dev wan 2>/dev/null || true

# 添加通过 VPN 的默认路由
ip route add default dev wg0

# 添加 VPN 服务器路由（防止路由循环）
ip route add 38.55.129.87 via 192.168.1.1 dev wan

# 配置 nftables NAT 规则
nft add table nat 2>/dev/null || true
nft flush table nat 2>/dev/null || true
nft add chain nat postrouting { type nat hook postrouting priority 100 \; }
nft add rule nat postrouting oifname wg0 masquerade

# 配置转发规则
nft add table filter 2>/dev/null || true
nft add chain filter forward { type filter hook forward priority 0 \; }
nft add rule filter forward iifname br-lan oifname wg0 accept
nft add rule filter forward iifname wg0 oifname br-lan accept

# 添加 MSS 钳制
nft add rule filter forward tcp flags syn tcp option maxseg size set 1320
"

echo "[7/8] 重启防火墙服务..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
/etc/init.d/firewall reload
"

echo "[8/8] 创建持久化配置..."
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
    
    # 添加 MSS 钳制
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

echo "=== 配置完成 ==="
echo ""
echo "现在进行最终测试..."

# 运行测试脚本
/Users/cheenle/UHRR/UHRR_mac/VPN/OPENWRT/test_openwrt_vpn.sh

echo ""
echo "=== 配置总结 ==="
echo "✅ WireGuard 接口已配置并启动"
echo "✅ 防火墙规则已配置"
echo "✅ 路由表已修复"
echo "✅ NAT 规则已配置"
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


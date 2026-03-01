#!/bin/bash
# OpenWrt VPN 路由修复脚本
# 解决手机等设备无法通过 VPN 访问外网的问题

set -euo pipefail

OPENWRT_IP="192.168.1.6"
OPENWRT_PASS="xy.cheenle"

echo "=== OpenWrt VPN 路由修复脚本 ==="
echo "目标设备: $OPENWRT_IP"

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

echo "[2/6] 检查当前网络配置..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
echo '--- 网络接口 ---'
uci show network | grep -E 'wan|lan|wg0'

echo '--- 防火墙区域 ---'
uci show firewall | grep -E 'zone|rule' | head -10

echo '--- 路由表 ---'
ip route show | head -10
"

echo "[3/6] 修复防火墙配置..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
# 确保 LAN 区域只包含 LAN 接口
uci set firewall.@zone[0].network='lan'
uci set firewall.@zone[0].name='lan'

# 创建或更新 VPN 区域
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

# 添加 LAN 到 VPN 的转发规则
uci add firewall rule
uci set firewall.@rule[-1].name='Allow-LAN-to-VPN'
uci set firewall.@rule[-1].src='lan'
uci set firewall.@rule[-1].dest='vpn'
uci set firewall.@rule[-1].target='ACCEPT'

# 添加 VPN 到 LAN 的转发规则
uci add firewall rule
uci set firewall.@rule[-1].name='Allow-VPN-to-LAN'
uci set firewall.@rule[-1].src='vpn'
uci set firewall.@rule[-1].dest='lan'
uci set firewall.@rule[-1].target='ACCEPT'

# 提交配置
uci commit firewall
"

echo "[4/6] 重启防火墙服务..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
/etc/init.d/firewall reload
"

echo "[5/6] 检查 NAT 和转发状态..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
echo '--- NAT 规则 ---'
iptables -t nat -L -n -v | head -10

echo '--- 转发规则 ---'
iptables -L FORWARD -n -v | head -10

echo '--- 路由表 ---'
ip route show | head -10
"

echo "[6/6] 测试连接..."
sshpass -p "$OPENWRT_PASS" ssh root@$OPENWRT_IP "
echo '测试 VPN 连接:'
ping -c 2 10.77.0.1 || echo 'VPN 服务器不可达'

echo '测试外网连接:'
ping -c 2 8.8.8.8 || echo '外网不可达'

echo '检查出口 IP:'
curl -4 -m 5 ifconfig.me 2>/dev/null || echo '无法获取出口 IP'
"

echo "=== 修复完成 ==="
echo "现在手机等设备应该可以通过 OpenWrt 的 VPN 访问外网了"
echo "如果仍有问题，请检查："
echo "1. 手机是否获得了正确的网关地址 (10.1.1.1)"
echo "2. DNS 设置是否正确"
echo "3. 防火墙规则是否生效"

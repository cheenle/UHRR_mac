#!/bin/sh
# OpenWrt WireGuard 完整修复脚本

set -e

echo "=== OpenWrt WireGuard 完整修复 ==="

# 停止现有接口
ifdown wg0 2>/dev/null || true
ip link delete wg0 2>/dev/null || true

# 重新创建 WireGuard 接口
echo "[1/4] 创建 WireGuard 接口..."
ip link add dev wg0 type wireguard

# 设置 WireGuard 配置
echo "[2/4] 配置 WireGuard..."
wg set wg0 private-key /etc/wireguard/wg0.conf private-key
wg set wg0 peer n4qHnoIirQIEErMh7/M+aA/rhkJSjcdDZyVGU9LXOHI= endpoint www.vlsc.net:9090 allowed-ips 0.0.0.0/0 persistent-keepalive 25

# 配置 IP 地址
echo "[3/4] 配置 IP 地址..."
ip addr add 10.77.0.2/24 dev wg0
ip link set wg0 up

# 配置路由和防火墙
echo "[4/4] 配置路由和防火墙..."
# 删除原有默认路由
ip route del default 2>/dev/null || true
# 添加 VPN 默认路由
ip route add default via 10.77.0.1 dev wg0
# 保留本地网络路由
ip route add 192.168.1.0/24 via 192.168.1.1 dev wan 2>/dev/null || true
ip route add 10.1.1.0/24 dev br-lan 2>/dev/null || true

# 配置防火墙规则
uci set firewall.@zone[0].network='wan'
uci set firewall.@zone[1].network='lan wg0'
uci commit firewall

# 重启防火墙
/etc/init.d/firewall restart

echo "=== 配置完成 ==="
echo "WireGuard 状态:"
wg show

echo
echo "网络接口:"
ifconfig wg0

echo
echo "路由表:"
ip route show | head -10

echo
echo "测试连接:"
ping -c 3 10.77.0.1 || echo "无法 ping 服务器"
ping -c 3 1.1.1.1 || echo "无法 ping 外网"

echo
echo "外网 IP 测试:"
curl -4 ifconfig.me 2>/dev/null || echo "无法获取外网 IP"

echo
echo "=== 管理命令 ==="
echo "停止: ip link delete wg0"
echo "重启: /tmp/openwrt_wg_fix.sh"
echo "状态: wg show"

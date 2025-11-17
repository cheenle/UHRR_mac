#!/bin/sh
# OpenWrt WireGuard 客户端部署脚本
# 连接到 www.vlsc.net:9090

set -e

# 配置参数
SERVER_ENDPOINT="www.vlsc.net:9090"
SERVER_PUBKEY="YOUR_SERVER_PUBLIC_KEY_HERE"  # 需要替换为实际公钥
CLIENT_PRIVKEY="YOUR_CLIENT_PRIVATE_KEY_HERE"  # 需要替换为实际私钥
CLIENT_IP="10.77.0.2/24"
SERVER_IP="10.77.0.1"

echo "=== OpenWrt WireGuard 客户端部署脚本 ==="
echo "目标服务器: $SERVER_ENDPOINT"
echo

# 检查是否为 root
if [ "$(id -u)" -ne 0 ]; then
    echo "错误: 需要 root 权限运行此脚本"
    exit 1
fi

# 更新软件包列表
echo "[1/8] 更新软件包列表..."
opkg update

# 安装 WireGuard
echo "[2/8] 安装 WireGuard..."
opkg install wireguard-tools kmod-wireguard

# 检查安装是否成功
if ! command -v wg >/dev/null 2>&1; then
    echo "错误: WireGuard 安装失败"
    exit 1
fi

# 创建 WireGuard 配置目录
echo "[3/8] 创建配置目录..."
mkdir -p /etc/wireguard

# 生成客户端密钥对（如果未提供）
if [ "$CLIENT_PRIVKEY" = "YOUR_CLIENT_PRIVATE_KEY_HERE" ]; then
    echo "[4/8] 生成客户端密钥对..."
    CLIENT_PRIVKEY=$(wg genkey)
    CLIENT_PUBKEY=$(echo "$CLIENT_PRIVKEY" | wg pubkey)
    echo "客户端私钥: $CLIENT_PRIVKEY"
    echo "客户端公钥: $CLIENT_PUBKEY"
    echo "请将客户端公钥添加到服务器配置中"
else
    CLIENT_PUBKEY=$(echo "$CLIENT_PRIVKEY" | wg pubkey)
    echo "[4/8] 使用提供的客户端密钥"
fi

# 创建 WireGuard 配置文件
echo "[5/8] 创建 WireGuard 配置..."
cat > /etc/wireguard/wg0.conf << EOF
[Interface]
PrivateKey = $CLIENT_PRIVKEY
Address = $CLIENT_IP
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = $SERVER_PUBKEY
Endpoint = $SERVER_ENDPOINT
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
EOF

# 设置配置文件权限
chmod 600 /etc/wireguard/wg0.conf

# 创建 UCI 配置
echo "[6/8] 创建 UCI 配置..."
uci set network.wg0=interface
uci set network.wg0.proto='wireguard'
uci set network.wg0.private_key="$CLIENT_PRIVKEY"
uci add_list network.wg0.addresses="$CLIENT_IP"
uci set network.wg0.dns='1.1.1.1 8.8.8.8'

# 添加 WireGuard 接口到防火墙区域
echo "[7/8] 配置防火墙..."
uci set firewall.@zone[0].network='wan wg0'
uci set firewall.@zone[1].network='lan wg0'

# 创建 WireGuard 对等点配置
uci set network.wg0_peer=wireguard_wg0
uci set network.wg0_peer.public_key="$SERVER_PUBKEY"
uci set network.wg0_peer.endpoint_host="www.vlsc.net"
uci set network.wg0_peer.endpoint_port="9090"
uci set network.wg0_peer.allowed_ips="0.0.0.0/0"
uci set network.wg0_peer.persistent_keepalive="25"

# 提交 UCI 配置
uci commit network
uci commit firewall

# 启动 WireGuard 接口
echo "[8/8] 启动 WireGuard 接口..."
ifup wg0

# 检查接口状态
echo
echo "=== 部署完成 ==="
echo "WireGuard 接口状态:"
wg show

echo
echo "网络接口状态:"
ip addr show wg0 2>/dev/null || ifconfig wg0 2>/dev/null || echo "接口 wg0 未找到"

echo
echo "路由表:"
ip route | grep wg0 || route | grep wg0 || echo "未找到 wg0 相关路由"

echo
echo "=== 测试连接 ==="
echo "测试 DNS 解析:"
nslookup google.com 1.1.1.1 || echo "DNS 解析失败"

echo
echo "测试外网连接:"
ping -c 3 1.1.1.1 || echo "外网连接失败"

echo
echo "=== 管理命令 ==="
echo "启动接口: ifup wg0"
echo "停止接口: ifdown wg0"
echo "重启接口: ifdown wg0 && ifup wg0"
echo "查看状态: wg show"
echo "查看日志: logread | grep wireguard"

echo
echo "=== 重要提醒 ==="
echo "1. 请将客户端公钥添加到服务器配置中:"
echo "   $CLIENT_PUBKEY"
echo
echo "2. 如果连接失败，请检查:"
echo "   - 服务器防火墙是否开放 9090/UDP 端口"
echo "   - 服务器 WireGuard 配置是否正确"
echo "   - 网络连接是否正常"
echo
echo "3. 如需修改配置，编辑: /etc/wireguard/wg0.conf"
echo "   然后运行: ifdown wg0 && ifup wg0"

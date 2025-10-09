# OpenWrt WireGuard VPN 配置指南

## 概述

本指南详细说明了如何在 OpenWrt 路由器上配置 WireGuard VPN，使连接到路由器的设备（如手机、电脑）能够通过 VPN 访问外网。

## 网络拓扑

```
互联网 ←→ VPN服务器(www.vlsc.net:8866) ←→ OpenWrt路由器(192.168.1.6) ←→ 手机/电脑(10.1.1.x)
```

- **VPN 服务器**: 38.55.129.87:8877
- **OpenWrt 内网**: 10.1.1.0/24 (网关: 10.1.1.1)
- **VPN 内网**: 10.77.0.0/24 (OpenWrt: 10.77.0.2, 服务器: 10.77.0.1)

## 配置步骤

### 1. 基础网络配置

```bash
# 配置 LAN 接口
uci set network.lan.proto='static'
uci set network.lan.ipaddr='10.1.1.1'
uci set network.lan.netmask='255.255.255.0'

# 配置 WAN 接口
uci set network.wan.proto='dhcp'
uci set network.wan.device='wan'
```

### 2. WireGuard 配置

```bash
# 创建 WireGuard 接口
uci set network.wg0=interface
uci set network.wg0.proto='wireguard'
uci set network.wg0.private_key='MMiqBSUYiwLJBZL8UkR8LJBBNb3foISG3LDSMJbSolk='
uci set network.wg0.addresses='10.77.0.2/24'
uci set network.wg0.mtu='1360'

# 配置对等端
uci set network.wg0_peer=wireguard_wg0
uci set network.wg0_peer.public_key='n4qHnoIirQIEErMh7/M+aA/rhkJSjcdDZyVGU9LXOHI='
uci set network.wg0_peer.endpoint_host='38.55.129.87'
uci set network.wg0_peer.endpoint_port='8877'
uci set network.wg0_peer.allowed_ips='0.0.0.0/0'
uci set network.wg0_peer.persistent_keepalive='15'
```

### 3. 防火墙配置

```bash
# 修复 LAN 区域（只包含 LAN 接口）
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
```

### 4. 路由配置

```bash
# 删除默认路由
ip route del default via 192.168.1.1 dev wan

# 添加通过 VPN 的默认路由
ip route add default dev wg0

# 添加 VPN 服务器路由（防止路由循环）
ip route add 38.55.129.87 via 192.168.1.1 dev wan
```

### 5. NAT 和转发配置

```bash
# 启用 IP 转发
echo 1 > /proc/sys/net/ipv4/ip_forward

# 配置 nftables NAT 规则
nft add table nat
nft add chain nat postrouting { type nat hook postrouting priority 100 \; }
nft add rule nat postrouting oifname wg0 masquerade

# 配置转发规则
nft add table filter
nft add chain filter forward { type filter hook forward priority 0 \; }
nft add rule filter forward iifname br-lan oifname wg0 accept
nft add rule filter forward iifname wg0 oifname br-lan accept

# 添加 MSS 钳制（防止分片问题）
nft add rule filter forward tcp flags syn tcp option maxseg size set 1320
```

## 关键配置要点

### 1. 路由配置
- **默认路由必须指向 wg0**，而不是 wan
- **必须添加 VPN 服务器路由**，防止路由循环
- **MTU 设置为 1360**，避免分片问题

### 2. 防火墙配置
- **LAN 区域只包含 LAN 接口**，不能包含 wan 或 wg0
- **VPN 区域独立配置**，包含 wg0 接口
- **必须启用 masq 和 mtu_fix**

### 3. NAT 配置
- **必须配置 MASQUERADE**，让 LAN 设备通过 VPN 访问外网
- **必须配置转发规则**，允许 LAN 和 VPN 之间的流量

### 4. MTU 和 MSS
- **接口 MTU: 1360**
- **MSS 钳制: 1320**，防止 TCP 分片问题

## 常见问题

### 1. 手机无法访问外网
**原因**: 路由配置错误，默认路由指向 wan 而不是 wg0
**解决**: 确保默认路由指向 wg0 接口

### 2. 网站无法加载
**原因**: MTU 分片问题
**解决**: 设置正确的 MTU 和 MSS 钳制

### 3. DNS 解析失败
**原因**: DNS 服务器配置错误
**解决**: 使用 VPN 服务器的 DNS (10.77.0.1) 或公共 DNS (8.8.8.8)

### 4. 连接不稳定
**原因**: 缺少持久化配置
**解决**: 创建启动脚本，确保重启后配置仍然有效

## 验证方法

1. **检查 VPN 连接**:
   ```bash
   wg show
   ping 10.77.0.1
   ```

2. **检查路由**:
   ```bash
   ip route show
   # 默认路由应该指向 wg0
   ```

3. **检查出口 IP**:
   ```bash
   curl ifconfig.me
   # 应该显示 VPN 服务器 IP (38.55.129.87)
   ```

4. **测试网站访问**:
   ```bash
   wget -O - http://www.google.com
   ```

## 持久化配置

为了确保重启后配置仍然有效，需要创建启动脚本：

```bash
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
```

## 总结

OpenWrt WireGuard VPN 配置的关键在于：

1. **正确的路由配置** - 默认路由必须指向 VPN 接口
2. **完整的防火墙规则** - LAN 和 VPN 区域必须正确配置
3. **有效的 NAT 配置** - 确保 LAN 设备可以通过 VPN 访问外网
4. **MTU 优化** - 避免分片问题
5. **持久化配置** - 确保重启后配置仍然有效

通过以上配置，连接到 OpenWrt 路由器的所有设备都能够通过 VPN 安全地访问外网。

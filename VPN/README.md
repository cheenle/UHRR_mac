VLSC VPN 子项目

本子项目用于管理 WireGuard VPN（服务器 www.vlsc.net）在本机与 OpenWrt 的配置、使用与运维。

1. 网络拓扑
- 服务器（VPS）：www.vlsc.net
  - WireGuard 接口：wg0
  - 监听端口：8866/UDP
  - 服务端地址：10.77.0.1/24
  - NAT：MASQUERADE 到公网出口
  - 内部 DNS（Unbound）：10.77.0.1:53
- 客户端 A（macOS）：
  - 接口：utunX（wg0）
  - 地址：10.77.0.2/24
  - DNS：10.77.0.1
- 客户端 B（OpenWrt）：
  - 接口：wg0
  - 默认路由：走 wg0
  - 回避路由：38.55.129.87 via 192.168.1.1 dev wan
  - 防火墙：vpn 区域（含 wg0，启用 masq 与 mtu_fix）
  - nft TCPMSS：对 wg0 出口 SYN 设置 MSS=1320

2. 配置清单
- macOS 客户端：`vlsc-wg-client.conf`
  - [Interface] DNS=10.77.0.1，MTU=1360
  - [Peer] Endpoint=www.vlsc.net:8866，AllowedIPs=0.0.0.0/0
- 本地脚本：`VPN/scripts/`
  - `wg-up.sh`：启动 wg0 并显示出口 IP
  - `wg-down.sh`：停止 wg0
  - `wg-status.sh`：查看状态（接口/路由）
  - 如需一键安装+启动，可继续使用仓库根的 `wg_oneclick.sh`
- 服务器：
  - WireGuard 监听 8866/UDP
  - Unbound 监听 10.77.0.1:53，上游 1.1.1.1/8.8.8.8
- OpenWrt：
  - wg0 MTU=1360，Endpoint=…:8866，AllowedIPs=0.0.0.0/0
  - dnsmasq 上游 10.77.0.1
  - 防火墙 vpn zone: masq=1, mtu_fix=1，lan->vpn forwarding
  - nft TCPMSS clamp MSS=1320（仅 wg0 出口）

3. 使用方法（macOS）
- 启动：
  sudo VPN/scripts/wg-up.sh
- 停止：
  sudo VPN/scripts/wg-down.sh
- 查看：
  VPN/scripts/wg-status.sh

4. 使用方法（OpenWrt 摘要）
- 已持久化配置：默认路由走 wg0，上游 DNS 指向 10.77.0.1。
- 重启接口：
  ifdown wg0; ifup wg0

5. 优化要点
- MTU/MSS：建议 MTU=1360，配合 nft TCPMSS=1320。
- 端口：采用 8866/UDP；变更需同步服务器与客户端、并放行防火墙。
- DNS：推荐使用 10.77.0.1（Unbound 缓存）。

6. 排错建议
- `wg show` RX=0：检查服务器 NAT（POSTROUTING MASQUERADE）、FORWARD 规则、内核转发。
- 能 ping 但网页慢/打不开：检查 MTU/MSS 与 `mtu_fix`，必要时下调 MTU 到 1320~1380 区间测试。
- DNS 失败：
  - macOS：确认配置中 DNS=10.77.0.1，重连隧道
  - OpenWrt：确认上游 10.77.0.1，重启 dnsmasq
- 端口变更后：同步修改 Endpoint/ListenPort 与 UFW 规则。

7. 目录结构
- README.md（本文档）
- scripts/（启停与状态脚本）
- archive/（历史脚本收纳）


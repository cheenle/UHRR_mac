# <www.vlsc.net> 服务器迁移 runbook（193.111.30.163 → 203.25.119.168）

> 执行日期：2026-10-01 夜（CST）
> 状态：进行中（S0–S8 已完成，S9 观察期内）
> 触发原因：用户决定把 <www.vlsc.net（含全部> nginx 相关内容）搬到香港新服务器。

> **后续增补（2026-10-04）**：迁移完成后数小时，hub 侧 V0.21 把 Cloud Hub（实例入口 +
> 门户 + 站点）**合并到了这同一台香港机器**——本文 §0 中"`mrrc.vlsc.net` → 47.80.243.9
> （hub，不动）"一行只存续了几个小时，现网 `*.mrrc.vlsc.net` 与 `portal.mrrc.vlsc.net`
> 同样落在 `203.25.119.168`，阿里云 `47.80.243.9` 那次拆分已被取代。现网实况以
> `../../../../mrrc_hub/SDD/12-operational-model.md` §12.8 为准。

## 0. 两端事实基线

| | 旧（源） | 新（目标） |
| --- | --- | --- |
| 地址 | `193.111.30.163`（欧洲） | `203.25.119.168`（香港，xTom AS9312） |
| 访问 | `ssh cheenle@www.vlsc.net`，免密 sudo | `ssh cheenle@203.25.119.168`，免密 sudo |
| OS | Ubuntu 26.04 LTS | Ubuntu 26.04.1 LTS（相同内核 7.0.0-15） |
| nginx | 1.28.3 Ubuntu | 1.28.3 Ubuntu（迁移时新装） |
| certbot | 4.0.0 | 4.0.0 |
| goaccess | 已装 | 1.9.4 |
| 磁盘 | 14G，用 9.5G，**剩 4G** | 14G，用 3.4G，剩 11G |
| 内存 | 907Mi（可用 393Mi，紧张） | 1.9Gi（可用 1.4Gi） |
| 服务器互通 | — | 新→旧 ping 44ms，22 端口通 ✅ |

DNS（阿里云 hichina，TTL ~324s，切换很快）：

- `vlsc.net`、`www.vlsc.net`、`radio1.vlsc.net` → 193.111.30.163（**待切换**）
- `mrrc.vlsc.net` / `test1.mrrc.vlsc.net` → 47.80.243.9（hub，不动）
- `radio.vlsc.net` → 仅 AAAA（家用 IPv6 机，不动）

## 1. 迁什么（"nginx 相关全部都搬"）

| 类别 | 路径 | 大小 |
| --- | --- | --- |
| 站点内容 | `/var/www/vlsc.net/`（mrrc_modern 含 2.9G downloads、mrrc、RJ、mrrc_ft8、blog、rig、efhw、yijing、zh…） | 3.5G |
| 诊断包上传 | `/var/www/support/`、`/var/www/support-modern/` | 1.7M |
| 服务代码 | `/opt/mrrc-support/`、`/opt/mrrc-modern-support/` | 36K |
| feedback | `/home/cheenle/feedback/`（含 feedback.db、呼号库） | 60M |
| 统计 | `/home/cheenle/stats/`（goaccess 报告 + `.htpasswd`） | 1.2M |
| nginx 配置 | `sites-available/{vlsc.net,radio1.conf}`、`conf.d/mrrc-portal-edge-ratelimit.conf`、`nginx.conf`、`/etc/nginx/mrrc-hub-trust.pem` | 190K |
| 证书 | `/etc/letsencrypt/` 全套 | 小 |
| 密钥/环境 | `/etc/{mrrc-support,mrrc-modern-support}.env`、`/etc/yijing/llm.env`（600） | 小 |
| systemd | `support-receiver[-modern]`、`vlsc-feedback`(+db.timer)、`yijing-llm`(+eval.timer) | 小 |
| 脚本/定时 | `/usr/local/bin/update-stats.sh` + root cron（每小时） | 小 |

**不搬**：`/var/www/backups`（用户指定）、unbound、`/home/cheenle/cli`、`.npm`、`/var/www/html`。
8891/8892 的 `-R` 隧道在 Mac 侧（`ssh -R ... cheenle@www.vlsc.net`），跟随 DNS 自动指向新机。

## 2. 顺带修复的历史 bug（迁移前完成）

`/etc/letsencrypt/live/www.vlsc.net` 的证书自 7 月 4 日起续期一直失败，原证书 **2026-10-02 03:17 UTC 到期**。
根因两处（均为 nginx 配置）：

1. 80 口 `return 301` 位于 **server 级** → rewrite 阶段先于 location 匹配执行，`/.well-known/acme-challenge/` 的 location 永远轮不到 → 挑战请求被 301。
2. LE 跟随 301 到 HTTPS 后命中 `location ~ /\. { deny all; }` → **403**（`/.well-known` 被当作隐藏文件拒绝）。

修复：

- 80 口：`location ^~ /.well-known/acme-challenge/`（带 `default_type "text/plain"`）+ 把 301 移入 `location / {}`
- 443 口：`location ~ /\.(?!well-known) { deny all; }`

已强制续期并 reload，线上证书现为 **2026-10-01 15:45 → 2026-12-30 15:45 UTC**，
`certbot renew --dry-run` 全绿（自愈链路恢复）。改前的配置在旧机留有
`/etc/nginx/sites-available/vlsc.net.bak-2026-10-02-004318`。

## 3. 执行步骤

- [x] **S0 止血**：修续期 bug → 强制续期 → reload → 线上验证
- [x] **S1 目标机装环境**：nginx 1.28.3 / certbot 4.0.0 / python3-certbot-nginx / goaccess
- [x] **S2 打通新→旧直连**：新机 ed25519 公钥加入旧机 `authorized_keys`；`sudo rsync` 通道验证
- [x] **S3 数据同步**：rsync（`-aHAX --rsync-path="sudo rsync"`，按名映射属主）全部清单，约 2 分钟
- [x] **S4 落配置**：nginx 配置、letsencrypt、env、systemd 单元、cron；`nginx -t` 通过
- [x] **S5 目标机自测**：全部 location 状态码与旧机逐项对齐（含 `/images/` 403、两个 401、404、405、hub 502）
- [x] **S6 增量同步**：`--delete` 增量零差异；`feedback.db` 用 sqlite backup API 取一致性快照（含 WAL）
- [x] **S7 切 DNS**：2026-10-02 00:55 用户在阿里云改 3 条 A 记录；01:03 五大公共解析器（1.1.1.1 / 8.8.8.8 / 9.9.9.9 / 114 / OpenDNS）全部收敛到新 IP
- [x] **S8 外部验收**：三域名全部落到 203.25.119.168；证书正确；全部路径状态码与切换前基线一致；隧道重连成功（radio1 → 302）
- [x] **S9 观察期**：旧机 nginx 保留服务，写路径服务已停，观察 3–7 天后可下线

### 已取得的验证证据（切换前）

| 检查 | 结果 |
| --- | --- |
| `/var/www/vlsc.net` 全量 checksum 对拍 | **零差异**（427 个文件） |
| 关键目录文件数 | support 36/36、support-modern 10/10、opt 1/1、stats 2/2 |
| `feedback.db` 的 comments 表 | 内容指纹 `0ed9687f3ae043ec` 一致（6 行） |
| 支持接收服务功能性 | 8098 带凭据 200（响应同为 2525 字节）、错口令 401；8099 与旧机同样 401 |
| 公网可达性（Mac 直连新 IP） | 80→301、443 证书正确、`/`、`/mrrc/`、`/mrrc_modern/`、`/mrrc_hub/`、`/RJ/` 均 200 |
| 首页逐字节 | `/mrrc/` 新旧完全一致 |
| goaccess 统计链路 | 手动跑通，报告 1.168 MB ≈ 旧机 1.171 MB（历史日志已并入） |
| 上游依赖（新机出网） | DashScope LLM 0.37s 可达；Club Log 数据已成功刷新 |
| 后端端口 | 8021 / 8098 / 8099 / 8100 全部监听，4 服务 + 2 timer active |

### 切换后实际执行的动作

1. **本机 `~/.ssh/known_hosts`**：`ssh-keygen -R www.vlsc.net` 后重连，新机主机键已登记；
   同时给旧机 IP `193.111.30.163` 补登了主机键（回滚时 SSH 不会再报未知主机）。
2. **Mac 侧 8891/8892 `-R` 隧道**：杀掉旧 `ssh -N -R` 进程（PID 17313），launchd 监控
   `com.user.mrrc.tunnel`（`~/HAM/mrrc/mrrc_tunnel.sh monitor`）在 30 s 内自动重连到新机；
   新机 `127.0.0.1:8891/8892` 已监听，旧机侧已释放。
3. **旧机停写**：`systemctl stop support-receiver support-receiver-modern vlsc-feedback yijing-llm`
   - `systemctl disable --now vlsc-feedback-db.timer yijing-llm-eval.timer`。
   **nginx 保持运行**（旧 DNS 缓存未过期的客户端仍可拿到静态页）。
4. **新机证书续期链路验证**：DNS 指向新机后 `certbot renew --dry-run` 两个证书均 success。

### 切换后验收（Mac 真实公网）

| 目标 | 结果 |
| --- | --- |
| `www.vlsc.net` / `vlsc.net` / `radio1.vlsc.net` | 全部 `203.25.119.168` |
| 证书 | `Oct 1 15:45 → Dec 30 15:45 UTC`，与旧机一致 |
| `/`、`/mrrc/`、`/mrrc_modern/`、`/mrrc_hub/`、`latest.json` | 200 |
| `/stats/` 401、`/feedback/api/` 404、`/yijing/api/` 405 | 与旧机基线一致 |
| `radio1.vlsc.net` | 302（隧道已通） |
| 新机定时任务 | `certbot.timer`、`vlsc-feedback-db.timer`（次日 03:00）、`yijing-llm-eval.timer`（周一）均已排程 |
| 发版通道 | `deploy_website.sh` 的 `sudo rsync` dry-run 对 `www.vlsc.net:/var/www/vlsc.net/mrrc/` 验证通过 |
| 真实流量 | 切换后 10 分钟内 11 个独立访客 IP 落在新机 |

### 收尾待办（观察期结束后）

- [ ] 新机 `/root/.ssh/id_migration`（可免密 sudo 旧机的迁移密钥）与旧机 `authorized_keys`
      中对应条目一并删除。
- [ ] **旧机 `193.111.30.163` 已于 2026-10-02 02:00 左右完全失联**（ICMP / 22 / 80 / 443
      从新机与家庭宽带两个不同网络均超时；归属 Greencloud LLC / 365 Group，日本）：
      非迁移动作所致也非迁移必需，但需你自行到服务商控制台确认是否被停机/欠费/宿主机故障。
      它已不再承担任何生产流量（DNS 已全量收敛），回滚能力随之失效。
- [ ] 新机 hostname 当前为 `hub`（服务商的默认名），如需改 `www` 可 `hostnamectl set-hostname www`。

## 4. 回滚（观察期内可用）

```bash
# 1) DNS 三条 A 记录改回 193.111.30.163（阿里云，TTL 5 分钟）
# 2) 旧机恢复写路径服务：
ssh cheenle@193.111.30.163 'sudo systemctl start support-receiver support-receiver-modern vlsc-feedback yijing-llm \
  && sudo systemctl enable --now vlsc-feedback-db.timer yijing-llm-eval.timer'
# 3) Mac 侧隧道切回旧机（DNS 已回指，重启隧道即可）：
kill $(pgrep -f 'ssh -N -R 8891')      # launchd 监控 30s 内自动重连
# 4) 本机 known_hosts 若拦 www.vlsc.net：ssh-keygen -R www.vlsc.net
```

**注意数据反向差异**：切换后新机已接收的 support 包与 feedback 条目不会自动回流旧机；
若要回滚且保留数据，需先把 `/var/www/support*` 与 `feedback.db` 从新机同步回旧机。

## 5. 已知风险

1. **新机对外 80/443 可达性**：初次探测时 22/80/443 均 refused（疑为开机自检期），
   nginx 起来后须从外网核实 80/443 真的可达（服务商侧防火墙）。
2. **`/mrrc_modern/listen` 等路径依赖 `radio.vlsc.net:8888`**（家用 IPv6）：
   新机在香港，到该源的连通性需单独验证。
3. **8891/8892 `-R` 隧道**：切换后需重启 Mac 侧隧道进程，且新机 sshd 必须允许远程转发。
4. `/var/www/vlsc.net` 顶层属主是 `cheenle:staff`（非 www-data），子目录混用；
   rsync 按名映射，名称需在两端一致（cheenle / www-data / staff 均存在）。

## 6. 顺带迁移的 VPN（WireGuard + unbound，用户选择 B 方案）

### 6.1 拓扑与客户端

原「范围外发现」：旧机除 nginx 外还跑着 WireGuard 服务端与给 VPN 网段用的 unbound。
已于同夜一并搬到新机。

| 项 | 值 |
| --- | --- |
| 服务端 | `wg0`，UDP **9903**，隧道地址 `10.77.0.1/24` + `fd77::1/64`，NAT 出口 `ens3`（NAT44 + NAT66） |
| 客户端 A | macOS（`~/vpn/`），隧道 `10.77.0.2`/`fd77::2`，外层 **IPv6**（`wg-up-6.sh`） |
| 客户端 B | OpenWrt 路由器 `192.168.1.6`，隧道 `10.77.0.3`/`fd77::3`，默认路由走 wg0 |
| 内部 DNS | unbound 监听 `10.77.0.1:53`（仅放行 `10.77.0.0/24`），上游 1.1.1.1 / 8.8.8.8 |

关键发现：客户端配置的 Endpoint 写的是**域名** `www.vlsc.net:9903` 或**服务器固定 IPv6**；
前者随 DNS 自动跟随，后者必须手改——本次两端都改了 IPv6。

### 6.2 新机落地内容

- `wireguard` + `wireguard-tools` + `unbound`（apt）
- `/etc/wireguard/wg0.conf`：与旧机逐字一致（同服务端私钥 → 客户端配置无需换密钥）
- `net.ipv4.ip_forward=1`（`/etc/sysctl.d/99-vpn-ipv4.conf`）、`net.ipv6.conf.all.forwarding=1`（`99-vpn-ipv6.conf`）
- unbound 四份配置（`unbound.conf` + `conf.d/{vpn,remote-control,root-auto-trust-anchor-file}.conf`）
- ufw：`22/tcp`、`80/tcp`、`443/tcp`、`9903/udp`、`53 from 10.77.0.0/24`，
  默认策略对齐旧机（INPUT DROP / FORWARD ACCEPT）；另 **mask 掉 systemd-resolved**
  （旧机就是 masked，且它占住 127.0.0.53/54:53 会让 unbound 无法绑定通配 53）

### 6.3 三处客户端改动

| 位置 | 改动 |
| --- | --- |
| `~/vpn/scripts/vpn.env` | `WG_SERVER_PUB_IPV6` → `2403:2c81:2000:2189::a`（旧值已入注释） |
| `~/vpn/scripts/macos-wg-client-v6.conf` | `Endpoint` → `[2403:2c81:2000:2189::a]:9903` |
| OpenWrt | 跑 `~/vpn/scripts/update_openwrt.sh`（自动改 endpoint/绕过路由/DNS 上游并备份） |

原文件均留 `*.bak-2026-10-02-*` 备份。

### 6.4 踩到的四个坑（均已定位并修复）

1. **unbound 起不来**（`Address already in use for 0.0.0.0 port 53`）：新机 systemd-resolved
   在跑（旧机是 masked）。已对齐旧机：停用 + mask，`/etc/resolv.conf` 落为普通文件（1.1.1.1）。
2. **`update_openwrt.sh` 在路由器上爆 `ash: syntax error: unexpected ";;"`，切换中断在 [4/6]**：
   根因是 `dig` 查询失败时把 `;; connection timed out; no servers could be reached`
   打到 **stdout**，被 `| head -1` 无校验捕获进 `CLEANUP_IPS`，生成的远程脚本里出现裸 `;;`。
   已改成：IP 字面量直接用、只对域名做 DNS、并用正则二次校验。共两处验证（本地 `bash -n`
   - 路由器 `sh -n` 均通过）。**同仓 `deploy_new_server.sh:275` 有同类写法（未改，该脚本引用的
   `~/UHRR/*` 路径已不存在，属遗留）**。
3. **路由器切换顺序**：脚本中断时 UCI 的 endpoint 已改但 bypass 路由还是旧的——若此时重启 wg0
   会把隧道流量打进隧道（回环断路，家里断网）。手工按「先补新机 bypass 路由 → 再重启 wg0」完成切换。
4. **本机全隧道与 `-R` 隧道互坑**：Mac 起 `wg-quick up` 后，原 `-R 8891` SSH 会话的源 IP 变了，
   TCP 被重置；新机侧那条 sshd 会话成了僵尸仍占着 `127.0.0.1:8891`，而隧道脚本带
   `ExitOnForwardFailure=yes` ⇒ 监控每 30s 重连全失败，`radio1.vlsc.net` 挂住返回 000。
   处理：清僵尸会话 `kill <pid>` + 本机 `wg-quick down` 复位。**运维要点：本机不需要起 wg
   （在家庭局域网里路由器已经提供 VPN），同时开会互相打断。**

### 6.5 验证证据

| 检查 | 结果 |
| --- | --- |
| 新机 `wg show` | 两个对端（Mac `10.77.0.2`、路由器 `10.77.0.3`）均有握手 |
| Mac 经隧道出口 | v4 `203.25.119.168` / v6 `2403:2c81:2000:2189::a` |
| 路由器经隧道出口 | v4 出口命中新机；ping 8.8.8.8 / 223.5.5.5 / 1.1.1.1 均通，~77ms |
| 内部 DNS | 路由器 `nslookup www.vlsc.net 127.0.0.1` → `203.25.119.168` |
| 家庭局域网 | Mac 的 v4 出口 = `203.25.119.168`（即 LAN 流量已走新机） |
| 用户脚本 | `update_openwrt.sh` 端到端跑通并输出「✅ 握手正常」 |

# MRRC 接入 Cloud Hub：改造计划与现状（2026-09-30 侦察，2026-10-04 全面更新）

目标：让 `mrrc`（本仓产品，Tornado，默认端口 8877）具备与 `mrrc_modern` 同等的
"可被云端入口接入"能力。**标签规则**采用主产品裸呼号、附加产品加产品后缀
（本仓若上线即 `bg1sb-legacy` 形式）；规则与理由见 `mrrc_hub/SDD/07-subject-area-model.md` §7.x.1。

> **2026-10-04 更新说明**：本文的侦察与改造完成于 2026-09-30。此后 hub 侧发生了
> V0.21 合并单机布局（2026-10-02）与门户公网上线，mrrc_modern 侧把"接入云端"
> 做成了产品功能（v1.24.0–v1.25.0）。本文已按现状全面修订；被取代的原始结论
> 以修订记录保留（见文末）。

## 四项能力的现状结论

| 能力 | 状态 |
| ------ | ------ |
| 子域根路径入口（`https://<标签>.mrrc.vlsc.net/`，**443**） | **开箱即用**，无需改造。认证走会话（`auth = FILE`，无 URL 令牌），fleet 评审的 P0-2 对本产品不适用 |
| 路径前缀能力（`/<产品段>/<呼号>/`） | **已实现并留有守卫**（见下"前缀改造"），但**当前公网没有路径入口在消费它** —— 唯一的海外边缘路径已随 hub V0.21（2026-10-02）整体删除。`base_path` 保持默认空值；若未来恢复路径入口（hub `deploy/README.md` X2：那段 `path proxy` 没有脚本能复现，需先写回脚本），本能力即启用点 |
| 令牌不进 URL | **天然满足**（会话机制，无 URL 令牌） |
| PTT 活性闸门 + 会话遥测 | **均已完成**（见下"已完成"两节） |

## Hub 现网形态（2026-10-04，取证自 mrrc_hub SDD §12.8/§12.9 与 deploy/README）

- **一台机器承担全部角色**：香港 VPS `203.25.119.168`（`hub.vlsc.net` = `www.vlsc.net`
  = `portal.mrrc.vlsc.net`），nginx（443）+ frps 0.71.0（控制口 8989）+ `mrrc-portal.service`
  （仅回环 8890）。**要 SSH 的是 `cheenle@www.vlsc.net`，不是 `8.160.161.80`** —— 那台
  阿里云 ECS 上跑着一套注册表已分叉的旧环境，自 2026-09-30 起无实例接入，不承载任何现网入口。
- **唯一入口**：`https://<呼号>.mrrc.vlsc.net/`（443 + `*.mrrc.vlsc.net` 通配真证书，
  DNS-01 签发、每日续期）。`:8899` / `:9988` 两个非标口与 `www.vlsc.net/mrrc_modern/<呼号>/`
  海外边缘路径**均已取消**（V0.21）。隧道控制 `tunnel.mrrc.vlsc.net:8989` 是唯一保留的独立端口。
- **呼号自助门户已公网上线**：`https://portal.mrrc.vlsc.net/`（挂在该名字的根，旧
  `/mrrc_portal/` 301 到根）。申请 → 运维在 `/admin` 核验批准（Club Log 全库 27 万余条 +
  自建名单 + 人工兜底）→ 凭**一次性登记口令**认领。
- **注册表三列**：`/etc/mrrc-hub/instances.tsv` 每行 `标签 <tab> 回环端口 <tab> 上游 TLS 名`。
  第三列留空 = 按实例自己的入口名（`<标签>.mrrc.vlsc.net`）校验上游证书；实例若仍用旧名
  证书（如 `radio.vlsc.net`）必须显式写第三列，否则入口 502。
- **实例证书链（一机一证）**：`make_instance_cert.sh <标签>` 在实例侧签 `<标签>.mrrc.vlsc.net`
  自签证书并**只把公钥**登记到 hub（`/etc/mrrc-hub/instance-certs/` → `trust-bundle.pem`）；
  nginx `proxy_ssl_name $mrrc_tls_name` + `proxy_ssl_trusted_certificate`，**校验始终开着**。
- **路由重生成是自动的**：root 的 `mrrc-hub-routes.timer` 每 30 s 跑 `gen_hub_routes.py`，
  生成物真的变了才 `nginx -t` + reload。**2026-10-03 实测教训**：现网曾只装了 `.service`
  而缺包装脚本与 timer ⇒ 路由自 10-02 起从未重生成、新实例全 404（当日已修）。验收：
  `systemctl is-enabled mrrc-hub-routes.timer` 应为 `enabled`，且
  `/usr/local/sbin/mrrc-hub-routes.sh` 的 sha256 与仓库 `deploy/mrrc-hub-routes.sh` 一致。
- **已知退化（有意接受）**：隧道路径下实例登录限流退化为全局桶（所有来源都是
  `::ffff:127.0.0.1`，5 次/300 s）。修法是实例信任 `X-Forwarded-For`（见下"未完成"）。

## mrrc_modern 的实现（参照系，已随 v1.25.0 进入打包版）

mrrc_modern 已把"接入云端"做成**应用内功能**（`docs/OPERATION_GUIDE.md` §0.9），
这是本产品接入时要对齐的行为目标：

- **应用内对话框**：抽屉菜单 →「接入云端（Cloud Hub）…」→ 呼号 / 联系方式 / 登记口令
  → 申请或直接接入；状态从「已提交申请」到「已接入」。
- **批准后零点击**（v1.25.0）：服务端 `_cloud_autoconnect_loop` 每 30 s 自查一次，
  发现已批准就**自己签证书 → 登记入口 → 写 frpc 配置 → 起隧道**；`/api/cloud/state`
  的 `autoconnect` 字段报告"上次何时问的、结果如何"。
- **隧道随应用启动拉起**（v1.24.8）：不再等有人打开设置对话框；重启后入口自己恢复。
- **证书生效判据按事实判断**（v1.24.7/v1.25.0）：进程正在服务的证书 vs 配置要求的证书，
  不一致就提示重启（TLS 上下文只在进程启动时建立）。
- **版本对齐**：frpc 版本 pin 到 hub 的 frps（`MRRC_FRP_VERSION=0.71.0`）—— 客户端比
  服务端新可能握手失败。

**本产品（mrrc）已移植同一套行为（2026-10-04，本仓 feat/hub）**：页面 `www/cloud.html`
（主界面 ☁️ 按钮 / 移动端菜单「☁️ 接入云端」），接口 `GET/POST /api/cloud/state|apply|refresh|restart`，
纯逻辑 `cloud_hub.py`（stdlib，守卫 `dev_tools/test_cloud_hub.py`）。与 mrrc_modern 的差异只有
被迫的两处：状态存 `mrrc_cloud.json`（本仓配置是 configparser 的 `MRRC.conf`，不能让代码重写
丢注释）；frpc 靠发现（`fleet/`、PATH、`~/.local/share/mrrc-fleet`）而非安装包内嵌。
申请时 `product=legacy` → 门户按标签规则分配 `<呼号>-legacy`。

## 前缀改造：逃逸点实测清单（2026-09-30 侦察）

| # | 位置 | 实测 | 处理 |
| --- | ------ | ------ | ------ |
| 1 | 路由注册表 | `MRRC:71` 起的 `handlers=[...]`（含 `/login` `/logout` `/CONFIG` `/mobile` `/test` `/api/mem_channels` `/api/recordings` `/WSaudioRX` `/WSaudioTX` `/WSCTRX` `/WSpanFFT` `/WSATR1000` `/WSATU` `/(panfft.*)` 等） | 引入 `base_path` 配置，注册时统一前缀（空值 = 现状） |
| 2 | HTML 绝对路径 | **5 个文件 / 8 处**（如 `www/index.html` 的 `href="/wdsp_settings.html"`、`/panfft.html`） | 改相对路径 |
| 3 | JS 绝对调用 | `fetch('/api/devices')` ×2、`fetch('/api/devices/apply')` ×1 | 改相对或经 `base_url()` |
| 4 | 登录跳转 | `MRRC:474` `549`（`/login?next=` + quote(request.uri)）、`MRRC:4241` `4430`（`redirect("/login")`）、`MRRC:4450` 内联 `window.location.href='https...'` | 目标前缀化；`next` 回跳要能处理带前缀的 uri（**这是 mrrc_modern 踩过的同一个坑**） |
| 5 | service worker | `www/sw.js` 存在 | 依 mrrc_modern 的断言规则：**文档资源用相对、预缓存清单保持绝对** |
| 6 | X-Forwarded-For | `MRRC.conf` 无概念 | 信任反代来源后按 XFF 取客户端 IP（否则限流退化为全局桶，同 §12.8 已知退化） |

## 守卫测试（照 mrrc_modern 的形状）

新增 `tests/`（或用 `dev_tools/`，本仓无统一 pytest 入口）：
断言"任何 HTML/JS 里不得出现指向站点根的绝对路径"（`sw.js` 预缓存清单除外）、
"路由表在 `base_path` 非空时全部带前缀"、"登录跳转与 `next` 往返保持前缀"。

## 进展：前缀改造已完成（2026-09-30）

| 项 | 落点 |
|----|------|
| 配置 | `MRRC.conf` `[SERVER] base_path =`（默认空 = 行为与改造前完全一致） |
| 模块 | `base_path.py`：`normalize/url/cookie_path/apply_to_handlers/application` |
| 路由 | 两处 `Application` 改走 `base_path.application(handlers, **kwargs)`——**不动参数列表**（早期尝试往字面量里插函数调用，括号失衡且修了两次，教训已记入提交信息） |
| 登录/回跳 | `prepare()` 放行判断、2 处 `next` 跳转、4 处裸 `/login`、`safe_next_url` 回退值 |
| **Cookie** | 5 处设置/清除都限定 `path=<前缀>` —— 路径入口下同 origin 多产品才不会互相覆盖会话 |
| 资产 | HTML 8 处相对化；`__wsURL`（管 5 个调用点）、`baseUrl`（2 处定义）、`__mrrcUrl` 统一前缀；`sw.js` 预缓存清单由注册 scope 推出前缀（仍是绝对路径） |
| 打包 | `Dockerfile` COPY `base_path.py`（漏了会 ImportError） |
| 守卫 | `dev_tools/test_path_prefix.py`（模块行为 8 项 + 资产扫描 + 服务端接线 + 打包）。**首跑即抓到 2 处漏网**（`control_trx.js`、`mobile_high.js` 用 `href.split` 拼 WS，grep 没覆盖到）+ `modern.js` 3 处 |

遗留：`www/pad.js` 含 WS 路径字面量但未见前缀化助手（守卫测试提示项，非失败项）——需确认那处是否真的建连接。

## 已完成（第二、三块）

1. **会话遥测** —— **已完成（2026-09-30）**：`session_metrics.py` + `GET /api/session_metrics`
   + `[SERVER] metrics_interval_s`（默认 60、0 关闭）+ `dev_tools/test_session_metrics.py`。
   连接数直接读既有 `*Clients` 列表（`AudioPana`/`AudioRX`/`AudioTX`/`ControlTRX`），**未侵入 WS 生命周期**。
   计数器目前只提供接口（`bump()`），尚未在音频/TX 路径埋点 —— 埋点要碰实时路径，留待需要时单独做。
   用途：Hub 侧容量决策（AD-H12 的扇出触发器，I-H1 的数据来源）。
2. **PTT 活性闸门（曾误记为缺失）** —— **不需要做（更正）**：能力**本来就存在** ——
   `WS_AudioTXHandler.stoppttontimeout()` 连续 25 × 200ms ≈ 5s 未收帧即 `CTRX.setPTT("false")`；
   另有 `PTTSafetyMonitor` 的 TOT 硬上限（`[CTRL] ptt_tot_seconds`，默认 120s）与释放失败每 2s 重试。
   本次只把阈值变成可配置（`[CTRL] tx_liveness_s`，默认 5.0 = 原行为，0 = 关闭）+ 补守卫测试。
   **教训**：原文档的结论来自只读了 TX 路径的一部分 —— 下结论前要读完那条路径。
   另注：配置值不能写行内注释（configparser 不支持），否则启动 ValueError。

## 未完成

1. **X-Forwarded-For 信任**（逃逸点 #6）：隧道路径下登录限流退化为全局桶
   （hub SDD §12.8 已记录在案、用户明确暂缓）。做的时候：仅在 `base_path` 非空
   或显式开关下信任反代来源的 XFF，按真实客户端 IP 进限流桶。mrrc_modern 同样未做，
   两边应取同一口径。

## 上线步骤

前置：**一个能独立运行该产品的站点** —— 它要占用电台/音频/串口，不能与主产品
mrrc_modern 同机并行；上线验证需独立硬件或经同意的停机窗口。

**应用内接入（2026-10-04 起，与 mrrc_modern v1.25.0 同一流程）**：

1. 打开主界面 ☁️ 按钮（或移动端菜单「☁️ 接入云端」）→ `cloud.html`。
2. 填呼号（可选联系方式 / 登记口令）→「申请入口 / 接入」；运维在
   `https://portal.mrrc.vlsc.net/admin` 核验批准。
3. **批准后零点击**：服务端每 30 s 自查一次，发现批准就自己签证书（`<标签>.mrrc.vlsc.net`，
   `ssl_bootstrap.sign_for`）→ 公钥登记到 hub → 写 `fleet/frpc-<标签>.toml` → 起 frpc
   （`cloud_hub.find_frpc`：`fleet/`、PATH、`~/.local/share/mrrc-fleet`）→ 自重启加载新证书。
4. 验证：`curl -s -o dev/null -w '%{http_code}\n' https://<标签>.mrrc.vlsc.net/login` ⇒ 200
   （443，不再有 `:8899`）；未知名 `nope.mrrc.vlsc.net` ⇒ 404。`curl -I` 打 `/login` 得 405
   是**正常**（登录页只接受 GET）。

**脚本接入（无图形环境 / 批量开通仍可用）**：`mrrc_hub/deploy/make_instance_cert.sh` +
`install_instance_tunnel.sh`（frpc localPort **8877**），注册表第三列与路由自动重生成见
上文「Hub 现网形态」。脚本路径签出的证书要配进 `MRRC.conf [SERVER] certfile/keyfile`；
应用内路径则写在 `mrrc_cloud.json`，启动时优先于 conf 配置。

## 修订记录

- **2026-09-30**：初版侦察 + 前缀改造完成 + 会话遥测完成 + PTT 活性闸门更正。
- **2026-10-04**：按 hub V0.21/V0.26 与 mrrc_modern v1.25.0 全面修订：
  - 入口从 `:8899` 改为 **443**（两个非标口与海外边缘路径已取消）；
  - "路径反代入口需要改造"的动机随边缘路径删除而消失，前缀能力转为储备（默认空）；
  - 新增 Hub 现网形态（合并单机、门户公网自助、注册表第三列、实例证书链、路由自动重生成）；
  - 新增 mrrc_modern 应用内接入实现（v1.24.0–v1.25.0）作为对齐参照；
  - **移植「接入云端」全套行为到本仓**（`cloud_hub.py` + `/api/cloud/*` + `www/cloud.html`
    + 启动拉起隧道/自动轮询/证书生效判据），上线步骤相应改为应用内优先。

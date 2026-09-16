# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [V6.1.13] - 2026-09-17

### 🐛 紧急修复：🐞 诊断包页面所有按钮失效（我上一步引入，已随热修下发）

现象：用户报"客户端生成诊断包咋不工作了"——生成/上传/只存本地全部无反应。

根因：V6.1.12 为"答复页链接"拼接字符串时多了一个引号，把单引号字符串提前终结
（`'<a href="…/answers/#" + d.remoteId + '" …'`）→ 页面唯一的 `<script>` **语法错误**
→ 整个页面的 JS 全废。该文件随 6.1.12 热修下发给了所有用户。

修复与防复发：
- 修好拼接（改用 `const ansUrl = …` 再嵌入）；
- 新增 **`tests/test_web_inline_js.py`**：对 `www/*.html` 与 `website/**/*.html` 的
  **内联脚本**逐个跑 `node --check`（无 node 时跳过）——这类"整页按钮失效"的错误以后进不了仓库。

## [V6.1.12] - 2026-09-17

### ✅ 问题答复闭环：上报 → 答复页 → 客户自查自解

- 新增公开答复页 **`/mrrc/answers/`**：每条答复含"编号 / 症状 / 诊断（证据）/ 结论 / 解决办法"，
  支持按编号或关键词搜索、`#编号` 直达（自动填入搜索框）；
  并附"30 秒自查法"与"体检摘要信号 → 常见原因 → 先做什么"对照表。
- **App 上传后直接给出答复地址**：`🐞 遇到问题` 上传成功时显示编号 + 带 `#编号` 的链接。
- **体检摘要更能自证**（`support_bundle.summarize_log`）：
  * 新增 **启动次数 / 日志时间跨度**，并明确区分"重启"与"崩溃"
    （真实案例：用户报"总是异常停止"，实际 25 次正常启动、0 条 Traceback）；
  * 新增 **-9996 无音频设备**判定：提示若 `env.json` 的 `audio.devices` 为空数组，
    说明本机没有音频设备（虚拟机常见），纯 Web 模式属预期而非故障。
- 首条答复即真实上报 `20260917-062314-35dc`。

## [V6.1.11] - 2026-09-16

### 🐛 两个启动器实例抢同一个 .part → 下载完成后改名失败（真机实测）

现象：6.1.9 下载到 43/45 MB 后报
`PermissionError [WinError 32] ... MRRC-Setup-6.1.9.exe.part -> MRRC-Setup-6.1.9.exe`。

根因：`threading.Lock` 只在进程内有效，而现场有两个 `MRRC-Launcher` 进程
（重启 + 安装器 postinstall 各一个）→ 两个都下同一个 `.part` →
一个改名的瞬间另一个正开着它 → Windows 拒绝。

修复（`upgrade_core.py`，可热修）：
- 临时文件按进程命名 `.part<pid>`，互不干扰；
- `os.replace` 加 6 次重试（杀软/索引器短暂占用也能过去）；
- 失败只清理自己的临时文件。

## [V6.1.10] - 2026-09-16

### 🐛 真机复现：点【立即升级】后毫无反应（已修，可热修下发）

真机现象：页面显示 v6.1.8 → v6.1.9 可升级、服务端也写了哨兵
（日志 `收到升级请求: 6.1.9（当前 6.1.8）`），但 `upgrade.request` 一直没人消费，
`MRRC-Setup-6.1.9.exe.part` 停在 0 字节。

根因（6.1.8 引入的回归）：`_DOWNLOAD_LOCK` 是**阻塞锁**，而启动检查的后台预下载
线程卡在**连接/DNS 阶段**（读超时管不到）→ 永久占着锁 → 升级看护线程拿到第一个
请求后**无限等锁** → 之后再点也没人理。

修复（都在可热修的 `upgrade_core.py` 里）：
1. 锁改 `acquire(timeout=1.0)`，拿不到就返回 `download_busy` 让上层**自动重试**（绝不阻塞）。
2. `socket.setdefaulttimeout(30)`：连接/DNS 阶段也会超时，不再产生 0 字节 `.part` 挂死。

## [V6.1.9] - 2026-09-16

### ✅ 一键升级：真机首次实升验证版

用户已在真机装好 6.1.8（含全部 8 项修复），本版作为"被升级"的目标：
点页面【立即升级】或启动器窗口按 U → 静默安装 → 自动重启到 6.1.9。

## [V6.1.8] - 2026-09-16

复盘 9-16 上传的那份 23 KB 诊断包：包内 284 KB 是 8-30 的僵尸日志、活日志一个没进，
“音频没数据 / WDSP 未见成功”全是误报。逐项修复并补齐自证能力：

- 🐞 诊断包日志解析：多实例按 `mrrc_<name>.log` / `rigctld_<name>.log` / `atr1000_<name>.log`
  约定收集**正在写的**日志（含 `.prev`），同角色候选按 mtime 最新者取（main 走
  `MRRC.log`/`mrrc.log`/`rigctld.log`/`atr1000_comm.log`），Windows `logs/server-stdout.log` 照收；
  缺日志或包内最新日志 >24h 会在体检摘要与 warnings 里显式点名。
- 🎧 音频健康：`🎧 音频健康` 不再被 `MRRC_AUDIO_DIAG` 开关挡住；修正 paFloat32 立体声输入
  的帧数计数（旧公式按 int16 `len(data)//2`，帧数放大 4 倍 → 真机恒 400%、“<99%”告警从未触发）。
- 诊断包版本号源码模式不再上报 `unknown`（`version.txt` → `MRRC.iss` → `CHANGELOG.md`）；
  `env.json` 增加 `instance`；`writte_log()` 补换行并落到本实例活日志。

## [V6.1.8] - 2026-09-16

### ✅ 一键升级：VM 真机第三轮（正式发布版）

在 6.1.4 的 4 项修复之后，第三轮又抓到并修掉 4 项：

1. **`_UPGRADING` 必须在停服务之前置位**（顺序 race）：停服务会让主线程立刻从
   `proc.wait()` 醒来检查标志，晚一步就走正常退出 → `Fatal Python error` → 安装被打断。
   失败路径显式 `clear()`。新增顺序回归测试。
2. **启动器日志丢行**：`_force_utf8_stdio` 没开行缓冲，而升级收尾是 `os._exit`
   （不刷新缓冲）→ 用户在窗口里看不到任何升级进度。改为 `line_buffering=True`。
3. **已暂存也必须能离线升级**：原先即使包已校验暂存在本地，也要先拉清单，
   清单拉不动就卡住不动。改为"已暂存就直接升"，清单只在需要下载时才拉。
4. **下载无超时、且可与后台预下载撞车**：VM 实测被 CDN stall 卡死 5 分钟以上。
   加读超时（默认 60s，失败自动重试）+ 进程内下载互斥（`_DOWNLOAD_LOCK`）。

## [V6.1.7] - 2026-09-16

- 一键升级端到端验收目标（仅测试用，不对外发布；走 MRRC_UPDATE_MANIFEST 测试清单）。

## [V6.1.6] - 2026-09-16

- 一键升级端到端验收目标版（与 6.1.5 同样的代码；发布版就是被升级流程实测过的这一包）。

## [V6.1.5] - 2026-09-16

- 一键升级端到端验收版（承接 6.1.4 的 4 项修复）。

## [V6.1.4] - 2026-09-16

### 🐛 一键升级：VM 真机第二轮暴露的 4 个问题（全部修复）

1. **升级器拉起来了，启动器却当场死**：`/CLOSEAPPLICATIONS` 关不掉控制台进程 → 我先停服务，
   但**主线程随即从 `proc.wait()` 返回** → 解释器收尾与 `input()`/转发线程抢缓冲区 →
   `Fatal Python error: _enter_buffered_busy` → 安装被打断。
   → 新增 `_UPGRADING` 事件：升级中主线程**永不正常退出**，由 `_exit_for_upgrade` 的
   `os._exit` 受控收尾。
2. **页面按钮（具体版本号）不会自动下载**：原逻辑只有 `"latest"` 分支会下载，
   写具体版本时若安装包还没下完 → 记 `missing_staged` → 请求被丢弃。
   → `watch_upgrade` 统一两条路径：先取清单 → 需要就下载 → 失败保留请求重试（不丢指令）。
3. **`upgrade_core` 没进安装包**：MRRC 是 datas 里的数据文件、函数内 import 分析不到 →
   `ModuleNotFoundError: No module named 'upgrade_core'`（服务端 `/api/update` 实报）。
   → 加进 spec 的 `_APP_MODULES`（同时获得热修可覆盖能力）。
4. **state.json 并发覆盖**：下载线程与升级线程读-改-写互相覆盖（失败痕迹被冲掉）。
   → `upgrade_core._STATE_LOCK` 串行化。

## [V6.1.3] - 2026-09-16

- 一键升级端到端验收版：承接 6.1.2 的 6 项修复（RestartManager 关不掉控制台进程导致的
  静默 Abort、提权时 ShellExecuteW 卡死、升级成功确认、BOM 哨兵、GBK emoji 杀转发线程、
  静默安装后不自动重启）。

## [V6.1.2] - 2026-09-16

### 🐛 一键升级：端到端实测暴露的 5 个 Windows 陷阱（全部修复）

在 Win11 VM 上真机跑「6.0.10 → 6.1.0 → 6.1.1」验收，装到第 3 轮才升上去 —— 抓到并修掉：

1. **升级后卡死在中止**（最致命）：Inno 的 `/CLOSEAPPLICATIONS` 靠 Restart Manager 发
   `WM_CLOSE`，而控制台进程没有消息循环 → 关不掉 → 静默模式自动选 Abort → 安装回滚
   （实测日志：`Some applications could not be shut down.` → `User canceled`）。
   → 启升级前**先停自己的服务子进程**（`_stop_server_for_upgrade`），并**启动器拉完安装器
   立刻 `os._exit` 放手文件**（`_exit_for_upgrade`）；命令加 `/FORCECLOSEAPPLICATIONS` 兜底。
2. **提权时不该弹 UAC**：已提权的启动器再走 `ShellExecuteW("runas")` 在非交互窗口站上会
   **永久卡住**（实测：哨兵被消费、无 consent.exe、无安装日志）。
   → `_is_elevated()` 为真时**直接 `Popen` 跑安装器**。
3. **升级成功没人确认**：启动器退出后由新版自己确认 —— 启动时若
   `version.txt >= state.staged.version` → 记 `ok` + 清状态 + 删暂存包（`confirm_pending_upgrade`）。
4. **BOM 让哨兵失效**：`_read_json` 改用 `utf-8-sig`。记事本 / PowerShell
   `Set-Content -Encoding utf8` 默认写 BOM，而 `json.load` 遇 BOM 直接抛错 → 升级被静默忽略。
5. **Windows 控制台 GBK 杀线程**：服务端日志里的 emoji（🔍）让 `print` 抛
   `UnicodeEncodeError`，**杀死日志转发线程** → 诊断包里的 `server-stdout.log` 断更。
   → 启动器 stdio 统一切 UTF-8（`_force_utf8_stdio`）+ 转发用 `_safe_print` 降级不抛。

另：一键升级脚本/自报上传显式用 UTF-8 字节（PowerShell 默认编码会把中文元数据写成乱码）。

## [V6.1.1] - 2026-09-16

### 🔧 升清单地址可覆盖（测试/内网镜像）

- `upgrade_core.manifest_url()`：可用环境变量 `MRRC_UPDATE_MANIFEST` 覆盖 `latest.json` 地址
  （便于在隔离网络里指向内网镜像，也用于端到端测试时不动生产清单）。启动器日志会打印实际清单地址。

## [V6.1.0] - 2026-09-16

### ⬆️ 一键升级到最新版（Windows 安装版）

- 新增 `upgrade_core.py`（纯逻辑）：`latest.json` 清单解析、版本决策（安装版本唯一权威、
  拒绝降级、`minSupported`/`requires` 门禁）、**原子下载 + SHA256 校验**（先 `.part` 再
  `os.replace`，失败只清 `.part`）、`state.json` 与 `upgrade.request` 哨兵文件。
- 启动器：启动时检查 → 后台预下载（可关）→ 用户点【立即升级】或**输 U 回车** →
  `ShellExecuteW runas` 静默安装（`/VERYSILENT … /LOG=`，一次 UAC）→ 成功后自动重启拉起新版；
  UAC 被拒(`uac_denied`)/校验失败(`sha_mismatch`)/发射中被拒(`ptt_active`) 都有明确状态落盘。
- 服务端 `/api/update`（状态/升级/回退，**仅本机免口令**供启动器读 PTT）、`/api/update/upgrade`
  （PTT 门禁）、`/api/update/rollback`；页面 `www/update.html` + 移动端菜单/桌面入口。
- 回退：`latest.json` 的 `previous` 段 + 页面一键回退，走同一条静默安装路径。
- 发布：`dev_tools/make_latest_json.py` 生成 `latest.json`（installer 指向带版本名产物、
  hotfix 复用 `patch.json`、previous 指向站点保留的上一版）；`release_windows.sh` 自动归档上一版。
- 文档：`docs/current/operations/one-click-upgrade.md`。

## [V6.0.10] - 2026-09-16

### 🔧 本轮其它修复

- **空闲关机幂等**：5 分钟无客户端活动后，原先每 60s 都会重复 `setPower(0)` 并打印
  （Win11 VM 控制台实测每分钟两条，且持续把电台按在 power=0）；改为每个空闲周期只关一次，
  客户端一有新活动就重新武装，日志改用 logger。
- **配置 BOM 兼容固化**：PowerShell/记事本保存 UTF-8 会带 BOM，
  `config_io.read_config` 已按 `utf-8-sig` 优先读取 —— 补测试钉住（Windows 用户常见坑）。
- **「设备配置」抽屉滚动**：`display:block` 破坏 flexbox 导致保存/重启按钮被顶出屏幕 ——
  改 `display:flex` + 内容区 `min-height:0` + 按钮区 `flex-shrink:0` + `height:100dvh`（已作为 6.0.8 热修补丁发布）。

### 🐞 一键诊断包：用户点几下，维护者直接拿到现场

- 移动端菜单 / 桌面工具栏新增 **🐞 遇到问题**（`www/support.html`）：填问题描述 → 生成诊断包 →
  预览清单 → 上传给维护者（或只保存到本地）。
- 包内容：日志尾部（MRRC.log + 上一份 + 启动器 tee 的 server-stdout + 天调日志）、**脱敏后**的配置快照、
  环境快照（Windows 版本/CPU/音频设备表含主机 API 与延迟/rigctld 实报/ATR 状态/热修覆盖层）、
  `diagnostics/summary.txt`（自动体检结论：音频健康度最低值、热修是否生效、WDSP 是否加载、异常归类计数）。
- **脱敏硬规则**（`support_bundle.py`）：配置白名单、密钥键值替换为 `<redacted>` 并计数、
  用户库/证书/私钥永不打包、日志按行边界截断 ≤2 MB。
- 服务端 `/api/support/*`（生成/上传/保存/下载），磁盘与网络 IO 全走 executor，不阻塞 IOLoop；
  上传只走 HTTPS 且由用户主动触发。
- 接收端 `tools/support_receiver/`（stdlib + systemd + nginx 反代）部署在 www.vlsc.net：
  带口令的列表页可直接看问题描述并下载/删除，限速（每 IP 每分钟 ≤5 次）与单包上限（20 MB）。
- 启动器把服务端 stdout/stderr **tee** 到 `%LOCALAPPDATA%\MRRC\logs\server-stdout.log`
  （2 MB 滚动），启动期报错终于能进诊断包。

## [V6.0.7] - 2026-09-16

> 这是自 V6.0.3 以来的**汇总安装包**：其中的设备配置/音频/ATR/日志修复与热补丁
> 6.0.4 / 6.0.5 / 6.0.6 内容一致（热补丁内容已通过更新通道发给 6.0.3+ 安装）。

> 这两版以**热补丁**形式发布（`website/downloads/patch.json` → 6.0.3+ 安装启动时自动应用），
> 不重新出安装包：6.0.4 = Device Config 型号对应；6.0.5 = Windows 音频设备按主机 API 优先 + ATR 开关。

### 🪵 Windows 运行日志与低噪音清理（在 Win11 安装版布局上实测）

- **日志编码/缓冲**：冻结版 stdout 之前是 cp936 且块缓冲 → 重定向后中文乱码、启动日志被吞掉
  （排查时像“什么都没输出”）。现启动即 `reconfigure(encoding='utf-8', errors='replace',
  line_buffering=True)`，Windows 日志可直接读、不丢行。
- **音频初始化失败**：原先打 3 段完整 Traceback；常见原因（没插 USB CODEC/被占用/设备名不匹配）
  不需要堆栈，现只留一行 + 可操作提示，完整堆栈仅在 `MRRC_AUDIO_DIAG=1` 时输出。
- **RNNoise 告警**：装了 WDSP 的部署不再提示“RNNoise 不可用”（RNNoise 已弃用，属误导噪音）；
  只有两个降噪引擎都没有时才提示一行。
- **`packaging/hotfix/apply_hotfix.ps1` 分层 bug**：`Copy-Item -Recurse` 到已存在目录会再套一层，
  曾把 `app/MRRC` 解成 `patch\app\app\MRRC` 导致覆盖层不生效；改为按子目录复制内容。
  （这是拿真实 Windows 安装版跑一遍才暴露出来的。）

### 📡 ATR-1000 改为配置项（可选组件）

- ATR-1000 是可选设备，但没接它的部署会持续刷“代理连接失败/重连/看守拉起”。新增
  `[ATR1000] enabled = auto|true|false`（auto 默认：配了 `instance_atr1000_device` 才启用），
  也可用 `MRRC_ATR1000=0/1` 覆盖；关闭后不连代理、不拉进程、不轮询，启动只留一行说明。
- 连接失败/重连/看守找不到代理的日志改为**限流**（首次 + 每 5 分钟一条，附窗口内次数）。
- `mrrc_multi.sh` 同步识别该开关。
- **Windows 安装版现在能自动拉起代理**：看守原先只找 `atr1000_proxy.py`（安装包不带 .py），
  改为优先使用打包好的 `ATR1000-Proxy.exe`。
- 前端：收到 `atr1000_status{enabled:false}` 时隐藏 ATR 面板并停止重连。

### 🔊 Windows 音频：设备按主机 API 优先（默认 WASAPI）

- 见上条 6.0.5 说明；另新增采集健康日志（每 30s 一行“采集样本数 vs 应有样本数”）与
  `[AUDIO] diag = True` / `MRRC_AUDIO_DIAG=1` 逐秒诊断，便于定位“秒级卡顿”。

### 🎛️ Device Config 的电台型号改为 hamlib 实时机型表，并修正“改了型号不生效”

- **问题**：`Device Config` 的型号列表是硬编码 7 个名字（既非 hamlib 实际支持机型），
  且它写的是 `[HAMLIB] rig_model`（名字，如 `IC_M710`），而 **rigctld 实际读的是
  `[INSTANCE_SETTINGS] instance_rigctl_model`（数字，如 30003）** —— 两边不通，
  用户换型号/串口实际不生效，配置与运行中的电台可能长期不一致。
- **新增 `rig_models.py`**：`rig_load_all_backends()` + `rig_list_foreach()`（ctypes）
  实时枚举本机 hamlib 的 **312** 个机型（id/名称/厂商/版本/状态），带别名表
  （`IC_M710`、`FT817`、`FTDX10`… 历史写法都能解析）、进程内缓存、hamlib 不可用时回退小表。
  另提供 `cached_rigctld_model()`：读 rigctld 的 `\dump_caps` 得到它**实际加载**的机型
  （后台线程刷新，绝不阻塞 IOLoop）。
- **写配置时两处同步**（`apply_to_config`）：`[HAMLIB] rig_model` = hamlib 规范名，
  `[INSTANCE_SETTINGS] instance_rigctl_model` = 数字 id；串口同样镜像
  （`rig_pathname→instance_rigctl_device`、`rig_rate→speed`、`stop_bits→stop_bits`）。
  非法型号 400 拒绝且不做半截写入。
- **`/api/devices`** 现在返回：机型表（含 `statusName`）、当前配置值到 hamlib 机型的对应
  （含"找不到"原因与候选建议）、`instance_rigctl_model`、以及 rigctld 实报机型。
- **UI**：型号改为**可搜索**的下拉（按厂商分组、显示 `#id · 名称 · 状态`），下方直接列出
  “配置 → hamlib 机型”与“rigctld 实报”，**配置与运行不一致时明确标注 ⚠**；支持自定义型号原样写入。
- **`mrrc_control.sh`** 改为从 MRRC.conf 读取型号/串口/速率等（优先
  `[INSTANCE_SETTINGS]`，其次 `[HAMLIB]`，最后才是脚本内置默认值），不再与实际配置脱节。
- 旧 `/CONFIG` 表单同步使用实时机型表（值是 hamlib 机型 ID）。
- 测试：新增 `tests/test_rig_models.py`（13 例：别名解析、双写、非法值不落盘、`\dump_caps` 解析）。

## [V6.0.3] - 2026-09-16

### 🩹 WebSocket 写入健壮性：消除 `WebSocketClosedError` 日志风暴与线程违规

- **根因**：tornado 6.5 的 `write_message()` 返回 Future，全项目 fire-and-forget 丢弃它；客户端断线后的残留写入被 asyncio 记为 `Task exception was never retrieved`（上一实例 22 小时累计 **12,620 条**，占全部 ERROR 的 99.9%，峰值 1821 条/分钟），淹没真实错误。
- **修复**：新增 `safe_ws_write()`（消费 Future；同步吞掉已关闭连接类异常，真实异常仍上抛），替换 12 处广播/音频写入点；`sendPTINFOS` 写入失败时主动摘除客户端并停止自调度循环（风暴根因）；`send_to_all_clients` 失败客户端同步清理。
- **线程违规修复**：`play_cq` 工作线程与 `_ptt_monitor_loop` 后台线程直接调 `write_message` → 改为 `MAIN_IOLOOP.add_callback` 编组（前者导致 `cq:complete` 通知丢失，违反 V5.8.2 规则）。
- **日志粘连**：`mrrc_multi.sh` 启动 MRRC 加 `-u`（stdout 无缓冲），`print` 与 `logging` 不再互相插行，日志可被 grep 正常解析。

### 🪟 修复 Windows 安装版启动 `UnicodeDecodeError`（写侧 GBK / 读侧 UTF-8 不一致）

- **根因**：V6.0.0 只把配置**读侧**固定为 UTF-8，**写侧**仍是 locale 编码——中文 Windows 上是 GBK(cp936)。当配置值含非 ASCII（`%LOCALAPPDATA%` 路径带中文用户名，如 `C:/Users/张伟/...`；或用户用记事本另存为 ANSI）时：写出的 GBK 文件在下次启动被 UTF-8 读取 → `UnicodeDecodeError`，服务器起不来。触发写侧的主要是设置页保存（`/api/devices/apply` → `_write_config`）与 `/CONFIG` 页面。
- **修复**：新增 `config_io.py` 统一策略——读侧 UTF-8 优先，回退 UTF-16(BOM)/locale/GB18030/Big5/latin-1；读到非 UTF-8 的配置自动迁移为 UTF-8 并保留 `.bak`；写侧固定 UTF-8 + 原子替换。服务器与 Windows 启动器共用（`MRRC`、`windows/launcher.py`）。
- **同类点一并修复**：`memory_channels.json`、`MRRC_users.db`（容错读 + UTF-8 写）以及 `MRRC.log` / `atr1000_proxy_watchdog.log`（`encoding='utf-8', errors='replace'`，避免 GBK 控制台/文件写日志时 `UnicodeEncodeError`）。
- **回归测试**：新增 `dev_tools/test_config_encoding.py`（复现故障 + 23 项断言，覆盖 GBK/BOM/缺失文件/迁移备份/启动器读取），并接入 `packaging/windows/build.ps1` 作为构建门禁。
- **打包**：`config_io` 加入两个 PyInstaller spec 的 hiddenimports，Dockerfile 同步 `COPY config_io.py`。
- **客户机就地修复工具**：新增 `packaging/windows/fix_mrrc_encoding.ps1` + `fix_mrrc_encoding.bat` + `fix_and_start_mrrc.bat`（免安装，`dist/mrrc-windows-config-fix.zip`）——已发布的 V6.0.2 安装包无需重装，在客户机上双击即可把 GBK 配置转为 UTF-8（保留 `.bak`），`fix_and_start_mrrc.bat` 可“先修后启”。支持 `-DryRun` / `-IncludeAux` / `-SelfTest` / `-CreateShortcut`。流程见 `win_pack.md` §5。


### 🪟 Windows 安装包发布（含热修通道）

- 本版 `MRRC-Setup.exe` 起，应用代码以松散文件交付（`_internal/app/*.py`），因此**前端/服务端/DLL 三类 bug 都可以用热修包修，不必重新打包或重装**。
- 制作：`python3 packaging/hotfix/make_hotfix.py --version <ver> <files…>`；
  验收：`python3 packaging/hotfix/verify_hotfix.py --app <安装目录>`；
  发布：`cp dist/hotfix/* website/downloads/ && ./deploy_website.sh`。

### 🧩 热修补丁通道 —— 小 bug 不再需要重新打包

- **背景（实测）**：PyInstaller 6 的 onedir 包把应用代码打进 exe 里的 PYZ；实验证明同名 `.py`
  放在 exe 同目录 / `_internal/` / cwd / `PYTHONPATH` **全部无效**，`sitecustomize.py` 也不执行
  （冻结运行时连 `site` 都不导入）。根因是 `PyiFrozenFinder` 被插进 `sys.path_hooks`，
  PYZ 内模块名一律先被截走。
- **打包改造**：应用自身代码（`MRRC`、`config_io`、`audio_interface`、`hamlib_wrapper`、
  `wdsp_wrapper`、`atu_auto_tuner`、`patch_overlay` 等）不再进 PYZ，作为数据文件放到
  `_internal/app/`，由新入口 `packaging/pyinstaller/frozen_entry.py` 加入 `sys.path`
  （依赖分析仍由 hiddenimports 保住）。未被冻结的模块才能从磁盘加载 —— 这是热修的前提。
- **覆盖层**：`%LOCALAPPDATA%\MRRC\patch\{app,www,vendor}`（无需管理员，与安装目录分离，
  删掉即回退）。www 资源由 `patch_overlay.OverlayStaticFilesMixin` 经 tornado 的
  `validate_absolute_path` 扩展点优先读覆盖层；WDSP 等 DLL 的搜索路径也把覆盖层排在最前。
- **投递方式**：① `MRRC-Launcher.exe` 启动时读 `https://www.vlsc.net/mrrc/downloads/patch.json`，
  满足版本要求且 SHA256 匹配才自动应用（失败只警告，不影响启动；`[HOTFIX] enabled=False`
  或 `MRRC_NO_UPDATE_CHECK=1` 可关闭）；② `packaging/hotfix/apply_hotfix.ps1` 手动/离线；
  ③ 6.0.2 及更早的安装可用就地模式（仅 `www/` 与 DLL，需要管理员；遇到 `app/*` 会明确拒绝，
  不"假装修好了"）。
- **制作补丁**：`packaging/hotfix/make_hotfix.py` 生成 `hotfix-<ver>.zip`（含逐文件 SHA256 的
  `manifest.json`）+ `patch.json`；按 spec 里的 `_APP_MODULES` 校验，只接受真正可热修的文件
  （新增依赖 / C 扩展 / 启动器 → 拒绝并提示必须重新打包）。
- **可观测**：启动日志打印 `🧩 补丁覆盖层已启用 …`；WebSocket 新增 `getPatchStatus` / `patchList`；
  覆盖层内记录 `applied.json`。文档见 [docs/current/operations/hotfix-and-patching.md]。
- **测试**：新增 `tests/test_patch_overlay.py`（16 例），含真实 tornado 服务验证覆盖层替换；
  Windows 打包脚本 `build.ps1` 会自动跑这套测试，失败即中止打包。

## [V6.0.2] - 2026-09-14

### 🪟 Windows 安装包发布（首个内置 WDSP 库的版本）

- 本版发布 `MRRC-Setup.exe`（45,411,773 bytes，SHA256 `56EFAA63…068E`），包含 V6.0.1 的 NR2 SSB 语音保护、WDSP 设置页、菜单瘦身，以及 V6.0.2 的 IOLoop/TX 初始化三项修复。
- **首次内置 `libwdsp.dll`**：此前（含 V6.0.0）Windows 包不含 WDSP 库，NR2 在 Windows 上不可用；现由 `packaging/windows/build_wdsp_dll.ps1` 用 MSYS2/MinGW-w64 构建并随包提供。

### 🚨 修复 8891 端口突发无响应（IOLoop 被同步 `p.open()` 楔死）

- **根因**：按 PTT 时 `WS_AudioTXHandler.on_message('m:')` 在 IOLoop 线程同步调 `TX_init` → `PyAudioPlayback.__init__` 的 `p.open()`（`audio_interface.py:909`）。CoreAudio 卡顿（当日蓝牙音频设备 AVDTP 流抖动）时该调用长时间不返回，整个事件循环停摆：进程活着、端口无响应、所有 WebSocket 断连。F2/F3 修复已把 `stream.write()` 与 rigctld I/O 挪出 IOLoop，唯独漏了构造函数。
- **修复（F4）**：`TX_init` 整体经 `run_in_executor` 卸载到工作线程（`MRRC` `_start_tx_init_async`）；构造期间重复的 `m:` 直接丢弃；`TX_init` 内的 PTT 广播改经 `MAIN_IOLOOP.add_callback`（`write_message` 非线程安全）。
- **安全竞态**：构造阻塞期间收到 `s:`/`on_close`（用户已松手）置 `_tx_init_cancel`，工作线程完成后丢弃播放实例且**绝不补键 PTT**，防止松手后电台重新发射。
- **诊断**：新增 `arm_ioloop_watchdog()`（`HTTP server started.` 后武装）——心跳超时调度在 IOLoop 上，晚于预定 >8s 即判定假死，`faulthandler.dump_traceback` 把所有线程栈打进日志，30s 防刷屏冷却。下次假死可直接看到阻塞调用点。
- **运维**：`mrrc_multi.sh` 启动时的 `> 日志` 清空改为先 `mv` 为 `.prev` 再写新文件——本次事故中旧实例的死亡现场被启动脚本截断，无法考证；`delete` 命令同步清理 `.prev`。
- **F4b（同日第二轮，09:01 实例日志实证）**：端口假死已消除，但 `p.open()` 在工作线程仍间歇性慢（实测 0.3s~15s+，蓝牙设备 AVDTP 抖动所致）。慢期间 TX 音频帧被静默丢弃 → "按了 PTT、电台发射、全程无调制"（ATR 功率计实证：两段 TX 6-7W 平坦载波 vs 两段 126-153W 正常调制）。修复：① 初始化期间到达的帧缓存 250 帧（5s），完成后补放；② 丢弃路径强制释放 PTT，覆盖 `s:` 与自动键控乱序竞态（安全关键）；③ 设备索引缓存 + 校验，按 PTT 全量枚举 6+ 设备（蓝牙抖动时每次 CoreAudio 查询都可阻塞数百 ms）降为 1 次查询；④ 枚举/`p.open` 分段耗时打点进日志。
- **端到端复盘**：完整因果链（蓝牙 DAC A2DP 协商失败 → CoreAudio 全局阻塞 → 端口假死/TX 静默）、验证方法、安全影响与排查工具箱见 `docs/current/reliability/RC-001-ioloop-wedge-and-tx-silence.md`。

---

## [V6.0.1] - 2026-09-13

### 🪟 Windows 安装包首次内置 WDSP 库

- 新增 `packaging/windows/build_wdsp_dll.ps1`：用 MSYS2/MinGW-w64 构建 `libwdsp.dll`（`-static`，运行时只依赖 `KERNEL32.dll`/`msvcrt.dll`），并自动校验导出符号与依赖。
- 为让 WDSP 源码能在 GCC/MinGW 下编译，新增 `DSP/patches/2026-09-13-windows-mingw-build.patch`：平台守卫补 `__MINGW32__`、`iobuffs.h` 的 `struct _iob` 改名避开 MSVCRT 同名符号、POSIX shim 的 `EnterCriticalSection`/`CloseHandle` 等在 mingw 下前缀化以免与 `libkernel32` 冲突。
- **V6.0.0 及更早的 Windows 包没有 WDSP 库**（`vendor\wdsp\windows\bin\x64\` 是空的），所以 Windows 上 NR2 一直不可用；6.0.2 安装包起随包提供。

### 🎛️ 新增独立「WDSP 设置」页 + 服务端热生效参数

- 新增 `www/wdsp_settings.html` 独立设置页（移动端菜单「🔧 WDSP 设置」、桌面工具栏「🔧WDSP」均可打开），无需改配置文件即可调 WDSP。
- `/WSCTRX` 新增 4 个动作：`setWDSPMaxAtten` / `setWDSPDry` / `setWDSPAGCTop` / `setWDSPPanelGain`，`getWDSPStatus` 同步返回这 4 个值；写入 `wdsp_config` 后按哈希热生效，无需重启。
- 删除页面上的无效控件（GainMethod / NpeMethod / AE 开关）：估计器已固定 MMSE、AE 由等级表决定，留着只会误导。

### 🧹 移动端菜单瘦身 + 修复「Recording 点了没反应」

- 菜单 10 项 → 6 项：删掉与主界面重复的 Band Selection、Mode Selection、Memory Management、Audio Filters（主界面已有 `band-btn`/`mode-btn`/`filter-btn`/M1–M6 记忆条），连带清掉 4 个死函数。
- 修复 `setupMenuItems()` 对所有 `.menu-item` 无条件 `preventDefault()`，导致 Recordings / WDSP 这类真链接被吞掉、点击无任何反应。
- 音频滤波默认改为 **LP2.4k**（`highshelf 2400 Hz / −20 dB`，原先初始化为 `lowshelf 22 kHz / 0` 等价关闭），滤波档位循环列表补上 LP2.4k。

### 🐛 修复

- **ATU 自动调谐回调从未挂上**：`atu_auto_tuner.py` 使用 `os.environ`/`os.name` 却漏了 `import os`，每次启动都报 `设置 ATU 回调函数失败: name 'os' is not defined`，`start_tune`/`stop_tune`/`set_freq` 三个回调被 `except` 吞掉。
- 旧版 `libwdsp`（未含本次 C 改动）启动时只告警一次并说明需重编，不再每帧刷错误。

### 🎙️ WDSP NR2（EMNR）SSB 语音保护 — 修复“声音变形过度”

- **根因**：EMNR 的最小统计噪声估计会把语音自身当噪声（实测干净单音 `gamma=0.97`、掩码 `0.022`；真实语音最强/最弱 bin 掩码均 ≈0.25，SNR 仅改善 ~1 dB），语音被整段削 10~33 dB；其后 AGC（`max_gain=10000`）再用 30~60 dB 补偿增益把残渣与掩码起伏放大回满量程。
- **C 端（`DSP/wdsp`，patch 见 `DSP/patches/2026-09-13-nr2-ssb-voice-protection.patch`）**：新增 `SetRXAEMNRmaxAttenDb`（每 bin 最大衰减）与 `SetRXAEMNRdry`（干湿混合），在 `calc_gain` 的最终掩码上生效；新增 `SetRXANBPFreqs`。
- **NR2 等级重映射**（主轴=每 bin 最大衰减）：level 1/2/3/4 = −6/−12/−16/−20 dB，估计器固定 MMSE（`npe=1`，实测不会把平稳段当噪声）。
- **SSB 带通改由 always-on 的 `nbp0` 承担**（移到 NR 之前，噪声估计更准），不再依赖 `bp1`：修复“NR2 关闭/改带通后 RX 静音”（`bp1` 在非 NR 驱动状态下输出全零）。
- **`fexchange0` 输出饥饿（`error=-2`）不再注入原始输入**（原始输入比处理后高约 18 dB，会造成 5.3 ms 响 click），改为保持上一块输出并计数告警。
- **增益级**：AGC 补偿封顶 `agc_top_db`（默认 +20 dB）；`panel_gain` 0.06 → 0.35（**RX 音量约 +15 dB，可用配置调回**）；AGC OFF 固定增益修正为 0 dB（原传 `1.0` 实为 +1 dB）；MED 时间常数 6/500/500 ms。
- **实测收益**：单音 —36.0 → −5.6 dB（不再被吃）；生产链路语音段衰减 −14.3 → **−2.8 dB**；静音段噪声抑制保留（隔离测量 L2 = 8.2 dB，受上限约束）；饥饿响 click 51 → 0 处。
- **新增配置**：`nr2_max_atten_db`（可选覆盖）、`nr2_dry`、`agc_top_db`、`panel_gain`。
- **Windows 打包注意**：`vendor\wdsp\windows\bin\x64\libwdsp.dll` 必须用 `DSP/patches/2026-09-13-nr2-ssb-voice-protection.patch` 重编（步骤见 `win_pack.md` §2.1），否则只有 MMSE 那一半修复生效，每 bin 最大衰减与“NR2 关闭后静音”修复不生效。

---

## [V6.0.0] - 2026-09-05

### 🪟 Windows 安装包正式发布

- 新增 Windows V6.0.0 安装包发布流程，安装后通过 `MRRC-Launcher.exe` 启动服务并自动打开浏览器。
- 首次运行自动生成本机 `admin` 登录账号，写入 `%LOCALAPPDATA%\MRRC\MRRC_users.db`。
- 生成 `%LOCALAPPDATA%\MRRC\MRRC Quick Start.txt`，开始菜单新增 `Login Info` 快捷方式，普通用户无需手工查找密码。
- Windows 配置文件固定为 `%LOCALAPPDATA%\MRRC\MRRC.conf`，模板默认 IC-M710：`rig_model = IC_M710`、`rig_rate = 4800`、`stop_bits = 2`、音频设备片段 `USB Audio`。
- 文档新增 [Windows Installer Configuration Guide](docs/current/operations/windows-installer-config-guide.md)，同步网站中英文安装页。

### 🔧 Windows 启动与打包修复

- 修复 Windows 中文/GBK 控制台下启动日志含 Unicode 字符时导致 `UnicodeEncodeError` 崩溃的问题。
- 配置文件读取固定为 UTF-8，修复 Windows 安装版读取含中文注释的 `MRRC.conf` 时 `UnicodeDecodeError`。
- 修复 PyInstaller onedir 安装版 `/mobile` 页面硬编码读取 `www/mobile_modern.html`，改为从 `_resource_dir()/www/mobile_modern.html` 加载。
- 移除 RTL-SDR 运行依赖：不再导入 `rtlsdr`，`requirements.txt`/Docker/安装检查/PyInstaller hidden import/Windows DLL 检查均去除 `pyrtlsdr`/`librtlsdr`。
- Windows 安装包仍保留 Panadapter 静态路由，但默认禁用 RTL-SDR 频谱数据流。

---

## [V5.8.5] - 2026-08-30

### 🔧 ATR-1000 天调自动学习修复

- **根因 1（回归）**：`handle_unix_client` 内嵌套的 `dispatch()` 未自行声明 `global is_tx`，
  `start`/`stop` 的赋值只改写了函数局部变量，模块级 `is_tx` 永远为 False →
  自动学习（依赖 is_tx）与 TX 模式轮询静默失效。由 V5.7.1「逐行解析」重构引入。
- **根因 2（设计局限）**：学习入口仍以 `is_tx`（前端 start 信号）判定发射，
  面板直发/外部软件路径永远收不到 start。改为与 SWR 守卫一致的按实测功率判定
  （`power >= LEARN_MIN_POWER`，默认 3W），覆盖所有发射路径。
- 同步修复 `dispatch` 内 `_swr_high_since` 赋值（set_freq/quick_tune/stop 的守卫复位此前同样失效）。

---

## [V5.8.3] - 2026-08-13

### ⚙️ 启动顺序与 iOS RX 缓冲优化

- **启动顺序调整（mrrc_control.sh / mrrc_multi.sh）**：ATR-1000 代理先于 MRRC 启动，
  避免 MRRC 启动时 Unix Socket 尚不存在导致的连接失败告警刷屏（原顺序 MRRC 在前会连刷 4-5 条 WARNING）
- **iOS RX 毫秒水印门控（controls.js / tx_button_optimized.js）**：ScriptProcessor 路径
  对齐 `rx_worklet_processor.js` 的毫秒水印机制 — `__rxPrebufferMs 200 / __rxRecoveryMs 80 / __rxMaxMs 500`，
  冷启动积累缓冲后输出、欠载后按迟滞水位重新武装，替代原硬编码 0.2s 样本上限；
  TX 释放/音频开关同步重置门控，消除 iOS 解码抖动导致的欠载补静音卡顿
- 前端缓存版本号 5.8.1 → 5.8.3（controls.js / tx_button_optimized.js）

---

## [V5.8.2] - 2026-08-09

### 🔧 ATR-1000 功率/SWR 前端不显示修复（IOLoop 线程错位）

- **根因**：tornado 6.5 中 `IOLoop.instance()` 是 `IOLoop.current()` 的别名，**线程相关**。
  ATR-1000 代理连接管理器在重连 Timer 后台线程执行 `_connect()` 时调用 `IOLoop.instance()`，
  Python 3.11 会为后台线程创建并捕获**独立的 asyncio 事件循环**（主线程另有自己的 loop）——
  `add_callback` 排队的电表广播回调被投递到后台线程的 loop，主线程永远不运行它 →
  前端 ATR 面板只收到 open() 的初始快照后无任何实时数据（功率/SWR 不显示、设备状态卡死）。
  典型触发：MRRC 启动时 ATR-1000 代理尚未就绪（如 mrrc_control.sh 先启 MRRC 再启代理，
  或代理崩溃后 MRRC 自动重连）——只要 `_connect` 经后台 Timer 线程成功，广播即永久失效。
- **修复**：模块顶部在主线程固定全局 `MAIN_IOLOOP = IOLoop.instance()`（与主循环 start() 同一对象），
  `ATR1000ProxyManager.main_ioloop` 及所有后台线程的 `add_callback` 一律改用 `MAIN_IOLOOP`：
  - `ATR1000ProxyManager._connect`（重连 Timer 线程）
  - `TRXRIG.setPTT` 内 `_broadcast_ptt` / `_broadcast_ptt_alarm`（rigctld executor 线程）
  - `PTTSafetyMonitor` 内 `_broadcast_tot`（独立监管线程）
- **验证**：复现原始故障场景（先启 MRRC、代理后启动）——修复前 WSATR1000 只收到 1 条初始快照、
  sync 全部无响应；修复后 5/5 广播正常，`start` 后功率/SWR 持续实时推送

---

## [V5.8.1] - 2026-08-09

### ⚡ RX 时延分析与提升（LAN）

- **修复 IOLoop 被 rigctld 阻塞（偶发 >100ms 网络时延 / 卡顿根因）**：
  `sendPTINFOS` 每 5s/客户端在单线程 IOLoop 上同步调用 `getFreq()` → 新建 TCP 连
  rigctld（3s 超时，IC-M710 4800 波特 CAT 缓存失效时偶发 50-200ms），卡住 IOLoop
  → 控制通道 PONG 与 RX 音频投递一起延迟。现改为读 `CTRX.infos["FREQ"]` 缓存
  （FrequencySyncThread 已在后台线程每 2s 刷新），仅在频率变化时同步 ATR-1000
- **on_message 全部 rigctld 阻塞调用 offload 到线程执行器**：`getFreq` / `setFreq` /
  `getMode` / `setMode` / `getPTT`（客户端每 5s 轮询）走 `run_in_executor`，
  与 `setPTT`/`setRFGain`/`setAGC` 的既有 F3 修复一致
- **RX 发送队列轮询延迟 10ms → 3ms**：`tailstream` 稳态 sleep 降至 3ms，
  每帧在 `Wavframes` 平均等待从 ~5ms 降到 ~1.5ms
- **客户端 worklet 水印 LAN 调参**：`prebufferMs 200→100`、`recoveryMs 80→40`、
  `maxMs 600→400`，冷启动/TX→RX 感知延迟减半，LAN 抖动余量仍充足
- **修复 TX→RX 长静音**：worklet `config` 在 priming 期间只允许下调开门阈值，
  不再从 20ms 低水印回跳稳态值导致静音等待；上调仅由 flush/reset 显式重置
- 前端缓存版本号 5.7.2 → 5.8.1

### 🔄 restart.sh / mrrc_multi.sh 停不干净修复

- **`kill_process` 遍历所有匹配 PID**：原实现把多 PID 拼成一个参数传给 `kill` → `invalid pid`
  全部失败，旧进程残留 → 重启时 start 误判 already running 而跳过（新代码不生效）。现逐个
  `kill` + `ps -p` 精确判定残留并强制 `kill -9`，返回真实结果
- **MRRC 匹配模式改精确**：`MRRC.*$INSTANCE` → `MRRC\.$INSTANCE\.conf`。原模式会把
  `tail -f .../MRRC/atr1000_radio1.log` 监控进程误判为 MRRC，导致 stop 杀不掉 / start 跳过
- **stop 结果聚合**：`stop_instance` 聚合 atr1000/MRRC/rigctld 三路结果，任一残留即返回非零，
  `restart.sh` 的 `if ! stop` 不再恒真（原末尾 `print_success` 恒返 0）

---

## [V5.8.0] - 2026-08-09

### ⚡ ATR-1000 SWR>2 自动完整调谐

- **新增 SWR 守卫**：发射期间（实测功率 ≥5W）SWR 严格大于 2.0 持续 ≥1.5s 时，
  自动发送 ATR-1000 完整调谐（mode=2）；30s 冷却；同一频率连续 3 次失败后放弃，
  直到频率变化或 SWR 回落
- **按实测功率判定发射中**：不依赖前端 TX start 信号，覆盖电台直接 PTT / 外部软件发射场景
- **状态重置**：频率变化 >1kHz 或 TX 结束自动重置守卫状态；调谐期间复用 `tuning`
  标志避免重复触发，与自动学习互不干扰
- **学习阈值下调**：`LEARN_MIN_POWER` 5W→3W、`SWR_RETUNE_MIN_POWER` 10W→5W，
  QRP（低功率）操作也能触发学习与自动调谐

---

## [V5.7.2] - 2026-08-09

### 🎛️ RagChew TX 预设修复与优化

- **修复低切 150Hz 失效**：`AudioTX_highCut` 节点此前已初始化并配置为 highpass@150Hz，
  但从未接入音频链（死节点）；现已接入 `preamp → highCut → antiAlias`，低切真正生效
- **启用 3kHz 高切**：RagChew 分支的 `antiAlias2` 由 22kHz 直通改为 3kHz 低通，
  与预设宣称的 3kHz 高切一致（标准预设仍为 4.5kHz）
- **真正启用压缩器**：RagChew 分支压缩器由透明旁路（threshold=0/ratio=1 永不触发）
  改为温和 3:1（-18dB / 3:1 / knee 6 / release 200ms），实现"平稳舒适"定位；
  DEFAULT/MEDIUM/STRONG 仍保持旁路，严格遵循 V5.7 保真哲学
- **修复 UI 预设值脱节**：`mobile_modern.js` TX EQ 面板 fallback 硬编码
  （MEDIUM low:-15 / STRONG low:-20）与实际预设（9 / 12）不符，已对齐
- 噪声门（-50dB / attack 10ms / release 300ms）保持现状，与压缩器 release 200ms 错开，
  无叠加拖尾；缓存版本号 5.7.1 → 5.7.2

---

## [V5.7.1] - 2026-08-09

### 🎙️ RX/TX 链路第二轮优化

- **TX 采集迁移 AudioWorklet**：新增 `tx-capture` worklet（`tx_worklet_processor.js` 重写），
  渲染线程按 960 样本/20ms 组帧回传，替代主线程 ScriptProcessorNode；
  iOS Safari/旧浏览器自动回退，两路共用 `OpusEncoderProcessor.pushSamples()`
- **修复 PTT 尾音丢失**：`stopRecord()` 现在 `encode_float_final()` 补发编码器尾部不完整帧
  （原每次 PTT 结尾最多丢 20ms 语音）
- **修复 TX warmup 空转**：预热帧 160 → 960 样本（原不足一帧，Opus 编码器不产出包）
- **修复麦克风资源泄漏**：`AudioTX_stop()` 现在停止 MediaStream tracks 并关闭 AudioContext
- **RX 采集 320 → 960 样本/次**（20ms@48kHz 对齐 Opus 帧）：消除 320/3 不整除的周期微爆音，
  每帧流水线开销降为 1/3；WDSP 配置哈希改为每 25 帧节流检查
- **消除 TX 录音/分析路径 Opus 双解码**：复用 `PyAudioPlayback._normalize()` 的解码结果；
  修复 TX 录音 48kHz 未降采样写入 16kHz 缓冲导致回放慢 3 倍的 bug
- **TX playback `frames_per_buffer` 按采样率动态对齐 20ms**（不再硬编码 960）

### 📡 ATR-1000 功率/驻波链路修复

- **幽灵功率读数根因修复**：代理 `stop` 动作清零功率/SWR 缓存（原 RX 期间持续显示最后
  一次 TX 功率，且让 MRRC 250ms 快速轮询永久自维持）
- **MRRC 快速轮询改由 CTRX PTT 状态驱动**（功率启发式降为回退）
- **修复 `_broadcast_batch` 从工作线程直接 `write_message` 的线程安全 bug**：
  广播编组到 Tornado IOLoop 执行
- 前端设备状态点改用代理上报的 `connected` 字段（原设备断电也显示在线）；
  SWR 1-99 异常分支加节流告警；`clearDisplay` SWR 内部状态与 DOM 一致化

### 🎛️ IC-M710 AGC / RF 增益控制

- 新增 `/WSCTRX` 命令 `setAGC`/`getAGC`/`setRFGain`/`getRFGain`
  （rigctld `L AGC`/`L RF` → icm710 NMEA `AGC ON/OFF`、`RFG 0-9`；RF 9 档浮点映射取档位
  中点避开 hamlib 截断取整误差）
- 手机端快捷行原 CW/FT8 链接位替换为 AGC 开关 + RF 档位（9-1）按钮，多端广播同步

### 🗑️ FT8/CW 功能整体移除

- 删除 `/WSFT8`、`WS_FT8Handler`、`ft8_integration.py`（JTDX UDP 桥）、`ft8_decoder.py`、
  `www/ft8*`/`www/cw_*` 全部页面、`models/` 与 `www/models/`（cw_decoder.onnx）、
  `dev_tools/test_ft8_packets.py` 及整个 `ft8/` ULTRON 目录
- `mobile.html` 数字模式面板移除 FT8/CW 控件；`sdr_modern` 菜单 CW 项移除
- 电台侧 CW **模式**（`setMode:CW`）不受影响

### 🐛 其他修复

- 修复 `mobile_opt.html` 控制通道 WebSocket 路径错误（`/WSControlTRX` → `/WSCTRX`，
  原路径未注册导致该页控制通道必然 404）
- `mobile_opt` 模式列表移除 CW/FT8，滤波器死代码按钮替换为 AGC/RF 控件

---

## [V5.7.0] - 2026-08-08

### 🎛️ RX 链路音质优化（参考 mrrc_ft710）

- **Opus 码率经 `max_data_bytes` 按帧限幅**：修复 Apple Silicon 上 `opus_encoder_ctl`
  变参 ABI 静默失效导致的码率不受控问题
- **RX 编码器切 AUDIO(2049) 模式 + 固定 32kbps**：移除全局共享自适应比特率
  （单客户端拥塞不再拖累全体）；码率控制 arm64 兼容
- **线格式加 1 字节编解码标签**（0x00=PCM / 0x01=Opus）：客户端按标签确定性解码，
  替换 `<500 字节` 猜帧启发式；ALSA 回退路径同步
- **Opus 帧长 40ms → 20ms**：延迟减半，音质无损失
- **客户端抖动缓冲重构为时间水印 + 迟滞**（prebuffer 200ms / recovery 80ms / max 600ms）：
  修复帧数水印在 Opus 突发到达下的卡顿
- **输入硬限幅与全范围 tanh 改为软膝限幅**（knee 0.95/0.97）：消除对正常语音的持续失真
- **WDSP 采样率 16k → 48k**：EMNR(4096 点 FFT) 用粗 bin，噪声估计平滑，消除"水音"音乐噪声回归；
  新增有状态窗口化-sinc 降采样器供 16k 路径使用
- **NR2 AE 自动均衡参数化**（`nr2_ae_psi` / `nr2_ae_zeta_thresh`，默认 12/0.65）：
  绑定 `SetRXAEMNRaePsi`/`SetRXAEMNRaeZetaThresh`，直接控制频谱减法音乐噪声

### 🎙️ TX 链路高音质化（参考 mrrc_ft710）

- **TX 编码 16k → 48kHz 全带宽**：去掉 3:1 降采样，编码 mic 原生率；44.1k mic 线性重采样
- **64kbps CBR**（VBR 关，FEC/DTX 关）：稳定包大小，复杂语音码率不波动
- **TX 线格式加标签**（m: 消息第 5 字段协商，旧客户端兼容）
- **服务端 TX 电平硬削波 → 软膝限幅**：低失真
- **修复 `frame_size` 缺 `/1000` 的过度分配 bug**（48k 下每帧 3.8MB → 1.9KB）及录音
  `source_rate` 推导
- **TX 保真收紧**：前置增益 +9.5dB → 0dB、压缩器透明旁路、DEFAULT EQ 调平 0/0/0，
  动态交给电台 ALC

### 🧹 Codebase 清理与发布基础设施

- 移除 5 个嵌套 git 仓库（ft8×3、DSP/wdsp、ant_switch/eWeLink-API）
- ft8 修复为 gitlink → gitignore(`ft8/*`) + 只跟踪 `base.json`
- 移除 6 处含私钥文件的跟踪（key 备份/zip/`.orig`），.gitignore 加固
- 客户端脚本缓存破：script 标签统一 `?v=` 版本号 + 静态 JS/CSS 强制 no-cache
- 新增 `restart.sh` 单实例重启脚本

---

## [V5.5.0] - 2026-06-06

### 🔧 ATR-1000 Tune 联动调谐

- Tune 按下发射 1kHz 单音后，若 ATR-1000 监测到 SWR > 1.6，自动触发完整调谐 (`mode=2`)
- 完整调谐结束后比较初始/最终 SWR；如果降低，则更新当前频率记忆参数；如果未降低，则恢复调谐前的 LC/CL、电感、电容参数
- ATR-1000 代理新增 `tuning` 状态转发和 45 秒超时保护，前端可等待调谐完成或稳定后再判断
- 松开 Tune 会取消联动流程，避免无 RF 输出时继续调谐判断

### 文件变更

- `www/modules/tune_cq.js` - Tune 启停接入 ATR-1000 联动流程
- `www/mobile_modern.js` - 新增 SWR 阈值判断、完整调谐等待和参数回滚
- `atr1000_proxy.py` - 转发 ATR-1000 调谐状态并增加超时保护
- `docs/ATR1000_Tuner_Auto_Learning.md` - 补充 Tune 联动完整调谐流程

---

### 📻 频道记忆 & 登录体验优化

**频道记忆保存/召回**:
- 新增 6 频道 3×2 网格记忆槽位 (M1-M6)，替代原有 4 频道横排布局
- 交互模型简化：点按 = 召回频率/模式，长按 = 覆盖保存（无需 SAVE 武装步骤）
- 完整记忆管理面板：召回 / 保存当前 / 清除 / 导出 JSON / 导入 JSON / 清空全部
- 视觉风格统一：SDR 蓝色 (#00d4ff) 设计语言，与 DSP 按钮/快捷控制一致
- 保存/召回闪烁动画 + 触觉反馈

**登录页面重设计**:
- 全新 SDR 蓝色毛玻璃登录页：深色径向渐变背景 + 品牌 Logo + 玻璃拟态卡片
- 移动端完整适配：viewport-fit、安全区域、iOS PWA 支持
- 表单交互优化：自动聚焦、大写键盘适配、输入框聚焦光晕
- 错误提示：密码错误时红色抖动动画 + 明确错误消息

**录音格式升级**:
- 录音格式从 WAV 切换为 MP3 (LAME VBR q:0 最高质量)
- 使用 ffmpeg pipe 编码，大幅减小文件体积

**移动端状态同步**:
- `controls.js` 频率/模式更新时自动同步 `mobileState`
- 频段按钮标签随频率变化自动更新

**文件变更**:
- `www/mobile_modern.html` / `www/mobile_modern_zh.html` - 记忆条带 HTML 重构
- `www/mobile_modern.css` - 新增记忆按钮 + 面板样式 (~280 行)
- `www/mobile_modern.js` - 记忆核心逻辑重写 + 管理面板 (~300 行)
- `MRRC` - 登录页面完整重设计
- `www/controls.js` - 移动端状态同步
- `audio_interface.py` - WAV → MP3 录制
- `atr1000_tuner.json` - 天调数据更新

---

## [V5.4.0] - 2026-06-06

### 🔧 FT8 集成修复与前端优化

**FT8 WebSocket 桥接稳定化**:
- 修复 Python-JS 方法名不匹配导致的 FT8 功能异常
- `ft8_integration.py` 重构，前后端方法对齐
- FT8 Ultron 前端界面优化 (`www/ft8_ultron.html`, `www/ft8_ultron.js`)

**网站与文档**:
- 双语网站全面更新 (EN/ZH)，导航栏一致性修复
- 新增 EFHW 知识库章节 (`website/efhw/`, `website/zh/efhw/`)
- 架构文档与图表更新至 V5.4
- 设计文档页面风格统一

**部署自动化**:
- 新增 Ansible playbook 部署脚本 (`ansible/`)
- `deploy_website.sh` 优化

**文件变更**:
- `ft8_integration.py` - FT8 集成重构
- `www/ft8_ultron.html`, `www/ft8_ultron.js` - FT8 前端优化
- `website/` - 16 个 HTML/CSS 页面更新
- `ansible/` - Ansible 部署脚本
- `atr1000_tuner.json` - 天调数据更新

---

## [V5.3.0] - 2026-05-25

### 🌐 网络监控与 UI 打磨

**网络状态可视化**:
- 实时带宽/延迟显示，网络状态监控
- 状态栏精简，信息密度优化
- 频宽可视化美化

**UI 打磨**:
- 界面细节打磨，现代化风格统一
- 移动端/桌面端体验一致性提升

**文件变更**:
- `www/controls.js` - 网络监控逻辑
- `www/mobile_modern.*` - UI 打磨
- `website/` - 网站页面更新

---

## [V5.2.0] - 2026-05-18

### ⚡ WDSP 配置缓存优化 & RX 音频播放引擎重写

**WDSP 性能优化**:
- 哈希缓存机制：7 个关键参数哈希对比替代每帧 100+ 行属性检查，减少 CPU 开销
- `frames_per_buffer` 256→960，对齐 Opus 帧 (20ms@48kHz → 320samples@16kHz)
- 简化 WDSP 初始化/重配置逻辑，删除冗余调试日志

**RX 音频播放引擎重写**:
- 多 BufferSourceNode 调度替代单节点复用，消除帧间间隙 (pops/clicks)
- 精确时间对齐 (`_rx_nextStartTime`)，每个 buffer 独立创建 source node
- 非递归调度 + `onended` 链式触发，限制并发调度数 (`_rx_maxScheduled=3`)
- 队列深度 10→20，更大缓冲容忍度
- AudioContext resume 处理，适配浏览器自动暂停策略
- 解码失败时丢弃帧而非断裂时间线

**文件变更**:
- `audio_interface.py` - WDSP 哈希缓存、Opus 帧对齐
- `www/audio_rx.js` - RX 播放引擎重写
- `mrrc_multi.sh` - 固定 Python 解释器路径
- `atr1000_tuner.json` - 天调运行数据更新

---

## [V5.1.0] - 2026-05-10

### 🎙️ RagChew TX 音频处理模式

**新增 RagChew 预设**：专为本地强信号、ragchew 轻松聊天优化

| 模块 | 参数 | 值 | 说明 |
|------|------|-----|------|
| **EQ 均衡器** | 低切 (HPF) | 150Hz | 保留低音底气，切除超低频噪声 |
| | 中低频衰减 | 500Hz -2dB | 减少"浊音"区，声音更清澈 |
| | Presence 增强 | 2.4kHz +3dB | 保证清晰度，不尖锐 |
| | 高切 (LPF) | 3.0kHz | 带宽略宽，听感更圆润 |
| **压缩器** | Ratio | 3:1 | 温和压缩，音量平稳 |
| | Threshold | -24dB | 说话时自动稳幅 |
| | Attack/Release | 3ms/250ms | 快速响应，从容释放 |
| **噪声门** | 阈值 | -50dB RMS | 不说话时完全静音 |
| | 释放时间 | 300ms | 避免断字 |

**技术实现**：
- 前端 Web Audio API 实现（BiquadFilter + DynamicsCompressor + Gain Gate）
- 音频链新增：`eqHigh → midCut → presence → compressor → noiseGate → gain_node`
- 标准模式（DEFAULT/MEDIUM/STRONG）不受影响，RagChew 节点自动设为直通

**音频链修复**：
- 修复 `setValueAtTime` 缺失第二参数导致的移动端 TypeError
- 增加 `try/catch` 包裹整个音频链初始化
- 改进错误提示信息，显示具体错误详情

**文件变更**：
- `www/controls.js` - RagChew 预设、压缩器、噪声门、音频链重构、错误修复
- `www/mobile_modern.js` - RagChew 面板显示适配
- `www/mobile_modern.html` - 版本号更新（v=4.9.0）
- `MRRC.conf` / `MRRC.radio*.conf` - RagChew 参数记录

---

## [V5.0.0] - 2026-04-30

### 🎨 移动端UI全面现代化

**视觉设计**:
- 玻璃拟态效果 (Glassmorphism): 毛玻璃卡片 + backdrop-filter blur(12px)
- S表/功率显示卡片半透明背景
- DSP控制面板玻璃效果
- 侧滑菜单毛玻璃背景

**图标系统**:
- 全部emoji替换为Unicode符号 + CSS着色
- 电源: `&#x23FB;`, 音量: `&#x1F50A;`, 录音: `&#x25CF;`
- DSP图标: NR2波形、NB闪电、ANF菱形、NF静音、AGC方格
- 跨平台渲染一致性保证

**触摸优化**:
- 音量滑块触摸热区从2px扩展到28px (视觉保持2px轨道)
- 所有按钮满足WCAG 44px最小触摸目标
- `@media (hover: none)` 下触摸反馈优化

**反馈增强**:
- Vibration API 震动反馈集成
  - 调谐按钮: 8ms 轻震
  - 菜单开合: 15ms 中震
  - 步长切换: 15ms 中震
- TX状态下频率显示红色呼吸光效动画

**语言统一**:
- UI标签全部英文: PWR/SWR/REC/CQ CQ/MED/L/OFF
- 设置面板英文化 (音频设置、WDSP设置、高级设置)
- DSP状态名称英文: NR2 ['OFF','MIN','LO','MED','HI'], AGC ['OFF','LONG','SLOW','MED','FAST']

**CSS优化**:
- 清理约324行冗余/失效CSS代码
- 删除: 旧调谐控件、旧PTT样式、旧音量滑块、旧ATR卡片布局
- 文件体积从46KB降至40KB (约15%瘦身)
- 添加 `contain: layout style paint` 优化卡片渲染性能

**文件变更**:
- `www/mobile_modern.html` - Unicode图标、英文标签
- `www/mobile_modern.css` - 玻璃拟态、TX光效、瘦身15%
- `www/mobile_modern.js` - 震动反馈、英文设置面板、TX状态联动
- `www/controls.js` - 英文设置面板HTML
- `docs/System_Architecture_Design.md` - V5.0.0版本更新

---

## [V4.9.3] - 2026-03-16

### 🔄 频率同步线程 - 第三方软件联动修复

**问题修复**:
- **修复JTDX/flrig频率联动失效**: 原频率同步逻辑依赖WebSocket客户端连接，无客户端时不工作
- **添加独立频率同步线程**: 新增 `FrequencySyncThread` 类，独立于WebSocket连接运行
- **支持第三方软件联动**: JTDX、flrig、wfview等软件改变频率时自动同步天调

**技术实现**:
- 新增 `FrequencySyncThread` 线程类（daemon模式）
- 每2秒检测频率变化（可配置）
- 频率变化时自动调用 `sync_freq_to_atr1000()` 同步到ATR-1000代理
- 启动时自动运行，无需客户端连接

**测试验证**:
- 7.074 MHz → 14.150 MHz → 3.850 MHz → 7.074 MHz 频率切换测试通过
- 天调参数自动调整正常

**文件变更**:
- `MRRC` - 添加 `FrequencySyncThread` 类和启动代码

---

## [V4.9.2] - 2026-03-15

### 🎨 UI风格改版与功能修复

**蓝色系专业风格UI改版**:
- 全新蓝色系配色方案（青色 #00d4ff 为主色调）
- CSS 变量系统化重构，支持主题定制
- 频率显示改为 SDR 风格蓝色数码管效果
- 按钮、菜单、弹窗统一蓝色风格
- 信号强度表(S-Meter)视觉优化

**S表显示优化**:
- 创建独立的 S 表分析器（不受音量控制影响）
- 音频链优化：滤波器后连接独立分析器
- 移动端 S 表更新支持

**CQ功能修复**:
- 修复 CQ 播放完成后自动停止逻辑
- 支持移动端 CQ 按钮状态同步
- 添加 `handleCQCompleteMobile` 移动端处理函数
- 完善 CQ 状态日志输出

**全屏模式功能**:
- 菜单中添加全屏模式按钮
- 支持一键进入/退出全屏
- 菜单按钮文字根据全屏状态自动更新
- 兼容 iOS Safari 和 Android Chrome

**WDSP DSP设置增强**:
- 在设置面板的WDSP区域添加'⚙️ 高级设置...'链接
- 新增高级设置面板，包含详细WDSP参数配置：
  - NR2 降噪强度选择（关闭/极温和/低/中/高）
  - WDSP 各功能独立开关
  - AGC 模式详细说明
- 默认NR2启用（nr2: true），默认级别 level=1（极温和）
- 新增 `setWDSPNR2Level()` 函数用于调节NR2强度
- 优化 `setWDSPNR2()` 函数，启用时自动设置默认level=1

**频率步进调整**:
- 默认步进从 100Hz (0.1kHz) 调整为 1kHz
- `mobileState.tuneStep` 默认值改为 1
- `mobileState.tuneStepIndex` 改为 1
- 更适合日常频率调整习惯

**天调数据更新**:
- `atr1000_tuner.json` 数据更新（样本数、SWR平均值等）

**文件变更**:
- `www/mobile_modern.css` - 蓝色系UI改版
- `www/mobile_modern.html` - 对应HTML结构调整，添加全屏按钮
- `www/mobile_modern.js` - 功能逻辑更新，添加全屏功能、WDSP高级设置、步进调整
- `www/controls.js` - S表和CQ功能修复
- `MRRC.radio1.conf` - NR设置优化
- `atr1000_tuner.json` - 天调数据更新

---

## [V4.9.1] - 2026-03-15

### 🎯 多实例支持深度优化

**多实例架构修复**:
- **配置键大小写修复**: 修复 ConfigParser 键名大小写问题
  - `INSTANCE_UNIX_SOCKET` → `instance_unix_socket`
- **Socket 路径修复**: 修复硬编码的 Unix Socket 路径
  - `sync_freq_to_atr1000` 函数现在使用 `INSTANCE_UNIX_SOCKET` 配置

**文件变更**:
- `MRRC` - 配置键和 Socket 路径修复

---

## [V4.9.0] - 2026-03-14

### 🚀 新功能发布：语音助手、CW模式、SDR界面

**语音文字助手**:
- 新增 `voice_assistant_service.py` 后端服务
- 集成 Whisper ASR 语音识别（支持中文/英文）
- 集成 Piper TTS 语音合成
- 新增移动端界面: `mobile_voice_text.html`
- 新增移动端语音助手界面: `mobile_voice_assistant.html`

**CW 电波模式**:
- 新增 CW DSP 界面: `cw_dsp.html`
- 新增 CW 信号发生器: `cw_generator.html`
- 新增 CW 实时解码: `cw_live.html`
- 新增 CW 简单测试: `cw_simple.html`
- 新增 CW 测试页面: `cw_test.html`

**SDR 现代界面**:
- 全新 SDR 控制界面: `sdr_modern.html`
- 配套 JavaScript: `sdr_modern.js`
- 配套样式: `sdr_modern.css`

**文件变更**:
- `voice_assistant_service.py` - 语音助手服务（新增）
- `VOICE_ASSISTANT_SETUP.md` - 语音助手安装指南（新增）
- `www/mobile_voice_*.html/js/css` - 移动端语音界面（新增）
- `www/cw_*.html` - CW模式页面（新增）
- `www/sdr_modern.*` - SDR现代界面（新增）
- `www/voice_assistant_asr.js` - ASR客户端（新增）

---

## [V4.8.0] - 2026-03-12

### 🎯 音频系统重构与录制功能

**后端优化**:
- **日志优化**: 减少I/O开销，设置日志级别为WARNING
  - 关闭 tornado 和 PIL 的 DEBUG 日志
  - 只输出到控制台，不写文件
- **PTT超时保护增强**: 从2秒(10次×200ms)增加到5秒(25次×200ms)
  - 提高网络延迟容忍度，减少误判
- **信号强度获取改进**: 优先从设备获取真实信号强度
  - 支持 rigctld 协议获取信号强度
  - 支持 hamlib 直接获取
  - 失败时返回 S0 而非随机值

**S表精细化**:
- **新增S表中间刻度**: 添加 S5, S15, S25, S35, S45, S55 等中间值
  - 更精细的信号强度显示 (-54dB ~ +60dB)

**前端增强**:
- **步进按钮修复**: 修正步进切换逻辑和事件绑定
  - 修复点击无响应问题
  - 支持100Hz/1kHz/5kHz/50kHz切换
- **PTT按钮优化**: 增加按钮高度适应更长按压
  - 从圆形改为圆角矩形 (120px → 240px高度)
- **步进显示改进**: 动态更新步进值显示

**音频处理**:
- **软削波功能 (Soft Clipping)**: 
  - 使用 tanh 函数平滑限幅
  - 阈值 0.95 保留足够动态范围
  - 避免硬削波产生的尖锐失真
- **立体声录制优化**:
  - 改为只录制右声道（电台录音通常右声道是RX输出）

**文件变更**:
- `MRRC` - 日志优化、PTT超时增强、信号强度获取改进
- `audio_interface.py` - 软削波、立体声优化
- `www/mobile_modern.js` - 步进按钮修复
- `www/mobile_modern.css` - PTT按钮高度增加、CW按钮样式

---

## [V4.7.0] - 2026-03-10

### 🎯 WDSP 优化与稳定性提升

**WDSP 库路径改进**:
- **添加项目目录搜索路径**: `wdsp_wrapper.py` 自动检测项目目录下的 `DSP/wdsp` 文件夹
  - 便于直接复制项目到不同机器运行，无需系统安装 libwdsp
  - 搜索顺序: 系统路径 → Homebrew路径 → 项目目录

**日志输出优化**:
- **减少WDSP调试日志**: 禁用大量周期性调试输出，降低日志噪音
  - 禁用 `frame_count % 100` 周期性状态打印
  - 禁用 NR2 更新时的详细日志
  - 禁用 AGC 模式切换时的打印
  - 禁用能量对比统计输出
- **保留关键日志**: 仍保留初始化成功/失败、错误等关键信息

**AGC 参数调整**:
- **注释掉 SetRXAAGCTarget**: 避免与 SetRXAAGCFixed 冲突
  - 使用固定增益模式时不需要目标增益设置
  - 简化AGC配置逻辑

**前端增强**:
- **WDSP 状态同步**: 页面加载后自动同步WDSP设置到后端
  - 1秒延迟确保WebSocket连接就绪
  - 支持重试机制（最多4秒等待）
- **sendCommand 调试**: 添加详细调试信息，便于排查问题
- **WebSocket 状态检查**: 连接成功后自动检查并记录状态

**文件变更**:
- `wdsp_wrapper.py` - 库路径优化，日志清理
- `audio_interface.py` - 禁用周期性调试输出
- `www/mobile_modern.js` - WDSP同步增强，调试改进

---

## [V4.6.1] - 2026-03-10

### 🔧 WDSP 关键BUG修复与性能优化

**重要修复**:
- **修复WDSP初始化被注释的致命BUG**: `wdsp_wrapper.py` 中 `_init_wdsp()` 被意外注释，导致WDSP完全未初始化
  - 这是导致之前"嘟噜嘟噜水声"失真和降噪无效的根本原因
  - 修复位置: `wdsp_wrapper.py` 第166-167行
  
**参数优化**:
- **PanelGain设置为0.2**: 修复WDSP输出16倍放大的问题，防止削波失真
- **NR2参数调整**: 默认使用 `gain_method=1` (moderate)，平衡降噪强度和语音保真度
- **禁用带通滤波器**: 暂时禁用（之前导致信号衰减），后续单独调试

**默认配置调整** (`MRRC.conf`):
```ini
[WDSP]
enabled = True
sample_rate = 48000
buffer_size = 256
agc_mode = 3
nr2_enabled = True
nr2_level = 4
nr2_gain_method = 0  # 保守模式，保护语音
nr2_npe_method = 0   # OSMS最优平滑
nr2_ae_run = True    # 必须开启，消除音乐噪音
nb_enabled = True
anf_enabled = True
```

**降噪效果总结**:
- 白噪声降噪: 5-10%（NR2设计针对稳态噪声，对白噪声效果有限属正常）
- 实际短波环境: 预计15-30%降噪效果（背景嘶嘶声）
- AGC工作正常: 弱信号自动增益，强信号自动衰减
- 语音保真度: 优秀，SSB语音自然清晰

**相关文件变更**:
- `wdsp_wrapper.py` - 修复初始化，优化参数
- `audio_interface.py` - 完善WDSP集成
- `MRRC.conf` - 更新默认配置
- `dev_tools/test_wdsp_*.py` - 新增测试工具

## [V4.6.0] - 2026-03-09

### 🎛️ WDSP 数字信号处理集成

#### 核心功能
- **WDSP 库集成**：集成 OpenHPSDR 项目的 WDSP 库，提供专业级 DSP 功能
  - GitHub: https://github.com/g0orx/wdsp
  - 需要先编译安装 `libwdsp` 库
- **NR2 频谱降噪**：基于谱减法的降噪算法，专门针对 SSB 语音优化
  - 降噪增益：15-20dB
  - 语音保真度：极高（让 SSB 听起来像 FM）
- **NB 噪声抑制**：消除脉冲干扰（电器火花、雷电等）
- **ANF 自动陷波**：自动消除单频干扰（CW 报音、载波干扰）
- **AGC 自动增益**：4 种模式（LONG/SLOW/MED/FAST）适应不同场景
- **带通滤波器**：可配置低切/高切频率，默认 300-2700Hz SSB 优化

#### 架构改进
- **处理流程**：48kHz 采样率 WDSP 处理 → 16kHz Opus 编码传输
  ```
  电台音频 (48kHz Float32)
      ↓
  DC去除 → AGC预放大 → 软削波保护
      ↓
  Int16转换 (48kHz)
      ↓
  WDSP处理 (NR2/NB/ANF/AGC)
      ↓
  Opus编码 (16kHz/20kbps)
      ↓
  WebSocket传输 → 前端
  ```
- **替换 RNNoise**：WDSP 成为默认降噪方案，RNNoise 降级为可选
- **前端控制**：移动端设置面板实时控制所有 DSP 参数
- **状态持久化**：Cookie 保存用户 WDSP 设置，页面刷新后恢复
- **WebSocket 命令**：支持动态开启/关闭各项 DSP 功能

#### 性能对比
| 特性 | WDSP (NR2) | RNNoise |
|------|-----------|---------|
| 算法类型 | 频谱减法 | 神经网络 |
| 降噪深度 | 15-20 dB | 10-15 dB |
| 语音保真度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| SSB 优化 | ✅ 专门优化 | ❌ 通用语音 |
| 延迟 | < 20ms | 30-50ms |
| 参数可调 | ✅ 多项参数 | ❌ 固定模型 |

#### 配置迁移
```ini
# 旧配置（RNNoise）
[RNNOISE]
enabled = True  # 改为 False

# 新配置（WDSP）
[WDSP]
enabled = True  # 默认启用
sample_rate = 48000
buffer_size = 256
nr2_enabled = True
nb_enabled = True
anf_enabled = False
agc_mode = 3  # MED
bandpass_low = 300.0
bandpass_high = 2700.0
```

#### 前端控制
在移动端界面"设置"菜单中：
- 🎛️ WDSP 主开关（联动禁用/启用子控件）
- 频谱降噪 (NR2)
- 噪声抑制 (NB)
- 自动陷波 (ANF)
- AGC 模式选择（关闭/长/慢/中/快）

#### 安装 WDSP 库
**macOS:**
```bash
cd /tmp && git clone https://github.com/g0orx/wdsp.git
cd wdsp && make
sudo cp libwdsp.dylib /usr/local/lib/
```

**Linux:**
```bash
cd /tmp && git clone https://github.com/g0orx/wdsp.git
cd wdsp && make
sudo cp libwdsp.so /usr/local/lib/ && sudo ldconfig
```

#### 文件变更
- `wdsp_wrapper.py` - WDSP Python 封装（新增）
- `audio_interface.py` - 集成 WDSP 到 RX 音频处理链
- `MRRC` - 添加 WebSocket 控制命令
- `www/mobile_modern.js` - 前端 WDSP 控制面板 + Cookie 持久化
- `www/mobile_modern.css` - WDSP UI 样式
- `www/controls.js` - WebSocket 消息处理
- `MRRC.conf` - WDSP 配置段
- `DSP.md` - WDSP 详细文档（新增）
- `IFLOW.md` - 架构文档更新
- `README_CN.md` - 用户手册更新
- `AOD.md` - 主要功能更新

#### Bug 修复
- 修复移动端 WDSP 设置面板状态不保存的问题
- 添加 Cookie 持久化，设置可跨会话保存
- 连接成功后自动同步 WDSP 状态到后端

---

## [V4.5.17] - 2026-03-08

### 🔧 ATU 天调系统修复与优化

#### 数据解析修复
- **RELAY_STATUS 字段位置修正**：根据实际测试修正数据解析位置
  - `data[3]` → SW（网络类型：0=LC, 1=CL）
  - `data[4]` → IND（电感索引，如 47=4.7uH）
  - `data[5]` → CAP（电容索引，如 79=790pF）

#### 数据清理
- 清理 JSON 中 6 条脏数据（sw=3/sw=47 等无效值）
- 保留 136 条有效学习记录

#### 参数调用统一
- 统一 `set_relay()` 调用参数顺序为 `(sw, ind, cap)`
- 修复三处调用点：自动调谐、快速调谐、手动设置

#### 微调模式改为存储调谐
- `_fine_tune()` 方法从扫描模式改为存储调谐模式
- 优先从映射表获取已学习的参数直接应用
- 存储参数不达标时回退到初始参数
- 大幅减少调谐时间（从~63次测试减少到1-2次）

#### SWR 过滤增强
- 学习逻辑排除 SWR=1.0 假数据（阈值改为 1.01）
- 保存结果限制 SWR 在 1.01-2.0 范围内

#### 第三方软件联动支持
- 支持 JTDX、flrig、wfview 等通过 rigctld 联动
- MRRC 定期从 rigctld 读取频率并同步给 ATR-1000 代理
- 无需打开网页界面，频率变更自动触发天调

## [V4.5.16] - 2026-03-08

### 🎯 ATR-1000 天调智能学习与快速调谐

#### 核心功能
- **智能学习**：发射时自动记录频率与天调参数（SW、IND、CAP）的对应关系
- **快速调谐**：切换频率时自动应用已学习的天调参数
- **频率同步**：MRRC 主程序实时同步频率给 ATR 代理
- **参数持久化**：学习记录保存在 `atr1000_tuner.json`，重启后自动加载

#### 协议修正
通过实际测试修正了 ATR-1000 协议解析：

| 项目 | 修正前 | 修正后 |
|------|--------|--------|
| SW 字段位置 | data[4] | data[3] |
| SW 映射 | 0=CL, 1=LC | 0=LC, 1=CL |
| IND 发送值 | 直接发送 | 原值÷10 |
| CAP 发送值 | 原值×10 | 直接发送 |

#### 继电器状态帧解析
```
原始数据: ff050701031b1e000e01
         │  │  │  │  │  │
         │  │  │  │  │  └─ data[6] = IND (电感)
         │  │  │  │  └──── data[5] = CAP (电容)
         │  │  │  └─────── data[4] = 保留
         │  │  └────────── data[3] = SW (网络类型)
         │  └───────────── LEN
         └──────────────── CMD
```

#### 值转换示例

| 频率 | SW | IND存储 | IND发送 | L显示 | CAP存储 | CAP发送 | C显示 |
|------|-----|---------|---------|-------|---------|---------|-------|
| 7MHz | CL | 30 | 3 | 0.3uH | 27 | 27 | 270pF |
| 14MHz | LC | 10 | 1 | 0.1uH | 9 | 9 | 90pF |

#### 节流保护
- 相同参数不重复发送
- 最小发送间隔 5 秒
- 防止设备频繁重启

#### 文件变更
- `atr1000_proxy.py` - 修正协议解析，添加频率同步接口
- `atr1000_tuner.py` - 天调存储模块
- `atr1000_tuner.json` - 学习记录存储
- `MRRC` - 添加 `sync_freq_to_atr1000()` 频率同步函数
- `docs/ATR1000_Tuner_Auto_Learning.md` - 完整技术文档

---

## [V4.5.5] - 2026-03-06

### 🚀 部署配置优化

#### 相对路径重构
所有脚本和配置文件改为相对路径，支持任意目录部署：

| 文件 | 改进内容 |
|------|---------|
| `mrrc_control.sh` | 使用 `$SCRIPT_DIR` 自动检测目录 |
| `mrrc_monitor.sh` | 使用 `$SCRIPT_DIR` 自动检测目录 |
| `mrrc_setup.sh` | 使用 `$SCRIPT_DIR` 并自动配置 launchd 服务 |
| `com.user.mrrc.plist` | 改为模板格式，使用 `{{INSTALL_DIR}}` 占位符 |

#### 证书配置优化
- 统一证书目录结构 (`certs/`)
- 添加详细的证书更换步骤
- 支持灵活的证书命名配置

#### 部署指南完善
- 添加完整的证书更换流程
- 添加硬件设备配置说明（串口、音频设备）
- 添加跨平台部署指南（macOS/Linux）

#### 技术细节
```bash
# 脚本自动检测目录
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# launchd 服务自动配置路径
sed "s|{{INSTALL_DIR}}|$MRRC_DIR|g" com.user.mrrc.plist > ~/Library/LaunchAgents/
```

---

## [V4.5.4] - 2026-03-06

### 🎵 WebRTC 最佳实践优化

#### 优化内容
基于 WebRTC 推荐参数优化 Opus 编码：

| 参数 | 优化前 | 优化后 | 说明 |
|------|--------|--------|------|
| 帧长 | 40ms | **20ms** | WebRTC 推荐值，更快响应 |
| 编码复杂度 | 10 | **5** | 平衡 CPU 和音质 |
| DTX 静音检测 | 关闭 | **开启** | 静音时不编码，释放 CPU |
| 帧大小 | 640 samples | **320 samples** | 配合 20ms 帧长 |

#### 预期效果
- 更快的音频处理周期（50次/秒 vs 25次/秒）
- 降低 CPU 占用（复杂度降低 + DTX）
- 静音时不编码，减少网络流量

#### 技术细节
```javascript
// Opus 编码器配置（WebRTC 最佳实践）
complexity = 5;         // 0-10，平衡 CPU 和音质
DTX = enabled;          // 静音时不编码
frameDuration = 20ms;   // WebRTC 推荐
sampleRate = 16000Hz;   // 保持 16kHz
```

---

## [V4.5.3] - 2026-03-06

### 🔍 ATR-1000 PTT 发射时功率/驻波更新延迟问题复盘

#### 问题描述
- **现象**：TUNE 模式下功率/驻波更新及时，PTT 发射模式下更新延迟严重甚至无更新
- **影响**：移动端用户无法实时监控发射功率和驻波比

#### 尝试的方案

| 方案 | 内容 | 结果 | 原因分析 |
|------|------|------|----------|
| **方案1** | 简化 TX 音频处理，移除降采样和帧累积 | ❌ PTT 立即切回 RX | 采样率不匹配（后端期望16kHz，实际发送48kHz） |
| **方案2** | 移动端切换到 PCM 模式（encode=0） | ❌ RX 全是噪音 | encode 变量同时控制 TX 编码和 RX 解码，后端仍发 Opus |
| **方案3** | 降低 Opus 码率到 8kbps | ❌ 无改善 | CPU 占用不是主要瓶颈 |

#### 根本原因分析

1. **架构限制**：`encode` 变量同时控制 TX 编码和 RX 解码，无法单独切换
2. **主线程阻塞**：`ScriptProcessorNode.onAudioProcess` 每 20ms 执行一次，阻塞 ATR-1000 WebSocket 消息处理
3. **消息处理延迟**：ATR-1000 sync 响应需要在主线程空闲时才能处理

#### 技术细节

```
TX 音频处理链路（每 20ms 执行）：
麦克风 → 降采样(48k→16k) → 帧累积(640样本) → Opus 编码 → WebSocket 发送
         ↓
    主线程阻塞 5-10ms
         ↓
    ATR-1000 sync 响应被延迟
```

#### 未来优化方向

| 优先级 | 方案 | 难度 | 预期效果 |
|--------|------|------|----------|
| **高** | Web Worker 音频编码 | 高 | 彻底释放主线程 |
| **中** | 分离 TX/RX 编码控制 | 中 | 允许 TX 用 PCM，RX 用 Opus |
| **低** | 后端 sync 节流 | 低 | 减少设备负载 |
| **低** | 增大 ScriptProcessorNode 缓冲区 | 低 | 降低回调频率 |

#### 结论

当前系统核心功能（TX/RX 音频）稳定工作。ATR-1000 响应延迟问题需要较大的架构改动（Web Worker），建议在未来版本中规划实施。

---

## [V4.5.2] - 2026-03-06
### 🔧 ATR-1000 通讯机制分析

**主题：ATR-1000 通讯频率与数据同步机制分析**

### 分析内容
- **通讯机制审查**：全面分析前端-后端-设备三方数据流
- **当前性能确认**：0.5秒更新间隔已正确实现
- **负载评估**：当前设备负载在可接受范围内

### 当前实现状态
| 组件 | 优化措施 | 状态 |
|------|---------|------|
| 前端 | 500ms sync 间隔 + 双重保护 | ✅ 已实现 |
| UHRR | 50ms 批量广播 | ✅ 已实现 |
| 代理 | 被动模式，不主动 SYNC | ✅ 已实现 |

### 优化建议（已记录，待后续实施）
- 后端 SYNC 命令节流（500ms）
- 智能频率策略（RX 1秒/TX 0.5秒）

### 文件变更
- 无代码变更，仅版本号更新

---

## [V4.5.1] - 2026-03-06
### 🎨 频率调整按钮布局优化

**主题：移动端频率调整按钮布局优化**

### 改进内容
- **布局重设计**：从交叉排列改为上下分离
  - 上排：+50, +10, +5, +1（增加频率）
  - 下排：-50, -10, -5, -1（减少频率）
- **视觉优化**：统一浅灰背景，乳白色加粗文字
- **操作习惯**：符合"上加下减"的自然认知

### 文件变更
- `www/mobile_modern.html` - 频率调整按钮HTML结构
- `www/mobile_modern.css` - 按钮样式优化

---

## [V4.5.0] - 2026-03-06
### 🎉 ATR-1000 实时功率显示稳定版

**主题：ATR-1000 功率/SWR 实时显示完全稳定**

### 核心改进

#### ATR-1000 实时显示优化
- **PTT 期间实时更新**：发射时功率/SWR 实时显示，延迟 <500ms
- **TUNE 模式同步**：天调模式同样支持实时功率显示
- **双重时间保护**：确保 sync 请求最小间隔 500ms，避免压垮设备
- **连接预热机制**：页面加载时预先建立连接，PTT 响应 <200ms

#### WebSocket 状态检查
- **防止错误发送**：检查 WebSocket 状态后再发送音频数据
- **避免 CLOSING/CLOSED 状态错误**：不再向已关闭连接发送数据

#### AudioWorklet 优化
- **欠载计数器重置**：PTT 释放时重置 AudioWorklet 欠载计数
- **日志清理**：减少不必要的控制台日志

### 性能指标
| 指标 | V4.4 | V4.5 |
|------|------|------|
| PTT 到功率显示 | ~2秒 | <200ms |
| Sync 请求间隔 | 不稳定 | 稳定 500ms |
| WebSocket 错误 | 偶发 | 无 |
| ATR-1000 稳定性 | 有压垮风险 | 稳定运行 |

### 文件变更
- `www/controls.js` - WebSocket 状态检查
- `www/mobile_modern.js` - 双重时间保护、心跳优化
- `www/mobile_modern.html` - 版本号更新
- `www/rx_worklet_processor.js` - 欠载计数器重置

### 版本历史详情

#### V4.4.22c - 双重时间保护
- 添加时间戳检查确保 sync 最小间隔 500ms
- 防止 setInterval 被错误调用多次

#### V4.4.22b - 心跳间隔修复
- 修正心跳间隔为 0.5 秒
- AudioWorklet 欠载计数器重置

#### V4.4.22 - WebSocket 状态检查
- PTT 期间检查 WebSocket 状态
- 避免向已关闭连接发送数据

---

## [V4.4.9] - 2026-03-06
### ✨ 频率显示初始化优化

**主题：刷新页面时从电台获取实际频率**

### 问题描述
- 刷新页面时频率显示默认为 7053 kHz
- 用户期望看到电台当前的实际频率

### 修复内容
- **showTRXfreq 函数优化**：支持新的 5 位 kHz 移动端格式
- **WebSocket 连接时自动获取频率**：`wsControlTRXopen()` 发送 `getFreq:` 命令
- **向后兼容**：同时支持旧版 9 位 Hz 格式

### 技术实现
- 页面加载 → WebSocket 连接 → 发送 `getFreq:` → 收到频率 → 调用 `showTRXfreq()` → 更新显示
- 新格式：`07053` = 7053 kHz（5 位数字）
- 旧格式：`007053000` = 7053000 Hz（9 位数字）

### 文件变更
- `www/controls.js` - `showTRXfreq()` 函数支持新旧两种格式

---

## [V4.4.0] - 2026-03-05
### 🚀 ATR-1000 Real-time Display Major Fix

**Theme: Solving the Long-standing Issue of Delayed Power/SWR Display**

### Problem Analysis
- **Root Cause 1**: Tornado's `IOLoop.add_callback()` batches messages, causing 2-5 second delays
- **Root Cause 2**: WebSocket `write_message()` must be called in main thread (with event loop)
- **Root Cause 3**: Frontend JavaScript syntax error (`try` without `catch`) broke all functionality
- **Root Cause 4**: Excessive logging caused performance overhead

### Backend Optimizations
- **Batch Broadcasting**: Collect messages in 50ms batches, broadcast only latest data
- **Thread Safety**: Use `add_callback` for thread-safe WebSocket communication
- **Reduced Logging**: Only log when power/SWR changes significantly

### Frontend Fixes
- **Syntax Error Fixed**: Added missing `catch` block in `_doUpdateDisplay()`
- **Removed Throttling**: Direct DOM update without RAF or throttle
- **Error Handling**: Added try-catch blocks for robustness

### Performance Results
| Metric | Before | After |
|--------|--------|-------|
| Broadcast Delay | 2-5 seconds | <500ms |
| Display Update | Often missing | Real-time |
| Power Button | Not working | Fixed |

### Files Changed
- `UHRR` - Batch broadcast mechanism, thread-safe WebSocket
- `www/mobile_modern.js` - Syntax fix, optimized DOM updates
- `www/mobile_modern.css` - UI refinements

---

## [V4.3.8] - 2026-03-05
### 🐛 Logging and ATR-1000 Stability Fixes

**Theme: Fix Performance Impact from Excessive Logging**

### Fixed
- **Opus encoding log**: Reduced from every frame to every 100 frames
- **ATR-1000 proxy**: Automatic reconnection on device disconnect
- **UHRR logging**: Reduced log frequency for ATR-1000 data forwarding

### Optimized
- CPU usage reduced by ~80% from logging overhead
- Log files grow much slower

---

## [V4.3.6] - 2026-03-05
### ⚡ ATR-1000 Real-time Display Optimization

**Theme: End-to-End Latency Analysis and Optimization**

### Analysis Results
- **Data push frequency**: ATR-1000 device pushes data at irregular intervals (100-900ms)
- **SYNC timing**: Previous 500ms interval was too slow for real-time updates
- **Log overhead**: Excessive logging causing performance impact

### Optimized
- **SYNC interval**: Changed from 500ms to 300ms for faster data triggering
- **UHRR broadcast**: Immediate broadcast without waiting, reduced log frequency
- **Frontend logging**: Only log when power/SWR changes significantly
- **Removed**: Unnecessary debug logs in updateDisplay()

### Expected Effect
- Display update latency: ~500-900ms → ~300-400ms
- Reduced CPU usage from logging overhead

---

## [V4.3.5] - 2026-03-04
### 📚 System Architecture Documentation Update

**Theme: Complete Architecture Refactoring for V4.3**

### Updated
- **System_Architecture_Design.md**: Complete architecture refactoring
  - Added ATR-1000 integration module
  - Added TX EQ (3-band equalizer) component
  - Updated architecture diagrams with new components
  - Added ATR-1000 WebSocket protocol documentation
  - Updated data flow diagrams
  - Added tuner storage module description
  - Updated version history to V4.3.4

### New Components Documented
- ATR-1000 Bridge (UHRR)
- ATR-1000 Independent Proxy (atr1000_proxy.py)
- Tuner Storage Module (atr1000_tuner.py)
- TX Equalizer (3-band audio EQ)
- ATR-1000 Client Module (mobile_modern.js)

---

## [V4.3.4] - 2026-03-04
### 📚 ATR-1000 Integration Documentation

**Theme: Complete ATR-1000 Integration Guide**

### Added
- **IFLOW.md**: Added comprehensive ATR-1000 integration documentation
  - Architecture design diagram
  - Startup methods and configuration
  - Data protocol specification
  - Tuner storage module description
  - Performance optimization details
  - Troubleshooting guide

---

## [V4.3.3] - 2026-03-04
### ⚡ ATR-1000 Connection Pre-warming

**Theme: Reduce PTT Press Latency**

### Optimized
- **Pre-connection**: ATR-1000 WebSocket connection established on page load
- **Connection persistence**: Keep connection alive after TX ends
- **SYNC pre-warming**: Send SYNC every 2s when client connected (not just during TX)
- **Removed**: Connection close on TX stop - connection stays warm

### Effect
- PTT press to power display: ~1-2s → ~100-200ms
- First TX after page refresh: instant response

---

## [V4.3.2] - 2026-03-04
### 🐛 ATR-1000 Display Optimization

**Theme: Improve Real-time Display Responsiveness**

### Fixed
- **Frontend Display Update**: Always call `updateDisplay()` on data receive, remove change detection dependency
- **Proxy Log Output**: Restore broadcast logging when power > 0
- **Debug Console Log**: Add power/SWR change logging for troubleshooting

### Optimized
- Reduced unnecessary conditional checks in frontend message handler
- Cleaner log output (only show when actual power is present)

---

## [V4.3.1] - 2026-03-04
### 🐛 ATR-1000 Display Fix & Tuner Storage Module

**Theme: Real-time Power/SWR Display and Tuner Parameter Storage**

### Added
- **ATR-1000 Tuner Storage Module** (`atr1000_tuner.py`)
  - Store tuner parameters (LC/CL, inductance, capacitance) by frequency
  - Auto-load matching parameters when frequency changes
  - JSON file persistence (`atr1000_tuner.json`)

- **Relay Status Parsing** in ATR-1000 proxy
  - Parse SCMD_RELAY_STATUS (command 5)
  - Extract SW (LC/CL), inductance index, capacitance index
  - Display in frontend UI

- **Frontend UI**: Tuner operation buttons
  - "Tune" button: Start auto-tuning
  - "Save" button: Save current parameters
  - "Records" button: View saved parameters

### Fixed
- **ATR-1000 WebSocket Data Forwarding** in UHRR
  - Use `IOLoop.add_callback()` for thread-safe WebSocket writes
  - Fixed display lag on mobile devices

### Technical Details
- **Data Flow**: Proxy → Unix Socket → UHRR → WebSocket (IOLoop) → Frontend
- **Tuner Storage**: Frequency-based parameter lookup with ±50kHz tolerance
- **Commands**: `set_relay`, `tune`, `save_tuner` actions

---

## [V4.3.0] - 2026-03-04
### 🔌 ATR-1000 Architecture Separation

**Theme: Independent ATR-1000 Proxy for Better Performance**

### Added
- **Independent ATR-1000 Proxy Program** (`atr1000_proxy.py`)
  - Separate process that doesn't block UHRR main program
  - Unix Socket communication with UHRR (`/tmp/atr1000_proxy.sock`)
  - Auto-reconnect to ATR-1000 device
  - On-demand data requests (only when clients connected)

- **ATR-1000 WebSocket Endpoint** in UHRR
  - New route `/WSATR1000` for frontend communication
  - Bridges frontend WebSocket to independent proxy via Unix Socket

### Changed
- **Data Request Interval**: Optimized from 0.3s to 1.0s for lower CPU usage
- **Frontend ATR-1000 Module**: Re-enabled with improved polling management
  - Added `_pollInterval` variable for proper timer management
  - Added `stopDataPolling()` function

### Architecture
```
Frontend (mobile_modern.js)
    ↓ WebSocket (/WSATR1000)
UHRR Main Program
    ↓ Unix Socket (/tmp/atr1000_proxy.sock)
ATR-1000 Independent Proxy (atr1000_proxy.py)
    ↓ WebSocket
ATR-1000 Device (192.168.1.63:60001)
```

### Benefits
| Feature | Before | After |
|---------|--------|-------|
| PTT Release Delay | ~2 seconds | < 100ms |
| CPU Usage (ATR-1000) | High (0.3s interval) | Low (1.0s interval, on-demand) |
| Architecture | Coupled | Decoupled independent process |

### Usage
```bash
# Start ATR-1000 proxy (background)
python3 atr1000_proxy.py --device 192.168.1.63 --port 60001 &

# Start UHRR main program
./mrrc_control.sh start
```

---

## [V4.2.0] - 2026-03-02

### 🎙️ TX Audio Equalizer

**Theme: Shortwave Communication Voice Optimization**

### Added
- **TX EQ System**: Three-band equalizer for transmit audio optimization
  - Low frequency boost (lowshelf @ 200Hz)
  - Mid frequency enhancement (peaking @ 1000Hz)
  - High frequency attenuation (highshelf @ 2500Hz)

- **Four Presets for Shortwave Communication**:
  | Preset | Low | Mid | High | Description |
  |--------|-----|-----|------|-------------|
  | Default | 0dB | 0dB | 0dB | No processing |
  | HF Voice | +4dB | +6dB | -3dB | Enhanced mid/low for SW voice |
  | DX Weak | +6dB | +8dB | -6dB | Strong mid/low for weak signals |
  | Contest | +2dB | +4dB | -2dB | Balanced for quick QSOs |

- **Mobile UI**: TX Equalizer panel in menu with preset selection
- **Persistence**: EQ preset saved to Cookie

### Technical Details
- Audio chain: micSource → eqLow → eqMid → eqHigh → gain_node → processor
- Uses Web Audio API BiquadFilter nodes
- Real-time parameter adjustment support

---

## [V4.1.0] - 2026-03-01

### 🏷️ Project Rebranding

**Theme: Mobile First - MRRC (Mobile Remote Radio Control)**

### Changed
- **Project Name**: Renamed from "Universal HamRadio Remote (UHRR)" to "Mobile Remote Radio Control (MRRC)"
- **Design Philosophy**: Mobile-first approach with emphasis on "Amateur Radio, Anytime, Anywhere"
- **Documentation**: Complete rebranding across all README files

### Added
- **Bilingual README**: Language-switchable documentation (English/Chinese)
- **Mobile-First Tagline**: "随时随地，畅享业余无线电" / "Amateur Radio, Anytime, Anywhere"

### Highlights
| Feature | Description |
|---------|-------------|
| 📱 Mobile First | Optimized for touch, one-hand operation |
| 🌍 Remote Anywhere | Control your station from anywhere |
| ⚡ Ultra Low Latency | TX→RX switching < 100ms |

---

## [V4.0.1] - 2026-03-01

### 🎨 Mobile Interface Enhancement

**Theme: S-Meter & Audio Control Improvements**

### Added
- **Volume Control on Main Screen**: Real-time AF gain slider with visual feedback (0-100%)
- **S-Meter Signal Text Display**: Shows signal level (S0-S9+60) with dB value
- **Hidden Audio Elements**: C_af and SQUELCH elements for controls.js compatibility

### Changed
- **S-Meter Display**: Rewritten to use correct SP mapping table (S0-S9+60dB)
- **Audio Settings Panel**: Improved slider initialization from Cookie values
- **Cookie Loading**: Now syncs main screen volume slider on page load

### Fixed
- **S-Meter Mapping**: Corrected signal level to pixel position mapping
- **AF Gain Synchronization**: Bidirectional sync between main screen and settings panel
- **Audio Gain Control**: Properly calls AudioRX_SetGAIN() and AudioTX_SetGAIN()

### Technical Details
| Feature | Implementation |
|---------|---------------|
| S-Meter Range | S0 (0px) to S9+60 (240px) |
| AF Gain Range | 0-100% (maps to 0-1000 internal) |
| Cookie Sync | Real-time bidirectional |

---

## [V4.0.0] - 2026-03-01

### 🎯 Milestone Release

**Theme: Performance Optimization & Architecture Simplification**

### Added
- **TUNE Button**: Long-press to transmit 1kHz tone for antenna tuner adjustment
- **End-to-End Analysis Report**: Comprehensive performance analysis and optimization recommendations
- **Modern Mobile Interface**: Optimized for iPhone 15 and modern mobile browsers

### Changed
- **Frequency Step Buttons**: Changed from 1k/100/10Hz to 10k/5k/1kHz with improved layout
- **TX→RX Switching Latency**: Optimized from 2-3 seconds to <100ms
- **PTT Command Format**: Unified command format (`ptt:` → `setPTT:`)

### Fixed
- **TX→RX Switching Delay**: Fixed PTT command not reaching backend
- **Audio TX Stop Command**: Now properly triggers PTT release
- **Control TRX Command Format**: Corrected PTT command format in control_trx.js

### Removed
- **VPN Functionality**: Removed all VPN-related files and scripts
- **Bottom Navigation Bar**: Removed unused Radio/Memory/Settings/Digital buttons
- **Redundant Scripts**: Cleaned up unused VPN configuration scripts

### Performance
| Metric | V3.x | V4.0 | Improvement |
|--------|------|------|-------------|
| TX Latency | ~100ms | ~65ms | 35% faster |
| RX Latency | ~100ms | ~51ms | 49% faster |
| TX→RX Switch | 2-3s | <100ms | 95%+ faster |
| PTT Reliability | 95% | 99%+ | More reliable |

### Documentation
- Updated all architecture documents to v4.0.0
- Added comprehensive end-to-end analysis report
- Updated IFLOW.md with complete version history

---

## [V3.2.0] - 2025-01-15

### Added
- Mobile audio optimization
- TX→RX switching delay fix
- iOS Safari AudioContext suspend fix

### Fixed
- Mobile frequency/mode display update
- Mobile menu functionality (band, mode, filter, settings)

---

## [V3.1.0] - 2025-01-10

### Added
- Mobile audio and PTT optimization
- iPhone browser compatibility fixes

### Fixed
- Audio processing on mobile devices
- PTT button responsiveness

---

## [V3.0.0] - 2024-12-20

### Added
- Modern mobile interface (iPhone 15 optimized)
- AAC/ADPCM audio encoding support
- TCI protocol support
- NanoVNA vector network analyzer integration
- PWA support with manifest.json and service worker

### Changed
- Improved mobile touch interactions
- Enhanced audio quality

---

## [V2.0.0] - 2024-11-15

### Added
- System architecture redesign
- AudioWorklet low-latency playback
- Int16 encoding for 50% bandwidth reduction
- TLS encryption support
- User authentication

### Changed
- Migrated from ALSA to PyAudio for cross-platform support
- Optimized audio buffering

---

## [V1.0.0] - 2024-10-01

### Added
- Initial release based on F4HTB/Universal_HamRadio_Remote_HTML5
- Basic remote radio control functionality
- WebSocket-based audio streaming
- Hamlib/rigctld integration
- Web-based control interface

---

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).
Based on [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5).

# 支持日志一键上传（Support Bundle）设计

> 状态：已获用户批准（2026-09-16），接收端选 (a)：部署在 `www.vlsc.net` 自有站点。
> 目标：用户在「🐞 遇到问题」里点几下，就能把一个**脱敏、自证**的诊断包送到维护者手里，
> 不用来回问"你的日志呢"。

## 1. 目标与非目标

**目标**

- 一键生成诊断包（关键日志 + 环境快照 + 自动体检摘要），上传到自有接收端；
- 维护者能在一个（带密码的）列表页看到：问题描述、环境摘要、下载完整包；
- 上传前**可预览清单**、**脱敏**、用户主动点击才发送；
- 离线/不想上传时能**只保存到本地**并把路径告诉用户。

**非目标**

- 不做实时遥测/自动上报（隐私与信任成本过高）；
- 不做工单系统（列表页 + 包足够，YAGNI）；
- 不采集用户按键/录音内容（可选音频只在他勾选时收 5 秒 RX 音频）。

## 2. 包结构

`support-<YYYYmmdd-HHMMSS>.zip`（ZIP_DEFLATED，目标 < 8 MB，硬上限 20 MB）：

```
manifest.json               # 包内清单：版本、生成时间、包含项、脱敏统计、平台信息
README.txt                  # 人读说明：这是什么、包含什么、哪些被脱敏
problem.txt                 # 用户填写的问题描述（+ 可选呼号/联系方式）
logs/MRRC.log               # 尾部 ≤2 MB（按行边界截断，保留最后 N 行）
logs/MRRC.log.prev          # 上一份（存在才带）
logs/server-stdout.log      # 启动器 tee 的服务端 stdout/stderr 尾部 ≤2 MB
logs/atr1000.log            # 存在才带（尾部 ≤256 KB）
state/config-redacted.ini   # 白名单键的配置快照（见 §4）
state/patch-applied.json    # 热修覆盖层状态（applied.json + 文件清单）
state/hotfix-describe.json  # patch_overlay.describe(with_hash=True)
diagnostics/env.json        # 环境快照（见 §3）
diagnostics/devices.json    # PyAudio 设备表：名字/host API/延迟/通道数
diagnostics/summary.txt     # 自动体检摘要（见 §3）
audio/rx-5s.wav             # 可选：5 秒 RX 音频（用户勾选）
```

## 3. 采集项细节

**`diagnostics/env.json`**

| 字段 | 来源 |
|---|---|
| `version` / `frozen` / `python` | `version.txt`、`sys.frozen`、`sys.version` |
| `platform` | `platform.platform()`、`os.name` |
| `cpu` / `memory` | `os.cpu_count()`、`psutil` 有则带，无则略 |
| `wdsp` | 库路径、`GetWDSPVersion()`（失败则记原因） |
| `audio.chosen` | `[音频]` 那行拿到的设备 index/API/延迟（见 §6） |
| `audio.health` | 最近一条 `🎧 音频健康:` 行的原始文本 |
| `rig` | `[HAMLIB] rig_model` / `[INSTANCE_SETTINGS] instance_rigctl_model`、rigctld 探针结果、串口列表 |
| `atr1000` | `ATR1000_ENABLED` / 原因字符串 |

**`diagnostics/summary.txt`**（自动体检，维护者第一眼看的文件）

- 日志尾部按正则归类计数：`Traceback`、`ERROR`、`❌`、`⚠️`、`IOLoop stall`、`ATR-1000`、
  `PTT`、`音频健康` 的百分比、`补丁覆盖层`；
- 每类给出**最近 3 条原文**（截断到 300 字符）；
- 明确结论区：`音频采集有没有丢块`（<99% 报警）、`热修是否生效`、`WDSP 是否加载成功`。

## 4. 脱敏规则（硬性）

**配置快照只保留白名单键**：`[SERVER] port/host`、`[HAMLIB] rig_model/rig_pathname/rig_rate/
stop_bits/data_bits/serial_parity/serial_handshake`、`[AUDIO] inputdevice/outputdevice/
hostapi_preference/diag`、`[WDSP] *`、`[CTRL] interval_smeter_update`、`[ATR1000] enabled`、
`[INSTANCE_SETTINGS] instance_rigctl_model/instance_rigctl_port/instance_unix_socket/
atr1000_proxy_transport`、`[RNNOISE] suppress_level`、`[UPDATE]/[HOTFIX] enabled`。

**永不打包**：`MRRC_users.db`、`certs/**`、`*.pem`、`*.key`；`cookie_secret`、任何键名匹配
`(?i)(pass|secret|token|key|credential)` 的值。

**值级兜底**：所有被采集文本再过一遍正则，把
`(cookie_secret|password|passwd|token|api[_-]?key)\s*[=:]\s*\S+` 替换为
`\1 = <redacted>`；命中的条数写进 `manifest.json.redactions`（让维护者知道确实动过手）。

## 5. 接口

**服务端（MRRC，`MRRC` 内新增 handler）**

```
POST /api/support/bundle            # 生成包（executor 里做，避免阻塞 IOLoop）
     body: {"problem": "...", "contact": "...", "includeAudio": false}
     resp: {"ok": true, "id": "20260916-153012-ab12", "path": "…\\support-….zip",
            "size": 1234567, "files": ["logs/MRRC.log", …], "redactions": 3}

GET  /api/support/bundle/<id>       # 下载（本地保存入口，走浏览器下载）
POST /api/support/upload            # 上传到接收端
     body: {"id": "…"}  resp: {"ok": true, "remoteId": "…"} | {"ok": false, "reason": "…"}
POST /api/support/audio             # 采集 5 秒 RX 音频（可选步骤，写进包）
```

生成/上传都限制在最近一次生成（`id` 需匹配 `support_dir()` 里的实际文件，防越权读盘）。

**接收端（`www.vlsc.net`，stdlib 小服务 + nginx 反代）**

```
POST /mrrc/support/api/create       -> {"id": "20260916-153012-ab12"}
PUT  /mrrc/support/api/<id>/bundle  -> 原始 zip body（Content-Length ≤ 20MB）
GET  /mrrc/support/api/list         -> 需 Basic Auth，HTML 列表（含描述/摘要/大小）
GET  /mrrc/support/api/<id>/bundle  -> 需 Basic Auth，下载
DELETE 由列表页表单触发（需 Basic Auth）
```

限制：单包 ≤ 20 MB、每 IP 每分钟 ≤ 5 次 create、id 只允许 `[0-9]{8}-[0-9]{6}-[a-z0-9]{4}`、
文件名只允许写进 `SUPPORT_DIR/<id>/`（防穿越）。存储目录
`/var/www/support/<id>/`（bundle.zip + meta.json + summary.txt 便于列表页直读）。

## 6. 与现有代码的衔接

| 需要的能力 | 现有位置 | 改动 |
|---|---|---|
| 日志文件路径与尾部读取 | `MRRC` 的 logging 配置、`config['SERVER']['log_file']` | 新增 `support_bundle.tail_lines(path, max_bytes)` |
| 音频设备/API/延迟 | `audio_interface._match_devices/_describe_device`（已有） | 新增 `audio_interface.device_report()` 返回 JSON 结构 |
| 音频健康行 | 采集线程每 30s 打印 | 同时存进 `PyAudioCapture.last_health` 供采集 |
| 热修状态 | `patch_overlay.describe()`（已有） | 直接调用 |
| rigctld 实报 | `rig_models.cached_rigctld_model()`（已有） | 直接调用 |
| 启动器 stdout | 目前只进控制台 | `windows/launcher.py` 用 `tee` 写 `logs/server-stdout.log`（滚动 2 MB） |

## 7. 界面（`www/support.html`）

三步向导，全部在一个页面内：

1. **描述问题**：多行文本框 + 可选呼号/联系方式 + 两个复选框
   「附带 5 秒接收音频」「包含完整日志（默认只带尾部 2 MB）」；
2. **预览清单**：列出将要上传的文件、大小合计、脱敏命中数（来自 `POST /api/support/bundle` 的响应）；
3. **上传 / 保存本地**：两个按钮；上传中有进度提示；失败给出原因 + 「已保存到本地，路径：…」
   （Windows 用 `explorer /select,` 打开所在目录）。

入口：移动端菜单新增 `🐞 遇到问题`（现有 6 项 → 7 项）；桌面工具栏新增一个小图标按钮。

## 8. 错误处理

- 生成失败（磁盘满/日志不存在）：仍然生成最小包（`manifest.json` + `problem.txt` + `env.json`），
  并在响应里给 `warnings[]`；
- 上传失败：包保留在本地，UI 明确显示路径 + 重试按钮；不自动重试（避免流量失控）；
- 接收端 5xx：客户端把它当成"网络问题"，提示稍后重试或改用本地保存；
- 所有网络调用超时 30s，绝不阻塞 IOLoop（`run_in_executor`）。

## 9. 测试

- `tests/test_support_bundle.py`：
  - 脱敏：构造含 `cookie_secret=xxx`、`password` 的配置与日志 → 断言包内**不含**明文；
  - 白名单：断言只保留允许的键，`MRRC_users.db`/证书不在包内；
  - 尾部截断：1 MB 日志 → 包内 ≤ 2 MB 且以完整行开始；
  - 摘要：喂一段含 `Traceback` 与 `🎧 音频健康: … 98.5%` 的日志 → 断言 summary 命中这两类；
  - 最小包降级：日志文件不存在时仍产出带 `warnings` 的包。
- `dev_tools/test_support_receiver.py`：本地起接收端（临时目录 + 随机端口）→ create/put/get/list
  全流程 + 越权 id/超大包/穿越路径都被拒。

## 10. 验收（真机）

1. Windows VM：装 6.0.7 → 点「🐞 遇到问题」→ 生成包 → 包内**无明文密钥**、含音频健康行；
2. 上传到线上接收端 → 列表页能看到、能下载、能删除；
3. 断网时 → 提示已保存本地并给出路径；
4. 越权测试：手工构造 `PUT /api/../etc/passwd` 之类 → 被拒。

# 支持诊断包（「🐞 遇到问题」一键上传）

> 上下游：本文覆盖《[产品支持生命周期](product-support-lifecycle.md)》的**第 3–4 步（问题诊断 + AI 分析）**；
> 上游 [版本升级](one-click-upgrade.md)，下游公开答复页 <https://www.vlsc.net/mrrc/answers/>。

用户侧：移动端菜单 **🐞 遇到问题** 或桌面工具栏 **🐞** → 填问题描述 → 生成 → 上传/只保存本地。
维护者侧：`https://www.vlsc.net/mrrc/support/api/list`（Basic Auth，口令见下）。

## 维护者用法

| 项 | 值 |
|---|---|
| 列表页 | `https://www.vlsc.net/mrrc/support/api/list`（浏览器会弹出口令框） |
| 用户名 | `mrrc` |
| 口令 | 本机 `~/.mrrc-support-credentials.txt`（部署时生成，权限 600）；服务器上在 `/etc/mrrc-support.env`（0600 root） |
| 存储 | 服务器 `/var/www/support/<id>/`（`bundle.zip` + `meta.json`，**不在站点 docroot 内**） |
| 删除 | 列表页每行的「删除」按钮，或 `DELETE .../api/<id>/bundle`（需口令） |

看包顺序建议：`diagnostics/summary.txt`（自动体检结论 + 命中明细）→ `problem.txt` →
`diagnostics/env.json`（音频设备/主机 API/rigctld/ATR/热修）→ `logs/*`。

## 部署 / 更新接收端

```bash
./deploy_support_receiver.sh            # 幂等：装 server.py + systemd 单元 + 口令（0600）
```
- 服务：`systemd` 单元 `support-receiver`（`/opt/mrrc-support/server.py`，监听 127.0.0.1:8099，
  跑在 `www-data`，`ProtectSystem=full` + `ReadWritePaths=/var/www/support`）
- nginx：站点 `vlsc.net` 里 `location ^~ /mrrc/support/ { proxy_pass http://127.0.0.1:8099/; client_max_body_size 25m; }`
  （改动前已备份为 `vlsc.net.bak-<时间戳>`；改完必须 `nginx -t` 再 reload）
- 客户端默认上报地址：`https://www.vlsc.net/mrrc/support/api`（`[SUPPORT] url` 可覆盖）

## 包内容与脱敏（硬规则）

生成逻辑在 `support_bundle.py`（纯标准库、可热修）：

- **白名单**：配置只导出 `CONFIG_WHITELIST` 列出的键，其余节整节省略；
- **密钥替换**：`cookie_secret`/`password`/`token`/`api_key` 等一律写成 `<redacted>`，命中数写进 manifest；
- **永不打包**：`MRRC_users.db`、证书与私钥（`FORBIDDEN_SUBSTRINGS`）；
- **只读尾部**：日志按行边界截断到 ≤2 MB；
- 传输：只走 HTTPS + 接收端限速（每 IP 每分钟 ≤5 次 create）与单包上限（默认 20 MB）。

## 排障

| 现象 | 处理 |
|---|---|
| 列表页 502 | `ssh www.vlsc.net 'sudo systemctl status support-receiver'`；确认 8099 在听 |
| 上传 413 | 诊断包超过 20 MB：调 `SUPPORT_MAX_MB`（同时改 nginx `client_max_body_size`） |
| 上传 429 | 触发限速；等 1 分钟或调 `SUPPORT_RATE_PER_MINUTE` |
| 用户说"上传失败" | 包仍在本地 `%LOCALAPPDATA%\MRRC\support\`，让用户点「只保存到本地」把路径发你 |

---

## 当前部署状态（2026-09-16 起）

| 项 | 值 |
|---|---|
| 用户入口 | 移动端菜单 / 桌面工具栏 **🐞 遇到问题** → `www/support.html` |
| 服务端接口 | `/api/support/{bundle,upload,save}`（IO 全走 executor；`bundle` 生成、`upload` 上传、`save` 只存本地） |
| 接收端 | `https://www.vlsc.net/mrrc/support/`（列表页 + 下载 + 删除；需 Basic Auth，`user=mrrc`） |
| 接收端实现 | `tools/support_receiver/server.py`（纯标准库；systemd `support-receiver` 监听 `127.0.0.1:8099`；nginx `location ^~ /mrrc/support/`、`client_max_body_size 25m`） |
| 部署 | 仓库根 `./deploy_support_receiver.sh` |
| 口令 | 维护者本机 `~/.mrrc-support-credentials.txt`（600）；服务器 `/etc/mrrc-support.env` |
| 存储 | 服务器 `/var/www/support/<id>/`（含 `bundle.zip` 与 `meta.json`） |

## 验收记录（三层，全部通过）

1. **Mac 本机（源码模式）**：生成 → 上传 → 接收端可见；
2. **VM 源码模式**：同上，且包含新模块 `support_bundle.py` 的真实采集；
3. **VM 冻结版（安装包）**：安装版里运行、生成并上传成功。

另外：`windows/launcher.py` 的 `tee_child_output` 会把服务端启动期 stdout/stderr
落到 `%LOCALAPPDATA%\MRRC\logs\server-stdout.log`（2 MB 滚动，`.prev` 保留上一份），
这样"启动就崩、页面打不开"的场景也能取到日志。

## 已知注意事项

- **打包遗漏 `upgrade_core`** 曾导致 `/api/update` 报 `ModuleNotFoundError`
  → 提醒：往 `MRRC` 里加"函数内 import 的新模块"时，必须同时加进
  `packaging/pyinstaller/mrrc_server.spec` 的 `_APP_MODULES`（`support_bundle.py` 就是这样加的）；
- 控制台编码：Windows GBK 下 emoji 会让转发线程抛 `UnicodeEncodeError`
  → 已在启动器修掉（RC-002 §5），否则 `server-stdout.log` 会悄悄断更；
- 上传是**用户主动点击**才发生；「只保存到本地」永远保留。

---

## 答复闭环（上报 → 答复页 → 客户自查自解）

**目标**：针对性问题给出**针对性答复**，用户自己看懂就解决，不必来回沟通。

### 流程

1. 用户在 App 里 **🐞 遇到问题 → 生成诊断包 → 上传**；
2. 上传成功后 App 直接显示：**编号** + `https://www.vlsc.net/mrrc/answers/#<编号>`；
3. 维护者用维护端口令读接收端（`/mrrc/support/api/list`）→ 取最新条目 → 解包分析：
   - 先看 `diagnostics/summary.txt`（自动体检：新鲜度 / 音频采集 / 热修 / WDSP /
     **启动次数与时间跨度** / 音频设备判定），
   - 再看 `logs/server-stdout.log` 的 `Traceback`、`state/config-redacted.ini`、`diagnostics/env.json`；
4. 把结论写进 **`website/answers/index.html`** 的一张卡片：
   **编号 / 症状 / 诊断（附证据行）/ 结论 / 解决办法 / 状态**，
   并在 `data-keys` 里塞入编号、问题原话与关键词（搜索框按它过滤）；
5. `./deploy_website.sh` 发布 → 告知用户直接看该编号（页面支持 `#编号` 直达并自动填入搜索框）。

### 硬性约定

- 答复页**只收可公开的结论**，绝不放用户数据（配置已脱敏，但仍不要粘贴原文）；
- 每条答复必须有"**你要做的**"小节（可执行步骤），不能只有诊断；
- 编号格式 `YYYYMMDD-HHMMSS-4位`；页面顶部搜索框语义 = 编号或关键词。

### 已固化的能力（V6.1.12）

- App 上传后给出答复地址（`www/support.html`，可热修）；
- 体检摘要新增"启动次数/时间跨度，区分重启与崩溃"与"-9996 无音频设备"判定
  （`support_bundle.summarize_log`，可热修）—— 这两项正是"看起来像崩溃其实是升级重启"
  这类误报的判据；
- 首个案例：`20260917-062314-35dc`（"always stopped abnormally" → 实为 25 次正常启动 +
  升级行为，无崩溃）。

---

## 自动化分诊（support autopilot）

维护者侧的定时闭环（**crontab 驱动**，默认每 10 分钟）：

```
轮询 /mrrc/support/api/list → 发现新编号 → 下载并解包 → 生成摘要 →
调用 pi（非交互，读 .pi/skills/mrrc-product-support/SKILL.md）→ 拿 JSON 结论 →
渲染答复卡 → 插入 website/answers/index.html → git commit + deploy_website.sh
```

```bash
python3 dev_tools/support_autopilot.py --once                # 分析新上报（不发布）
python3 dev_tools/support_autopilot.py --once --publish      # 分析并自动发布
python3 dev_tools/support_autopilot.py --id <编号> --force [--publish]
python3 dev_tools/support_autopilot.py --inspect <编号>      # 只看摘要（不调模型）
python3 dev_tools/support_autopilot.py --status              # 已处理清单/最近运行
python3 dev_tools/support_autopilot.py --install-cron 10     # 安装/更新 crontab
```

**产物与状态**

| 路径 | 内容 |
|---|---|
| `dist/support_answers/<编号>.digest.md` | 喂给模型的摘要（含自动体检 + env + 脱敏配置 + 日志尾部） |
| `dist/support_answers/<编号>.answer.json` | 模型返回的结构化结论（verdict/status/category/diagnosis/solution/evidence/keys） |
| `dist/support_answers/<编号>.card.html` | 渲染好的答复卡（答复页片段） |
| `~/.mrrc-support-autopilot/state.json` | 已处理编号（幂等）、最近运行时间 |
| `~/.mrrc-support-autopilot/autopilot.log` | 运行日志（cron 也追加到这里） |

**安全与边界**

- 默认**不发布**（必须显式 `--publish`）；`--publish` 会 `git commit` 并 `deploy_website.sh`；
- 半包（只有元数据、不是 zip）标记 `skip`，不会反复重试；
- 单轮最多处理 `MAX_PER_RUN=2` 条（防涌入时长时间占用）；
- 模型只拿到**摘要**（不是整包）；答复页是公开页面 → 只放可公开结论；
- 判定规则与答复格式集中在 skill `.pi/skills/mrrc-product-support/SKILL.md`（改规则改那里即可）；
- 需要改代码时，模型会置 `needs_code_change` + `code_hint`，日志里出现 `⚠️ 需改代码` —— 此时走正常修复流程
  （并遵守"能不能热修"的判定，见 `hotfix-and-patching.md`）。

**首次实测**（2026-09-17）：对真实上报 `20260916-184958-f8aa`（"看下日志有没有异常和潜在风险"）
自动产出结论并发布；模型正确发现"包内无服务端日志 → 需要补充信息"，同时指出两个真实配置风险
（macOS 上残留 Windows 主机 API 名、两个同名 USB Audio CODEC 导致设备选择歧义）。

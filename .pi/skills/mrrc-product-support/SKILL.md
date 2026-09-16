---
name: mrrc-product-support
description: MRRC 产品支持全链路操作指南——发布（构建/站点清单/热修）→ 版本升级（一键升级与热修通道）→ 问题诊断（🐞 诊断包与体检摘要判读）→ AI 分析（自动分诊流水线）→ 回复解决（公开答复页）。当需要发版、处理升级或热修、分析用户上报、判断环境问题还是产品缺陷、或维护这条支持流水线时使用。
license: GPL-3.0
metadata:
  repo: HAM/mrrc
  lifecycle-doc: docs/current/operations/product-support-lifecycle.md
  answers-page: https://www.vlsc.net/mrrc/answers/
  autopilot: dev_tools/support_autopilot.py
  audit: dev_tools/site_audit.py
---

# MRRC 产品支持（发布 · 升级 · 诊断 · 分析 · 答复）

一条链：**开发发版 → 版本升级 → 问题诊断 → AI 分析 → 回复解决**。
本 skill 是这条链的**操作手册**；总览与不变量见 `docs/current/operations/product-support-lifecycle.md`。

## 何时用

- 要发版、发热修、改站点清单（`latest.json` / `patch.json`）；
- 用户报升级失败 / 点【立即升级】没反应 / 热修没生效；
- 收到「🐞 遇到问题」上报，要判断是**环境**、**使用**还是**产品缺陷**并给出答复；
- 维护自动分诊（crontab + `support_autopilot.py`）或公开答复页。

## 0. 快速索引（改这条链之前先读）

| 主题 | 文档 |
|---|---|
| 总览 + 闭环不变量 8 条 + 守卫清单 | `docs/current/operations/product-support-lifecycle.md` |
| 发版流程（含 VM 自动化陷阱） | `docs/current/operations/release-process.md` |
| 一键升级机制/排障 | `docs/current/operations/one-click-upgrade.md` |
| 诊断包 + 自动分诊 | `docs/current/operations/support-bundle.md` |
| 热修可覆盖范围 | `docs/current/operations/hotfix-and-patching.md` |
| 升级/退出链路 10 个 Windows 陷阱 | `docs/current/reliability/RC-002-launcher-upgrade-and-shutdown.md` |

## 1. 发布

**版本语义**：`packaging/windows/MRRC.iss` 的 `MyAppVersion` → 安装目录 `version.txt`（运行时唯一权威）。
**三道闸门**（缺一不发）：单元测试（含内联 JS 语法守卫）+ 全站审计 + **产物级热修验收 3/3**。

```bash
python3 -m unittest discover -s tests          # 111 项
python3 dev_tools/site_audit.py                # 网站结构体检（断链/样式/nav/中英成对）
# Windows 包只能在 Windows 上出：ham.vlsc.net 的 Win11 VM
#   Expand-Archive → packaging\windows\build_wdsp_dll.ps1 → packaging\windows\build.ps1
#   → python packaging\hotfix\verify_hotfix.py --app C:\mrrc\dist\windows\MRRC --repo C:\mrrc
```

**上架三件套（必须 git 入库）**：`MRRC-Setup.exe` + `MRRC-Setup-<ver>.exe` + 上一版
`MRRC-Setup-<prev>.exe`（`deploy_website.sh` 是 `rsync --delete`，未入库的服务器文件会被删 ✗）。
清单：`latest.json`（installer/previous/hotfix/notes）与 `patch.json`（热修）。
**复核以服务器侧 SHA256 为准**（本机下载链路不可信）：

```bash
ssh cheenle@www.vlsc.net 'cd /var/www/vlsc.net/mrrc/downloads && sha256sum MRRC-Setup*.exe'
```

**不变量**：安装版本 > 热修通道版本；`previous` 不能指向已知有问题的版本；回退目标必须在站上真实存在。

## 2. 升级（用户侧）

- 触发：页面 **⬆️ 软件更新 →【立即升级】** 或启动器窗口**按 `U`**；服务端 PTT 门禁（发射中 423）。
- **唯一成功判据**：`%LOCALAPPDATA%\MRRC\updates\state.json` 的 `lastResult.status == "ok"`
  （由**新版启动时自证**；`installing` 只是"已拉起安装器"）。
- **热修通道**：不改安装版本，覆盖 `www/**`、`_APP_MODULES`（含 `upgrade_core.py`、`support_bundle.py`）、
  `vendor` → 用户**重启 MRRC 即生效**；`MRRC` 主脚本与 `windows/launcher.py` 在 PYZ 里，**必须发版**。
- 排障判读：`upgrade.request` 长期存在 = 启动器没在处理；`*.part` 长期 0 字节 = 连接阶段卡住；
  `install-<ver>.log` 缺失 = 安装器没起来；先看 `state.json.lastResult` 再下结论。
- 已知坑与修复见 RC-002（控制台进程关不掉、提权进程 `runas` 卡死、BOM/GBK、锁与超时…）。

## 3. 诊断（用户上报 → 你要看的顺序）

1. `diagnostics/summary.txt`（自动体检，**先读这个**）
2. `logs/server-stdout.log`（找 `Traceback` / 反复出现的同一处异常）
3. `diagnostics/env.json`（版本、平台、CPU、`audio.devices`、热修覆盖层）
4. `state/config-redacted.ini`（音频设备名、机型、端口）
5. `problem.txt`（用户原话）

**判据表（照这个表定性，别猜）**

| 证据 | 定性 | 答复方向 |
|---|---|---|
| `Traceback` / `Fatal` / 反复同一处异常 | **产品缺陷** | 给临时规避 + 指出文件/函数（`needs_code_change=true`） |
| 启动次数多但**无** `Traceback` | **不是崩溃** | 说明升级/重启属正常（升级会退出再自动回来） |
| `-9996` 且 `audio.devices: []` | **环境** | 本机无音频设备（虚拟机常见），纯 Web 模式属预期 |
| `Device 'X' not found` | **使用问题** | 在 Device Config 选实际设备名 |
| `rigctld daemon not running` / 模拟模式 | **环境** | 启动 rigctld；核对 `instance_rigctl_port` |
| `🎧 音频健康` < 99% / `IOLoop stall` / `TX 初始化 > 200ms` | 性能 | 引 RC-001（设备抖动/独占） |
| `download_busy` / `download_failed` / 升级无反应 | 升级 | 网络抖动会自动重试；看 `lastResult` |
| 自签名证书告警 / 401 / 403 | 正常噪声 | 不是缺陷 |

## 4. AI 分析（自动分诊流水线）

```bash
python3 dev_tools/support_autopilot.py --inspect <编号>          # 只看摘要（不调模型）
python3 dev_tools/support_autopilot.py --id <编号> --force [--publish]
python3 dev_tools/support_autopilot.py --once [--publish]        # crontab 每 10 分钟在跑
python3 dev_tools/support_autopilot.py --status
```

流程：轮询接收端 → 下载解包 → 摘要（复用 `support_bundle.summarize_log`）→
`pi --thinking high --tools read,grep,find,ls` 分析 → 结构化 JSON → 渲染答复卡 →（`--publish`）发布。
**护栏**：幂等（`state.json`）、默认不发布、半包（非 zip）跳过、单轮上限 2 条、pi 超时 9 分钟、
cron 用 venv 绝对路径 + 显式 PATH。

**输出契约**（模型必须只输出一个 JSON 对象）：

```json
{"verdict":"一句话结论","status":"answered|needs_fix|need_more_info",
 "category":"环境|使用问题|产品缺陷|网络|升级|音频|电台|其他",
 "diagnosis":["要点（附证据）"],"solution":["用户可执行步骤"],"evidence":["原始行/字段"],
 "keys":["搜索关键词"],"needs_code_change":false,"code_hint":"文件/函数"}
```

**判定纪律**：保守（材料不足 → `need_more_info`）；结论必须落到用户能做的动作；
环境类不算缺陷；答复页是公开页面，不泄露用户数据。

## 5. 回复解决

- 答复发布到 **<https://www.vlsc.net/mrrc/answers/>**（可搜索、`#编号` 直达并自动填入搜索框）；
- 每条答复固定结构：`编号 / 症状 / 诊断（附证据）/ 结论 / 你要做的 / 状态`；
- 面向现象写"已知问题卡"（例：`🐞 页面按钮点不动` → 6.1.12 内联 JS 语法错 → 重启 MRRC 拉热修即修复）；
- 确认缺陷时：**先给临时规避**，再修代码，并按可热修性决定走热修还是发版；修好后把卡片标 `已修复 · <版本>`。

## 6. 硬性规则（违反即返工）

1. 成功必须可判定：升级 = `lastResult == "ok"`；否则别写"应该好了"。
2. 发布前必过三道闸门；**不提交测试失败的状态**（管道会吃掉退出码 ✗，用 `if ... then` 显式判断）。
3. 站点清单与归档包必须入库；回退目标必须是"已知良好"的版本。
4. 热修只动可覆盖范围；其它改动老实发版。
5. 改网站后跑 `dev_tools/site_audit.py` + 内联 JS 守卫（否则断链/样式漂移/中文滞后会静默进入线上）。
6. 环境类问题不写成产品缺陷；答复里不出现"等维护者修"。
7. 每次事故都要在生命周期文档 §6 留一条**守卫**（测试/工具/检查），否则不算修完。
8. `.ps1` 含中文必须 **UTF-8 单 BOM**；`schtasks /tr` 里别塞引号；长任务用计划任务而非 SSH 会话。
9. 大文件（>20MB）先传 `~` 再 `sudo mv`（服务器 `/tmp` 是 454MB tmpfs）。
10. 结论要附**原始证据行**（用户能自己核对）。

## 7. 工具清单

| 工具 | 用途 |
|---|---|
| `dev_tools/release_windows.sh` | 一键发版（构建→验收→取回→归档→清单→部署→复核） |
| `packaging/hotfix/make_hotfix.py` | 生成热修包 + `patch.json` |
| `packaging/hotfix/verify_hotfix.py` | 产物级热修验收（3/3 闸门） |
| `dev_tools/support_autopilot.py` | 自动分诊（crontab 驱动） |
| `dev_tools/site_audit.py` | 全站结构体检（断链/样式/nav/中英成对/版本） |
| `dev_tools/vm_upgrade_e2e.ps1` | 真机升级端到端验收（可 `file://` 离线跑） |
| `tests/` | 111 项：升级逻辑、启动器、诊断包、网站守卫（内联 JS / 中英 / 审计） |

> 本 skill 的单一真相源在仓库 `.pi/skills/mrrc-product-support/SKILL.md`；
> 更新后执行 `dev_tools/sync_skills.sh` 同步到全局（`~/.pi/agent/skills/`）。

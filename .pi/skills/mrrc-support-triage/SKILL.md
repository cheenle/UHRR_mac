---
name: mrrc-support-triage
description: 分析 MRRC「🐞 遇到问题」上报的诊断包，给出结论与用户可自解的答复，并把它发布到公开答复页 /mrrc/answers/。当需要处理用户上报、判断一条报错是环境问题还是产品缺陷、或运行/维护支持自动驾驶（support autopilot）时使用。
license: GPL-3.0
metadata:
  project: MRRC
  entrypoint: dev_tools/support_autopilot.py
  answers-page: https://www.vlsc.net/mrrc/answers/
---

# MRRC 支持分诊（support triage）

把一条用户上报变成**用户看得懂、自己能做**的答复，并发布到答复页。
完整闭环：`轮询接收端 → 取包 → 本 skill 分析 → 生成答复卡 → 发布`。

## 什么时候用

- 有一条新的「🐞 遇到问题」上报需要答复；
- 需要判断某个报错是**环境**、**使用问题**还是**产品缺陷**；
- 运行或维护 `dev_tools/support_autopilot.py`。

## 快速命令

```bash
# 看某条上报的摘要（不调用模型）
python3 dev_tools/support_autopilot.py --inspect <编号>

# 只分析一条，产出草稿（不发布）
python3 dev_tools/support_autopilot.py --id <编号> --force

# 分析并发布（commit + deploy_website.sh）
python3 dev_tools/support_autopilot.py --id <编号> --force --publish

# 处理所有新上报 / 看状态 / 装/卸 crontab
python3 dev_tools/support_autopilot.py --once [--publish]
python3 dev_tools/support_autopilot.py --status
python3 dev_tools/support_autopilot.py --install-cron 10
```

产物：草稿在 `dist/support_answers/<编号>.{digest.md,answer.json,card.html}`，
状态在 `~/.mrrc-support-autopilot/state.json`，日志在 `~/.mrrc-support-autopilot/autopilot.log`。

## 分诊方法（必须先看证据）

**顺序**：`diagnostics/summary.txt`（自动体检）→ `logs/server-stdout.log` → `diagnostics/env.json` →
`state/config-redacted.ini` → `problem.txt`（用户原话）。

### 判据表

| 证据 | 判定 | 答复方向 |
|---|---|---|
| `Traceback` / `Fatal` / 反复同一处异常 | **产品缺陷**（needs_fix） | 给出临时规避 + 指明文件/函数；同时置 `needs_code_change=true` |
| `启动次数` 多但**无** `Traceback` | **不是崩溃** | 说明"升级/重启属正常"（升级时会主动退出再自动回来），给出如何区分 |
| `-9996 Invalid input device` / `audio.devices: []` | **环境** | 设备未插/被独占/虚拟机无声卡；纯 Web 模式属预期 |
| `Device 'X' not found` | **使用问题** | Device Config 里选实际设备名（或留空用系统默认） |
| `rigctld daemon not running` / simulation mode | **环境** | 启动 rigctld；确认 `instance_rigctl_port` |
| `🎧 音频健康` < 99% | **性能** | 查 CPU/WDSP 档位/主机 API；引用 RC-001 |
| `IOLoop stall` / `pstall` / 看门狗 | **性能/可用性** | 见 `docs/current/reliability/RC-001` |
| `TX 初始化耗时 > 200ms` | **性能** | 多为音频设备抖动（蓝牙/独占） |
| `download_busy` / `download_failed` / 升级无反应 | **升级** | 看 `lastResult`；多为网络抖动，会自动重试；见 `one-click-upgrade.md` |
| 401/403、证书告警、`SSL Error`（自签名） | **正常噪声** | 自签名证书的浏览器/本机告警属预期，不要当缺陷 |
| 材料不足（无日志/日志过旧） | **need_more_info** | 明确列出"请补充什么、从哪台机器上报" |

### 硬性规则

1. **结论必须落在用户能做的动作上**：`solution` 里不许出现"等维护者修"。
2. **保守判定**：证据不足 → `need_more_info`；不要为了"有结论"而猜。
3. **不泄露**：不贴配置原文大段内容、不贴凭据；答复页是公开页面。
4. **区分"重启"与"崩溃"**：没有 Traceback 就不叫崩溃。
5. **每条答复都要能被搜索**：`keys` 里放编号、用户原话、现象关键词（中文+英文）。
6. 产品缺陷要写清**临时规避**（用户当下怎么办）。

## 输出格式（机器可解析）

只输出一个 JSON 对象：

```json
{
  "verdict": "一句话结论（中文，≤40字）",
  "status": "answered|needs_fix|need_more_info",
  "category": "环境|使用问题|产品缺陷|网络|升级|音频|电台|其他",
  "diagnosis": ["诊断要点（附关键证据）"],
  "solution": ["用户可执行步骤（有序）"],
  "evidence": ["支撑结论的原始行/字段"],
  "keys": ["搜索关键词 8~14 个"],
  "needs_code_change": false,
  "code_hint": "需要改代码时指出文件/函数，否则空字符串"
}
```

`dev_tools/support_autopilot.py` 会把它渲染成答复卡（编号 / 症状 / 诊断 / 你要做的 / 证据）
并插入 `website/answers/index.html` 顶部。

## 答复页维护约定

- 新答复**插在列表最前**（最新在上），卡片 `data-keys` 必须含编号与关键词；
- 页面顶部有搜索框，支持 `https://www.vlsc.net/mrrc/answers/#<编号>` 直达（自动填入）；
- 只写可公开结论；页面本身不含任何用户数据；
- 发布 = `git commit` + `./deploy_website.sh`（`--publish` 才会做）。

## 需要动代码时

1. 先给用户临时规避（写进 `solution`）；
2. 修在该修的地方（多为 `MRRC` / `windows/launcher.py` / `upgrade_core.py` / `support_bundle.py` / `www/**`）；
3. 判断**能不能热修**：`www/**`、`_APP_MODULES`（含 `support_bundle.py`、`upgrade_core.py`）可热修；
   `MRRC` 主脚本与 `windows/launcher.py` 在 PYZ 里，必须发安装包
   （见 `docs/current/operations/hotfix-and-patching.md` 与 `release-process.md`）；
4. 测试与发布流程见 `docs/current/operations/release-process.md`。

## 相关文档

- 诊断包与答复闭环：`docs/current/operations/support-bundle.md`
- 一键升级：`docs/current/operations/one-click-upgrade.md`
- 发版/热修：`docs/current/operations/release-process.md`
- 可靠性案例：`docs/current/reliability/RC-001-*.md`、`RC-002-*.md`

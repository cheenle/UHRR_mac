# MRRC 产品支持生命周期（实践小结）

> 一条链：**开发发版 → 版本升级 → 问题诊断 → AI 分析 → 回复解决**，两端分别落在
> **维护者侧**（构建/发布/接收）与**用户侧**（升级/上报/自助）。
> 本文是这套能力的**总览与实践小结**；实施细则在各自专项文档里（见每节末"细则"）。
>
> 相关专项：`release-process.md`（发版）· `one-click-upgrade.md`（升级）·
> `support-bundle.md`（诊断包 + 自动分诊）· `hotfix-and-patching.md`（热修）·
> `runtime-and-verification.md`（验证）· `reliability/RC-00{1,2}`（可靠性案例）

---

## 0. 一张图

```
[维护者]  开发 ──► 发版 ──► 站点清单 latest.json / patch.json
                    │                    │
                    │            ┌───────┴────────┐
                    │            ▼                ▼
[用户]        （新装）      一键升级（点按钮/按U）   热修覆盖层（重启即生效）
                                 │                │
                                 └────── 运行中 ───┘
                                          │ 出问题
                                          ▼
                             🐞 一键诊断包（脱敏 + 自动体检摘要）
                                          │ 上传
[维护者]                                   ▼
                              接收端 /support/（口令）──► crontab 自动分诊
                                                              │ 取包 → 摘要
                                                              ▼
                                                     pi + skill 分析 → 结论 JSON
                                                              │ 渲染答复卡
                                                              ▼
                              公开答复页 /answers/#编号  ◄──── 发布（git + deploy）
                                          │
[用户]                                    ▼
                                    自己看懂 → 自己解决（无需人工往返）
```

---

## 1. 开发发版（维护者）

**目标**：任何一次发布都可复现、可验证、可回退。

| 环节 | 做法 | 判据/产物 |
|---|---|---|
| 版本语义 | `MRRC.iss` 的 `MyAppVersion` → 安装目录 `version.txt`；运行时**唯一权威** | 拒绝降级；安装版本 > 热修通道版本 |
| 质量闸门 | 单元测试（当前 **104 项**）+ **内联 JS 语法守卫**（`node --check` 逐段扫 `www/**`、`website/**`）+ 产物级**热修验收 3/3** | 不过闸门不允许发布 |
| 构建 | Windows 包只能在 Windows 上出 → `ham.vlsc.net` 上的 Win11 VM（`build_wdsp_dll.ps1` → `build.ps1`） | 产物 `MRRC-Setup.exe` + `version.txt` |
| 上架 | `MRRC-Setup.exe`（兼容旧书签）+ `MRRC-Setup-<ver>.exe`（清单指向）+ 上一版归档；`latest.json`（installer/previous/hotfix/notes）；`patch.json`（热修） | **三件套必须 git 入库** |
| 复核 | **服务器侧** `sha256sum` 对比清单 `installer.sha256`；清单自检（installer/previous 两个文件的 sha 都要对） | 线上哈希一致 |
| 事故驱动 | 每次事故都加一条**守卫**（见 §6） | 同类问题不再复发 |

**不变量（踩过的坑）**
1. `previous` 必须在站点上真实存在 **且已入库**——部署是 `rsync --delete`，未入库的服务器文件会被删掉（回退按钮 404，实际发生过）；
2. 回退目标不能指向"已知有问题的版本"（例：6.1.13 的 `previous` 刻意设为 6.1.11，跳过带坏页面的 6.1.12）；
3. 服务器 `/tmp` 是 454 MB tmpfs：大文件先传 `~` 再 `sudo mv`；
4. 本机→站点的下载链路不可信，**只有服务器侧哈希算数**。

> 细则：`release-process.md`

## 2. 版本升级（用户侧）

**目标**：用户点一下就能升级，失败不损坏现有安装，随时可回退。

| 环节 | 做法 |
|---|---|
| 发现 | 启动器启动时读 `latest.json` → 只提示 + **后台预下载**（不打断收听） |
| 触发 | 页面 **⬆️ 软件更新 →【立即升级】** 或启动器窗口**输入 U 回车**；服务端先做 PTT 门禁（发射中 423） |
| 执行 | 已暂存则**离线直接升**；否则下载（`.part<pid>` → SHA256 → 原子改名，带超时/重试/互斥）→ 停服务 →（已提权则直跑，否则一次 UAC）静默安装 → 启动器退出让出文件 → 安装器 `[Run]` 自动重启 |
| 成功判据 | 新版启动时自证：`state.json` 的 `lastResult.status == "ok"`（**唯一成功态**） |
| 回退 | 页面【回退到上一版】→ 同一条静默安装路径 |
| 热修通道 | 不改安装版本；覆盖 `www/**`、`_APP_MODULES`（含 `upgrade_core.py`、`support_bundle.py`）、`vendor` —— 用户**重启即生效**，无需重装 |
| 已知陷阱 | Windows 上 10 个"静默失效"（控制台进程关不掉、解释器收尾打断、跨进程抢 `.part`、BOM/GBK 编码、连接阶段无超时…）→ 全部修复并有回归测试 |

> 细则：`one-click-upgrade.md`（含排障表）、`hotfix-and-patching.md`（可热修范围）、
> 根因：`reliability/RC-002-launcher-upgrade-and-shutdown.md`

## 3. 问题诊断（用户侧）

**目标**：让用户在**不需要理解日志**的前提下，把维护者真正需要的现场交出来。

- 入口：页面/移动端菜单 **🐞 遇到问题** →「① 填现象 ② 生成诊断包 ③ 上传 / 只存本地」。
- 包内容：日志尾部（当前 + `.prev` + 服务端 stdout）、**脱敏**配置（白名单，密钥替换）、
  环境快照（版本/平台/CPU/音频设备表）、以及**自动体检摘要** `diagnostics/summary.txt`。
- **永不打包**：用户数据库、证书私钥、会话密钥。
- 摘要要能被"一眼读"（也决定用户能不能自查）：
  数据新鲜度 · 音频采集健康度 · 热修/ WDSP 状态 · **启动次数与时间跨度（区分重启与崩溃）** ·
  音频设备判定（`-9996` 且 `audio.devices` 为空 = 本机没有声卡）· 命中明细（ERROR/❌/⚠️/Traceback）。

> 细则：`support-bundle.md`

## 4. AI 分析（维护者侧，自动分诊）

**目标**：把"读包 + 判断 + 写答复"变成**定时自动完成**，人只处理需要改代码的部分。

```
crontab */10 ─► support_autopilot.py --once --publish
   ① 轮询接收端列表（凭据仅本地读取）
   ② 新编号 → 下载解包 → 生成摘要（复用 support_bundle.summarize_log）
   ③ pi 非交互分析：pi --thinking high --tools read,grep,find,ls -p "<prompt>"
        prompt 指定读 skill：.pi/skills/mrrc-product-support/SKILL.md
   ④ 拿结构化 JSON：verdict / status / category / diagnosis / solution / evidence / keys
   ⑤ 渲染答复卡 → 插入 website/answers/index.html 顶部
   ⑥ git commit + deploy_website.sh → 公开答复页
```

**判定纪律（写进 skill，非可选项）**
- 保守：材料不足 → `need_more_info`；**没有 Traceback 就不叫崩溃**；
- 结论必须落在用户能做的动作上（不许写"等维护者修"）；
- 环境类（无声卡、无 rigctld、虚拟机、未接电台）**不判成产品缺陷**；
- 答复页是公开页面 → 只放可公开结论；
- 只有确实属缺陷才 `needs_code_change=true` 并指出文件/函数。

**工程化护栏**：幂等（`state.json` 记已处理编号）· 默认不发布（`--publish` 才发）·
半包（非 zip）跳过不重试 · 单轮上限 2 条 · pi 超时 9 分钟 · cron 用 venv 绝对路径 + 显式 PATH。

> 细则：`support-bundle.md` §自动化分诊、skill `.pi/skills/mrrc-product-support/SKILL.md`

## 5. 回复解决（用户侧自助）

**目标**：用户看到答复就能自己解决；不能解决的，带着"已定位的证据"进入人工修复。

- 公开答复页 **<https://www.vlsc.net/mrrc/answers/>**：可搜索（编号/关键词），支持 `#编号` 直达并自动填入搜索框；
- 每条答复**固定结构**：`编号 / 症状 / 诊断（附原始证据）/ 结论 / 你要做的 / 状态`；
- **已知问题卡**：面向"用户看到的现象"写（例：`🐞 页面按钮点不动` → 6.1.12 的一个内联 JS 语法错误 → 重启 MRRC 拉热修即修复）；
- 若是缺陷：先给**临时规避**（写进"你要做的"），再修代码，并按"能不能热修"决定走热修还是发版；
- 修复发布后，答复卡可更新为 `已修复 · <版本>`，用户按编号仍能找到。

## 6. 事故驱动的改进清单（每条都补了守卫）

| 事故 | 加什么守卫 |
|---|---|
| IOLoop 楔死 / 蓝牙 DAC 致 TX 静默（RC-001） | 看门狗 + 线程栈转储 + TX 初始化打点（`⏱️ TX audio init`） |
| 升级链路 10 个静默失效（RC-002） | 10 项修复 + 顺序/互斥/超时的回归测试 + "新版自证 ok" |
| 打包漏 `upgrade_core` → `/api/update` 报 ModuleNotFoundError | 加入 spec `_APP_MODULES`；"函数内 import 的新模块"必须显式登记 |
| Windows GBK 控制台 emoji 杀死日志转发线程 | 启动器 stdio 统一 UTF-8 + `_safe_print` + 行缓冲 |
| **改页面拼字符串写坏内联 JS → 整页按钮失效**（6.1.12，随热修下发） | **`tests/test_web_inline_js.py`：所有内联脚本逐段 `node --check`** |
| 半包上报（只有元数据）让自动分诊反复失败 | 非 zip 载荷标记 `skip`，不重试 |

## 7. 闭环不变量（验收这套能力时看这 8 条）

1. 安装版本唯一权威 = `version.txt`；升级成功唯一判据 = `lastResult.status == "ok"`；
2. 每次发布都有**可用的回退目标**（且已入库、不是已知坏版本）；
3. 任何发布都过三道闸：单测 + 内联 JS 守卫 + 产物热修验收；
4. 热修能覆盖的范围是明确的（`www/**`、`_APP_MODULES`、`vendor`），其余必须发版；
5. 诊断包**永不**包含用户库/证书/密钥，且用户是主动点击才上传；
6. 自动分诊**默认不发布**、幂等、材料不足就 `need_more_info`；
7. 每条答复必须可被用户"照着做"，并可通过编号被检索到；
8. 每次事故都要在 §6 留下一条守卫（否则不算修完）。

## 8. 能力边界（诚实记录）

- 无代码签名（信任锚 = 站点 TLS + 清单 SHA256；UAC 是最后人工闸门）；
- AI 分析基于**摘要**而非完整环境，复杂音频/时序问题仍可能判 `need_more_info`；
- V6.0.10 及更早没有升级逻辑，需手动装一次 6.1.x；
- 自动分诊目前只覆盖"上报→答复页"这一条路径，不替代人工的深度硬件排障。

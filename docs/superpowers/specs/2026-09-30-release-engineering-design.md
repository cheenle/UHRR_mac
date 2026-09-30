# MRRC 发布工程化：完成度检查器 + 发布技能 + macOS 打包链 设计

> 状态：**待用户复核**（2026-09-30）。本文件定稿并获批准后，才进入 writing-plans 出实施计划。
> 起点：把 `mrrc_modern/.agents/skills/{dual-platform-release,windows-installer,macos-installer}`
> 三个发布技能移植到本仓库 —— 但本仓库没有 macOS 产物、没有机器可读的产物清单，
> 且发布知识散落在四份文档里，所以"移植"实际展开为三件事。
> 目标：**让"发版"这件事的完成度由构造保证，而不是靠人记。**

## 0. 一句话

一次发版要改的文件分散在 `packaging/`、`www/`、`website/`、`README*`、`CHANGELOG.md`，
目前只靠 `docs/current/operations/release-process.md` §1.4 的一段散文约束，
**已经漏了**（见 §2.4）。本设计引入三件互相独立的交付物，让漏改导致构建失败：

1. **`dev_tools/release_check.py`**（P1）—— 机器可读的产物清单 + 可执行检查器，接进 `tests/`；
2. **`.pi/skills/` 下三个发布技能**（P2）—— 把"发版 / 打 Windows 包 / 打 macOS 包"的操作与陷阱沉淀；
3. **一条 macOS 打包链**（P3）—— 本仓库目前完全没有 macOS 产物。

## 1. 目标与非目标

**目标**

- 版本漂移**在提交前就可执行地检出**（不是靠读文档），并可被 `tests/` 当作回归守卫；
- "发版"与"发热修"的决策、命令序列、已知陷阱，任何 agent 说一句"发版"就能拿到；
- 产出可分发的 macOS 产物（`.dmg` / `.app`），运行行为与 Windows 安装版对齐；
- 三个技能里的每条陷阱都**指到真实文件与行号**，可核对。

**非目标**

- 不重构 `windows/launcher.py`（942 行）。仅在 P3 抽取**平台中立的壳**，不动其逻辑；
- 不做 macOS 的自动升级通道（见 §3 决策 D2）；
- 不做公证（notarization）/Developer ID（见 §3 决策 D3）；
- 不做 Raspberry Pi 镜像（本仓库无此产物，YAGNI）；
- 不把 `release_check.py` 做成 CI 服务；它只作为 `tests/` 里一个 stdlib unittest 被调用。

## 2. 现状（事实，逐条带出处）

### 2.1 版本权威链

```
packaging/windows/MRRC.iss:2   #define MyAppVersion "6.1.18"
        │  dev_tools/release_windows.sh:39   读出 VERSION
        │  packaging/windows/build.ps1:79-86 写入 dist/windows/MRRC/version.txt
        ▼
产物内 version.txt  ← 运行时唯一权威
        │  windows/launcher.py:108-114  _installed_version() 读它
        ▼
升级/热修决策（upgrade_core.plan_upgrade、launcher.check_for_hotfix）
```

- **没有任何版本常量编译进产物**；`version.txt` 是唯一运行时标记。
- `CHANGELOG.md` 的版本标题是**大写 V**：`## [V6.1.18]`（共 75 条，`CHANGELOG.md:18` 起）。
  **且其中夹着非版本标题**：`## [Unreleased]`（`:8`）、`## [未发布]`（`:28`）。

### 2.2 现有发布编排

`dev_tools/release_windows.sh`（160 行）已是一条命令跑完全程：
读 iss 版本 → 打源码包 → 上传 `ham.vlsc.net` → 跳进 Win11 VM 构建 →
`verify_hotfix.py` 产物级验收 → 取回 → 归档上一版 → `make_latest_json.py` 生成清单 →
提交推送 → `deploy_website.sh` → 线上 `sha256sum` 复核。

⇒ **P2 的技能不需要发明流程，只需把既有流程的正确用法与陷阱写清楚。**

### 2.3 现有检查器惯例

本仓库已有「dev_tool 检查器 + stdlib unittest」的本地惯例：
`dev_tools/site_audit.py`（`--json` / `--strict`，退出码 0/1）+ `tests/test_site_audit.py`（43 行）。
P1 沿用这个惯例，**不照搬** `mrrc_modern` 的 `.agents/skills/<name>/harness/` 布局。

### 2.4 已存在的版本漂移（P1 上线即可抓到的）

当前发行版 = **6.1.18**（`packaging/windows/MRRC.iss:2`）。

| 文件 | 实际 | 应为 | 出处 |
|---|---|---|---|
| `www/mobile_modern.html` | `6.1.16` | 6.1.18 | `:13` CSS `?v=6.1.16`；`:257` `MRRC V6.1.16` |
| `www/mobile_modern_zh.html` | `V6.1.16` | 6.1.18 | `:237` |
| `README_CN.md` | `V6.0.0` | 6.1.18 | `:1`、`:3` badge、`:389`"最新版本: V6.0.0 (2026-09-05)" |
| `README_en.md` | `V6.0.0` | 6.1.18 | `:1`、`:3` badge、`:365`"Latest Version: V6.0.0" |

而 `docs/current/operations/release-process.md` §1.4 明文要求每次发版同步
`www/mobile_modern*.html`（页脚 + CSS `?v=`）与 `README.md` —— **6.1.18 那次没做**。

### 2.5 Windows 打包链（P3 的参照系）

- 三个 PyInstaller spec：`mrrc_server.spec`（onedir，入口 `frozen_entry.py`）、
  `mrrc_launcher.spec`（onefile，入口 `windows/launcher.py`）、`atr1000_proxy.spec`（onefile）。
- **`mrrc_server.spec:70-75` 与 `atr1000_proxy.spec:17-22` 已带 `elif sys.platform == "darwin"` 分支**
  （映射 `vendor/<family>/macos`）—— 当初就留了 macOS 的口子。
- `packaging/pyinstaller/frozen_entry.py` **平台中立**（只用 `sys._MEIPASS`/`os.path`/`runpy`）。
- app 代码**刻意不进 PYZ**，以松散文件放 `_internal/app/`，供 `patch_overlay` 覆盖（`mrrc_server.spec:137`）。
- 配置种子 = `windows/MRRC.conf.template`（**Windows 口味**：`wasapi`、`COM3`）；
  **本仓库没有 `default.env`**。

### 2.6 本机构建前提（已实测）

| 项 | 状态 |
|---|---|
| `venv/` | Python **3.11.14** + PyInstaller **6.22.3** |
| 系统 `python3` | 3.14.5，**无** PyInstaller |
| `rumps` / `PyObjC` | **两边都没装**（P3 需要安装） |
| `codesign` / `hdiutil` / `xcrun` / `spctl` | 均可用 |

### 2.7 热修通道（跨平台通道，客户端实现不跨平台）

| 环节 | 实现 | 跨平台? |
|---|---|---|
| 生成 `hotfix-<ver>.zip` + `patch.json` | `packaging/hotfix/make_hotfix.py` | ✅ |
| 运行时覆盖层 | `patch_overlay.py`（`patch/` 解析见 `:82-90`） | ✅ |
| 客户端 检查/下载/校验/解包 | `windows/launcher.py:173-217`、`:125-155` | ❌ 在 Windows 启动器内 |
| 构建期验收闸门 | `packaging/hotfix/verify_hotfix.py` —— `:122` 硬编码 `MRRC-Server.exe`、`:134` 读 `LOCALAPPDATA` | ❌ |
| 手动/离线安装 | `packaging/hotfix/apply_hotfix.ps1`（PowerShell） | ❌ |

通道契约（`make_hotfix.py` 与 `check_for_hotfix()` 共同定义，macOS 侧须等价实现）：
`patch.json` = `{latest, url, sha256, requires}`；`latest` > 本机 `version.txt` 才应用；
`requires` > 本机版本则跳过并提示装完整包；404 = 未发布过热修，静默跳过；
失败一律只警告、不阻断启动。

## 3. 关键决策

| # | 决策 | 理由 |
|---|---|---|
| **D1** | 版本权威 = **`packaging/windows/MRRC.iss` 的 `MyAppVersion`** | 操作链决定的：`release_windows.sh:39` 与 `build.ps1:79` 都读它。`CHANGELOG` 顶条虽也已同步，但构建不读它 |
| **D2** | 被治理对象 = 权威的**下游**；权威自身不作为规则 | 避免"循环权威"：iss 不能既是来源又是待检项 |
| **D3** | **热修通道是 Windows / macOS 共用的下发通道**（非 macOS 专属）；macOS **不做**升级通道 | 热修链的产物与运行时本就跨平台：`make_hotfix.py` → `patch.json` → `patch_overlay.py` 覆盖层。Windows 侧已成熟并在服役。升级链不同：它是 Inno + `ShellExecuteW runas` 驱动的，macOS 无对应物 |
| **D3b** | 因此 macOS 上**热修是唯一的修复下发路径** → 不是"保留"，是**必须做对** | 没有升级通道兜底，热修一旦不通，macOS 用户只能重装 dmg |
| **D4** | macOS 签名 = **ad-hoc（`codesign --sign -`）**，不做公证 | 零成本、无前置账号；代价是首次打开需右键→打开，写进文档 |
| **D5** | macOS 启动器 = **rumps 菜单栏 app**（新写，非搬运） | 用户选定。MM 的 `macos/launcher.py` 是它那 353 行 console launcher 的镜像，搬过来会丢掉 mrrc 的 `config_io`/`patch_overlay`/`upgrade_core`/`MRRC_users.db` 语义 |
| **D6** | 检查器落 `dev_tools/`，不落技能目录 | 沿用 §2.3 的本仓库惯例；顺带消除 MM 那套运行时项目发现的需求（`ROOT = parents[1]` 一行足够） |
| **D7** | 技能做**三个**：`mrrc-release` + `windows-installer` + `macos-installer` | 原计划"1+1"是在 macOS 链不存在时定的；现在 macOS 有真实产物与真实陷阱，应独立成篇 |
| **D8** | `CHANGELOG.md` 的 `[Unreleased]`/`[未发布]` 标题**保持原样，不规范化** | 历史记录不该为了工具改写；由 pattern 跳过非版本标题 |
| **D9** | P1 不做 `--online` | 需要站点 + 远端 tag，且 MM 的实现硬编码 `origin`。真要做时另立 |

**以上 D1–D9 为推荐默认，spec 复核时均可推翻。**

## 4. P1：完成度检查器

### 4.1 交付物

```
dev_tools/release_check.py        检查器（stdlib only，可 --json / --strict）
dev_tools/release_artifacts.json  机器可读的产物清单（规则表）
tests/test_release_artifacts.py   stdlib unittest，导入检查器
```

### 4.2 规则 schema（精简版 —— 只保留会被读取的字段）

```jsonc
{
  "version": 1,
  "app_version_source": {          // 只读，不判定
    "path": "packaging/windows/MRRC.iss",
    "pattern": "#define MyAppVersion \"([0-9.]+)\"",
    "comment": "安装版本的唯一权威；build.ps1 与 release_windows.sh 都读它"
  },
  "rules": [
    {
      "id": "changelog-top",
      "path": "CHANGELOG.md",
      "pattern": "^## \\[(?:V)?([0-9]+\\.[0-9]+\\.[0-9]+)\\]",
      "expect": "app",             // 捕获组 1 = 版本
      "first_only": true,          // 只看首个匹配 —— CHANGELOG 有 75 条历史标题，不能数条数
      "why": "人先改的地方；与 iss 不一致意味着有一条忘了改"
    }
  ]
}
```

字段语义（**只移植 MM 里真正被读取的那些**）：

| 字段 | 必填 | 语义 |
|---|---|---|
| `id` | ✅ | 报告标签 |
| `path` | ✅ | 仓库相对路径 |
| `pattern` | ✅ | 正则，**捕获组 1 = 版本**，`re.MULTILINE` |
| `expect` | ✅ | 固定为 `"app"`（本仓库只有一个版本维度；不移植 MM 的 `sdd`） |
| `first_only` | ❌ | 只取**首个**匹配（忽略其余），用于"顶条"语义；与 `count`/`min_count` 互斥 |
| `count` | ❌ | 精确条数，否则 FAIL |
| `min_count` | ❌ | 至少 N 条，否则 FAIL |
| `optional` | ❌ | 文件不存在 → SKIP 而非 FAIL |
| `why` | ❌ | 只进人读报告，不参与判定 |

**不移植**：`sdd_version_source`、`diagrams`、`history_only`、`manual_review`，
以及 MM 里**声明了却从未被读取**的死字段 `artifact_facts.size_pattern`、
`artifact_facts.sha_prefix`、`stale_tokens.allow_versions`。

### 4.3 规则清单（pattern 已按实际文件核实）

| id | path | 锚点 pattern | 期望 | 现状 |
|---|---|---|---|---|
| `changelog-top` | `CHANGELOG.md` | `^## \[(?:V)?([0-9]+\.[0-9]+\.[0-9]+)\]` | **`first_only`** | ✅ 6.1.18 |
| `mobile-css` | `www/mobile_modern.html` | `mobile_modern\.css\?v=([0-9.]+)` | count 1 | ⚠️ 6.1.16 |
| `mobile-footer` | `www/mobile_modern.html` | `version-text">MRRC V([0-9.]+)` | count 1 | ⚠️ 6.1.16 |
| `mobile-zh-footer` | `www/mobile_modern_zh.html` | `version-text">MRRC V([0-9.]+)` | count 1 | ⚠️ 6.1.16 |
| `readme-title` | `README.md` | `\(MRRC\) V([0-9.]+)` | count 1 | ✅ |
| `readme-badge` | `README.md` | `version-V([0-9.]+)-green\.svg` | count 1 | ✅ |
| `readme-cn-title` | `README_CN.md` | `\(MRRC\) V([0-9.]+)` | count 1 | ⚠️ V6.0.0 |
| `readme-cn-badge` | `README_CN.md` | `版本-V([0-9.]+)-green\.svg` | count 1 | ⚠️ V6.0.0 |
| `readme-en-title` | `README_en.md` | `\(MRRC\) V([0-9.]+)` | count 1 | ⚠️ V6.0.0 |
| `readme-en-badge` | `README_en.md` | `version-V([0-9.]+)-green\.svg` | count 1 | ⚠️ V6.0.0 |
| `readme-cn-latest` | `README_CN.md` | `最新版本: V([0-9.]+)` | count 1 | ⚠️ V6.0.0 |
| `readme-en-latest` | `README_en.md` | `Latest Version: V([0-9.]+)` | count 1 | ⚠️ V6.0.0 |
| `website-stat` | `website/index.html` | `stat-value">V([0-9]+\.[0-9]+\.[0-9]+)` | count 1 | ✅ |
| `website-headline` | `website/index.html` | `section-title">V([0-9]+\.[0-9]+\.[0-9]+)` | count 1 | ✅ |
| `website-zh-stat` | `website/zh/index.html` | `stat-value">V([0-9]+\.[0-9]+\.[0-9]+)` | count 1 | ✅ |
| `website-zh-headline` | `website/zh/index.html` | `section-title">V([0-9]+\.[0-9]+\.[0-9]+)` | count 1 | ✅ |

**硬性约束：pattern 必须是锚点式的，绝不允许对整文件裸扫 `V[0-9.]+`。**
反例：`README.md:35-40` 是一段"更新史"（V6.0.10、V6.0.7…），
`website/index.html:329` 提到"Installs up to V6.0.10" —— 这些**是历史事实，不该被改**。
MM 用 `history_only` 名单处理同类问题；本仓库改用**锚点 pattern** 从根上避免。

> **上表 16 条 pattern 已对着真实文件实测**（不是推演）：7 条干净、9 条精确命中
> `www/mobile_modern*.html`、`README_CN.md`、`README_en.md` 四个文件的漂移，
> 且锚定后的 website 规则**不会**误伤 `website/index.html:327,329` 的
> `V6.1.0` / `V6.0.10` 历史举例（这正是裸扫 `V[0-9.]+` 会犯的错）。

**刻意不设规则的文档**：`docs/current/operations/release-process.md` 与 `win_pack.md`。
已核实二者出现的版本串**全部是历史举例**（`6.0.3`、`V6.1.10/11`、`6.1.8`/`6.1.9`）或
占位符（`MRRC-Setup-<ver>.exe`）—— 给它们造 pattern 只会把**正确的历史记录**判成漂移。
这两份文档的同步由人复核（`mrrc-release` 技能里列为发布后清单的一项）。

### 4.4 CLI

对齐 `dev_tools/site_audit.py`：

```
python3 dev_tools/release_check.py            # 人读报告（ASCII 标记 ok / FAIL / skip）
python3 dev_tools/release_check.py --json     # 机器可读（tests 用）
python3 dev_tools/release_check.py --strict   # 发布日：SKIP 也算失败
```

退出码：`0` 干净；`1` 有 FAIL（**总是**，不依赖 `--strict`）；`2` 清单不可读或权威无法解析。
`--strict` 额外把 SKIP 也算失败（发布日每个产物都该在）。
输出用 **ASCII 标记而非 emoji** —— 本仓库有 Windows 控制台历史（`win_pack.md` 的 GBK 陷阱），
emoji 会在 GBK 代码页下出乱码。

### 4.5 测试 `tests/test_release_artifacts.py`

沿用 `tests/test_site_audit.py` 的风格（stdlib `unittest`，`sys.path.insert` + `import`）：

1. **真实仓库干净**：`rc.main([]) == 0` —— 这一步在 P1 完成时必须为真，
   意味着**现存漂移（§2.4 四个文件）要先修掉**；
2. **规则引擎单测**：临时目录 + 显式传 `root=` 参数（`evaluate_rule(rule, expected, root)`，
   不用 `mock.patch` —— 依赖注入比打补丁更直白），
   覆盖 版本一致 → PASS、iss 与 changelog 不一致 → FAIL、文件缺失 + `optional` → SKIP、
   `first_only` → 只取首个匹配、`first_only` 与 `count` 同时出现 → 加载报错；
3. **构建步守卫**（对应 MM 的 `VersionTxtBuildStepTests`）：断言
   `packaging/windows/build.ps1` 仍从 iss 派生 `version.txt`（字符串存在性检查），
   防止有人改回硬编码；
4. 全部离线、无网络、无硬件，秒级。

## 5. P2：三个发布技能

落点（`dev_tools/sync_skills.sh` 以 `.pi/skills/` 为权威，同步到 `~/.pi/agent/skills` 与 `~/.agents/skills`）：

```
.pi/skills/mrrc-release/SKILL.md
.pi/skills/windows-installer/SKILL.md
.pi/skills/macos-installer/SKILL.md
```

**注意**：`sync_skills.sh:9-20` **只复制 `SKILL.md`**。
因此技能正文里**不得**引用同目录的兄弟文件；所有对检查器的引用都写成仓库相对路径
（`dev_tools/release_check.py`），保证全局安装后依然成立。

frontmatter 的 `description` 要写成**触发条件**（含症状词），让 agent 能自己判断何时加载：
- `mrrc-release`：要发版 / 发热修 / 改 `latest.json` / `patch.json` / 部署站点 / 版本号该改哪些文件；
- `windows-installer`：要出 Windows 安装包 / VM 连不上 / `BUILD_DONE` 但没产物 / PyInstaller 或 iscc 失败 / 产物缺 DLL；
- `macos-installer`：要出 macOS dmg / `.app` 打不开「已损坏」/ 服务端起不来 `Failed to load Python shared library` / 无麦克风权限 / 热修补丁没被 macOS 启动器应用。

正文骨架（每个技能）：
1. **何时用 / 何时不用**；
2. **决策**（`mrrc-release` 独有：发版 vs 热修 —— 引 `release-process.md` §4 的可热修文件表；
   并说明**热修是 Windows / macOS 共用的下发通道**，macOS 侧它是唯一的修复路径）；
3. **命令序列**（直接给可复制的命令，指到 `dev_tools/release_windows.sh` 的参数）；
4. **CRITICAL Gotchas** —— 每条附真实出处（文件:行 或 日期）；
5. **验证**；
6. **收尾**（跑 `dev_tools/release_check.py --strict`）。

`mrrc-release` 必须收录的既有陷阱（源自 `release-process.md` / `win_pack.md` / `AGENTS.md`）：
- `deploy_website.sh` 是 `rsync --delete` → 回退目标包**必须入库**，否则【回退】按钮 404（2026-09-16 实际发生过）；
- 服务器 `/tmp` 是 454 MB tmpfs → 45 MB 包先传 `~` 再 `sudo mv`；
- 线上复核必须用**服务端** `sha256sum`；
- 安装版本必须 **>** 热修通道最新版本，否则启动器反复重放旧热修；
- `latest.json` 的 `installer.sha256` 必须对应**带版本名**的文件。

另需更新 `AGENTS.md`：在「Existing Guidance」附近加一行指向三个技能，
并补一条 `dev_tools/release_check.py` 的用法（对齐现有 `site_audit.py` 的记述方式）。

## 6. P3：macOS 打包链

### 6.1 新增文件

```
packaging/macos/build.sh             构建编排（改自 mrrc_modern，194 行版）
packaging/macos/Info.plist           包描述（CFBundleName=MRRC, net.vlsc.mrrc）
packaging/macos/mrrc_launcher.spec   launcher 的 onefile spec（mac 专用，放这里与 build.sh 同目录）
macos/launcher.py                    rumps 菜单栏启动器（新写，自带 helper）
macos/first_run.py                   首启自动配置（改自 mrrc_modern）
macos/MRRC.conf.template             配置种子（mac 口味）
macos/launcher_log.py                StartupTee 日志复制（新写，见 §6.4）
```

`mrrc_server.spec` 与 `atr1000_proxy.spec` **不动**：二者已有 darwin vendor 分支
（`mrrc_server.spec:70-75`、`atr1000_proxy.spec:17-22`），macOS 构建直接复用，
只在 `build.sh` 里指定 `--distpath`。

**唯一被修改的既有文件**：`packaging/hotfix/verify_hotfix.py`（参数化，向后兼容，见 §6.4）。
```

### 6.2 从 `mrrc_modern` **近乎照搬**的部分（它花 6 个版本才调对）

- `.app` 手工装配 + **两个软链**：`Contents/Frameworks -> Resources`、
  `Contents/MacOS/_internal -> ../Resources`。
  理由：`codesign` 拒绝签含数据的 `MacOS`/`Frameworks`；且 bundle 模式启动器把
  `sys._MEIPASS` 解析为 `Contents/Frameworks`。
  **缺这两个软链的症状**：`Failed to load Python shared library '.../Contents/Frameworks/Python'`。
- ad-hoc 签名**顺序**：先 `*.dylib`/`*.so`，再三个可执行文件，最后根 bundle；**不加 `--deep`**。
- `hdiutil create -fs HFS+ -format UDZO -srcfolder <staging>`（**不用** `create-dmg`）。
- `runtime_path()` / `app_dir()` / `wait_for_server()` / `build_command()` 这几个 helper 的**思路**。
- `first_run.py` 的串口探测（macOS `/dev/cu.*`）。

### 6.3 必须改（照搬会坏）

| 项 | `mrrc_modern` | 本仓库 |
|---|---|---|
| 版本来源 | `CHANGELOG.md` 小写 `## [v…]` | **`MRRC.iss` 的 `MyAppVersion`**（小写 v 的 pattern 在本仓库匹配不到，会直接 abort） |
| 产品名 | `MRRC Modern` | `MRRC` |
| Bundle ID | `net.vlsc.mrrc-modern` | `net.vlsc.mrrc` |
| 可执行名 | `MRRC-Modern-Launcher` / `-Server` | `MRRC-Launcher` / `MRRC-Server`（mac 无 `.exe`） |
| server 入口 | `server.py` | `packaging/pyinstaller/frozen_entry.py` + `_internal/app/` 覆盖层 |
| 配置模块 | `config.py`（`default_baud_for`） | **`config_io.py`**（无 `config.py`） |
| 数据文件 | `mem_channels.json` | **`memory_channels.json`** + `MRRC_users.db` |
| 端口 | 8888 | **8877** |
| 用户数据目录 | `~/Library/Application Support/MRRC-Modern` | `~/Library/Application Support/MRRC` |
| 配置模板 | `macos/default.env` | 新增 `macos/MRRC.conf.template`（`coreaudio`、`/dev/cu.*`） |

`Info.plist` 必须含 `NSMicrophoneUsageDescription`，否则 **macOS 静默哑音 RX**
（`mrrc_modern` 的 `build.sh:69-73` 已把它做成硬失败 —— 照抄这个守卫）。

### 6.4 启动器（rumps，新写）

保留 `mrrc_modern` 的**形态**：`LSUIElement` 菜单栏、菜单项
`Open Web UI / Edit Config / Show Password / Restart / Quit`、
退出码 42 自动重启、`rumps.alert` 报致命错、启动 stdout 走 tee。

**但逻辑对着本仓库重写**，复用本仓库既有的平台中立模块：
`ssl_bootstrap`（证书）、`config_io`（配置读写 + GBK 迁移）、
`patch_overlay`（热修覆盖层）、`upgrade_core`（版本决策 —— 仅用于读取/展示，不触发安装）、
`memory_channels.json` 与 `MRRC_users.db` 的种子逻辑。

**D3 的落地**：macOS 启动器**不提供**升级入口；菜单里若显示新版本，只给"打开下载页"。

**热修通道（D3/D3b）—— 本设计里最容易低估的一块。** 现状是**通道跨平台、客户端实现不跨平台**：

| 环节 | 现状 | macOS 侧要做什么 |
|---|---|---|
| 产物生成 `hotfix-<ver>.zip` + `patch.json` | `packaging/hotfix/make_hotfix.py`（Python，仅一处打印提到 `%LOCALAPPDATA%`） | **可共用**，无需改 |
| 运行时覆盖层 | `patch_overlay.py` 跨平台解析 `patch/`（`:82-90`） | **可共用**，无需改 |
| 客户端：检查/下载/校验/解包 | `windows/launcher.py:173-217 check_for_hotfix()` + `:125-155 apply_hotfix_pack()` | **必须在 `macos/launcher.py` 重新实现**：拉 `patch.json`、比版本、校验 `requires` 与 SHA-256、解到 `patch/` |
| 构建期验收闸门 | `packaging/hotfix/verify_hotfix.py` —— **硬编码 `MRRC-Server.exe`（`:122`）与 `%LOCALAPPDATA%`（`:134`）** | 需参数化（`--exe-name` / `--patch-root`）或加 mac 分支，否则 macOS 产物**过不了同一道闸门** |
| 手动/离线安装工具 | `packaging/hotfix/apply_hotfix.ps1`（PowerShell） | macOS 无对应物；**本期不做**，文档里写明 macOS 走启动器自动热修 |

已核实客户端流程的语义（照此在 macOS 侧等价实现，勿改语义）：
`latest` 必须 **>** 本机 `version.txt`；`requires` 必须 **≤** 本机版本（否则"假装修好了"）；
`patch.json` 404 = 从未发布过热修，静默跳过；任何失败只警告、**不阻断启动**。

**本仓库的 Windows 运行时代码一行都不动。** 已核实：本仓库没有独立的 `launcher_log.py`，
tee 实现在 `windows/launcher.py:474 tee_child_output`。因此不采用"抽取共用模块"的方案
（那会让 P3 的回归面覆盖到正在服役的 Windows 链），改为：

**唯一对既有文件的改动**是 `packaging/hotfix/verify_hotfix.py`（§6.4 热修表）：
它硬编码了 `MRRC-Server.exe`（`:122`）与 `%LOCALAPPDATA%`（`:134`），
是 macOS 产物过验收闸门的必经环节。做法是**参数化 + 默认值等于现状**
（新增 `--exe-name` / `--patch-root`，缺省时行为与今天完全一致），
以保证 `dev_tools/release_windows.sh:86` 的现有调用**字节级不变地继续工作**。


- `macos/launcher.py` **自带**它的 helper（`app_dir` / `runtime_path` / `wait_for_server` /
  `build_command`）—— `mrrc_modern` 的 macOS 启动器本来就是自成一套（它那边的两个
  launcher 也是近重复而非共用），照此办理；
- 新增 `macos/launcher_log.py`（等价于 `mrrc_modern` 的 `launcher_log.StartupTee`），
  **不碰** `windows/launcher.py` 里的 `tee_child_output`；
- 真正复用的只有本就平台中立的顶层模块：`ssl_bootstrap`、`config_io`、
  `patch_overlay`、`upgrade_core`（只读版本，不触发安装）。

因此 P3 对在服役代码只有**一处向后兼容的参数化改动**（`verify_hotfix.py`），
其余一律新增文件，回归面可控；
`tests/test_launcher_tee.py`、`tests/test_upgrade_core.py`、`tests/test_patch_overlay.py`
应始终为绿（它们只覆盖 Windows 侧，本设计不触及）。

### 6.5 构建前置（写进技能）

- 用 **`venv/bin/python`**，**不要** `source venv/bin/activate`
  （`mrrc_modern` 的 `.venv` 是从别的仓库复制的，activate 脚本硬编码了错误的 `VIRTUAL_ENV`；
  本仓库的 `venv/` 需实测确认是否同样问题，实施时验证）；
- `pip install rumps pyobjc-framework-Cocoa`（本仓库当前两者皆无，§2.6）；
- `pip install pyaudio` 需先 `brew install portaudio`。

## 7. 验证策略（每期独立的完成判据）

| 期 | 完成判据 |
|---|---|
| **P1** | `python3 dev_tools/release_check.py --strict` 退出码 0；`python3 -m unittest tests.test_release_artifacts` 全绿；§2.4 的四个漂移文件已修正 |
| **P2** | 三个 `SKILL.md` 存在于 `.pi/skills/` 且被 git 跟踪；`./dev_tools/sync_skills.sh` 后 `~/.pi/agent/skills` 与 `~/.agents/skills` 出现同名技能；技能里引用的**每个** `file:line` 抽查可核对；`AGENTS.md` 已接线 |
| **P3** | `packaging/macos/build.sh` 在干净 `venv/` 上跑通并产出 `.app` + `.dmg`；`codesign --verify` 通过；`spctl -a -t exec` 不报 damaged；**从 dmg 安装到 `/Applications` 双击能启动、浏览器自动打开、RX 有声**（真机验收，不可省）；产物内 `Contents/Resources/version.txt` == `MRRC.iss` 的 `MyAppVersion`；**热修通道端到端可用**：发一个真热修补丁 → macOS 启动器拉到、校验 SHA-256、解到 `patch/`、重启后覆盖层生效（因 macOS 无升级通道，这是唯一的修复下发路径，必须实测而非推断）；**且 Windows 侧 `verify_hotfix.py` 的现有调用（`release_windows.sh:86` 的参数形态）仍通过**，证明参数化是向后兼容的 |

**P1 与 P2 可先合入并产生价值，P3 独立推进。**

## 8. 风险与未决

| 风险 | 应对 |
|---|---|
| `rumps` / `PyObjC` 在 Python 3.11 + 本机架构上装不上（`mrrc_modern` 文档记录过旧 Python 装不上的坑） | P3 第一步就先验证这一步；装不上则回到"无 GUI 启动器"方案（需你重新拍板） |
| 两份 launcher（Windows / macOS）各自演化，helper 逻辑漂移 | 接受这个代价换取"不碰在服役代码"（§6.4）。真正共享的语义（配置、证书、热修覆盖层）都在既有顶层模块里，已天然共用；**纯 helper 允许重复** |
| 规则表可能漏掉"某人新加了一个带版本的文件" | 这是**已知的能力边界**：清单是人维护的。`release_artifacts.json` 的 `description` 里写明"新文件开始携带版本/大小时必须补一条规则"，并由 `mrrc-release` 技能在发布后清单里提示 |
| `verify_hotfix.py` 参数化时改坏 Windows 验收闸门（`release_windows.sh:86` 正在用它） | 新增参数**全部可选、缺省即现状**；P3 完成判据里加一条"Windows 侧 `verify_hotfix.py` 现有调用仍通过" |
| P3 的真机验收依赖你的 Mac + 音频设备 | 由你执行；验收清单写在 `macos-installer` 技能里 |
| `venv/` 的 activate 问题（§6.5） | 实施时实测；技能里直接要求用绝对路径解释器 |

**未决**：无。D1–D9 为推荐默认，复核时可改。

## 9. 分期与实施顺序

```
P1  检查器 + 测试 + 修掉四处现存漂移        ← 独立可交付，立刻有价值
P2  三个技能 + AGENTS.md 接线               ← 依赖 P1 的命令行存在
P3  macOS 打包链（含启动器）                ← 独立，最重，最后做
```

P3 内部顺序（**先验证前提，再动手**）：

1. 装 `rumps`/`PyObjC`，确认在 Python 3.11 上可行（否则回头改方案）；
2. `macos/MRRC.conf.template` + `Info.plist`（含 `NSMicrophoneUsageDescription` 硬守卫）；
3. `macos/launcher.py` 最小可用：起 server + 探健康 + 开浏览器 + 菜单退出；
4. `packaging/macos/build.sh`（含软链布局与 ad-hoc 签名）+ 出 dmg；
5. **热修通道**：`macos/launcher.py` 实现客户端检查/下载/校验/解包；
   `verify_hotfix.py` 参数化（去掉硬编码的 `MRRC-Server.exe` 与 `LOCALAPPDATA`）
   使 macOS 产物能过同一道闸门 —— 这是 macOS **唯一**的修复下发路径，做在真机验收之前；
6. 真机验收（§7 的 P3 判据全项）；
7. 补首启自动配置 `first_run.py`。

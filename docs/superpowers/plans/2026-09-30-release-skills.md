# 发布技能（P2）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"发版时该做什么、什么会静默出错"从记忆和零散文档，变成两条能在仓库里被检查、被同步到全局的 skill。

**Architecture:** `.pi/skills/<name>/SKILL.md` 是唯一真相源（`dev_tools/sync_skills.sh` 只复制 SKILL.md 到 `~/.pi/agent/skills` 与 `~/.agents/skills`）。技能正文里所有仓库相对路径都由 `tests/test_release_skills.py` 校验存在性——技能因此不会悄悄漂移。技能**不**内联检查器代码，只引用 P1 落地的 `dev_tools/release_check.py`。

**Tech Stack:** Markdown（YAML frontmatter）+ Python 标准库（`unittest` / `re` / `pathlib` / `json`）+ Bash（改一处 `dev_tools/release_windows.sh`）。

**Spec:** `docs/superpowers/specs/2026-09-30-release-engineering-design.md`（§5 三个技能、§7 P2 完成判据）

**前置依赖**：本计划假定 **P1（`2026-09-30-release-checker.md`）已合入**。Task 4 会校验技能里引用的
`dev_tools/release_check.py` 等 P1 产物存在。

## 与 spec 的偏离（需要你点头）

spec D7 批准了**三个**技能。本计划只交付**两个**：

- `mrrc-release` ✅
- `windows-installer` ✅
- `macos-installer` ⏸ **挪到 P3 交付**

理由：这类技能的价值全在"每条 gotcha 都对应一次真实坏过的构建"（MM 的技能开头就是这么写的）。mrrc 现在**没有任何 macOS 打包链**——P2 阶段写 `macos-installer`，它只能是推测性的流程描述，没有一条经过实战。P3 把链子搭起来、跑通一次真机验收之后再写，技能才是有价值的。这**只调整交付时机，不调整 D7 的内容**：三个技能最终都会有。

## 第二处偏离（需要你点头）

核对发行源码包时发现一个真实问题，本计划顺手修掉：

**`dev_tools/release_windows.sh:63-76` 打的源码包会把 `certs/` 整个带上构建 VM。** 该目录是 git 跟踪的，其中有 `certs/backup/radio.vlsc.net.key.20260317_010431`（**TLS 私钥**）与 `certs/legacy/UHRH.key`。已实测确认**构建链一行都不读 `certs/`**（`grep -rniE '\bcerts\b' packaging/ dev_tools/release_windows.sh` 无输出，`MRRC.iss` 只打包 `dist\windows\MRRC\*`），所以它是纯粹的净损失。Task 3 修掉并加守卫测试。

不想动发布脚本的话，直接删掉 Task 3——它是独立的，不影响 Task 1/2/4。

## Global Constraints

- **技能 frontmatter 必须用 mrrc 的文风**（见 `.pi/skills/mrrc-product-support/SKILL.md`）：`name` / 中文 `description`（以"当需要…时使用"收尾）/ `license: GPL-3.0` / `metadata.repo: HAM/mrrc`。**不是** mrrc_modern 的英文 description 风格。
- **只复制 SKILL.md**：`sync_skills.sh` 不带走技能目录下的其它文件。技能里**绝不能**引用"本技能目录下的 X"（如 MM 的 `harness/release_check.py`）——只能引用仓库相对路径。
- **版本权威 = `packaging/windows/MRRC.iss` 的 `MyAppVersion`**。这与 `../mrrc_modern` **相反**（那里是 CHANGELOG 顶条），两边习惯不可混用。这条必须在 `mrrc-release` 里写明。
- **技能的断言必须可核对**：每条 gotcha 要么指向本仓库的代码行，要么指向 `docs/current/` 下的文档，要么标明出自 `mrrc_modern` 的同宿主实测。不写没有出处的警告。
- **凡是断言"某文件在 X"的地方，反引号里写完整仓库相对路径**（`packaging/pyinstaller/mrrc_server.spec`，不是 `mrrc_server.spec`）——Task 4 的测试只校验"以已知顶层目录开头"的反引号 token，裸文件名会被跳过。文件名太长的后文可以简称，但**首次出现必须是全路径**。
- **不改 `MRRC` 主脚本、`windows/launcher.py`**（它们在 PYZ 里，改动必须重发安装包——见 AGENTS.md）。

## Review Focus

以下六类最可能让用技能的人踩坑，且不被任务测试天然覆盖；每条都在对应任务里钉住：

1. **把 mrrc_modern 的版本权威习惯带过来**（去改 CHANGELOG 顶条当权威，或以为 `build.sh` 会解析它）→ 发出去的包 `version.txt` 与 iss 不符，一键升级判定错乱。→ `mrrc-release` 开篇断言 + Task 4 的 `test_release_skill_states_authority`。
2. **热修包的 `requires` 用了默认值**：`packaging/hotfix/make_hotfix.py:171` 的 `--requires` 默认是 **`6.0.3`**，而 `release_windows.sh:145` 给的示例命令**不传** `--requires` → 一个只对 6.1.x 有效的补丁会被允许装到 6.0.x 上。→ `mrrc-release` 必须写明"显式传 `--requires`"。
3. **热修通道最危险的失败是静默的**：`make_hotfix.py` 出包后忘了 `cp dist/hotfix/* website/downloads/` + `./deploy_website.sh`，客户端拿到 HTTP 404 **按设计静默跳过、不报错**（`windows/launcher.py` 的 `check_for_hotfix`），于是"修了但没人收到"且毫无症状。→ `mrrc-release` 的验收表把"线上 `patch.json` 可下载"列成硬门禁。
4. **源码包把 `certs/` 私钥带上构建 VM** → Task 3 的 `ReleaseSourceZipTests`。
5. **只信构建脚本的退出码/`BUILD_DONE` 而不认产物**：`release_windows.sh:83` 只把 `build exit=$LASTEXITCODE` 打进日志。→ `windows-installer` 的"认产物"章节。
6. **技能里引用的路径/命令在仓库里不存在**（改名、删除后技能没跟）→ Task 4 的 `tests/test_release_skills.py` 逐条校验。

---

### Task 1: `.pi/skills/mrrc-release/SKILL.md`

**Files:**
- Create: `.pi/skills/mrrc-release/SKILL.md`

**Interfaces:**
- Consumes: P1 的 `dev_tools/release_check.py`（`--strict`）与 `dev_tools/release_artifacts.json`
- Produces: 技能名 `mrrc-release`（Task 4 的测试与 AGENTS.md 注册依赖它）

- [ ] **Step 1: 写文件**

创建 `.pi/skills/mrrc-release/SKILL.md`：

````markdown
---
name: mrrc-release
description: MRRC 发版全链路——版本号权威（MRRC.iss 的 MyAppVersion）与全仓一致性检查、Windows 安装包的构建/站点发布/SHA-256 线上复核、以及热修通道（不重装给已装用户下发修复，含 latest.json / patch.json 的维护）。当需要发布新版本、决定"发版还是发热修"、改 latest.json 或 patch.json、部署站点、给已装用户下发修复、修"某个文件版本号忘了改"、或排查"装的是新包但行为没变""点升级却反复重放旧补丁"时使用。
license: GPL-3.0
metadata:
  repo: HAM/mrrc
  lifecycle-doc: docs/current/operations/product-support-lifecycle.md
  release-runbook: docs/current/operations/release-process.md
  upgrade-doc: docs/current/operations/one-click-upgrade.md
  hotfix-checker: dev_tools/release_check.py
---

# MRRC 发版

## 何时用 / 何时不用

**用**：要出一个新版本；要决定"这次该发版还是发热修"；给已装用户下发修复；改
`latest.json`/`patch.json`；部署站点；版本号该改哪些文件；"装的是新包但行为没变"。

**不用**：改构建脚本本身/VM 排障 → `windows-installer`；改 macOS 打包 → `macos-installer`（P3 后可用）。

## 第一个决策：发版还是热修？

先看你要改的文件落在 `docs/current/operations/release-process.md` §4 的哪一行：

| 位置 | 能否热修 | 走哪条路 |
| --- | --- | --- |
| `www/**`（前端） | ✅ | 热修 |
| `mrrc_server.spec` 的 `_APP_MODULES` 里的模块 | ✅ | 热修 |
| `vendor`（第三方依赖 / 原生库） | ✅ | 热修 |
| 其它 Python（`MRRC` 主脚本、`windows/launcher.py`） | ❌ 在 PYZ 里 | **必须重发安装包** |
| 原生 DLL（`vendor/{opus,hamlib,wdsp}`）需重建 | ❌ | **必须重发安装包** |

判据一句话：**改动落在覆盖层够得着的地方就发**热修，落在 PYZ 里就**必须**重发包。

## 版本权威只有一处

**`packaging/windows/MRRC.iss` 的 `#define MyAppVersion "6.1.18"`。**

```
MRRC.iss  ──► dev_tools/release_windows.sh:39      取发行号
    │     └─► packaging/windows/build.ps1:79-86   写 dist/windows/MRRC/version.txt
    └────────► windows/launcher.py:108-114        运行时 _installed_version() 读 version.txt
```

产物里**没有任何编译进去的版本常量**——运行时版本完全来自 `version.txt`，而它必须由
`build.ps1` 从 iss 派生。`tests/test_release_artifacts.py::VersionTxtDerivationTests` 守着这条。

> ⚠️ 这与 `../mrrc_modern` **相反**：那边 CHANGELOG 顶条是权威、iss 手抄。别把两边的习惯混用。
> CHANGELOG 顶条在 mrrc 里是**下游**，由 `dev_tools/release_check.py` 治理，不是权威。

## 发版前：先跑一致性检查

```bash
python3 dev_tools/release_check.py            # 人读：列出哪个文件还停在旧版本
python3 dev_tools/release_check.py --strict   # 发布日：SKIP 也算失败
```

退出码 `0` 干净 / `1` 有漂移 / `2` 规则表或权威不可读。规则表在
`dev_tools/release_artifacts.json`——**新文件开始携带版本号时必须补一条规则**，
否则它会静默漂移（这正是 `www/mobile_modern*.html` 与两个非英文 README 落后 2~11 个版本的成因）。
规则 pattern 必须锚定到具体位置，**绝不可裸扫 `V[0-9.]+`**。

## 发版：一条命令

```bash
./dev_tools/release_windows.sh
```

它依次做：读 iss 版本 → 打源码包 → 传 `ham.vlsc.net` → 跳进 Win11 VM 构建
（`packaging/windows/build.ps1`）→ 在产物上跑热修通道验收
（`packaging/hotfix/verify_hotfix.py`）→ 取回 exe → 归档上一版 → 生成 `latest.json`
→ 提交推送 → `./deploy_website.sh` → 下载线上包比对 SHA-256。

常用开关：`--skip-build`（用 VM 上已有产物，只取回+发布）、`--no-deploy`（只出包+提交）、
`--dry-run`。

构建细节与 VM 排障见同目录的 `windows-installer` 技能。

## 发版后：热修通道（**主要**的修复下发方式）

用户已经装了 6.1.18，你修了 `www/controls.js`——**不要重发包**，走热修：

```bash
python3 packaging/hotfix/make_hotfix.py \
    --version 6.1.19 --requires 6.1.18 \
    --notes "修复 XXX" \
    www/controls.js wdsp_wrapper.py
cp dist/hotfix/* website/downloads/ && ./deploy_website.sh
```

**`--requires` 必须显式传**。`make_hotfix.py` 的默认值是 `6.0.3`（见其 `add_argument`），
一个只对 6.1.x 成立的补丁会被放行到 6.0.x 的装机上。用 `--range v6.1.18..HEAD` 也可自动列出改动。

通道契约（客户端实现在 `windows/launcher.py` 的 `check_for_hotfix` / `apply_hotfix_pack`）：

- `patch.json` 的 `latest` 必须 **>** 本机 `version.txt`，`requires` 必须 **≤** 本机版本；
- 解出的文件经 SHA-256 校验后落到 `%LOCALAPPDATA%\MRRC\patch`，运行时由 `patch_overlay.py` 覆盖；
- 覆盖面只有 `www/**`、`packaging/pyinstaller/mrrc_server.spec` 的 `_APP_MODULES` 与 `vendor`；
- **`MRRC` 主脚本与 `windows/launcher.py` 在 PYZ 里，热修覆盖不到——改动它们必须重发安装包。**

### 四个容易静默失败的坑

1. **忘了 `cp dist/hotfix/* website/downloads/`**：客户端拿到 HTTP 404 会**按设计静默跳过**，
   不报错、不提示。症状是"修了但没人收到"，且没有任何日志异常。所以线上验证是硬门禁（见下）。
2. **`latest` 没大于本机版本**：同样静默跳过。
3. **安装版本必须 > `patch.json` 的 `latest`**：否则装了新版之后启动器还会认定"有新补丁"，
   **反复重放旧热修**，把已经修好的文件覆盖回旧版本。
4. **新版安装包发布时 `latest.json` 的 `previous` 指向站点上不存在的文件**：站点部署是
   `rsync --delete`，**没进 git 的服务器文件会被清掉**——`previous`、`MRRC-Setup-<上一版>.exe`、
   `hotfix-*.zip`、`patch.json` **全部必须入库**，否则【回退到上一版】按钮 404
   （2026-09-16 实际发生过一次）。

### 两个部署期的物理约束

- **服务器 `/tmp` 是 454 MB tmpfs**：连传几个 45 MB 安装包就会写失败
  （`scp: write remote "/tmp/x.exe": Failure`）。大文件先传 `~`，再 `sudo mv` 进
  `/var/www/vlsc.net/mrrc/downloads/`。
- 站点 `downloads/` 是**扁平一层**：`latest.json`、`patch.json`、`MRRC-Setup*.exe`、
  `hotfix-*.zip` 全在同一层。

## 发版验收表

| # | 检查 | 证据 |
| --- | --- | --- |
| 1 | 全仓版本一致 | `python3 dev_tools/release_check.py --strict` → 退出码 0 |
| 2 | 单元测试 | `python3 -m unittest discover -s tests` 全绿 |
| 3 | 产物存在且是新的 | `dist/windows/MRRC-Setup.exe` 的 mtime/大小 + `shasum -a 256` |
| 4 | **服务器侧**哈希一致 | `ssh cheenle@www.vlsc.net 'cd /var/www/vlsc.net/mrrc/downloads && sha256sum MRRC-Setup.exe MRRC-Setup-<ver>.exe'` |
| 5 | 线上包逐字节一致 | `release_windows.sh` 末尾自动比对下载回来的 `MRRC-Setup.exe` 的 SHA-256 |
| 6 | 线上 `latest.json` 正确 | `curl -s https://www.vlsc.net/mrrc/downloads/latest.json`：`latest` 对；`installer.url` 指向**带版本名**的文件；`installer.sha256` 对应该文件；`previous.version` 的文件在站上真实存在 |
| 7 | （发热修时）线上 `patch.json` 可下载 | `curl -sI https://www.vlsc.net/mrrc/downloads/patch.json` → 200；且 `patch.json.latest` > 本机装机版本 |
| 8 | 站点显示新版本 | `curl -s https://www.vlsc.net/mrrc/ \| grep -oE "V<版本>"` |

清单里的 `installer.sha256` 必须等于**带版本名**那个文件（`dev_tools/make_latest_json.py` 自动取它）
——把 `MRRC-Setup.exe` 的名字写进清单是错的。更细的复核清单见
`docs/current/operations/release-process.md` §5。

## 已知的发布后人工项

- **TX 音频无法在构建 VM 上验证**：KVM 的 USB 透传破坏同步 OUT 调度，TX 噼啪声在 VM 上必然出现，
  与代码无关。必须在物理 Windows 机器上验（见 `windows-installer`）。
- 真实电台的通联/录音验收同样只能在物理设备上做。

## 出处

发布排障细节见 `docs/current/operations/release-process.md` 与
`docs/current/operations/one-click-upgrade.md`；根因与 Windows 陷阱见
`docs/current/reliability/RC-002-launcher-upgrade-and-shutdown.md`；
全链路（发版→升级→诊断→分析→答复）见
`docs/current/operations/product-support-lifecycle.md`。
````

- [ ] **Step 2: 核对正文里每条断言**

逐条实测（**不能只靠读**，这些数字写进技能就变成别人会依赖的事实）：

```bash
grep -n 'MyAppVersion' packaging/windows/MRRC.iss
grep -n 'MyAppVersion' packaging/windows/build.ps1
grep -n 'version.txt' windows/launcher.py
grep -n 'requires' packaging/hotfix/make_hotfix.py
grep -n 'patch.json\|check_for_hotfix\|apply_hotfix_pack' windows/launcher.py
grep -n 'latest\|requires\|sha256' packaging/hotfix/make_hotfix.py | head
```

Expected: 行号与技能里写的对得上。**对不上就改技能，不是改代码**。

- [ ] **Step 3: 确认 frontmatter 合法**

Run:
```bash
python3 -c "
import re,pathlib
t=pathlib.Path('.pi/skills/mrrc-release/SKILL.md').read_text(encoding='utf-8')
m=re.match(r'---\n(.*?)\n---\n', t, re.S); assert m, 'frontmatter 缺失'
import yaml  # 若无 pyyaml，改用 dev_tools/test_installation.py 的 JSON 思路跳过本行
print(yaml.safe_load(m.group(1))['name'])"
```
Expected: 打印 `mrrc-release`。若本机无 `pyyaml`，改为人工目视 `head -10`，检查 `name:` / `description:` / `license:` / `metadata.repo:` 四项齐全。

- [ ] **Step 4: 提交**

```bash
git add .pi/skills/mrrc-release/SKILL.md
git commit -m "docs(skills): 新增 mrrc-release —— 版本权威链、发版编排与热修通道"
```

---

### Task 2: `.pi/skills/windows-installer/SKILL.md`

**Files:**
- Create: `.pi/skills/windows-installer/SKILL.md`

**Interfaces:**
- Consumes: 无（Task 1 的 `mrrc-release` 会指向它）
- Produces: 技能名 `windows-installer`

- [ ] **Step 1: 写文件**

创建 `.pi/skills/windows-installer/SKILL.md`：

````markdown
---
name: windows-installer
description: MRRC Windows 安装包（MRRC-Setup.exe / Inno Setup）的构建、校验与排障——在 Win11 KVM VM 上跑 packaging/windows/build.ps1（PyInstaller×3 → iscc）、证明产物真的含本次代码、诊断构建中途 VM 失联/OOM、venv 被删、"打了包但行为没变"、缺 DLL 或静态资源、PowerShell 5.1 与 GBK 编码陷阱。当需要出 Windows 安装包、VM 构建失败、或怀疑产物是旧的时使用。
license: GPL-3.0
metadata:
  repo: HAM/mrrc
  orchestrator: dev_tools/release_windows.sh
  build-script: packaging/windows/build.ps1
  hamlib-vendoring: packaging/windows/collect_hamlib.ps1
---

# Windows 安装包构建（MRRC）

## 谁在驱动它

正常发版**不要手敲这套流程**——`./dev_tools/release_windows.sh` 已经编排好了。
本技能是它的排障手册。手动重建时：

```
Mac ──ssh──► ham.vlsc.net（KVM 宿主）──ssh──► cheenle@192.168.122.133（win11 VM）
                                              默认 shell 是 PowerShell 5.1
```

`packaging/windows/build.ps1` 的门禁顺序（任一步失败即中止，`Invoke-Checked`，见其 :6）：

1. `python -m py_compile` 全部 Python
2. `python -m unittest discover -s tests -v`（全量套件）
3. `dev_tools/test_config_encoding.py`
4. 三个 PyInstaller spec：`packaging/pyinstaller/mrrc_server.spec`、`mrrc_launcher.spec`、
   `atr1000_proxy.spec`
5. 从 `MRRC.iss` 读 `MyAppVersion` 写 `dist/windows/MRRC/version.txt`（:79-86）
6. WDSP DLL（`build_wdsp_dll.ps1`，:110 附近；**刻意不走 `Invoke-Checked`**——gcc 的
   `-I`/`-O` 会被 PowerShell 函数参数绑定误解析）
7. `iscc packaging/windows/MRRC.iss` → `dist/windows/MRRC-Setup.exe`

`MRRC.iss` 只打包 `dist\windows\MRRC\*`（`ignoreversion recursesubdirs createallsubdirs`）
——**原生 DLL 必须先落到 `vendor/{opus,hamlib,wdsp}/windows/bin/x64/`**，否则包里没有它们；
hamlib（含 `rigctld.exe`）用 `packaging/windows/collect_hamlib.ps1` 收集。见 `win_pack.md`。

## 证明产物真的含本次代码（**不要**只看退出码）

`release_windows.sh:83` 只把 `build exit=$LASTEXITCODE` 打进日志。**退出码不是证据**——
`Invoke-Checked` 中止的是*子* PowerShell，外层脚本会继续往下走。只认产物：

```powershell
Get-Item C:\mrrc\dist\windows\MRRC-Setup.exe | Select-Object Length, LastWriteTime
Get-FileHash C:\mrrc\dist\windows\MRRC-Setup.exe -Algorithm SHA256
Get-Content C:\mrrc\dist\windows\MRRC\version.txt     # 必须 == 本次 iss 版本
```

Mac 侧取回后再比对一次：`shasum -a 256 dist/windows/MRRC-Setup.exe` 必须等于 VM 的 `Get-FileHash`。

**`strings`/`grep` 看不进压缩的 PYZ**——缺失的符号和存在的符号长得一模一样。要证明符号在包里，
走归档（VM 的 venv 有 PyInstaller）：

```python
# bundle_check.py —— 在 VM 上跑：.\venv\Scripts\python.exe bundle_check.py
import marshal, types
from PyInstaller.archive.readers import CArchiveReader
r = CArchiveReader(r"C:\mrrc\dist\windows\MRRC\MRRC-Server.exe")
# 注意：PyInstaller 6 里 a.toc 是 dict，不是 list；a.toc[0] 会 KeyError: 0
code = marshal.loads(r.extract("server"))     # 入口"脚本"是 CArchive 条目，不是 PYZ 模块
try:
    code = marshal.loads(r.extract("server"))
except Exception:
    code = marshal.loads(r.extract("server")[8:])   # 可能带 8 字节头
seen = set()
def walk(c):
    seen.update(c.co_names)
    for k in c.co_consts:
        if isinstance(k, types.CodeType): walk(k)
walk(code)
print("你要验的符号" in seen)
```

## 热修覆盖面 = 打包时被踢出 PYZ 的那批模块

`packaging/pyinstaller/mrrc_server.spec:137` 刻意把 `_APP_MODULES`（:28-47）排除出 PYZ，
好让 `patch_overlay.py` 能在运行时用 `%LOCALAPPDATA%\MRRC\patch` 里的 `.py` 覆盖它们。
**新增一个需要可热修的模块，必须同时加进 `_APP_MODULES`**——`upgrade_core` 漏过一次，
VM 实测报 `ModuleNotFoundError`。

## 在产物上跑热修通道验收

`release_windows.sh:86` 会在打包产物上跑 `packaging/hotfix/verify_hotfix.py`。
它从 `%LOCALAPPDATA%\MRRC\` 找配置、按启动器的方式解包到 `patch\`、再启动 `MRRC-Server.exe` 验证。
手动跑：

```powershell
& "$env:USERPROFILE\mrrc\venv\Scripts\python.exe" packaging\hotfix\verify_hotfix.py `
    --app "C:\mrrc\dist\windows\MRRC" --repo "C:\mrrc"
```

## VM 上的陷阱（多数在本仓库实测过）

1. **SSH 会话一断，`Start-Process` 起的子进程会被回收**（Windows job object）。
   长任务别用裸 `ssh ... Start-Process`；用计划任务：
   `schtasks /create /tn X /tr <命令行> /RL HIGHEST /RU <user> /IT` 再 `schtasks /run /tn X`。
   **`/tr` 里别塞引号。**
2. **含中文的 `.ps1` 必须存成 UTF-8 单 BOM**，否则 PowerShell 5.1 按 GBK 读，脚本直接语法错。
3. **`Tee-Object` 没有 `-Encoding` 参数**——写了会报参数不存在。
4. **PowerShell 5.1 的 `&&` 非法**，用 `;`。`2>` 重定向写出的是 UTF-16LE，
   `grep` 前先 `iconv -f UTF-16LE -t UTF-8`。多跳 ssh 的引号嵌套是个坑，
   **总是把命令写成 `.ps1` 本地文件 → scp → `-File` 执行**。
5. **`ham.vlsc.net` 的 `/tmp` 是 454 MB tmpfs**。大文件先传到 `~` 再 `sudo mv` 进去。
   本仓库的产物（exe ~45 MB）不会撞线，但源码包+多份归档要留神。
6. **VM 的网络对 ~45 MB 下载不稳**。离线验收可以用
   `MRRC_UPDATE_MANIFEST=file://…` 指本地清单跑，避免卡在下载上。
7. **venv 会在解压源码时被删掉**：解压前 `Move-Item C:\mrrc\venv C:\mrrc_venv_keep`，
   解压后移回来。venv 真没了就按 `win_pack.md` 的完整重装序列来——
   否则 `.\venv\Scripts\Activate.ps1` 不存在，构建立刻失败。
8. **`requirements-build.txt` 变过就要重装依赖**（保下来的 venv 里是旧依赖）。
9. **"本地绿、VM 红"通常是打开文件没关**：测试留下未关闭的文件句柄时，macOS/Linux 允许
   删除打开的文件，Windows 报 `PermissionError: [WinError 32] ... being used by another process`
   （`TemporaryDirectory.cleanup()` 阶段）。在 `tearDown` 里关掉它。
   **把它当真实的跨平台 bug，不要当 VM 怪癖。**
10. **TX 音频永远无法在这台 VM 上验证**：KVM 的 USB 透传破坏同步 OUT 调度
    （MME 与 WASAPI 一样乱；RX 采集与 FT4222 批量传输不受影响）。别在这儿调 TX 噼啪声，
    去物理 Windows 机器上验。
11. **电台 USB 被拔掉会连带 COM 口和音频设备一起消失**，直到重新附加透传设备。
12. **宿主可能在中途 OOM 掉整个 VM**（*此条出自 `mrrc_modern` 在同宿主的实测，2026-09-12*）：
    症状依次是 `ssh` 报 `No route to host` → `virsh -c qemu:///system domifaddr win11`
    说 domain not running → `/var/log/libvirt/qemu/win11.log` 结尾 `shutting down, reason=crashed`
    → `sudo dmesg -T | grep -i oom` 看到 `Killed process ... (qemu-system-x86)`。
    处置：把 VM 缩到 10 GB 并给宿主加 swap，`virsh start win11` 前先看 `free -m`
    （可用 <1 GB 就还会再死一次）。

## 常见症状对照

| 症状 | 原因 / 处置 |
| --- | --- |
| 脚本打印构建完成但没有新 exe | 退出码不是证据（见上）；看 `Get-Item` 的 mtime + 大小 + `Get-FileHash` |
| 包里缺 opus/hamlib/wdsp 的 DLL | 原生 DLL 没先落到 `vendor/*/windows/bin/x64/`；hamlib 用 `collect_hamlib.ps1` 收 |
| 装了包但行为没变 | 符号不在包里（走 `CArchiveReader` 验）；或改的是 `_APP_MODULES` 里的模块但没进列表 |
| `ModuleNotFoundError` 只在热修后出现 | 该模块**没**在 `mrrc_server.spec` 的 `_APP_MODULES` 里 |
| `Activate.ps1` 找不到 | venv 在解压时被删（陷阱 7） |
| 含中文的 `.ps1` 报语法错 | 存成了无 BOM（陷阱 2） |
| 长任务在 ssh 断开后消失 | job object 回收（陷阱 1）；改用 `schtasks` |
| VM 中途失联 | 宿主 OOM（陷阱 12） |
| 本地绿、VM 报 `WinError 32` | 测试泄漏了打开的文件句柄（陷阱 9） |
| VM 上 TX 噼啪 | KVM 同步 OUT 坏（陷阱 10）；去物理机验，别改代码 |
````

- [ ] **Step 2: 核对正文里每条断言**

```bash
grep -n 'Invoke-Checked\|pyinstaller \|iscc\|MyAppVersion\|version.txt' packaging/windows/build.ps1
grep -n '_APP_MODULES\|PYZ(' packaging/pyinstaller/mrrc_server.spec
grep -n 'Source:' packaging/windows/MRRC.iss
grep -n 'add_argument' packaging/hotfix/verify_hotfix.py
ls -1 packaging/windows/collect_hamlib.ps1 packaging/windows/build_wdsp_dll.ps1
```

Expected: 行号/文件与技能里写的一致（`_APP_MODULES` 在 `mrrc_server.spec:28`、PYZ 排除在 `:137`、
`iscc` 在 `build.ps1:125`、`Source:` 在 `MRRC.iss:28`）。**对不上就改技能**。

- [ ] **Step 3: 确认 frontmatter 与 mrrc 文风一致**

Run: `head -10 .pi/skills/windows-installer/SKILL.md`
Expected: `name: windows-installer`；`description` 是中文且以"时使用。"收尾；
有 `license: GPL-3.0`；`metadata.repo: HAM/mrrc`。

- [ ] **Step 4: 提交**

```bash
git add .pi/skills/windows-installer/SKILL.md
git commit -m "docs(skills): 新增 windows-installer —— VM 构建门禁、产物取证与陷阱"
```

---

### Task 3: 源码包排除清单外置（含 `certs/` 私钥）

**Files:**
- Create: `dev_tools/release_src_excludes.json`
- Modify: `dev_tools/release_windows.sh:63-76`（源码包生成段）
- Test: `tests/test_release_artifacts.py`（追加 `ReleaseSourceZipTests`）

**Interfaces:**
- Consumes: P1 已合入的 `tests/test_release_artifacts.py`（本任务往里追加一个测试类）
- Produces: `dev_tools/release_src_excludes.json`，schema `{"exclude_prefixes": [str], "why": {prefix: str}}`

**为什么**：该目录是 git 跟踪的，含 `certs/backup/radio.vlsc.net.key.20260317_010431`（TLS 私钥）
与 `certs/legacy/UHRH.key`；已实测构建链一行都不读 `certs/`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_release_artifacts.py` 的 `if __name__ == "__main__":` **之前**追加：

```python
class ReleaseSourceZipTests(unittest.TestCase):
    """发行源码包（传给构建 VM 的 zip）的文件选择。

    打包逻辑在 dev_tools/release_windows.sh，排除前缀外置在
    dev_tools/release_src_excludes.json，本测试是该不变量的唯一守卫。
    """

    EXCLUDES = rc.ROOT / "dev_tools" / "release_src_excludes.json"

    def _excludes(self):
        return json.loads(self.EXCLUDES.read_text(encoding="utf-8"))

    def test_exclude_file_exists_and_is_wellformed(self):
        data = self._excludes()
        self.assertIsInstance(data["exclude_prefixes"], list)
        self.assertTrue(all(isinstance(p, str) and p.endswith("/")
                            for p in data["exclude_prefixes"]),
                        "排除前缀必须以 / 结尾，避免 certs 误伤 certs_foo")

    def test_private_key_material_is_excluded(self):
        """certs/ 下确实有私钥，且必须被排除。"""
        import subprocess
        tracked = subprocess.run(["git", "ls-files"], cwd=rc.ROOT,
                                 capture_output=True, text=True, check=True).stdout.split()
        keys = [f for f in tracked if f.startswith("certs/")
                and f.endswith((".key", ".pem"))]
        self.assertTrue(keys, "前提失效：certs/ 下已无私钥，本规则可删")
        excludes = self._excludes()["exclude_prefixes"]
        leaked = [f for f in keys if not any(f.startswith(p) for p in excludes)]
        self.assertEqual(leaked, [], f"私钥会随源码包上传构建 VM：{leaked}")

    def test_every_exclude_prefix_matches_something(self):
        """没有失效规则（拼错的前缀会静默不排除任何东西）。"""
        import subprocess
        tracked = subprocess.run(["git", "ls-files"], cwd=rc.ROOT,
                                 capture_output=True, text=True, check=True).stdout.split()
        for prefix in self._excludes()["exclude_prefixes"]:
            with self.subTest(prefix=prefix):
                self.assertTrue(any(f.startswith(prefix) for f in tracked),
                                f"排除前缀 {prefix!r} 不匹配任何被跟踪文件")

    def test_script_reads_the_exclude_file(self):
        """脚本必须真的读它，而不是各写一份。"""
        text = (rc.ROOT / "dev_tools" / "release_windows.sh").read_text(
            encoding="utf-8", errors="replace")
        self.assertIn("release_src_excludes.json", text)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_release_artifacts.ReleaseSourceZipTests -v`
Expected: ERROR —— `FileNotFoundError`（`release_src_excludes.json` 不存在）

- [ ] **Step 3: 建排除清单**

创建 `dev_tools/release_src_excludes.json`：

```json
{
  "description": "发行源码包（dev_tools/release_windows.sh 打给构建 VM 的 zip）的文件前缀排除清单。一行一个前缀，必须以 / 结尾。由 tests/test_release_artifacts.py::ReleaseSourceZipTests 守卫：私钥不得随包上传，且每条前缀都必须真的匹配到文件（防止拼错后静默失效）。",
  "exclude_prefixes": [
    "website/downloads/",
    "certs/"
  ],
  "why": {
    "website/downloads/": "安装包/热修包由服务器管理，打源码包不需要它们",
    "certs/": "TLS 私钥材料（certs/backup/*.key、certs/legacy/UHRH.key）。已实测构建链一行都不读 certs/（MRRC.iss 只打包 dist\\windows\\MRRC\\*），故纯粹是净损失"
  }
}
```

- [ ] **Step 4: 让脚本读它**

把 `dev_tools/release_windows.sh:63-76` 的源码包生成段整体替换为（注意 `run "..."` 用的是双引号，
Python 里的 `\n` 要保持双反斜杠写法）：

```bash
    run "venv/bin/python3 - <<'PY'
import json, os, subprocess, zipfile
excl = json.load(open('dev_tools/release_src_excludes.json'))['exclude_prefixes']
tracked=[f for f in subprocess.run(['git','ls-files'],capture_output=True,text=True).stdout.split('\\n') if f and os.path.isfile(f)]
tracked=[f for f in tracked if not any(f.startswith(p) for p in excl)]
dsp=sorted(os.path.join('DSP/wdsp',f) for f in os.listdir('DSP/wdsp')
           if f.endswith(('.c','.h','.md','.sh')) or f.startswith(('Makefile','makefile')))
extra=[f for f in ('win_pack.md','memory_channels.json','MRRC_users.db','windows/MRRC.conf.template') if os.path.isfile(f)]
files=sorted(set(tracked+[f for f in dsp if os.path.isfile(f)]+extra))
out='$SRC_ZIP'
if os.path.exists(out): os.remove(out)
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in files: z.write(f,f)
print(f'源码包 {len(files)} 文件 / {os.path.getsize(out)/1e6:.1f} MB（已排除 {excl}）')
PY"
```

**唯一的行为变化**是把 `not f.startswith('website/downloads/')` 换成读清单的多前缀判断。

- [ ] **Step 5: 跑测试确认通过**

Run: `python3 -m unittest tests.test_release_artifacts.ReleaseSourceZipTests -v`
Expected: 4 个测试 PASS

- [ ] **Step 6: 干跑验证脚本没坏**

Run: `./dev_tools/release_windows.sh --dry-run 2>&1 | head -20`
Expected: 打印 `发行版本: V6.1.18` 与 `[dry-run] ...` 行，**无语法错误**（`--dry-run` 下 `run()` 只回显不执行）

- [ ] **Step 7: 真跑一次打包（只到出 zip）**

Run: `venv/bin/python3 -c "
import json,os,subprocess
excl=json.load(open('dev_tools/release_src_excludes.json'))['exclude_prefixes']
t=subprocess.run(['git','ls-files'],capture_output=True,text=True).stdout.split()
sel=[f for f in t if os.path.isfile(f) and not any(f.startswith(p) for p in excl)]
print('certs 命中:', [f for f in sel if f.startswith('certs/')])
print('website/downloads 命中:', [f for f in sel if f.startswith('website/downloads/')])
print('总文件数:', len(sel))"`
Expected: 两个列表都为空 `[]`

- [ ] **Step 8: 提交**

```bash
git add dev_tools/release_src_excludes.json dev_tools/release_windows.sh \
        tests/test_release_artifacts.py
git commit -m "fix(release): 源码包不再带上 certs/ 私钥，排除清单外置并加守卫测试"
```

---

### Task 4: 技能体检测试 + `AGENTS.md` 注册

**Files:**
- Create: `tests/test_release_skills.py`
- Modify: `AGENTS.md`（在「Existing Guidance」之前插入一节）

**Interfaces:**
- Consumes: Task 1/2 的两个 `SKILL.md`；**以及 P1 已合入**——`SkillFactTests.test_referenced_repo_paths_exist`
  会校验技能里引用的 `dev_tools/release_check.py`、`dev_tools/release_artifacts.json`、
  `tests/test_release_artifacts.py` 三个路径存在，它们在 P1 才被创建
- Produces: 让技能里的路径引用在仓库里被机器校验

**前置**：P1 未合入时本任务**必然失败**（已预跑确认：3 条路径 MISS）。先做完 P1。已实测技能正文里
13 条路径全部存在，上述 3 条是唯一缺口。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_release_skills.py`：

```python
"""发布技能（.pi/skills/*）的一致性测试。

技能是给人读的散文，但它里面的仓库路径、命令、权威声明都是"事实"。
这些事实会在文件改名/删除后悄悄失效——本测试把它们钉住。
"""

import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / ".pi" / "skills"

RELEASE_SKILLS = ("mrrc-release", "windows-installer")

# 会被校验存在性的顶层目录（只认这些，避免把 dist/ 之类运行时路径误判）
REPO_DIRS = ("dev_tools/", "packaging/", "windows/", "macos/", "www/",
             "website/", "tests/", "docs/", ".pi/", "DSP/", "certs/")

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)


def read_skill(name):
    return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")


def frontmatter(text):
    m = FRONTMATTER.match(text)
    if not m:
        raise AssertionError("SKILL.md 缺少 YAML frontmatter")
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    if "metadata" in m.group(1):
        meta = re.search(r"metadata:\n((?:  .*\n)+)", m.group(1))
        if meta:
            fields["_metadata"] = meta.group(1)
    return fields


def referenced_repo_paths(text):
    """取出反引号里、以已知顶层目录开头的仓库相对路径。"""
    found = set()
    for token in re.findall(r"`([^`\n]+)`", text):
        token = token.strip()
        if not any(token.startswith(d) for d in REPO_DIRS):
            continue
        if any(ch in token for ch in "*<>%$?") or " " in token:
            continue          # glob / 占位符 / 环境变量路径不是文件
        token = token.split(":")[0].rstrip(".,;")
        found.add(token)
    return found


class SkillFrontmatterTests(unittest.TestCase):
    def test_all_release_skills_exist(self):
        for name in RELEASE_SKILLS:
            with self.subTest(skill=name):
                self.assertTrue((SKILLS_DIR / name / "SKILL.md").is_file())

    def test_frontmatter_matches_mrrc_house_style(self):
        for name in RELEASE_SKILLS:
            with self.subTest(skill=name):
                text = read_skill(name)
                fm = frontmatter(text)
                self.assertEqual(fm.get("name"), name,
                                 "frontmatter name 必须等于目录名（sync_skills.sh 依赖）")
                self.assertIn("license", fm)
                self.assertIn("metadata", fm)
                self.assertIn("repo: HAM/mrrc", fm["_metadata"])
                desc = fm.get("description", "")
                self.assertTrue(desc.endswith("使用。"),
                                "description 需以“使用。”收尾（mrrc 文风）")
                self.assertGreater(len(desc), 40)


class SkillFactTests(unittest.TestCase):
    def test_referenced_repo_paths_exist(self):
        for name in RELEASE_SKILLS:
            for rel in sorted(referenced_repo_paths(read_skill(name))):
                with self.subTest(skill=name, path=rel):
                    self.assertTrue((ROOT / rel).exists(),
                                    f"{name} 引用了不存在的路径：{rel}")

    def test_release_skill_states_the_real_authority(self):
        """版本权威必须是 iss 的 MyAppVersion，且必须警告别沿用 mrrc_modern 的习惯。"""
        text = read_skill("mrrc-release")
        self.assertIn("packaging/windows/MRRC.iss", text)
        self.assertIn("MyAppVersion", text)
        self.assertIn("mrrc_modern", text)

    def test_release_skill_uses_the_checker(self):
        text = read_skill("mrrc-release")
        self.assertIn("dev_tools/release_check.py", text)
        self.assertIn("--strict", text)

    def test_release_skill_demands_explicit_requires(self):
        """热修包的 requires 默认值是陷阱，技能必须点名。"""
        text = read_skill("mrrc-release")
        self.assertIn("--requires", text)
        self.assertIn("6.0.3", text)

    def test_release_skill_covers_the_hotfix_publish_step(self):
        """静默失败的那一步：把补丁放到站点。"""
        text = read_skill("mrrc-release")
        self.assertIn("dist/hotfix", text)
        self.assertIn("website/downloads", text)
        self.assertIn("patch.json", text)

    def test_release_skill_records_the_site_must_be_in_git(self):
        """rsync --delete 会清掉没入库的站点文件（2026-09-16 真实事故）。"""
        text = read_skill("mrrc-release")
        self.assertIn("rsync --delete", text)
        self.assertIn("previous", text)

    def test_release_skill_records_the_tmp_size_trap(self):
        text = read_skill("mrrc-release")
        self.assertIn("454 MB tmpfs", text)

    def test_release_skill_points_at_the_hotfixable_file_table(self):
        """决定“发版还是热修”的依据表必须被指名。"""
        text = read_skill("mrrc-release")
        self.assertIn("release-process.md", text)

    def test_release_skill_requires_server_side_hash_check(self):
        text = read_skill("mrrc-release")
        self.assertIn("sha256sum", text)
        self.assertIn("installer.sha256", text)

    def test_windows_skill_names_the_real_gate_script(self):
        text = read_skill("windows-installer")
        self.assertIn("packaging/windows/build.ps1", text)
        self.assertIn("_APP_MODULES", text)

    def test_windows_skill_demands_artifact_proof(self):
        """退出码不是证据——技能必须教人去认产物。"""
        text = read_skill("windows-installer")
        self.assertIn("Get-FileHash", text)
        self.assertIn("version.txt", text)
        self.assertIn("CArchiveReader", text)


class SkillSyncTests(unittest.TestCase):
    def test_sync_script_targets_the_skills_dir(self):
        text = (ROOT / "dev_tools" / "sync_skills.sh").read_text(encoding="utf-8")
        self.assertIn(".pi/skills", text)
        self.assertIn("~/.pi", text.replace("${HOME}", "~"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_release_skills -v`
Expected: `SkillFactTests.test_referenced_repo_paths_exist` 等 FAIL —— 先确认它**能**失败（比如临时把技能里某个路径写错），再往下走。若一次就全绿，说明校验逻辑没生效，回头检查 `referenced_repo_paths`。

- [ ] **Step 3: 跑测试确认通过**

Run: `python3 -m unittest tests.test_release_skills -v`
Expected: 全部 PASS

- [ ] **Step 4: 接线 AGENTS.md**

在 `AGENTS.md` 的「## Existing Guidance」**之前**插入：

```markdown
## 发布技能
- `.pi/skills/mrrc-release/` —— 发版全链路：版本权威链（`packaging/windows/MRRC.iss` 的
  `MyAppVersion`，**不是** CHANGELOG 顶条，与 `../mrrc_modern` 相反）、`./dev_tools/release_windows.sh`
  一条命令发版、热修通道下发（`--requires` 必须显式传；漏了 `cp dist/hotfix/* website/downloads/`
  会静默失败）、发版验收表。
- `.pi/skills/windows-installer/` —— Win11 KVM VM 上的构建门禁、产物取证（别信退出码）、
  `_APP_MODULES` 与热修覆盖面、PowerShell 5.1 / GBK / OOM / job object 等陷阱。
- 两者都由 `tests/test_release_skills.py` 守着（frontmatter 文风 + 正文引用的仓库路径必须存在），
  改动后用 `./dev_tools/sync_skills.sh` 同步到 `~/.pi/agent/skills` 与 `~/.agents/skills`。
- `macos-installer` 技能待 P3（macOS 打包链）落地后补，那时才有经过实战的 gotcha 可写。
```

- [ ] **Step 5: 全量回归**

Run: `python3 -m unittest discover -s tests -v`
Expected: 全部 PASS

- [ ] **Step 6: 同步到全局目录**

Run: `./dev_tools/sync_skills.sh`
Expected: 输出里出现 `→ mrrc-release 已同步` 与 `→ windows-installer 已同步`；
末尾 `ls -1 "$DEST"` 列出 `mrrc-release`、`windows-installer`（以及原有的
`antenna-sweep`、`mrrc-product-support`）。

- [ ] **Step 7: 提交**

```bash
git add tests/test_release_skills.py AGENTS.md
git commit -m "test(skills): 发布技能一致性体检 + AGENTS.md 注册"
```

---

## 验收

P2 完成时：

```bash
python3 -m unittest tests.test_release_skills -v
python3 -m unittest discover -s tests -p "test_release_artifacts.py" -v
./dev_tools/sync_skills.sh
```

三条都干净，且 `~/.pi/agent/skills/mrrc-release/SKILL.md` 与
`~/.agents/skills/windows-installer/SKILL.md` 存在。

## 与 spec 的对应

| spec 章节 | 本计划任务 |
|---|---|
| §5 技能 `mrrc-release` | T1 |
| §5 技能 `windows-installer` | T2 |
| §5 技能 `macos-installer` | 推迟到 P3（见「与 spec 的偏离」） |
| §5 AGENTS.md 接线 | T4 Step 4 |
| §7 P2 完成判据 | 验收节 |
| —（新增） | T3 源码包私钥排除 |

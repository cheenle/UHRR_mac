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
| `packaging/pyinstaller/mrrc_server.spec` 的 `_APP_MODULES` 里的模块 | ✅ | 热修 |
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

### 改版本号：先分“当前声明”与“历史事实”

V6.2.0 发版实测：全仓 `6.1.18` 有 **108 处**，而规则表只管 17 处。剩下的里面
**一大批是历史事实，改了就成了假话**：

| 类型 | 例子 | 处置 |
| --- | --- | --- |
| 当前版本声明 | hero 徽章、页脚、`stat-value`、文档页眉“当前版本”、下载按钮 | **跟着升** |
| 能力引入版本 | “rigctld now starts automatically (V6.1.18)”、“AI 分诊（V6.1.18 起）” | **不改** |
| 能力门槛 | “Already installed (V6.1.18 or newer)?”（只有该版以后才有一键升级） | **不改** |
| 验证发生的版本 | “validated end-to-end … in V6.1.18” | **不改** |
| 用户上报版本 / 答复卡检索键 | `website/answers/` 的 `data-keys`、“上报版本 6.1.18” | **不改** |
| 缺陷影响范围 | RC-003 的“影响版本：V6.1.18 及之前” | **不改** |
| 回顾文 / 计划 / 规格 / 技能示例 | retrospective、“已装 6.1.18 → 热修 6.1.19” | **不改** |

做法：**逐行断言的白名单脚本**（每条先验证“该行号上命中期望文本”且“版本号在该行只出现 1 次”，
任一不中就整体中止不落盘），**绝不 `sed -i` 全仓替换**。写完把白名单与“故意不改”清单
一起给人看一遍。发完就把脚本删掉：行号写死的东西下次必然失准，真正的审计轨迹是
 git diff + CHANGELOG + 规则表的 `why` 字段。

补规则时注意 `release_check.py` 自带的**反锚定守卫**（`_has_anchor`）：捕获组之前去掉正则元字符后
必须还剩 `0123456789. \tVv` 之外的字符。所以 `V([0-9.]+) · GPLv3 License` 会被拒（前缀只有 `V`），
要写成 `^\s*V([0-9.]+) · GPLv3 License`（行首锚定 + 特征后缀）。

### 大文件改写别用编辑工具：异步格式化器会整文件重排，甚至会损坏内容

编辑工具保存后，格式化器是**异步**跑的 —— 刚改完量 `git diff --numstat` 会看到“干净”的小数字，
过一会文件才变成几百行。V6.2.0 实测：

| 文件 | 我实际改了几处 | numstat 变成 |
| --- | --- | --- |
| `website/index.html` | 5 | **659 增 / 354 删** |
| `website/zh/index.html` | 5 | **531 增 / 300 删** |
| `README_CN.md` / `README_en.md` | 各 3 | 39/9、31/9 |
| `CHANGELOG.md`（2400 行） | 47 行 | 393/29，其中 **173 行在历史条目里** |

两类后果，第二类才是真危险的：

1. **打断治理规则的锚点**：`<span class="stat-value">V6.2.0</span` 的闭合 `>` 被挑到下一行、
   `section-title` 的文本被折行 ⇒ `release_check.py` 报 `pattern 无匹配（锚点可能已被改写）`。
2. **改坏内容**（markdownlint 自动修复干的，不是人干的）：
   - 裸 URL 被加尖括号，**把全角冒号一起包进去**：`部署在 www.vlsc.net：` → `部署在 <www.vlsc.net：>`
     ⇒ 渲染出来是个坏链接；
   - HTML 实体被改了一位：音量图标 `&#x1F50A;`（🔊）→ `&#x1F60A;`（😊）。

处置：

- **大 `.md` / `.html` 的外科手术式修改走脚本**（整串精确替换 + 命中次数断言 + 未命中整体中止），
  不走编辑工具。外部写入不触发格式化器（已实测）。
- 已经被重排的文件：`git checkout --` 还原，再用脚本重做。
- **判据不是“改完马上量”，而是“等一会再量”**，并用 `release_check.py` 复核锚点还在。
- 历史段被格式化器污染时，**先证明那里没有真实内容改动再还原**：把两边都规范化
  （去空行 / `*`→`-` / 表格分隔行归一 / 解掉自动链接 / 压缩空白）后逐条比：
  实测两边各 1524 条、完全一致，只剩那 2 处损坏 ⇒ 还原不会丢掉别人的工作。

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
5. **归档必须早于覆盖，否则回退按钮静默装上新版**（V6.2.0 修）：`release_windows.sh` 先
   `cp 新包 website/downloads/MRRC-Setup.exe`，**然后**才把 `MRRC-Setup.exe` 归档成
   `MRRC-Setup-<上一版>.exe` —— 归档到的是刚取回的新包。而 `make_latest_json.py` 是
   **事后**算哈希的，所以 `previous.sha256` 跟那个错文件还对得上：校验全绿，用户点
   【回退到上一版】却装上了新版，没有任何报错。修法：归档移到覆盖之前 +
   **已入库的历史归档一律不覆盖**（它是回退入口的唯一凭据）。发版后抽查：
   `previous.sha256` 必须 ≠ `installer.sha256`，两者相等就是又踩了这一条。

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

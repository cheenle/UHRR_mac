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

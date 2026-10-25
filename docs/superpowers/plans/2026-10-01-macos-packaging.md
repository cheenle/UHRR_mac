# macOS 打包链（P3）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 MRRC 做出一条真能用的 macOS 交付链：`packaging/macos/build.sh` 一条命令产出 `.app` + `.dmg`（ad-hoc 签名、可过 Gatekeeper 检查），`macos/launcher.py`（rumps 菜单栏）拉起服务、开浏览器、并在 macOS 上实现**热修通道客户端**——那是 macOS 唯一的修 bug 下发路径。

**Architecture:** 手工装配 `.app`（不用 PyInstaller BUNDLE），布局与签名顺序照搬 `mrrc_modern` 花了 6 个版本调对的方案（数据全进 `Contents/Resources`，`Frameworks` 与 `MacOS/_internal` 两条软链，ad-hoc 逐层签名、不用 `--deep`）。启动器**形态**学 `mrrc_modern`（LSUIElement 菜单栏 + 退出码 42 重启 + `StartupTee`），**逻辑**对着本仓库的 `windows/launcher.py` 与 `config_io`/`ssl_bootstrap`/`patch_overlay`/`upgrade_core` 重写（本仓库是 `MRRC.conf` INI 模型，不是 env-file 模型）。既有在服役代码**零改动**（见「与 spec 的偏离」）。

**Tech Stack:** Bash + `hdiutil`/`codesign`/`spctl`（Xcode CLT）、PyInstaller ×3、Python 3.11 `venv` + `rumps`/`pyobjc-framework-Cocoa`、stdlib `unittest`。

**Spec:** `docs/superpowers/specs/2026-09-30-release-engineering-design.md` §6（P3）、§7（P3 完成判据）、§9

**前置依赖**：P1/P2 已合入 main（`release_check.py`、`tests/test_release_skills.py`、`.pi/skills/{mrrc-release,windows-installer}` 均在位）。

## 与 spec 的偏离（需要你点头）

**偏离 1：`verify_hotfix.py` 不需要改，P3 对既有代码是零改动。**
spec §6.4 判定它"硬编码 `MRRC-Server.exe`（:122）与 `%LOCALAPPDATA%`（:134）"，需要参数化。
出发前逐行核对 `packaging/hotfix/verify_hotfix.py` 的现状：

- 可执行文件是**两段回退**：`app_dir / "MRRC-Server.exe"` → `app_dir / "MRRC-Server"`（:121-123），macOS 产物天然命中第二条；
- 配置有 `--config` 参数（:114），且 `%LOCALAPPDATA%` 只在**没传** `--config` 时用作默认值（:132-137）——构建脚本显式传参即可；
- 覆盖层目录用的是 `cfg.parent / "patch"`（:155，配置相对路径），与 `patch_overlay.py` 的"配置同级 `patch/`"规则一致，macOS 同样成立；
- `load_launcher(repo_root)`（:103-110）import 的是 `windows/launcher.py`，该模块顶层只有跨平台 import（`configparser/hashlib/json/os/secrets/signal/subprocess/sys/threading/time/urllib/webbrowser/zipfile/pathlib` + `config_io` + `ssl_bootstrap`，见 `windows/launcher.py:1-24`），在 macOS 上 exec 无副作用。

结论：**不改它**，比 spec 更保守（在服役的 Windows 验收闸门回归面为零）。Task 5 用实跑证明这条判断，spec §7 里"参数化向后兼容"的判据自动满足。

**偏离 2：`first_run.py` 的实施顺序提到真机验收之前。**
spec §9 把 first_run 排在真机验收（第 6 步）之后。本计划把它放到验收之前（Task 6），避免对同一台 Mac 跑两轮人肉验收。成本若错：first_run 引入的回归会在验收中暴露——与其它代码同等对待，没有额外风险。

**偏离 3：`first_run.py` 的探测逻辑不对照 `mrrc_modern` 照搬。**
`mrrc_modern` 探测的是 FT-710 ASCII CAT / IC-7300 CI-V 两套协议；本仓库的电台链是 `rigctld`/Hamlib（IC-M710，`[HAMLIB] rig_pathname`）。spec 只点名"串口探测（macOS `/dev/cu.*`）"，不指定协议。本计划实现为：枚举 `/dev/cu.*`（排除蓝牙/debug-console）→ 把首选候选写进 `[HAMLIB] rig_pathname`（仅当当前值为空或模板占位值时），不做协议握手。

---

## Global Constraints

- **版本权威 = `packaging/windows/MRRC.iss` 的 `MyAppVersion`**（与 `../mrrc_modern` 相反：那边是 CHANGELOG 顶条小写 `## [v…]`）。`build.sh` 只能用
  `grep -oE 'MyAppVersion "[^"]+"' packaging/windows/MRRC.iss` 取版本，**绝不可**抄 mm 的 CHANGELOG regex（本仓库 CHANGELOG 是大写 `## [V6.1.18]`，小写模式匹配不到会 abort）。
- **`version.txt` 内容是不带 `v` 的裸三段**（`6.1.18`），与 Windows/树莓派一致；macOS 里它落在 `Contents/Resources/version.txt`（codesign 不许数据留在 `Contents/MacOS`），**读取必须走 `runtime_path("version.txt")`**。
- **两个软链与签名顺序是硬约束**（改动=重复历史事故）：
  `Contents/Frameworks -> Resources`、`Contents/MacOS/_internal -> ../Resources`；
  数据（`macos/`、`memory_channels.json`、`version.txt`、`vendor/`）全部移到 `Contents/Resources/`；
  ad-hoc `codesign --sign -` 先 `*.dylib`/`*.so`、再三个可执行文件、最后根 bundle；**不用 `--deep`**。
- **`Info.plist` 必须有 `NSMicrophoneUsageDescription`**，否则 macOS 静默拒绝麦克风、RX 播放静音且无任何报错。`build.sh` 里要有硬门禁。
- **命名**：`MRRC.app`、可执行 `MRRC-Launcher` / `MRRC-Server`（无 `.exe`）、`CFBundleIdentifier=net.vlsc.mrrc`、DMG `MRRC-<版本>-arm64.dmg`、`-volname "MRRC"`。
- **端口默认 8877**（`windows/launcher.py:52` 的 `DEFAULT_PORT`）；用户数据目录 `~/Library/Application Support/MRRC`（与 Windows 的 `%LOCALAPPDATA%\MRRC` 对齐）。
- **热修客户端语义必须与 `windows/launcher.py:173-217` 逐条一致**：`latest` 必须 **>** 本机版本；`requires` 非空时本机必须 **≥** `requires`；`applied.json` 去重；SHA-256 不符即放弃；HTTP 404 静默；任何失败只警告、不阻断启动。
- **不改** `MRRC` 主脚本、`windows/launcher.py`、`packaging/hotfix/verify_hotfix.py`、`patch_overlay.py`、`config_io.py`、`ssl_bootstrap.py`、既有 spec。
- **技能文风**沿用 mrrc 房规（见 `.pi/skills/mrrc-release/SKILL.md`）：中文 `description` 以"时使用。"收尾、`license: GPL-3.0`、`metadata.repo: HAM/mrrc`；正文里的仓库路径会被 `tests/test_release_skills.py` 校验。
- **venv 一律用绝对路径解释器**（`venv/bin/python3`），**不要** `source venv/bin/activate`（本仓库 venv 实测待验证，见 Task 1）。

## Review Focus（P3 最容易坏的六件事）

1. **`version.txt` 读取路径**：macOS 的 launcher 若按 `app_dir()/version.txt` 直读（Windows 的写法），因为文件在 `Resources/` 会永远读不到 → 版本判定 `0.0.0` → 已装版本 < 任何热修 `latest` → **反复重放同一个补丁**。必须 `runtime_path("version.txt")`。→ Task 3 测试 + Task 5 集成验证。
2. **数据留在 `Contents/MacOS` 导致 codesign"假成功"**：根签名失败被吞掉时 `_CodeSignature` 不会写、Gatekeeper 报"已损坏"——`mrrc_modern` 每个版本中招到 v1.18.0。→ Task 5 的 `codesign --verify` + `spctl` 硬门禁与断言。
3. **缺 `NSMicrophoneUsageDescription`** → RX 静默无声。→ Task 2 测试 + Task 5 build.sh 硬门禁。
4. **热修客户端语义漂移**（漏 `requires` 门禁、漏 `applied.json` 去重、SHA 校验写错）→ "假装修好了"/补丁无限重放。→ Task 3 的逐条测试。
5. **ad-hoc 签名用 `--deep`、DMG 用 `create-dmg`** → 嵌套 `.dist-info` 签名失败/环境依赖。→ Task 5 静态守卫测试。
6. **`first_run` 覆盖用户手改的 `rig_pathname`** → 现场能连的电台配置被自动探测改坏。→ Task 6 只在空/占位值时写。

---

### Task 1: 环境前提（rumps/PyObjC/PyInstaller 在 venv 实测）

**Files:**
- Create: `packaging/macos/requirements-build.txt`

**Interfaces:**
- Produces: `venv/bin/python3` 可 `import rumps`、可 `import PyInstaller`；`packaging/macos/requirements-build.txt` 供 Task 5 文档化复现。

- [ ] **Step 1: 确认 venv 解释器与依赖基线**

```bash
cd /Users/cheenle/HAM/mrrc
venv/bin/python3 -V                    # 期望 3.11.x
venv/bin/python3 -c "import PyInstaller, serial, tornado; print('base ok')"
venv/bin/python3 -c "import pyaudio; print('pyaudio ok')" || brew install portaudio
```

Expected: 打印 `base ok`；`pyaudio` 缺失时先 `brew install portaudio` 再 `venv/bin/python3 -m pip install pyaudio`（spec §6.5）。缺 `PyInstaller` 时：`venv/bin/python3 -m pip install pyinstaller`。

- [ ] **Step 2: 安装 rumps / PyObjC（spec §8 的第一风险项）**

```bash
venv/bin/python3 -m pip install rumps pyobjc-framework-Cocoa
venv/bin/python3 -c "import rumps, objc, AppKit; print('rumps ok')"
```

Expected: 打印 `rumps ok`。**装不上就停下**（回退方案"无 GUI 启动器"需要重新拍板，spec §8）。

- [ ] **Step 3: 写 requirements-build.txt**

```
# macOS 构建专用依赖（运行依赖见仓库根 requirements.txt）
-r ../../requirements.txt
pyinstaller
rumps
pyobjc-framework-Cocoa
```

- [ ] **Step 4: 建失败先行的测试文件骨架**

创建 `tests/test_macos_launcher.py`：

```python
"""macOS 启动器（macos/launcher.py）的可测逻辑测试。

在非 macOS 主机上也能跑：launcher 对 rumps 缺失有 stub（照搬 mrrc_modern 的做法），
只有真正需要 AppKit 的行为才 skip。
"""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class VenvToolchainTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "darwin", "macOS 专用工具链")
    def test_rumps_is_importable(self):
        import rumps  # noqa: F401


if __name__ == "__main__":
    unittest.main()
```

Run: `venv/bin/python3 -m unittest tests.test_macos_launcher -v`
Expected: PASS（1 个测试；非 macOS 上 SKIP）。

- [ ] **Step 5: Commit**

```bash
git add packaging/macos/requirements-build.txt tests/test_macos_launcher.py
git commit -m "build(macos): 构建依赖清单 + 启动器测试骨架"
```

---

### Task 2: `packaging/macos/Info.plist` + `macos/MRRC.conf.template` + 静态守卫

**Files:**
- Create: `packaging/macos/Info.plist`
- Create: `macos/MRRC.conf.template`
- Test: `tests/test_release_artifacts.py`（追加 `MacPackagingTests`）

**Interfaces:**
- Consumes: 无
- Produces: `Info.plist`（`__VERSION__` 占位符由 build.sh `sed` 注入；`CFBundleExecutable=MRRC-Launcher`）；
  `macos/MRRC.conf.template`（`str.format` 占位符 `{certfile}` `{keyfile}` `{db_users_file}` `{log_file}`，供 Task 3 的 `ensure_config` 使用）。

- [ ] **Step 1: 写失败测试**

在 `tests/test_release_artifacts.py` 的 `if __name__ == "__main__":` 之前追加：

```python
class MacPackagingTests(unittest.TestCase):
    """macOS 打包链的静态守卫（build.sh / Info.plist / 配置模板）。

    这些文件是历史事故的沉淀（"已损坏"签名、RX 静默无声、版本文件读不到），
    让它们能被机器检查而不是靠记忆。
    """

    def _text(self, rel):
        return (rc.ROOT / rel).read_text(encoding="utf-8")

    def test_info_plist_has_microphone_reason(self):
        """缺 NSMicrophoneUsageDescription = macOS 静默拒绝麦克风（RX 无声）。"""
        text = self._text("packaging/macos/Info.plist")
        self.assertIn("NSMicrophoneUsageDescription", text)
        self.assertIn("__VERSION__", text, "版本必须由 build.sh 注入，不许写死")
        self.assertIn("<string>MRRC-Launcher</string>", text)
        self.assertIn("net.vlsc.mrrc", text)
        self.assertIn("LSUIElement", text)

    def test_config_template_is_mac_flavored(self):
        text = self._text("macos/MRRC.conf.template")
        self.assertIn("[SERVER]", text)
        self.assertIn("port = 8877", text)
        self.assertIn("{certfile}", text)
        self.assertIn("{keyfile}", text)
        self.assertIn("{db_users_file}", text)
        # Windows 专属的 hostapi 优先级不属于 mac 模板（CoreAudio 只有一个主机 API）
        self.assertNotIn("hostapi_preference", text)

    def test_build_script_uses_iss_version_and_guards(self):
        text = self._text("packaging/macos/build.sh")
        self.assertIn("MyAppVersion", text, "版本只能来自 MRRC.iss")
        self.assertNotIn("## [v", text, "不许沿用 mm 的 CHANGELOG 小写版本 regex")
        self.assertIn("NSMicrophoneUsageDescription", text, "必须保留硬门禁")
        self.assertIn("version.txt", text)
        self.assertIn("hdiutil", text)
        self.assertNotIn("create-dmg", text)
        self.assertNotIn("codesign --deep", text, "ad-hoc 签名绝不用 --deep")

    def test_build_script_builds_the_symlink_layout(self):
        text = self._text("packaging/macos/build.sh")
        self.assertIn("ln -sfn Resources", text)
        self.assertIn("ln -sfn ../Resources", text)
        self.assertIn("is not a symlink", text)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_release_artifacts.MacPackagingTests -v`
Expected: ERROR/FAIL —— `FileNotFoundError: packaging/macos/Info.plist`

- [ ] **Step 3: 写 `packaging/macos/Info.plist`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>MRRC</string>
    <key>CFBundleDisplayName</key>
    <string>MRRC</string>
    <key>CFBundleIdentifier</key>
    <string>net.vlsc.mrrc</string>
    <key>CFBundleShortVersionString</key>
    <string>__VERSION__</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>MRRC-Launcher</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <!-- 后台菜单栏应用：无 Dock 图标、无主菜单栏。 -->
    <key>LSUIElement</key>
    <true/>
    <!-- 音频输入（电台的 USB 声卡）需要麦克风 TCC 权限。
         缺这个键 macOS 会拒绝授权（kTCCServiceMicrophone），CoreAudio 随后
         "成功"打开流但填零：RX 静音、峰值 0.0%，任何日志都没有报错
         （2026-09-18 实测事故）。 -->
    <key>NSMicrophoneUsageDescription</key>
    <string>MRRC 需要访问音频输入设备（电台的 USB 声卡），以便把接收到的电台音频转发到浏览器。
MRRC needs audio input access (the radio's USB sound card) to stream received radio audio to the browser.</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSMultipleInstancesProhibited</key>
    <true/>
</dict>
</plist>
```

- [ ] **Step 4: 写 `macos/MRRC.conf.template`**

以 `windows/MRRC.conf.template` 为底，做四处 mac 化改动（其余段落原样保留）：

1. `[AUDIO]` 删除 `hostapi_preference` 行（CoreAudio 单一主机 API），设备名保持空串让服务器自动枚举；
2. `[HAMLIB] rig_pathname =` 置空（首启由 `first_run` 探测 `/dev/cu.*`，见 Task 6）；`rig_model`/`rig_rate`/`stop_bits` 保留 IC-M710 值；
3. `[INSTANCE_SETTINGS]` 注释改写为 mac 口味（保留 `atr1000_proxy_transport = unix`、`instance_unix_socket = /tmp/atr1000_proxy.sock`）；
4. 顶部注释改成"配置位于 ~/Library/Application Support/MRRC/MRRC.conf"。

`{certfile}` / `{keyfile}` / `{db_users_file}` / `{log_file}` 四个占位符保持与 Windows 模板同形（Task 3 的 `ensure_config` 用 `str.format` 注入）。

- [ ] **Step 5: 跑测试确认通过**

Run: `python3 -m unittest tests.test_release_artifacts.MacPackagingTests -v`
Expected: 4 个测试 PASS（`test_build_script_*` 两条此时仍会 FAIL —— 它们要等 Task 5 的 `build.sh`。先只跑三条非脚本的：

```bash
python3 -m unittest \
  tests.test_release_artifacts.MacPackagingTests.test_info_plist_has_microphone_reason \
  tests.test_release_artifacts.MacPackagingTests.test_config_template_is_mac_flavored -v
```

Expected: PASS。`build.sh` 的两条留给 Task 5 转绿。）

- [ ] **Step 6: Commit**

```bash
git add packaging/macos/Info.plist macos/MRRC.conf.template tests/test_release_artifacts.py
git commit -m "feat(macos): Info.plist + MRRC.conf.template（含麦克风用途硬守卫）"
```

---

### Task 3: `macos/launcher.py` 核心逻辑（无 GUI 依赖部分）+ 热修客户端

**Files:**
- Create: `macos/launcher.py`
- Create: `macos/launcher_log.py`
- Test: `tests/test_macos_launcher.py`（追加）
- Port from: `mrrc_modern/macos/launcher.py:95-270`（helpers 形态）、`mrrc_modern/launcher_log.py`（全量）；
  **逻辑对照** `windows/launcher.py:67-217, 220-379, 409-471, 517-527`

**Interfaces:**
- Produces（Task 5/6 与验收依赖的公共符号）：
  `app_dir() -> Path`、`runtime_path(*parts) -> Path`、`user_data_dir() -> Path`、
  `config_path() -> Path`、`patch_dir() -> Path`、`ensure_config() -> Path`、
  `ensure_users() -> tuple[str|None, str|None, bool]`、`ssl_material() -> tuple[Path, Path] | None`、
  `_installed_version() -> str`、`check_for_hotfix(cfg: Path) -> None`、
  `apply_hotfix_pack(zip_path, patch_root) -> list[str]`、`build_command(cfg) -> list[str] | None`、
  `wait_for_server(url, proc, timeout_s=15.0, secure=True) -> bool`、`local_url(port, host, secure=True) -> str`、
  `MRRCApp`（Task 4）、`main() -> int`、`guarded_main() -> int`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_macos_launcher.py` 追加：

```python
import configparser
import json
import tempfile
import urllib.error
import zipfile
from unittest import mock

sys.path.insert(0, str(ROOT / "macos"))
sys.path.insert(0, str(ROOT))

import launcher  # noqa: E402  （macos/launcher.py）


class CorePathTests(unittest.TestCase):
    def test_app_dir_in_source_mode_is_repo_root(self):
        self.assertEqual(launcher.app_dir(), ROOT)

    def test_user_data_dir_is_mac_convention(self):
        with mock.patch.dict(os.environ, {"HOME": "/tmp/fakehome"}):
            self.assertEqual(launcher.user_data_dir(),
                             Path("/tmp/fakehome/Library/Application Support/MRRC"))

    def test_runtime_path_prefers_app_dir_then_internal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "MacOS"
            (root / "_internal").mkdir(parents=True)
            (root / "_internal" / "version.txt").write_text("6.1.18", encoding="utf-8")
            with mock.patch.object(launcher, "app_dir", return_value=root):
                self.assertEqual(launcher.runtime_path("version.txt"),
                                 root / "_internal" / "version.txt")


class ConfigSeedTests(unittest.TestCase):
    def test_ensure_config_formats_template_and_seeds_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with mock.patch.dict(os.environ, {"HOME": str(home)}), \
                 mock.patch.object(launcher.ssl_bootstrap, "ensure_self_signed",
                                   return_value=(home / "c.crt", home / "c.key")):
                (home / "c.crt").write_text("x", encoding="utf-8")
                (home / "c.key").write_text("x", encoding="utf-8")
                cfg = launcher.ensure_config()
            parser = configparser.ConfigParser()
            parser.read(cfg, encoding="utf-8")
            self.assertEqual(parser.get("SERVER", "port"), "8877")
            self.assertEqual(parser.get("SERVER", "certfile"), str(home / "c.crt"))
            self.assertTrue((cfg.parent / "memory_channels.json").is_file())
            self.assertNotIn("{certfile}", cfg.read_text(encoding="utf-8"))


class VersionMarkerTests(unittest.TestCase):
    def test_installed_version_reads_through_runtime_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "MacOS"
            (root / "_internal").mkdir(parents=True)
            (root / "_internal" / "version.txt").write_text("6.1.18\n", encoding="utf-8")
            with mock.patch.object(launcher, "app_dir", return_value=root):
                self.assertEqual(launcher._installed_version(), "6.1.18")


class HotfixClientTests(unittest.TestCase):
    """逐条钉住 windows/launcher.py:173-217 的热修语义。"""

    def _manifest(self, latest="6.1.19", requires="6.1.18", sha="deadbeef", url="https://x/p.zip"):
        return json.dumps({"latest": latest, "requires": requires,
                           "sha256": sha, "url": url, "notes": "t"}).encode()

    def _patch_installed(self, version):
        return mock.patch.object(launcher, "_installed_version", return_value=version)

    def test_newer_hotfix_is_applied_when_sha_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "MRRC.conf"
            cfg.write_text("[SERVER]\nport = 8877\n", encoding="utf-8")
            data = Path(tmp)
            pack = data / "p.zip"
            with zipfile.ZipFile(pack, "w") as z:
                z.writestr("www/x.js", "ok")
            digest = launcher._sha256_file(pack)
            with self._patch_installed("6.1.18"), \
                 mock.patch.object(launcher, "user_data_dir", return_value=data), \
                 mock.patch.object(launcher, "patch_dir", return_value=data / "patch"), \
                 mock.patch.object(launcher, "_hotfix_enabled", return_value=True), \
                 mock.patch("urllib.request.urlopen") as urlopen:
                urlopen.side_effect = [
                    mock.MagicMock(__enter__=lambda s: s, __exit__=lambda *a: False,
                                   read=lambda: self._manifest(sha=digest, url=str(pack))),
                    mock.MagicMock(__enter__=lambda s: s, __exit__=lambda *a: False,
                                   read=lambda: pack.read_bytes()),
                ]
                launcher.check_for_hotfix(cfg)
            self.assertTrue((data / "patch" / "www" / "x.js").is_file())

    def test_requires_gate_blocks_older_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "MRRC.conf"
            cfg.write_text("[SERVER]\nport = 8877\n", encoding="utf-8")
            with self._patch_installed("6.0.3"), \
                 mock.patch.object(launcher, "patch_dir", return_value=Path(tmp) / "patch"), \
                 mock.patch.object(launcher, "_hotfix_enabled", return_value=True), \
                 mock.patch("urllib.request.urlopen") as urlopen:
                urlopen.return_value = mock.MagicMock(
                    __enter__=lambda s: s, __exit__=lambda *a: False,
                    read=lambda: self._manifest())
                launcher.check_for_hotfix(cfg)
            self.assertFalse((Path(tmp) / "patch").exists())

    def test_http_404_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "MRRC.conf"
            cfg.write_text("[SERVER]\nport = 8877\n", encoding="utf-8")
            with self._patch_installed("6.1.18"), \
                 mock.patch.object(launcher, "_hotfix_enabled", return_value=True), \
                 mock.patch("urllib.request.urlopen",
                            side_effect=urllib.error.HTTPError("u", 404, "nf", {}, None)), \
                 mock.patch("builtins.print") as out:
                launcher.check_for_hotfix(cfg)
            self.assertNotIn("[hotfix] 更新检查失败", "".join(str(c) for c in out.call_args_list))

    def test_applied_version_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "MRRC.conf"
            cfg.write_text("[SERVER]\nport = 8877\n", encoding="utf-8")
            patch = Path(tmp) / "patch"
            patch.mkdir()
            (patch / "applied.json").write_text(
                json.dumps([{"version": "6.1.19", "files": []}]), encoding="utf-8")
            with self._patch_installed("6.1.18"), \
                 mock.patch.object(launcher, "patch_dir", return_value=patch), \
                 mock.patch.object(launcher, "_hotfix_enabled", return_value=True), \
                 mock.patch("urllib.request.urlopen") as urlopen:
                urlopen.return_value = mock.MagicMock(
                    __enter__=lambda s: s, __exit__=lambda *a: False,
                    read=lambda: self._manifest())
                launcher.check_for_hotfix(cfg)
            self.assertEqual(urlopen.call_count, 1)   # 只拉了 patch.json，没下 zip
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_macos_launcher -v`
Expected: `ModuleNotFoundError: No module named 'launcher'`

- [ ] **Step 3: 写 `macos/launcher_log.py`**

从 `mrrc_modern/launcher_log.py` **逐行复制**（100 行，类 `StartupTee`：`_rotate`/`start`/`_pump`/`stop`，常量 `DEFAULT_NAME="server-stdout.log"`、`DEFAULT_MAX_BYTES=2MiB`），仅把模块 docstring 里"spec 2026-09-17 §5"的出处改成"移植自 mrrc_modern（RC-001 同源问题：启动期报错只存在于 stdout）"。不要改任何行为。

- [ ] **Step 4: 写 `macos/launcher.py`（本任务的非 GUI 部分）**

模块结构（顺序）与来源：

1. docstring + `from __future__ import annotations`；
2. import（照 `mrrc_modern/macos/launcher.py:17-32`，去掉 `urllib.error` 裸名两行无关内容）；
3. **rumps 缺失 stub**：逐行照搬 `mrrc_modern/macos/launcher.py:34-75`（`_RumpsMissingApp` / `_RumpsMissing`，含"赋类不赋实例"的注释）；
4. 路径接线：照 `windows/launcher.py:22-24` 的做法先
   ```python
   sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # 仓库根
   sys.path.insert(0, str(Path(__file__).resolve().parent))       # macos/（flat import launcher_log/first_run）
   ```
   再 `import config_io` / `import ssl_bootstrap` / `import launcher_log`；
5. 常量：`APP_NAME = "MRRC"`、`DEFAULT_PORT = "8877"`、`PATCH_MANIFEST_URL = "https://www.vlsc.net/mrrc/downloads/patch.json"`、`PATCH_CHECK_TIMEOUT = 10`；
6. 逐行移植 `windows/launcher.py` 的这些函数，改动点如下表：

| 函数（windows/launcher.py 行号） | mac 版改动 |
|---|---|
| `app_dir` :67-70 | 原样（frozen 时 `sys.executable` 的父目录 = `Contents/MacOS`） |
| `user_data_dir` :73-77 | `HOME` → `~/Library/Application Support/MRRC` |
| `patch_dir` :80-82 | 原样（`user_data_dir()/patch`，与 `patch_overlay` 的 cfg 同级规则重合） |
| `_sha256_file` :85-90 | 原样 |
| `_hotfix_enabled` :93-105 | 原样（`config_io.read_config` 跨平台） |
| `_installed_version` :108-114 | **改为 `runtime_path("version.txt")` 读取**（Windows 直读 `app_dir()`；macOS 文件在 `Resources/`） |
| `_version_tuple` :117-122 | 原样 |
| `apply_hotfix_pack` :125-155 | 原样（含 `applied.json` 记录） |
| `applied_hotfix_versions` :158-170 | 原样 |
| `check_for_hotfix` :173-217 | 原样（URL/超时/语义一字不改） |
| `config_path` :220-221 | 原样（`user_data_dir()/MRRC.conf`） |
| `default_config_path` :228-229 | 改为 `runtime_path("macos", "MRRC.conf.template")`（不是 `app_dir()/windows/...`） |
| `_copy_seed`/`_seed_candidates` :232-246 | `_seed_candidates` 改为 `(app_dir()/f, app_dir()/"_internal"/f)`（经软链命中 Resources） |
| `ensure_config` :249-275 | **签名改为 `ensure_config() -> Path`**（内部先 `ssl_material()` 拿证书）：模板 `str.format(certfile=…, keyfile=…, db_users_file=…, log_file=…)`；文本编码走 `config_io.read_text`/`write_text`（GBK 迁移）；种子文件只放 `memory_channels.json`（与 Windows 一致；`MRRC_users.db` 由 `ensure_users()` 生成/校验），**不改写用户已有文件** |
| `_read_accounts`/`ensure_users` :278-306 | 原样（文本用户文件 + `secrets.token_urlsafe(12)`；account 常量沿用 `DEFAULT_LOGIN_USER="admin"`） |
| `ssl_material` :376-379 | 原样（`ssl_bootstrap.ensure_self_signed(user_data_dir()/certs)`） |
| `_read_config_port_host` :409-416 | 原样 |
| `local_url` :419-427 | 原样 |
| `server_executable` :430-437 | **改为 `app_dir()/"MRRC-Server"`**；源码模式回退 `app_dir()/"MRRC"`（不是 `MRRC-Server.exe`） |
| `wait_for_server` :440-462 | 原样（探针用 `url + "/"`） |
| `build_command` :465-471 | **改为恒返回 `[str(server), str(cfg)]`**（mac 无 `.exe`；源码模式返回 `[sys.executable, str(server), str(cfg)]`） |
| `stop_process` :517-527 | 原样（SIGTERM → 5s → kill） |
| `runtime_path`（新） | 从 `mrrc_modern/macos/launcher.py:256-270` 逐行移植（`app_dir()` → `app_dir()/"_internal"` 两级探测） |
| `report_fatal`/`guarded_main` | 从 `mrrc_modern/macos/launcher.py:492-534` 移植（写 `launcher.log` + `rumps.alert`），`APP_NAME` 用 MRRC |

另加一个 mac 专用小函数（升级只读展示，spec D3）：

```python
def check_for_upgrade_notice() -> str | None:
    """只读地查一次升级清单，返回新版本号（无新版本/失败一律 None）。

    macOS 启动器不提供安装入口（D3）：菜单最多给一个"打开下载页"。
    """
    try:
        import upgrade_core
        manifest, _reason = upgrade_core.fetch_manifest(timeout=8)   # 返回 (manifest|None, 失败原因)
        latest = str((manifest or {}).get("latest") or "").strip()
        if latest and upgrade_core.version_tuple(latest) > upgrade_core.version_tuple(_installed_version()):
            return latest
    except Exception:
        pass
    return None
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python3 -m unittest tests.test_macos_launcher -v`
Expected: 全部 PASS（CorePath/ConfigSeed/VersionMarker/HotfixClient/VenvToolchain）。

- [ ] **Step 6: Commit**

```bash
git add macos/launcher.py macos/launcher_log.py tests/test_macos_launcher.py
git commit -m "feat(macos): 启动器核心逻辑 + 热修客户端（语义与 Windows 版逐条对齐）"
```

---

### Task 4: rumps 菜单栏层（`MRRCApp`）

**Files:**
- Modify: `macos/launcher.py`（追加 `MRRCApp` 类与 `main()`）
- Test: `tests/test_macos_launcher.py`（追加不依赖 AppKit 的部分）

**Interfaces:**
- Consumes: Task 3 的全部符号
- Produces: `MRRCApp`、`main()`、`guarded_main()`（Task 5 的 spec 入口 `if __name__ == "__main__": raise SystemExit(guarded_main())`）

- [ ] **Step 1: 写失败测试（菜单项与重启语义）**

```python
class AppShellTests(unittest.TestCase):
    def test_menu_items_match_spec(self):
        """菜单至少要有 Open/Edit/Show Password/Restart/Quit 五项（mm 的形态）。"""
        from pathlib import Path
        text = (ROOT / "macos" / "launcher.py").read_text(encoding="utf-8")
        for item in ("Open Web UI", "Edit Configuration…", "Show Password…",
                     "Restart Server", "Quit MRRC"):
            self.assertIn(item, text)

    def test_exit_code_42_triggers_restart(self):
        text = (ROOT / "macos" / "launcher.py").read_text(encoding="utf-8")
        self.assertIn("rc == 42", text)

    def test_launcher_does_not_install_upgrades(self):
        """D3：macOS 启动器不提供升级入口（只能打开下载页）。"""
        text = (ROOT / "macos" / "launcher.py").read_text(encoding="utf-8")
        for forbidden in ("run_upgrade", "_exit_for_upgrade", "ShellExecute"):
            self.assertNotIn(forbidden, text)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_macos_launcher.AppShellTests -v`
Expected: FAIL（`AssertionError: 'Open Web UI' not found…`）

- [ ] **Step 3: 实现 `MRRCApp` 与 `main()`**

形态照搬 `mrrc_modern/macos/launcher.py:297-490`（`class MRRCModernApp(rumps.App)`、`start_server`、`launch_and_open`、`_monitor_loop`、菜单回调、`main()`、SIGTERM `_on_sigterm`、`atexit.register(stop_process, app.proc)`），改动点：

- 类名 `MRRCApp`；标题 `f"{APP_NAME} :{port}"`；
- 菜单加一项（D3 的只读展示）：
  ```python
  @rumps.clicked("Check for Updates…")
  def on_check_updates(self, _):
      latest = check_for_upgrade_notice()
      if latest:
          rumps.alert(title=APP_NAME,
                      message=f"发现新版本 {latest}。\n"
                              "macOS 版请到下载页手动安装（本应用不自动升级）。")
      else:
          rumps.notification(APP_NAME, "已是最新", f"当前版本 {_installed_version()}")
  ```
- `start_server()` 里：配置路径通过 `build_command(config_path())` 进入 argv（本仓库服务端只认 `sys.argv[1]`，**没有** `MRRC_CONFIG_FILE` 这种环境变量，别发明）；`cwd=str(app_dir())`；`self.tee = launcher_log.StartupTee(user_data_dir() / "logs")`；
- **启动前调用 `check_for_hotfix(config_path())`**（顺序：`ensure_config` → `ensure_users` → `check_for_hotfix` → 起服务；与 Windows 启动器 `main()` 的顺序一致，实施时对照 `windows/launcher.py:840-938` 的头部顺序）；
- 退出码 42 自动重启的 `_monitor_loop` 原样。

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_macos_launcher -v`
Expected: 全部 PASS。

- [ ] **Step 5: 源码模式冒烟（不打包，先证明能跑）**

```bash
cd /Users/cheenle/HAM/mrrc
HOME=/tmp/mrrc-mac-smoke venv/bin/python3 -c "
import sys; sys.path[:0] = ['.', 'macos']
import launcher
cfg = launcher.ensure_config()
print('config:', cfg)
print('command:', launcher.build_command(cfg))
"
```

Expected: 打印的 command 形如 `['<venv>/bin/python3', '<repo>/MRRC', '<tmp-home>/Library/Application Support/MRRC/MRRC.conf']`
（源码模式下 server 回退是 `app_dir()/"MRRC"`）。**不要**直接跑 `macos/launcher.py`——rumps 会真的拉起菜单栏，
那是人肉验收（Task 7）的事。

- [ ] **Step 6: Commit**

```bash
git add macos/launcher.py tests/test_macos_launcher.py
git commit -m "feat(macos): rumps 菜单栏层（含退出码 42 重启与只读升级提示）"
```

---

### Task 5: `packaging/macos/mrrc_launcher.spec` + `packaging/macos/build.sh` + 出包

**Files:**
- Create: `packaging/macos/mrrc_launcher.spec`
- Create: `packaging/macos/build.sh`
- Test: `tests/test_release_artifacts.py`（Task 2 里写好的两条 `test_build_script_*` 转绿）

**Interfaces:**
- Consumes: `macos/launcher.py`（Task 4）、`packaging/pyinstaller/{mrrc_server,atr1000_proxy}.spec`（现成，darwin 分支已有）、`packaging/macos/Info.plist`（Task 2）
- Produces: `dist/macos/MRRC.app`、`dist/macos/MRRC-<版本>-arm64.dmg`

- [ ] **Step 1: 跑失败测试确认仍红**

Run: `python3 -m unittest tests.test_release_artifacts.MacPackagingTests -v`
Expected: 两条 `test_build_script_*` FAIL（`FileNotFoundError: packaging/macos/build.sh`）。

- [ ] **Step 2: 写 `packaging/macos/mrrc_launcher.spec`**

以 `mrrc_modern/packaging/macos/mrrc_modern_launcher.spec` 为底，改动：

- `Analysis([str(ROOT / "macos" / "launcher.py")], pathex=[str(ROOT), str(ROOT / "macos")], ...)`；
- `hiddenimports`: 保留 `rumps/objc/AppKit/Foundation/PyObjCTools/ssl_bootstrap/cryptography/serial/serial.tools.list_ports/serial.tools.list_ports_osx`，把 `launcher_log`/`first_run` 改为 `"macos.launcher_log"` 不可行（launcher 用的是 `sys.path` 直接 import）——**保持扁平** `"launcher_log"`、`"first_run"`，靠 `pathex` 的 `macos/` 命中；
- `name="MRRC-Launcher"`、`console=False`；
- 删掉 mm 里未使用的 `VERSION = os.environ.get(...)` 两行（本仓库不靠它）。

- [ ] **Step 3: 写 `packaging/macos/build.sh`**

结构照搬 `mrrc_modern/packaging/macos/build.sh`（同样的步骤注释与顺序），逐段改动：

1. **版本段**（替换 mm 的 CHANGELOG regex）：
   ```bash
   VERSION="$(grep -oE 'MyAppVersion "[^"]+"' packaging/windows/MRRC.iss | head -1 | sed 's/.*"\(.*\)"/\1/')"
   : "${VERSION:?Could not read MyAppVersion from packaging/windows/MRRC.iss}"
   export MRRC_VERSION="$VERSION"
   echo "==> Building MRRC ${VERSION} (arm64) for macOS"
   ```
2. **PYBIN**：`PYBIN="${PYTHON:-$REPO_ROOT/venv/bin/python3}"`，注释写明"不要 source activate"；
3. **Step 0/1/2 门禁**：`py_compile` 用 `$REPO_ROOT/*.py` 全集（与 build.ps1 的语义一致：至少覆盖根模块）；`-m unittest discover -s tests`；`dev_tools/test_config_encoding.py`；FTDI dylib 检查对本仓库**删除**（mrrc 的 FT4222 在 `vendor/ftdi/` 无此树，检查保留会永远告警——改成对 `vendor/wdsp/macos` 的 warn-only 提示）；
4. **Step 3 三个 PyInstaller**：
   ```bash
   "$PYBIN" -m PyInstaller packaging/pyinstaller/mrrc_server.spec \
       --noconfirm --distpath "$PYI_ROOT" --workpath "$BUILD_WORK"
   "$PYBIN" -m PyInstaller packaging/pyinstaller/atr1000_proxy.spec \
       --noconfirm --distpath "$PYI_ROOT" --workpath "$BUILD_WORK"
   "$PYBIN" -m PyInstaller packaging/macos/mrrc_launcher.spec \
       --noconfirm --distpath "$PYI_ROOT" --workpath "$BUILD_WORK"
   ```
5. **Step 4 装配**（mm 的 63-141 行，逐个名字替换）：
   - `APP_BUNDLE="$DIST_ROOT/MRRC.app"`；
   - `sed "s/__VERSION__/${VERSION}/" "$SCRIPT_DIR/Info.plist"` + `grep -q NSMicrophoneUsageDescription || exit 1`（**照抄 mm 的硬门禁与错误文案**）；
   - `cp "$PYI_ROOT/MRRC-Launcher" "$APP_MACOS/"`；`cp -R "$PYI_ROOT/MRRC-Server/." "$APP_MACOS/"`；`cp "$PYI_ROOT/ATR1000-Proxy" "$APP_MACOS/"`（原 mm 的 `scope_pipe` 位置）；
   - `printf '%s\n' "$VERSION" > "$APP_MACOS/version.txt"`（本仓库版本无 `v` 前缀，**不需要** `${VERSION#v}`）；
   - `mkdir -p "$APP_MACOS/macos"; cp macos/MRRC.conf.template "$APP_MACOS/macos/"`（替代 mm 的 default.env）；
   - `cp memory_channels.json "$APP_MACOS/"`（启动器的首个种子；`windows/MRRC.conf.template` **不复制**，mac 用上面的 mac 模板；`MRRC_users.db` 由 `ensure_users()` 在用户目录生成，不需要复制——服务端 spec 自带的 datas 副本不受影响）；
   - data→Resources 迁移循环 + 两条软链 + `[ -L "$APP_MACOS/_internal" ]` 断言：**逐字照抄 mm 的 114-137 行**（含注释），只把文件清单 `for item in macos memory_channels.json version.txt vendor`；
   - pycache 清理照抄。
6. **Step 5 签名**：照抄 mm 的 144-169 行，可执行文件列表换成
   `MRRC-Launcher` / `MRRC-Server` / `ATR1000-Proxy`；保留 `codesign --verify` 与 `spctl -a -t exec … grep -qiE "damaged|invalid signature|not signed at all"` 的 `exit 1`。
7. **Step 6 DMG**：`DMG="$DIST_ROOT/MRRC-${VERSION}-arm64.dmg"`、`-volname "MRRC"`，其余照抄（含 `/Applications` 软链 staging）。
8. **Step 7 校验和**：照抄（`md5 -q` + `shasum -a 256`）。
9. **最后一段：热修闸门**（spec §7 的 P3 硬判据）：用**临时 HOME** 生成配置，对产物跑既有 `verify_hotfix.py`（本计划「偏离 1」：零改动调用）：
   ```bash
   echo "==> Hotfix gate (verify_hotfix.py)"
   VERIFY_HOME="$(mktemp -d)"
   HOME="$VERIFY_HOME" "$PYBIN" - <<PY
   import sys
   sys.path[:0] = ["$REPO_ROOT", "$REPO_ROOT/macos"]
   import launcher
   cfg = launcher.ensure_config()
   launcher.ensure_users()
   print(cfg)
   PY
   HOME="$VERIFY_HOME" "$PYBIN" packaging/hotfix/verify_hotfix.py \
       --app "$APP_MACOS" --repo "$REPO_ROOT" \
       --config "$VERIFY_HOME/Library/Application Support/MRRC/MRRC.conf"
   rm -rf "$VERIFY_HOME"
   ```
   Expected: `✅ 热修通道验收通过`。失败即 build.sh 失败（`set -e`）。

- [ ] **Step 4: 静态守卫转绿**

Run: `python3 -m unittest tests.test_release_artifacts -v`
Expected: 全绿（含 `MacPackagingTests` 四条）。

- [ ] **Step 5: 真跑一次出包**

```bash
chmod +x packaging/macos/build.sh
packaging/macos/build.sh 2>&1 | tee /tmp/mrrc-macos-build.log
```

Expected: 末段打印 `App:` / `DMG:` / `Size:` / `MD5` / `SHA256`；且 Step 8 的 `✅ 热修通道验收通过`。
（中途失败按日志定位；本任务的失败模式与排查写进 Task 8 的技能。）

- [ ] **Step 6: 产物取证（别只信退出码）**

```bash
ls -la dist/macos/MRRC-*.dmg
codesign --verify --verbose=2 dist/macos/MRRC.app
spctl -a -t exec dist/macos/MRRC.app 2>&1 | head -3
test -L dist/macos/MRRC.app/Contents/MacOS/_internal && echo "symlink ok"
test -f dist/macos/MRRC.app/Contents/Resources/version.txt && \
  cat dist/macos/MRRC.app/Contents/Resources/version.txt   # 必须 == MRRC.iss 的 MyAppVersion
```

Expected: `codesign` 无输出（成功）、`spctl` 不含 `damaged`、软链存在、`version.txt` 与 iss 一致。

- [ ] **Step 7: Commit**

```bash
git add packaging/macos/mrrc_launcher.spec packaging/macos/build.sh
git commit -m "feat(macos): build.sh + launcher spec —— 手工装配/软链布局/ad-hoc 签名/热修闸门"
```

---

### Task 6: `macos/first_run.py`（首启自动配置：串口探测 + 配置回写）

**Files:**
- Create: `macos/first_run.py`
- Modify: `macos/launcher.py`（在 `main()` 起服务前调用 `first_run.apply_first_run`）
- Test: `tests/test_macos_launcher.py`（追加）

**Interfaces:**
- Consumes: `config_io.read_config` / `write_config`（`config_io.py:111-132`）
- Produces: `detect_serial_ports(comports=None) -> list[str]`、`apply_first_run(cfg: Path, *, comports=None) -> list[str]`（返回写过的键名列表，便于日志与测试）

- [ ] **Step 1: 写失败测试**

```python
class FirstRunTests(unittest.TestCase):
    class _Port:
        def __init__(self, device, description="", hwid=""):
            self.device, self.description, self.hwid = device, description, hwid

    def test_candidates_prefer_serial_adapters_and_exclude_bluetooth(self):
        ports = [
            self._Port("/dev/cu.Bluetooth-Incoming-Port"),
            self._Port("/dev/cu.debug-console"),
            self._Port("/dev/cu.usbserial-0001", "CP2102 USB to UART", "USB VID:PID=10c4"),
            self._Port("/dev/cu.SLAB_USBtoUART", "CP210x", "USB VID:PID=10c4"),
        ]
        found = first_run.detect_serial_ports(ports)
        self.assertEqual(found[0], "/dev/cu.usbserial-0001")
        self.assertNotIn("/dev/cu.Bluetooth-Incoming-Port", found)

    def test_apply_first_run_fills_only_empty_rig_pathname(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "MRRC.conf"
            cfg.write_text("[HAMLIB]\nrig_pathname =\nrig_model = IC-M710\n",
                           encoding="utf-8")
            ports = [self._Port("/dev/cu.usbserial-0001")]
            written = first_run.apply_first_run(cfg, comports=ports)
            self.assertIn("rig_pathname", written)
            parser = configparser.ConfigParser()
            parser.read(cfg, encoding="utf-8")
            self.assertEqual(parser.get("HAMLIB", "rig_pathname"), "/dev/cu.usbserial-0001")

    def test_apply_first_run_never_overwrites_operator_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "MRRC.conf"
            cfg.write_text("[HAMLIB]\nrig_pathname = /dev/cu.custom\n", encoding="utf-8")
            first_run.apply_first_run(cfg, comports=[self._Port("/dev/cu.other")])
            parser = configparser.ConfigParser()
            parser.read(cfg, encoding="utf-8")
            self.assertEqual(parser.get("HAMLIB", "rig_pathname"), "/dev/cu.custom")
```

（测试文件头部 import 加上 `import first_run`，就近 `sys.path` 插入 `macos/` 已有。）

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_macos_launcher.FirstRunTests -v`
Expected: `ModuleNotFoundError: No module named 'first_run'`

- [ ] **Step 3: 实现 `macos/first_run.py`**

```python
"""首启自动配置（macOS）：把 /dev/cu.* 里最像电台的串口写进 [HAMLIB] rig_pathname。

只导入 stdlib + pyserial（测试与非 mac 主机都能跑）。不做协议握手：
本仓库的电台链是 rigctld/Hamlib，探测协议属于 rigctld 的职责。
"""
from __future__ import annotations

import configparser
import sys
from pathlib import Path

import serial.tools.list_ports

import config_io

_BOGUS_PREFIXES = ("/dev/cu.Bluetooth", "/dev/cu.IRComm", "/dev/cu.debug-console")
_ADAPTER_HINTS = ("cp210", "slab", "usbserial", "usb serial", "usb-serial", "ch340")


def detect_serial_ports(comports=None) -> list[str]:
    """返回候选串口，USB 串口适配器排前，蓝牙/调试口排除。"""
    ports = list(serial.tools.list_ports.comports()) if comports is None else list(comports)
    candidates = [
        p for p in ports
        if p.device.startswith("/dev/cu.") and not p.device.startswith(_BOGUS_PREFIXES)
    ]

    def _key(p) -> tuple[int, str]:
        text = (p.description + " " + p.hwid).lower()
        if any(h in text for h in _ADAPTER_HINTS):
            return (0, p.device)
        return (1, p.device)

    candidates.sort(key=_key)
    return [p.device for p in candidates]


def apply_first_run(cfg: Path, *, comports=None) -> list[str]:
    """把探测到的串口写进 [HAMLIB] rig_pathname（只填空值）。返回写过的键。"""
    ports = detect_serial_ports(comports)
    if not ports:
        return []
    parser = configparser.ConfigParser()
    config_io.read_config(parser, str(cfg))
    if not parser.has_section("HAMLIB"):
        return []
    if parser.get("HAMLIB", "rig_pathname", fallback="").strip():
        return []                                   # 操作员/模板已定，绝不覆盖
    parser.set("HAMLIB", "rig_pathname", ports[0])
    config_io.write_config(parser, str(cfg))
    return ["rig_pathname"]


if __name__ == "__main__":                          # 手动调试入口
    print(apply_first_run(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("MRRC.conf")))
```

- [ ] **Step 4: 接线 launcher**

在 `macos/launcher.py` 的 `main()` 里、`ensure_config`/`ensure_users` 之后调用：

```python
    import first_run                   # macos/ 已在 launcher 顶部进 sys.path（Task 3 Step 4 第 4 条）
    written = first_run.apply_first_run(config_path())
    if written:
        print(f"[first-run] 已写入 {', '.join(written)}")
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python3 -m unittest tests.test_macos_launcher -v`
Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add macos/first_run.py macos/launcher.py tests/test_macos_launcher.py
git commit -m "feat(macos): 首启串口探测（只填空值，绝不覆盖操作员配置）"
```

---

### Task 7: 真机验收（**不可省**，由你执行）

**Files:** 无代码变更；验收记录写入 `.pi/skills/macos-installer/SKILL.md`（Task 8）

**为什么必须人来做**：spec §7 的 P3 判据要求"从 dmg 安装、双击启动、浏览器自动打开、RX 有声"——音频链路（CoreAudio + 电台 USB 声卡）无法在 CI/脚本里验。

- [ ] **Step 1: 安装与启动**

```bash
packaging/macos/build.sh          # 若产物已有则跳过
open dist/macos/MRRC-<版本>-arm64.dmg
# 把 MRRC.app 拖进 /Applications，右键 → 打开（ad-hoc 签名首次会被 Gatekeeper 拦）
```

Expected（逐条记录到技能）：
1. 菜单栏出现 MRRC 图标，无 Dock 图标；
2. 浏览器自动打开 `https://localhost:8877`（自签名告警 → 高级 → 继续）；
3. 用菜单 "Show Password…" 的密码能登录；
4. **RX 有声**（关键：若无声，先查 `NSMicrophoneUsageDescription` 是否在产物里、再查系统设置→隐私与安全性→麦克风）；
5. 退出菜单 → 进程确实退出（`pgrep -f MRRC-Server` 为空）；
6. 菜单 "Restart Server" → 服务重启、页面恢复。

- [ ] **Step 2: 热修端到端（**需要你点头**：会向站点发布一个真实补丁）**

这一步是 spec §7 的硬判据（macOS 无升级通道，热修是唯一修复路径），且**会产生线上副作用**：
`patch.json` 一发布，所有 6.1.18 的 Windows/macOS 装机都会拉到它（补丁内容为惰性探针文件，无行为影响）。
做之前**停下问用户**；得到同意后：

```bash
# 1) 打一个真补丁（内容用惰性探针，不碰任何行为）
printf '/* mac hotfix e2e probe %s */\n' "$(date +%s)" > www/hotfix_e2e_probe.js
python3 packaging/hotfix/make_hotfix.py \
    --version 6.1.19 --requires 6.1.18 \
    --notes "macOS 热修通道端到端验收（惰性探针）" \
    www/hotfix_e2e_probe.js
cp dist/hotfix/* website/downloads/ && ./deploy_website.sh
# 2) 线上复核（patch.json 可下载且 latest 正确）
curl -sI https://www.vlsc.net/mrrc/downloads/patch.json | head -1
curl -s https://www.vlsc.net/mrrc/downloads/patch.json
# 3) Mac 上重启 MRRC.app → 启动器应打印/记录 [hotfix] 发现热补丁 6.1.19 → 已应用
grep -r "hotfix" ~/Library/Application\ Support/MRRC/logs/ | tail -5
ls ~/Library/Application\ Support/MRRC/patch/www/            # 探针文件应出现
```

Expected: 启动器日志出现"发现热补丁 6.1.19 … 已应用"，`patch/applied.json` 记录版本；
重启页面后 `https://localhost:8877/hotfix_e2e_probe.js` 返回探针内容。

（验收后清理：删除 `www/hotfix_e2e_probe.js`，并把 `patch.json`/`hotfix-*.zip` 从
`website/downloads/` 移除后重新 `./deploy_website.sh` —— **这一步也要问用户**；
用户若同意"保留惰性探针补丁"则跳过清理。）

- [ ] **Step 3: 记录验收结果**

把每条的实测结果（含失败与处置）写进 Task 8 的技能"真机验收清单"一节；有回归则回到对应任务修复后重跑。

- [ ] **Step 4: Commit（如有验收期间的修复）**

---

### Task 8: `macos-installer` 技能 + AGENTS.md/技能测试接线

**Files:**
- Create: `.pi/skills/macos-installer/SKILL.md`
- Modify: `tests/test_release_skills.py`（`RELEASE_SKILLS` 增加 `"macos-installer"`）
- Modify: `AGENTS.md`（发布技能一节：删掉"待 P3"，写实际内容）
- Modify: `.pi/skills/mrrc-release/SKILL.md`（"改 macOS 打包 → `macos-installer`（P3 后可用）" → 去掉"（P3 后可用）"）

**Interfaces:**
- Consumes: Task 5 的构建/取证行号、Task 7 的验收结果
- Produces: 可在 `~/.pi/agent/skills` 与 `~/.agents/skills` 同步的第三条发布技能

- [ ] **Step 1: 写失败测试（把技能登记进体检）**

`tests/test_release_skills.py`：

```python
RELEASE_SKILLS = ("mrrc-release", "windows-installer", "macos-installer")
```

Run: `python3 -m unittest tests.test_release_skills -v`
Expected: FAIL（`macos-installer/SKILL.md` 不存在）。

- [ ] **Step 2: 写 `.pi/skills/macos-installer/SKILL.md`**

frontmatter 照房规（`name: macos-installer`、中文 description 以"时使用。"收尾、`license: GPL-3.0`、`metadata.repo: HAM/mrrc`）。正文结构（**每条 gotcha 都要写清"症状 → 原因 → 处置"三件套**）：

1. **何时用**：出 macOS 包 / dmg 打不开 / Gatekeeper 说"已损坏" / RX 无声 / 热修没生效 / 构建脚本 failed；
2. **谁在驱动它**：`packaging/macos/build.sh` 一条命令（步骤表：3 个 PyInstaller → 手工装配 → 软链布局 → ad-hoc 签名 → hdiutil DMG → `verify_hotfix.py` 闸门）；构建前置（Xcode CLT、`venv/bin/python3` 绝对路径、`packaging/macos/requirements-build.txt`）；
3. **签名布局（别改回去）**：两条软链 + 数据进 Resources + 不用 `--deep` —— 附"为什么"（2026-09-17 每个版本都发"已损坏"、`Failed to load Python shared library` 的历史）；
4. **RX 无声** → `NSMicrophoneUsageDescription` / 系统麦克风权限；
5. **热修通道**（macOS 唯一修复路径）：客户端在 `macos/launcher.py`，语义与 `windows/launcher.py` 对齐；`patch.json` 404 静默；`applied.json` 去重；`version.txt` 在 `Contents/Resources/`、必须走 `runtime_path`；
6. **真机验收清单**（Task 7 的六条 + 热修 e2e 结果）；
7. **症状对照表**（Gatekeeper 已损坏 / 服务器起不来 / 菜单栏无图标 / 反复重放补丁 / 权限弹窗不出现）。

引用的每个仓库路径必须是完整相对路径（`tests/test_release_skills.py::test_referenced_repo_paths_exist` 会校验）。

- [ ] **Step 3: 跑测试确认通过**

Run: `python3 -m unittest tests.test_release_skills tests.test_release_artifacts -v`
Expected: 全部 PASS。

- [ ] **Step 4: 接线 AGENTS.md 与 mrrc-release**

AGENTS.md 的「## 发布技能」一节：
- 把 "`macos-installer` 技能待 P3（macOS 打包链）落地后补…" 替换为：
  ```markdown
  - `.pi/skills/macos-installer/` —— macOS 打包链（`packaging/macos/build.sh`）：手工 .app 装配与两条软链、
    ad-hoc 签名顺序、`NSMicrophoneUsageDescription` 硬门禁、`hdiutil` DMG、热修通道在 mac 的客户端位置。
  ```
- `.pi/skills/mrrc-release/SKILL.md`：把 "`macos-installer`（P3 后可用）" 改为 "`macos-installer`"。

- [ ] **Step 5: 同步全局并全量回归**

```bash
./dev_tools/sync_skills.sh
python3 -m unittest discover -s tests 2>&1 | tail -4
python3 dev_tools/release_check.py --strict; echo "exit=$?"
```

Expected: 同步出现 `→ macos-installer 已同步`；套件全绿（含新增 Mac 测试）；
`release_check --strict` 退出 0（macOS 的 `Info.plist` 只有 `__VERSION__`，不引入新的版本声明）。

- [ ] **Step 6: Commit**

```bash
git add .pi/skills/macos-installer/SKILL.md .pi/skills/mrrc-release/SKILL.md \
        tests/test_release_skills.py AGENTS.md
git commit -m "docs(skills): macos-installer —— 构建/签名/热修/验收全链路"
```

---

## 验收（P3 完成判据，对应 spec §7）

```bash
packaging/macos/build.sh                        # 干净 venv 上跑通 → .app + .dmg
codesign --verify --verbose=2 dist/macos/MRRC.app
spctl -a -t exec dist/macos/MRRC.app            # 不含 damaged
cat dist/macos/MRRC.app/Contents/Resources/version.txt   # == MRRC.iss MyAppVersion
python3 -m unittest discover -s tests           # 全绿
./dev_tools/sync_skills.sh                      # 三条发布技能同步
```

外加 Task 7 的人肉验收（安装 → 启动 → 浏览器 → RX 有声 → 热修端到端）。
Windows 侧回归面：`verify_hotfix.py`/`release_windows.sh` 零改动（偏离 1），现有调用的兼容性不受影响。

## 与 spec 的对应

| spec 章节 | 本计划任务 |
|---|---|
| §6.1 新增文件清单 | T2（Info.plist、模板）、T3（launcher/launcher_log）、T4（菜单层）、T5（build.sh、launcher spec）、T6（first_run） |
| §6.2 照搬清单（软链/签名顺序/hdiutil/helpers/first_run 思路） | T5 Step 3、T3 Step 4、T6 Step 3 |
| §6.3 必须改的硬编码（版本权威/产品名/Bundle ID/端口/用户目录/模板） | Global Constraints + T2 + T5 Step 3 |
| §6.4 启动器与热修通道 | T3（客户端）、T4（rumps 形态）、T5 Step 3-8（参数化→零改动，见偏离 1） |
| §6.5 构建前置（venv/依赖） | T1 |
| §7 P3 判据 | 验收节 + T7 |
| §9 P3 内部顺序 | T1→T8（first_run 位置调整，见偏离 2） |
| D3（macOS 无升级入口） | T4 的 `check_for_upgrade_notice` + `test_launcher_does_not_install_upgrades` |

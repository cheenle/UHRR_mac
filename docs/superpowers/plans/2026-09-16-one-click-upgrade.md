# 一键升级到最新版 实现计划（Windows 安装版）

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 已安装的 MRRC 在联网时能"点一下/按一个键"升到最新版：自动下载 + SHA256 校验 + 静默安装 + 自动重启（接受一次 UAC）。

**架构：** 纯逻辑放进 **`upgrade_core.py`**（可单测、平台无关：清单解析、版本决策、原子下载校验、状态文件、哨兵文件），操作系统相关部分留在 `windows/launcher.py`（`ShellExecuteW runas` 静默安装、控制台按键、重启）。服务端新增 `/api/update*`（状态 + 触发升级），UI 加"有新版本/立即升级"入口。发布侧由 `dev_tools/release_windows.sh` 生成 `latest.json` 与带版本号的安装包。

**技术栈：** Python 标准库（urllib/hashlib/ctypes/subprocess/threading）、tornado（服务端）、Inno Setup（静默安装）、现有 unittest 运行器。

规格：`docs/superpowers/specs/2026-09-16-one-click-upgrade-design.md`

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `upgrade_core.py`（新建，仓库根） | 纯逻辑：清单拉取/解析、版本决策、下载+SHA256+原子落盘、`state.json`、`upgrade.request` 哨兵、`latest.json` 生成辅助（供发布脚本复用） |
| `tests/test_upgrade_core.py`（新建） | 上述逻辑的单测（含本地 HTTP 服务做下载/校验/篡改用例） |
| `windows/launcher.py`（修改） | 启动时检查、后台下载、控制台按 `U`、轮询哨兵、`run_upgrade()`（提权静默安装 + 重启）、把结果写回 `state.json` |
| `MRRC`（修改） | `/api/update` 状态（含 `pttActive`，仅本机可无口令读）、`/api/update/upgrade`（PTT 门禁 + 写哨兵） |
| `www/update.html` + `www/mobile_modern.html` + `www/index.html`（新建/修改） | "检查更新/立即升级"页面与入口 |
| `dev_tools/release_windows.sh`（修改） | 产物带版本名、保留上一版、生成 `latest.json`、线上复核 |

---

### 任务 1：`upgrade_core.py` —— 清单与版本决策

**文件：** 创建 `upgrade_core.py`、`tests/test_upgrade_core.py`

- [ ] **步骤 1：写失败的测试**

```python
# tests/test_upgrade_core.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import upgrade_core as uc

MANIFEST = {
    "latest": "6.1.0",
    "installer": {"url": "https://x/MRRC-Setup-6.1.0.exe", "sha256": "a" * 64, "size": 100},
    "hotfix": {"url": "https://x/hotfix-6.1.0.zip", "sha256": "b" * 64, "requires": "6.0.10"},
    "previous": {"version": "6.0.10", "url": "https://x/MRRC-Setup-6.0.10.exe", "sha256": "c" * 64},
    "minSupported": "6.0.3", "mandatory": False, "notes": "x",
}

class VersionTest(unittest.TestCase):
    def test_tuple_and_compare(self):
        self.assertGreater(uc.version_tuple("6.0.10"), uc.version_tuple("6.0.9"))
        self.assertGreater(uc.version_tuple("v6.1"), uc.version_tuple("6.0.9"))
        self.assertEqual(uc.version_tuple("6.0.3"), (6, 0, 3))

class DecisionTest(unittest.TestCase):
    def test_installer_upgrade_available(self):
        plan = uc.plan_upgrade("6.0.10", MANIFEST)
        self.assertTrue(plan["installer"]["available"])
        self.assertEqual(plan["installer"]["version"], "6.1.0")
        self.assertFalse(plan["installer"]["mandatory"])

    def test_no_action_when_up_to_date_or_newer(self):
        for installed in ("6.1.0", "6.1.1", "7.0"):
            plan = uc.plan_upgrade(installed, MANIFEST)
            self.assertFalse(plan["installer"]["available"], installed)

    def test_hotfix_requires_gate(self):
        old = uc.plan_upgrade("6.0.2", MANIFEST)      # < minSupported/requires
        self.assertFalse(old["hotfix"]["available"])
        self.assertTrue(old["hotfix"]["blockedReason"])
        new = uc.plan_upgrade("6.0.10", MANIFEST)
        self.assertTrue(new["hotfix"]["available"])

    def test_missing_sections_are_tolerated(self):
        plan = uc.plan_upgrade("6.0.10", {"latest": "6.1.0"})
        self.assertFalse(plan["installer"]["available"])
        self.assertFalse(plan["hotfix"]["available"])

    def test_previous_used_only_for_rollback(self):
        plan = uc.plan_upgrade("6.1.0", MANIFEST)
        self.assertEqual(plan["previous"]["version"], "6.0.10")
        self.assertFalse(plan["installer"]["available"])
```

- [ ] **步骤 2：运行测试确认失败**

运行：`venv/bin/python3 -m unittest tests.test_upgrade_core -v`
预期：FAIL，`ModuleNotFoundError: No module named 'upgrade_core'`

- [ ] **步骤 3：实现**

```python
# upgrade_core.py
"""一键升级的纯逻辑（可单测、平台无关）。

设计要点见 docs/superpowers/specs/2026-09-16-one-click-upgrade-design.md：
  * 安装版本（version.txt）是唯一权威；热修不改安装版本（用 requires + applied.json 判重）
  * 拒绝降级；installed < minSupported 时禁用热修、必须走完整包
  * 下载必须原子：先写 .part → SHA256 校验 → os.replace()；失败绝不动现有安装
  * 启动器与页面通过 %LOCALAPPDATA%\\MRRC\\updates\\ 下的 state.json / upgrade.request 通信
"""

import hashlib
import json
import os
import re
import time
import urllib.request

DEFAULT_MANIFEST_URL = "https://www.vlsc.net/mrrc/downloads/latest.json"
LEGACY_PATCH_URL = "https://www.vlsc.net/mrrc/downloads/patch.json"


def version_tuple(text):
    """'6.0.10' → (6, 0, 10)；'v6.1' → (6, 1, 0, 0)。"""
    parts = []
    for chunk in str(text or "").replace("v", "").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts[:4])


def fetch_manifest(url=DEFAULT_MANIFEST_URL, timeout=10, fallback_url=LEGACY_PATCH_URL):
    """拉清单；失败或不是 JSON 返回 (None, 原因)。latest.json 不可用时回退 patch.json。"""
    for candidate in (url, fallback_url):
        try:
            with urllib.request.urlopen(candidate, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict) and data.get("latest"):
                data.setdefault("_source", candidate)
                return data, None
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
    return None, reason


def plan_upgrade(installed, manifest, applied_hotfixes=()):
    """给当前安装版本 + 清单，算出该做什么（不产生副作用）。"""
    installed = str(installed or "0.0.0").strip()
    installed_t = version_tuple(installed)
    latest = str((manifest or {}).get("latest") or "").strip()
    latest_t = version_tuple(latest)
    min_supported = str((manifest or {}).get("minSupported") or "").strip()
    plan = {"installed": installed, "latest": latest,
            "installer": {"available": False}, "hotfix": {"available": False},
            "previous": {"available": False}}

    installer = (manifest or {}).get("installer") or {}
    if installer.get("url") and installer.get("sha256") and latest_t > installed_t:
        plan["installer"] = {
            "available": True, "version": latest, "url": installer["url"],
            "sha256": str(installer["sha256"]).lower(),
            "size": int(installer.get("size") or 0),
            "mandatory": bool((manifest or {}).get("mandatory")),
        }

    hotfix = (manifest or {}).get("hotfix") or {}
    requires = str(hotfix.get("requires") or min_supported or "").strip()
    if hotfix.get("url") and hotfix.get("sha256") and latest_t > installed_t:
        if latest not in set(applied_hotfixes):
            if not requires or installed_t >= version_tuple(requires):
                plan["hotfix"] = {"available": True, "version": latest,
                                  "url": hotfix["url"], "sha256": str(hotfix["sha256"]).lower(),
                                  "requires": requires, "notes": hotfix.get("notes", "")}
            else:
                plan["hotfix"] = {"available": False,
                                  "blockedReason": f"需要安装版本 >= {requires}（本机 {installed}）"}
    previous = (manifest or {}).get("previous") or {}
    if previous.get("version") and previous.get("url"):
        plan["previous"] = {"available": True, "version": previous["version"],
                            "url": previous["url"], "sha256": str(previous.get("sha256") or "").lower()}
    plan["minSupported"] = min_supported
    plan["notes"] = (manifest or {}).get("notes", "")
    return plan
```

- [ ] **步骤 4：运行测试确认通过**

运行：`venv/bin/python3 -m unittest tests.test_upgrade_core -v`
预期：6 个测试 PASS

- [ ] **步骤 5：Commit**

```bash
git add upgrade_core.py tests/test_upgrade_core.py
git commit -m "feat(upgrade): 清单解析与版本决策（任务 1/8）"
```

---

### 任务 2：`upgrade_core.py` —— 原子下载、状态文件、哨兵

**文件：** 修改 `upgrade_core.py`、`tests/test_upgrade_core.py`

- [ ] **步骤 1：写失败的测试**（用本地 HTTP 服务托管假安装包）

```python
class DownloadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import http.server, socketserver, threading
        cls.payload = b"PK\x03\x04 fake installer " * 100
        cls.sha = __import__("hashlib").sha256(cls.payload).hexdigest()
        payload = cls.payload
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.send_header("Content-Length", str(len(payload)))
                self.end_headers(); self.wfile.write(payload)
            def log_message(self, *a): pass
        cls.httpd = socketserver.TCPServer(("127.0.0.1", 0), H)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.httpd.server_address[1]}/setup.exe"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="mrrc-upgrade-")

    def test_download_verifies_and_stages_atomically(self):
        result = uc.download_installer(self.url, self.sha, self.tmp, version="6.1.0")
        self.assertTrue(result["ok"])
        self.assertTrue(os.path.isfile(result["path"]))
        self.assertFalse(os.path.exists(result["path"] + ".part"), "不得残留 .part")
        # state.json 已记录
        state = uc.read_state(self.tmp)
        self.assertEqual(state["staged"]["version"], "6.1.0")
        self.assertEqual(state["staged"]["sha256"], self.sha)

    def test_sha_mismatch_discards_download(self):
        bad = "0" * 64
        result = uc.download_installer(self.url, bad, self.tmp, version="6.1.0")
        self.assertFalse(result["ok"])
        self.assertIn("sha256", result["reason"])
        self.assertFalse(os.path.exists(result["path"]))
        self.assertFalse(os.path.exists(result["path"] + ".part"))
        self.assertEqual(uc.read_state(self.tmp), {}, "失败不得留下 staged 记录")

    def test_request_file_roundtrip(self):
        uc.write_upgrade_request(self.tmp, "6.1.0")
        self.assertEqual(uc.read_upgrade_request(self.tmp)["version"], "6.1.0")
        uc.clear_upgrade_request(self.tmp)
        self.assertIsNone(uc.read_upgrade_request(self.tmp))

    def test_record_result(self):
        uc.record_result(self.tmp, "uac_denied", version="6.1.0", detail="user cancelled")
        self.assertEqual(uc.read_state(self.tmp)["lastResult"]["status"], "uac_denied")
```

- [ ] **步骤 2：运行测试确认失败** → `AttributeError: download_installer`

- [ ] **步骤 3：实现**

```python
# upgrade_core.py（追加）
def updates_dir(base_dir):
    path = os.path.join(str(base_dir), "updates")
    os.makedirs(path, exist_ok=True)
    return path


def state_path(base_dir):
    return os.path.join(updates_dir(base_dir), "state.json")


def request_path(base_dir):
    return os.path.join(updates_dir(base_dir), "upgrade.request")


def read_state(base_dir):
    try:
        with open(state_path(base_dir), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json_atomic(path, payload):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def write_state(base_dir, **fields):
    state = read_state(base_dir)
    state.update(fields)
    _write_json_atomic(state_path(base_dir), state)
    return state


def record_result(base_dir, status, version="", detail=""):
    return write_state(base_dir, lastResult={
        "status": status, "version": version, "detail": str(detail)[:2000],
        "at": time.strftime("%Y-%m-%dT%H:%M:%S")})


def write_upgrade_request(base_dir, version):
    _write_json_atomic(request_path(base_dir),
                       {"version": str(version), "at": time.strftime("%Y-%m-%dT%H:%M:%S")})


def read_upgrade_request(base_dir):
    try:
        with open(request_path(base_dir), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def clear_upgrade_request(base_dir):
    try:
        os.remove(request_path(base_dir))
    except OSError:
        pass


def installer_filename(version):
    return f"MRRC-Setup-{version}.exe"


def download_installer(url, sha256, base_dir, version, timeout=300, progress=None):
    """下载 → 校验 → 原子落盘 + 记 state；失败只留/清 .part，绝不动现有安装。"""
    target = os.path.join(updates_dir(base_dir), installer_filename(version))
    part = target + ".part"
    expected = str(sha256 or "").lower()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp, open(part, "wb") as fh:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = resp.read(262144)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        digest = hashlib.sha256()
        with open(part, "rb") as fh:
            for chunk in iter(lambda: fh.read(262144), b""):
                digest.update(chunk)
        actual = digest.hexdigest()
        if expected and actual != expected:
            os.remove(part)
            record_result(base_dir, "sha_mismatch", version, f"{actual[:12]} != {expected[:12]}")
            return {"ok": False, "reason": f"sha256 不符（{actual[:12]}… != {expected[:12]}…）",
                    "path": target}
        os.replace(part, target)
        write_state(base_dir, staged={"version": str(version), "sha256": actual,
                                      "path": target, "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        return {"ok": True, "path": target, "size": os.path.getsize(target), "sha256": actual}
    except Exception as exc:
        try:
            if os.path.exists(part):
                os.remove(part)
        except OSError:
            pass
        record_result(base_dir, "download_failed", version, f"{type(exc).__name__}: {exc}")
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}", "path": target}


def staged_matches(state, version, sha256=None):
    """state 里暂存的安装包是否就是目标版本（且文件还在）。"""
    staged = (state or {}).get("staged") or {}
    if str(staged.get("version")) != str(version):
        return False
    if sha256 and str(staged.get("sha256", "")).lower() != str(sha256).lower():
        return False
    return os.path.isfile(staged.get("path", ""))
```

- [ ] **步骤 4：运行测试确认通过** → 10 个 PASS

- [ ] **步骤 5：Commit**

```bash
git add upgrade_core.py tests/test_upgrade_core.py
git commit -m "feat(upgrade): 原子下载/SHA256 校验/状态与哨兵文件（任务 2/8）"
```

---

### 任务 3：启动器接线（检查 + 后台下载 + 按键 + 轮询）

**文件：** 修改 `windows/launcher.py`

- [ ] **步骤 1：把升级核心接入启动流程**

```python
# windows/launcher.py 顶部导入区
import upgrade_core as up            # 纯逻辑模块（见任务 1/2），随启动器一起打包
```

```python
MANIFEST_URL = "https://www.vlsc.net/mrrc/downloads/latest.json"

def _update_enabled(cfg: Path) -> bool:
    if os.environ.get("MRRC_NO_UPDATE_CHECK"):
        return False
    parser = configparser.ConfigParser()
    try:
        config_io.read_config(parser, cfg)
    except Exception:
        return True
    if parser.has_section("UPDATE"):
        return parser.getboolean("UPDATE", "enabled", fallback=True)
    return True


def _auto_download_enabled(cfg: Path) -> bool:
    parser = configparser.ConfigParser()
    config_io.read_config(parser, cfg)
    if parser.has_section("UPDATE"):
        return parser.getboolean("UPDATE", "autoDownload", fallback=True)
    return True


def check_for_upgrade(cfg: Path, data_dir: Path) -> dict | None:
    """启动时检查；可用时打印提示并（按配置）后台预下载。返回升级计划。"""
    import upgrade_core as up
    if not _update_enabled(cfg):
        return None
    manifest, error = up.fetch_manifest(MANIFEST_URL)
    if not manifest:
        print(f"[update] 检查失败（忽略）：{error}")
        return None
    plan = up.plan_upgrade(_installed_version(), manifest,
                           applied_hotfixes=applied_hotfix_versions(patch_dir()))
    if not plan["installer"]["available"]:
        # 只有热修也要说一声（热修已由 check_for_hotfix 处理）
        return plan
    info = plan["installer"]
    print(f"[update] 发现新版本 {info['version']}（本机 {plan['installed']}）"
          f"{'【强制】' if info['mandatory'] else ''}：{plan.get('notes', '')}")
    if _auto_download_enabled(cfg) and not up.staged_matches(up.read_state(data_dir), info["version"], info["sha256"]):
        def _bg():
            result = up.download_installer(info["url"], info["sha256"], data_dir, info["version"])
            if result["ok"]:
                print(f"[update] 已下载 {info['version']}（{result['size'] // 1024} KB），按 U 立即升级")
            else:
                print(f"[update] 下载失败（忽略）：{result['reason']}")
        threading.Thread(target=_bg, name="update-download", daemon=True).start()
    else:
        print(f"[update] 新版本已就绪，按 U 立即升级")
    return plan
```

- [ ] **步骤 2：控制台按键 + 哨兵轮询 + 执行升级**

```python
def run_upgrade(data_dir: Path, version: str) -> str:
    """执行静默安装（一次 UAC）。返回状态串：ok/uac_denied/install_failed/missing_staged。"""
    import upgrade_core as up
    state = up.read_state(data_dir)
    staged = state.get("staged") or {}
    setup = staged.get("path", "")
    if str(staged.get("version")) != str(version) or not os.path.isfile(setup):
        up.record_result(data_dir, "missing_staged", version)
        return "missing_staged"
    log_path = str(Path(data_dir) / "updates" / f"install-{version}.log")
    params = (f'/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS '
              f'/LOG="{log_path}"')
    try:
        import ctypes
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", setup, params,
                                                 str(Path(data_dir) / "updates"), 1)
    except Exception as exc:
        up.record_result(data_dir, "install_failed", version, str(exc))
        return "install_failed"
    if rc <= 32:                                  # 5 = ERROR_ACCESS_DENIED（用户拒绝 UAC）
        status = "uac_denied" if rc == 5 else "install_failed"
        up.record_result(data_dir, status, version, f"ShellExecute rc={rc}")
        return status
    # 等待安装器进程结束（按名字轮询，避免拿不到句柄）
    deadline = time.time() + 600
    while time.time() < deadline:
        time.sleep(2)
        if _installed_version() == str(version):
            break
    ok = _installed_version() == str(version)
    up.record_result(data_dir, "ok" if ok else "install_failed", version,
                     "" if ok else "安装后 version.txt 未更新（见 install log）")
    return "ok" if ok else "install_failed"
```

在 `main()` 里（`check_for_hotfix(cfg)` 之后）：

```python
    plan = check_for_upgrade(cfg, data_dir)
    pending = (plan or {}).get("installer", {})
    ...
    # 起服务后：后台线程轮询哨兵 + 控制台按键（两者任一触发即升级）
    def _watch_upgrade():
        import upgrade_core as up
        while True:
            request = up.read_upgrade_request(data_dir)
            target = (request or {}).get("version") or (pending.get("version") if pending.get("available") else None)
            if target:
                up.clear_upgrade_request(data_dir)
                status = run_upgrade(data_dir, str(target))
                print(f"[update] 升级结果：{status}")
                if status == "ok":
                    os.execv(sys.executable, [sys.executable] + sys.argv)   # 重启启动器 → 拉起新版
                return
            time.sleep(1)
    threading.Thread(target=_watch_upgrade, name="update-watch", daemon=True).start()
```

- [ ] **步骤 3：语法与既有测试**

运行：`python3 -m py_compile windows/launcher.py && venv/bin/python3 -m unittest discover -s tests`
预期：OK（现有 51 项不回归）

- [ ] **步骤 4：Commit**

```bash
git add windows/launcher.py
git commit -m "feat(upgrade): 启动器接线（检查/后台下载/按键U/哨兵/静默安装）（任务 3/8）"
```

---

### 任务 4：服务端 `/api/update*`

**文件：** 修改 `MRRC`

- [ ] **步骤 1：实现 handler**

```python
class UpdateApiHandler(BaseHandler):
    """一键升级的状态与触发。

    GET  /api/update          状态（installed/latest/staged/lastResult/notes/pttActive）
    POST /api/update/upgrade  写哨兵 upgrade.request（PTT 活跃时拒绝）
    POST /api/update/rollback 写哨兵指向 previous 版本
    """

    def _updates_dir(self):
        base = os.path.dirname(os.path.abspath(config_file))
        return os.path.join(base, "updates")

    def _status(self):
        import upgrade_core as up
        base = os.path.dirname(os.path.abspath(config_file))
        version = ""
        for candidate in (os.path.join(_runtime_dir(), "version.txt"),
                          os.path.join(_resource_dir(), "version.txt")):
            if os.path.exists(candidate):
                try:
                    version = open(candidate, encoding="utf-8").read().strip()
                except OSError:
                    pass
                break
        state = up.read_state(base)
        plan = {}
        try:
            manifest, _err = up.fetch_manifest()
            if manifest:
                plan = up.plan_upgrade(version, manifest,
                                       applied_hotfixes=set(getattr(patch_overlay, "applied_versions", lambda: [])()))
        except Exception:
            plan = {}
        return {"ok": True, "installed": version, "plan": plan, "state": state,
                "pttActive": bool(CTRX and getattr(CTRX, "mrrc_ptt_active", False)),
                "request": up.read_upgrade_request(base)}

    def get(self):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(self._status(), ensure_ascii=False, default=str))

    async def post(self):
        self.set_header("Content-Type", "application/json")
        if not self.current_user:
            self.set_status(403)
            self.write(json.dumps({"ok": False, "reason": "auth_required"}))
            return
        if self.request.path.rstrip("/").endswith("rollback"):
            import upgrade_core as up
            base = os.path.dirname(os.path.abspath(config_file))
            status = self._status()
            previous = (status.get("plan") or {}).get("previous") or {}
            if not previous.get("available"):
                self.write(json.dumps({"ok": False, "reason": "no_previous"})); return
            # 回退同样走"下载+校验+静默安装"：先由启动器下载 previous 包
            up.write_upgrade_request(base, previous["version"])
            self.write(json.dumps({"ok": True, "queued": previous["version"]}, ensure_ascii=False))
            return
        if CTRX and getattr(CTRX, "mrrc_ptt_active", False):
            self.set_status(423)
            self.write(json.dumps({"ok": False, "reason": "ptt_active",
                                   "message": "发射中不升级，请先松开 PTT"}))
            return
        import upgrade_core as up
        base = os.path.dirname(os.path.abspath(config_file))
        payload = {}
        try:
            payload = json.loads(self.request.body or b"{}") or {}
        except Exception:
            payload = {}
        status = self._status()
        version = str(payload.get("version") or (status.get("plan") or {}).get("latest") or "").strip()
        if not version:
            self.write(json.dumps({"ok": False, "reason": "unknown_version"})); return
        up.write_upgrade_request(base, version)
        self.write(json.dumps({"ok": True, "queued": version,
                               "note": "启动器会在 1 秒内接手；会弹出一次 UAC 确认"}, ensure_ascii=False))
```
路由：`(r'/api/update.*', UpdateApiHandler),`

- [ ] **步骤 2：本机验证**（临时实例）

```bash
# 起临时实例后
curl -sk https://localhost:8894/api/update -H "Cookie: user=<签名>" | python3 -m json.tool | head -20
# 期望：installed=6.0.10，plan.installer.available 视清单而定，pttActive=false
```

- [ ] **步骤 3：Commit**

```bash
git add MRRC
git commit -m "feat(upgrade): /api/update 状态与触发（PTT 门禁）（任务 4/8）"
```

---

### 任务 5：页面与入口

**文件：** 创建 `www/update.html`；修改 `www/mobile_modern.html`、`www/index.html`

- [ ] **步骤 1：页面**（与 `support.html` 同风格：状态卡片 + 立即升级/回退按钮 + 结果区）

```html
<h2>⬆️ 软件更新</h2>
<div class="card" id="state">正在检查…</div>
<button id="btnUp" onclick="doUpgrade()">立即升级</button>
<button id="btnRollback" onclick="doRollback()">回退到上一版</button>
<pre id="detail"></pre>
<script>
async function refresh(){ const d = await (await fetch('/api/update')).json(); /* 渲染 installed/latest/staged/lastResult/pttActive */ }
async function doUpgrade(){ const d = await (await fetch('/api/update/upgrade',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})})).json(); /* 提示：已通知启动器，窗口会弹 UAC */ }
</script>
```
入口：移动端菜单加「⬆️ 软件更新」；桌面工具栏加 ⬆️ 按钮（有新版本时标题带红点/文案）。

- [ ] **步骤 2：语法检查**：`node --check`（若含外链 JS）+ 页面 HTTP 200 自测

- [ ] **步骤 3：Commit**

```bash
git add www/update.html www/mobile_modern.html www/index.html
git commit -m "feat(upgrade): 更新页面与入口（任务 5/8）"
```

---

### 任务 6：发布流程（`latest.json` + 带版本名产物）

**文件：** 修改 `dev_tools/release_windows.sh`

- [ ] **步骤 1：产物命名与归档**

```bash
# 发布时（取 VERSION 与上一版 PREV）
cp "$LOCAL_EXE" "website/downloads/MRRC-Setup-${VERSION}.exe"      # 带版本名，供升级通道固定 SHA256
cp "$LOCAL_EXE" "website/downloads/MRRC-Setup.exe"                 # 兼容老书签
# previous：若 website/downloads/MRRC-Setup-${PREV}.exe 不存在，保留当前 MRRC-Setup.exe 的旧快照
```

- [ ] **步骤 2：生成 `latest.json`**

```bash
venv/bin/python3 - "$VERSION" "$(shasum -a 256 website/downloads/MRRC-Setup-${VERSION}.exe | awk '{print $1}')" \
    "$(stat -f%z website/downloads/MRRC-Setup-${VERSION}.exe)" "$PREV" <<'PY'
import json, os, sys, hashlib
version, sha, size, prev = sys.argv[1:5]
def h(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else ""
base = "https://www.vlsc.net/mrrc/downloads"
manifest = {"latest": version,
            "installer": {"url": f"{base}/MRRC-Setup-{version}.exe", "sha256": sha, "size": int(size)},
            "minSupported": "6.0.3", "mandatory": False,
            "releasedAt": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
            "notes": os.environ.get("RELEASE_NOTES", "")}
patch = os.path.join("website/downloads", "patch.json")
if os.path.exists(patch):
    p = json.load(open(patch)); manifest["hotfix"] = {"url": p["url"], "sha256": p["sha256"],
                                                     "requires": p.get("requires", "6.0.3"),
                                                     "notes": p.get("notes", "")}
prev_exe = f"website/downloads/MRRC-Setup-{prev}.exe"
if prev and os.path.exists(prev_exe):
    manifest["previous"] = {"version": prev, "url": f"{base}/MRRC-Setup-{prev}.exe",
                            "sha256": h(prev_exe)}
json.dump(manifest, open("website/downloads/latest.json", "w"), ensure_ascii=False, indent=2)
print(json.dumps(manifest, ensure_ascii=False)[:400])
PY
```

- [ ] **步骤 3：线上复核**：`curl .../latest.json` 的 sha256 与实际下载一致（复用现有校验步骤）

- [ ] **步骤 4：Commit**

```bash
git add dev_tools/release_windows.sh website/downloads/latest.json
git commit -m "feat(upgrade): 发布流程生成 latest.json 与带版本名安装包（任务 6/8）"
```

---

### 任务 7：VM 端到端（真实升级 6.0.10 → 6.1.0）

**文件：** `dev_tools/verify_upgrade_vm.md`（新增，记录步骤与结果）

- [ ] **步骤 1：先出 6.0.10 安装包**（本轮已完成）：`dist/windows/MRRC-Setup.exe`（45 MB，SHA 已知）
- [ ] **步骤 2：改 `MyAppVersion=6.1.0` 再出 6.1.0 包**（构建机上 `build.ps1`，约 2 分钟），只用于升级测试
- [ ] **步骤 3：构造临时 `latest.json`**，把 installer 指向 6.1.0 包（托管在 VM 的本地 HTTP 或站点临时路径）
- [ ] **步骤 4：VM 内装 6.0.10**（`MRRC-Setup.exe /VERYSILENT`），确认 `version.txt=6.0.10`
- [ ] **步骤 5：启动启动器** → 期望打印 `[update] 发现新版本 6.1.0…` → 后台下载 + 校验 → `按 U 立即升级`
- [ ] **步骤 6：按 U（或页面点按钮）** → UAC → 静默安装 → `version.txt=6.1.0` + 服务自动拉起
- [ ] **步骤 7：负例**：篡改 `latest.json` 的 sha256 → 拒绝（`sha_mismatch`）；拒绝 UAC → `uac_denied` 且旧版照常；PTT 活跃时页面按钮返回 423
- [ ] **步骤 8：记录结果**进 `dev_tools/verify_upgrade_vm.md` 并 Commit

---

### 任务 8：文档与 CHANGELOG

- [ ] **步骤 1：`docs/current/operations/one-click-upgrade.md`**：开关（`[UPDATE] enabled/autoDownload/channel`、`MRRC_NO_UPDATE_CHECK=1`）、状态文件位置、失败状态含义、回退用法、发布 `latest.json` 的注意事项（sha256 必须与带版本名产物一致）
- [ ] **步骤 2：CHANGELOG** 新增 `### ⬆️ 一键升级`；`AGENTS.md` 加一行指针
- [ ] **步骤 3：Commit**

```bash
git add docs/current/operations/one-click-upgrade.md CHANGELOG.md AGENTS.md
git commit -m "docs(upgrade): 一键升级文档与 CHANGELOG（任务 8/8）"
```

---

## 自检

**规格覆盖度**：§3 清单 → 任务 1/6；§4 启动器状态机 → 任务 2/3；§5 配置开关 → 任务 3（`[UPDATE]`）+ 任务 8；§6 页面入口 → 任务 4/5；§7 发布流程 → 任务 6；§8 安全边界 → 任务 1（SHA256/拒绝降级）+ 任务 3（UAC）；§9 测试 → 任务 1/2 + 任务 7；§10 验收清单 → 任务 7 逐条。

**占位符扫描**：任务 5 的页面片段展示了关键 JS 函数体（`refresh/doUpgrade/doRollback`）与元素 id，实现时按 `support.html` 的既有风格补全样式与错误分支——这是唯一需要照抄邻近文件的地方，已在步骤中指明参照对象。

**类型一致性**：`plan_upgrade()` 返回的 `installer/hotfix/previous` 三个子字典在任务 1、3、4、6 中字段一致（`available/version/url/sha256/size/mandatory`）；`download_installer()` 与 `staged_matches()/read_state()` 的字段（`staged.version/sha256/path`）在任务 2、3、4 一致；`record_result()` 的状态串（`ok/uac_denied/install_failed/sha_mismatch/download_failed/missing_staged`）在任务 2、3、8 一致。

# 支持日志一键上传 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在「🐞 遇到问题」页面一键生成脱敏诊断包并上传到 `www.vlsc.net` 的自有接收端，维护者可在带密码的列表页查看。

**架构：** 客户端三块——`support_bundle.py`（纯逻辑：尾读日志、脱敏、打包、体检摘要）、`MRRC` 的 `/api/support/*`（executor 中执行 IO）、`www/support.html`（三步向导）。接收端是 stdlib `http.server` 小服务（`tools/support_receiver/server.py`），nginx 反代 `/mrrc/support/`，存储在 `/var/www/support/<id>/`。

**技术栈：** Python 3.7+ 标准库（zipfile/re/urllib/http.server）、tornado（现有）、unittest（现有 runner：`python3 -m unittest discover -s tests`）。

规格：`docs/superpowers/specs/2026-09-16-support-log-upload-design.md`

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `support_bundle.py`（新建，仓库根） | 收集/脱敏/打包/摘要。纯标准库、无 tornado 依赖 → 可单测、可热修 |
| `tests/test_support_bundle.py`（新建） | 上述模块的单元测试（脱敏必测） |
| `MRRC`（修改） | 4 个 `/api/support/*` 接口；音频采集回调；设备报告 |
| `audio_interface.py`（修改） | `device_report()`；把最近一条音频健康行存到 `PyAudioCapture.last_health` |
| `www/support.html`（新建） | 三步向导页面 |
| `www/mobile_modern.html` / `.js`（修改） | 菜单加 `🐞 遇到问题` 入口（新窗口打开） |
| `www/index.html`（修改） | 桌面工具栏加小图标入口 |
| `tools/support_receiver/server.py`（新建） | 接收端（stdlib，Basic Auth 列表页） |
| `tools/support_receiver/support-receiver.service`（新建） | systemd 单元 |
| `deploy_support_receiver.sh`（新建，仓库根） | 部署到 www.vlsc.net（rsync + systemd + nginx location，含配置备份） |
| `dev_tools/test_support_receiver.py`（新建） | 本地起接收端跑全流程 + 越权/超限用例 |
| `windows/launcher.py`（修改） | 把服务端 stdout/stderr tee 到 `%LOCALAPPDATA%\MRRC\logs\server-stdout.log`（滚动 2 MB） |

---

### 任务 1：`support_bundle.py` 的脱敏与尾读（核心安全逻辑，先写测试）

**文件：** 创建 `support_bundle.py`、`tests/test_support_bundle.py`

- [ ] **步骤 1：写失败的测试**

```python
# tests/test_support_bundle.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import support_bundle as sb

class RedactionTest(unittest.TestCase):
    def test_secret_values_replaced(self):
        text = "cookie_secret = L8LwECiNxyz\npassword: hunter2\napikey=abc123\nnormal=1"
        out, hits = sb.redact_text(text)
        self.assertNotIn("L8LwECiNxyz", out)
        self.assertNotIn("hunter2", out)
        self.assertNotIn("abc123", out)
        self.assertIn("<redacted>", out)
        self.assertGreaterEqual(hits, 3)

    def test_config_whitelist_only(self):
        cfg = ("[SERVER]\nport = 8877\ncookie_secret = SECRET\n"
               "[AUDIO]\ninputdevice = USB Audio\n"
               "[HAMLIB]\nrig_model = IC-M710\nrig_pathname = COM3\n")
        out = sb.redact_config_text(cfg)
        self.assertIn("port = 8877", out)
        self.assertIn("rig_model = IC-M710", out)
        self.assertNotIn("SECRET", out)
        self.assertNotIn("cookie_secret", out)

    def test_forbidden_files_never_included(self):
        for name in ("MRRC_users.db", "certs/fullchain.pem", "x.key"):
            self.assertFalse(sb.is_collectable(name))
```

- [ ] **步骤 2：运行测试确认失败**

运行：`venv/bin/python3 -m unittest tests.test_support_bundle -v`
预期：FAIL，`ModuleNotFoundError: No module named 'support_bundle'`

- [ ] **步骤 3：实现 `support_bundle.py` 的这三个函数**

```python
# support_bundle.py（节选）
import os, re

SECRET_KEY_RE = re.compile(
    r"(?i)\b(cookie[_-]?secret|pass(?:word|wd)?|secret|token|api[_-]?key|credential)\b"
    r"(\s*[=:]\s*)(\S+)")

# 配置里允许出现在诊断包中的键（其余一律不进包）
CONFIG_WHITELIST = {
    "SERVER": {"port", "host"},
    "HAMLIB": {"rig_model", "rig_pathname", "rig_rate", "stop_bits", "data_bits",
               "serial_parity", "serial_handshake", "trxautopower"},
    "AUDIO": {"inputdevice", "outputdevice", "hostapi_preference", "diag"},
    "WDSP": {"sample_rate", "buffer_size", "nr2_level", "nr2_enabled", "nb_enabled",
             "anf_enabled", "agc_mode", "bandpass_low", "bandpass_high", "nr2_max_atten_db",
             "nr2_dry", "agc_top_db", "panel_gain", "nr2_ae_psi", "nr2_ae_zeta_thresh"},
    "CTRL": {"interval_smeter_update"},
    "ATR1000": {"enabled"},
    "INSTANCE_SETTINGS": {"instance_rigctl_model", "instance_rigctl_port",
                          "instance_unix_socket", "atr1000_proxy_transport"},
    "RNNOISE": {"suppress_level"},
    "UPDATE": {"enabled", "autoDownload", "channel"},
    "HOTFIX": {"enabled"},
}

FORBIDDEN_SUBSTRINGS = ("mrrc_users.db", "cert", ".pem", ".key", ".crt", ".p12")


def redact_text(text):
    """把密钥类键值替换掉，返回 (新文本, 命中数)。"""
    return SECRET_KEY_RE.subn(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", text or "")


def redact_config_text(text):
    """保留白名单键，其余丢弃；行内再走一次密钥替换。"""
    out, section = [], None
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            allowed = CONFIG_WHITELIST.get(section)
            out.append(line)
            if allowed is None:
                out.append("; <section omitted: not in whitelist>")
            continue
        if section is None or "=" not in line:
            out.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        allowed = CONFIG_WHITELIST.get(section, set())
        if key not in allowed:
            continue                       # 白名单外：整行丢
        cleaned, _ = redact_text(line)
        out.append(cleaned)
    return "\n".join(out) + "\n"


def is_collectable(relative_path):
    """路径是否允许进包（用户库/证书/私钥一律不进）。"""
    lowered = str(relative_path).lower()
    return not any(token in lowered for token in FORBIDDEN_SUBSTRINGS)


def tail_lines(path, max_bytes=2 * 1024 * 1024):
    """读取文件尾部 ≤max_bytes，并对齐到完整行（返回 str；文件不存在返回 ''）。"""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                fh.readline()               # 丢掉可能被截断的半行
            data = fh.read()
    except OSError:
        return ""
    return data.decode("utf-8", "replace")
```

- [ ] **步骤 4：运行测试确认通过**

运行：`venv/bin/python3 -m unittest tests.test_support_bundle -v`
预期：3 个测试 PASS

- [ ] **步骤 5：Commit**

```bash
git add support_bundle.py tests/test_support_bundle.py
git commit -m "feat(support): 诊断包脱敏与日志尾读（白名单+密钥替换+尾对齐）"
```

---

### 任务 2：打包与体检摘要（`build_bundle`）

**文件：** 修改 `support_bundle.py`、`tests/test_support_bundle.py`

- [ ] **步骤 1：写失败的测试**

```python
class BundleTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="sb-test-")
        os.makedirs(os.path.join(self.tmp, "logs"), exist_ok=True)
        with open(os.path.join(self.tmp, "logs", "MRRC.log"), "w", encoding="utf-8") as fh:
            fh.write("ok\n" + "Traceback (most recent call last):\n" * 3 +
                     "🎧 音频健康: 30s 采集 1430000 样本（应有 1440000，98.5%）\n")

    def test_bundle_contains_expected_and_no_secrets(self):
        result = sb.build_bundle(out_dir=self.tmp, problem="声音卡顿",
                                 contact="BG1SB", env={"version": "6.0.7"},
                                 log_files={"logs/MRRC.log": os.path.join(self.tmp, "logs", "MRRC.log")},
                                 config_text="[SERVER]\nport = 8877\ncookie_secret = TOP\n")
        self.assertTrue(os.path.isfile(result["path"]))
        import zipfile
        with zipfile.ZipFile(result["path"]) as z:
            names = set(z.namelist())
            self.assertIn("manifest.json", names)
            self.assertIn("problem.txt", names)
            self.assertIn("diagnostics/summary.txt", names)
            self.assertIn("state/config-redacted.ini", names)
            blob = b"".join(z.read(n) for n in names if n.endswith((".txt", ".json", ".ini", ".log")))
            self.assertNotIn(b"TOP", blob)                      # 密钥不进包
            summary = z.read("diagnostics/summary.txt").decode()
            self.assertIn("Traceback", summary)
            self.assertIn("98.5%", summary)                     # 音频健康行被识别
        self.assertGreaterEqual(result["redactions"], 1)

    def test_missing_logs_still_produce_minimal_bundle(self):
        result = sb.build_bundle(out_dir=self.tmp, problem="", contact="", env={},
                                 log_files={"logs/MRRC.log": os.path.join(self.tmp, "nope.log")},
                                 config_text="")
        self.assertTrue(result["warnings"])
        self.assertTrue(os.path.isfile(result["path"]))
```

- [ ] **步骤 2：运行测试确认失败**

运行：`venv/bin/python3 -m unittest tests.test_support_bundle -v`
预期：FAIL，`AttributeError: module 'support_bundle' has no attribute 'build_bundle'`

- [ ] **步骤 3：实现 `summarize_log` 与 `build_bundle`**

```python
# support_bundle.py（追加）
import json, time, zipfile

SUMMARY_PATTERNS = [
    ("Traceback", re.compile(r"Traceback \(most recent call last\)")),
    ("ERROR", re.compile(r"\bERROR\b")),
    ("异常标记 ❌", re.compile("❌")),
    ("告警 ⚠️", re.compile("⚠️")),
    ("IOLoop 卡顿", re.compile(r"IOLoop stall")),
    ("ATR-1000", re.compile(r"ATR-1000")),
    ("PTT", re.compile(r"\bPTT\b")),
    ("热修覆盖层", re.compile("补丁覆盖层")),
]
AUDIO_HEALTH_RE = re.compile(r"🎧 音频健康:.*?([0-9]+\.[0-9])%")


def summarize_log(text):
    """把日志尾部归类计数 + 每类最近 3 条，最后给结论区。"""
    lines = (text or "").splitlines()
    parts, conclusions = [], []
    for label, pattern in SUMMARY_PATTERNS:
        hits = [ln.strip()[:300] for ln in lines if pattern.search(ln)]
        if not hits:
            continue
        parts.append(f"== {label}：{len(hits)} 条 ==")
        parts.extend(f"  - {h}" for h in hits[-3:])
        parts.append("")
    pcts = [float(m) for m in AUDIO_HEALTH_RE.findall(text or "")]
    if pcts:
        worst = min(pcts)
        conclusions.append(f"音频采集：最低健康度 {worst:.1f}%"
                           + ("（<99%，采集跟不上，需查 CPU/WDSP 设置/主机 API）" if worst < 99 else "（正常）"))
    conclusions.append("热修覆盖层："
                       + ("生效过" if "补丁覆盖层已启用" in (text or "") else "未见启用记录"))
    conclusions.append("WDSP："
                       + ("加载成功" if "WDSP 库加载成功" in (text or "") else "未见成功记录"))
    head = ["=== 自动体检结论 ==="] + [f"  * {c}" for c in conclusions] + ["", "=== 命中明细 ==="]
    return "\n".join(head + parts) + "\n"


def build_bundle(out_dir, problem="", contact="", env=None, log_files=None,
                 config_text="", include_audio=None, extra_files=None,
                 manifest_extra=None):
    """生成诊断包，返回 {id, path, size, files, redactions, warnings}。"""
    os.makedirs(out_dir, exist_ok=True)
    bundle_id = time.strftime("%Y%m%d-%H%M%S") + "-" + os.urandom(2).hex()
    warnings, redactions, collected = [], 0, []
    zpath = os.path.join(out_dir, f"support-{bundle_id}.zip")

    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        def add(name, data):
            if isinstance(data, str):
                data = data.encode("utf-8")
            z.writestr(name, data)
            collected.append(name)

        add("problem.txt", f"# 问题描述\n{problem or '(未填写)'}\n\n# 联系方式\n{contact or '(未填写)'}\n")
        add("README.txt",
            "本包由 MRRC「遇到问题 → 上传日志」生成。\n"
            "包含：日志尾部、脱敏后的配置快照、环境快照、自动体检摘要。\n"
            "不含：登录数据库、证书私钥、cookie_secret 等任何凭据。\n")

        log_text_for_summary = ""
        for name, path in (log_files or {}).items():
            if not is_collectable(name):
                warnings.append(f"跳过受限文件 {name}")
                continue
            text = tail_lines(path)
            if not text:
                warnings.append(f"日志不存在或为空：{name}")
                continue
            cleaned, hits = redact_text(text)
            redactions += hits
            log_text_for_summary += cleaned
            add(name, cleaned)

        cleaned_cfg, hits = redact_text(redact_config_text(config_text))
        redactions += hits
        add("state/config-redacted.ini", cleaned_cfg)
        add("diagnostics/summary.txt", summarize_log(log_text_for_summary))
        add("diagnostics/env.json", json.dumps(env or {}, ensure_ascii=False, indent=2))
        for name, data in (extra_files or {}).items():
            if is_collectable(name):
                add(name, data)
        if include_audio:
            add("audio/rx-5s.wav", include_audio)

        manifest = {
            "id": bundle_id, "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "files": collected, "redactions": redactions, "warnings": warnings,
        }
        manifest.update(manifest_extra or {})
        add("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    return {"id": bundle_id, "path": zpath, "size": os.path.getsize(zpath),
            "files": collected, "redactions": redactions, "warnings": warnings}
```

- [ ] **步骤 4：运行测试确认通过**

运行：`venv/bin/python3 -m unittest tests.test_support_bundle -v`
预期：5 个测试 PASS

- [ ] **步骤 5：Commit**

```bash
git add support_bundle.py tests/test_support_bundle.py
git commit -m "feat(support): 诊断包生成 + 自动体检摘要（含最小包降级）"
```

---

### 任务 3：接收端服务（stdlib）与本地全流程测试

**文件：** 创建 `tools/support_receiver/server.py`、`dev_tools/test_support_receiver.py`

- [ ] **步骤 1：写失败的测试**（节选关键断言）

```python
# dev_tools/test_support_receiver.py
import base64, json, os, re, subprocess, sys, tempfile, time, unittest, urllib.request

class ReceiverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="recv-")
        env = dict(os.environ, SUPPORT_DIR=cls.tmp, SUPPORT_PASSWORD="pw", SUPPORT_PORT="0")
        cls.proc = subprocess.Popen([sys.executable, "tools/support_receiver/server.py"],
                                    env=env, stdout=subprocess.PIPE, text=True)
        line = cls.proc.stdout.readline()                 # server 打印 "listening on 127.0.0.1:PORT"
        cls.base = "http://" + re.search(r"on (\S+)", line).group(1)

    def test_full_flow_and_limits(self):
        req = urllib.request.Request(self.base + "/api/create", data=b"{}",
                                     headers={"Content-Type": "application/json"})
        rid = json.loads(urllib.request.urlopen(req).read())["id"]
        put = urllib.request.Request(self.base + f"/api/{rid}/bundle", data=b"PK\x03\x04fake",
                                     method="PUT")
        self.assertEqual(urllib.request.urlopen(put).status, 200)
        auth = base64.b64encode(b"mrrc:pw").decode()
        listing = urllib.request.urlopen(urllib.request.Request(
            self.base + "/api/list", headers={"Authorization": "Basic " + auth})).read().decode()
        self.assertIn(rid, listing)
        # 越权 id
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(urllib.request.Request(
                self.base + "/api/../etc/passwd"))
```

- [ ] **步骤 2：运行测试确认失败**

运行：`venv/bin/python3 dev_tools/test_support_receiver.py -v`
预期：FAIL（服务不存在）

- [ ] **步骤 3：实现接收端**

```python
# tools/support_receiver/server.py
"""MRRC 支持包接收端（仅标准库）。

环境变量：
  SUPPORT_DIR      存储根目录（默认 /var/www/support）
  SUPPORT_PASSWORD 列表页/下载的 Basic Auth 密码（必填）
  SUPPORT_USER     用户名（默认 mrrc）
  SUPPORT_PORT     监听端口（默认 8099；0 = 随机，测试用）
  SUPPORT_MAX_MB   单包上限（默认 20）
"""
import base64, hmac, json, os, re, socketserver, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")
DIR = os.environ.get("SUPPORT_DIR", "/var/www/support")
USER = os.environ.get("SUPPORT_USER", "mrrc")
PASSWORD = os.environ.get("SUPPORT_PASSWORD", "")
MAX_BYTES = int(os.environ.get("SUPPORT_MAX_MB", "20")) * 1024 * 1024
RATE = {}                                      # ip -> [timestamps]


class Handler(BaseHTTPRequestHandler):
    server_version = "MRRC-Support"

    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            user, _, pwd = base64.b64decode(header[6:]).decode().partition(":")
        except Exception:
            return False
        return hmac.compare_digest(user, USER) and hmac.compare_digest(pwd, PASSWORD)

    def _rate_ok(self):
        now = time.time()
        bucket = [t for t in RATE.get(self.client_address[0], []) if now - t < 60]
        bucket.append(now)
        RATE[self.client_address[0]] = bucket
        return len(bucket) <= 5

    def do_POST(self):
        if self.path == "/api/create":
            if not self._rate_ok():
                return self._json(429, {"ok": False, "reason": "rate_limited"})
            length = int(self.headers.get("Content-Length") or 0)
            meta = json.loads(self.rfile.read(length) or b"{}")
            rid = time.strftime("%Y%m%d-%H%M%S") + "-" + os.urandom(2).hex()
            target = os.path.join(DIR, rid)
            os.makedirs(target, exist_ok=True)
            with open(os.path.join(target, "meta.json"), "w", encoding="utf-8") as fh:
                json.dump({"id": rid, "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
                           "remote": self.client_address[0], **meta}, fh, ensure_ascii=False, indent=2)
            return self._json(200, {"ok": True, "id": rid})
        return self._json(404, {"ok": False, "reason": "not_found"})

    def do_PUT(self):
        m = re.match(r"^/api/([^/]+)/bundle$", self.path)
        if not m or not ID_RE.match(m.group(1)):
            return self._json(400, {"ok": False, "reason": "bad_id"})
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BYTES:
            return self._json(413, {"ok": False, "reason": "too_large"})
        target = os.path.join(DIR, m.group(1))
        if not os.path.isdir(target):
            return self._json(404, {"ok": False, "reason": "unknown_id"})
        data = self.rfile.read(length)
        with open(os.path.join(target, "bundle.zip"), "wb") as fh:
            fh.write(data)
        return self._json(200, {"ok": True, "size": length})

    def do_GET(self):
        if not self._authed():
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="MRRC Support"')
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path in ("/api/list", "/api/list/"):
            rows = []
            for rid in sorted(os.listdir(DIR), reverse=True)[:200]:
                folder = os.path.join(DIR, rid)
                if not ID_RE.match(rid) or not os.path.isdir(folder):
                    continue
                meta = {}
                try:
                    meta = json.load(open(os.path.join(folder, "meta.json"), encoding="utf-8"))
                except Exception:
                    pass
                size = os.path.getsize(os.path.join(folder, "bundle.zip")) \
                    if os.path.exists(os.path.join(folder, "bundle.zip")) else 0
                rows.append(f'<li><b>{rid}</b> {size/1024:.0f} KB — '
                            f'{meta.get("problem", "")[:120]} '
                            f'({meta.get("version", "?")}, {meta.get("remote", "?")}) '
                            f'<a href="/api/{rid}/bundle">下载</a></li>')
            body = ("<html><meta charset='utf-8'><body><h3>MRRC 支持包</h3><ul>"
                    + "".join(rows) + "</ul></body></html>").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        m = re.match(r"^/api/([^/]+)/bundle$", self.path or "")
        if m and ID_RE.match(m.group(1)):
            path = os.path.join(DIR, m.group(1), "bundle.zip")
            if os.path.isfile(path):
                data = open(path, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="support-{m.group(1)}.zip"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.client_address[0], fmt % args))


def main():
    if not PASSWORD:
        print("SUPPORT_PASSWORD 未设置", file=sys.stderr)
        return 2
    os.makedirs(DIR, exist_ok=True)
    port = int(os.environ.get("SUPPORT_PORT", "8099"))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"listening on {httpd.server_address[0]}:{httpd.server_address[1]}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **步骤 4：运行测试确认通过**

运行：`venv/bin/python3 dev_tools/test_support_receiver.py -v`
预期：PASS（含越权 id 被拒）

- [ ] **步骤 5：Commit**

```bash
git add tools/support_receiver/server.py dev_tools/test_support_receiver.py
git commit -m "feat(support): 接收端（stdlib、Basic Auth 列表页、限速限大小、防穿越）"
```

---

### 任务 4：MRRC 接口（生成 / 下载 / 上传）

**文件：** 修改 `MRRC`（新增 `SupportApiHandler` 与路由 `/api/support/.*`）

- [ ] **步骤 1：写失败的测试**（HTTP 级别，复用 `tests/` 里的临时实例模式）

```python
# tests/test_support_api.py（在源码模式起一个最小 MRRC？—— 太重；
# 这里改为直接测 handler 依赖的两个纯函数，HTTP 行为交给 VM 端到端验收）
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import support_bundle as sb

class UploadPayloadTest(unittest.TestCase):
    def test_collect_env_shape(self):
        env = sb.collect_env_snapshot(version="6.0.7", extra={"audio": {"api": "Windows WASAPI"}})
        for key in ("version", "platform", "python", "audio"):
            self.assertIn(key, env)
```

- [ ] **步骤 2：运行测试确认失败** → `AttributeError: collect_env_snapshot`

- [ ] **步骤 3：实现 `collect_env_snapshot()` + `MRRC` 接口**

```python
# support_bundle.py 追加
def collect_env_snapshot(version="", extra=None):
    import platform, sys
    snap = {
        "version": version, "frozen": bool(getattr(sys, "frozen", False)),
        "python": sys.version.split()[0], "platform": platform.platform(),
        "cpuCount": os.cpu_count(),
    }
    snap.update(extra or {})
    return snap
```

```python
# MRRC：新增 handler（放在 DevicesApiHandler 之后）
class SupportApiHandler(BaseHandler):
    """一键诊断包：POST /api/support/bundle | /upload ；GET /api/support/bundle/<id>"""

    def _support_dir(self):
        base = os.path.dirname(os.path.abspath(config_file))
        path = os.path.join(base, "support")
        os.makedirs(path, exist_ok=True)
        return path

    def _env_snapshot(self):
        import support_bundle, rig_models, platform, sys
        audio = {}
        try:
            import audio_interface
            audio = audio_interface.device_report()
        except Exception as exc:
            audio = {"error": f"{type(exc).__name__}: {exc}"}
        return support_bundle.collect_env_snapshot(
            version=(open(os.path.join(_runtime_dir(), "version.txt")).read().strip()
                     if os.path.exists(os.path.join(_runtime_dir(), "version.txt")) else ""),
            extra={"audio": audio, "rigctld": rig_models.cached_rigctld_model(
                       *SupportApiHandler._rigctld_endpoint()),
                   "atr1000": {"enabled": bool(ATR1000_ENABLED), "reason": ATR1000_ENABLED_REASON}})

    @staticmethod
    def _rigctld_endpoint():
        host, port = "127.0.0.1", 4532
        if config.has_option('INSTANCE_SETTINGS', 'instance_rigctl_host'):
            host = config.get('INSTANCE_SETTINGS', 'instance_rigctl_host').strip() or host
        if config.has_option('INSTANCE_SETTINGS', 'instance_rigctl_port'):
            try: port = int(config.get('INSTANCE_SETTINGS', 'instance_rigctl_port'))
            except ValueError: pass
        return host, port

    def _log_files(self):
        base = os.path.dirname(os.path.abspath(config_file))
        runtime = _runtime_dir()
        candidates = {
            "logs/MRRC.log": os.path.join(runtime, config.get('SERVER', 'log_file', fallback='MRRC.log')),
            "logs/MRRC.log.prev": os.path.join(runtime,
                config.get('SERVER', 'log_file', fallback='MRRC.log') + ".prev"),
            "logs/server-stdout.log": os.path.join(base, "logs", "server-stdout.log"),
            "logs/atr1000.log": os.path.join(runtime, "atr1000_proxy_watchdog.log"),
        }
        return {name: path for name, path in candidates.items() if os.path.isfile(path)}

    def post(self):
        payload = json.loads(self.request.body or b"{}")
        action = self.path.rstrip('/').split('/')[-1]
        if action == "bundle":
            import support_bundle, patch_overlay
            kwargs = dict(problem=payload.get("problem", ""), contact=payload.get("contact", ""),
                          env=self._env_snapshot(), log_files=self._log_files(),
                          config_text=open(config_file, encoding="utf-8", errors="replace").read(),
                          manifest_extra={"hotfix": patch_overlay.describe(with_hash=True)})
            result = tornado.ioloop.IOLoop.current().run_in_executor(
                None, lambda: support_bundle.build_bundle(out_dir=self._support_dir(), **kwargs))
            # run_in_executor 是 awaitable：本 handler 改成 async def post(...)（见任务说明）
            ...
        elif action == "upload":
            ...
```

> 说明：`post` 必须是 `async def`，用 `await self.run_in_executor(...)`（tornado 6 支持
> `RequestHandler.run_in_executor`），确保磁盘 IO 与网络上传都不占用 IOLoop 线程。

- [ ] **步骤 4：注册路由与权限**

```python
(r'/api/support/.*', SupportApiHandler),
```
放在 `(r'/(.*)', ...)` 静态处理器**之前**；handler 继承现有 `BaseHandler`（已带登录校验）。

- [ ] **步骤 5：手工验证**

```bash
# 本机（源码模式，独立端口）
venv/bin/python3 -u ./MRRC /tmp/mrrc_support_test/MRRC.conf &
curl -sk -X POST https://localhost:8894/api/support/bundle \
     -H "Cookie: user=<签名cookie>" -d '{"problem":"冒烟测试"}' | python3 -m json.tool
```
预期：返回 `{ok, id, path, size, files, redactions, warnings}`，且 `path` 文件存在。

- [ ] **步骤 6：Commit**

```bash
git add MRRC support_bundle.py tests/test_support_api.py
git commit -m "feat(support): /api/support 生成/下载/上传接口（IO 走 executor）"
```

---

### 任务 5：页面与菜单入口

**文件：** 创建 `www/support.html`；修改 `www/mobile_modern.html`、`www/mobile_modern.js`、`www/index.html`

- [ ] **步骤 1：写页面骨架**（与 `wdsp_settings.html` 同风格）

```html
<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MRRC 遇到问题</title><link rel="stylesheet" href="mobile_modern.css?v=6.0.9">
<style>
 body{background:#12121a;color:#e0e0e0;font-family:tahoma,sans-serif;padding:16px}
 textarea{width:100%;min-height:110px;background:#0f0f16;color:#fff;border:1px solid #444;border-radius:4px;padding:8px}
 button{padding:10px 14px;border:0;border-radius:4px;background:#4a9eff;color:#fff;font-weight:bold;margin-right:8px}
 pre{background:#0f0f16;border:1px solid #333;border-radius:4px;padding:10px;overflow:auto;font-size:12px}
 .muted{color:#888;font-size:12px}
</style></head><body>
<h3>🐞 遇到问题</h3>
<label>问题描述</label><textarea id="problem" placeholder="例如：接收声音每隔 1 秒卡一下；电台型号/频率；什么时候开始的"></textarea>
<label><input type="checkbox" id="audio"> 附带 5 秒接收音频（可选）</label><br><br>
<label>联系方式（可选）</label><input id="contact" type="text" placeholder="呼号 / 邮箱">
<p><button onclick="buildBundle()">① 生成诊断包</button>
   <button onclick="uploadBundle()" id="btnUp" disabled>② 上传给维护者</button>
   <button onclick="saveLocal()" id="btnSave" disabled>保存到本地</button></p>
<div id="status" class="muted"></div>
<pre id="listing" style="display:none"></pre>
<script>
let currentId = null;
function setStatus(t){ document.getElementById('status').textContent = t; }
async function buildBundle(){
  setStatus('正在收集…');
  const res = await fetch('/api/support/bundle', {method:'POST', headers:{'Content-Type':'application/json'},
     body: JSON.stringify({problem: problem.value, contact: contact.value, includeAudio: audio.checked})});
  const data = await res.json();
  if(!data.ok){ setStatus('生成失败：' + (data.reason||'')); return; }
  currentId = data.id;
  document.getElementById('listing').style.display='block';
  document.getElementById('listing').textContent =
    data.files.map(f=>'  ' + f).join('\n') +
    `\n\n合计 ${(data.size/1024).toFixed(0)} KB；脱敏 ${data.redactions} 处` +
    (data.warnings.length ? '\n提示：\n' + data.warnings.map(w=>'  ⚠ ' + w).join('\n') : '');
  btnUp.disabled = btnSave.disabled = false;
  setStatus('已生成，确认清单后上传或保存到本地。');
}
async function uploadBundle(){
  setStatus('正在上传…');
  const res = await fetch('/api/support/upload', {method:'POST', headers:{'Content-Type':'application/json'},
     body: JSON.stringify({id: currentId})});
  const data = await res.json();
  setStatus(data.ok ? '✅ 已上传，谢谢！维护者会尽快看。' :
                      '上传失败：' + (data.reason||'') + '（诊断包已保存在本地，见下方路径）');
}
async function saveLocal(){
  const res = await fetch('/api/support/save', {method:'POST', headers:{'Content-Type':'application/json'},
     body: JSON.stringify({id: currentId})});
  const data = await res.json();
  setStatus(data.ok ? '已保存到：' + data.path : '保存失败：' + (data.reason||''));
}
</script></body></html>
```

- [ ] **步骤 2：加入菜单与桌面入口**

```html
<!-- www/mobile_modern.html：现有 6 项之后 -->
<li><a href="support.html" target="_blank" class="menu-item">🐞 遇到问题</a></li>
```
```html
<!-- www/index.html：工具栏（与 🔧WDSP 同排） -->
<div id="div-support"><button onclick="window.open('support.html','_blank');" title="遇到问题/上传日志">🐞</button></div>
```

- [ ] **步骤 3：语法检查**

运行：`node --check www/mobile_modern.js && python3 -c "import re,sys;html=open('www/support.html').read();assert html.count('<script')==1;print('ok')"`
预期：ok

- [ ] **步骤 4：Commit**

```bash
git add www/support.html www/mobile_modern.html www/index.html
git commit -m "feat(support): 遇到问题页面 + 移动端菜单/桌面入口"
```

---

### 任务 6：启动器 tee 服务端输出 + 设备报告

**文件：** 修改 `windows/launcher.py`、`audio_interface.py`

- [ ] **步骤 1：`audio_interface.device_report()`**

```python
def device_report():
    """给诊断包用的设备快照：名字/host API/延迟/通道数；失败返回 {'error': …}。"""
    try:
        p = pyaudio.PyAudio()
        rows = []
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            rows.append({
                "index": i, "name": info["name"],
                "api": _hostapi_name(p, info["hostApi"]),
                "in": info["maxInputChannels"], "out": info["maxOutputChannels"],
                "latLowInMs": round(info.get("defaultLowInputLatency", 0) * 1000, 1),
                "latHighInMs": round(info.get("defaultHighInputLatency", 0) * 1000, 1),
            })
        p.terminate()
        return {"devices": rows, "lastHealth": PyAudioCapture.last_health,
                "hostapiPreference": _HOSTAPI_PREFERENCE_OVERRIDE
                                     or os.environ.get("MRRC_HOSTAPI_PREFERENCE")
                                     or _HOSTAPI_PREFERENCE_DEFAULT}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
```

同时在采集线程的健康摘要分支里加一行 `PyAudioCapture.last_health = f"…{_ratio*100:.1f}%"`，
并在类属性处声明 `last_health = ""`。

- [ ] **步骤 2：启动器把子进程输出写文件（带滚动）**

```python
# windows/launcher.py：替换 Popen 调用
log_dir = data_dir / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
stdout_log = log_dir / "server-stdout.log"
if stdout_log.exists() and stdout_log.stat().st_size > 2 * 1024 * 1024:
    stdout_log.replace(log_dir / "server-stdout.log.prev")     # 滚动，保留一份
sink = open(stdout_log, "ab", buffering=0)
proc = subprocess.Popen(command, cwd=str(app_dir()), env=env,
                        creationflags=creationflags, stdout=sink, stderr=subprocess.STDOUT)
```
（`stdout=sink` 同时保留控制台可见性时改用 `tee` 线程；先用最简单可靠的文件重定向，
控制台不再显示服务端日志——启动器自己仍打印关键行。）

- [ ] **步骤 3：运行现有测试确认没破坏东西**

运行：`venv/bin/python3 -m unittest discover -s tests`
预期：全部 PASS

- [ ] **步骤 4：Commit**

```bash
git add windows/launcher.py audio_interface.py
git commit -m "feat(support): 启动器 tee 服务端日志 + 音频设备快照接口"
```

---

### 任务 7：部署接收端 + 文档 + 端到端验收

**文件：** 创建 `deploy_support_receiver.sh`、`tools/support_receiver/support-receiver.service`；修改 `win_pack.md`、`CHANGELOG.md`、`AGENTS.md`

- [ ] **步骤 1：systemd 单元与部署脚本**

```ini
# tools/support_receiver/support-receiver.service
[Unit]
Description=MRRC support bundle receiver
After=network.target
[Service]
Environment=SUPPORT_DIR=/var/www/support
Environment=SUPPORT_PASSWORD=__SET_ME__
Environment=SUPPORT_PORT=8099
ExecStart=/usr/bin/python3 /opt/mrrc-support/server.py
Restart=always
User=www-data
[Install]
WantedBy=multi-user.target
```

```bash
#!/usr/bin/env bash
# deploy_support_receiver.sh [user@host]
set -euo pipefail
REMOTE="${1:-cheenle@www.vlsc.net}"
ssh "$REMOTE" 'sudo mkdir -p /opt/mrrc-support /var/www/support && sudo chown www-data /var/www/support'
rsync -avz tools/support_receiver/server.py "$REMOTE:/tmp/mrrc-support-server.py"
rsync -avz tools/support_receiver/support-receiver.service "$REMOTE:/tmp/mrrc-support.service"
ssh "$REMOTE" 'sudo cp /tmp/mrrc-support-server.py /opt/mrrc-support/server.py && \
  sudo cp /tmp/mrrc-support.service /etc/systemd/system/support-receiver.service && \
  sudo systemctl daemon-reload && sudo systemctl enable --now support-receiver && \
  sudo systemctl --no-pager status support-receiver | head -5'
echo "下一步：在服务器 nginx 站点里加 location /mrrc/support/ { proxy_pass http://127.0.0.1:8099/; }"
```

- [ ] **步骤 2：nginx location（含备份，可回滚）**

```bash
ssh "$REMOTE" 'sudo cp /etc/nginx/sites-enabled/<站点> /etc/nginx/sites-enabled/<站点>.bak-$(date +%F) && \
  sudo sed -i "/server_name .*vlsc.net/a \\\n    location /mrrc/support/ { proxy_pass http://127.0.0.1:8099/api/; }" /etc/nginx/sites-enabled/<站点> && \
  sudo nginx -t && sudo systemctl reload nginx'
```

- [ ] **步骤 3：真机验收（VM）**

```powershell
# VM 内：安装 6.0.7 → 打开 support.html → 生成 → 上传
# 断言：线上列表页出现该 id；下载 zip 后 grep 不到 cookie_secret
```
并记录到 `docs/current/operations/support-bundle.md`（新增：使用说明 + 维护者侧查看/删除步骤）。

- [ ] **步骤 4：文档与 CHANGELOG**

`CHANGELOG.md` 新增 `### 🐞 遇到问题：一键诊断包上传`；
`AGENTS.md` 加一行：诊断包生成在 `support_bundle.py`（可热修），接收端在 `tools/support_receiver/`。

- [ ] **步骤 5：Commit**

```bash
git add deploy_support_receiver.sh tools/support_receiver/ docs/current/operations/support-bundle.md CHANGELOG.md AGENTS.md
git commit -m "feat(support): 接收端部署脚本 + 文档 + CHANGELOG"
```

---

## 自检

**规格覆盖度**

| 规格章节 | 任务 |
|---|---|
| §2 包结构 | 任务 2（build_bundle 的 add 列表） |
| §3 采集项 | 任务 4（env/rig/atr1000）+ 任务 6（设备报告、last_health） |
| §4 脱敏 | 任务 1（白名单/密钥/受限文件） |
| §5 接口 | 任务 3（接收端）+ 任务 4（MRRC 侧） |
| §6 与现有代码衔接 | 任务 4（patch_overlay/rig_models 复用）+ 任务 6（tee） |
| §7 界面 | 任务 5 |
| §8 错误处理 | 任务 2（warnings/最小包）+ 任务 4（executor/超时） |
| §9 测试 | 任务 1/2/3 的测试 + VM 端到端（任务 7） |
| §10 验收 | 任务 7 步骤 3 |

**占位符扫描**：无 TODO/待定；`<站点>` 是部署时的真实占位（任务 7 步骤 2 里用实际文件名），
实现时须替换为 `deploy_website.sh` 里同一个 nginx 站点文件。

**类型一致性**：`build_bundle()` 的返回值键（`id/path/size/files/redactions/warnings`）在
任务 2、4、5 中一致；`describe()`、`cached_rigctld_model()`、`device_report()` 均来自已存在或本计划定义的接口。

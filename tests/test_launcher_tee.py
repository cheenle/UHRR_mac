"""启动器日志 tee 的单元测试（任务 6）。

诊断包要能带上服务端启动期输出（PyInstaller/依赖/WDSP 加载报错都只在 stdout），
所以启动器需要：既转发到自己的控制台，又落盘一份并滚动。
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_launcher():
    spec = importlib.util.spec_from_file_location("mrrc_launcher", REPO / "windows" / "launcher.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TeeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.launcher = load_launcher()

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mrrc-tee-")
        self.log = os.path.join(self.tmp, "server-stdout.log")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_child(self, script, log_path=None, max_bytes=None):
        proc = subprocess.Popen([sys.executable, "-u", "-c", script],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        args = [proc, log_path or self.log]
        if max_bytes is not None:
            args.append(max_bytes)
        lines = self.launcher.tee_child_output(*args)
        return proc.wait(timeout=10), lines

    def test_writes_and_forwards(self):
        code, captured = self._run_child("print('hello-bin'); print('second')")
        self.assertEqual(code, 0)
        content = open(self.log, encoding="utf-8").read()
        self.assertIn("hello-bin", content)
        self.assertIn("second", content)
        joined = "".join(captured)
        self.assertIn("hello-bin", joined, "控制台仍要能看到（大屏习惯）")

    def test_unicode_and_emoji_survive(self):
        self._run_child("print('\\U0001F9E9 补丁覆盖层已启用: test')")
        content = open(self.log, encoding="utf-8").read()
        self.assertIn("🧩", content)
        self.assertIn("补丁覆盖层已启用", content)

    def test_safe_print_survives_gbk_console(self):
        """Windows 控制台默认 GBK：转发带 emoji 的服务端日志不能让线程崩
        （6.1.0 端到端实测：UnicodeEncodeError 杀死 server-stdout-tee → 日志断更）。"""

        class GbkStdout:
            encoding = "gbk"

            def __init__(self):
                self.written = []

            def write(self, text):
                text.encode("gbk")        # 模拟 GBK 控制台：emoji 直接抛
                self.written.append(text)

            def flush(self):
                pass

        fake = GbkStdout()
        old = sys.stdout
        sys.stdout = fake
        try:
            self.launcher._safe_print("🔍 音频设备枚举 48kHz")     # 不得抛异常
        finally:
            sys.stdout = old
        self.assertTrue(fake.written, "降级后仍应写出可编码的文本")
        self.assertIn("?", "".join(fake.written))

    def test_force_utf8_stdio_sets_child_encoding(self):
        old_pio = os.environ.pop("PYTHONIOENCODING", None)
        try:
            self.launcher._force_utf8_stdio()
            self.assertEqual(os.environ.get("PYTHONIOENCODING"), "utf-8")
        finally:
            if old_pio is None:
                os.environ.pop("PYTHONIOENCODING", None)
            else:
                os.environ["PYTHONIOENCODING"] = old_pio

    def test_rolls_when_exceeding_limit(self):
        open(self.log, "w", encoding="utf-8").write("x" * 500)
        self._run_child("print('after-roll')", max_bytes=200)
        self.assertTrue(os.path.exists(self.log + ".prev"), "超限要滚动出 .prev")
        self.assertIn("x" * 500, open(self.log + ".prev", encoding="utf-8").read())
        self.assertIn("after-roll", open(self.log, encoding="utf-8").read())

    def test_survives_missing_directory(self):
        """日志目录不存在时不抛异常（只丢日志）。"""
        code, _ = self._run_child("print('ok')", log_path=os.path.join(self.tmp, "nope", "x.log"))
        self.assertEqual(code, 0)


class UpgradeRobustnessTest(unittest.TestCase):
    """升级健壮性：6.1.0 端到端实测暴露的两个 Windows 陷阱。"""

    @classmethod
    def setUpClass(cls):
        cls.launcher = load_launcher()

    def test_installer_forces_close_and_stops_server_first(self):
        """安装器替换被占用的 exe/dll 会「DeleteFile failed; code 5」——
        必须升级前先停服务 + 命令里强关占用进程。"""
        import inspect
        src = inspect.getsource(self.launcher.run_upgrade)
        self.assertIn("FORCECLOSEAPPLICATIONS", src)
        self.assertIn("_stop_server_for_upgrade()", src)

    def test_stop_server_for_upgrade_really_stops_child(self):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        old = self.launcher._SERVER_PROC
        self.launcher._SERVER_PROC = proc
        try:
            self.launcher._stop_server_for_upgrade(timeout=10)
            self.assertIsNotNone(proc.poll(), "升级前必须真的把服务停掉")
        finally:
            self.launcher._SERVER_PROC = old
            if proc.poll() is None:
                proc.kill()

    def test_stop_server_tolerates_no_child(self):
        old = self.launcher._SERVER_PROC
        self.launcher._SERVER_PROC = None
        try:
            self.launcher._stop_server_for_upgrade(timeout=1)   # 不得抛异常
        finally:
            self.launcher._SERVER_PROC = old

    def test_installer_has_elevated_direct_run_path(self):
        """已提权时必须直跑安装器：ShellExecuteW(runas) 在非交互窗口站会永远卡住
        （6.1.0 实测：哨兵被消费、无 UAC 弹窗、无安装日志）。"""
        import inspect
        src = inspect.getsource(self.launcher.run_upgrade)
        self.assertIn("_is_elevated()", src)
        self.assertIn("_exit_for_upgrade()", src)
        self.assertIn("subprocess.Popen", src)

    def test_is_elevated_is_bool(self):
        self.assertIsInstance(self.launcher._is_elevated(), bool)

    def test_confirm_pending_upgrade_marks_ok_and_clears(self):
        """安装后首次启动确认：写 ok + 清状态 + 删暂存包（升级时启动器已自行退出）。"""
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "updates").mkdir(parents=True)
            pkg = data / "updates" / "MRRC-Setup-6.1.2.exe"
            pkg.write_bytes(b"x")
            (data / "updates" / "state.json").write_text(json.dumps({
                "staged": {"version": "6.1.2", "path": str(pkg), "sha256": "a" * 64,
                           "size": 1, "at": "t"}}), encoding="utf-8")
            app = data / "app"
            app.mkdir()
            (app / "version.txt").write_text("6.1.2", encoding="utf-8")
            old = self.launcher.app_dir
            self.launcher.app_dir = lambda: app
            try:
                self.launcher.confirm_pending_upgrade(data)
            finally:
                self.launcher.app_dir = old
            state = json.loads((data / "updates" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["lastResult"]["status"], "ok")
            self.assertIsNone(state.get("staged"))
            self.assertFalse(pkg.exists(), "确认成功后应删掉暂存安装包")

    def test_confirm_pending_upgrade_handles_not_upgraded(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "updates").mkdir(parents=True)
            (data / "updates" / "state.json").write_text(json.dumps({
                "staged": {"version": "9.9.9", "path": "C:/nope.exe", "at": "t"}}),
                encoding="utf-8")
            app = data / "app"
            app.mkdir()
            (app / "version.txt").write_text("6.1.2", encoding="utf-8")
            old = self.launcher.app_dir
            self.launcher.app_dir = lambda: app
            try:
                self.launcher.confirm_pending_upgrade(data)      # 不得抛异常
            finally:
                self.launcher.app_dir = old


class UpgradeWatcherTest(unittest.TestCase):
    """watch_upgrade：页面按钮写的是具体版本号，没暂存时必须自己下载；失败不能丢请求。

    2026-09-16 VM 端到端实测：哨兵比下载早到 1 分钟 → 只记 missing_staged → 升级被静默丢弃。
    """

    def setUp(self):
        self.launcher = load_launcher()
        self.tmp = Path(tempfile.mkdtemp())
        self._saved = []

    def tearDown(self):
        for obj, name, old in reversed(self._saved):
            setattr(obj, name, old)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _patch(self, obj, name, value):
        self._saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    def test_specific_version_downloads_then_installs(self):
        import upgrade_core as uc
        calls = []
        info = {"available": True, "version": "6.1.4", "url": "https://x/a.exe",
                "sha256": "a" * 64, "size": 10}
        self._patch(uc, "fetch_manifest", lambda *a, **k: ({"latest": "6.1.4"}, None))
        self._patch(uc, "plan_upgrade", lambda installed, man, **k: {"installer": info})
        self._patch(uc, "staged_matches", lambda state, v, s: False)
        self._patch(uc, "download_installer",
                    lambda url, sha, base, version: calls.append(("dl", version)) or {"ok": True, "size": 10})
        self._patch(self.launcher, "_installed_version", lambda: "6.1.3")
        self._patch(self.launcher, "run_upgrade",
                    lambda base, v: calls.append(("run", v)) or "installing")
        self._patch(self.launcher, "_exit_for_upgrade", lambda *a, **k: calls.append(("exit", "")))
        uc.write_upgrade_request(self.tmp, "6.1.4")
        self.launcher.watch_upgrade(self.tmp, "", 0.01, "")          # 会 return（不能挂住）
        self.assertIn(("dl", "6.1.4"), calls, "具体版本号也必须先下载")
        self.assertIn(("run", "6.1.4"), calls, "下载完必须真的执行升级")
        self.assertIn(("exit", ""), calls, "拉起安装器后要走受控退出")

    def test_main_blocked_normally_while_upgrading(self):
        """升级中主线程不能正常退出：否则解释器收尾会 Fatal Python error 打断安装。"""
        import inspect
        src = inspect.getsource(self.launcher.main)
        self.assertIn("_UPGRADING.is_set()", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)

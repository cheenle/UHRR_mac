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


if __name__ == "__main__":
    unittest.main(verbosity=2)

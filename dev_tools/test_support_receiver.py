"""接收端（tools/support_receiver/server.py）的本地全流程测试。

真实起进程、真实 HTTP：create → PUT bundle → 带密码 list/下载；并验证
限速、超限、越权 id 与路径穿越都被拒绝。运行：python3 dev_tools/test_support_receiver.py -v
"""

import base64
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(REPO, "tools", "support_receiver", "server.py")


class ReceiverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = tempfile.mkdtemp(prefix="mrrc-support-store-")
        env = dict(os.environ, SUPPORT_DIR=cls.store, SUPPORT_PASSWORD="pw",
                   SUPPORT_PORT="0", SUPPORT_MAX_MB="1")
        cls.proc = subprocess.Popen([sys.executable, SERVER], env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        line = cls.proc.stdout.readline()
        m = re.search(r"on (\S+:\d+)", line)
        if not m:
            raise RuntimeError(f"接收端未启动：{line!r}")
        cls.host, cls.port = m.group(1).split(":")
        cls.base = f"http://{cls.host}:{cls.port}"
        cls.debug_proc = cls.proc

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.proc.kill()

    # ---- 工具 ----
    def _create(self):
        req = urllib.request.Request(self.base + "/api/create", data=json.dumps(
            {"problem": "声音卡顿", "version": "6.0.7", "contact": "BG1SB"}).encode(),
            headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=10).read())

    def _put(self, rid, payload=b"PK\x03\x04fakedata"):
        req = urllib.request.Request(self.base + f"/api/{rid}/bundle", data=payload, method="PUT")
        return urllib.request.urlopen(req, timeout=10)

    def _auth(self):
        return {"Authorization": "Basic " + base64.b64encode(b"mrrc:pw").decode()}

    # ---- 正向流程 ----
    def test_01_full_flow(self):
        created = self._create()
        self.assertTrue(created["ok"])
        rid = created["id"]
        self.assertRegex(rid, r"^\d{8}-\d{6}-[0-9a-f]{4}$")
        self.assertEqual(self._put(rid).status, 200)
        self.assertTrue(os.path.isfile(os.path.join(self.store, rid, "bundle.zip")))
        listing = urllib.request.urlopen(urllib.request.Request(
            self.base + "/api/list", headers=self._auth()), timeout=10).read().decode()
        self.assertIn(rid, listing)
        self.assertIn("声音卡顿", listing)          # 列表页要能直接看到问题描述
        data = urllib.request.urlopen(urllib.request.Request(
            self.base + f"/api/{rid}/bundle", headers=self._auth()), timeout=10).read()
        self.assertEqual(data, b"PK\x03\x04fakedata")

    def test_02_list_requires_password(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.base + "/api/list", timeout=10)
        self.assertEqual(ctx.exception.code, 401)
        bad = {"Authorization": "Basic " + base64.b64encode(b"mrrc:wrong").decode()}
        with self.assertRaises(urllib.error.HTTPError) as ctx2:
            urllib.request.urlopen(urllib.request.Request(
                self.base + "/api/list", headers=bad), timeout=10)
        self.assertEqual(ctx2.exception.code, 401)

    def test_03_bad_and_unknown_ids(self):
        for bad in ("../../etc", "20260916-000000-ZZZZ", "x"):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self._put(bad, b"data")
            self.assertIn(ctx.exception.code, (400, 404), bad)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._put("20260916-000000-abcd", b"data")       # 合法格式但未 create
        self.assertEqual(ctx.exception.code, 404)

    def test_04_raw_path_traversal_rejected(self):
        """绕过 urllib 的规范化，直接发原始请求行，验证服务端自己的守卫。"""
        with socket.create_connection((self.host, int(self.port)), timeout=5) as sock:
            body = b"data"
            sock.sendall(b"PUT /api/../../../etc/passwd/bundle HTTP/1.1\r\n"
                         b"Host: x\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
            resp = sock.recv(200).decode("latin-1")
        self.assertRegex(resp.splitlines()[0], r"400|404")
        self.assertFalse(os.path.exists("/tmp/passwd"))

    def test_05_size_limit(self):
        rid = self._create()["id"]
        big = b"x" * (2 * 1024 * 1024)               # SUPPORT_MAX_MB=1
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._put(rid, big)
        self.assertEqual(ctx.exception.code, 413)
        self.assertFalse(os.path.exists(os.path.join(self.store, rid, "bundle.zip")))

    def test_06_rate_limit(self):
        codes = []
        for _ in range(8):
            try:
                self._create()
                codes.append(200)
            except urllib.error.HTTPError as exc:
                codes.append(exc.code)
        self.assertIn(429, codes, "短时间大量 create 必须被限速")


if __name__ == "__main__":
    unittest.main(verbosity=2)

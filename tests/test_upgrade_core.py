"""一键升级纯逻辑的单元测试（任务 1/2）。

重点：版本决策（拒绝降级 / requires 门禁）、原子下载与 SHA256 校验、状态与哨兵文件。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import upgrade_core as uc  # noqa: E402

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
        self.assertEqual(uc.version_tuple(""), (0,))


class DecisionTest(unittest.TestCase):
    def test_installer_upgrade_available(self):
        plan = uc.plan_upgrade("6.0.10", MANIFEST)
        self.assertTrue(plan["installer"]["available"])
        self.assertEqual(plan["installer"]["version"], "6.1.0")
        self.assertFalse(plan["installer"]["mandatory"])
        self.assertEqual(plan["notes"], "x")

    def test_no_action_when_up_to_date_or_newer(self):
        for installed in ("6.1.0", "6.1.1", "7.0"):
            plan = uc.plan_upgrade(installed, MANIFEST)
            self.assertFalse(plan["installer"]["available"], installed)
            self.assertFalse(plan["hotfix"]["available"], installed)

    def test_hotfix_requires_gate(self):
        blocked = uc.plan_upgrade("6.0.2", MANIFEST)
        self.assertFalse(blocked["hotfix"]["available"])
        self.assertTrue(blocked["hotfix"]["blockedReason"])
        allowed = uc.plan_upgrade("6.0.10", MANIFEST)
        self.assertTrue(allowed["hotfix"]["available"])

    def test_applied_hotfix_not_reoffered(self):
        plan = uc.plan_upgrade("6.0.10", MANIFEST, applied_hotfixes={"6.1.0"})
        self.assertFalse(plan["hotfix"]["available"])

    def test_missing_sections_tolerated(self):
        plan = uc.plan_upgrade("6.0.10", {"latest": "6.1.0"})
        self.assertFalse(plan["installer"]["available"])
        self.assertFalse(plan["hotfix"]["available"])
        self.assertFalse(plan["previous"]["available"])
        plan_none = uc.plan_upgrade("6.0.10", None)
        self.assertFalse(plan_none["installer"]["available"])

    def test_previous_for_rollback(self):
        plan = uc.plan_upgrade("6.1.0", MANIFEST)
        self.assertTrue(plan["previous"]["available"])
        self.assertEqual(plan["previous"]["version"], "6.0.10")


class DownloadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import hashlib
        import http.server
        import socketserver
        import threading
        cls.payload = b"PK\x03\x04 fake installer " * 100
        cls.sha = hashlib.sha256(cls.payload).hexdigest()
        payload = cls.payload

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *a):
                pass

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
        self.assertTrue(result["ok"], result)
        self.assertTrue(os.path.isfile(result["path"]))
        self.assertFalse(os.path.exists(result["path"] + ".part"), "不得残留 .part")
        state = uc.read_state(self.tmp)
        self.assertEqual(state["staged"]["version"], "6.1.0")
        self.assertEqual(state["staged"]["sha256"], self.sha)
        self.assertTrue(uc.staged_matches(state, "6.1.0", self.sha))
        self.assertFalse(uc.staged_matches(state, "6.0.10", self.sha), "版本不符不算就绪")

    def test_sha_mismatch_discards_download(self):
        result = uc.download_installer(self.url, "0" * 64, self.tmp, version="6.1.0")
        self.assertFalse(result["ok"])
        self.assertIn("sha256", result["reason"])
        self.assertFalse(os.path.exists(result["path"]))
        self.assertFalse(os.path.exists(result["path"] + ".part"))
        self.assertEqual(uc.read_state(self.tmp).get("staged"), None, "失败不得留下 staged")
        self.assertEqual(uc.read_state(self.tmp)["lastResult"]["status"], "sha_mismatch")

    def test_download_failure_is_recorded(self):
        result = uc.download_installer("http://127.0.0.1:1/none.exe", self.sha, self.tmp, version="6.1.0")
        self.assertFalse(result["ok"])
        self.assertEqual(uc.read_state(self.tmp)["lastResult"]["status"], "download_failed")

    def test_request_file_roundtrip(self):
        uc.write_upgrade_request(self.tmp, "6.1.0")
        self.assertEqual(uc.read_upgrade_request(self.tmp)["version"], "6.1.0")
        uc.clear_upgrade_request(self.tmp)
        self.assertIsNone(uc.read_upgrade_request(self.tmp))

    def test_record_result(self):
        uc.record_result(self.tmp, "uac_denied", version="6.1.0", detail="user cancelled")
        last = uc.read_state(self.tmp)["lastResult"]
        self.assertEqual(last["status"], "uac_denied")
        self.assertEqual(last["version"], "6.1.0")
        self.assertIn("cancelled", last["detail"])

    def test_installer_filename_has_version(self):
        self.assertEqual(uc.installer_filename("6.1.0"), "MRRC-Setup-6.1.0.exe")


if __name__ == "__main__":
    unittest.main(verbosity=2)

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

    def test_bom_tolerated(self):
        """带 BOM 的 JSON 必须能读：记事本 / PowerShell(Set-Content -Encoding utf8) 默认写 BOM，
        而 json.load 遇 BOM 直接抛错 → 升级被静默忽略（6.1.0 端到端实测）。"""
        with open(uc.request_path(self.tmp), "w", encoding="utf-8-sig") as fh:
            fh.write('{"version": "6.1.0", "at": "x"}')
        self.assertEqual(uc.read_upgrade_request(self.tmp)["version"], "6.1.0")
        with open(uc.state_path(self.tmp), "w", encoding="utf-8-sig") as fh:
            fh.write('{"staged": {"version": "6.1.0"}}')
        self.assertEqual(uc.read_state(self.tmp)["staged"]["version"], "6.1.0")

    def test_record_result(self):
        uc.record_result(self.tmp, "uac_denied", version="6.1.0", detail="user cancelled")
        last = uc.read_state(self.tmp)["lastResult"]
        self.assertEqual(last["status"], "uac_denied")
        self.assertEqual(last["version"], "6.1.0")
        self.assertIn("cancelled", last["detail"])

    def test_download_busy_does_not_block_forever(self):
        """锁被占用时必须立刻返回 busy，不能无限等：VM 实测后台预下载卡死时
        升级看护线程被一起拖死，用户点【立即升级】毫无反应。"""
        target = os.path.join(uc.updates_dir(self.tmp), uc.installer_filename("6.1.9"))
        uc._DOWNLOAD_LOCK.acquire()
        try:
            result = uc.download_installer("https://x/a.exe", "a" * 64, self.tmp, "6.1.9")
        finally:
            uc._DOWNLOAD_LOCK.release()
        self.assertFalse(result["ok"])
        self.assertIn("busy", result["reason"])
        self.assertFalse(os.path.exists(target))

    def test_installer_filename_has_version(self):
        self.assertEqual(uc.installer_filename("6.1.0"), "MRRC-Setup-6.1.0.exe")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class MakeLatestJsonTest(unittest.TestCase):
    """升级清单生成器（发布流程用）：sha256 必须对应带版本名的产物。"""

    def setUp(self):
        import importlib.util
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="mrrc-manifest-")
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "dev_tools", "make_latest_json.py")
        spec = importlib.util.spec_from_file_location("make_latest_json", path)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.exe = os.path.join(self.tmp, "MRRC-Setup.exe")
        with open(self.exe, "wb") as fh:
            fh.write(b"PK\x03\x04 fake")

    def test_manifest_uses_versioned_name_and_hash(self):
        import json
        manifest = self.mod.build_manifest("6.0.10", self.exe, self.tmp, notes="x")
        self.assertEqual(manifest["latest"], "6.0.10")
        self.assertTrue(manifest["installer"]["url"].endswith("MRRC-Setup-6.0.10.exe"))
        self.assertEqual(manifest["installer"]["sha256"], self.mod.sha256_file(self.exe))
        self.assertEqual(manifest["installer"]["size"], os.path.getsize(self.exe))
        self.assertNotIn("hotfix", manifest)
        self.assertNotIn("previous", manifest)

    def test_hotfix_and_previous_sections(self):
        import json
        json.dump({"url": "https://x/h.zip", "sha256": "a" * 64, "requires": "6.0.3",
                   "notes": "h"}, open(os.path.join(self.tmp, "patch.json"), "w"))
        with open(os.path.join(self.tmp, "MRRC-Setup-6.0.7.exe"), "wb") as fh:
            fh.write(b"old")
        manifest = self.mod.build_manifest("6.0.10", self.exe, self.tmp, previous="6.0.7")
        self.assertEqual(manifest["hotfix"]["sha256"], "a" * 64)
        self.assertEqual(manifest["previous"]["version"], "6.0.7")
        self.assertEqual(manifest["previous"]["sha256"], self.mod.sha256_file(
            os.path.join(self.tmp, "MRRC-Setup-6.0.7.exe")))

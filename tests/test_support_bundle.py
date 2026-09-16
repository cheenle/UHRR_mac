"""支持诊断包（support bundle）的单元测试。

重点在**安全**：密钥绝不能进包、白名单外的配置键不出现、用户库与证书永不打包。
运行：python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import support_bundle as sb  # noqa: E402


class RedactionTest(unittest.TestCase):
    def test_secret_values_replaced(self):
        text = "cookie_secret = L8LwECiNxyz\npassword: hunter2\napikey=abc123\nnormal=1"
        out, hits = sb.redact_text(text)
        self.assertNotIn("L8LwECiNxyz", out)
        self.assertNotIn("hunter2", out)
        self.assertNotIn("abc123", out)
        self.assertIn("<redacted>", out)
        self.assertIn("normal=1", out, "普通键不该被动")
        self.assertGreaterEqual(hits, 3)

    def test_config_keeps_whitelist_only(self):
        cfg = ("[SERVER]\nport = 8877\ncookie_secret = SECRET_VALUE\n"
               "[AUDIO]\ninputdevice = USB Audio\n"
               "[HAMLIB]\nrig_model = IC-M710\nrig_pathname = COM3\n"
               "[SECRETS]\ntoken = abc\n")
        out = sb.redact_config_text(cfg)
        self.assertIn("port = 8877", out)
        self.assertIn("rig_model = IC-M710", out)
        self.assertIn("inputdevice = USB Audio", out)
        self.assertNotIn("SECRET_VALUE", out)
        self.assertNotIn("cookie_secret", out)
        self.assertNotIn("abc", out, "白名单外的节整节丢弃")
        self.assertNotIn("[SECRETS]", out)

    def test_forbidden_files_never_included(self):
        for name in ("MRRC_users.db", "certs/fullchain.pem", "x.key", "server.crt", "a.p12"):
            self.assertFalse(sb.is_collectable(name), name)
        for name in ("logs/MRRC.log", "state/config-redacted.ini", "diagnostics/env.json"):
            self.assertTrue(sb.is_collectable(name), name)

    def test_tail_lines_aligns_and_bounds(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "big.log")
            with open(path, "w", encoding="utf-8") as fh:
                for i in range(20000):
                    fh.write(f"line-{i:06d}-{'x' * 60}\n")
            text = sb.tail_lines(path, max_bytes=4096)
            self.assertLessEqual(len(text.encode()), 4096 + 100)
            self.assertTrue(text.startswith("line-"), "应落在完整行边界上")
            self.assertNotIn("line-000000", text, "必须只保留尾部")

    def test_tail_lines_missing_file_is_empty(self):
        self.assertEqual(sb.tail_lines("/nonexistent/path/xyz.log"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class BundleTest(unittest.TestCase):
    """打包与自动体检摘要（任务 2）。"""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="sb-bundle-")
        self.log = os.path.join(self.tmp, "MRRC.log")
        with open(self.log, "w", encoding="utf-8") as fh:
            fh.write("普通行\n")
            fh.write("Traceback (most recent call last):\n" * 3)
            fh.write("2026-09-16 ERROR 电台无响应\n")
            fh.write("🎧 音频健康: 30s 采集 1430000 样本（应有 1440000，98.5%）  ⚠ 明显跟不上\n")
            fh.write("补丁覆盖层已启用: xxx\nWDSP 库加载成功\n")

    def test_bundle_contains_expected_files_and_no_secrets(self):
        import json as _json
        import zipfile
        result = sb.build_bundle(
            out_dir=self.tmp, problem="接收声音每秒卡一下",
            contact="BG1SB", env={"version": "6.0.7", "platform": "Windows-11"},
            log_files={"logs/MRRC.log": self.log},
            config_text="[SERVER]\nport = 8877\ncookie_secret = TOP_SECRET\n"
                        "[AUDIO]\ninputdevice = USB Audio CODEC\n")
        self.assertTrue(os.path.isfile(result["path"]))
        self.assertEqual(result["id"], os.path.basename(result["path"]).split("support-")[1][:-4])
        with zipfile.ZipFile(result["path"]) as z:
            names = set(z.namelist())
            for expected in ("manifest.json", "README.txt", "problem.txt",
                             "diagnostics/summary.txt", "diagnostics/env.json",
                             "state/config-redacted.ini", "logs/MRRC.log"):
                self.assertIn(expected, names)
            blob = b"".join(z.read(n) for n in names)
            self.assertNotIn(b"TOP_SECRET", blob, "密钥绝不能进包")
            self.assertNotIn(b"cookie_secret", blob)
            self.assertIn(b"USB Audio CODEC", blob, "白名单内的键要保留")
            summary = z.read("diagnostics/summary.txt").decode("utf-8")
            self.assertIn("Traceback", summary)
            self.assertIn("98.5", summary)
            self.assertIn("音频采集", summary)
            manifest = _json.loads(z.read("manifest.json"))
            self.assertEqual(manifest["problem"], "接收声音每秒卡一下")
            self.assertGreaterEqual(manifest["redactions"], 1)
            self.assertEqual(manifest["warnings"], [])

    def test_missing_log_yields_warning_and_minimal_bundle(self):
        result = sb.build_bundle(out_dir=self.tmp, problem="", contact="", env={},
                                 log_files={"logs/MRRC.log": os.path.join(self.tmp, "nope.log")},
                                 config_text="")
        self.assertTrue(result["warnings"], "缺日志要给出 warnings")
        self.assertTrue(os.path.isfile(result["path"]))

    def test_forbidden_log_names_are_skipped(self):
        result = sb.build_bundle(out_dir=self.tmp, problem="", contact="", env={},
                                 log_files={"certs/server.key": self.log}, config_text="")
        self.assertTrue(any("受限" in w for w in result["warnings"]))

    def test_collect_env_snapshot_shape(self):
        snap = sb.collect_env_snapshot(version="6.0.7", extra={"audio": {"api": "Windows WASAPI"}})
        for key in ("version", "platform", "python", "frozen", "cpuCount", "audio"):
            self.assertIn(key, snap)
        self.assertEqual(snap["audio"]["api"], "Windows WASAPI")


class WindowsEditorCompatTest(unittest.TestCase):
    """Windows 记事本/PS 保存 UTF-8 会带 BOM —— 配置读取必须容忍（否则服务器起不来）。"""

    def test_bom_config_is_readable(self):
        import tempfile
        import config_io
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "MRRC.conf")
            with open(path, "w", encoding="utf-8-sig") as fh:      # 带 BOM
                fh.write("[SERVER]\nport = 8877\ncookie_secret = x\n"
                         "[AUDIO]\ninputdevice = USB Audio CODEC\n")
            self.assertEqual(open(path, "rb").read(3), b"\xef\xbb\xbf")
            cfg = __import__("configparser").ConfigParser()
            encoding = config_io.read_config(cfg, path)
            self.assertEqual(cfg.get("SERVER", "port"), "8877")
            self.assertEqual(cfg.get("AUDIO", "inputdevice"), "USB Audio CODEC")
            # 迁移到无 BOM 的 UTF-8 后仍可用（config_io.should_migrate 的判定不得乱动）
            if config_io.should_migrate(encoding):
                config_io.write_config(cfg, path)
                cfg2 = __import__("configparser").ConfigParser()
                config_io.read_config(cfg2, path)
                self.assertEqual(cfg2.get("SERVER", "port"), "8877")

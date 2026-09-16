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

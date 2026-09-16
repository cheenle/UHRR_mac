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

    def test_summary_distinguishes_restarts_from_crashes(self):
        """真实案例（上报 20260917-062314-35dc）：用户以为"总是异常停止"，
        其实是 25 次正常启动、0 条 Traceback（升级本身就会重启）。摘要必须一眼说清。"""
        import support_bundle as sb
        log = "\n".join([
            "2026-09-16 08:12:32,100 - MRRC - WARNING - x",
            "HTTP server started.",
            "2026-09-16 09:12:32,100 - MRRC - WARNING - x",
            "HTTP server started.",
            "❌ 音频初始化失败: [Errno -9996] Invalid input device (no default output device)",
        ])
        out = sb.summarize_log(log, freshness_hours=0.02)
        self.assertIn("启动次数：2 次", out)
        self.assertIn("无崩溃痕迹", out)
        self.assertIn("时间跨度 2026-09-16 08:12:32 → 2026-09-16 09:12:32", out)
        self.assertIn("音频设备：Windows 报 -9996", out)

    def test_summary_flags_real_crashes(self):
        import support_bundle as sb
        log = "HTTP server started.\nTraceback (most recent call last):\n"
        out = sb.summarize_log(log, freshness_hours=0.1)
        self.assertIn("Traceback", out)
        self.assertIn("按崩溃排查", out)


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

    def test_stale_logs_are_flagged(self):
        """老日志（>24h）要在 warnings 与 summary 里显式提示，避免"拿错文件还得出没问题"。"""
        import time
        import zipfile
        stamp = time.time() - 3 * 86400
        os.utime(self.log, (stamp, stamp))
        result = sb.build_bundle(out_dir=self.tmp, problem="", contact="", env={},
                                 log_files={"logs/MRRC.log": self.log}, config_text="")
        self.assertTrue(any("过旧" in w for w in result["warnings"]), result["warnings"])
        with zipfile.ZipFile(result["path"]) as z:
            summary = z.read("diagnostics/summary.txt").decode("utf-8")
        self.assertIn("新鲜度", summary)

    def test_initial_warnings_are_merged(self):
        result = sb.build_bundle(out_dir=self.tmp, problem="", contact="", env={},
                                 log_files={"logs/MRRC.log": self.log}, config_text="",
                                 initial_warnings=["未找到本实例日志"])
        self.assertIn("未找到本实例日志", result["warnings"])


class LogResolutionTest(unittest.TestCase):
    """日志解析：必须拿"本实例正在写的"日志，而不是历史遗留文件。

    事故背景（2026-09-16）：多实例 radio1 上传的诊断包里塞的是 8-30 的 MRRC.log 与
    atr1000_proxy_watchdog.log，活日志 mrrc_radio1.log / atr1000_radio1.log 一个没进去，
    维护者据此得出"没问题"的错误结论。
    """

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="sb-logres-")
        self.log_dir = os.path.join(self.tmp, "runtime")
        self.base_dir = os.path.join(self.tmp, "base")
        os.makedirs(self.log_dir)
        os.makedirs(os.path.join(self.base_dir, "logs"))

    def _make(self, directory, name, age_days=0.0):
        import time
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"{name}\n")
        if age_days:
            stamp = time.time() - age_days * 86400
            os.utime(path, (stamp, stamp))
        return path

    def _names(self, resolved):
        return {os.path.basename(p) for p in resolved.values()}

    def test_named_instance_prefers_live_logs_over_legacy(self):
        self._make(self.log_dir, "MRRC.log", age_days=17)
        self._make(self.log_dir, "atr1000_proxy_watchdog.log", age_days=17)
        live_app = self._make(self.log_dir, "mrrc_radio1.log")
        live_rig = self._make(self.log_dir, "rigctld_radio1.log")
        live_atr = self._make(self.log_dir, "atr1000_radio1.log")
        got = sb.resolve_log_files(log_dir=self.log_dir, base_dir=self.base_dir,
                                   instance_name="radio1")
        self.assertEqual(got.get("app"), live_app)
        self.assertEqual(got.get("rigctld"), live_rig)
        self.assertEqual(got.get("atr1000"), live_atr)
        self.assertNotIn("MRRC.log", self._names(got), "遗留 MRRC.log 不该再进包")

    def test_prev_of_chosen_app_log_is_included(self):
        live = self._make(self.log_dir, "mrrc_radio1.log")
        prev = self._make(self.log_dir, "mrrc_radio1.log.prev")
        got = sb.resolve_log_files(log_dir=self.log_dir, base_dir=self.base_dir,
                                   instance_name="radio1")
        self.assertEqual(got.get("app"), live)
        self.assertEqual(got.get("app_prev"), prev)

    def test_main_instance_uses_mrrc_log_and_comm_atr(self):
        app = self._make(self.log_dir, "MRRC.log")
        rig = self._make(self.log_dir, "rigctld.log")
        atr = self._make(self.log_dir, "atr1000_comm.log")
        got = sb.resolve_log_files(log_dir=self.log_dir, base_dir=self.base_dir,
                                   instance_name="")
        self.assertEqual(got.get("app"), app)
        self.assertEqual(got.get("rigctld"), rig)
        self.assertEqual(got.get("atr1000"), atr)

    def test_watchdog_log_is_last_resort_for_atr(self):
        watchdog = self._make(self.log_dir, "atr1000_proxy_watchdog.log")
        got = sb.resolve_log_files(log_dir=self.log_dir, base_dir=self.base_dir,
                                   instance_name="radio2")
        self.assertEqual(got.get("atr1000"), watchdog)

    def test_windows_stdout_tee_is_always_collected(self):
        out = self._make(os.path.join(self.base_dir, "logs"), "server-stdout.log")
        prev = self._make(os.path.join(self.base_dir, "logs"), "server-stdout.log.prev")
        got = sb.resolve_log_files(log_dir=self.log_dir, base_dir=self.base_dir,
                                   instance_name="")
        self.assertEqual(got.get("stdout"), out)
        self.assertEqual(got.get("stdout_prev"), prev)

    def test_missing_everything_yields_empty_dict(self):
        self.assertEqual(sb.resolve_log_files(log_dir=self.log_dir, base_dir=self.base_dir,
                                              instance_name="radio3"), {})


class AppendLogLineTest(unittest.TestCase):
    """writte_log 的落盘约定：补换行、自动建目录（旧实现会黏行 + 依赖 CWD）。"""

    def test_appends_with_newline_and_creates_parent_dirs(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "deep", "nested", "MRRC.log")
            self.assertEqual(sb.append_log_line(path, "first"), path)
            sb.append_log_line(path, "second")
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "first\nsecond\n")

    def test_empty_path_is_noop(self):
        self.assertEqual(sb.append_log_line("", "ignored"), "")


class VersionDetectTest(unittest.TestCase):
    """源码模式也要能报版本：version.txt → MRRC.iss → CHANGELOG（否则上传显示 unknown）。"""

    def test_version_txt_wins(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "version.txt"), "w", encoding="utf-8") as fh:
                fh.write("6.2.0\n")
            self.assertEqual(sb.detect_version(tmp), "6.2.0")

    def test_iss_fallback(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            iss_dir = os.path.join(tmp, "packaging", "windows")
            os.makedirs(iss_dir)
            with open(os.path.join(iss_dir, "MRRC.iss"), "w", encoding="utf-8") as fh:
                fh.write('#define MyAppVersion "6.1.6"\n')
            self.assertEqual(sb.detect_version(tmp), "6.1.6")

    def test_changelog_fallback(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "CHANGELOG.md"), "w", encoding="utf-8") as fh:
                fh.write("# Changelog\n\n## [V6.1.6] - 2026-09-16\n\n- x\n")
            self.assertEqual(sb.detect_version(tmp), "6.1.6")

    def test_nothing_found_is_empty(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(sb.detect_version(tmp), "")


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

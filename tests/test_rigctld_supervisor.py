"""rigctld 自启动看护的单元测试（真机上报驱动）

用户上报（2026-09-17）：Windows 安装版不自动拉起 rigctld.exe，FT-891 连不上，
必须手动启动 —— 本模块负责在 MRRC 启动时自己拉起来。
"""

import configparser
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import rigctld_supervisor as sup  # noqa: E402


def cfg_with(text: str) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read_string(text)
    return cfg


class ResolveConfigTest(unittest.TestCase):
    def test_instance_settings_win_over_hamlib(self):
        cfg = cfg_with("""
[INSTANCE_SETTINGS]
instance_rigctl_model = 1036
instance_rigctl_device = COM8
instance_rigctl_speed = 38400
instance_rigctl_stop_bits = 1
instance_rigctl_host = 127.0.0.1
instance_rigctl_port = 4532

[HAMLIB]
rig_model = IC-M710
rig_pathname = /dev/cu.usbserial-140
rig_rate = 4800
stop_bits = 2
""")
        p = sup.resolve_config(cfg)
        self.assertEqual(p["model"], "1036")
        self.assertEqual(p["device"], "COM8")
        self.assertEqual(p["speed"], "38400")
        self.assertEqual(p["stop_bits"], "1")
        self.assertEqual(p["port"], "4532")

    def test_hamlib_fallback_and_name_to_number(self):
        cfg = cfg_with("""
[HAMLIB]
rig_model = IC-M710
rig_pathname = /dev/cu.usbserial-140
rig_rate = 4800
stop_bits = 2
""")
        p = sup.resolve_config(cfg)
        # 机型名应折算成 hamlib 数字（折算不可用时保留原名，也算可接受）
        self.assertTrue(p["model"] == "30003" or p["model"] == "IC-M710", p["model"])
        self.assertEqual(p["device"], "/dev/cu.usbserial-140")
        self.assertEqual(p["port"], "4532")          # 默认值

    def test_has_rig_and_autostart_switch(self):
        self.assertFalse(sup.has_rig({"model": ""}))
        self.assertFalse(sup.has_rig({"model": "none"}))
        self.assertTrue(sup.has_rig({"model": "1036"}))
        self.assertTrue(sup.autostart_enabled({"autostart": "true"}))
        self.assertFalse(sup.autostart_enabled({"autostart": "false"}))
        os.environ["MRRC_RIGCTLD_AUTOSTART"] = "0"
        try:
            self.assertFalse(sup.autostart_enabled({"autostart": "true"}))
        finally:
            os.environ.pop("MRRC_RIGCTLD_AUTOSTART", None)


class CommandTest(unittest.TestCase):
    def test_build_command_matches_shell_script(self):
        cmd = sup.build_command("/x/rigctld", {"model": "1036", "device": "COM8", "speed": "38400",
                                               "stop_bits": "1", "host": "127.0.0.1", "port": "4532"})
        self.assertEqual(cmd[:9], ["/x/rigctld", "-m", "1036", "-r", "COM8", "-s", "38400", "-C", "stop_bits=1"])
        self.assertIn("-T", cmd); self.assertIn("-t", cmd); self.assertIn("-vvv", cmd)

    def test_find_rigctld_env_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "rigctld.exe"
            fake.write_bytes(b"x")
            os.environ["MRRC_RIGCTLD_BIN"] = str(fake)
            try:
                self.assertEqual(sup.find_rigctld(), str(fake))
            finally:
                os.environ.pop("MRRC_RIGCTLD_BIN", None)


class EnsureRunningTest(unittest.TestCase):
    def test_no_rig_skips(self):
        res = sup.ensure_running(cfg_with("[HAMLIB]\nrig_model = none\n"))
        self.assertEqual(res["status"], "no_rig")

    def test_disabled_switch(self):
        res = sup.ensure_running(cfg_with("[HAMLIB]\nrig_model = 1036\nautostart = false\n"))
        self.assertEqual(res["status"], "disabled")

    def test_already_listening_is_idempotent(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0)); srv.listen(1)
        port = srv.getsockname()[1]
        try:
            res = sup.ensure_running(cfg_with(f"[INSTANCE_SETTINGS]\ninstance_rigctl_model = 1036\n"
                                              f"instance_rigctl_port = {port}\n"), wait_seconds=0.5)
            self.assertEqual(res["status"], "already_running")
        finally:
            srv.close()

    def test_no_binary_gives_actionable_hint(self):
        os.environ["MRRC_RIGCTLD_BIN"] = "/nonexistent/rigctld"
        try:
            res = sup.ensure_running(cfg_with("[INSTANCE_SETTINGS]\ninstance_rigctl_model = 1036\n"
                                              "instance_rigctl_port = 45999\n"), wait_seconds=0.5)
            # 找不到可执行文件：要么给提示，要么在开发机上被 PATH 命中 → dry_run 之外不该崩
            self.assertIn(res["status"], ("no_binary", "started", "started_slow", "failed"))
            if res["status"] == "no_binary":
                self.assertIn("MRRC_RIGCTLD_BIN", res["detail"])
        finally:
            os.environ.pop("MRRC_RIGCTLD_BIN", None)

    def test_dry_run_assembles_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "rigctld.exe"; fake.write_bytes(b"x")
            os.environ["MRRC_RIGCTLD_BIN"] = str(fake)
            try:
                res = sup.ensure_running(cfg_with("[INSTANCE_SETTINGS]\ninstance_rigctl_model = 1036\n"
                                                  "instance_rigctl_device = COM8\n"
                                                  "instance_rigctl_port = 45998\n"), dry_run=True)
                self.assertEqual(res["status"], "dry_run")
                self.assertEqual(res["command"][0], str(fake))
                self.assertIn("-m", res["command"])
            finally:
                os.environ.pop("MRRC_RIGCTLD_BIN", None)


if __name__ == "__main__":
    unittest.main(verbosity=2)

class ModelListParseTest(unittest.TestCase):
    """hamlib 的 -m 只接受编号：必须能把机型名解析成编号（真机实测：传名字会
    "Unknown rig num 0" 直接退出）。"""

    SAMPLE = """   1  Yaesu  FT-847  1.0  Beta  RIG_MODEL_FT847
1036  Yaesu  FT-891  20241118.11  Stable  RIG_MODEL_FT891
 3073  Icom  IC-M710  1.0  Stable  RIG_MODEL_ICM710
"""

    def test_name_variants_resolve(self):
        for name in ("FT-891", "FT891", "ft 891", "RIG_MODEL_FT891"):
            self.assertEqual(sup.parse_model_list(self.SAMPLE, name), "1036", name)
        for name in ("IC-M710", "ICM710", "ic m710"):
            self.assertEqual(sup.parse_model_list(self.SAMPLE, name), "3073", name)

    def test_unknown_returns_none(self):
        self.assertIsNone(sup.parse_model_list(self.SAMPLE, "NOPE-123"))
        self.assertIsNone(sup.parse_model_list("", "FT-891"))

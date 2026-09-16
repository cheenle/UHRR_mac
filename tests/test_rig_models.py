"""hamlib 机型表与"配置值 ↔ rigctld 型号"对应的单元测试。

背景：Device Config 原先硬编码 7 个型号，且写的是 [HAMLIB] rig_model（名字），
而 rigctld 真正读的是 [INSTANCE_SETTINGS] instance_rigctl_model（数字）——
两边不通，用户改型号实际不生效。见 rig_models.py 头部。
"""

import configparser
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rig_models  # noqa: E402


FAKE = [
    {"id": 1, "name": "Dummy", "mfg": "Hamlib", "version": "x", "status": 3},
    {"id": 1020, "name": "FT-817", "mfg": "Yaesu", "version": "x", "status": 3},
    {"id": 1042, "name": "FTDX-10", "mfg": "Yaesu", "version": "x", "status": 2},
    {"id": 2031, "name": "TS-590S", "mfg": "Kenwood", "version": "x", "status": 3},
    {"id": 30003, "name": "IC-M710", "mfg": "Icom", "version": "x", "status": 3},
    {"id": 3073, "name": "IC-7300", "mfg": "Icom", "version": "x", "status": 3},
]


class ResolveTest(unittest.TestCase):
    def test_normalize_ignores_separators_and_case(self):
        for text in ("IC-M710", "IC_M710", "ic m710", "icm710", "  IC-M710  "):
            self.assertEqual(rig_models._key(text), "ICM710")

    def test_numeric_id(self):
        self.assertEqual(rig_models.resolve("30003", FAKE)["name"], "IC-M710")
        self.assertIsNone(rig_models.resolve("99999", FAKE))

    def test_exact_and_legacy_names(self):
        self.assertEqual(rig_models.resolve("IC-M710", FAKE)["id"], 30003)
        self.assertEqual(rig_models.resolve("IC_M710", FAKE)["id"], 30003)      # 配置里的历史写法
        self.assertEqual(rig_models.resolve("FT817", FAKE)["id"], 1020)        # 旧下拉的写法
        self.assertEqual(rig_models.resolve("FTDX10", FAKE)["id"], 1042)
        self.assertEqual(rig_models.resolve("TS590", FAKE)["id"], 2031)
        self.assertEqual(rig_models.resolve("IC7300", FAKE)["id"], 3073)

    def test_mfg_prefixed_and_unknown(self):
        self.assertEqual(rig_models.resolve("Icom IC-M710", FAKE)["id"], 30003)
        self.assertIsNone(rig_models.resolve("IC-9999", FAKE))
        self.assertIsNone(rig_models.resolve("", FAKE))
        self.assertIsNone(rig_models.resolve(None, FAKE))

    def test_describe_reports_reason_and_fallback(self):
        desc = rig_models.describe.__wrapped__ if hasattr(rig_models.describe, "__wrapped__") else None
        # describe 走真实 hamlib；这里只验证 status 名称映射
        self.assertEqual(rig_models.status_name(3), "Stable")
        self.assertEqual(rig_models.status_name(2), "Beta")
        self.assertEqual(rig_models.status_name(99), "?")

    def test_suggest_finds_close_matches(self):
        hits = rig_models.suggest("IC-73", FAKE)
        self.assertTrue(any(m["name"] == "IC-7300" for m in hits))


class ApplyToConfigTest(unittest.TestCase):
    def _cfg(self, with_instance=True):
        cfg = configparser.ConfigParser()
        cfg.add_section("HAMLIB")
        cfg.set("HAMLIB", "rig_model", "IC_M710")
        if with_instance:
            cfg.add_section("INSTANCE_SETTINGS")
            cfg.set("INSTANCE_SETTINGS", "instance_rigctl_model", "30003")
        return cfg

    def test_writes_canonical_name_and_instance_id(self):
        """这是本次修复的核心：两处必须同时写，rigctld 才真正换型号。"""
        cfg = self._cfg()
        name, err = rig_models.apply_to_config(cfg, "30003")
        self.assertIsNone(err)
        self.assertEqual(name, "IC-M710")
        self.assertEqual(cfg.get("HAMLIB", "rig_model"), "IC-M710")
        self.assertEqual(cfg.get("INSTANCE_SETTINGS", "instance_rigctl_model"), "30003")

        name, err = rig_models.apply_to_config(cfg, "FTDX10")
        self.assertIsNone(err)
        self.assertEqual(cfg.get("HAMLIB", "rig_model"), "FTDX-10")
        self.assertEqual(cfg.get("INSTANCE_SETTINGS", "instance_rigctl_model"), "1042")

    def test_unknown_model_is_rejected_without_partial_write(self):
        cfg = self._cfg()
        name, err = rig_models.apply_to_config(cfg, "IC-9999")
        self.assertIsNone(name)
        self.assertIn("找不到", err)
        self.assertEqual(cfg.get("HAMLIB", "rig_model"), "IC_M710")          # 原值保持不变
        self.assertEqual(cfg.get("INSTANCE_SETTINGS", "instance_rigctl_model"), "30003")

    def test_empty_value_means_no_change(self):
        cfg = self._cfg()
        self.assertEqual(rig_models.apply_to_config(cfg, "   "), (None, None))
        self.assertEqual(cfg.get("HAMLIB", "rig_model"), "IC_M710")

    def test_single_instance_config_without_instance_section(self):
        cfg = self._cfg(with_instance=False)
        name, err = rig_models.apply_to_config(cfg, "IC-7300")
        self.assertIsNone(err)
        self.assertEqual(cfg.get("HAMLIB", "rig_model"), "IC-7300")


class DumpCapsParseTest(unittest.TestCase):
    # rigctld \dump_caps 的真实输出片段（hamlib 4.7.2）
    SAMPLE = (
        "Caps dump for model: 30003\n"
        "Model name:\tIC-M710\n"
        "Mfg name:\tIcom\n"
        "Hamlib version:\tHamlib 4.7.2 2026-06-21T13:07:37Z\n"
        "Backend version:\t20181007.0\n"
        "Backend status:\tStable\n"
        "Rig type:\tOther Receiver Transmitter Transceiver \n"
    )

    def test_parses_model_id_name_mfg_status(self):
        info = rig_models._parse_dump_caps(self.SAMPLE)
        self.assertEqual(info["id"], 30003)
        self.assertEqual(info["name"], "IC-M710")
        self.assertEqual(info["mfg"], "Icom")
        self.assertEqual(info["status"], "Stable")
        self.assertEqual(info["version"], "20181007.0")

    def test_returns_none_for_useless_output(self):
        self.assertIsNone(rig_models._parse_dump_caps("error\n"))


class HamlibAvailabilityTest(unittest.TestCase):
    def test_available_returns_models_or_fallback(self):
        info = rig_models.available()
        self.assertTrue(info["models"], "机型表不能为空（hamlib 或回退表）")
        self.assertIsInstance(info["fallback"], bool)
        for model in info["models"]:
            self.assertIn("id", model)
            self.assertIn("name", model)


if __name__ == "__main__":
    unittest.main(verbosity=2)

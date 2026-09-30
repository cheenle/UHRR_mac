"""发布完成度检查器（dev_tools/release_check.py）的单元测试。

重点：规则引擎的判定语义（锚点匹配 / first_only / count / stale / optional），
以及真实仓库的检查结果。
"""

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev_tools"))

import release_check as rc  # noqa: E402


class RuleEngineTests(unittest.TestCase):
    """规则评估语义。全部在临时目录里跑，不碰真实仓库。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def test_matching_version_passes(self):
        self._write("a.html", "<span>V6.1.18</span>")
        rule = {"id": "a", "path": "a.html", "pattern": r"V([0-9.]+)", "count": 1}
        self.assertEqual(rc.evaluate_rule(rule, "6.1.18", self.root).status, rc.PASS)

    def test_stale_version_fails(self):
        self._write("a.html", "<span>V6.1.16</span>")
        rule = {"id": "a", "path": "a.html", "pattern": r"V([0-9.]+)", "count": 1}
        found = rc.evaluate_rule(rule, "6.1.18", self.root)
        self.assertEqual(found.status, rc.FAIL)
        self.assertIn("6.1.16", found.detail)

    def test_count_mismatch_fails(self):
        self._write("a.html", "V6.1.18 V6.1.18")
        rule = {"id": "a", "path": "a.html", "pattern": r"V([0-9.]+)", "count": 1}
        self.assertEqual(rc.evaluate_rule(rule, "6.1.18", self.root).status, rc.FAIL)

    def test_min_count_not_met_fails(self):
        self._write("a.html", "V6.1.18")
        rule = {"id": "a", "path": "a.html", "pattern": r"V([0-9.]+)", "min_count": 2}
        self.assertEqual(rc.evaluate_rule(rule, "6.1.18", self.root).status, rc.FAIL)

    def test_pattern_without_match_fails(self):
        self._write("a.html", "no version here")
        rule = {"id": "a", "path": "a.html", "pattern": r"V([0-9.]+)", "count": 1}
        found = rc.evaluate_rule(rule, "6.1.18", self.root)
        self.assertEqual(found.status, rc.FAIL)
        self.assertIn("锚点", found.detail)

    def test_missing_required_file_fails(self):
        rule = {"id": "a", "path": "nope.html", "pattern": r"V([0-9.]+)", "count": 1}
        self.assertEqual(rc.evaluate_rule(rule, "6.1.18", self.root).status, rc.FAIL)

    def test_missing_optional_file_skips(self):
        rule = {"id": "a", "path": "nope.html", "pattern": r"V([0-9.]+)",
                "count": 1, "optional": True}
        self.assertEqual(rc.evaluate_rule(rule, "6.1.18", self.root).status, rc.SKIP)

    def test_first_only_skips_non_version_headings(self):
        """CHANGELOG 顶部夹着非版本标题时必须仍取到第一个版本标题。"""
        self._write("CHANGELOG.md",
                    "# Changelog\n\n"
                    "## [Unreleased]\n\n"
                    "## [草稿]\n\n"
                    "## [V6.1.18] - 2026-09-17\n\n"
                    "## [V6.1.17] - 2026-09-17\n")
        rule = {"id": "top", "path": "CHANGELOG.md",
                "pattern": r"^## \[(?:V)?([0-9]+\.[0-9]+\.[0-9]+)\]", "first_only": True}
        found = rc.evaluate_rule(rule, "6.1.18", self.root)
        self.assertEqual(found.status, rc.PASS, found.detail)

    def test_first_only_detects_stale_top_entry(self):
        self._write("CHANGELOG.md",
                    "## [V6.1.18] - x\n\n## [V6.1.17] - y\n")
        rule = {"id": "top", "path": "CHANGELOG.md",
                "pattern": r"^## \[(?:V)?([0-9]+\.[0-9]+\.[0-9]+)\]", "first_only": True}
        # 权威是 6.1.19 → 顶条 6.1.18 落后，必须 FAIL
        self.assertEqual(rc.evaluate_rule(rule, "6.1.19", self.root).status, rc.FAIL)

    def test_leading_v_is_normalized(self):
        self._write("a.html", "V6.1.18")
        rule = {"id": "a", "path": "a.html", "pattern": r"V([0-9.]+)", "count": 1}
        # 期望值带不带 v 都该通过（两侧都 lstrip）
        self.assertEqual(rc.evaluate_rule(rule, "v6.1.18", self.root).status, rc.PASS)

    def test_first_only_with_count_is_rejected(self):
        """互斥字段同时出现必须报错，不能静默取其一。"""
        rule = {"id": "a", "path": "a.html", "pattern": r"V([0-9.]+)",
                "first_only": True, "count": 1}
        with self.assertRaises(ValueError):
            rc.validate_rule(rule)

    def test_rule_requires_id_path_pattern(self):
        for missing in ("id", "path", "pattern"):
            rule = {"id": "a", "path": "a.html", "pattern": r"V([0-9.]+)"}
            del rule[missing]
            with self.assertRaises(ValueError):
                rc.validate_rule(rule)

    def test_app_version_reads_iss(self):
        reg = {"app_version_source": {
            "path": "packaging/windows/MRRC.iss",
            "pattern": r'#define MyAppVersion "([0-9.]+)"'}}
        self._write("packaging/windows/MRRC.iss", '#define MyAppVersion "6.1.18"\n')
        self.assertEqual(rc.app_version(reg, self.root), "6.1.18")

    def test_app_version_raises_when_unparseable(self):
        reg = {"app_version_source": {
            "path": "packaging/windows/MRRC.iss",
            "pattern": r'#define MyAppVersion "([0-9.]+)"'}}
        self._write("packaging/windows/MRRC.iss", "nothing to see\n")
        with self.assertRaises(ValueError):
            rc.app_version(reg, self.root)


class RepositoryStateTests(unittest.TestCase):
    """真实仓库的检查结果。

    本任务断言"检查器能检出已知漂移"；Task 3 修掉漂移后，
    这里的期望会翻转为"干净"。
    """

    def test_registry_loads_and_validates(self):
        registry = rc.load_registry()
        # 不断言具体版本号——升级后本测试不应变红
        self.assertRegex(rc.app_version(registry), r"^\d+\.\d+\.\d+$")
        for rule in registry["rules"]:
            rc.validate_rule(rule)  # 不抛即可

    def test_registry_governs_the_expected_files(self):
        paths = {r["path"] for r in rc.load_registry()["rules"]}
        for expected in ("CHANGELOG.md", "www/mobile_modern.html",
                         "www/mobile_modern_zh.html", "README.md",
                         "README_CN.md", "README_en.md",
                         "website/index.html", "website/zh/index.html"):
            self.assertIn(expected, paths)

    def test_authority_file_is_not_itself_a_rule(self):
        """iss 是权威，不能同时被治理（避免循环权威）。"""
        paths = {r["path"] for r in rc.load_registry()["rules"]}
        self.assertNotIn("packaging/windows/MRRC.iss", paths)

    def test_non_anchored_pattern_would_false_positive(self):
        """边界说明：裸扫 V[0-9.]+ 会把历史举例判成漂移。

        这条测试锁住"为什么规则必须锚定"——它是给未来改规则的人的警告，
        不是要求检查器支持裸扫。
        """
        registry = rc.load_registry()
        expected = rc.app_version(registry)   # 不硬编码版本号
        text = (rc.ROOT / "website" / "index.html").read_text(encoding="utf-8")
        loose = {v.lstrip("vV") for v in re.findall(r"V([0-9]+\.[0-9]+\.[0-9]+)", text)}
        anchored_rule = next(r for r in registry["rules"] if r["id"] == "website-stat")
        anchored = {v.lstrip("vV") for v in re.findall(
            anchored_rule["pattern"], text, re.MULTILINE)}
        # 裸扫会带出历史版本；锚定不会
        self.assertTrue(loose - {expected}, "裸扫未带出历史版本，本测试失去意义")
        self.assertEqual(anchored, {expected})

    def test_main_is_clean_after_drift_fix(self):
        """漂移已修：真实仓库必须干净。"""
        self.assertEqual(rc.main([]), 0)

    def test_main_is_clean_in_strict_mode(self):
        """发布日形态：不允许任何 SKIP（当前无 optional 规则，故同样应为 0）。"""
        self.assertEqual(rc.main(["--strict"]), 0)


if __name__ == "__main__":
    unittest.main()

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


class VersionTxtDerivationTests(unittest.TestCase):
    """守卫：version.txt 必须由构建脚本从权威派生，不能硬编码。"""

    def _text(self, rel):
        return (rc.ROOT / rel).read_text(encoding="utf-8", errors="replace")

    def test_windows_build_derives_version_txt_from_iss(self):
        text = self._text("packaging/windows/build.ps1")
        self.assertIn("version.txt", text, "build.ps1 必须写 version.txt")
        self.assertIn("MyAppVersion", text,
                      "build.ps1 必须从 MRRC.iss 的 MyAppVersion 派生版本")

    def test_windows_launcher_reads_version_txt(self):
        text = self._text("windows/launcher.py")
        self.assertIn("version.txt", text,
                      "运行时权威是 version.txt；启动器必须读它")


class ReleaseSourceZipTests(unittest.TestCase):
    """发行源码包（传给构建 VM 的 zip）的文件选择。

    打包逻辑在 dev_tools/release_windows.sh，排除前缀外置在
    dev_tools/release_src_excludes.json，本测试是该不变量的唯一守卫。
    """

    EXCLUDES = rc.ROOT / "dev_tools" / "release_src_excludes.json"

    def _excludes(self):
        return json.loads(self.EXCLUDES.read_text(encoding="utf-8"))

    def _tracked(self):
        import subprocess
        return subprocess.run(["git", "ls-files"], cwd=rc.ROOT,
                              capture_output=True, text=True,
                              check=True).stdout.split()

    def test_exclude_file_exists_and_is_wellformed(self):
        data = self._excludes()
        self.assertIsInstance(data["exclude_prefixes"], list)
        self.assertTrue(all(isinstance(p, str) and p.endswith("/")
                            for p in data["exclude_prefixes"]),
                        "排除前缀必须以 / 结尾，避免 certs 误伤 certs_foo")

    def test_private_key_material_is_excluded(self):
        """certs/ 下确实有私钥，且必须被排除。

        判据是"basename 里含 `.key`"而不是"以 `.key` 结尾"——真实私钥
        `radio.vlsc.net.key.20260317_010431` 带时间戳后缀；而
        `certs/backup/fullchain_complete.pem` 是**公开**的证书链，不算私钥。
        """
        keys = [f for f in self._tracked()
                if f.startswith("certs/") and ".key" in Path(f).name]
        self.assertTrue(keys, "前提失效：certs/ 下已无可识别的私钥，本规则可删")
        excludes = self._excludes()["exclude_prefixes"]
        leaked = [f for f in keys if not any(f.startswith(p) for p in excludes)]
        self.assertEqual(leaked, [], f"私钥会随源码包上传构建 VM：{leaked}")

    def test_every_exclude_prefix_matches_something(self):
        """没有失效规则（拼错的前缀会静默不排除任何东西）。"""
        tracked = self._tracked()
        for prefix in self._excludes()["exclude_prefixes"]:
            with self.subTest(prefix=prefix):
                self.assertTrue(any(f.startswith(prefix) for f in tracked),
                                f"排除前缀 {prefix!r} 不匹配任何被跟踪文件")

    def test_script_reads_the_exclude_file(self):
        """脚本必须真的读它，而不是各写一份。"""
        text = (rc.ROOT / "dev_tools" / "release_windows.sh").read_text(
            encoding="utf-8", errors="replace")
        self.assertIn("release_src_excludes.json", text)


if __name__ == "__main__":
    unittest.main()

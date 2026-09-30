# 发布完成度检查器（P1）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让「本次发版有没有漏改文件」从一个靠人记的问题，变成一条能跑、能在测试套件里失败的检查。

**Architecture:** 一个机器可读的规则表（`dev_tools/release_artifacts.json`）声明"哪些文件的哪个位置必须等于安装版本"，一个 stdlib-only 的检查器（`dev_tools/release_check.py`）读它并与权威（`packaging/windows/MRRC.iss` 的 `MyAppVersion`）比对。检查器同时提供 CLI（给人）和可导入函数（给测试）。上线即会检出现存的四处真实漂移，最后一并修掉。

**Tech Stack:** Python 3 标准库（`json` / `re` / `argparse` / `pathlib` / `unittest`）。**不引入任何第三方依赖**——本仓库的 `dev_tools/test_installation.py` 明确校验 Python 3.7+ 且无 venv 也能跑。

**Spec:** `docs/superpowers/specs/2026-09-30-release-engineering-design.md`（§2.1 版本权威链、§2.4 现存漂移、§4 检查器设计）

## Global Constraints

- **Python 3.7+ 兼容**：文件头 `from __future__ import annotations`；只用 `NamedTuple`（不用 `dataclass(slots=True)` 等 3.10+ 特性）。
- **零第三方依赖**：只用标准库。`dev_tools/test_installation.py` 会在无依赖环境下跑。
- **版本权威 = `packaging/windows/MRRC.iss` 的 `#define MyAppVersion "6.1.18"`**，正则 `#define MyAppVersion "([0-9.]+)"`。权威**只读不判**——它自己不出现在 `rules` 里（避免循环权威）。
- **测试用 stdlib `unittest`，不用 pytest**（本仓库无 pytest 配置）。沿用 `tests/test_upgrade_core.py` 的 `sys.path.insert` 风格。
- **规则 pattern 必须是锚点式的**，绝不允许对整文件裸扫 `V[0-9.]+`（会把 `README.md` 的"更新史"、`website/index.html:327,329` 的 `V6.1.0`/`V6.0.10` 历史举例判成漂移）。
- **输出 GBK 安全**：不用 emoji，用 ASCII 标记（`ok` / `FAIL` / `skip`）。原因见 `win_pack.md` 的 GBK 陷阱。
- **退出码**：`0` 干净；`1` 有 FAIL（**总是**，不依赖 `--strict`）；`2` 清单不可读或权威无法解析。`--strict` 额外把 SKIP 也算失败（发布日：每个产物都该在）。
- 检查器内 `ROOT = Path(__file__).resolve().parents[1]`（`dev_tools/` 的上一级即仓库根）。

## Review Focus

以下是最可能出现、且不被任务测试天然覆盖的五类情况。每一条都已在下面对应任务的测试里钉住：

1. **有人给规则加了一条裸扫 pattern** → 会把 `README.md:35-40` 的"更新史"和 `website/index.html:329` 的 "Installs up to V6.0.10" 判成版本漂移，于是检查器开始报**假警**，团队学会忽略它。→ 由 Task 2 的 `test_non_anchored_pattern_would_false_positive` 说明边界，由 Task 4 的 AGENTS.md 记述约定。
2. **`first_only` 与 `count` 同时出现在一条规则里** → 语义冲突。→ 由 Task 1 的 `test_first_only_with_count_is_rejected` 钉住（加载时报错，不静默取其一）。
3. **CHANGELOG 顶部新增一个非版本标题**（如 `## [草稿]`）→ 仍必须取到**第一个版本形状**的标题。→ 由 Task 1 的 `test_first_only_skips_non_version_headings` 钉住。
4. **被治理的文件被删除或改名**（如 `README_en.md` 被合并掉）→ 必须 FAIL 而不是静默通过；只有显式写了 `optional` 才 SKIP。→ 由 Task 1 的 `test_missing_required_file_fails` / `test_missing_optional_file_skips` 钉住。
5. **`version.txt` 的派生链被改**（有人把版本硬编码进 `build.ps1`）→ 运行时版本会静默脱离权威。→ 由 Task 4 的 `VersionTxtDerivationTests` 钉住。

---

### Task 1: 检查器核心 —— 权威解析与单条规则评估

**Files:**
- Create: `dev_tools/release_check.py`
- Test: `tests/test_release_artifacts.py`

**Interfaces:**
- Consumes: 无（本任务是第一块）
- Produces:
  - `class Finding(NamedTuple)` 字段 `rule_id: str`、`path: str`、`status: str`、`detail: str`
  - 常量 `PASS = "PASS"`、`FAIL = "FAIL"`、`SKIP = "SKIP"`
  - `app_version(registry: dict, root: Path = ROOT) -> str` —— 返回去掉前导 `v`/`V` 的版本串；解析不出抛 `ValueError`
  - `evaluate_rule(rule: dict, expected: str, root: Path = ROOT) -> Finding`
  - `validate_rule(rule: dict) -> None` —— 字段互斥/必填校验，违规抛 `ValueError`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_release_artifacts.py`：

```python
"""发布完成度检查器（dev_tools/release_check.py）的单元测试。

重点：规则引擎的判定语义（锚点匹配 / first_only / count / stale / optional），
以及真实仓库的检查结果。
"""

import json
import os
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest discover -s tests -p "test_release_artifacts.py" -v`
Expected: 全部 ERROR，`ModuleNotFoundError: No module named 'release_check'`

- [ ] **Step 3: 写最小实现**

创建 `dev_tools/release_check.py`：

```python
#!/usr/bin/env python3
"""MRRC 发布完成度检查器 —— 回答"本次发版有没有漏改文件"。

权威：packaging/windows/MRRC.iss 的 MyAppVersion（build.ps1:79 与
      dev_tools/release_windows.sh:39 都读它）。
规则表：dev_tools/release_artifacts.json 里每一条"该跟它一致"的位置。

用法：
    python3 dev_tools/release_check.py            # 人读报告
    python3 dev_tools/release_check.py --json     # 机器可读
    python3 dev_tools/release_check.py --strict   # SKIP 也算失败（发布日）

退出码：0 干净 / 1 有 FAIL（--strict 下 SKIP 也算）/ 2 清单或权威不可用
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = Path(__file__).resolve().parent / "release_artifacts.json"

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

_REQUIRED_FIELDS = ("id", "path", "pattern")


class Finding(NamedTuple):
    rule_id: str
    path: str
    status: str
    detail: str = ""


def validate_rule(rule: dict) -> None:
    """规则字段校验。互斥/缺失一律抛 ValueError（不静默取其一）。"""
    for field in _REQUIRED_FIELDS:
        if not rule.get(field):
            raise ValueError(f"规则缺少必填字段 {field!r}：{rule!r}")
    if rule.get("first_only") and ("count" in rule or "min_count" in rule):
        raise ValueError(
            f"规则 {rule['id']!r}：first_only 与 count/min_count 互斥")
    try:
        re.compile(rule["pattern"])
    except re.error as exc:
        raise ValueError(f"规则 {rule['id']!r} 的 pattern 非法：{exc}") from exc


def _normalize(version: str) -> str:
    """去掉前导 v/V，便于两侧比较。"""
    return version.lstrip("vV")


def app_version(registry: dict, root: Path = ROOT) -> str:
    """从权威文件解析安装版本。解析不出抛 ValueError。"""
    src = registry["app_version_source"]
    target = root / src["path"]
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ValueError(f"权威文件不可读：{src['path']}（{exc}）") from exc
    match = re.search(src["pattern"], text, re.MULTILINE)
    if not match:
        raise ValueError(
            f"无法从权威文件解析版本：{src['path']}（pattern 不匹配）")
    return _normalize(match.group(1))


def evaluate_rule(rule: dict, expected: str, root: Path = ROOT) -> Finding:
    """评估单条规则。expected 为权威版本串。"""
    validate_rule(rule)
    rule_id, rel = rule["id"], rule["path"]
    target = root / rel
    expected = _normalize(expected)

    if not target.exists():
        if rule.get("optional"):
            return Finding(rule_id, rel, SKIP, "文件不存在（optional）")
        return Finding(rule_id, rel, FAIL, "文件不存在")

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return Finding(rule_id, rel, FAIL, f"读取失败：{exc}")

    found = [_normalize(v) for v in re.findall(rule["pattern"], text, re.MULTILINE)]
    if not found:
        return Finding(rule_id, rel, FAIL, "pattern 无匹配（锚点可能已被改写）")

    if rule.get("first_only"):
        found = found[:1]

    if "count" in rule and len(found) != rule["count"]:
        return Finding(rule_id, rel, FAIL,
                       f"匹配 {len(found)} 处，期望 {rule['count']} 处")
    if "min_count" in rule and len(found) < rule["min_count"]:
        return Finding(rule_id, rel, FAIL,
                       f"匹配 {len(found)} 处，至少需要 {rule['min_count']} 处")

    stale = sorted({v for v in found if v != expected})
    if stale:
        return Finding(rule_id, rel, FAIL,
                       f"版本漂移：{'、'.join(stale)}（应为 {expected}）")
    return Finding(rule_id, rel, PASS, f"{len(found)} 处 = {expected}")


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_rules(registry: dict, expected: str, root: Path = ROOT) -> list:
    return [evaluate_rule(rule, expected, root) for rule in registry["rules"]]


_MARK = {PASS: "ok  ", FAIL: "FAIL", SKIP: "skip"}


def _report(registry: dict, expected: str, findings: list) -> None:
    print(f"安装版本权威 = {expected}")
    print(f"规则 {len(findings)} 条：")
    for f in findings:
        print(f"  {_MARK[f.status]} {f.rule_id:<22} {f.path:<34} {f.detail}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MRRC 发布完成度检查")
    parser.add_argument("--json", action="store_true", help="机器可读输出")
    parser.add_argument("--strict", action="store_true",
                        help="SKIP 也算失败（发布日用）")
    args = parser.parse_args(argv)

    try:
        registry = load_registry()
        for rule in registry["rules"]:
            validate_rule(rule)
        expected = app_version(registry)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"清单或权威不可用：{exc}", file=sys.stderr)
        return 2

    findings = check_rules(registry, expected)
    if args.json:
        print(json.dumps(
            {"version": expected,
             "findings": [dict(f._asdict()) for f in findings]},
            ensure_ascii=False, indent=2))
    else:
        _report(registry, expected, findings)

    has_fail = any(f.status == FAIL for f in findings)
    has_skip = any(f.status == SKIP for f in findings)
    if has_fail or (args.strict and has_skip):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest discover -s tests -p "test_release_artifacts.py" -v`
Expected: 15 个测试全部 PASS

- [ ] **Step 5: 确认 3.7 兼容与零依赖**

Run: `python3 dev_tools/test_installation.py`
Expected: 通过（证明新增文件未引入依赖）

- [ ] **Step 6: 提交**

```bash
git add dev_tools/release_check.py tests/test_release_artifacts.py
git commit -m "feat(release): 发布完成度检查器核心 —— 权威解析与规则评估"
```

---

### Task 2: 规则清单与全量检查（检出已知漂移）

**Files:**
- Create: `dev_tools/release_artifacts.json`
- Modify: `dev_tools/release_check.py`（已在上一步写好 `check_rules`/`main`；本任务只补 `test_` 覆盖）
- Test: `tests/test_release_artifacts.py`（追加 `RepositoryStateTests` / `CliTests`）

**Interfaces:**
- Consumes: Task 1 的 `evaluate_rule` / `app_version` / `main` / `Finding`
- Produces: `dev_tools/release_artifacts.json`（`app_version_source` + `rules[]`，供 P2 技能与后续发版引用）

**规则表内容已实测**：下列 16 条 pattern 全部对着真实文件跑过，7 条干净、9 条精确命中四处漂移。

- [ ] **Step 1: 写失败测试**

在 `tests/test_release_artifacts.py` 的 `if __name__ == "__main__":` **之前**追加：

```python
class RepositoryStateTests(unittest.TestCase):
    """真实仓库的检查结果。

    本任务断言"检查器能检出已知漂移"；Task 3 修掉漂移后，
    这里的期望会翻转为"干净"。
    """

    # spec §2.4：四个已知漂移文件，共 9 个锚点
    KNOWN_DRIFT_IDS = {
        "mobile-css", "mobile-footer", "mobile-zh-footer",
        "readme-cn-title", "readme-cn-badge", "readme-cn-latest",
        "readme-en-title", "readme-en-badge", "readme-en-latest",
    }

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

    def test_detects_exactly_the_known_drift(self):
        """当前状态下，恰好这 9 个锚点漂移。"""
        registry = rc.load_registry()
        expected = rc.app_version(registry)
        failed = {f.rule_id for f in rc.check_rules(registry, expected)
                  if f.status == rc.FAIL}
        self.assertEqual(failed, self.KNOWN_DRIFT_IDS)

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
        """Task 3 修完漂移后本函数必须返回 0；当前应为 1。"""
        self.assertEqual(rc.main([]), 0)
```

**注意**：`test_main_is_clean_after_drift_fix` 在本任务会 **FAIL（返回 1）**，这是预期的红灯——它定义了 Task 3 的完成条件。

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest discover -s tests -p "test_release_artifacts.py" -v`
Expected: `RepositoryStateTests` 因缺 `release_artifacts.json` 全部 ERROR（`FileNotFoundError`）

- [ ] **Step 3: 写规则清单**

创建 `dev_tools/release_artifacts.json`：

```json
{
  "version": 1,
  "description": "MRRC 产物清单：每个携带版本号的文件在此登记一条规则。新文件开始携带版本/大小时必须补一条规则 —— 这是它不静默漂移的唯一保证。由 dev_tools/release_check.py 消费，tests/test_release_artifacts.py 在套件里执行。pattern 必须锚定到具体位置，绝不可裸扫 V[0-9.]+。",
  "app_version_source": {
    "path": "packaging/windows/MRRC.iss",
    "pattern": "#define MyAppVersion \"([0-9.]+)\"",
    "comment": "安装版本的唯一权威：build.ps1:79 与 dev_tools/release_windows.sh:39 都读它。权威只读不判，不出现在 rules 里。"
  },
  "rules": [
    {
      "id": "changelog-top",
      "path": "CHANGELOG.md",
      "pattern": "^## \\[(?:V)?([0-9]+\\.[0-9]+\\.[0-9]+)\\]",
      "first_only": true,
      "why": "人先改的地方；与 iss 不一致 = 有一条忘了改。顶部夹有 [Unreleased]/[未发布] 等非版本标题，故取首个匹配而非数条数。"
    },
    {
      "id": "mobile-css",
      "path": "www/mobile_modern.html",
      "pattern": "mobile_modern\\.css\\?v=([0-9.]+)",
      "count": 1,
      "why": "静态资源缓存戳；不改则手机端拿到旧 JS。"
    },
    {
      "id": "mobile-footer",
      "path": "www/mobile_modern.html",
      "pattern": "version-text\">MRRC V([0-9.]+)",
      "count": 1
    },
    {
      "id": "mobile-zh-footer",
      "path": "www/mobile_modern_zh.html",
      "pattern": "version-text\">MRRC V([0-9.]+)",
      "count": 1
    },
    {
      "id": "readme-title",
      "path": "README.md",
      "pattern": "\\(MRRC\\) V([0-9.]+)",
      "count": 1
    },
    {
      "id": "readme-badge",
      "path": "README.md",
      "pattern": "version-V([0-9.]+)-green\\.svg",
      "count": 1
    },
    {
      "id": "readme-cn-title",
      "path": "README_CN.md",
      "pattern": "\\(MRRC\\) V([0-9.]+)",
      "count": 1
    },
    {
      "id": "readme-cn-badge",
      "path": "README_CN.md",
      "pattern": "版本-V([0-9.]+)-green\\.svg",
      "count": 1
    },
    {
      "id": "readme-cn-latest",
      "path": "README_CN.md",
      "pattern": "最新版本: V([0-9.]+)",
      "count": 1,
      "why": "用户可见的\"当前版本\"声明，比 badge 更容易被当真。"
    },
    {
      "id": "readme-en-title",
      "path": "README_en.md",
      "pattern": "\\(MRRC\\) V([0-9.]+)",
      "count": 1
    },
    {
      "id": "readme-en-badge",
      "path": "README_en.md",
      "pattern": "version-V([0-9.]+)-green\\.svg",
      "count": 1
    },
    {
      "id": "readme-en-latest",
      "path": "README_en.md",
      "pattern": "Latest Version: V([0-9.]+)",
      "count": 1
    },
    {
      "id": "website-stat",
      "path": "website/index.html",
      "pattern": "stat-value\">V([0-9]+\\.[0-9]+\\.[0-9]+)",
      "count": 1,
      "why": "锚定到 HTML 属性；同一文件里还有 V6.1.0/V6.0.10 的历史举例，裸扫会误报。"
    },
    {
      "id": "website-headline",
      "path": "website/index.html",
      "pattern": "section-title\">V([0-9]+\\.[0-9]+\\.[0-9]+)",
      "count": 1
    },
    {
      "id": "website-zh-stat",
      "path": "website/zh/index.html",
      "pattern": "stat-value\">V([0-9]+\\.[0-9]+\\.[0-9]+)",
      "count": 1
    },
    {
      "id": "website-zh-headline",
      "path": "website/zh/index.html",
      "pattern": "section-title\">V([0-9]+\\.[0-9]+\\.[0-9]+)",
      "count": 1
    }
  ]
}
```

- [ ] **Step 4: 跑测试确认「检出了已知漂移」**

Run: `python3 -m unittest discover -s tests -p "test_release_artifacts.py" -v`
Expected: `test_detects_exactly_the_known_drift`、`test_registry_*`、`test_non_anchored_*` 全部 PASS；**仅** `test_main_is_clean_after_drift_fix` FAIL（返回 1）——这正是红灯。

- [ ] **Step 5: 人读一遍报告，确认 9 条漂移可读**

Run: `python3 dev_tools/release_check.py`
Expected: 输出 `安装版本权威 = 6.1.18`，随后 7 行 `ok`、9 行 `FAIL`，每条 FAIL 指出具体旧版本号。

- [ ] **Step 6: 提交**

```bash
git add dev_tools/release_artifacts.json tests/test_release_artifacts.py \
        dev_tools/release_check.py
git commit -m "feat(release): 产物清单 —— 16 条已实测的版本锚点规则"
```

---

### Task 3: 修掉四处现存漂移

**Files:**
- Modify: `www/mobile_modern.html`（`:13` 的 `?v=`、`:257` 的页脚）
- Modify: `www/mobile_modern_zh.html`（`:237` 的页脚）
- Modify: `README_CN.md`（`:1`、`:3` badge、`:389` "最新版本: V6.0.0"）
- Modify: `README_en.md`（`:1`、`:3` badge、`:365` "Latest Version: V6.0.0"）
- Test: `tests/test_release_artifacts.py`（把期望从"检出漂移"翻转为"干净"）

**Interfaces:**
- Consumes: Task 2 的规则表
- Produces: 检查器在真实仓库上返回 0（P2 技能与发布日清单依赖这条）

**纪律**：只改版本号本身。`README_CN.md`/`README_en.md` 里的**更新史**（如 `V6.0.0 更新亮点`）是历史记录，**不要动**——规则已锚定，不会因此报警。

- [ ] **Step 1: 改四个文件**

目标版本以 `python3 dev_tools/release_check.py` 打印的权威为准（当前为 `6.1.18`）。下面的字面量按当前值写。

`www/mobile_modern.html`：
- `:13` → `href="mobile_modern.css?v=6.1.18"`
- `:257` → `<span class="version-text">MRRC V6.1.18</span>`

`www/mobile_modern_zh.html`：
- `:237` → `<span class="version-text">MRRC V6.1.18</span>`

`README_CN.md`：
- `:1` → `# Mobile Remote Radio Control (MRRC) V6.1.18`
- `:3` → badge `版本-V6.1.18-green.svg`
- `:389` → `**最新版本: V6.1.18** (2026-09-17) | [查看更新日志](CHANGELOG.md)`

`README_en.md`：
- `:1` → `# Mobile Remote Radio Control (MRRC) V6.1.18`
- `:3` → badge `version-V6.1.18-green.svg`
- `:365` → `**Latest Version: V6.1.18** (2026-09-17) | [View Changelog](CHANGELOG.md)`

- [ ] **Step 2: 翻转测试期望**

在 `tests/test_release_artifacts.py` 里：
- 删掉 `KNOWN_DRIFT_IDS` 与 `test_detects_exactly_the_known_drift`（漂移已不存在，这条测试失去意义）
- 把 `test_main_is_clean_after_drift_fix` 的文档串改为 `"""漂移已修：真实仓库必须干净。"""`

```python
    def test_main_is_clean_after_drift_fix(self):
        """漂移已修：真实仓库必须干净。"""
        self.assertEqual(rc.main([]), 0)

    def test_main_is_clean_in_strict_mode(self):
        """发布日形态：不允许任何 SKIP（当前无 optional 规则，故同样应为 0）。"""
        self.assertEqual(rc.main(["--strict"]), 0)
```

- [ ] **Step 3: 跑测试确认全绿**

Run: `python3 -m unittest discover -s tests -p "test_release_artifacts.py" -v`
Expected: 全部 PASS

- [ ] **Step 4: 人工复核检查器输出**

Run: `python3 dev_tools/release_check.py`
Expected: `安装版本权威 = 6.1.18`，16 行全 `ok`，退出码 0（`echo $?`）

- [ ] **Step 5: 确认没误伤历史记录**

Run: `grep -n 'V6.0.10\|V6.1.0' README.md README_CN.md README_en.md website/index.html | head`
Expected: 更新史与历史举例**仍在**（只是不再被规则覆盖）

- [ ] **Step 6: 提交**

```bash
git add www/mobile_modern.html www/mobile_modern_zh.html README_CN.md \
        README_en.md tests/test_release_artifacts.py
git commit -m "fix(release): 补齐 6.1.18 遗漏的四处版本同步（手机页脚/CSS 缓存戳、中英 README）"
```

---

### Task 4: 派生链守卫与文档接线

**Files:**
- Modify: `tests/test_release_artifacts.py`（追加 `VersionTxtDerivationTests`）
- Modify: `AGENTS.md`（在「Existing Guidance」附近加一行）

**Interfaces:**
- Consumes: 无
- Produces: 一条防回归守卫 + 团队可见的入口说明

**背景**：`packaging/windows/build.ps1:79-86` 从 `MRRC.iss` 读出 `MyAppVersion` 写进 `dist/windows/MRRC/version.txt`；运行时 `windows/launcher.py:108-114` 读它。**产物里没有任何编译进去的版本常量**——一旦有人把版本硬编码进 `build.ps1`，运行时会静默脱离权威。这条守卫就是钉住这个。

- [ ] **Step 1: 写失败测试**

在 `tests/test_release_artifacts.py` 的 `if __name__ == "__main__":` **之前**追加（不要追加到文件最末，那会落在 `unittest.main()` 之后）：

```python
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
```

- [ ] **Step 2: 跑测试**

Run: `python3 -m unittest discover -s tests -p "test_release_artifacts.py" -v`
Expected: PASS（现状本就满足）。若不通过，说明派生链已被改坏 —— 先查 `build.ps1:79`，不要改测试。

- [ ] **Step 3: 验证守卫真的会抓**

临时把 `packaging/windows/build.ps1` 里的 `MyAppVersion` 改成 `MyAppVer`：
Run: `python3 -m unittest discover -s tests -p "test_release_artifacts.py" -v`
Expected: `test_windows_build_derives_version_txt_from_iss` **FAIL**
然后 `git checkout packaging/windows/build.ps1` 复原。

- [ ] **Step 4: 接线 AGENTS.md**

在 `AGENTS.md` 的「Existing Guidance」小节**之前**插入新的一节：

```markdown
## 发布完成度检查
- `python3 dev_tools/release_check.py` 校验"该跟安装版本一致的文件是否真的一致"；
  `--strict` 把 SKIP 也算失败（发布日用），`--json` 给机器读。权威 = `packaging/windows/MRRC.iss`
  的 `MyAppVersion`（`build.ps1` 与 `dev_tools/release_windows.sh` 都读它）。
- 规则表 `dev_tools/release_artifacts.json`：**新文件开始携带版本/大小时必须补一条规则**，
  否则它会静默漂移。规则 pattern 必须锚定到具体位置，**绝不可裸扫 `V[0-9.]+`**——
  `README.md` 的更新史与 `website/index.html` 的历史举例会被误判。
- `tests/test_release_artifacts.py` 在套件里跑它；发版收尾必跑一次 `--strict`。
```

- [ ] **Step 5: 全量回归**

Run: `python3 -m unittest discover -s tests -v`
Expected: 全部 PASS（含既有测试；若既有测试本就失败，记录基线，不要在本任务里修）

- [ ] **Step 6: 提交**

```bash
git add tests/test_release_artifacts.py AGENTS.md
git commit -m "test(release): version.txt 派生链守卫 + AGENTS.md 记述检查器用法"
```

---

## 验收

P1 完成时：

```bash
python3 dev_tools/release_check.py --strict && echo "checker clean"
python3 -m unittest discover -s tests -p "test_release_artifacts.py" -v
```

两条都必须干净。此后 P2（三个技能）才有可引用的命令。

## 与 spec 的对应

| spec 章节 | 本计划任务 |
|---|---|
| §4.1 交付物（三文件落点） | T1（检查器+测试）、T2（规则表） |
| §4.2 规则 schema | T1（`validate_rule`）、T2（JSON） |
| §4.3 规则清单（16 条已实测） | T2 |
| §4.4 CLI 与退出码 | T1（`main`） |
| §4.5 测试四项 | T1（规则引擎单测）、T2（仓库态）、T3（修漂移后干净）、T4（构建步守卫） |
| §2.4 四处现存漂移 | T3 |
| §7 P1 完成判据 | 验收节 |

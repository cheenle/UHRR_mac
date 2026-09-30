#!/usr/bin/env python3
"""MRRC 发布完成度检查器 —— 回答"本次发版有没有漏改文件"。

权威：packaging/windows/MRRC.iss 的 MyAppVersion（build.ps1 与
      dev_tools/release_windows.sh 都读它）。
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

# 捕获组的起点；`(?:...)` 不算
_CAPTURE_START = re.compile(r"(?<!\\)\((?!\?)")
_REGEX_META = re.compile(r"[\\^$.|?*+(){}\[\]]")
# 裸版本扫描里会出现的字符——只有这些不算"具体上下文"
_VERSION_ONLY = set("0123456789. \tVv")


class Finding(NamedTuple):
    rule_id: str
    path: str
    status: str
    detail: str = ""


def _has_anchor(pattern: str) -> bool:
    """捕获组之前是否留有"具体上下文"（属性名 / 标签 / 行首）。"""
    m = _CAPTURE_START.search(pattern)
    if m is None:
        return True          # 没有捕获组：无可判定的锚点，交给别处报错
    prefix = _REGEX_META.sub("", pattern[:m.start()])
    return any(ch not in _VERSION_ONLY for ch in prefix)


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
    if not _has_anchor(rule["pattern"]):
        raise ValueError(
            f"规则 {rule['id']!r} 的 pattern 未锚定：捕获组前必须有具体上下文"
            f"（属性名/标签/行首），不能裸扫 V([0-9.]+)——README 的更新史与"
            f"网站的历史举例会被判成漂移")


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


def _report(expected: str, findings: list) -> None:
    print(f"安装版本权威 = {expected}")
    print(f"规则 {len(findings)} 条：")
    for f in findings:
        print(f"  {_MARK[f.status]} {f.rule_id:<22} {f.path:<34} {f.detail}")


def main(argv=None, registry_path: Path = REGISTRY_PATH) -> int:
    parser = argparse.ArgumentParser(description="MRRC 发布完成度检查")
    parser.add_argument("--json", action="store_true", help="机器可读输出")
    parser.add_argument("--strict", action="store_true",
                        help="SKIP 也算失败（发布日用）")
    args = parser.parse_args(argv)

    try:
        registry = load_registry(registry_path)
        rules = registry["rules"]
        if not isinstance(rules, list):
            raise ValueError(f"rules 必须是列表，实际是 {type(rules).__name__}")
        for rule in rules:
            if not isinstance(rule, dict):
                raise ValueError(f"每条规则必须是对象，实际是 {rule!r}")
            validate_rule(rule)
        expected = app_version(registry)
    except (OSError, KeyError, ValueError, TypeError, AttributeError,
            json.JSONDecodeError) as exc:
        print(f"清单或权威不可用：{exc}", file=sys.stderr)
        return 2

    findings = check_rules(registry, expected)
    if args.json:
        print(json.dumps(
            {"version": expected,
             "findings": [dict(f._asdict()) for f in findings]},
            ensure_ascii=False, indent=2))
    else:
        _report(expected, findings)

    has_fail = any(f.status == FAIL for f in findings)
    has_skip = any(f.status == SKIP for f in findings)
    if has_fail or (args.strict and has_skip):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

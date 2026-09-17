#!/usr/bin/env python3
"""MRRC 网站全站体检（一次性回答"哪里滞后/断链/样式不统一"）

覆盖：
  1. 站内链接断链（所有页面，含 zh/、efhw/）
  2. 样式统一（是否引主站 css/style.css）+ nav 项数分布
  3. 版本串体检（页面上出现旧版本却没有当前版本 → 可能滞后）
  4. 新能力入口覆盖（答复页 / 一键升级 / 诊断包 / 支持生命周期）
  5. 中英成对情况（含 efhw/）与 nav 结构一致性（归一化后比对）

用法：
    python3 dev_tools/site_audit.py            # 人读报告
    python3 dev_tools/site_audit.py --json     # 机器可读（tests 用）
    python3 dev_tools/site_audit.py --strict   # 有发现则退出码 1（CI/测试用）

退出码：0 干净 / 1 有发现（仅 --strict）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

REPO = Path(__file__).resolve().parents[1]
SITE = REPO / "website"
ISS = REPO / "packaging" / "windows" / "MRRC.iss"

# 允许仅英文（深度设计文档；answers 本身中英双语单页）
# efhw/ 正文本身为中文（两篇工程指南 + 中文入口），因此不要求中英逐一镜像
EN_ONLY_ALLOWED = ("docs/design/", "answers/", "efhw/")
# 中文站独有的入口页（英文树已有 docs/design.html 作为对应）
ZH_ONLY_ALLOWED = ("docs/design/index.html",)
# 不随仓库发布的大文件（视频等），缺失只提示不算失败
EXTERNAL_BIG_ASSETS = ("videos", "downloads")   # 目录名：视频；安装包（只随发布上传，不入库）
# 主站样式表集合（顺序敏感）：style.css → octen.css?v=5 → sunsdrmobile.css → [docs.css]
CANON_CSS = ["css/style.css", "css/octen.css?v=5", "css/sunsdrmobile.css?v=1"]


def current_version() -> str:
    m = re.search(r'MyAppVersion\s+"([^"]+)"', ISS.read_text(encoding="utf-8"))
    return m.group(1) if m else ""


def pages() -> list[Path]:
    return sorted(SITE.rglob("*.html"))


def rel(p: Path) -> str:
    return p.relative_to(SITE).as_posix()


def _resolved(page: Path, href: str) -> str | None:
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("#"):
        return None
    path_part = href.split("#")[0].split("?")[0]
    if not path_part:
        return None
    stack: list[str] = []
    for seg in (page.parent.relative_to(SITE) / path_part).as_posix().split("/"):
        if seg == "..":
            if stack:
                stack.pop()
        elif seg not in ("", "."):
            stack.append(seg)
    return "/".join(stack)


def _strip_zh(path: str) -> str:
    return path[3:] if path.startswith("zh/") else path


def nav_targets(page: Path) -> list[str] | None:
    text = page.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<nav.*?</nav>", text, re.S)
    if not m:
        return None
    own = _strip_zh(page.relative_to(SITE).as_posix())
    out = []
    for tag in re.findall(r"<a\s[^>]*>", m.group(0)):
        if "lang-btn" in tag:
            continue
        hm = re.search(r'href="([^"]*)"', tag)
        if not hm:
            continue
        t = _resolved(page, hm.group(1))
        if t is None:
            continue
        if not t.startswith(("http://", "https://")):
            t = _strip_zh(t)
            if t == own:
                continue
        out.append(t)
    return out


def audit() -> dict:
    ver = current_version()
    pages_ = pages()
    result: dict = {"version": ver, "pages": len(pages_),
                    "broken_links": [], "external_assets": [], "missing_style": [],
                    "css_drift": [], "nav_counts": {},
                    "stale_version_pages": [], "missing_zh": [], "missing_en": [],
                    "nav_mismatch": [], "capability_coverage": {}}

    for p in pages_:
        text = p.read_text(encoding="utf-8", errors="replace")
        # 1) 断链
        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith(("http://", "https://", "mailto:", "javascript:", "#", "/", "data:")):
                continue                      # 站根绝对路径/内联数据无法在磁盘校验
            target = href.split("#")[0].split("?")[0]
            if not target:
                continue
            t = (p.parent / unquote(target)).resolve()
            if t.is_dir():
                t = t / "index.html"
            if not t.exists():
                norm = target.lstrip("./")          # ../downloads/x → downloads/x
                if any(a.rstrip("/") in norm.split("/") for a in EXTERNAL_BIG_ASSETS):
                    result["external_assets"].append(f"{rel(p)} → {href}")
                else:
                    result["broken_links"].append(f"{rel(p)} → {href}")
        # 2) 样式表集合与顺序（主站统一风格）
        links = re.findall(r'<link rel="stylesheet" href="([^"]+)"', text)
        css = [re.sub(r'^(\.\./)+', '', l) for l in links if not l.startswith("http")]
        if css:
            head = css[:3]
            want = CANON_CSS + (["css/docs.css"] if "docs.css" in " ".join(css) else [])
            if head != CANON_CSS or css[:len(want)] != want:
                result["css_drift"].append(f"{rel(p)} → {css[:4]}")
        # 3) 样式 + nav
        nav = re.search(r"<nav.*?</nav>", text, re.S)
        if nav:
            result["nav_counts"][rel(p)] = len(re.findall(r"<a\s[^>]*>", nav.group(0)))
            if "css/style.css" not in text:
                result["missing_style"].append(rel(p))
        # 3) 版本
        vers = set(re.findall(r"V(\d+\.\d+\.\d+)", text))
        old = [v for v in vers if v.startswith(("5.", "6.0", "6.1")) and v != ver]
        if old and ver not in vers:
            result["stale_version_pages"].append(f"{rel(p)}（只有 {sorted(old)[:4]}）")
        # 4) 能力入口
        for key in ("answers/", "update", "support", "product-support-lifecycle"):
            if key in text:
                result["capability_coverage"].setdefault(key, []).append(rel(p))

    en = {rel(p) for p in pages_ if not rel(p).startswith("zh/")}
    zh = {rel(p)[3:] for p in SITE.glob("zh/**/*.html")}
    result["missing_zh"] = sorted(x for x in en
                                  if not any(x.startswith(a) for a in EN_ONLY_ALLOWED)
                                  and x not in zh)
    result["missing_en"] = sorted(
        x for x in zh
        if not any(x.startswith(a) for a in ZH_ONLY_ALLOWED) and x not in en)

    for p in sorted(SITE.glob("zh/**/*.html")):
        r = p.relative_to(SITE / "zh").as_posix()
        e = SITE / r
        if not e.exists():
            continue
        a, b = nav_targets(e), nav_targets(p)
        if a is not None and b is not None and a != b:
            result["nav_mismatch"].append(
                f"{r}: 仅英文有 {[x for x in a if x not in b]} / 仅中文有 {[x for x in b if x not in a]}")
    result["broken_links"] = sorted(set(result["broken_links"]))
    return result


def report(r: dict) -> None:
    print(f"MRRC 网站体检 · 当前版本 V{r['version']} · 共 {r['pages']} 页\n")
    sections = [
        ("站内断链", r["broken_links"]),
        ("未引主站 style.css", r["missing_style"]),
        ("样式表集合/顺序与主站不一致", r["css_drift"]),
        ("外部大文件（视频等，未随仓库发布）", r["external_assets"]),
        ("可能滞后（有旧版本但无当前版本）", r["stale_version_pages"]),
        ("缺中文镜像", r["missing_zh"]),
        ("缺英文对应（中文独有）", r["missing_en"]),
        ("nav 结构不一致", r["nav_mismatch"]),
    ]
    for title, items in sections:
        print(f"== {title}：{len(items)} ==")
        for x in items[:20]:
            print("   -", x)
        if len(items) > 20:
            print(f"   … 另 {len(items) - 20} 条")
        print()
    print("== nav 项数分布 ==", dict(Counter(r["nav_counts"].values())))
    print("\n== 新能力入口覆盖（页面数）==")
    for k, v in sorted(r["capability_coverage"].items(), key=lambda kv: -len(kv[1])):
        print(f"   {k}: {len(v)} 页")


def main() -> int:
    ap = argparse.ArgumentParser(description="MRRC 网站全站体检")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--strict", action="store_true", help="有发现则退出码 1")
    args = ap.parse_args()
    r = audit()
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        report(r)
    findings = (r["broken_links"] + r["missing_style"] + r["missing_zh"]
                + r["missing_en"] + r["nav_mismatch"] + r["css_drift"])
    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

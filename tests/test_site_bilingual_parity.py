"""中英文站点同步守卫（用户报"中文版滞后很多"驱动）

三条结构性断言：
1. **用户可见页面必须有中文镜像**（`website/zh/**`）——深度设计文档 `docs/design/*` 与
   本身中英双语的 `answers/` 允许仅英文；
2. 成对页面的**导航结构一致**：把每个 `<a>` 的 href 归一化成"站内路径"后比对
   （排除语言切换按钮 lang-btn —— 它必然指向另一种语言；排除指向本页自身的链接 ——
   有的页写 `#`、有的写 `index.html`，等价）；深度不同（`../` 数量）归一化后应一致。
3. 主要中文页面**必须出现当前版本号**（版本语义的"唯一权威"在 `packaging/windows/MRRC.iss`）。

翻译内容无法自动比对，但这三条能挡住"结构性滞后"。
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SITE = REPO / "website"
# 允许仅英文的目录：深度设计文档（SDD/API/SPEC…）；答案是中英双语单页
EN_ONLY_ALLOWED = ("docs/design/", "answers/")


def current_version() -> str:
    text = (REPO / "packaging" / "windows" / "MRRC.iss").read_text(encoding="utf-8")
    m = re.search(r'MyAppVersion\s+"([^"]+)"', text)
    return m.group(1) if m else ""


def _resolved(page: Path, href: str) -> str | None:
    """把相对 href 解析成站内路径；页内锚点返回 None。"""
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("#"):
        return None
    path_part, _, frag = href.partition("#")
    stack = []
    for seg in (page.parent.relative_to(SITE) / path_part).as_posix().split("/"):
        if seg == "..":
            if stack:
                stack.pop()
        elif seg not in ("", "."):
            stack.append(seg)
    out = "/".join(stack)
    return out + (("#" + frag) if frag else "")


def _strip_zh(path: str) -> str:
    return path[3:] if path.startswith("zh/") else path


def nav_items(page: Path):
    """nav 里所有 `<a>` 的归一化目标（排除 lang-btn 与指向本页自身的链接）。"""
    if not page.exists():
        return None
    text = page.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<nav.*?</nav>", text, re.S)
    if not m:
        return None
    own = _strip_zh(page.relative_to(SITE).as_posix())
    out = []
    for tag in re.findall(r"<a\s[^>]*>", m.group(0)):
        if "lang-btn" in tag:
            continue
        href_m = re.search(r'href="([^"]*)"', tag)
        if not href_m:
            continue
        target = _resolved(page, href_m.group(1))
        if target is None:
            continue
        if not target.startswith(("http://", "https://")):
            target = _strip_zh(target)
            if target.split("#")[0] == own:
                continue                      # 指向本页自身（写 # 或 index.html 都算）
        out.append(target)
    return out


class BilingualParityTest(unittest.TestCase):
    def test_user_facing_pages_have_chinese_mirror(self):
        missing = []
        for page in sorted(SITE.rglob("*.html")):
            rel = page.relative_to(SITE).as_posix()
            if rel.startswith(("zh/", "efhw/")):
                continue
            if any(rel.startswith(a) for a in EN_ONLY_ALLOWED):
                continue
            if not (SITE / "zh" / rel).exists():
                missing.append(rel)
        self.assertEqual(missing, [],
                         "以下英文页缺中文镜像（中文版会滞后）：" + ", ".join(missing))

    def test_nav_structure_matches(self):
        mismatched = []
        for page in sorted((SITE / "zh").rglob("*.html")):
            rel = page.relative_to(SITE / "zh").as_posix()
            en = SITE / rel
            if not en.exists():
                continue
            a, b = nav_items(en), nav_items(page)
            if a is None or b is None:
                continue
            if a != b:
                only_en = [x for x in a if x not in b]
                only_zh = [x for x in b if x not in a]
                mismatched.append(f"{rel}: EN {len(a)} 项 / ZH {len(b)} 项；"
                                  f"仅英文有 {only_en}；仅中文有 {only_zh}")
        self.assertEqual(mismatched, [], "中英导航结构不一致：\n" + "\n".join(mismatched))

    def test_chinese_key_pages_show_current_version(self):
        ver = current_version()
        self.assertTrue(ver, "无法从 MRRC.iss 解析当前版本号")
        stale = []
        for rel in ("zh/index.html", "zh/docs/installation.html", "zh/docs/windows-fix.html"):
            page = SITE / rel
            if not page.exists():
                continue
            text = page.read_text(encoding="utf-8", errors="replace")
            if f"V{ver}" not in text and f"v{ver}" not in text:
                stale.append(rel)
        self.assertEqual(stale, [],
                         f"以下中文页未出现当前版本 V{ver}（版本会漂移）：" + ", ".join(stale))


if __name__ == "__main__":
    unittest.main(verbosity=2)

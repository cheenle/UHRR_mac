"""中英文站点同步守卫（用户报"中文版滞后很多"驱动）

检查三件事：
1. **用户可见页面必须有中文镜像**（`website/zh/**`）——深度设计文档 `docs/design/*` 允许仅英文；
2. 成对页面的**导航项数量一致**（nav 是硬约定，结构漂移会让中文用户跳错页）；
3. 主要中文页面**必须出现当前版本号**（版本语义的"唯一权威"在 MRRC.iss）。

中英内容不可能自动比对（翻译是人工的），但这三条能挡住"结构性滞后"。
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SITE = REPO / "website"
EN_ONLY_ALLOWED = ("docs/design/",)          # 深度设计文档（SDD/API/SPEC…）允许仅英文


def current_version() -> str:
    text = (REPO / "packaging" / "windows" / "MRRC.iss").read_text(encoding="utf-8")
    m = re.search(r'MyAppVersion\s+"([^"]+)"', text)
    return m.group(1) if m else ""


def nav_items(path: Path):
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<nav.*?</nav>", text, re.S)
    if not m:
        return None
    return re.findall(r"<a[^>]*>", m.group(0))


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
            if len(a) != len(b):
                mismatched.append(f"{rel}: EN {len(a)} 项 vs ZH {len(b)} 项")
        self.assertEqual(mismatched, [], "中英导航项数不一致：\n" + "\n".join(mismatched))

    def test_chinese_key_pages_show_current_version(self):
        ver = current_version()
        self.assertTrue(ver, "无法从 MRRC.iss 解析当前版本号")
        key_pages = ["zh/index.html", "zh/docs/installation.html", "zh/docs/windows-fix.html"]
        stale = []
        for rel in key_pages:
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

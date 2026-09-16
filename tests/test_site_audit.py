"""网站全站体检（严格模式）：断链 / 中文镜像 / nav / 样式统一 / CSS 集合漂移。

把 dev_tools/site_audit.py 的审计接进测试，任何"真实发现"都让测试失败 ——
这样"中文版滞后""样式不统一""页面断链"不会再悄悄发生。
（外部大文件如 videos/*.mp4 缺失只作提示，不算失败。）
"""

import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "dev_tools"))

import site_audit  # noqa: E402


class SiteAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = site_audit.audit()

    def test_no_broken_internal_links(self):
        self.assertEqual(self.r["broken_links"], [],
                         "站内断链：\n" + "\n".join(self.r["broken_links"]))

    def test_every_page_has_chinese_mirror(self):
        self.assertEqual(self.r["missing_zh"], [],
                         "缺中文镜像：\n" + "\n".join(self.r["missing_zh"]))

    def test_nav_structure_consistent(self):
        self.assertEqual(self.r["nav_mismatch"], [],
                         "nav 结构不一致：\n" + "\n".join(self.r["nav_mismatch"]))

    def test_stylesheets_unified(self):
        self.assertEqual(self.r["missing_style"], [],
                         "未引主站 style.css：\n" + "\n".join(self.r["missing_style"]))
        self.assertEqual(self.r["css_drift"], [],
                         "样式表集合/顺序漂移：\n" + "\n".join(self.r["css_drift"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)

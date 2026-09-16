"""内联 JS 语法守卫（真实事故驱动）

2026-09-17 事故：`www/support.html` 里为"答复页链接"拼接字符串时多了一个引号，
把单引号字符串提前终结 → 整页唯一的 `<script>` 语法错 → **生成诊断包/上传/只存本地
所有按钮全部失效**（用户报"客户端生成诊断包咋不工作了"），并且这个坏文件随热修
下发给了所有用户。

本测试用 `node --check` 校验 `www/*.html` 与 `website/**/*.html` 里的内联脚本；
没有 node 时跳过（不阻塞无 node 的环境）。
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class InlineJsSyntaxTest(unittest.TestCase):
    def test_inline_scripts_parse(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("未安装 node，跳过内联 JS 语法检查")
        pages = sorted(list((REPO / "www").glob("*.html"))
                       + list((REPO / "website").rglob("*.html")))
        self.assertGreater(len(pages), 5, "页面数量异常，路径可能写错")
        failures = []
        with tempfile.TemporaryDirectory() as tmp:
            for page in pages:
                html = page.read_text(encoding="utf-8", errors="replace")
                blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
                for i, js in enumerate(blocks):
                    if not js.strip():
                        continue
                    f = Path(tmp) / f"{page.stem}_{i}.js"
                    f.write_text(js, encoding="utf-8")
                    r = subprocess.run([node, "--check", str(f)],
                                       capture_output=True, text=True)
                    if r.returncode != 0:
                        lines = [ln.strip() for ln in (r.stderr or "").splitlines() if ln.strip()]
                        failures.append(f"{page.relative_to(REPO)} [script {i}]: "
                                        + (lines[0] if lines else "语法错误"))
        self.assertEqual(failures, [], "内联 JS 语法错误（会让整页按钮失效）：\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main(verbosity=2)

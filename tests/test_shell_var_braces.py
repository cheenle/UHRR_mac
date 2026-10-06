#!/usr/bin/env python3
"""守卫：shell 脚本里 `$VAR` 后面**不能紧跟非 ASCII 字符**。

为什么这是个真缺陷（2026-10-06 在 dev_tools/release_windows.sh 上实测命中）：

macOS 的 bash（5.3）在 UTF-8 locale 下解析 `$VAR` 时，会把紧跟其后的**高位字节吃进变量名**。
于是 `"...$HOST（网络..."` 实际查的是名为 `HOST\\xef\\xbc\\x88...` 的变量；脚本开着
`set -u`，结果就是 `未绑定的变量` 并**整个脚本退出**。换成 `LC_ALL=C` 就一切正常 ——
所以它是**依赖 locale 的静默故障**，本地随手一跑常常发现不了。

实测对照（LANG=zh_CN.UTF-8 vs LC_ALL=C）：

    HOST="ham.vlsc.net"
    echo "T1: $HOST（网络"     # zh_CN.UTF-8 → 行 3: HOST？: 未绑定的变量，EXIT=1
    echo "T2: ${HOST}（网络"   # 两种 locale 都正常

命中的三处都在 release_windows.sh，其中一处位于**成功路径**：
  :64  `echo "❌ 无法连接 $HOST（网络/DDNS？）"`   —— 连接失败时才走，所以以前没暴露
  :173 `ok "main 已快进到 $CUR_BRANCH（发版…）"`   —— 本版新加，dry-run 当场炸
  :188 `ok "线上文件与本地逐字节一致（$LIVE_SHA）"` —— **每次发版成功都会走到**
修法统一为 `${VAR}`。

本测试扫全仓 .sh（跳过 venv/dist/.git），把这个不变量钉住，防止再写回去。
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", "venv", "dist", "build", "node_modules", "__pycache__", "payload"}

# `$名字` 后紧跟一个非 ASCII 字符
BAD = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)([^\x00-\x7f])")


def shell_scripts() -> list[Path]:
    out = []
    for p in ROOT.rglob("*.sh"):
        if SKIP_PARTS & set(p.relative_to(ROOT).parts):
            continue
        out.append(p)
    return sorted(out)


class ShellVarBraceTests(unittest.TestCase):
    def test_there_are_shell_scripts_to_check(self):
        """空集合会让本测试变成装饰品 —— 至少得扫到几个脚本。"""
        self.assertGreaterEqual(len(shell_scripts()), 3)

    def test_no_bare_var_followed_by_non_ascii(self):
        offenders = []
        for path in shell_scripts():
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                for m in BAD.finditer(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{lineno}: "
                                     f"${m.group(1)}＋非ASCII → 应写 ${{{m.group(1)}}}")
        self.assertEqual(
            offenders, [],
            "下列位置在 UTF-8 locale + set -u 下会报「未绑定的变量」并中止脚本：\n  "
            + "\n  ".join(offenders))

    def test_release_script_specifically_is_clean(self):
        """发版编排脚本在成功路径上，最值得单独钉一条。"""
        path = ROOT / "dev_tools" / "release_windows.sh"
        self.assertTrue(path.is_file(), path)
        text = path.read_text(encoding="utf-8", errors="replace")
        self.assertEqual([m.group(0) for m in BAD.finditer(text)], [])


if __name__ == "__main__":
    unittest.main()

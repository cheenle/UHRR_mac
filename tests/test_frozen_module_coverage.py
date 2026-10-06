#!/usr/bin/env python3
"""守卫：冻结包必须能解析到松散代码 import 的每一个本地模块。

为什么需要这条（V6.2.0 洁净室实测，见 docs/current/reliability/RC-006）：

本仓的冻结入口 `packaging/pyinstaller/frozen_entry.py` **不**直接 import 应用代码，而是
把 `_internal/app` 加进 sys.path 后用 `runpy.run_path(_internal/app/MRRC)` 跑它 ——
这是热修覆盖层能生效的前提（PyInstaller 6 的 PyiFrozenFinder 会截走 PYZ 内同名模块，
磁盘上的 .py 覆盖无效，所以应用代码必须留在 PYZ 外）。

代价是：**PyInstaller 的 Analysis 看不到 MRRC 的任何 import**。一个模块要想进包，
必须被显式登记在两处之一：

  * `_APP_MODULES`  → 作为数据文件发到 `_internal/app/<name>.py`（松散、可热修）
  * `hiddenimports` → 冻进 PYZ

`antenna_sweep` 两处都没有（MRRC:2675 的注释明明写着它是"松散模块"），于是它既不在
PYZ 里、也没被当数据文件发出。前三层验证全绿 —— 产物时间戳/大小/SHA 都对、
结构核对 20 个松散 .py 一个不缺、符号走查也过 —— 只有**真跑一次**才炸：

    ModuleNotFoundError: No module named 'antenna_sweep'
    [PYI-xxxx:ERROR] Failed to execute script 'frozen_entry' due to unhandled exception!

即安装包**一启动就死**。这类缺陷靠"构建成功"和退出码永远发现不了。
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "pyinstaller" / "mrrc_server.spec"
APP_ENTRY = ROOT / "MRRC"


def _spec_text() -> str:
    return SPEC.read_text(encoding="utf-8")


def _app_modules() -> list[str]:
    """从 spec 里取 _APP_MODULES 的字面量列表（用 ast，不做子串匹配）。"""
    text = _spec_text()
    start = text.index("_APP_MODULES = [")
    end = text.index("]", start)
    node = ast.parse(text[start + len("_APP_MODULES = "):end + 1], mode="eval").body
    # 先收窄到 ast.List 再取 .elts：ast.Expression.body 的静态类型是 expr，
    # 而 .elts 只存在于 List/Tuple/Set 上；常量值也要先确认是 str。
    if not isinstance(node, ast.List):
        raise AssertionError("_APP_MODULES 不是字面量列表，无法静态解析")
    return [e.value for e in node.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)]


def _hiddenimports() -> set[str]:
    """取 Analysis(hiddenimports=[...]) 里的字面量（`*_APP_MODULES` 展开另算）。"""
    tree = ast.parse(_spec_text())
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "hiddenimports":
            if isinstance(node.value, ast.List):
                for e in node.value.elts:
                    if isinstance(e, ast.Constant) and isinstance(e.value, str):
                        out.add(e.value.split(".")[0])
    return out


def _local_modules() -> set[str]:
    """仓库根的本地模块（松散模块的候选池）。"""
    return {p.stem for p in ROOT.glob("*.py")}


def _imports_of(path: Path) -> set[str]:
    """一个文件里所有顶层 import 的模块名。"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module.split(".")[0])
    return out


def _loose_sources() -> list[Path]:
    """运行时从磁盘加载、因此 PyInstaller 看不见其 import 的那些文件。"""
    srcs = [APP_ENTRY]
    for name in _app_modules():
        p = ROOT / f"{name}.py"
        if p.is_file():
            srcs.append(p)
    return srcs


class FrozenModuleCoverageTests(unittest.TestCase):
    def test_spec_and_entry_exist(self):
        self.assertTrue(SPEC.is_file(), SPEC)
        self.assertTrue(APP_ENTRY.is_file(), APP_ENTRY)

    def test_every_app_module_entry_is_a_real_file(self):
        """反方向：登记了却不存在的名字会静默少发一个模块（upgrade_core 漏过一次）。"""
        missing = [n for n in _app_modules() if not (ROOT / f"{n}.py").is_file()]
        self.assertEqual(missing, [], f"_APP_MODULES 里这些名字没有对应的 .py：{missing}")

    def test_loose_code_imports_are_all_covered(self):
        """正方向：松散代码 import 的每个本地模块都必须被登记，否则装完就 ModuleNotFoundError。"""
        covered = set(_app_modules()) | _hiddenimports() | {"MRRC"}
        local = _local_modules()
        gaps: dict[str, list[str]] = {}
        for src in _loose_sources():
            for mod in _imports_of(src):
                if mod in local and mod not in covered:
                    gaps.setdefault(mod, []).append(src.name)
        self.assertEqual(
            gaps, {},
            "下列本地模块被松散代码 import，但既不在 _APP_MODULES 也不在 hiddenimports —— "
            "frozen_entry 用 runpy 跑 MRRC，PyInstaller 看不到这些 import，"
            "模块不会进包，安装后一启动就 ModuleNotFoundError：\n  "
            + "\n".join(f"{m} <- {', '.join(sorted(set(w)))}" for m, w in sorted(gaps.items())))

    def test_antenna_sweep_is_registered(self):
        """钉住这次实测抓到的那一个，防止被"顺手清理"掉。"""
        self.assertIn("antenna_sweep", _app_modules())
        self.assertTrue((ROOT / "antenna_sweep.py").is_file())

    def test_cloud_hub_modules_are_registered(self):
        """V6.2.0 的内网穿透三件套必须可热修（在 _APP_MODULES 里）。"""
        for name in ("cloud_hub", "session_metrics", "base_path"):
            with self.subTest(module=name):
                self.assertIn(name, _app_modules())
                self.assertTrue((ROOT / f"{name}.py").is_file())

    def test_app_modules_are_excluded_from_the_pyz(self):
        """_APP_MODULES 的意义就是"留在 PYZ 外"，spec 必须真的那样过滤。"""
        text = _spec_text()
        self.assertRegex(
            text, r"PYZ\(\s*\[\s*entry\s+for\s+entry\s+in\s+a\.pure\s+if\s+entry\[0\]\s+not\s+in\s+set\(_APP_MODULES\)",
            "spec 必须把 _APP_MODULES 从 PYZ 里过滤掉，否则热修覆盖层失效")

    def test_users_db_is_not_bundled(self):
        """RC-005：明文口令文件不得再进包。"""
        self.assertNotRegex(_spec_text(), r'\(\s*str\(ROOT\s*/\s*"MRRC_users\.db"\s*\)')


if __name__ == "__main__":
    unittest.main()

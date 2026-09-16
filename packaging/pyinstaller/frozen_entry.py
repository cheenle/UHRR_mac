"""MRRC-Server.exe 的冻结包入口（PyInstaller onedir）。

为什么不用 MRRC 直接当入口：见 `patch_overlay` 模块头部的实验记录 —— PyInstaller 6
的 PyiFrozenFinder 会截走 PYZ 内所有同名模块，磁盘上的 .py 覆盖**无效**；而没进 PYZ
的模块可以从 sys.path 正常加载。所以构建时把应用代码排除出 PYZ、作为数据文件放到
`_internal/app/`，本入口负责：

1. 把 `_internal/app` 加入 sys.path（应用代码从磁盘加载）；
2. 计算补丁覆盖层（`%LOCALAPPDATA%\\MRRC\\patch\\app`，见 patch_overlay），
   插到 sys.path 最前 —— 于是覆盖层里的同名 .py 优先；
3. 以 `__main__` 运行应用入口：覆盖层里有 `app/MRRC` 就用它，否则用内置的。

参数与真实入口保持一致（`MRRC-Server.exe <config>`），sys.argv 原样传给应用。
"""

import os
import sys


def _meipass():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))


def _bootstrap():
    meipass = _meipass()
    runtime_dir = os.path.dirname(os.path.abspath(sys.executable))
    app_dir = os.path.join(meipass, "app")
    config_path = sys.argv[1] if len(sys.argv) > 1 else None

    if os.path.isdir(app_dir) and app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    overlay_app = None
    try:
        import patch_overlay
        patch_overlay.configure(config_path=config_path, resource_dir=meipass,
                                runtime_dir=runtime_dir)
        patch_overlay.apply_python_path()
        patch_dir = patch_overlay.patch_dir()
        if patch_dir:
            overlay_app = os.path.join(patch_dir, "app")
            # 引擎自身也要可热修：上面的 import 已经加载了内置副本，若覆盖层里有
            # patch_overlay.py，就丢掉缓存重新加载（此后 MRRC 的 import 会拿到覆盖层版本）。
            if os.path.isfile(os.path.join(overlay_app, "patch_overlay.py")):
                import importlib
                sys.modules.pop("patch_overlay", None)
                patch_overlay = importlib.import_module("patch_overlay")
                patch_overlay.configure(config_path=config_path, resource_dir=meipass,
                                        runtime_dir=runtime_dir)
                patch_overlay.apply_python_path()
    except Exception as exc:                                    # 覆盖层坏了也必须能启动
        print(f"⚠️ 补丁覆盖层初始化失败（继续使用内置代码）: {exc}", flush=True)

    entry = os.path.join(app_dir, "MRRC")
    if overlay_app:
        candidate = os.path.join(overlay_app, "MRRC")
        if os.path.isfile(candidate):
            entry = candidate
    return entry


def main():
    entry = _bootstrap()
    if not os.path.isfile(entry):
        sys.stderr.write(f"❌ 找不到应用入口: {entry}\n")
        sys.exit(2)
    import runpy
    runpy.run_path(entry, run_name="__main__")


if __name__ == "__main__":
    main()

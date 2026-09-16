"""用户补丁覆盖层（hotfix overlay）——不重新打包即可修复已安装的 MRRC。

## 为什么需要这个模块

PyInstaller 6 的 onedir 包把应用自己的模块打进 exe 里的 PYZ。2026-09-14 的实测结论：

    pyinstaller 6.22.3 onedir，丢同名 .py 覆盖：
      exe 同目录 / _internal / cwd / PYTHONPATH   → 全部无效（仍是冻结版）
      sitecustomize                               → 冻结运行时连 site 都不导入，脚本不执行
    根因：PyiFrozenFinder 被插进 sys.path_hooks（PyInstaller/loader/pyimod02_importers.py），
          只要模块名在 PYZ 里，磁盘文件一律被截走。

但同一次实验也证明：**没有被打进 PYZ 的模块，可以从 sys.path 上的普通 .py 加载**
（往 `_internal/` 丢 `extra.py` → 成功导入）。所以打包时把自家代码排除出 PYZ、
作为数据文件放到 `_internal/app/`，运行时就退化成普通 Python 源码目录，
再在 `sys.path` 最前面插入覆盖层目录，即可实现"丢一个 .py 就修 bug"。

## 目录约定

覆盖层根目录（按优先级）：

1. 环境变量 `MRRC_PATCH_DIR`
2. 配置文件所在目录下的 `patch/`  ——  冻结安装时即 `%LOCALAPPDATA%\\MRRC\\patch`（用户可写，无需管理员）
3. 源码模式：仓库根目录下的 `patch/`

覆盖层内部布局与内置资源同构：

    patch/
      app/            ← 覆盖 _internal/app/：MRRC、config_io.py、wdsp_wrapper.py …
      www/            ← 覆盖 _internal/www/：controls.js、mobile_modern.html …
      vendor/         ← 覆盖 DLL：wdsp/windows/bin/x64/libwdsp.dll 或直接放 libwdsp.dll

## 用法

    import patch_overlay
    patch_overlay.configure(config_path=config_file, resource_dir=_resource_dir(),
                            runtime_dir=_runtime_dir())
    patch_overlay.log_status()                      # 启动日志里留一行证据
    path = patch_overlay.www_candidate("controls.js")   # 覆盖层优先，无则 None
    dirs = patch_overlay.dll_dirs()                 # 交给 ctypes 搜索路径
"""

import hashlib
import os

PATCH_DIR_ENV = "MRRC_PATCH_DIR"

# 覆盖层里各子目录的用途
SUBDIRS = ("app", "www", "vendor")

_state = {
    "patch_dir": None,      # 覆盖层根目录（可能不存在）
    "active": False,        # 覆盖层根目录存在且可用
    "app_dirs": [],         # sys.path 顺序：[patch/app, 内置 app]
    "www_candidates": [],   # [patch/www, 内置 www]（存在者）
    "dll_dirs": [],         # [patch/vendor, patch, 内置 vendor...]（存在者）
    "resources": [],        # 内置资源目录候选（frozen: _internal；源码: 仓库根）
    "runtime": None,
    "configured": False,
}


def _norm(path):
    return os.path.abspath(os.path.expanduser(path)) if path else None


def _ensure():
    """未显式 configure() 时按默认规则自动初始化（供独立工具/开发脚本调用）。"""
    if _state["configured"]:
        return
    config_path = None
    try:
        import sys as _sys
        if len(_sys.argv) > 1 and _sys.argv[1].endswith((".conf", ".ini")):
            config_path = _sys.argv[1]
    except Exception:
        pass
    configure(config_path=config_path, runtime_dir=os.getcwd())


def _default_patch_dir(config_path=None, runtime_dir=None):
    env = os.environ.get(PATCH_DIR_ENV)
    if env:
        return _norm(env)
    if config_path:
        return os.path.join(os.path.dirname(_norm(config_path)), "patch")
    if runtime_dir:
        return os.path.join(_norm(runtime_dir), "patch")
    return None


def configure(config_path=None, resource_dir=None, runtime_dir=None, patch_dir=None):
    """计算覆盖层路径。可重复调用（幂等）。

    config_path: 正在使用的配置文件路径（冻结安装时位于 %LOCALAPPDATA%\\MRRC）
    resource_dir: 内置只读资源根目录（frozen 为 sys._MEIPASS，源码为仓库根）
    runtime_dir: 可执行文件所在目录（frozen 为 exe 所在目录）
    patch_dir: 显式指定覆盖层根目录（优先级最高，测试用）
    """
    patch = _norm(patch_dir) or _default_patch_dir(config_path, runtime_dir)
    resource = _norm(resource_dir) or _norm(runtime_dir)
    runtime = _norm(runtime_dir)

    app_dirs = []
    www_candidates = []
    dll_dirs = []
    if patch:
        app_dirs.append(os.path.join(patch, "app"))
        www_candidates.append(os.path.join(patch, "www"))
        # DLL 允许平铺在 patch/ 或按内置结构放 patch/vendor/...
        dll_dirs.extend([os.path.join(patch, "vendor"), patch])
    if resource:
        app_dirs.append(os.path.join(resource, "app"))
        www_candidates.append(os.path.join(resource, "www"))
    if runtime:
        dll_dirs.append(os.path.join(runtime, "vendor"))

    # 去重并保留顺序
    def _uniq(seq):
        seen, out = set(), []
        for item in seq:
            if item and item not in seen:
                seen.add(item)
                out.append(item)
        return out

    _state["patch_dir"] = patch
    _state["active"] = bool(patch and os.path.isdir(patch))
    _state["app_dirs"] = _uniq(app_dirs)
    _state["www_candidates"] = _uniq(www_candidates)
    _state["bundled_www"] = os.path.join(resource, "www") if resource else None
    _state["dll_dirs"] = _uniq(dll_dirs)
    _state["resources"] = _uniq([resource])
    _state["runtime"] = runtime
    _state["configured"] = True
    return dict(_state)


def patch_dir():
    _ensure()
    return _state["patch_dir"]


def app_dirs():
    _ensure()
    return list(_state["app_dirs"])


def dll_dirs():
    """DLL 搜索目录，覆盖层在最前（含 patch/libwdsp.dll 这种平铺写法）。"""
    _ensure()
    dirs = list(_state["dll_dirs"])
    return [d for d in dirs if d and os.path.isdir(d)]


def bundled_www_root():
    """内置 www 目录（frozen 为 _MEIPASS/www，源码为仓库根/www）。"""
    _ensure()
    return _state["bundled_www"]


def www_candidate(rel_path):
    """返回 www 下某相对路径在覆盖层里的实际文件；覆盖层没有则返回 None。

    找不到时调用方应回落到内置资源（本函数不做回落，便于调用方自行决定）。
    """
    _ensure()
    rel_path = (rel_path or "").lstrip("/\\")
    if not rel_path:                       # '' 表示目录本身
        return None
    rel_path = rel_path.replace("/", os.sep).replace("\\", os.sep)
    patch = _state["patch_dir"]
    if not patch:
        return None
    candidate = os.path.normpath(os.path.join(patch, "www", rel_path))
    # 防目录穿越：必须仍在 patch/www 之内
    root = os.path.normpath(os.path.join(patch, "www"))
    if not candidate.startswith(root + os.sep):
        return None
    return candidate if os.path.isfile(candidate) else None


def apply_python_path():
    """把覆盖层代码目录插到 sys.path 最前（幂等）。返回最终顺序。

    只有在应用代码未被打进 PYZ（见 packaging/pyinstaller/mrrc_server.spec）时才有效。
    """
    import sys
    ordered = [d for d in _state["app_dirs"] if os.path.isdir(d)]
    for d in reversed(ordered):            # 反向插入 → 覆盖层落在最前
        while d in sys.path:
            sys.path.remove(d)
        sys.path.insert(0, d)
    return ordered


def _sha256(path, limit=None):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(262144)
                if not chunk:
                    break
                h.update(chunk)
                if limit is not None and fh.tell() >= limit:
                    break
    except OSError:
        return None
    return h.hexdigest()


def list_overlay_files(with_hash=False):
    """列出覆盖层里所有文件（相对路径 + 大小 [+ sha256]），用于状态上报/支持排查。"""
    _ensure()
    patch = _state["patch_dir"]
    if not patch or not os.path.isdir(patch):
        return []
    out = []
    for base, _dirs, files in os.walk(patch):
        for name in sorted(files):
            full = os.path.join(base, name)
            rel = os.path.relpath(full, patch).replace(os.sep, "/")
            try:
                size = os.path.getsize(full)
                mtime = os.path.getmtime(full)
            except OSError:
                continue
            item = {"path": rel, "size": size, "mtime": mtime}
            if with_hash:
                item["sha256"] = _sha256(full)
            out.append(item)
    return out


def describe(with_hash=False):
    """状态快照（供 WS 状态接口 / 日志使用）。

    active 动态判断而不缓存：热修包是服务运行中解压进覆盖层的，状态查询必须反映当下，
    否则页面/日志会一直显示"未启用"。
    """
    files = list_overlay_files(with_hash=with_hash)
    patch = _state["patch_dir"]
    return {
        "patchDir": patch,
        "active": bool(patch and os.path.isdir(patch)),
        "fileCount": len(files),
        "files": [f["path"] for f in files],
        "details": files if with_hash else None,
        "appDirs": _state["app_dirs"],
        "wwwCandidates": _state["www_candidates"],
        "dllDirs": dll_dirs(),
        "envOverride": os.environ.get(PATCH_DIR_ENV) or None,
    }


class OverlayStaticFilesMixin:
    """与 tornado.web.StaticFileHandler 组合使用：www 资源优先从覆盖层读。

    tornado 在 get() 里调 validate_absolute_path()，官方注释即说明“可在返回前修改路径”；
    故只需把命中的路径换成覆盖层里的同名文件，etag/range/content-type 全部沿用 tornado
    自身实现。本类不依赖 tornado（只用 os.path），因此可被单独单测。
    """

    def validate_absolute_path(self, root, absolute_path):
        bundled = bundled_www_root()
        if bundled:
            try:
                rel = os.path.relpath(absolute_path, bundled)
                if not rel.startswith(".."):
                    overlay = www_candidate(rel)
                    if overlay:
                        return overlay
            except Exception:
                pass
        return super().validate_absolute_path(root, absolute_path)


def _flush_print(message):
    """重定向到文件时 Python 默认块缓冲，启动日志会被吞掉——这里强制 flush。"""
    print(message, flush=True)


def log_status(printer=_flush_print):
    """启动时打印一行（含文件数），便于在用户日志里确认补丁是否生效。"""
    info = describe()
    if info["active"]:
        printer(f"🧩 补丁覆盖层已启用: {info['patchDir']}"
                f"（{info['fileCount']} 个文件：{', '.join(info['files'][:6])}"
                f"{' …' if info['fileCount'] > 6 else ''}）")
    else:
        printer(f"🧩 补丁覆盖层未启用（{info['patchDir'] or '未配置'}）")
    return info


if __name__ == "__main__":
    # 命令行自检：python3 patch_overlay.py [config_path]
    import sys as _sys
    _cfg = _sys.argv[1] if len(_sys.argv) > 1 else None
    configure(config_path=_cfg, runtime_dir=os.getcwd())
    import json as _json
    print(_json.dumps(describe(with_hash=True), indent=2, default=str))

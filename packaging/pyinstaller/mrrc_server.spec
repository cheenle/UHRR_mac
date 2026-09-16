# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder spec for the MRRC Tornado server.

Bundles the Tornado server, the browser UI, default configuration, and Windows
vendor runtime files.  The companion mrrc_launcher.spec builds the user-facing
desktop launcher.
"""
from pathlib import Path
import sys


ROOT = Path(SPECPATH).parents[1]


# ---------------------------------------------------------------------------
# 应用自身的代码（MRRC + 同级模块）不进 PYZ，而是作为数据文件放到 _internal/app/。
#
# 原因（2026-09-14 实测，见 patch_overlay.py 头部）：PyInstaller 6 的 PyiFrozenFinder
# 会截走 PYZ 内所有同名模块，磁盘上的 .py 覆盖无效；没进 PYZ 的模块才能被
# %LOCALAPPDATA%\MRRC\patch\app 里的同名文件覆盖 → 不重新打包即可修 bug。
#
# 依赖发现不能降级：这些模块名仍然写进 hiddenimports，让 Analysis 照常追踪
# pyaudio/serial/… 等第三方依赖，只是最后从 PYZ 归档内容里过滤掉它们自己。
# ---------------------------------------------------------------------------
_APP_ENTRY = "MRRC"
_APP_MODULES = [
    "patch_overlay",           # 覆盖层自身也应可被覆盖（后续演进兼容）
    "config_io",
    "audio_interface",
    "hamlib_wrapper",
    "wdsp_wrapper",
    "atu_auto_tuner",
    "atu_fuchs_handler",
    "atr1000_tuner",
    "recording_session",
    "mrrc_perf_monitor",
    "ssl_bootstrap",
    "tci_client",
]
_APP_DATA = [(str(ROOT / _APP_ENTRY), "app")]
for _name in _APP_MODULES:
    _src = ROOT / f"{_name}.py"
    if _src.exists():
        _APP_DATA.append((str(_src), "app"))


# Vendor runtime files are platform-specific.  Missing vendor files are non-fatal:
# the corresponding feature gracefully degrades (WDSP disabled, Opus fallback,
# Hamlib unavailable until the user supplies a DLL).
_vendor_data = []
if sys.platform == "win32":
    for family in ("opus", "hamlib", "wdsp"):
        root = ROOT / "vendor" / family / "windows"
        if root.exists():
            _vendor_data.append((str(root), f"vendor/{family}/windows"))
elif sys.platform == "darwin":
    for family in ("opus", "hamlib", "wdsp"):
        root = ROOT / "vendor" / family / "macos"
        if root.exists():
            _vendor_data.append((str(root), f"vendor/{family}/macos"))


a = Analysis(
    [str(ROOT / "packaging" / "pyinstaller" / "frozen_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "www"), "www"),
        (str(ROOT / "memory_channels.json"), "."),
        (str(ROOT / "MRRC_users.db"), "."),
        (str(ROOT / "windows" / "MRRC.conf.template"), "windows"),
        (str(ROOT / "windows" / "launcher.py"), "windows"),
        *_APP_DATA,
        *_vendor_data,
    ],
    hiddenimports=[
        # 应用模块：仅为让 Analysis 追踪它们的第三方依赖（随后会从 PYZ 里剔除）
        *_APP_MODULES,
        # Web server / async
        "tornado",
        "tornado.web",
        "tornado.websocket",
        "tornado.httpserver",
        "tornado.ioloop",
        # Audio / serial / radio
        "pyaudio",
        "numpy",
        "serial",
        # Opus wrapper
        "opus",
        "opus.api",
        "opus.api.decoder",
        "opus.api.encoder",
        "opus.api.ctl",
        "opus.api.constants",
        # Local modules (some are imported conditionally)
        "hamlib_wrapper",
        "wdsp_wrapper",
        "audio_interface",
        "atu_auto_tuner",
        "atu_fuchs_handler",
        "atr1000_tuner",
        "ssl_bootstrap",
        "config_io",
        "dev_tools.tx_audio_analyzer",
        # TLS bootstrap
        "cryptography",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ([entry for entry in a.pure if entry[0] not in set(_APP_MODULES)])
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MRRC-Server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MRRC-Server",
)

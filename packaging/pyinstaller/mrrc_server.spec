# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder spec for the MRRC Tornado server.

Bundles the Tornado server, the browser UI, default configuration, and Windows
vendor runtime files.  The companion mrrc_launcher.spec builds the user-facing
desktop launcher.
"""
from pathlib import Path
import sys


ROOT = Path(SPECPATH).parents[1]


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
    [str(ROOT / "MRRC")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "www"), "www"),
        (str(ROOT / "memory_channels.json"), "."),
        (str(ROOT / "MRRC_users.db"), "."),
        (str(ROOT / "windows" / "MRRC.conf.template"), "windows"),
        (str(ROOT / "windows" / "launcher.py"), "windows"),
        *_vendor_data,
    ],
    hiddenimports=[
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
pyz = PYZ(a.pure)
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

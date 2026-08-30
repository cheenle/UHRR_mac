# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-file spec for the ATR-1000 tuner proxy worker.

The proxy is a separate TCP/Unix-socket service; bundling it lets Windows users
run it without installing Python.  MRRC itself talks to the proxy over the
socket configured in MRRC.conf / the MRRC_ATR1000_* environment variables.
"""
from pathlib import Path
import sys


ROOT = Path(SPECPATH).parents[1]


# Same vendor pattern as the server so the proxy can load libopus if needed.
_vendor_data = []
if sys.platform == "win32":
    for family in ("opus",):
        root = ROOT / "vendor" / family / "windows"
        if root.exists():
            _vendor_data.append((str(root), f"vendor/{family}/windows"))
elif sys.platform == "darwin":
    for family in ("opus",):
        root = ROOT / "vendor" / family / "macos"
        if root.exists():
            _vendor_data.append((str(root), f"vendor/{family}/macos"))


a = Analysis(
    [str(ROOT / "atr1000_proxy.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=_vendor_data,
    hiddenimports=[
        "atr1000_tuner",
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
    a.binaries,
    a.datas,
    [],
    name="ATR1000-Proxy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

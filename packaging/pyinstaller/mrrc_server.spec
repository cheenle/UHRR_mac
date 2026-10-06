# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder spec for the MRRC Tornado server.

Bundles the Tornado server, the browser UI, default configuration, and Windows
vendor runtime files.  The companion mrrc_launcher.spec builds the user-facing
desktop launcher.
"""
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files


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
    "rigctld_manager",        # rigctld 生命周期（Windows 自启/看护；COM 口排障逻辑要能单独热修）
    "rig_models",              # hamlib 机型表（改型号列表/别名时无需重新打包）
    "rigctld_supervisor",      # rigctld 自启动看护（Windows 安装版必须自己拉起电台后台；可热修）
    "support_bundle",          # 诊断包收集/脱敏（安全逻辑，需可单独热修）
    "upgrade_core",            # 一键升级纯逻辑（服务端 /api/update 与启动器都 import；
                               #   漏了它会 ModuleNotFoundError，2026-09-16 VM 实测）
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
    "antenna_sweep",           # 天线 SWR 扫频引擎。MRRC:2675 上方的注释就写着它是
                               #   “松散模块（回调注入）”，但一直没进本列表 ——
                               #   而 frozen_entry.py 是用 runpy.run_path() 跑 _internal/app/MRRC 的，
                               #   PyInstaller 看不到 MRRC 的任何 import，所以未登记的模块
                               #   既不在 PYZ 里、也不会被当数据文件发出 ⇒ 安装包一启动就
                               #   ModuleNotFoundError（V6.2.0 洁净室实测抓到，见 RC-006）。
                               #   守卫：tests/test_frozen_module_coverage.py
    "cloud_hub",               # Cloud Hub（内网穿透）纯逻辑：门户表单协议 / frpc 配置生成 /
                               #   frpc 发现 / 陈旧隧道回收 / TunnelProcess。stdlib、无 Tornado 依赖，
                               #   正是该可热修的那一类（守卫：dev_tools/test_cloud_hub.py）
    "session_metrics",         # 会话遥测（Cloud Hub 容量决策的数据来源）
    "base_path",               # 路径入口前缀（守卫：dev_tools/test_path_prefix.py）
    "tci_client",
]
_APP_DATA = [(str(ROOT / _APP_ENTRY), "app")]
for _name in _APP_MODULES:
    _src = ROOT / f"{_name}.py"
    if _src.exists():
        _APP_DATA.append((str(_src), "app"))


# 可选包的数据文件：pyrnnoise（RNNoise 降噪）会 import audiolab，而 audiolab 靠
# 自带的 jinja2 模板（format.txt）初始化 —— 不收集数据文件时冻结包会在 import 阶段
# 报 TemplateNotFound（2026-09-16 在 macOS 冻结产物上实测）。包不存在则跳过。
_optional_pkg_data = []
for _pkg in ("pyrnnoise", "audiolab"):
    try:
        _optional_pkg_data += collect_data_files(_pkg)
    except Exception as _exc:            # 未安装或没有数据文件都不影响构建
        print(f"[spec] 跳过 {_pkg} 的数据文件: {_exc}")


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
        # MRRC_users.db 是**明文口令文件**（"username password" 每行一条），不是数据库。
        # 曾经打进包里（_internal/MRRC_users.db），而安装包在站点上公开可下载 ⇒ 等于把
        # 构建机上那份真实口令发给所有人。且它在运行时**根本够不到**：
        #   * Windows 新装：launcher 把 db_users_file 写成用户数据目录的绝对路径，
        #     并由 ensure_users() 自己生成随机口令；
        #   * 相对路径配置：config_io.read_text 只是 open(path)，按 CWD 解析，
        #     不做 _resource_dir() 解析，所以永远落不到 _internal/；
        #   * Docker：docker-compose.yml 显式挂载仓库根那份。
        # 故此处不再打包（2026-10-06，见 docs/current/reliability/RC-005）。
        (str(ROOT / "windows" / "MRRC.conf.template"), "windows"),
        (str(ROOT / "windows" / "launcher.py"), "windows"),
        *_APP_DATA,
        *_optional_pkg_data,
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
        "rigctld_manager",
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

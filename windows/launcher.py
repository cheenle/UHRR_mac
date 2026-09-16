from __future__ import annotations

import configparser
import hashlib
import json
import os
import secrets
import signal
import subprocess
import threading
import sys
import time
import urllib.error
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

# ssl_bootstrap lives at the repo root; PyInstaller bundles it via pathex.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config_io
import ssl_bootstrap


def _force_utf8_stdio() -> None:
    """Windows 控制台默认 GBK：日志里的 emoji（🔍 等）会让 print 抛 UnicodeEncodeError，
    轻则日志乱码、重则杀死输出转发线程（server-stdout.log 从此断更）。
    统一把 stdio 切到 UTF-8，并用 errors='replace' 保证任何字符都不抛异常。"""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _safe_print(text: str) -> None:
    """print 的保险版：编码不支持（GBK 遇到 emoji）时降级，绝不让调用线程崩掉。"""
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        try:
            print(text.encode("ascii", "replace").decode("ascii"), flush=True)
        except Exception:
            pass
    except Exception:
        pass


APP_NAME = "MRRC"
DEFAULT_PORT = "8877"
_SERVER_PROC = None      # 主流程拉起的服务子进程（升级前必须先停，见 _stop_server_for_upgrade）
DEFAULT_LOGIN_USER = "admin"
KNOWN_DEFAULT_ACCOUNTS = {("BG1SB", "abcd1234"), ("admin", "uhrr2024")}

# 热修补丁：小幅 bugfix 不必重装（见 patch_overlay.py / docs/.../hotfix-and-patching.md）。
# 只从本站 HTTPS 拉取，且必须通过 patch.json 里的 SHA256 校验；失败一律忽略不影响启动。
PATCH_MANIFEST_URL = "https://www.vlsc.net/mrrc/downloads/patch.json"
PATCH_CHECK_TIMEOUT = 10


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def user_data_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "MRRC"
    return Path.home() / ".mrrc"


def patch_dir() -> Path:
    """热修覆盖层目录（与 MRRC/patch_overlay.py 的默认规则一致：配置文件同级的 patch/）。"""
    return user_data_dir() / "patch"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(262144), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hotfix_enabled(cfg: Path) -> bool:
    """配置开关：\
    [HOTFIX] enabled = False 可彻底关掉；环境变量 MRRC_NO_UPDATE_CHECK=1 同样关掉。"""
    if os.environ.get("MRRC_NO_UPDATE_CHECK"):
        return False
    parser = configparser.ConfigParser()
    try:
        config_io.read_config(parser, cfg)
    except Exception:
        return True
    if parser.has_section("HOTFIX"):
        return parser.getboolean("HOTFIX", "enabled", fallback=True)
    return True


def _installed_version() -> str:
    """本安装的版本号：取 dist 里写入的 version.txt（构建时生成），取不到就回退 0.0.0。"""
    marker = app_dir() / "version.txt"
    try:
        return marker.read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def _version_tuple(text: str) -> tuple:
    parts = []
    for chunk in str(text).replace("v", "").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts[:4])


def apply_hotfix_pack(zip_path: Path, patch_root: Path) -> list[str]:
    """把热修包解到覆盖层目录。返回写入的相对路径列表。

    包内布局与覆盖层同构（app/、www/、vendor/），额外可选 manifest.json。
    安全：拒绝绝对路径与 ../ 穿越；不允许写入覆盖层以外的位置。
    """
    patch_root.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            if name == "manifest.json":
                continue
            target = (patch_root / name).resolve()
            if not str(target).startswith(str(patch_root.resolve()) + os.sep):
                raise ValueError(f"热修包路径非法: {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
            written.append(name)
    # 记录已应用内容，供 support 查证
    record = patch_root / "applied.json"
    try:
        history = json.loads(record.read_text(encoding="utf-8")) if record.exists() else []
    except Exception:
        history = []
    history.append({"appliedAt": time.strftime("%Y-%m-%d %H:%M:%S"), "files": written})
    record.write_text(json.dumps(history[-20:], indent=2), encoding="utf-8")
    return written


def applied_hotfix_versions(patch_root: Path) -> set:
    """读过 patch/applied.json，返回已经应用过的补丁版本集合。

    没有这个检查时，每次启动都会因为“安装版本号没变”而反复下载/重放同一个补丁。
    """
    record = patch_root / "applied.json"
    try:
        history = json.loads(record.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if not isinstance(history, list):
        history = [history]
    return {str(item.get("version")) for item in history if isinstance(item, dict) and item.get("version")}


def check_for_hotfix(cfg: Path) -> None:
    """启动前检查并应用热补丁（失败一律只打印一句警告，不影响启动）。"""
    if not _hotfix_enabled(cfg):
        return
    try:
        with urllib.request.urlopen(PATCH_MANIFEST_URL, timeout=PATCH_CHECK_TIMEOUT) as response:
            manifest = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code != 404:          # 404 = 还没发布过任何热补丁，静默跳过
            print(f"[hotfix] 更新检查失败（HTTP {exc.code}）")
        return
    except Exception as exc:
        print(f"[hotfix] 跳过检查（{type(exc).__name__}: {exc}）")
        return
    try:
        latest = str(manifest.get("latest") or "").strip()
        url = str(manifest.get("url") or "").strip()
        expected = str(manifest.get("sha256") or "").strip().lower()
        requires = str(manifest.get("requires") or "").strip()
        if not (latest and url and expected):
            return
        if _version_tuple(latest) <= _version_tuple(_installed_version()):
            return
        # requires 必须满足：否则（如 6.0.2 安装包收到含 app/ 的补丁）会“假装修好了”
        if requires and _version_tuple(_installed_version()) < _version_tuple(requires):
            print(f"[hotfix] 跳过 {latest}：需要安装版本 >= {requires}（本机 {_installed_version()}），"
                  f"请先安装新版完整安装包")
            return
        if latest in applied_hotfix_versions(patch_dir()):
            return                                   # 已应用过，不再重复下载/重放
        print(f"[hotfix] 发现热补丁 {latest}（本机 {_installed_version()}）: {manifest.get('notes', '')}")
        tmp = user_data_dir() / f"hotfix-{latest}.zip.part"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as response, open(tmp, "wb") as out:
            out.write(response.read())
        actual = _sha256_file(tmp)
        if actual != expected:
            print(f"[hotfix] SHA256 不符，已放弃（期望 {expected[:12]}…，实际 {actual[:12]}…）")
            tmp.unlink(missing_ok=True)
            return
        written = apply_hotfix_pack(tmp, patch_dir())
        tmp.unlink(missing_ok=True)
        print(f"[hotfix] 已应用 {latest}：{len(written)} 个文件 -> {patch_dir()}")
    except Exception as exc:
        print(f"[hotfix] 应用失败（忽略，继续启动）: {type(exc).__name__}: {exc}")


def config_path() -> Path:
    return user_data_dir() / "MRRC.conf"


def quick_start_path() -> Path:
    return user_data_dir() / "MRRC Quick Start.txt"


def default_config_path() -> Path:
    return app_dir() / "windows" / "MRRC.conf.template"


def _copy_seed(target: Path, source: Path) -> None:
    if target.exists():
        return
    if source.exists():
        try:
            target.write_bytes(source.read_bytes())
        except OSError:
            pass


def _seed_candidates(filename: str) -> tuple[Path, ...]:
    return (
        app_dir() / filename,
        app_dir() / "_internal" / filename,
    )


def ensure_config(cert_path: Path, key_path: Path) -> Path:
    data_dir = user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    cfg = config_path()
    if not cfg.exists():
        default = default_config_path()
        if default.exists():
            text = default.read_text(encoding="utf-8").format(
                certfile=str(cert_path).replace("\\", "/"),
                keyfile=str(key_path).replace("\\", "/"),
                db_users_file=str(data_dir / "MRRC_users.db").replace("\\", "/"),
                log_file=str(data_dir / "MRRC.log").replace("\\", "/"),
            )
            cfg.write_text(text, encoding="utf-8")
        else:
            cfg.write_text(
                "[SERVER]\nport = 8877\ncertfile = server.crt\nkeyfile = server.key\n"
                "auth = FILE\ncookie_secret = change_me\n"
                "db_users_file = MRRC_users.db\nlog_file = MRRC.log\n",
                encoding="utf-8",
            )

    # Seed user-modifiable files next to the config.
    for seed in _seed_candidates("memory_channels.json"):
        _copy_seed(data_dir / "memory_channels.json", seed)
    return cfg


def _read_accounts(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    accounts = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            accounts.append((parts[0], parts[1]))
    return accounts


def ensure_users() -> tuple[str | None, str | None, bool]:
    """Ensure a first-run login exists without shipping a public password."""
    db = user_data_dir() / "MRRC_users.db"
    accounts = _read_accounts(db)
    if accounts and set(accounts) != KNOWN_DEFAULT_ACCOUNTS:
        return accounts[0][0], accounts[0][1], False

    password = secrets.token_urlsafe(12)
    db.write_text(
        "# MRRC local users: one account per line as: username password\n"
        "# Edit this file from the Start Menu if you want to change the password.\n"
        f"{DEFAULT_LOGIN_USER} {password}\n",
        encoding="utf-8",
    )
    return DEFAULT_LOGIN_USER, password, True


def _detect_windows_serial_port() -> str | None:
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM") as key:
            ports = []
            index = 0
            while True:
                try:
                    _, value, _ = winreg.EnumValue(key, index)
                except OSError:
                    break
                if isinstance(value, str) and value.upper().startswith("COM"):
                    ports.append(value.upper())
                index += 1
    except OSError:
        return None
    preferred = [p for p in sorted(set(ports), key=lambda p: int(p[3:]) if p[3:].isdigit() else 999) if p != "COM1"]
    return preferred[0] if preferred else None


def apply_simple_defaults(cfg: Path) -> None:
    parser = configparser.ConfigParser()
    config_io.read_config(parser, cfg)
    changed = False
    detected = _detect_windows_serial_port()
    if detected and parser.has_section("HAMLIB"):
        current = parser.get("HAMLIB", "rig_pathname", fallback="").strip().upper()
        if current in ("", "COM3") and detected != current:
            parser.set("HAMLIB", "rig_pathname", detected)
            changed = True
    if parser.has_section("AUDIO"):
        for key in ("inputdevice", "outputdevice"):
            current = parser.get("AUDIO", key, fallback="").strip()
            if current in ("", "USB Audio CODEC"):
                parser.set("AUDIO", key, "USB Audio")
                changed = True
    if changed:
        with cfg.open("w", encoding="utf-8") as f:
            parser.write(f)


def write_quick_start(user: str | None, password: str | None) -> None:
    lines = [
        "MRRC Quick Start",
        "================",
        "",
        "1. Connect the IC-M710 USB/serial adapter and USB audio device.",
        "2. Start MRRC from the Start Menu or desktop shortcut.",
        "3. Browser opens automatically. Accept the self-signed HTTPS warning.",
        "4. Log in with:",
        f"   Username: {user or '(your existing MRRC_users.db user)'}",
        f"   Password: {password or '(unchanged; see MRRC_users.db)'}",
        "",
        f"Config file: {config_path()}",
        f"Users file:  {user_data_dir() / 'MRRC_users.db'}",
        "",
        "If CAT does not connect, edit MRRC.conf and set [HAMLIB] rig_pathname to the COM port shown in Device Manager.",
        "Default IC-M710 rigctld model: 30003, speed: 4800, stop bits: 2.",
    ]
    quick_start_path().write_text("\n".join(lines) + "\n", encoding="utf-8")


def ssl_material() -> tuple[Path, Path] | None:
    """Return (cert, key) path, generating a self-signed pair if absent."""
    cert_dir = user_data_dir() / "certs"
    return ssl_bootstrap.ensure_self_signed(cert_dir)


def _vendor_bin_dirs() -> list[Path]:
    """Return any vendor/*/windows/bin/x64 directories shipped with the app."""
    vendor_root = app_dir() / "vendor"
    if not vendor_root.exists():
        return []
    dirs: list[Path] = []
    for family in vendor_root.iterdir():
        candidate = family / "windows" / "bin" / "x64"
        if candidate.is_dir():
            dirs.append(candidate)
    return dirs


def _environ_with_vendor_path(env: dict[str, str]) -> dict[str, str]:
    extra = [str(d) for d in _vendor_bin_dirs()]
    # 热修覆盖层里的 DLL 优先（patch/vendor/... 或直接 patch/libwdsp.dll）
    patch_root = patch_dir()
    for candidate in (patch_root / "vendor", patch_root):
        if candidate.is_dir():
            extra.insert(0, str(candidate))
    if not extra:
        return env
    separator = ";" if os.name == "nt" else ":"
    env["PATH"] = separator.join(extra + [env.get("PATH", "")])
    return env


def _read_config_port_host(cfg: Path) -> tuple[str, str]:
    parser = configparser.ConfigParser()
    config_io.read_config(parser, cfg)
    port = parser.get("SERVER", "port", fallback=DEFAULT_PORT)
    host = parser.get("SERVER", "host", fallback="127.0.0.1")
    if host in ("0.0.0.0", "::", ""):
        host = "127.0.0.1"
    return port, host


def local_url(port: str, host: str, secure: bool = True) -> str:
    scheme = "https" if secure else "http"
    if host == "::":
        display_host = "localhost"
    elif host in ("0.0.0.0", ""):
        display_host = "127.0.0.1"
    else:
        display_host = host
    return f"{scheme}://{display_host}:{port}"


def server_executable() -> Path | None:
    exe = app_dir() / "MRRC-Server.exe"
    if exe.exists():
        return exe
    script = app_dir() / "MRRC"
    if not getattr(sys, "frozen", False) and script.exists():
        return script
    return None


def wait_for_server(url: str, proc: subprocess.Popen | None = None,
                    timeout_s: float = 15.0, secure: bool = True) -> bool:
    """Poll until the server answers HTTP (any status) or give up."""
    ctx = None
    if secure:
        import ssl as _ssl

        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
    deadline = time.monotonic() + timeout_s
    probe = url + "/"
    while time.monotonic() < deadline:
        if proc is not None and proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(probe, timeout=2, context=ctx):
                return True
        except urllib.error.HTTPError:
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.3)
    return False


def build_command(cfg: Path) -> list[str] | None:
    server = server_executable()
    if server is None:
        return None
    if server.suffix.lower() == ".exe":
        return [str(server), str(cfg)]
    return [sys.executable, str(server), str(cfg)]


def tee_child_output(proc: subprocess.Popen, log_path, max_bytes: int = 2 * 1024 * 1024):
    """把子进程输出**既转发到本进程控制台、又落盘一份**（超限滚动成 .prev）。

    为什么必须有：服务端的启动期报错（PyInstaller/依赖缺失/WDSP 加载失败）只在 stdout，
    不落盘就没法进诊断包；而改成纯文件重定向用户又看不到控制台。
    另外必须持续读取管道，否则管道写满会让服务端阻塞（与 F4b 同类的问题）。

    返回本进程捕获到的行（测试断言用；生产调用忽略返回值）。
    """
    log_path = Path(log_path)
    lines = []
    sink = None
    try:
        if max_bytes and log_path.exists() and log_path.stat().st_size > max_bytes:
            backup = log_path.with_name(log_path.name + ".prev")
            try:
                backup.unlink(missing_ok=True)
                log_path.replace(backup)
            except OSError:
                pass
        log_path.parent.mkdir(parents=True, exist_ok=True)
        sink = open(log_path, "a", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        sink = None                      # 落盘失败不影响转发
    try:
        for raw in proc.stdout or ():
            text = raw.rstrip("\n")
            _safe_print(text)            # 控制台保持可见（用户习惯看这个窗口）
            lines.append(text)
            if sink is not None:
                try:
                    sink.write(text + "\n")
                except OSError:
                    sink = None
    finally:
        if sink is not None:
            try:
                sink.close()
            except OSError:
                pass
    return lines


def stop_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def confirm_pending_upgrade(data_dir: Path) -> None:
    """安装后首次启动：确认升级成功（写结果 + 清掉暂存安装包）。

    升级时启动器会主动退出（安装器要替换它占用的文件），所以“成功”只能由新版自己确认。
    """
    import upgrade_core as up
    try:
        state = up.read_state(data_dir)
        staged = state.get("staged") or {}
        version = str(staged.get("version") or "")
        if not version:
            return
        current = _installed_version()
        if up.version_tuple(current) >= up.version_tuple(version):
            up.record_result(data_dir, "ok", version, "安装后启动确认成功")
            try:
                os.remove(str(staged.get("path") or ""))
            except OSError:
                pass
            up.write_state(data_dir, staged=None)
            print(f"[update] 已升级到 {version}（当前 {current}）")
        else:
            print(f"[update] 上次升级 {version} 似乎没完成（当前 {current}），可重试")
    except Exception as exc:                     # 确认失败不能影响启动
        print(f"[update] 升级结果确认跳过：{type(exc).__name__}: {exc}")


def check_for_upgrade(cfg: Path, data_dir: Path):
    """启动时检查升级（见 docs/superpowers/specs/2026-09-16-one-click-upgrade-design.md）。

    返回 plan（可能为 None）。行为：
      * 仅提示 + 可选的**后台预下载**，绝不打断收听；
      * 已就绪（state.staged 同版本同 sha）则不重复下载；
      * 任何失败只打印一行，不影响启动。
    """
    import upgrade_core as up
    if not _update_enabled(cfg):
        return None
    manifest, error = up.fetch_manifest()          # 可用 MRRC_UPDATE_MANIFEST 覆盖
    print(f"[update] 清单: {up.manifest_url()}")
    if not manifest:
        print(f"[update] 检查更新失败（忽略）: {error}")
        return None
    plan = up.plan_upgrade(_installed_version(), manifest,
                           applied_hotfixes=applied_hotfix_versions(patch_dir()))
    info = plan.get("installer") or {}
    if not info.get("available"):
        return plan
    print(f"[update] 发现新版本 {info['version']}（本机 {plan['installed']}）"
          f"{'【强制升级】' if info.get('mandatory') else ''}"
          + (f"：{plan.get('notes')}" if plan.get("notes") else ""))
    if up.staged_matches(up.read_state(data_dir), info["version"], info["sha256"]):
        print("[update] 安装包已就绪，按 U 立即升级")
        return plan
    if not _auto_download_enabled(cfg):
        print("[update] 自动下载已关闭（[UPDATE] autoDownload=False）")
        return plan

    def _bg():
        result = up.download_installer(info["url"], info["sha256"], data_dir, info["version"])
        if result.get("ok"):
            print(f"[update] 已下载 {info['version']}（{result['size'] // 1024} KB），"
                  f"按 U 立即升级")
        else:
            print(f"[update] 下载失败（忽略，可用旧版）: {result.get('reason')}")

    threading.Thread(target=_bg, name="update-download", daemon=True).start()
    return plan


def _is_elevated() -> bool:
    """当前进程是否已提权（提权时无需再弹 UAC，直接跑安装器更稳）。"""
    if os.name != "nt":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _exit_for_upgrade(delay: float = 1.0) -> None:
    """安装器要替换本进程占用的文件：必须真的退出。

    Inno 的 /CLOSEAPPLICATIONS 靠 Restart Manager 发 WM_CLOSE；控制台进程没有消息循环，
    它关不掉（6.1.0 实测日志：“Some applications could not be shut down.” → 静默模式自动
    选 Abort → 升级失败）。所以启动器拉完安装器就自己放手。
    """
    def _later():
        time.sleep(delay)
        os._exit(0)                     # 不走 atexit/清理：马上放开被占的文件
    threading.Thread(target=_later, name="exit-for-upgrade", daemon=True).start()


def _stop_server_for_upgrade(timeout: float = 15.0) -> None:
    """升级前停掉本启动器拉起的服务进程。

    安装器要替换 MRRC-Server.exe / 依赖 DLL，文件被占用时 Inno 会失败：
    「DeleteFile failed; code 5」（6.1.0 端到端测试实测）。先停再装最稳，
    /FORCECLOSEAPPLICATIONS 只做兜底。
    """
    proc = _SERVER_PROC
    if proc is None or proc.poll() is not None:
        return
    print("[update] 先停止正在运行的服务…")
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc.wait(timeout=timeout)
    except Exception:
        try:
            stop_process(proc)
        except Exception:
            pass


def run_upgrade(data_dir: Path, version: str) -> str:
    """提权静默安装（一次 UAC）+ 验证版本。返回状态串（见 upgrade_core.record_result）。"""
    import upgrade_core as up
    state = up.read_state(data_dir)
    staged = state.get("staged") or {}
    setup = str(staged.get("path") or "")
    if str(staged.get("version")) != str(version) or not os.path.isfile(setup):
        up.record_result(data_dir, "missing_staged", version,
                         "安装包尚未下载完成（稍后重试或检查网络）")
        return "missing_staged"
    log_path = str(Path(data_dir) / "updates" / f"install-{version}.log")
    _stop_server_for_upgrade()
    args = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
            "/CLOSEAPPLICATIONS", "/FORCECLOSEAPPLICATIONS", f"/LOG={log_path}"]
    try:
        import ctypes
        if _is_elevated():
            # 已提权：直接跑（不再弹 UAC）——也避免 ShellExecuteW 在非交互窗口站上卡死。
            subprocess.Popen([setup] + args, cwd=str(Path(data_dir) / "updates"),
                             close_fds=True)
            up.record_result(data_dir, "installing", version, "已启动静默安装（提权直跑）")
            print("[update] 已启动静默安装；本窗口即将退出，安装完成后会自动打开新版本。")
            _exit_for_upgrade()
            return "installing"
        params = " ".join(f'"{a}"' if " " in a else a for a in args)
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", setup, params, str(Path(data_dir) / "updates"), 1)
    except Exception as exc:
        up.record_result(data_dir, "install_failed", version, f"{type(exc).__name__}: {exc}")
        return "install_failed"
    if rc <= 32:                       # 5 = ERROR_ACCESS_DENIED（用户拒绝 UAC）
        status = "uac_denied" if rc == 5 else "install_failed"
        up.record_result(data_dir, status, version, f"ShellExecute 返回 {rc}")
        return status
    print(f"[update] 安装程序已启动（等待完成，最多 10 分钟）… 日志：{log_path}")
    deadline = time.time() + 600
    while time.time() < deadline:
        time.sleep(2)
        if _installed_version() == str(version):
            break
    ok = _installed_version() == str(version)
    up.record_result(data_dir, "ok" if ok else "install_failed", version,
                     "" if ok else "安装后 version.txt 未更新，见 install 日志")
    return "ok" if ok else "install_failed"


def server_allows_upgrade(port: str, timeout: float = 3.0):
    """问一下本地服务端是否允许升级（发射中拒绝）。

    服务端 /api/update 在**仅本机**访问时免口令（见 MRRC 的 UpdateApiHandler），
    返回 {"pttActive": bool}。服务端不可达时返回 (True, "server_unreachable")：这时它
    本来就没在跑，升级是安全的。
    """
    import ssl as _ssl
    import urllib.request
    ctx = _ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE
    try:
        with urllib.request.urlopen(f"https://127.0.0.1:{port}/api/update",
                                    context=ctx, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
        if data.get("pttActive"):
            return False, "ptt_active"
        return True, "ok"
    except Exception as exc:
        return True, f"server_unreachable: {type(exc).__name__}"


def wait_for_upgrade_key(data_dir: Path, stop_event: threading.Event) -> None:
    """控制台按 U（+回车）请求升级。

    用行读而不是原始单键：Windows 上不需要 msvcrt，且与 Ctrl-C 共存最稳；
    提示文案里写清楚"输入 U 再回车"。
    """
    import upgrade_core as up
    while not stop_event.is_set():
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            return
        except Exception:
            return
        if line.strip().lower().startswith("u"):
            up.write_upgrade_request(data_dir, "latest")
            print("[update] 已收到升级指令，准备中…（如需最新版本号，请用页面里的按钮）")


def watch_upgrade(data_dir: Path, pending_version: str = "", poll_seconds: float = 1.0,
                  port: str = "") -> None:
    """轮询哨兵文件（页面里的「立即升级」按钮会写它）并执行升级；成功后重启启动器。"""
    import upgrade_core as up
    while True:
        request = up.read_upgrade_request(data_dir)
        target = str((request or {}).get("version") or "").strip()
        if target:
            up.clear_upgrade_request(data_dir)          # 先清，避免重复触发
        elif pending_version:
            target, pending_version = pending_version, ""   # 启动检查已经知道有新版本
        if target == "latest":
            manifest, _err = up.fetch_manifest()
            plan = up.plan_upgrade(_installed_version(), manifest) if manifest else {}
            info = (plan or {}).get("installer") or {}
            if not info.get("available"):
                print("[update] 清单里没有可用新版本（可能已是最新或网络失败）")
                time.sleep(poll_seconds)
                continue
            if not up.staged_matches(up.read_state(data_dir), info["version"], info["sha256"]):
                print(f"[update] 正在下载 {info['version']} …")
                result = up.download_installer(info["url"], info["sha256"], data_dir, info["version"])
                if not result.get("ok"):
                    print(f"[update] 下载失败：{result.get('reason')}")
                    time.sleep(poll_seconds)
                    continue
            target = info["version"]
        if target:
            if port:
                allowed, why = server_allows_upgrade(port)
                if not allowed:
                    print(f"[update] 现在不能升级：{why}（发射中请先松开 PTT，稍后再按 U）")
                    up.record_result(data_dir, "ptt_active", target, why)
                    pending_version = ""
                    time.sleep(poll_seconds)
                    continue
            status = run_upgrade(data_dir, target)
            print(f"[update] 升级结果：{status}")
            if status == "ok":
                print("[update] 升级完成，正在重启…")
                try:
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                except Exception as exc:               # 重启失败也不能崩
                    print(f"[update] 自动重启失败（请手动重开）：{exc}")
                return
            pending_version = ""
        time.sleep(poll_seconds)


def _update_enabled(cfg: Path) -> bool:
    """[UPDATE] enabled=False 或 MRRC_NO_UPDATE_CHECK=1 时完全不检查（含热修）。"""
    if os.environ.get("MRRC_NO_UPDATE_CHECK"):
        return False
    parser = configparser.ConfigParser()
    try:
        config_io.read_config(parser, cfg)
    except Exception:
        return True
    if parser.has_section("UPDATE"):
        return parser.getboolean("UPDATE", "enabled", fallback=True)
    return True


def _auto_download_enabled(cfg: Path) -> bool:
    parser = configparser.ConfigParser()
    try:
        config_io.read_config(parser, cfg)
    except Exception:
        return True
    if parser.has_section("UPDATE"):
        return parser.getboolean("UPDATE", "autoDownload", fallback=True)
    return True


def main() -> int:
    _force_utf8_stdio()
    data_dir = user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    ssl_pair = ssl_material()
    if ssl_pair is None:
        print("ERROR: Could not create or find TLS certificate.")
        print("Install the 'cryptography' package, or provide a cert/key in MRRC.conf.")
        return 1

    cfg = ensure_config(ssl_pair[0], ssl_pair[1])
    apply_simple_defaults(cfg)
    check_for_hotfix(cfg)
    confirm_pending_upgrade(data_dir)
    upgrade_plan = check_for_upgrade(cfg, data_dir)
    login_user, login_password, generated_login = ensure_users()
    write_quick_start(login_user, login_password)
    port, host = _read_config_port_host(cfg)
    url = local_url(port, host, secure=True)

    print(APP_NAME)
    print(f"Config: {cfg}")
    print(f"Quick Start: {quick_start_path()}")
    if generated_login:
        print(f"First-run login: {login_user} / {login_password}")
    print(f"URL:    {url}")
    print("HTTPS:  self-signed certificate (browser will warn once — accept it)")
    print("Close this window or press Ctrl-C to stop the server.")

    command = build_command(cfg)
    if command is None:
        print("ERROR: MRRC-Server.exe not found next to the launcher.")
        return 1

    env = os.environ.copy()
    env["MRRC_MEMORY_CHANNELS_FILE"] = str(data_dir / "memory_channels.json")
    env["MRRC_ATR1000_STORE"] = str(data_dir / "atr1000_tuner.json")
    # 让服务端与入口用同一个覆盖层目录（patch_overlay.py 默认也会推出这个路径）
    env["MRRC_PATCH_DIR"] = str(patch_dir())
    if login_user and login_password:
        env["MRRC_FIRST_RUN_LOGIN_USER"] = login_user
        env["MRRC_FIRST_RUN_LOGIN_PASSWORD"] = login_password
    env = _environ_with_vendor_path(env)

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    # stdout/stderr 走管道 → tee 线程同时打印到控制台并写 logs/server-stdout.log，
    # 这样「🐞 遇到问题」的诊断包才能带上启动期报错（见 support_bundle）。
    proc = subprocess.Popen(
        command,
        cwd=str(app_dir()),
        env=env,
        creationflags=creationflags,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    global _SERVER_PROC
    _SERVER_PROC = proc
    server_log = data_dir / "logs" / "server-stdout.log"
    threading.Thread(target=tee_child_output, args=(proc, server_log),
                     name="server-stdout-tee", daemon=True).start()
    # 升级看护：页面按钮（哨兵文件，带具体版本）或控制台按 U（取清单里的 latest）
    # → 停服务（安装器 /CLOSEAPPLICATIONS）→ 静默安装（一次 UAC）→ 自动重启
    upgrade_stop = threading.Event()
    threading.Thread(target=watch_upgrade, args=(data_dir, "", 1.0, port),
                     name="update-watch", daemon=True).start()
    threading.Thread(target=wait_for_upgrade_key, args=(data_dir, upgrade_stop),
                     name="update-key", daemon=True).start()
    if (upgrade_plan or {}).get("installer", {}).get("available"):
        print("提示：有新版本待安装 —— 在此窗口输入 U 回车即可升级（会弹一次 UAC）。")
    if wait_for_server(url, proc, secure=True):
        webbrowser.open(url)
    elif proc.poll() is not None:
        print("Server exited during startup — see messages above.")
        return proc.returncode or 1
    else:
        print(f"Server did not answer within 15s; opening {url} anyway.")
        webbrowser.open(url)
    try:
        return proc.wait()
    except KeyboardInterrupt:
        stop_process(proc)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

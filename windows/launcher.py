from __future__ import annotations

import configparser
import os
import secrets
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

# ssl_bootstrap lives at the repo root; PyInstaller bundles it via pathex.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ssl_bootstrap


APP_NAME = "MRRC"
DEFAULT_PORT = "8877"
DEFAULT_LOGIN_USER = "admin"
KNOWN_DEFAULT_ACCOUNTS = {("BG1SB", "abcd1234"), ("admin", "uhrr2024")}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def user_data_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "MRRC"
    return Path.home() / ".mrrc"


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
    parser.read(cfg, encoding="utf-8")
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
    if not extra:
        return env
    separator = ";" if os.name == "nt" else ":"
    env["PATH"] = separator.join(extra + [env.get("PATH", "")])
    return env


def _read_config_port_host(cfg: Path) -> tuple[str, str]:
    parser = configparser.ConfigParser()
    parser.read(cfg, encoding="utf-8")
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


def main() -> int:
    data_dir = user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    ssl_pair = ssl_material()
    if ssl_pair is None:
        print("ERROR: Could not create or find TLS certificate.")
        print("Install the 'cryptography' package, or provide a cert/key in MRRC.conf.")
        return 1

    cfg = ensure_config(ssl_pair[0], ssl_pair[1])
    apply_simple_defaults(cfg)
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
    if login_user and login_password:
        env["MRRC_FIRST_RUN_LOGIN_USER"] = login_user
        env["MRRC_FIRST_RUN_LOGIN_PASSWORD"] = login_password
    env = _environ_with_vendor_path(env)

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(
        command,
        cwd=str(app_dir()),
        env=env,
        creationflags=creationflags,
    )
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

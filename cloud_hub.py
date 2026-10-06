"""Cloud Hub onboarding, from inside the app (ported from mrrc_modern v1.25.0).

The tenant-side story used to be a shell script: paste a token and a one-time secret into a
terminal, then hand the operator a root command. This module turns it into three calls the
web UI (`www/cloud.html`) can make:

    apply()    ask the portal for an entry (callsign + contact), keep the request token
    status()   ask whether it has been approved yet
    connect()  once approved: sign the certificate the hub will verify, enroll it, record it
               in the instance's own state file so the app serves it from then on, and run
               the tunnel

Differences from the mrrc_modern original, forced by this app's shape:

- State lives in ``mrrc_cloud.json`` next to the config file (atomic write, 0600 - it holds
  the request token), not in an env file: this app's configuration is ``MRRC.conf``
  (configparser), which must not be rewritten by code that would lose its comments.
- frpc is discovered (repo ``fleet/`` dir, ``PATH``, the ``install_instance_tunnel.sh``
  cache) instead of taken from an installer payload, because this repo's product is mostly
  source-run.

It is deliberately stdlib-only and free of Tornado imports so it can be unit-tested without
starting the server (dev_tools/test_cloud_hub.py).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import ssl_bootstrap

logger = logging.getLogger(__name__)

#: The hub's own portal entry, and the app's default. Hub V0.21 (2026-10-02) merged portal,
#: instance entries and the site onto one machine and one port; the old :8899 address and the
#: www edge path redirect here and are remapped below for configs written before the merge.
PORTAL_DEFAULT = "https://portal.mrrc.vlsc.net"

TIMEOUT = 25


class CloudHubError(RuntimeError):
    """Anything the UI should show as a sentence rather than a traceback."""


class _Unreachable(CloudHubError):
    """The request never reached a portal: DNS/TCP/TLS failure, a timeout, or a hop's 502/504.

    Kept apart from a portal that *answered* (even with a rejection), because only the former is
    worth retrying on another path - repeating an application the portal already recorded would
    just trade one failure for a duplicate.
    """


def _post_once(portal: str, route: str, payload: dict, timeout: int) -> dict:
    """POST form-encoded fields on one path - the shape the portal speaks - and return its JSON."""
    url = portal.rstrip("/") + route
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(url, data=data,
                                headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as reply:
            return json.loads(reply.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read() or b"{}").get("error", "")
        except Exception:                       # noqa: BLE001 - the body is best effort
            pass
        message = detail
        if not message:
            message = f"portal returned HTTP {exc.code}"
        if exc.code in (502, 504):              # a proxy hop died; the portal never spoke
            raise _Unreachable(message) from exc
        raise CloudHubError(message) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise _Unreachable(f"cannot reach the portal ({exc.__class__.__name__}: {exc})") from exc


def _post(portal: str, route: str, payload: dict, timeout: int = TIMEOUT) -> dict:
    """POST form-encoded fields to the portal on the one address it now has.

    A config written before the V0.21 merge may still name an old address; those are sent to
    the current one instead, because each of them now redirects there anyway.
    """
    legacy = ("https://portal.mrrc.vlsc.net:8899",
              "https://www.vlsc.net/mrrc_portal",
              "https://portal.mrrc.vlsc.net/mrrc_portal")
    base = PORTAL_DEFAULT if portal.rstrip("/") in legacy else portal.rstrip("/")
    try:
        return _post_once(base, route, payload, timeout)
    except _Unreachable as exc:
        raise CloudHubError(f"portal did not answer ({base}): {exc}") from exc


def apply(portal: str, callsign: str, contact: str = "", product: str = "") -> dict:
    """Submit an application. The reply carries the request token used by status()."""
    reply = _post(portal, "/apply", {"callsign": callsign, "contact": contact, "product": product})
    if not reply.get("request_token"):
        raise CloudHubError("portal did not return a request token")
    return reply


def claim(portal: str, callsign: str, secret: str) -> dict:
    """Adopt an application the operator already approved, using the secret they handed over.

    Without this, an app can only see an application it submitted itself - so an approval made
    against a web-submitted application would be invisible to the app that has to use it.
    """
    reply = _post(portal, "/claim", {"callsign": callsign, "secret": secret})
    if not reply.get("request_token"):
        raise CloudHubError("portal did not return a request token")
    return reply


def status(portal: str, callsign: str, token: str) -> dict:
    """Ask whether this application has been approved, and for its connection details once it is."""
    return _post(portal, "/status", {"callsign": callsign, "token": token})


# ---------------------------------------------------------------------------
# Instance state (mrrc_cloud.json) - replaces mrrc_modern's env-file writes.
# ---------------------------------------------------------------------------

def load_state(state_path: Path) -> dict:
    """Read the instance's cloud state; {} when absent or unreadable."""
    try:
        data = json.loads(Path(state_path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state_path: Path, updates: dict) -> dict:
    """Merge ``updates`` into the state file atomically and return the whole state.

    The file holds the request token (a bearer for the application until the enrolment
    completes), so it is written 0600 like the frpc config that holds the hub token.
    """
    state_path = Path(state_path)
    state = load_state(state_path)
    state.update(updates)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass                                # Windows ACLs don't map POSIX modes - fine
    tmp.replace(state_path)
    return state


def frpc_config_text(name: str, token: str, local_port: int, remote_port: int,
                     hub_host: str = "tunnel.mrrc.vlsc.net", control_port: int = 8989,
                     log_file: str = "") -> str:
    """The tunnel's TOML. Written as ASCII with no BOM: frpc's parser rejects a BOM outright."""
    lines = [
        f'serverAddr = "{hub_host}"',
        f"serverPort = {control_port}",
        "",
        'auth.method = "token"',
        f'auth.token = "{token}"',
        "",
    ]
    if log_file:
        # Forward slashes: a backslash inside a TOML basic string is an escape, so a raw Windows
        # path makes the file unparseable - frpc reports "non-hex character" at the \U of
        # "C:\Users" and refuses to start, which is a silent 502 for the entry. frpc accepts
        # forward slashes on Windows.
        lines += [f'log.to = "{str(log_file).replace(chr(92), "/")}"', 'log.level = "info"', ""]
    lines += [
        "[[proxies]]",
        f'name = "{name}"',
        'type = "tcp"',
        'localIP = "127.0.0.1"',
        f"localPort = {local_port}",
        f"remotePort = {remote_port}",
    ]
    return "\n".join(lines) + "\n"


def find_frpc(fleet_dir: Path) -> Path | None:
    """Locate an frpc binary: MRRC_FRPC env, repo fleet/ dir, PATH, ~/bin, install-script cache.

    mrrc_modern gets frpc from its installer payload; this product is mostly source-run, so
    the realistic sources are `brew install frp` (PATH), `~/bin/frpc` (where
    mrrc_hub/deploy/install_instance_tunnel.sh put it on the first machine) or that script's
    cache (~/.local/share/mrrc-fleet). The hub's frps is pinned (0.71.0 at the time of
    writing) - a much newer client can fail the handshake.
    """
    name = "frpc.exe" if os.name == "nt" else "frpc"
    override = os.environ.get("MRRC_FRPC", "").strip()
    candidates = [Path(override)] if override else []
    candidates.append(Path(fleet_dir) / name)
    on_path = shutil.which("frpc")
    if on_path:
        candidates.append(Path(on_path))
    candidates.append(Path.home() / "bin" / name)
    candidates.append(Path.home() / ".local" / "share" / "mrrc-fleet" / name)
    for cand in candidates:
        try:
            if cand.exists():
                return cand
        except OSError:
            continue
    return None


def _stale_frpc_pids(config_path: Path, ps_output: str | None = None) -> list[int]:
    """PIDs of running frpc processes that name this instance's own config.

    ``ps_output`` is a test seam (inject a fake ``ps -eo pid=,command=`` dump); when it is None
    the real process table is read, per platform. Only processes naming *this* config are
    returned, so a second instance on the same machine is never touched; the calling process
    itself is excluded defensively.
    """
    marker = str(config_path)
    if ps_output is not None:
        lines = ps_output.splitlines()
    elif os.name == "nt":
        try:
            lines = subprocess.run(
                ["wmic", "process", "where", "name='frpc.exe'", "get", "ProcessId,CommandLine"],
                capture_output=True, text=True, timeout=15).stdout.splitlines()
        except Exception:                                        # noqa: BLE001 - best effort
            return []
    else:
        try:
            lines = subprocess.run(["ps", "-eo", "pid=,command="],
                                   capture_output=True, text=True, timeout=15).stdout.splitlines()
        except Exception:                                        # noqa: BLE001 - best effort
            return []

    pids: list[int] = []
    for line in lines:
        if marker not in line or "frpc" not in line:
            continue
        tokens = line.split()
        if not tokens:
            continue
        # POSIX `ps -eo pid=,command=` 首列是 PID；Windows wmic 的 PID 在行末。
        candidate = tokens[0] if tokens[0].isdigit() else tokens[-1]
        try:
            pid = int(candidate)
        except ValueError:
            continue
        if pid != os.getpid():
            pids.append(pid)
    return pids


def _pid_alive(pid: int) -> bool:
    """Alive and not a zombie（被杀掉的孤儿在 init 回收前会以 Z 状态滞留）。"""
    if os.name == "nt":
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    try:
        state = subprocess.run(["ps", "-o", "state=", "-p", str(pid)],
                               capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:                                            # noqa: BLE001 - best effort
        return False
    return bool(state) and not state.startswith("Z")


def _kill_stale_frpc(config_path: Path) -> None:
    """Kill an frpc left behind by a previous run of this instance, if there is one.

    实测（2026-10-04，macOS）：杀掉应用不会带走它的 frpc 子进程，下一次启动因此注册不上
    同名 proxy —— 隧道保持掉线而 UI 上看不出原因；而且每次重启泄漏一个 frpc（本机曾累积 5 个
    互相抢名、日志每 10s 一条 "proxy already exists"，隧道实际由早已失去父进程的孤儿持有）。
    只碰 "命令行里点名了本实例自己配置" 的进程，同机另一实例的 frpc 不受影响。

    原实现只写了 wmic/taskkill 并在非 Windows 上一行 return —— 这就是上面那个现象在 macOS
    上一直存在的原因（F7/RC-003 附带：POSIX 走 ps + SIGTERM，宽限 3s 后 SIGKILL）。
    """
    pids = _stale_frpc_pids(config_path)
    if not pids:
        return
    for pid in pids:
        # print 而非 logger.info：本产品 basicConfig 级别是 WARNING，info 不进日志，
        # 而"清掉了哪个陈旧 frpc"是解释隧道行为的运维可见事实（AGENTS.md 约定）。
        print(f"☁️ cloud hub: clearing a stale frpc (pid {pid}) holding this instance's tunnel")

    if os.name == "nt":
        for pid in pids:
            try:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=10)
            except Exception:                                    # noqa: BLE001 - best effort
                pass
        return

    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + 3.0
    alive = list(pids)
    while alive and time.time() < deadline:
        time.sleep(0.1)
        alive = [pid for pid in alive if _pid_alive(pid)]
    for pid in alive:
        logger.warning("cloud hub: stale frpc %s ignored SIGTERM — killing", pid)
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


class TunnelProcess:
    """Keep one frpc alive, restarting it if it exits.

    The app runs it as a child rather than a service: the tunnel is only useful while the app is
    up, and a child needs no elevation and no scheduler entry to manage.
    """

    def __init__(self, frpc: Path, conf: Path):
        self.frpc = Path(frpc)
        self.conf = Path(conf)
        _kill_stale_frpc(self.conf)
        self.proc: subprocess.Popen | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error = ""

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="cloud-hub-frpc", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        delay = 2
        while not self._stop.is_set():
            try:
                self.proc = subprocess.Popen(
                    [str(self.frpc), "-c", str(self.conf)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
                )
                self.last_error = ""
                delay = 2
                while self.proc.poll() is None and not self._stop.is_set():
                    time.sleep(1)
                if self._stop.is_set():
                    break
                self.last_error = f"frpc exited with {self.proc.returncode}"
                logger.warning("cloud hub: %s; restarting in %ss", self.last_error, delay)
            except OSError as exc:
                self.last_error = f"cannot run frpc: {exc}"
                logger.warning("cloud hub: %s", self.last_error)
            self._stop.wait(delay)
            delay = min(delay * 2, 60)

    def stop(self) -> None:
        self._stop.set()
        proc = self.proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    @property
    def running(self) -> bool:
        return bool(self.proc and self.proc.poll() is None)


def connect(portal: str, callsign: str, token: str, *, state_path: Path, cert_dir: Path,
            data_dir: Path, local_port: int, frpc: Path | None = None,
            tunnel: TunnelProcess | None = None, extra_names=None) -> dict:
    """Do everything that follows approval, and report what happened.

    Steps, in order: confirm approval, sign the certificate for the entry name the hub will check,
    enroll its public half, record the certificate in the instance state so the app serves it from
    the next start on, then write the tunnel config and start frpc (when a binary was found).

    ``extra_names`` are the instance's other reachable names (legacy direct-IPv6 entries such as
    ``radio.vlsc.net``); they are added to the certificate's SAN list so those bookmarks keep
    validating. The hub only requires its own name to be present.
    """
    state = status(portal, callsign, token)
    if state.get("status") != "granted":
        return {"connected": False, "status": state.get("status", "unknown"), "reason": "尚未批准"}

    label = str(state.get("label") or "")
    # The portal is remote input: a malformed port must read as a sentence in the UI, not as an
    # unhandled ValueError that the endpoint turns into a 500.
    try:
        port = int(state.get("port") or 0)
    except (TypeError, ValueError) as exc:
        raise CloudHubError(f"portal sent a non-numeric port: {state.get('port')!r}") from exc
    secret = str(state.get("enroll_secret") or "")
    hub_token = str(state.get("hub_token") or "") or os.environ.get("MRRC_HUB_TOKEN", "")
    if not (label and port and secret):
        raise CloudHubError("portal says granted but sent no label/port/secret")

    fqdn = f"{label}.mrrc.vlsc.net"
    pair = ssl_bootstrap.sign_for(fqdn, cert_dir, extra_names=extra_names)
    if pair is None:
        raise CloudHubError("cannot sign a certificate (cryptography unavailable)")
    cert_path, key_path = pair

    _post(portal, "/enroll", {"callsign": callsign, "secret": secret,
                              "cert": cert_path.read_text(encoding="utf-8")})

    conf = Path(data_dir) / f"frpc-{label}.toml"
    conf.parent.mkdir(parents=True, exist_ok=True)
    log_file = str(Path(data_dir) / f"frpc-{label}.log")
    conf.write_text(
        frpc_config_text(label, hub_token, local_port, port, log_file=log_file),
        encoding="ascii",
    )

    save_state(Path(state_path), {
        "label": label,
        "port": port,
        "entry": f"https://{fqdn}/",
        "fqdn": fqdn,
        "cert": str(cert_path),
        "key": str(key_path),
    })

    started = False
    if tunnel is not None and frpc is not None:
        tunnel.frpc = Path(frpc)
        tunnel.conf = conf
        tunnel.start()
        started = True

    return {
        "connected": True,
        "status": "granted",
        "label": label,
        "port": port,
        "fqdn": fqdn,
        "entry": f"https://{fqdn}/",
        "cert": str(cert_path),
        "tunnel_config": str(conf),
        "tunnel_started": started,
        "frpc": str(frpc) if frpc else "",
    }

"""rigctld 生命周期管理：探测 → 按配置拉起 → 看护 → 停止。

## 为什么需要这个模块（2026-09-17 实测）

Windows 安装版只带 `libhamlib.dll`（`hamlib_wrapper` 用 ctypes 枚举机型），**不带也从不
启动 `rigctld.exe`**；而 `MRRC` 里 `TRXRIG` 只认 rigctld 的 TCP 端口（127.0.0.1:4532）：

    ⚠ rigctld daemon not running: timed out
    Running in simulation mode - radio commands will be simulated

于是用户装了包、配置也写对了（`rig_model = FT-891` / COM8 / 38400），电台依旧完全不可控。
用户上报 20260917-073700-14ef、20260917-085736-ebd2 都是这一条根因（"音频能同步、CAT 连不上"）。
macOS 之所以没这个毛病，是因为 `mrrc_control.sh` / `mrrc_multi.sh` 在外面拉 rigctld。

## 设计约束（改之前先读）

1. **已有监听者绝不抢端口**：macOS 的 `mrrc_control.sh` 继续按老流程管 rigctld，
   本模块探测到端口已经在响应就什么都不做（`mode="external"`）。
2. **只在能自己拉起时才自动拉起**：`autostart = auto`（默认）= 本地能找到 rigctld 可执行
   （Windows 安装版的 `vendor/hamlib/windows/bin/x64/rigctld.exe`）；`true` / `false` 显式覆盖，
   `MRRC_RIGCTLD=0/1` 环境变量优先（排障用）。
3. **参数只有一套来源**：`[INSTANCE_SETTINGS] instance_rigctl_*` → `[HAMLIB]` 兜底，
   与 `mrrc_control.sh` 的顺序完全一致；空值一律不传（`-C stop_bits=` 空串会让 hamlib 起不来）。
4. **自己拉起的进程必须认得出来**：pid + 参数指纹写进 `<配置目录>/rigctld.managed.json`，
   改机型/串口重启后按指纹判断"复用还是换掉"，避免换了 FT-891 还连着 IC-M710 的旧进程。
5. **失败要留证据**：rigctld 的 stdout/stderr 落到 `<配置目录>/logs/rigctld.log`（2MB 滚动），
   诊断包会带上它 —— 否则串口打不开这种事在用户机器上完全不可见。

本模块是"松散文件"（不进 PYZ，见 packaging/pyinstaller/mrrc_server.spec 的 _APP_MODULES），
可随热修补丁单独替换。
"""

import configparser
import hashlib
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4532
RIGCTLD_NAMES = ("rigctld.exe", "rigctld")
STATE_NAME = "rigctld.managed.json"
LOG_NAME = "rigctld.log"
LOG_MAX_BYTES = 2 * 1024 * 1024

# 串口细分参数：hamlib 的 rigctld 通过 -C <token>=<value> 接收（token 名与配置键同名）
_SERIAL_TOKENS = ("stop_bits", "data_bits", "serial_parity", "serial_handshake",
                  "dtr_state", "rts_state")

# 配置里表示"没设"的写法：空串、None/Null、-、unset
_EMPTY_VALUES = {"", "none", "null", "nil", "-", "unset", "0.0"}


# --------------------------------------------------------------------------- #
# 配置解析
# --------------------------------------------------------------------------- #
def _get(cfg, section, key, default=""):
    try:
        value = cfg.get(section, key)
    except Exception:
        return default
    return "" if value is None else str(value).strip()


def _is_set(value):
    return value.strip().lower() not in _EMPTY_VALUES


def _as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on", "auto")


def data_dir(config_path=None, runtime_dir=None):
    """状态/日志落盘目录：配置文件所在目录（Windows 安装版 = %LOCALAPPDATA%\\MRRC）。"""
    if config_path:
        return os.path.dirname(os.path.abspath(config_path))
    return runtime_dir or os.getcwd()


def find_binary(runtime_dir=None, resource_dir=None, environ=None):
    """找 rigctld 可执行文件：先打包目录（安装版自带），再 PATH（macOS/Linux 开发机）。"""
    env = os.environ if environ is None else environ
    bases = []
    for base in (runtime_dir, resource_dir):
        if not base:
            continue
        bases.append(base)
        # PyInstaller onedir：运行时目录旁边还有一个 _internal/
        bases.append(os.path.join(base, "_internal"))
    seen = set()
    for base in bases:
        for name in RIGCTLD_NAMES:
            path = os.path.join(base, "vendor", "hamlib", "windows", "bin", "x64", name)
            if path in seen:
                continue
            seen.add(path)
            if os.path.isfile(path):
                return path
    for name in RIGCTLD_NAMES:
        for directory in env.get("PATH", "").split(os.pathsep):
            if not directory:
                continue
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                return path
    return ""


def rigctld_settings(config, models=None, environ=None, runtime_dir=None, resource_dir=None):
    """把配置翻译成一份"怎么起 rigctld"的完整描述（纯函数，便于测试）。

    键：autostart/binary/host/port/model/model_text/device/speed/stop_bits/data_bits/
        serial_parity/serial_handshake/dtr_state/rts_state/spawn_blocker
    """
    cfg = config if hasattr(config, "get") else configparser.ConfigParser()
    env = os.environ if environ is None else environ

    host = (_get(cfg, "INSTANCE_SETTINGS", "instance_rigctl_host")
            or DEFAULT_HOST)
    port = _get(cfg, "INSTANCE_SETTINGS", "instance_rigctl_port") or ""
    try:
        port = int(port)
    except Exception:
        port = DEFAULT_PORT

    device = (_get(cfg, "INSTANCE_SETTINGS", "instance_rigctl_device")
              or _get(cfg, "HAMLIB", "rig_pathname"))
    speed = (_get(cfg, "INSTANCE_SETTINGS", "instance_rigctl_speed")
             or _get(cfg, "HAMLIB", "rig_rate"))

    model_text = _get(cfg, "HAMLIB", "rig_model")
    model_raw = _get(cfg, "INSTANCE_SETTINGS", "instance_rigctl_model") or model_text
    model = None
    model_text_out = model_text
    if model_raw:
        if str(model_raw).strip().isdigit():
            model = int(str(model_raw).strip())
        else:
            try:
                import rig_models
                found = rig_models.resolve(model_raw, models)
            except Exception:
                found = None
            if found:
                model = int(found["id"])
                model_text_out = found["name"]
            else:
                model_text_out = model_raw

    settings = {
        "host": host,
        "port": port,
        "model": model,
        "model_text": model_text_out,
        "device": device,
        "speed": speed,
    }
    for token in _SERIAL_TOKENS:
        settings[token] = (_get(cfg, "INSTANCE_SETTINGS", "instance_rigctl_" + token)
                           or _get(cfg, "HAMLIB", token))

    binary = find_binary(runtime_dir=runtime_dir, resource_dir=resource_dir, environ=env)
    settings["binary"] = binary

    # autostart 判定：环境变量 > 配置 > auto（有自带 rigctld 才启用）
    mode = _get(cfg, "HAMLIB", "rigctld_autostart") or "auto"
    env_override = str(env.get("MRRC_RIGCTLD", "")).strip().lower()
    if env_override in ("0", "false", "no", "off"):
        autostart = False
        source = "env"
    elif env_override in ("1", "true", "yes", "on"):
        autostart = True
        source = "env"
    elif mode.lower() in ("false", "0", "no", "off"):
        autostart = False
        source = "config"
    elif mode.lower() in ("true", "1", "yes", "on"):
        autostart = True
        source = "config"
    else:
        autostart = bool(binary)
        source = "auto"
    settings["autostart"] = autostart
    settings["autostart_source"] = source

    blocker = ""
    if not _is_set(device):
        blocker = "device"
    elif model is None:
        blocker = "model"
    elif not binary:
        blocker = "binary"
    settings["spawn_blocker"] = blocker
    return settings


def build_argv(settings):
    """组装 rigctld 命令行（与 mrrc_control.sh 的 -m/-r/-s/-C/-T/-t 顺序一致）。"""
    argv = [settings.get("binary") or RIGCTLD_NAMES[0]]
    if settings.get("model") is not None:
        argv += ["-m", str(settings["model"])]
    if _is_set(settings.get("device", "")):
        argv += ["-r", str(settings["device"]).strip()]
    if _is_set(str(settings.get("speed", ""))):
        argv += ["-s", str(settings["speed"]).strip()]
    for token in _SERIAL_TOKENS:
        value = str(settings.get(token, "") or "").strip()
        if _is_set(value):
            argv += ["-C", f"{token}={value}"]
    argv += ["-T", str(settings.get("host") or DEFAULT_HOST), "-t", str(settings.get("port") or DEFAULT_PORT)]
    argv += ["-vvv"]                      # 串口 I/O 是排障的唯一线索（落 logs/rigctld.log）
    return argv


def fingerprint(settings):
    """参数指纹：判断"端口上那个 rigctld 还是不是我要的那一个"。"""
    core = "|".join(str(x) for x in (
        os.path.basename(settings.get("binary") or ""),
        settings.get("model"),
        settings.get("device"),
        settings.get("speed"),
        settings.get("host"),
        settings.get("port"),
        *[settings.get(t, "") for t in _SERIAL_TOKENS],
    ))
    return hashlib.sha256(core.encode("utf-8", "replace")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# 端口探测 / 进程识别
# --------------------------------------------------------------------------- #
def probe(host, port, timeout=2.0):
    """探测 rigctld 是否在正常应答。返回 (ok, detail)。

    detail 区分三种失败，排障时能一眼看出是"没人监听"还是"有人监听但卡住"：
      refused  端口关闭（没起 rigctld）
      timeout  连上了但不回答 / 连接被丢（rigctld 卡在串口上、或防火墙拦截）
      error    其它 OSError
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout)
        sock.connect((host, int(port)))
    except socket.timeout:
        return False, "timeout"
    except ConnectionRefusedError:
        return False, "refused"
    except OSError as exc:
        # Windows 的 WSAECONNREFUSED（10061）也走这里，转成 refused 便于读日志
        if getattr(exc, "winerror", None) == 10061 or "refused" in str(exc).lower():
            return False, "refused"
        return False, f"error: {exc}"
    try:
        sock.settimeout(timeout)
        sock.sendall(b"f\n")
        data = sock.recv(256)
        if not data:
            return False, "timeout"
        return True, ""
    except socket.timeout:
        return False, "timeout"
    except OSError as exc:
        return False, f"error: {exc}"
    finally:
        try:
            sock.close()
        except Exception:
            pass


def process_name(pid):
    """进程名（认人用）；查不到返回 ''。"""
    if not pid:
        return ""
    try:
        if os.name == "nt":
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout or ""
            first = out.strip().splitlines()[0] if out.strip() else ""
            return first.split(",")[0].strip('"') if first else ""
        out = subprocess.run(["ps", "-p", str(int(pid)), "-o", "comm="],
                             capture_output=True, text=True, timeout=10).stdout or ""
        return out.strip()
    except Exception:
        return ""


def kill_pid(pid):
    """结束进程（先礼后兵）；失败不抛异常。"""
    if not pid:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"],
                           capture_output=True, text=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            import signal
            os.kill(int(pid), signal.SIGTERM)
    except Exception as exc:
        logger.debug(f"结束 rigctld pid={pid} 失败: {exc}")


def rotate_log(path, max_bytes=LOG_MAX_BYTES):
    """超限就把当前日志挪成 .prev（保留上一份，供诊断包取尾部）。"""
    try:
        if path and os.path.isfile(path) and os.path.getsize(path) > max_bytes:
            prev = path + ".prev"
            if os.path.exists(prev):
                os.remove(prev)
            os.replace(path, prev)
    except Exception as exc:
        logger.debug(f"rigctld 日志滚动失败: {exc}")


def _kill_child_with_parent(proc):
    """Windows：把 rigctld 放进 KillOnJobClose 的 Job 对象。

    否则用户直接关启动器窗口（MRRC-Server.exe 被 TerminateProcess）时，rigctld 会活下来
    继续占着 COM 口 —— 用户想用别的 CAT 软件时打不开串口，而且找不到是谁占的。
    失败只记 debug：Job 嵌套 / 权限受限时都不允许影响拉起 rigctld。
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class _BasicLimit(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                        ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class _IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class _ExtendedLimit(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", _BasicLimit),
                        ("IoInfo", _IoCounters),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return
        info = _ExtendedLimit()
        info.BasicLimitInformation.LimitFlags = 0x2000        # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            return
        handle = getattr(proc, "_handle", None)
        if not handle:
            return
        if not kernel32.AssignProcessToJobObject(job, wintypes.HANDLE(int(handle))):
            logger.debug(f"把 rigctld 加入 Job 对象失败（err={ctypes.get_last_error()}）")
            return
        proc._mrrc_job = job                                # 持住句柄：本进程活着 Job 就在
    except Exception as exc:
        logger.debug(f"Job 对象绑定失败（无碍，仅可能留下孤儿 rigctld）: {exc}")


def state_path(config_path):
    """自己拉起的 rigctld 的 pid/参数指纹（配置文件同目录）。"""
    return os.path.join(data_dir(config_path), STATE_NAME)


# --------------------------------------------------------------------------- #
# 管理器
# --------------------------------------------------------------------------- #
class RigctldManager:
    """进程级单例：确保"配置指向的 rigctld"在运行，并看护自己拉起的那一个。"""

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_once()
        return cls._instance

    def _init_once(self):
        self._lock = threading.RLock()
        self._proc = None
        self._pid = None
        self._settings = None
        self._config_path = None
        self._mode = "idle"          # idle|external|managed|disabled|blocked|failed
        self._last_error = ""
        self._spawned_at = 0.0
        self._restarts = 0
        self._starting = False
        self._watch_stop = threading.Event()
        self._watch_thread = None
        self._log_state = {}
        self._log_path = ""

    # ---- 日志（限流，避免串口坏掉时刷屏） ----
    def _log(self, level, key, message, interval=300.0):
        now = time.time()
        state = self._log_state.setdefault(key, {"last": 0.0, "count": 0})
        state["count"] += 1
        if now - state["last"] >= interval:
            extra = f"（同类已 {state['count']} 次）" if state["count"] > 1 else ""
            state["last"] = now
            state["count"] = 0
            logger.log(level, message + extra)

    # ---- 状态快照（诊断包 / API 用） ----
    def status(self):
        with self._lock:
            info = {
                "mode": self._mode,
                "pid": self._pid,
                "restarts": self._restarts,
                "last_error": self._last_error,
                "log_path": self._log_path,
                "settings": {},
            }
            s = self._settings or {}
            for key in ("binary", "host", "port", "model", "model_text", "device", "speed",
                        "autostart", "autostart_source", "spawn_blocker"):
                if key in s:
                    info["settings"][key] = s[key]
            if s.get("spawn_blocker"):
                info["spawn_blocker"] = s["spawn_blocker"]
            return info

    # ---- 状态文件 ----
    def _read_state(self):
        path = state_path(self._config_path)
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def _write_state(self, settings, pid):
        try:
            rotate_log(self._log_path)
            with open(state_path(self._config_path), "w", encoding="utf-8") as fh:
                json.dump({"pid": pid, "argv": build_argv(settings),
                           "fingerprint": fingerprint(settings),
                           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}, fh,
                          ensure_ascii=False, indent=1)
        except Exception as exc:
            logger.debug(f"写 rigctld 状态文件失败: {exc}")

    def _clear_state(self):
        try:
            os.remove(state_path(self._config_path))
        except Exception:
            pass

    # ---- 主入口 ----
    def ensure(self, config, config_path=None, runtime_dir=None, resource_dir=None, wait_s=3.0):
        """确保 rigctld 可用。返回 True 表示确信端口上有可应答的 rigctld。"""
        with self._lock:
            self._config_path = config_path or self._config_path
            self._log_path = os.path.join(data_dir(self._config_path, runtime_dir), "logs", LOG_NAME)
            settings = rigctld_settings(config, runtime_dir=runtime_dir, resource_dir=resource_dir)
            self._settings = settings

            if not settings["autostart"]:
                self._mode = "disabled"
                self._last_error = "autostart=off"
                return False
            if settings["spawn_blocker"]:
                self._mode = "blocked"
                self._last_error = {
                    "device": "配置里没有串口（[HAMLIB] rig_pathname / instance_rigctl_device）",
                    "model": f"型号无法解析成 hamlib 数字 id（rig_model={settings['model_text']!r}）",
                    "binary": "找不到 rigctld 可执行文件（未随包分发 / 不在 PATH）",
                }.get(settings["spawn_blocker"], settings["spawn_blocker"])
                self._log(logging.WARNING, "blocked:" + settings["spawn_blocker"],
                          f"⚠ 无法自动启动 rigctld：{self._last_error}")
                return False

            ok, detail = probe(settings["host"], settings["port"])
            state = self._read_state()
            same = bool(state) and state.get("fingerprint") == fingerprint(settings)

            if same and state.get("pid") and self._alive(state["pid"]):
                # 上一轮（同配置）留下的自有进程：直接接管，不重启串口
                self._pid = int(state["pid"])
                self._mode = "managed"
                self._last_error = ""
                self._start_watch()
                if ok:
                    logger.info(f"✓ rigctld 已在本机运行（pid={self._pid}，{settings['device']}，"
                                f"复用上一轮进程）")
                    return True
                # 进程在但端口不应答：给它一点时间（复位后哈）
                ok, detail = self._wait_ready(settings, wait_s)
                self._last_error = "" if ok else f"rigctld 在跑但不回答（{detail}）"
                return ok

            if ok and not same:
                if state:
                    self._retire_stale(state, settings)
                self._mode = "external"
                self._last_error = ""
                logger.info(f"✓ rigctld 已在 {settings['host']}:{settings['port']} 应答"
                            f"（外部进程/脚本管理，本模块不接管）")
                return True

            if state:
                self._retire_stale(state, settings)

            self._mode = "starting"
            self._restarts = 0
            self._watch_stop.clear()
            proc = self._spawn(settings)
            if proc is None:
                self._mode = "failed"
                return False
            self._pid = proc.pid
            self._write_state(settings, proc.pid)
            self._start_watch()
            ok, detail = self._wait_ready(settings, wait_s)
            if ok:
                self._mode = "managed"
                self._last_error = ""
                logger.info(f"✓ rigctld 已启动（pid={proc.pid}，model={settings['model']}，"
                            f"device={settings['device']}，speed={settings['speed']}，"
                            f"{settings['host']}:{settings['port']}）")
                return True
            self._mode = "failed"
            tail = self._log_tail()
            self._last_error = f"rigctld 启动后 {detail or '没有应答'}"
            self._log(logging.ERROR, "start-failed",
                      f"❌ rigctld 未能提供服务（{self._last_error}）——详情见 {self._log_path}"
                      + (f"；日志尾部：{tail}" if tail else ""))
            return False

    def _retire_stale(self, state, settings):
        """旧的自有进程参数和现在不一致（换机型/换串口）：结束它，别让它占着串口。"""
        pid = state.get("pid")
        name = process_name(pid).lower()
        if pid and "rigctld" in name:
            logger.info(f"↻ 配置已变化（旧参数 {state.get('argv')}）→ 结束旧 rigctld pid={pid}")
            kill_pid(pid)
            deadline = time.time() + 3.0
            while time.time() < deadline and self._alive(pid):
                time.sleep(0.1)
        self._clear_state()

    def _alive(self, pid):
        return bool(pid) and "rigctld" in process_name(pid).lower()

    def _spawn(self, settings):
        argv = build_argv(settings)
        log_path = self._log_path
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            rotate_log(log_path)
            log_fh = open(log_path, "ab", buffering=0)
        except Exception as exc:
            logger.debug(f"打开 rigctld 日志失败（不落盘继续）: {exc}")
            log_fh = subprocess.DEVNULL
        flags = 0
        if os.name == "nt":
            flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)   # 别弹黑框
                     | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        try:
            proc = subprocess.Popen(
                argv,
                cwd=os.path.dirname(settings["binary"]) or None,
                stdin=subprocess.DEVNULL,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                creationflags=flags,
                close_fds=(os.name != "nt"),
            )
        except Exception as exc:
            self._last_error = f"启动 rigctld 失败: {exc}"
            self._log(logging.ERROR, "spawn-error", f"❌ {self._last_error}")
            return None
        finally:
            if hasattr(log_fh, "close"):
                try:
                    log_fh.close()
                except Exception:
                    pass
        self._proc = proc
        self._spawned_at = time.time()
        _kill_child_with_parent(proc)
        logger.info(f"🚀 启动 rigctld: {' '.join(argv)}")
        return proc

    def _wait_ready(self, settings, wait_s):
        """等 rigctld 打开串口并开始应答（串口握手要几百毫秒到几秒）。"""
        deadline = time.time() + max(0.0, float(wait_s))
        detail = "refused"
        while True:
            if self._proc is not None and self._proc.poll() is not None and self._mode == "starting":
                return False, f"进程已退出（code={self._proc.returncode}）"
            ok, detail = probe(settings["host"], settings["port"], timeout=1.0)
            if ok:
                return True, ""
            if time.time() >= deadline:
                return False, detail
            time.sleep(0.25)

    def _start_watch(self):
        if self._watch_thread and self._watch_thread.is_alive():
            return
        self._watch_thread = threading.Thread(target=self._watch_loop, name="rigctld-watch", daemon=True)
        self._watch_thread.start()

    def _watch_loop(self):
        """看护自己拉起的 rigctld：掉了就按退避重拉（USB 掉线/电台断电后能自己回来）。"""
        delay = 5.0
        while not self._watch_stop.is_set():
            self._watch_stop.wait(2.0)
            if self._watch_stop.is_set():
                return
            with self._lock:
                if self._mode not in ("managed", "failed"):
                    return
                alive = self._proc.poll() is None if self._proc is not None else self._alive(self._pid)
                if alive:
                    continue
                if time.time() - self._spawned_at < 3.0:
                    continue
                settings = self._settings
                if not settings:
                    return
                self._restarts += 1
                self._log(logging.WARNING, "restart",
                          f"⚠ rigctld 已退出（pid={self._pid}），{delay:.0f}s 后自动重拉"
                          f"（第 {self._restarts} 次）")
                self._watch_stop.wait(delay)
                if self._watch_stop.is_set():
                    return
                self._spawn_stopped = True
                old = self._proc
                proc = self._spawn(settings)
                if proc is None:
                    delay = min(delay * 2, 300.0)
                    continue
                self._pid = proc.pid
                self._write_state(settings, proc.pid)
                ok, detail = self._wait_ready(settings, 3.0)
                if ok:
                    logger.info(f"✓ rigctld 已重新拉起（pid={proc.pid}）")
                    self._mode = "managed"
                    self._last_error = ""
                    delay = 5.0
                else:
                    self._last_error = f"重拉失败（{detail}）"
                    self._mode = "failed"
                    delay = min(delay * 2, 300.0)
                if old is not None and old.poll() is None:
                    try:
                        old.terminate()
                    except Exception:
                        pass
        return

    def _log_tail(self, limit=600):
        for path in (self._log_path, self._log_path + ".prev"):
            try:
                if not path or not os.path.isfile(path):
                    continue
                with open(path, "rb") as fh:
                    fh.seek(max(0, os.path.getsize(path) - 4096))
                    text = fh.read().decode("utf-8", "replace").strip()
                if text:
                    return text[-limit:].replace("\n", " | ")
            except Exception:
                continue
        return ""

    def stop(self):
        """结束自己拉起的 rigctld（进程退出/重启前调用，释放串口）。"""
        self._watch_stop.set()
        proc = self._proc
        pid = self._pid
        self._proc = None
        self._pid = None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        elif pid and self._mode == "managed" and self._alive(pid):
            kill_pid(pid)
        self._clear_state()
        if self._mode != "disabled":
            self._mode = "idle"


_manager = None


def get_manager():
    global _manager
    if _manager is None:
        _manager = RigctldManager()
    return _manager


def ensure_rigctld(config, config_path=None, runtime_dir=None, resource_dir=None, wait_s=3.0):
    """给 MRRC 用的一行入口：出错也不许影响启动。"""
    try:
        return get_manager().ensure(config, config_path=config_path, runtime_dir=runtime_dir,
                                    resource_dir=resource_dir, wait_s=wait_s)
    except Exception as exc:                     # 绝不让电台控制把服务拖死
        logger.error(f"rigctld 自动启动失败（忽略，继续启动服务）: {exc}")
        return False


def stop_managed():
    """MRRC 退出/自我重启前调用。"""
    try:
        get_manager().stop()
    except Exception as exc:
        logger.debug(f"停止 rigctld 失败: {exc}")


def status():
    try:
        return get_manager().status()
    except Exception:
        return {}


if __name__ == "__main__":                       # 手工排障：python3 rigctld_manager.py [MRRC.conf]
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    import configparser as _cp
    path = sys.argv[1] if len(sys.argv) > 1 else "MRRC.conf"
    parser = _cp.ConfigParser()
    parser.read(path, encoding="utf-8")
    print(json.dumps(rigctld_settings(parser, runtime_dir=os.path.dirname(os.path.abspath(path))),
                     ensure_ascii=False, indent=1))
    print(json.dumps(get_manager().status(), ensure_ascii=False, indent=1))

"""rigctld 自启动看护（Windows 安装版必须自己拉起电台后台）

背景（真机上报 2026-09-17）：Unix 由 ``mrrc_control.sh start`` 启动 rigctld，
而 **Windows 安装版历史上只"检测"不启动** → 用户必须手动开 ``rigctld.exe``，
否则 MRRC 进入模拟模式、界面提示"rigctld daemon not running"。

本模块由 ``hamlib_wrapper`` 在**导入时**调用（MRRC 启动早期就会 import hamlib_wrapper），
所以它是"可热修"的挂载点：把本文件与 ``hamlib_wrapper.py`` 放进热修覆盖层即可生效。

行为（幂等、绝不阻断启动）
--------------------------
* 目标端口已在监听 → 什么都不做（``already_running``）；
* 配置里没有电台（model 为空/none/0） → ``no_rig``；
* ``[HAMLIB] autostart = false`` 或 ``MRRC_RIGCTLD_AUTOSTART=0`` → ``disabled``；
* 找不到 ``rigctld`` 可执行文件 → ``no_binary``（打印一行可执行的提示）；
* 否则拉起：``rigctld -m <model> -r <device> -s <speed> -C stop_bits=<n> -T <host> -t <port> -vvv``
  （参数与 ``mrrc_control.sh`` 保持一致），日志写 ``logs/rigctld-stdout.log``。

配置优先级与 ``mrrc_control.sh`` 一致：
``[INSTANCE_SETTINGS] instance_rigctl_*`` 优先，其次 ``[HAMLIB] rig_model/rig_pathname/rig_rate/stop_bits``，
最后是内置默认值。机型名用 ``rig_models.resolve()`` 折算成 hamlib 数字。
"""

from __future__ import annotations

import configparser
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

# 与 mrrc_control.sh 的默认值保持一致
DEFAULTS = {"model": "", "device": "", "speed": "", "stop_bits": "", "host": "127.0.0.1", "port": "4532"}

_proc = None
_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# 配置
# --------------------------------------------------------------------------- #
def _cfg_get(cfg: configparser.ConfigParser, section: str, key: str, default: str = "") -> str:
    try:
        value = cfg.get(section, key)
    except Exception:
        return default
    return (value or "").strip() or default


def resolve_config(cfg: configparser.ConfigParser) -> dict:
    """把配置折算成启动 rigctld 需要的参数（双键优先级 + 机型名→数字）。"""
    out = dict(DEFAULTS)
    # [INSTANCE_SETTINGS]（设备配置抽屉写入的就是这里）
    out["model"] = _cfg_get(cfg, "INSTANCE_SETTINGS", "instance_rigctl_model",
                            _cfg_get(cfg, "HAMLIB", "rig_model", ""))
    out["device"] = _cfg_get(cfg, "INSTANCE_SETTINGS", "instance_rigctl_device",
                             _cfg_get(cfg, "HAMLIB", "rig_pathname", ""))
    out["speed"] = _cfg_get(cfg, "INSTANCE_SETTINGS", "instance_rigctl_speed",
                            _cfg_get(cfg, "HAMLIB", "rig_rate", ""))
    out["stop_bits"] = _cfg_get(cfg, "INSTANCE_SETTINGS", "instance_rigctl_stop_bits",
                                _cfg_get(cfg, "HAMLIB", "stop_bits", ""))
    out["host"] = _cfg_get(cfg, "INSTANCE_SETTINGS", "instance_rigctl_host", out["host"])
    out["port"] = _cfg_get(cfg, "INSTANCE_SETTINGS", "instance_rigctl_port", out["port"])
    out["autostart"] = _cfg_get(cfg, "HAMLIB", "autostart", "true")

    # 机型号折算：**必须便宜**。这里绝不能做"实时枚举本机 hamlib 机型"这类重活——
    # 它要遍历几百个 id、甚至去开用户电台占用的串口，会把 MRRC 的启动卡死（真机实测）。
    # 顺序：数字直接透传 → 运行中的 rigctld 自报（\dump_caps，极便宜）→ 原样交给 rigctld。
    model = str(out["model"]).strip()
    if model and not model.lstrip("-").isdigit():
        code = None
        try:
            import rig_models
            cached = getattr(rig_models, "cached_rigctld_model", None)
            if callable(cached):
                code = cached(out.get("host") or DEFAULTS["host"], out.get("port") or DEFAULTS["port"])
        except Exception:
            code = None
        if code:
            out["model"] = str(code)
        # 折算不出来就保留原名：rigctld 的 -m 也接受机型名（找不到时它自己会报错，日志可见）
    return out


def has_rig(cfg_params: dict) -> bool:
    model = str(cfg_params.get("model", "")).strip().lower()
    return model not in ("", "none", "0", "-1")


def autostart_enabled(cfg_params: dict) -> bool:
    if os.environ.get("MRRC_RIGCTLD_AUTOSTART", "").strip() in ("0", "false", "False", "no"):
        return False
    return str(cfg_params.get("autostart", "true")).strip().lower() not in ("0", "false", "no", "off")


def candidate_configs() -> list[Path]:
    """按"最可能是这台机器在用的那份"排序找配置。"""
    cands: list[Path] = []
    env = os.environ.get("MRRC_CONF") or os.environ.get("MRRC_CONFIG")
    if env:
        cands.append(Path(env))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        cands.append(Path(local) / "MRRC" / "MRRC.conf")
    here = Path(sys.argv[0]).resolve().parent if sys.argv and sys.argv[0] else Path.cwd()
    frozen_app = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else here
    cands += [frozen_app / "MRRC.conf", Path.cwd() / "MRRC.conf",
              Path(__file__).resolve().parent / "MRRC.conf"]
    seen, out = set(), []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def load_config() -> configparser.ConfigParser | None:
    for path in candidate_configs():
        if not path.is_file():
            continue
        cfg = configparser.ConfigParser()
        try:
            cfg.read(str(path), encoding="utf-8-sig")
        except Exception:
            continue
        return cfg
    return None


# --------------------------------------------------------------------------- #
# 可执行文件定位
# --------------------------------------------------------------------------- #
def find_rigctld() -> str | None:
    """按优先级找 rigctld：显式覆盖 → 安装目录 vendor → PATH → 常见安装位置。"""
    env = os.environ.get("MRRC_RIGCTLD_BIN", "").strip()
    if env:
        # 显式指定即权威：指错就返回 None（不回退 PATH），便于排障与测试
        return env if Path(env).is_file() else None

    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    roots.append(Path(__file__).resolve().parent)

    rel = [
        Path("vendor") / "hamlib" / "windows" / "bin" / "x64",
        Path("vendor") / "hamlib" / "windows" / "bin",
        Path("vendor") / "hamlib" / "bin",
        Path("rigctld"),
        Path("bin"),
    ]
    names = ["rigctld.exe", "rigctld"]
    for root in roots:
        for r in rel:
            for n in names:
                cand = root / r / n
                if cand.is_file():
                    return str(cand)

    from shutil import which
    for n in names:
        found = which(n)
        if found:
            return found

    # 常见安装位置：Hamlib 官方 Windows 包会带版本号目录（如 hamlib-w64-4.7.2），
    # 所以这里要按通配匹配（真机实测：C:\Program Files\hamlib-w64-4.7.2\bin\rigctld.exe）。
    patterns = [
        "C:/Program Files/hamlib*/bin/rigctld.exe",
        "C:/Program Files (x86)/hamlib*/bin/rigctld.exe",
        "C:/Program Files/Hamlib*/bin/rigctld.exe",
        "C:/hamlib*/bin/rigctld.exe",
        "C:/msys64/*/bin/rigctld.exe",
    ]
    import glob
    for pat in patterns:
        for hit in sorted(glob.glob(pat)):
            if Path(hit).is_file():
                return hit
    # 环境变量兜底（可选）
    for env_name in ("HAMLIB_BIN", "HAMLIB_PATH"):
        val = os.environ.get(env_name, "").strip()
        if val:
            cand = Path(val) / ("rigctld.exe" if os.name == "nt" else "rigctld")
            if cand.is_file():
                return str(cand)
    return None


# --------------------------------------------------------------------------- #
# 启动
# --------------------------------------------------------------------------- #
def build_command(binary: str, params: dict) -> list[str]:
    """与 mrrc_control.sh 的 start_rigctld 参数保持一致。"""
    cmd = [binary]
    if str(params.get("model", "")).strip():
        cmd += ["-m", str(params["model"]).strip()]
    if str(params.get("device", "")).strip():
        cmd += ["-r", str(params["device"]).strip()]
    if str(params.get("speed", "")).strip():
        cmd += ["-s", str(params["speed"]).strip()]
    if str(params.get("stop_bits", "")).strip():
        cmd += ["-C", f"stop_bits={str(params['stop_bits']).strip()}"]
    cmd += ["-T", str(params.get("host") or DEFAULTS["host"]).strip() or DEFAULTS["host"]]
    cmd += ["-t", str(params.get("port") or DEFAULTS["port"]).strip() or DEFAULTS["port"]]
    cmd += ["-vvv"]
    return cmd


def port_open(host: str, port, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def ensure_running(cfg: configparser.ConfigParser | None = None, log_dir: Path | None = None,
                   dry_run: bool = False, wait_seconds: float = 3.0) -> dict:
    """幂等地确保 rigctld 在跑。返回 {'status', 'detail', 'command'}（永不抛异常）。"""
    global _proc
    result = {"status": "unknown", "detail": "", "command": []}
    try:
        cfg = cfg or load_config()
        if cfg is None:
            result.update(status="no_config", detail="找不到 MRRC.conf，跳过 rigctld 自启动")
            return result
        params = resolve_config(cfg)

        if not has_rig(params):
            result.update(status="no_rig", detail="配置里没有电台（model 为空），无需启动 rigctld")
            return result
        if not autostart_enabled(params):
            result.update(status="disabled", detail="[HAMLIB] autostart=false（或 MRRC_RIGCTLD_AUTOSTART=0）")
            return result

        host, port = params["host"], params["port"]
        if port_open(host, port):
            result.update(status="already_running",
                          detail=f"rigctld 已在 {host}:{port} 监听（外部启动或上次残留）")
            return result

        binary = find_rigctld()
        if not binary:
            result.update(status="no_binary", detail=(
                "找不到 rigctld（Hamlib 的电台后台）。请任选一种：\n"
                "  ① 安装 Hamlib 并把 rigctld.exe 放到 MRRC 安装目录的 vendor\\hamlib\\windows\\bin\\x64\\ 下；\n"
                "  ② 把 Hamlib 的 bin 目录加入 PATH；\n"
                "  ③ 设置环境变量 MRRC_RIGCTLD_BIN=<rigctld.exe 的完整路径>。\n"
                "  未启动 rigctld 时 MRRC 会以模拟模式运行（界面可开，但电台命令不生效）。"))
            return result

        cmd = build_command(binary, params)
        result["command"] = cmd
        if dry_run:
            result.update(status="dry_run", detail="dry-run：只组装命令，不真正启动")
            return result

        # 真正要 spawn 之前才拦测试环境：纯逻辑用例（no_rig/disabled/already_running/no_binary）
        # 必须照常返回，只有"会真拉起进程"这一步在测试里跳过
        if "unittest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
            result.update(status="skipped_in_tests",
                          detail="检测到测试环境，跳过真正启动 rigctld（逻辑判断已在上方完成）")
            return result

        log_path = None
        if log_dir is None:
            local = os.environ.get("LOCALAPPDATA")
            log_dir = (Path(local) / "MRRC" / "logs") if local else (Path(binary).parent / "logs")
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "rigctld-stdout.log"
        except OSError:
            log_path = None

        with _lock:
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            # 永远重定向子进程输出：绝不能让它继承父进程的 stdout/stderr
            # （否则在测试/脚本里父进程会一直等管道关闭 —— 真机实测挂死 300s）
            sink = None
            if log_path:
                try:
                    sink = open(log_path, "a", encoding="utf-8", errors="replace", buffering=1)
                except OSError:
                    sink = None
            _proc = subprocess.Popen(
                cmd, cwd=str(Path(binary).parent), creationflags=creationflags,
                stdin=subprocess.DEVNULL,
                stdout=(sink if sink is not None else subprocess.DEVNULL),
                stderr=subprocess.STDOUT)
            if sink is not None:
                try:
                    sink.close()          # 句柄已交给子进程，父进程这边关掉
                except OSError:
                    pass
        result["detail"] = f"已启动：{binary} → {host}:{port}（日志 {log_path}）"

        deadline = time.time() + max(0.5, wait_seconds)
        while time.time() < deadline:
            if port_open(host, port, timeout=0.3):
                result.update(status="started")
                return result
            if _proc.poll() is not None:
                result.update(status="failed",
                              detail=f"rigctld 启动后立刻退出（退出码 {_proc.returncode}），"
                                     f"见 {log_path}（常见原因：串口被占用、机型号/速率不匹配）")
                return result
            time.sleep(0.3)
        result.update(status="started_slow",
                      detail=f"已启动但 {wait_seconds:.0f}s 内端口未就绪，稍后自动重连（日志 {log_path}）")
        return result
    except Exception as exc:                       # 自启动失败绝不阻断启动
        result.update(status="error", detail=f"{type(exc).__name__}: {exc}")
        return result


def shutdown() -> None:
    global _proc
    if _proc is not None and _proc.poll() is None:
        try:
            _proc.terminate()
        except Exception:
            pass
    _proc = None


def autostart_from_default_config(timeout: float = 8.0) -> dict | None:
    """给 hamlib_wrapper 在导入时调用的入口（MRRC 启动路径）。

    整段包一层硬超时：宁可这次不自启动，也绝不把 MRRC 的启动卡住
    （真机实测过一次"导入时枚举机型 → 卡死"的事故）。
    """
    box: dict = {}

    def _work():
        try:
            box["res"] = ensure_running()
        except Exception as exc:
            box["res"] = {"status": "error", "detail": f"{type(exc).__name__}: {exc}"}

    th = threading.Thread(target=_work, name="rigctld-autostart", daemon=True)
    th.start()
    th.join(timeout)
    if th.is_alive():
        print(f"[rigctld] ⚠️ 自启动检查超过 {timeout:.0f}s 未完成，本次跳过（不影响启动）")
        return None
    res = box.get("res")
    if not res:
        return None
    status = res.get("status")
    if status in ("started", "started_slow"):
        print(f"[rigctld] ✅ {res['detail']}")
    elif status in ("no_binary", "failed"):
        print(f"[rigctld] ⚠️ {res['detail']}")
    elif status == "already_running":
        pass                                        # 正常情况，不刷屏
    elif status in ("disabled", "no_rig", "no_config"):
        pass
    else:
        print(f"[rigctld] 自启动检查：{status} {res.get('detail','')}")
    return res


if __name__ == "__main__":                          # 手动排障：python rigctld_supervisor.py
    import json
    print(json.dumps(ensure_running(dry_run="--dry-run" in sys.argv), ensure_ascii=False, indent=2))

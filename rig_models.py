"""hamlib 机型表：枚举真实机型，并把配置里的 rig_model 准确对应过去。

## 为什么需要这个模块

Device Config 原先用硬编码的 7 个名字（`MRRC` 里的 `RIG_MODELS = ["FT817", "IC_M710", …]`）：

  * 那不是 hamlib 实际支持的机型表（本地 hamlib 4.7.2 有 312 个机型）；
  * 而且写回配置的值（`IC_M710`）并不等于 rigctld 真正使用的**数字**型号
    （`[INSTANCE_SETTINGS] instance_rigctl_model`，脚本里默认 30003）——
    用户在 UI 里换型号，实际运行的 rigctld 根本没变，属于"看着改了其实没生效"。

本模块提供三件事：

  1. `available()`：从已加载的 hamlib（`rig_load_all_backends()` + `rig_list_foreach()`）
     枚举全部机型：`{id, name, mfg, version, status}`。实测 312 个；
  2. `resolve(value)`：把配置里的任意写法（`30003` / `IC-M710` / `IC_M710` / `ic m710` /
     旧下拉的 `FTDX10`…）解析成 hamlib 机型，带**别名表**照顾历史值；
  3. `cached_rigctld_model(host, port)`：读 rigctld 的 `\\dump_caps`，返回它**实际**加载的
     机型（用于在 UI 上验证"配置 ↔ 运行中"是否一致）。带缓存 + 后台刷新，绝不阻塞 IOLoop。

hamlib 不可用时回退到最小内置表（`available()["fallback"]` 为 True，UI 会明确提示）。
"""

from __future__ import annotations

import ctypes
import os
import re
import threading
import time

# hamlib 的 rig_status_e（见 hamlib/rig.h）
STATUS_NAMES = {
    0: "Alpha",
    1: "Untested",
    2: "Beta",
    3: "Stable",
    4: "Buggy",
}

# 历史遗留写法的别名（旧下拉表 + 常见口误写法 → hamlib 的规范名）。
# 键与值都按 _key() 归一化后比较。
ALIASES = {
    "FT817": "FT-817",
    "FT991": "FT-991",
    "FTDX10": "FTDX-10",
    "TS590": "TS-590S",
    "IC706": "IC-706",
    "IC7300": "IC-7300",
    "ICM710": "IC-M710",
    "IC7100": "IC-7100",
}

# hamlib 不可用时的最小回退表（按键位保持与真实 hamlib 一致的 id）
FALLBACK_MODELS = [
    {"id": 30003, "name": "IC-M710", "mfg": "Icom", "version": "", "status": 3},
    {"id": 3073, "name": "IC-7300", "mfg": "Icom", "version": "", "status": 3},
    {"id": 3070, "name": "IC-7100", "mfg": "Icom", "version": "", "status": 3},
    {"id": 1020, "name": "FT-817", "mfg": "Yaesu", "version": "", "status": 3},
    {"id": 1035, "name": "FT-991", "mfg": "Yaesu", "version": "", "status": 3},
    {"id": 1042, "name": "FTDX-10", "mfg": "Yaesu", "version": "", "status": 3},
    {"id": 2031, "name": "TS-590S", "mfg": "Kenwood", "version": "", "status": 3},
]

_cache = {"models": None, "fallback": False, "error": None, "loaded_at": 0.0,
          "backends_loaded": False}
_lock = threading.Lock()


def _key(text: str) -> str:
    """归一化：大写并去掉 -、_、空格、/（`IC_M710` == `IC-M710` == `ic m710`）。"""
    return re.sub(r"[-_ /]+", "", str(text or "")).upper()


# --------------------------------------------------------------------------- #
# 枚举
# --------------------------------------------------------------------------- #
class _RigCaps(ctypes.Structure):
    """struct rig_caps 的前缀字段（hamlib/rig.h 里这几个字段在最前面）。"""

    _fields_ = [
        ("rig_model", ctypes.c_int),
        ("model_name", ctypes.c_char_p),
        ("mfg_name", ctypes.c_char_p),
        ("version", ctypes.c_char_p),
        ("copyright", ctypes.c_char_p),
        ("status", ctypes.c_int),
    ]


class _quiet_c_stderr:
    """临时把 C 层 stderr 重定向到空设备。

    `rig_load_all_backends()` 会打印 50+ 行后端初始化日志（"initrigs4_icom: _init called"…）
    直接把服务日志冲烂，而这是 hamlib 的 C 层 fprintf(stderr)，Python 的 contextlib 管不着。
    """

    def __enter__(self):
        self._saved = None
        try:
            self._saved = os.dup(2)
            self._null = os.open(os.devnull, os.O_WRONLY)
            os.dup2(self._null, 2)
        except Exception:
            self._saved = None
        return self

    def __exit__(self, *exc_info):
        try:
            if self._saved is not None:
                os.dup2(self._saved, 2)
                os.close(self._saved)
                os.close(self._null)
        except Exception:
            pass
        return False


def _load_from_hamlib() -> list:
    """用 ctypes 调 hamlib 枚举机型；失败抛异常（由调用方回退）。"""
    from hamlib_wrapper import libham            # 复用其平台相关搜索路径

    libham.rig_load_all_backends.argtypes = []
    libham.rig_load_all_backends.restype = None
    if not _cache["backends_loaded"]:            # 只需加载一次（进程生命周期内有效）
        with _quiet_c_stderr():
            libham.rig_load_all_backends()       # 不调用它，机型表是空的（实测 0 个）
        _cache["backends_loaded"] = True

    found = []
    callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(_RigCaps), ctypes.c_void_p)

    @callback_type
    def _collect(caps, _data):
        caps = caps.contents
        found.append({
            "id": int(caps.rig_model),
            "name": (caps.model_name or b"").decode("utf-8", "replace"),
            "mfg": (caps.mfg_name or b"").decode("utf-8", "replace"),
            "version": (caps.version or b"").decode("utf-8", "replace"),
            "status": int(caps.status),
        })
        return 1                              # 非 0 = 继续遍历

    libham.rig_list_foreach.argtypes = [callback_type, ctypes.c_void_p]
    libham.rig_list_foreach.restype = ctypes.c_int
    libham.rig_list_foreach(_collect, None)
    if not found:
        raise RuntimeError("hamlib 返回 0 个机型（后端未加载？）")
    found.sort(key=lambda m: (m["mfg"].lower(), m["name"].lower()))
    return found


def available(force: bool = False) -> dict:
    """返回 {models: [...], fallback: bool, error: str|None}（进程内缓存）。"""
    with _lock:
        if _cache["models"] is not None and not force:
            return {"models": _cache["models"], "fallback": _cache["fallback"],
                    "error": _cache["error"]}
        try:
            models = _load_from_hamlib()
            _cache.update(models=models, fallback=False, error=None, loaded_at=time.time())
        except Exception as exc:                 # hamlib 缺失/加载失败 → 回退
            models = [dict(m, fallback=True) for m in FALLBACK_MODELS]
            _cache.update(models=models, fallback=True, error=f"{type(exc).__name__}: {exc}",
                          loaded_at=time.time())
        return {"models": _cache["models"], "fallback": _cache["fallback"], "error": _cache["error"]}


def models() -> list:
    return available()["models"]


def status_name(code) -> str:
    try:
        return STATUS_NAMES.get(int(code), "?")
    except (TypeError, ValueError):
        return "?"


# --------------------------------------------------------------------------- #
# 解析：配置值 → hamlib 机型
# --------------------------------------------------------------------------- #
def _alias_target(value: str) -> str | None:
    return ALIASES.get(_key(value))


def resolve(value, model_list=None):
    """把配置里的 rig_model 解析成机型 dict；解析不到返回 None。

    接受：数字 id、hamlib 规范名、旧别名（见 ALIASES）、大小写/分隔符任意写法。
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    items = model_list if model_list is not None else models()

    if text.isdigit():                            # 数字 → 直接按 id
        target = int(text)
        for model in items:
            if model["id"] == target:
                return model
        return None

    wanted = _key(text)
    alias = _alias_target(text)
    alias_key = _key(alias) if alias else None
    for model in items:
        if _key(model["name"]) == wanted or (alias_key and _key(model["name"]) == alias_key):
            return model
    # 再放宽一点：允许 "Icom IC-M710" 这种 "厂商 + 型号" 写法
    for model in items:
        combined = _key(f"{model['mfg']}{model['name']}")
        if combined == wanted or (alias_key and _key(f"{model['mfg']}{alias}") == combined):
            return model
    return None


def describe(value) -> dict:
    """给 UI 用：配置值 + 是否匹配 + 匹配到的机型（含数字 id）。"""
    info = available()
    model = resolve(value, info["models"])
    result = {
        "value": "" if value is None else str(value),
        "matched": bool(model),
        "id": model["id"] if model else None,
        "name": model["name"] if model else None,
        "mfg": model["mfg"] if model else None,
        "status": status_name(model["status"]) if model else None,
        "version": model["version"] if model else None,
        "fallback": info["fallback"],
    }
    if not model and value and str(value).strip().isdigit():
        result["reason"] = f"hamlib 里没有 id={value} 这个机型"
    elif not model and value:
        result["reason"] = f"hamlib 机型表里找不到“{value}”（可改用型号搜索选择）"
    return result


def suggest(value, model_list=None, limit: int = 8) -> list:
    """模糊建议：给拼写不完全一致的值找候选（UI 上提示"你是不是想要…"）。"""
    if not value:
        return []
    wanted = _key(value)
    if not wanted:
        return []
    items = model_list if model_list is not None else models()
    scored = []
    for model in items:
        key = _key(model["name"])
        if wanted in key or key in wanted:
            scored.append((abs(len(key) - len(wanted)), model))
    scored.sort(key=lambda pair: pair[0])
    return [model for _score, model in scored[:limit]]


# --------------------------------------------------------------------------- #
# rigctld 实际加载的机型（验证"配置 ↔ 运行中"是否一致）
# --------------------------------------------------------------------------- #
_rigctld_cache = {"value": None, "at": 0.0, "refreshing": False}
_RIGCTLD_TTL = 20.0
_rigctld_lock = threading.Lock()


def _parse_dump_caps(text: str) -> dict | None:
    """从 rigctld `\\dump_caps` 的多行输出里取机型信息。

    实际输出（hamlib 4.7.2 实测）：
        Caps dump for model: 30003
        Model name:\tIC-M710
        Mfg name:\tIcom
        Backend status:\tStable
        Backend version:\t20181007.0
    """
    info = {"id": None, "name": None, "mfg": None, "status": None, "version": None}

    def _value(line):
        return line.split(":", 1)[1].strip() if ":" in line else ""

    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("Caps dump for model:"):
            digits = re.sub(r"\D", "", _value(stripped))
            info["id"] = int(digits) if digits else None
        elif stripped.startswith("Model name:"):
            info["name"] = _value(stripped)
        elif stripped.startswith("Mfg name:"):
            info["mfg"] = _value(stripped)
        elif stripped.startswith("Backend status:"):
            info["status"] = _value(stripped)
        elif stripped.startswith("Backend version:"):
            info["version"] = _value(stripped)
        elif info["id"] is None and re.match(r"^Model:\s*\d+\s*$", stripped):
            info["id"] = int(_value(stripped))
    if info["id"] is None and info["name"]:
        # 老版本 rigctld 不报 id 时，用机型名反查 hamlib 机型表补上
        model = resolve(info["name"])
        if model:
            info["id"] = model["id"]
            info["status"] = info["status"] or status_name(model["status"])
    return info if (info["name"] or info["id"]) else None


def _probe_rigctld(host: str, port: int, timeout: float = 1.5) -> dict | None:
    import socket
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(b"\\dump_caps\n")
            chunks = []
            while True:
                try:
                    data = sock.recv(65536)
                except socket.timeout:
                    break
                if not data:
                    break
                chunks.append(data)
                if b"\n" in data and len(b"".join(chunks)) > 512:
                    break
            return _parse_dump_caps(b"".join(chunks).decode("utf-8", "replace"))
    except Exception:
        return None


def apply_to_config(cfg, value, model_list=None):
    """把 UI/表单传来的型号写进 configparser 对象。

    写入两处（这是“准确对应”的关键）：
      * `[HAMLIB] rig_model`  = hamlib 规范名（如 `IC-M710`）
      * `[INSTANCE_SETTINGS] instance_rigctl_model` = 数字 id（**rigctld -m 实际用这个**）

    返回 `(规范名 | None, 错误信息 | None)`。
    value 为空 → `(None, None)`，表示“不改”。
    """
    text = "" if value is None else str(value).strip()
    if not text:
        return None, None
    model = resolve(text, model_list)
    if not model:
        return None, (f"hamlib 机型表里找不到“{text}”；"
                      f"请从列表里选择，或勾选自定义型号后原样保存")
    if not cfg.has_section("HAMLIB"):
        cfg.add_section("HAMLIB")
    cfg.set("HAMLIB", "rig_model", model["name"])
    # 只有多实例部署（存在 [INSTANCE_SETTINGS]）才有 rigctld 的 instance_* 键
    if cfg.has_section("INSTANCE_SETTINGS"):
        cfg.set("INSTANCE_SETTINGS", "instance_rigctl_model", str(model["id"]))
    return model["name"], None


def cached_rigctld_model(host: str = "127.0.0.1", port: int = 4532) -> dict | None:
    """带缓存 + 后台刷新的 rigctld 机型查询（绝不阻塞调用线程）。

    IOLoop 线程上调用是安全的：超过 TTL 时返回上一次结果，并起一个后台线程刷新。
    """
    now = time.time()
    with _rigctld_lock:
        fresh = (now - _rigctld_cache["at"]) < _RIGCTLD_TTL
        if fresh or _rigctld_cache["refreshing"]:
            return _rigctld_cache["value"]
        _rigctld_cache["refreshing"] = True

    def _refresh():
        try:
            result = _probe_rigctld(host, port)
            with _rigctld_lock:
                _rigctld_cache.update(value=result, at=time.time())
        finally:
            with _rigctld_lock:
                _rigctld_cache["refreshing"] = False

    threading.Thread(target=_refresh, name="rigctld-caps-probe", daemon=True).start()
    return _rigctld_cache["value"]


def reset_cache():
    """测试/配置变更后清缓存。"""
    with _lock:
        _cache.update(models=None, fallback=False, error=None, loaded_at=0.0)
    with _rigctld_lock:
        _rigctld_cache.update(value=None, at=0.0, refreshing=False)


if __name__ == "__main__":                       # python3 rig_models.py 自检
    info = available()
    print(f"hamlib 机型数: {len(info['models'])}  fallback={info['fallback']}  error={info['error']}")
    for probe in ("30003", "IC-M710", "IC_M710", "FTDX10", "IC-7300", "不存在的东西", ""):
        print(f"  resolve({probe!r}) -> {describe(probe)}")
    print("  rigctld:", cached_rigctld_model())

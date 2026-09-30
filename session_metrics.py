"""会话遥测（Cloud Hub 前置能力之一）。

目的与 mrrc_modern 的同名模块一致：给 Hub 侧的容量决策提供真实数据（并发 Listener 数、
上行占用、发送/解码失败），而不是靠估计。实现刻意分成两层：

  - 本模块只做**纯逻辑**：计数器、快照组装、日志行格式化。不 import 本产品任何东西，
    因此可以被单独测试（dev_tools/test_session_metrics.py）。
  - 具体的"当前有几个 WS 连接"由 MRRC 脚本从它既有的连接列表读出后传进来 —— 遥测因此
    **不需要侵入 WebSocket 的 open/on_close**，也就不会影响连接生命周期。
"""
from __future__ import annotations

import threading
import time

_started_at = time.time()
_lock = threading.Lock()
_counters: dict[str, int] = {}


def bump(name: str, n: int = 1) -> None:
    """累加一个计数器（线程安全）。"""
    with _lock:
        _counters[name] = _counters.get(name, 0) + int(n)


def counters() -> dict:
    with _lock:
        return dict(_counters)


def uptime_s() -> int:
    return int(time.time() - _started_at)


def render(active: dict, extra: dict | None = None) -> dict:
    """组装遥测载荷。active 为 {类型: 连接数}，由调用方从连接列表读出。"""
    payload = {
        "uptime_s": uptime_s(),
        "active": {k: int(v) for k, v in sorted((active or {}).items())},
        "counters": counters(),
    }
    if extra:
        payload.update(extra)
    return payload


def format_line(payload: dict) -> str:
    """一行式日志，便于 grep 与长期归档（不做多行 JSON，避免日志被撑爆）。"""
    active = payload.get("active", {})
    parts = " ".join(f"{k}={v}" for k, v in active.items()) or "none"
    counters = payload.get("counters", {})
    count_txt = " ".join(f"{k}={v}" for k, v in sorted(counters.items())) or "none"
    return (f"📊 [metrics] uptime={payload.get('uptime_s', 0)}s "
            f"active: {parts} | counters: {count_txt}")

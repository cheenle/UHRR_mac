#!/usr/bin/env python3
"""Focused regression checks for ATR1000ProxyManager."""

import ast
import sys
import threading as real_threading
import unittest
from pathlib import Path
from types import SimpleNamespace


class FakeLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass


class FakeTimer:
    started = 0

    def __init__(self, *args, **kwargs):
        self.daemon = False

    def start(self):
        FakeTimer.started += 1


def load_atr1000_proxy_manager():
    source_path = Path(__file__).resolve().parents[1] / "MRRC"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ATR1000ProxyManager"
    )
    module = ast.Module(body=[class_node], type_ignores=[])
    ast.fix_missing_locations(module)

    globals_dict = {
        "threading": SimpleNamespace(Lock=real_threading.Lock, Timer=FakeTimer),
        "logger": FakeLogger(),
        "ATR1000HandlerClients": [],
    }
    exec(compile(module, str(source_path), "exec"), globals_dict)
    return globals_dict["ATR1000ProxyManager"]


class ATR1000ProxyManagerTests(unittest.TestCase):
    def test_read_loop_exits_when_peer_closes_unix_socket(self):
        manager_cls = load_atr1000_proxy_manager()
        manager_cls._instance = None
        manager = manager_cls()

        class ClosedSocket:
            recv_calls = 0

            def recv(self, size):
                self.recv_calls += 1
                return b""

        closed_socket = ClosedSocket()
        manager.running = True
        manager.unix_socket = closed_socket
        manager._connect = lambda: None
        manager._reconnect_delay = 0.5
        FakeTimer.started = 0
        select_calls = 0

        def fake_select(*args):
            nonlocal select_calls
            select_calls += 1
            if select_calls > 1:
                raise KeyboardInterrupt("read loop spun after peer close")
            return [closed_socket], [], []

        original_select = sys.modules.get("select")
        sys.modules["select"] = SimpleNamespace(select=fake_select)
        try:
            manager._read_loop()
        finally:
            if original_select is None:
                del sys.modules["select"]
            else:
                sys.modules["select"] = original_select

        self.assertEqual(closed_socket.recv_calls, 1)
        self.assertEqual(FakeTimer.started, 1)


if __name__ == "__main__":
    unittest.main()

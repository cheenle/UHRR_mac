#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""antenna_sweep 引擎单测 — 全 mock 回调，不碰硬件"""
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import antenna_sweep as sw


class FakeRig:
    """模拟电台+ATR 代理：记录全部动作，电表返回固定功率/SWR"""
    def __init__(self, swr=1.5, power=25.0):
        self.actions = []
        self.swr = swr
        self.power = power
        self.keyed = False

    def set_freq(self, hz):
        self.actions.append(("freq", hz))
        return True

    def ptt(self, on):
        self.actions.append(("ptt", on))
        self.keyed = on
        return True

    def tone(self, on):
        self.actions.append(("tone", on))

    def get_meter(self):
        if not self.keyed:
            return {"power": 0, "swr": 0}
        return {"power": self.power, "swr": self.swr}

    def proxy_cmd(self, cmd):
        self.actions.append(("proxy", cmd))
        return True


def run_engine(rig, tmpdir, bands=("30m",), step=25, dwell=0.5):
    eng = sw.AntennaSweepEngine(
        set_freq=rig.set_freq, ptt=rig.ptt, tone=rig.tone,
        get_meter=rig.get_meter, proxy_cmd=rig.proxy_cmd,
        results_dir=tmpdir, logger=lambda m: None)
    eng.start(bands=list(bands), step_khz=step, dwell_s=dwell, settle_s=0.2, note="test")
    for _ in range(600):
        if not eng.status()["running"]:
            break
        threading.Event().wait(0.05)
    return eng


class TestSweepEngine(unittest.TestCase):
    def test_full_sweep_30m(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rig = FakeRig(swr=1.37)
            eng = run_engine(rig, tmpdir)
            st = eng.status()
            self.assertEqual(st["phase"], "done", st.get("error"))
            # 30m: 10100..10150 step 25 -> 10100,10125,10150 = 3 点
            self.assertEqual(st["points_done"], 3)
            self.assertEqual(len(st["points"]), 3)
            self.assertAlmostEqual(st["points"][0]["swr"], 1.37)
            self.assertEqual(st["points"][0]["freq_khz"], 10100)
            # 学习被关闭又恢复
            proxy_cmds = [a[1] for a in rig.actions if a[0] == "proxy"]
            self.assertIn({"action": "set_learning", "enabled": False}, proxy_cmds)
            self.assertIn({"action": "set_autotune", "enabled": False}, proxy_cmds)
            self.assertIn({"action": "set_relay", "sw": 0, "ind": 0, "cap": 0}, proxy_cmds)
            self.assertIn({"action": "set_learning", "enabled": True}, proxy_cmds)
            self.assertIn({"action": "set_autotune", "enabled": True}, proxy_cmds)
            # 每点都发了 no_tune 的 set_freq
            no_tune = [c for c in proxy_cmds if c.get("action") == "set_freq" and c.get("no_tune")]
            self.assertEqual(len(no_tune), 3)
            # PTT 成对出现且最终为释放
            ptts = [a[1] for a in rig.actions if a[0] == "ptt"]
            self.assertEqual(ptts, [True, False] * 3)
            # 结果文件落盘
            self.assertTrue(st["result_file"] and os.path.exists(st["result_file"]))
            self.assertEqual(len(eng.list_results()), 1)
            # 结束时 tone 关闭
            self.assertEqual(rig.actions[-1][0], "proxy")  # 恢复 set_freq
            self.assertIn(("tone", False), rig.actions)

    def test_abort_releases_ptt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rig = FakeRig()
            eng = sw.AntennaSweepEngine(
                set_freq=rig.set_freq, ptt=rig.ptt, tone=rig.tone,
                get_meter=rig.get_meter, proxy_cmd=rig.proxy_cmd,
                results_dir=tmpdir, logger=lambda m: None)
            eng.start(bands=["40m"], step_khz=10, dwell_s=5, settle_s=0.2)
            threading.Event().wait(1.0)
            eng.stop()
            for _ in range(200):
                if not eng.status()["running"]:
                    break
                threading.Event().wait(0.05)
            st = eng.status()
            self.assertEqual(st["phase"], "aborted")
            self.assertFalse(rig.keyed)  # PTT 必须已释放
            proxy_cmds = [a[1] for a in rig.actions if a[0] == "proxy"]
            self.assertIn({"action": "set_learning", "enabled": True}, proxy_cmds)
            self.assertIn({"action": "set_autotune", "enabled": True}, proxy_cmds)

    def test_no_carrier_aborts(self):
        """载波没出去（电表恒 0）→ 连续 5 空点后中止"""
        with tempfile.TemporaryDirectory() as tmpdir:
            rig = FakeRig()
            rig.keyed = False
            rig.get_meter = lambda: {"power": 0, "swr": 0}
            eng = run_engine(rig, tmpdir, bands=("40m",), step=25, dwell=0.5)
            st = eng.status()
            self.assertEqual(st["phase"], "error")
            self.assertIn("无载波", st["error"])
            self.assertEqual(st["points_done"], 5)

    def test_ptt_failure_aborts_and_releases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rig = FakeRig()
            rig.ptt = lambda on: False  # 键控全部失败
            eng = run_engine(rig, tmpdir, bands=("30m",), step=50)
            st = eng.status()
            self.assertEqual(st["phase"], "error")
            self.assertIn("PTT", st["error"])

    def test_bad_band_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rig = FakeRig()
            eng = sw.AntennaSweepEngine(rig.set_freq, rig.ptt, rig.tone,
                                        rig.get_meter, rig.proxy_cmd, results_dir=tmpdir)
            with self.assertRaises(sw.SweepError):
                eng.start(bands=["60m"])

    def test_double_start_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rig = FakeRig()
            eng = sw.AntennaSweepEngine(rig.set_freq, rig.ptt, rig.tone,
                                        rig.get_meter, rig.proxy_cmd, results_dir=tmpdir,
                                        logger=lambda m: None)
            eng.start(bands=["40m"], dwell_s=5)
            with self.assertRaises(sw.SweepError):
                eng.start(bands=["30m"])
            eng.stop()
            for _ in range(200):
                if not eng.status()["running"]:
                    break
                threading.Event().wait(0.05)

    def test_load_result_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rig = FakeRig()
            eng = sw.AntennaSweepEngine(rig.set_freq, rig.ptt, rig.tone,
                                        rig.get_meter, rig.proxy_cmd, results_dir=tmpdir)
            with self.assertRaises(sw.SweepError):
                eng.load_result("../etc/passwd")
            with self.assertRaises(sw.SweepError):
                eng.load_result("nojson")

    def test_custom_freqs(self):
        """freqs_khz 自定义频点列表（复测掉读点）：跳过 bands，逐点扫描"""
        with tempfile.TemporaryDirectory() as tmpdir:
            rig2 = FakeRig(swr=2.22)
            eng2 = sw.AntennaSweepEngine(rig2.set_freq, rig2.ptt, rig2.tone,
                                         rig2.get_meter, rig2.proxy_cmd,
                                         results_dir=tmpdir, logger=lambda m: None)
            eng2.start(freqs_khz=[7130, 14090.4, 29300], dwell_s=0.5, settle_s=0.2)
            for _ in range(400):
                if not eng2.status()["running"]:
                    break
                threading.Event().wait(0.05)
            st = eng2.status()
            self.assertEqual(st["phase"], "done", st.get("error"))
            freqs = [p["freq_khz"] for p in st["points"]]
            self.assertEqual(freqs, [7130, 14090, 29300])
            bands = [p["band"] for p in st["points"]]
            self.assertEqual(bands, ["40m", "20m", "10m"])
            # 越界频点拒绝
            with self.assertRaises(sw.SweepError):
                eng2.start(freqs_khz=[100])


if __name__ == "__main__":
    unittest.main()

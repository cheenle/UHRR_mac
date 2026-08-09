#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATR-1000 SWR>2 自动完整调谐守卫单元测试
运行: venv/bin/python dev_tools/test_swr_retune.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import atr1000_proxy as ap


class FakeClock:
    now = 1000.0
    @classmethod
    def time(cls):
        return cls.now


class FakeATR:
    def __init__(self):
        self.tune_calls = []  # [(mode, ts), ...]
    def start_tune(self, mode=2):
        self.tune_calls.append((mode, FakeClock.now))


def _reset(freq=21074000, swr=1.0, power=0, tuning=False, relay_changed=0):
    ap._swr_high_since = 0
    ap._last_retune_time = 0
    ap._retune_fail_count.clear()
    with ap.cache_lock:
        ap.cache["freq"] = freq
        ap.cache["swr"] = swr
        ap.cache["power"] = power
        ap.cache["tuning"] = tuning
        ap.cache["tuning_started_at"] = 0
        ap.cache["tuning_relay_stable_since"] = 0
        ap.cache["relay_changed_at"] = relay_changed


def _feed(fake_atr, swr, power, n=1, dt=0.2):
    for _ in range(n):
        FakeClock.now += dt
        ap.check_swr_retune(fake_atr, power, swr)


def test_triggers_once_after_debounce():
    _reset(swr=2.5, power=40)
    fake = FakeATR()
    _feed(fake, 2.5, 40, n=6, dt=0.2)   # 距首个高SWR样本 1.0s，未满 1.5s
    assert fake.tune_calls == [], f"不应提前触发: {fake.tune_calls}"
    _feed(fake, 2.5, 40, n=3, dt=0.2)   # 距首个样本 1.6s ≥ 1.5s → 触发
    assert len(fake.tune_calls) == 1, f"应恰好触发一次: {fake.tune_calls}"
    assert fake.tune_calls[0][0] == 2, "应为完整调谐 mode=2"
    print("✓ 去抖后恰好触发一次完整调谐 (mode=2)")


def test_cooldown_blocks_repeat():
    _reset(swr=2.5, power=40)
    fake = FakeATR()
    _feed(fake, 2.5, 40, n=9, dt=0.2)   # 触发第一次（距首个样本 1.6s）
    assert len(fake.tune_calls) == 1
    with ap.cache_lock:
        ap.cache["tuning"] = False       # 模拟调谐完成，进入 30s 冷却期
    _feed(fake, 2.5, 40, n=10, dt=0.2)  # 冷却期内继续高 SWR
    assert len(fake.tune_calls) == 1, "冷却期内不应再次触发"
    print("✓ 冷却期内不重复触发")


def test_gives_up_after_max_fails():
    _reset(swr=2.5, power=40)
    fake = FakeATR()
    for i in range(3):
        FakeClock.now += 31            # 过 30s 冷却
        ap._swr_high_since = 0         # 模拟 SWR 回落再升高
        with ap.cache_lock:
            ap.cache["tuning"] = False          # 模拟上次调谐已完成
            ap.cache["tuning_started_at"] = 0
            ap.cache["tuning_relay_stable_since"] = 0
        _feed(fake, 2.5, 40, n=9, dt=0.2)
        assert len(fake.tune_calls) == i + 1, f"第{i+1}次应触发"
    # 第 4 次连续段：失败计数已达上限 → 不再触发
    FakeClock.now += 31
    ap._swr_high_since = 0
    with ap.cache_lock:
        ap.cache["tuning"] = False
        ap.cache["tuning_started_at"] = 0
        ap.cache["tuning_relay_stable_since"] = 0
    _feed(fake, 2.5, 40, n=9, dt=0.2)
    assert len(fake.tune_calls) == 3, "3 次失败后不应再触发"
    print("✓ 3 次失败后放弃自动调谐")


def test_skips_when_not_conditions():
    _reset(swr=2.5, power=5)           # 功率不足
    fake = FakeATR()
    _feed(fake, 2.5, 5, n=8, dt=0.2)
    assert fake.tune_calls == [], "功率不足不应触发"

    _reset(swr=1.5, power=40)          # SWR 达标
    fake = FakeATR()
    _feed(fake, 1.5, 40, n=8, dt=0.2)
    assert fake.tune_calls == [], "SWR≤2 不应触发"

    _reset(swr=2.5, power=40, tuning=True)  # 调谐中
    fake = FakeATR()
    _feed(fake, 2.5, 40, n=8, dt=0.2)
    assert fake.tune_calls == [], "调谐中不应触发"

    _reset(swr=2.5, power=40, relay_changed=FakeClock.now - 0.2)  # 继电器忽略窗口
    fake = FakeATR()
    _feed(fake, 2.5, 40, n=8, dt=0.2)
    assert fake.tune_calls == [], "继电器变化 1s 内不应触发"
    print("✓ 功率不足/SWR达标/调谐中/继电器忽略窗口均不触发")


def main():
    ap.time.time = FakeClock.time      # 打桩模块级 time.time
    tests = [test_triggers_once_after_debounce, test_cooldown_blocks_repeat,
             test_gives_up_after_max_fails, test_skips_when_not_conditions]
    for t in tests:
        FakeClock.now = 1000.0
        t()
    print(f"\n全部 {len(tests)} 个测试通过")


if __name__ == "__main__":
    main()

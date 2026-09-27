#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATR-1000 tune 确认学习（V5.9.0）单元测试

验证：完整调谐结束后，若 settled SWR 较调谐前改善且 ≤LEARN_SWR_MAX，
设备选定的最终继电器参数被 force_update 写库——不受 3W 学习功率门限制。
运行: venv/bin/python dev_tools/test_tune_confirm.py
"""
import os
import sys
import tempfile

# 存储重定向到临时目录（必须在 import atr1000_proxy 之前设置）
_tmp = tempfile.mkdtemp()
os.environ["MRRC_ATR1000_STORE"] = os.path.join(_tmp, "tuner.json")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import atr1000_proxy as ap
from atr1000_tuner import get_storage


class FakeClock:
    now = 1000.0
    @classmethod
    def time(cls):
        return cls.now


def _reset(freq=3850000, pre_swr=5.49):
    ap._pre_tune_swr = 0.0
    ap._pre_tune_freq = 0
    ap._tune_confirm_deadline = 0.0
    ap._was_tuning = False
    with ap.cache_lock:
        ap.cache["freq"] = freq
        ap.cache["swr"] = pre_swr
        ap.cache["power"] = 0
        ap.cache["tuning"] = False
        ap.cache["sw"], ap.cache["ind"], ap.cache["cap"] = 0, 31, 127
    get_storage().clear()


def _meter(power, swr_raw, sw=0, ind=31, cap=127, dt=0.15, tuning=None):
    """模拟一个 METER 包解析后的确认捕获（与生产代码一样在 cache_lock 内调用）"""
    FakeClock.now += dt
    with ap.cache_lock:
        if tuning is not None:
            ap.cache["tuning"] = tuning
        ap.cache["sw"], ap.cache["ind"], ap.cache["cap"] = sw, ind, cap
        ap.cache["power"] = power
        # 与 _parse_data 相同的 SWR 归一化
        if swr_raw >= 100:
            ap.cache["swr"] = swr_raw / 100.0
        elif swr_raw > 0:
            ap.cache["swr"] = float(swr_raw)
        elif power > 0:
            ap.cache["swr"] = 1.0
        return ap._tune_confirm_capture(power, ap.cache["swr"], swr_raw)


def _do_learn(capture):
    """模拟生产代码锁外写库"""
    return get_storage().learn(freq=capture["freq"], sw=capture["sw"],
                               ind=capture["ind"], cap=capture["cap"],
                               swr=capture["swr"], force_update=True)


def test_confirm_learn_after_tune():
    """调谐完成后 settled SWR 改善 → 确认学习入库（2W 弱载波也收）"""
    _reset()
    ap._tune_confirm_arm(3850000, 5.49)   # 调谐前 SWR=5.49
    with ap.cache_lock:
        ap.cache["tuning"] = True
    # 调谐期间的 METER：不产生确认
    assert _meter(2, 549, tuning=True) is None
    # 调谐完成沿 + 有效改善样本（2W、SWR=1.71）→ 确认
    cap = _meter(2, 171, tuning=False)
    assert cap is not None, "调谐后改善样本应触发确认"
    assert cap["swr"] == 1.71 and cap["pre_swr"] == 5.49
    assert (cap["sw"], cap["ind"], cap["cap"]) == (0, 31, 127)
    assert _do_learn(cap)
    rec = get_storage().find_best(3850000)
    assert rec and rec["ind"] == 31 and rec["cap"] == 127, f"记录应入库: {rec}"
    assert abs(rec["swr_avg"] - 1.71) < 1e-6
    print("✓ 调谐后改善样本确认入库（2W 弱载波，绕过 3W 功率门）")


def test_fake_swr10_rejected():
    """swr_raw=0 的伪 1.0 拒收，窗口保留等真值"""
    _reset()
    ap._tune_confirm_arm(3850000, 5.49)
    with ap.cache_lock:
        ap.cache["tuning"] = True
    _meter(2, 549, tuning=True)
    # 完成沿后先来一个 swr_raw=0 → cache swr=1.0（伪完美匹配）→ 必须拒收
    assert _meter(2, 0, tuning=False) is None, "swr_raw=0 的伪 1.0 不应确认"
    # 窗口仍在，随后真实 1.5 确认成功
    cap = _meter(2, 150)
    assert cap is not None and cap["swr"] == 1.5
    print("✓ swr_raw=0 伪 1.0 拒收，窗口内后续真值正常确认")


def test_no_improvement_keeps_waiting():
    """未改善不关窗；窗口内出现改善样本仍确认"""
    _reset()
    ap._tune_confirm_arm(3850000, 5.49)
    with ap.cache_lock:
        cache_tuning = ap.cache
        cache_tuning["tuning"] = True
    _meter(2, 549, tuning=True)
    assert _meter(2, 549, tuning=False) is None   # 5.49 没改善
    assert _meter(2, 200) is None                 # 2.00 改善但 >1.8 学习门
    cap = _meter(2, 171)                          # 1.71 改善且 ≤1.8 → 确认
    assert cap is not None and cap["swr"] == 1.71
    print("✓ 未改善/超学习门样本不关窗，改善到 ≤1.8 才确认")


def test_freq_changed_invalidates():
    """确认窗口内频率变了 → 作废"""
    _reset()
    ap._tune_confirm_arm(3850000, 5.49)
    with ap.cache_lock:
        ap.cache["tuning"] = True
    _meter(2, 549, tuning=True)
    with ap.cache_lock:
        ap.cache["freq"] = 7060000
    assert _meter(2, 171, tuning=False) is None, "频率变化后不应确认"
    # 窗口已关闭，切回来也不再确认
    with ap.cache_lock:
        ap.cache["freq"] = 3850000
    assert _meter(2, 150) is None
    print("✓ 频率变化作废确认窗口")


def test_window_expiry():
    """超过确认窗口 → 不再确认"""
    _reset()
    ap._tune_confirm_arm(3850000, 5.49)
    with ap.cache_lock:
        ap.cache["tuning"] = True
    _meter(2, 549, tuning=True)
    assert _meter(0, 0, tuning=False) is None     # 完成沿，无载波样本
    FakeClock.now += ap.TUNE_CONFIRM_WINDOW + 1   # 窗口过期
    assert _meter(2, 150) is None, "窗口过期后不应确认"
    print("✓ 确认窗口过期作废")


def test_bypass_relay_rejected():
    """直通状态（ind=0,cap=0）不确认"""
    _reset()
    ap._tune_confirm_arm(3850000, 5.49)
    with ap.cache_lock:
        ap.cache["tuning"] = True
    _meter(2, 549, tuning=True)
    assert _meter(2, 120, sw=0, ind=0, cap=0, tuning=False) is None
    print("✓ 直通继电器参数不确认")


def test_no_arm_no_confirm():
    """未经武装（如代理重启后 tuning 标志残留翻转）不确认"""
    _reset()
    # 没有 arm：pre_swr=0，完成沿不开窗
    with ap.cache_lock:
        ap.cache["tuning"] = True
    _meter(2, 549, tuning=True)
    assert _meter(2, 120, tuning=False) is None
    assert get_storage().find_best(3850000) is None
    print("✓ 未武装的调谐翻转不确认")


def main():
    ap.time.time = FakeClock.time      # 打桩模块级 time.time
    tests = [test_confirm_learn_after_tune, test_fake_swr10_rejected,
             test_no_improvement_keeps_waiting, test_freq_changed_invalidates,
             test_window_expiry, test_bypass_relay_rejected, test_no_arm_no_confirm]
    for t in tests:
        FakeClock.now = 1000.0
        t()
    print(f"\n全部 {len(tests)} 个测试通过")


if __name__ == "__main__":
    main()

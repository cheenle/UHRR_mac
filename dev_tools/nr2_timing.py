#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WDSP fexchange0 时序探针：
  1) 实时节拍（模拟生产：20ms 读 960 → 3~4 个 256 块）下 error=-2 的比例
  2) 满速灌入时的最大吞吐（DSP 线程能否跟上）
  3) error=-2 时 wrapper 用原始输入顶替 → 拼接失真量化
"""
import ctypes, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode, _wdsp

SR, BS = 48000, 256


def make_proc(nr2=True, agc=WDSPAGCMode.MED, panel=0.06):
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=False,
                      enable_nb=False, enable_anf=False, agc_mode=agc)
    _wdsp.SetRXAPanelGain1(ctypes.c_int(0), ctypes.c_double(panel))
    if nr2:
        _wdsp.SetRXAEMNRRun(ctypes.c_int(0), ctypes.c_int(1))
        _wdsp.SetRXAEMNRgainMethod(ctypes.c_int(0), ctypes.c_int(0))
        _wdsp.SetRXAEMNRnpeMethod(ctypes.c_int(0), ctypes.c_int(0))
        _wdsp.SetRXAEMNRaeRun(ctypes.c_int(0), ctypes.c_int(1))
        _wdsp.SetRXAEMNRPosition(ctypes.c_int(0), ctypes.c_int(0))
    else:
        _wdsp.SetRXAEMNRRun(ctypes.c_int(0), ctypes.c_int(0))
    p.set_bandpass(300.0, 2700.0)
    return p


def exch(p, blk):
    e = ctypes.c_int(0)
    p._in_buffer[0::2] = blk
    p._in_buffer[1::2] = 0.0
    _wdsp.fexchange0(ctypes.c_int(0),
                     p._in_buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                     p._out_buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                     ctypes.byref(e))
    return e.value, p._out_buffer[0::2].copy()


def realtime_test(seconds=6.0, nr2=True):
    """生产节拍：每次 960 样本（20ms）分 3~4 块推入"""
    p = make_proc(nr2=nr2)
    t = np.arange(int(SR * seconds)) / SR
    sig = 0.2 * np.sin(2 * np.pi * 700 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))
    t0 = time.monotonic()
    err_counts = {}
    n_blocks = 0
    out_nr2_fallback = 0
    lat = []
    i = 0
    while i < len(sig) - BS:
        for _ in range(4):                        # 20ms 一批 = 960 样本
            if i >= len(sig) - BS:
                break
            e, _ = exch(p, sig[i:i + BS])
            err_counts[e] = err_counts.get(e, 0) + 1
            n_blocks += 1
            if e == -2:
                out_nr2_fallback += 1
            i += BS
        target = t0 + i / SR
        d = target - time.monotonic()
        if d > 0:
            time.sleep(d)
    elapsed = time.monotonic() - t0
    p.close()
    return err_counts, n_blocks, elapsed


def throughput_test(seconds_audio=30.0, nr2=True):
    """满速推入，量 DSP 线程吞吐"""
    p = make_proc(nr2=nr2)
    nblk = int(SR * seconds_audio / BS)
    blk = (0.2 * np.sin(2 * np.pi * 700 * np.arange(BS) / SR))
    t0 = time.monotonic()
    err0 = err2 = 0
    for _ in range(nblk):
        e, _ = exch(p, blk)
        if e == 0:
            err0 += 1
        elif e == -2:
            err2 += 1
    dt = time.monotonic() - t0
    p.close()
    return err0, err2, dt, seconds_audio / dt


print("=== 1) 实时节拍（生产模式）===")
for nr2 in (False, True):
    for trial in range(2):
        ec, nb, el = realtime_test(6.0, nr2=nr2)
        miss = ec.get(-2, 0)
        print(f"  NR2={'on ' if nr2 else 'off'} trial{trial}: blocks={nb} errs={ec} "
              f"缺块率={miss/nb*100:.1f}%  实测耗时={el:.2f}s/6.00s音频")

print("\n=== 2) 满速吞吐（DSP 线程能力上限）===")
for nr2 in (False, True):
    e0, e2, dt, ratio = throughput_test(60.0, nr2=nr2)
    print(f"  NR2={'on ' if nr2 else 'off'}: ok={e0} starved={e2} "
          f"处理 60s 音频耗时 {dt:.2f}s → {ratio:.1f}x 实时")

print("\n=== 3) 判定 ===")
print("  若实时模式下缺块率≈0，则生产不受 fexchange0 饥饿影响；")
print("  否则 wrapper 的 -2→返回原始输入 会造成按块拼接的失真。")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1：单音穿透增益（走生产 wrapper 路径：WDSPProcessor + set_bandpass + set_nr2_level）。

验收：level 2 时 1 kHz 净增益应 >= -18 dB（修复前为 -37 dB）。
等级阶梯（修复后）应随 nr2_level 递减（主轴 = 每 bin 最大衰减）。
"""
import ctypes, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode, _wdsp

SR, BS = 48000, 256


def tone_gain(level, seconds=2.0, amp=0.2, agc_off=True):
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=True,
                      enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED)
    if agc_off:                     # 关掉 AGC 的补偿增益，才能看到 NR2 本身对语音的"吃掉量"
        _wdsp.SetRXAAGCMode(ctypes.c_int(0), ctypes.c_int(0))
        _wdsp.SetRXAAGCFixed(ctypes.c_int(0), ctypes.c_double(0.0))
        _wdsp.SetRXAPanelGain1(ctypes.c_int(0), ctypes.c_double(1.0))
    p.set_bandpass(300.0, 2700.0)
    p.set_nr2_level(level)
    n = int(SR * seconds)
    t = np.arange(n) / SR
    x = amp * np.sin(2 * np.pi * 1000.0 * t)
    out = np.zeros(n)
    t0 = time.monotonic()
    for b in range(n // BS):
        blk = x[b * BS:(b + 1) * BS]
        out[b * BS:(b + 1) * BS] = p.process(blk.astype(np.float64))
        d = t0 + (b + 1) * BS / SR - time.monotonic()
        if d > 0:
            time.sleep(d)
    p.close()
    seg = out[n // 2:]
    X = np.fft.rfft(seg * np.hanning(len(seg)))
    fr = np.fft.rfftfreq(len(seg), 1 / SR)
    k = int(np.argmin(abs(fr - 1000)))
    a = 2 * abs(X[k]) / np.sum(np.hanning(len(seg)))
    return 20 * np.log10(max(a, 1e-12) / amp)


if __name__ == "__main__":
    print(f"{'level':>6s} {'1kHz 净增益(dB)':>16s}")
    for lv in (0, 1, 2, 3, 4):
        print(f"{lv:6d} {tone_gain(lv):16.1f}")

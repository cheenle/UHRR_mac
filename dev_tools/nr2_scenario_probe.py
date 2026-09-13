#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单进程单场景：复现生产初始化/更新路径。用法: nr2_scenario_probe.py <A|B|C|D>"""
import ctypes, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode, _wdsp
SR, BS = 48000, 256
sc = sys.argv[1]
def probe(p):
    t = np.arange(SR) / SR
    x = 0.2 * np.sin(2 * np.pi * 1000 * t)
    out = np.zeros(len(x)); t0 = time.monotonic()
    for b in range(len(x) // BS):
        blk = x[b * BS:(b + 1) * BS]
        p._in_buffer[0::2] = blk; p._in_buffer[1::2] = 0.0
        e = ctypes.c_int(0)
        _wdsp.fexchange0(ctypes.c_int(0), p._in_buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                         p._out_buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), ctypes.byref(e))
        out[b * BS:(b + 1) * BS] = blk if e.value == -2 else p._out_buffer[0::2]
        d = t0 + (b + 1) * BS / SR - time.monotonic()
        if d > 0: time.sleep(d)
    seg = out[SR // 2:]
    X = np.fft.rfft(seg * np.hanning(len(seg))); fr = np.fft.rfftfreq(len(seg), 1 / SR)
    k = np.argmin(abs(fr - 1000)); amp = 2 * abs(X[k]) / np.sum(np.hanning(len(seg)))
    return 20 * np.log10(max(amp, 1e-12) / 0.2)
if sc == "A":      # nr2_enabled=False 初始化
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=False, agc_mode=WDSPAGCMode.MED)
    p.set_bandpass(300.0, 2700.0)
elif sc == "B":    # nr2_enabled=True + level 2（生产）
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=True, agc_mode=WDSPAGCMode.MED)
    p.set_bandpass(300.0, 2700.0); p.set_nr2_level(2)
elif sc == "C":    # 运行中关掉 NR2（level 0）后 set_bandpass（同频）
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=True, agc_mode=WDSPAGCMode.MED)
    p.set_bandpass(300.0, 2700.0); p.set_nr2_level(2)
    p.set_nr2_level(0); p.set_bandpass(300.0, 2700.0)
elif sc == "D":    # 关掉 NR2 后再改带通频率
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=True, agc_mode=WDSPAGCMode.MED)
    p.set_bandpass(300.0, 2700.0); p.set_nr2_level(2)
    p.set_nr2_level(0); p.set_bandpass(350.0, 2600.0)
elif sc == "E":    # 只开 NB（NR2 关）→ 验证 RXAbp1Check 的 gain=2 分支能否救回
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=False, enable_nb=True, agc_mode=WDSPAGCMode.MED)
    p.set_bandpass(300.0, 2700.0)
g = probe(p)
print(f"场景{sc}: 1kHz增益={g:+8.1f} dB   {'✅ 音频正常' if g > -20 else '❌ 静音/无输出'}")
p.close()

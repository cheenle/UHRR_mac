#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单进程单用例：验证 bp1 gain=1.0 是否真的静音。
用法: python3 nr2_bp1_probe.py <case>
  case: off | bp_g1 | emnr_bp | bp_only
"""
import ctypes, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wdsp_wrapper as W
if os.environ.get("WDSP_LIB"):
    W._wdsp = ctypes.CDLL(os.environ["WDSP_LIB"])
_wdsp = W._wdsp
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode

SR, BS = 48000, 256
case = sys.argv[1]
p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=False,
                  enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED)
_wdsp.SetRXAAGCMode(ctypes.c_int(0), ctypes.c_int(0))
_wdsp.SetRXAAGCFixed(ctypes.c_int(0), ctypes.c_double(0.0))
_wdsp.SetRXAPanelGain1(ctypes.c_int(0), ctypes.c_double(1.0))

if case == "off":
    pass
elif case == "bp_g1":
    p.set_bandpass(300.0, 2700.0)                       # bp1 run=1, gain 仍为 1.0
elif case == "emnr_bp":
    _wdsp.SetRXAEMNRRun(ctypes.c_int(0), ctypes.c_int(1))   # → RXAbp1Check 置 gain=2.0
    p.set_bandpass(300.0, 2700.0)
elif case == "bp_only":
    _wdsp.SetRXABandpassRun(ctypes.c_int(0), ctypes.c_int(1))
    _wdsp.SetRXABandpassFreqs(ctypes.c_int(0), ctypes.c_double(300.0), ctypes.c_double(2700.0))

t = np.arange(SR * 2) / SR
x = 0.2 * np.sin(2 * np.pi * 1000 * t)
n = len(x) // BS
out = np.zeros(n * BS)
t0 = time.monotonic()
for b in range(n):
    blk = x[b * BS:(b + 1) * BS]
    p._in_buffer[0::2] = blk
    p._in_buffer[1::2] = 0.0
    e = ctypes.c_int(0)
    _wdsp.fexchange0(ctypes.c_int(0),
                     p._in_buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                     p._out_buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                     ctypes.byref(e))
    out[b * BS:(b + 1) * BS] = blk if e.value == -2 else p._out_buffer[0::2]
    d = t0 + (b + 1) * BS / SR - time.monotonic()
    if d > 0:
        time.sleep(d)
seg = out[SR:]
X = np.fft.rfft(seg * np.hanning(len(seg)))
fr = np.fft.rfftfreq(len(seg), 1 / SR)
k = np.argmin(abs(fr - 1000))
amp = 2 * abs(X[k]) / np.sum(np.hanning(len(seg)))
print(f"case={case:8s} 输出1kHz幅度={amp:.5f}  相对输入={20*np.log10(max(amp,1e-12)/0.2):+7.2f} dB")
p.close()

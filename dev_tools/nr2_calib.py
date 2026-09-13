#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WDSP RXA 增益链定标：单音 1kHz，逐环节开关，测量输入→输出增益。"""
import ctypes, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode, WDSPMeterType, _wdsp

SR, BS = 48000, 256
AMP = 0.1

def run(agc_mode, panel, nr2, bp=True, mode=WDSPMode.USB):
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=mode, enable_nr2=False,
                      enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED)
    _wdsp.SetRXAAGCMode(ctypes.c_int(0), ctypes.c_int(agc_mode))
    if agc_mode == 0:
        _wdsp.SetRXAAGCFixed(ctypes.c_int(0), ctypes.c_double(1.0))
    _wdsp.SetRXAPanelGain1(ctypes.c_int(0), ctypes.c_double(panel))
    _wdsp.SetRXAEMNRRun(ctypes.c_int(0), ctypes.c_int(1 if nr2 else 0))
    if bp:
        p.set_bandpass(300.0, 2700.0)
    else:
        _wdsp.SetRXABandpassRun(ctypes.c_int(0), ctypes.c_int(0))
    n = SR * 2
    t = np.arange(n) / SR
    x = AMP * np.sin(2 * np.pi * 1000.0 * t)
    pad = np.concatenate([np.zeros(BS * 80), x])
    out = np.zeros(len(pad))
    errs = {}
    for i in range(0, len(pad) - BS + 1, BS):
        blk = pad[i:i + BS].astype(np.float64)
        e = ctypes.c_int(0)
        p._in_buffer[0::2] = blk
        p._in_buffer[1::2] = 0.0
        _wdsp.fexchange0(ctypes.c_int(0),
                         p._in_buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                         p._out_buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                         ctypes.byref(e))
        errs[e.value] = errs.get(e.value, 0) + 1
        out[i:i + BS] = p._out_buffer[0::2]
    tail = out[len(pad)//2:]
    rms = np.sqrt(np.mean(tail**2))
    pk = np.max(np.abs(tail))
    agc_m = [p.get_meter(t) for t in (WDSPMeterType.AGC_GAIN, WDSPMeterType.AGC_PK, WDSPMeterType.S_PK, WDSPMeterType.S_AV)]
    p.close()
    return rms, pk, errs, agc_m

print(f"{'agc':>4s} {'panel':>6s} {'nr2':>4s} {'bp':>3s} | {'out_rms':>9s} {'out_pk':>8s} {'gain(dB)':>9s} | meters(AGC_gain,AGC_pk,S_pk,S_av)")
for agc in (0, 3):
    for panel in (0.06, 1.0, 4.0):
        for nr2 in (False, True):
            rms, pk, errs, m = run(agc, panel, nr2)
            g = 20*np.log10(max(rms, 1e-12) / (AMP/np.sqrt(2)))
            print(f"{agc:4d} {panel:6.2f} {str(nr2):>4s} {str(True):>3s} | {rms:9.5f} {pk:8.5f} {g:9.2f} | "
                  f"{m[0]:.4g} {m[1]:.4g} {m[2]:.4g} {m[3]:.4g}  errs={errs}")
print()
rms, pk, errs, m = run(3, 0.06, False, bp=False)
print(f"无带通: rms={rms:.5f} pk={pk:.5f} errs={errs}")
rms, pk, errs, m = run(0, 0.06, False, bp=False)
print(f"无带通+AGCoff: rms={rms:.5f} pk={pk:.5f} errs={errs}")

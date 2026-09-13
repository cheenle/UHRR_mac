#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A9：生成 NR2 新旧对照试听 WAV（同一段"语音+噪声"）到 dev_tools/nr2_out/。

- A_nr2_off.wav          : NR2 关闭（参考）
- B_nr2_L2_new.wav       : 新默认（level 2：max_atten -12dB / MMSE / AGC 封顶 +20dB / panel 0.35）
- C_nr2_L2_legacy.wav    : 旧行为复现（npe=0 OSMS, max_atten=0 不限制, panel 0.06, AGC 顶 +80dB）
- D_nr2_L1_new.wav       : 新 level 1（max_atten -6dB，最保守）
"""
import ctypes, os, sys, time, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode, WDSPNR2Level, _wdsp

SR, BS = 48000, 256
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nr2_out")


def load_speech(path, peak=0.25):
    with wave.open(path, "rb") as w:
        d = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
        r = w.getframerate()
    n = int(len(d) * SR / r)
    X = np.fft.rfft(d); Y = np.zeros(n // 2 + 1, complex)
    k = min(len(X), len(Y)); Y[:k] = X[:k]
    d = np.fft.irfft(Y, n) * (n / len(d))
    return d / np.max(np.abs(d)) * peak


def band_noise(n, lo=250.0, hi=2950.0, seed=11):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1.0 / SR)
    X[(f < lo) | (f > hi)] = 0.0
    y = np.fft.irfft(X, n)
    return y / np.sqrt(np.mean(y ** 2))


def render(x, tag, level=0, legacy=False):
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=True,
                      enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED)
    if legacy:
        p._panel_gain = 0.06
        p._agc_top_db = 80.0
    p.set_bandpass(300.0, 2700.0)
    if legacy:
        _wdsp.SetRXAEMNRRun(ctypes.c_int(0), ctypes.c_int(1))
        _wdsp.SetRXAEMNRgainMethod(ctypes.c_int(0), ctypes.c_int(0))
        _wdsp.SetRXAEMNRnpeMethod(ctypes.c_int(0), ctypes.c_int(0))   # 旧: OSMS(最小统计)
        _wdsp.SetRXAEMNRaeRun(ctypes.c_int(0), ctypes.c_int(1))
        _wdsp.SetRXAEMNRaePsi(ctypes.c_int(0), ctypes.c_double(12.0))
        _wdsp.SetRXAEMNRaeZetaThresh(ctypes.c_int(0), ctypes.c_double(0.65))
        _wdsp.SetRXAEMNRmaxAttenDb(ctypes.c_int(0), ctypes.c_double(0.0))  # 旧: 不限制
        _wdsp.SetRXAAGCTop(ctypes.c_int(0), ctypes.c_double(80.0))
        _wdsp.SetRXAPanelGain1(ctypes.c_int(0), ctypes.c_double(0.06))
    else:
        p._panel_gain = 0.35          # 电平对齐（生产 panel=0.35）
        _wdsp.SetRXAPanelGain1(ctypes.c_int(0), ctypes.c_double(0.35))
        p.set_nr2_level(level)
    n = len(x) // BS
    out = np.zeros(n * BS)
    t0 = time.monotonic()
    for b in range(n):
        out[b * BS:(b + 1) * BS] = p.process(x[b * BS:(b + 1) * BS].astype(np.float64))
        d = t0 + (b + 1) * BS / SR - time.monotonic()
        if d > 0:
            time.sleep(d)
    p.close()
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, tag)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(out, -1, 1) * 32767).astype(np.int16).tobytes())
    pk = np.max(np.abs(out[SR:]))
    print(f"  {tag:24s} peak={pk:.3f} rms={20*np.log10(np.sqrt(np.mean(out[SR:]**2))+1e-12):6.1f} dBFS")


if __name__ == "__main__":
    sp = load_speech(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cq.wav"))
    nz = band_noise(len(sp)) * np.sqrt(np.mean(sp ** 2)) * 10 ** (-8 / 20) * np.sqrt(2)
    noisy = np.concatenate([np.zeros(SR // 2), sp + nz])     # 前 0.5s 静音便于听启动
    print(f"输入: {len(noisy)/SR:.1f}s 语音+噪声(带内SNR 8dB) → {OUT}")
    render(noisy, "A_nr2_off.wav", level=0)
    render(noisy, "B_nr2_L2_new.wav", level=2)
    render(noisy, "D_nr2_L1_new.wav", level=1)
    render(noisy, "E_nr2_L4_new.wav", level=4)
    render(noisy, "C_nr2_L2_legacy.wav", legacy=True)

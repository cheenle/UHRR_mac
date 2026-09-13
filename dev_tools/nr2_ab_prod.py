#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A3：生产 wrapper 路径的 NR2 等级 A/B。

走真实链路：WDSPProcessor(默认配置) + set_bandpass + set_nr2_level(level)
（含 AGC 封顶 / panel / NR2 语音保护），量化"静音段降噪 vs 语音段损伤"。

验收：level 2 时 NR静音 <= -12 dB 且 语音Δ >= -6 dB（修复前 语音Δ ≈ -14.3 dB）。
"""
import os, sys, time, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode

SR, BS = 48000, 256
HERE = os.path.dirname(os.path.abspath(__file__))
MARK, PAD = int(0.5 * SR), int(0.2 * SR)


def load_speech(path, seconds=8.0, peak=0.25):
    with wave.open(path, "rb") as w:
        d = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
        r = w.getframerate()
        if w.getnchannels() == 2:
            d = d.reshape(-1, 2)[:, 0]
    n = int(len(d) * SR / r)
    X = np.fft.rfft(d); Y = np.zeros(n // 2 + 1, complex)
    k = min(len(X), len(Y)); Y[:k] = X[:k]
    d = np.fft.irfft(Y, n) * (n / len(d))
    return (d[:int(seconds * SR)]) / np.max(np.abs(d[:int(seconds * SR)])) * peak


def band_noise(n, lo=250.0, hi=2950.0, seed=11, amp=1.0):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1.0 / SR)
    X[(f < lo) | (f > hi)] = 0.0
    y = np.fft.irfft(X, n)
    return y / np.sqrt(np.mean(y ** 2)) * amp


def run(x, level, seconds_pace=True, agc_on=True):
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=True,
                      enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED)
    p.set_bandpass(300.0, 2700.0)
    p.set_nr2_level(level)
    if not agc_on:          # 隔离测量：关 AGC 补偿增益，只看 NR2 本身对语音/噪声的作用
        from wdsp_wrapper import _wdsp
        import ctypes
        _wdsp.SetRXAAGCMode(ctypes.c_int(0), ctypes.c_int(0))
        _wdsp.SetRXAAGCFixed(ctypes.c_int(0), ctypes.c_double(0.0))
        _wdsp.SetRXAPanelGain1(ctypes.c_int(0), ctypes.c_double(1.0))
    n = len(x) // BS
    out = np.zeros(n * BS)
    t0 = time.monotonic()
    for b in range(n):
        out[b * BS:(b + 1) * BS] = p.process(x[b * BS:(b + 1) * BS].astype(np.float64))
        if seconds_pace:
            d = t0 + (b + 1) * BS / SR - time.monotonic()
            if d > 0:
                time.sleep(d)
    p.close()
    return out


def lag(x, y, maxlag=12000):
    a = x[:MARK]
    best, bl = -1e18, 0
    for d in range(0, maxlag, 2):
        v = float(np.dot(a, y[d:d + MARK]))
        if v > best:
            best, bl = v, d
    for d in range(max(0, bl - 8), bl + 9):
        v = float(np.dot(a, y[d:d + MARK]))
        if v > best:
            best, bl = v, d
    return bl


def stft(x, n=1024, hop=256):
    win = np.hanning(n)
    nf = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(nf)[:, None]
    return np.abs(np.fft.rfft(x[idx] * win, axis=1)) + 1e-12


def metrics(ci, ni, y, lg, start=0):
    """start: 跳过人工合成的静音段（数字 0 会让能量比值虚高）；只用真实语音区。"""
    L = min(len(ci) - start, len(y) - lg - start)
    o, c, n = y[lg + start:lg + start + L], ci[start:start + L], ni[start:start + L]
    Mo, Mn, Mc = stft(o), stft(n), stft(c)
    nf = min(len(Mo), len(Mn), len(Mc)); Mo, Mn, Mc = Mo[:nf], Mn[:nf], Mc[:nf]
    ec = np.sum(Mc ** 2, axis=1)
    sp = ec > np.percentile(ec, 65) * 0.05
    si = ec <= np.percentile(ec, 20) * 0.5
    eo, en = np.sum(Mo ** 2, axis=1), np.sum(Mn ** 2, axis=1)
    db = lambda v: 10 * np.log10(max(v, 1e-20))
    nr = float(np.mean([db(a) - db(b) for a, b in zip(eo[si], en[si])]))
    spd = float(np.mean([db(a) - db(b) for a, b in zip(eo[sp], en[sp])]))
    lsd = float(np.mean(np.sqrt(np.mean((20 * np.log10(Mo[sp] / Mc[sp])) ** 2, axis=1))))
    lsdn = float(np.mean(np.sqrt(np.mean((20 * np.log10(Mn[sp] / Mc[sp])) ** 2, axis=1))))
    return dict(nr=nr, spd=spd, lsd=lsd, lsdn=lsdn,
                snr_imp=-(nr + spd), peak=float(np.max(np.abs(o))),
                jit=float(np.std(10 * np.log10(eo[si] + 1e-20))))


if __name__ == "__main__":
    sp = load_speech(os.path.join(os.path.dirname(HERE), "cq.wav"))
    nz = band_noise(len(sp)) * np.sqrt(np.mean(sp ** 2)) * 10 ** (-8 / 20) * np.sqrt(2)
    noisy = sp + nz
    mark = band_noise(MARK, seed=99, amp=0.1)
    prep = lambda s: np.concatenate([mark, np.zeros(PAD), s])
    ci, ni = prep(sp), prep(noisy)
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--agc-off", action="store_true", help="隔离测量：关 AGC/panel=1（只看 NR2 本身）")
    args = ap.parse_args()
    mode = "AGC=OFF/panel=1（隔离测量，基准=带通-6dB）" if args.agc_off else "生产：AGC=MED, panel=0.35, agc_top=+20dB"
    print(f"语音 {len(sp)/SR:.1f}s 带内SNR=8dB  ({mode})")
    print(f"{'level':>6s} {'peak':>7s} {'NR静音':>8s} {'语音Δ':>7s} {'SNR提升':>8s} {'LSD':>6s} {'(无NR)':>7s} {'抖动':>6s}")
    for lv in (0, 1, 2, 3, 4):
        y = run(ni, lv, agc_on=not args.agc_off)
        lg = lag(ni, y)
        m = metrics(ci, ni, y, lg, start=MARK + PAD)
        print(f"{lv:6d} {m['peak']:7.3f} {m['nr']:8.1f} {m['spd']:7.1f} {m['snr_imp']:8.1f} "
              f"{m['lsd']:6.1f} {m['lsdn']:7.1f} {m['jit']:6.1f}")

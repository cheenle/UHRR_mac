#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NR2/EMNR 掩码级分析：把 EMNR 实际施加的频谱增益 m(f,t) 量出来。
- 输入前 0.5s 放一段带限噪声"标记"用于精确对齐（不改动 NR2 行为）
- 干净语音（无噪声）→ 理想 NR2 应 m≈1；偏差即"无中生有的变形"
- 带噪语音 → m 在语音 bin 上的分布即"谱切割"程度（语音发闷/机器人化）
"""
import ctypes, os, sys, time, wave, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode, _wdsp

SR, BS = 48000, 256
HERE = os.path.dirname(os.path.abspath(__file__))
MARK = int(0.5 * SR)


def band_noise(n, lo=250.0, hi=2900.0, seed=11):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1.0 / SR)
    X[(f < lo) | (f > hi)] = 0.0
    y = np.fft.irfft(X, n)
    return y / np.sqrt(np.mean(y ** 2))


def load_speech(seconds=6.0, peak=0.25):
    with wave.open(os.path.join(os.path.dirname(HERE), "cq.wav"), "rb") as w:
        d = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
        r = w.getframerate()
    n_out = int(len(d) * SR / r)
    X = np.fft.rfft(d); Y = np.zeros(n_out // 2 + 1, complex)
    k = min(len(X), len(Y)); Y[:k] = X[:k]
    d = np.fft.irfft(Y, n_out) * (n_out / len(d))
    d = d[:int(seconds * SR)]
    return d / np.max(np.abs(d)) * peak


def process(x, emnr=True, gm=0, npe=0, ae=1, psi=10.0, zeta=0.75, agc=WDSPAGCMode.MED,
            panel=0.06, bp=(300.0, 2700.0), pace=True):
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=False,
                      enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED)
    _wdsp.SetRXAPanelGain1(ctypes.c_int(0), ctypes.c_double(panel))
    if agc is None:
        _wdsp.SetRXAAGCMode(ctypes.c_int(0), ctypes.c_int(0))
        _wdsp.SetRXAAGCFixed(ctypes.c_int(0), ctypes.c_double(0.0))
    else:
        _wdsp.SetRXAAGCMode(ctypes.c_int(0), ctypes.c_int(agc))
        _wdsp.SetRXAAGCAttack(ctypes.c_int(0), ctypes.c_int(4))
        _wdsp.SetRXAAGCDecay(ctypes.c_int(0), ctypes.c_int(250))
        _wdsp.SetRXAAGCHang(ctypes.c_int(0), ctypes.c_int(250))
    if emnr:
        _wdsp.SetRXAEMNRRun(ctypes.c_int(0), ctypes.c_int(1))
        _wdsp.SetRXAEMNRgainMethod(ctypes.c_int(0), ctypes.c_int(gm))
        _wdsp.SetRXAEMNRnpeMethod(ctypes.c_int(0), ctypes.c_int(npe))
        _wdsp.SetRXAEMNRaeRun(ctypes.c_int(0), ctypes.c_int(ae))
        _wdsp.SetRXAEMNRPosition(ctypes.c_int(0), ctypes.c_int(0))
        _wdsp.SetRXAEMNRaePsi(ctypes.c_int(0), ctypes.c_double(psi))
        _wdsp.SetRXAEMNRaeZetaThresh(ctypes.c_int(0), ctypes.c_double(zeta))
    else:
        _wdsp.SetRXAEMNRRun(ctypes.c_int(0), ctypes.c_int(0))
    if bp:
        p.set_bandpass(*bp)
    else:
        _wdsp.SetRXABandpassRun(ctypes.c_int(0), ctypes.c_int(0))
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
        if pace:
            d = t0 + (b + 1) * BS / SR - time.monotonic()
            if d > 0:
                time.sleep(d)
    p.close()
    return out


def lag_from_mark(x, y, maxlag=20000):
    a = x[:MARK]
    n = min(len(y) - MARK, maxlag)
    best, bl = -1e18, 0
    for d in range(0, n, 4):
        v = float(np.dot(a, y[d:d + MARK]))
        if v > best:
            best, bl = v, d
    for d in range(max(0, bl - 6), bl + 7):
        v = float(np.dot(a, y[d:d + MARK]))
        if v > best:
            best, bl = v, d
    return bl


def mask_stats(x, y, lag, n=512, hop=128):
    """m(f,t) = |Y|/|X|（对齐后），只在 300-3000Hz 语音带内统计"""
    nf = (min(len(x), len(y) - lag) - n) // hop
    win = np.hanning(n)
    idx = np.arange(n)[None, :] + hop * np.arange(nf)[:, None]
    X = np.abs(np.fft.rfft(x[idx] * win, axis=1)) + 1e-9
    Y = np.abs(np.fft.rfft(y[idx + lag] * win, axis=1)) + 1e-9
    f = np.fft.rfftfreq(n, 1.0 / SR)
    band = (f >= 300) & (f <= 3000)
    M = 20 * np.log10(Y[:, band] / X[:, band])
    Xb = X[:, band]
    E = np.sum(Xb ** 2, axis=1)
    sp = E > np.percentile(E, 70) * 0.05
    si = E <= np.percentile(E, 20) * 0.5
    def q(mask, tag):
        if mask.size == 0:
            return {}
        return {f"{tag}_med": float(np.median(mask)),
                f"{tag}_p10": float(np.percentile(mask, 10)),
                f"{tag}_p90": float(np.percentile(mask, 90)),
                f"{tag}_frac_lt3": float(np.mean(mask < -3)),
                f"{tag}_frac_lt6": float(np.mean(mask < -6)),
                f"{tag}_frac_gt3": float(np.mean(mask > 3))}
    out = {}
    out.update(q(M[sp], "sp"))
    out.update(q(M[si], "si"))
    # 帧内跨频波动（音色变形）与帧间波动（调制/水音）
    out["sp_within_std"] = float(np.mean(np.std(M[sp], axis=1))) if sp.any() else 0
    out["sp_time_std"] = float(np.mean(np.std(M[sp], axis=0))) if sp.any() else 0
    out["si_time_std"] = float(np.mean(np.std(M[si], axis=0))) if si.any() else 0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--snr", type=float, default=10.0)
    args = ap.parse_args()

    sp = load_speech(args.seconds)
    nz = band_noise(len(sp)) * np.sqrt(np.mean(sp ** 2)) * 10 ** (-args.snr / 20) * np.sqrt(2)
    noisy = sp + nz
    mark = band_noise(MARK, seed=99) * 0.1

    def prep(sig):
        return np.concatenate([mark, np.zeros(BS), sig])

    clean_in = prep(sp)
    noisy_in = prep(noisy)

    print("【A】干净语音（无噪声, AGC关/panel=1）→ 理想 m≈0dB；偏差=NR2 自造变形")
    print(f"{'配置':26s} {'sp_med':>7s} {'sp_p10':>7s} {'<-3dB':>7s} {'<-6dB':>7s} {'>+3dB':>7s} "
          f"{'帧内σ':>6s} {'帧间σ':>6s}")
    cases = [("NR2 OFF", dict(emnr=False)),
             ("gm0_ae1 (L2生产)", dict(emnr=True, gm=0, ae=1)),
             ("gm0_ae0", dict(emnr=True, gm=0, ae=0)),
             ("gm1_ae1", dict(emnr=True, gm=1, ae=1)),
             ("gm2_ae1 (WDSP默认)", dict(emnr=True, gm=2, ae=1)),
             ("gm2_ae0", dict(emnr=True, gm=2, ae=0)),
             ("gm0_npe1_ae1", dict(emnr=True, gm=0, npe=1, ae=1))]
    res = {}
    for tag, kw in cases:
        y = process(clean_in, agc=None, panel=1.0, **kw)
        lag = lag_from_mark(clean_in, y)
        m = mask_stats(clean_in, y, lag)
        res[tag] = m
        print(f"{tag:26s} {m.get('sp_med',0):7.1f} {m.get('sp_p10',0):7.1f} "
              f"{m.get('sp_frac_lt3',0)*100:6.1f}% {m.get('sp_frac_lt6',0)*100:6.1f}% "
              f"{m.get('sp_frac_gt3',0)*100:6.1f}% {m.get('sp_within_std',0):6.1f} {m.get('sp_time_std',0):6.1f}")

    print(f"\n【B】带噪语音（带内SNR={args.snr}dB, AGC关/panel=1）→ 静音段降噪 vs 语音段谱切割")
    print(f"{'配置':26s} {'静音段m':>8s} {'sp_med':>7s} {'sp_p10':>7s} {'<-6dB':>7s} {'帧内σ':>6s} {'帧间σ':>6s}")
    for tag, kw in cases:
        y = process(noisy_in, agc=None, panel=1.0, **kw)
        lag = lag_from_mark(noisy_in, y)
        m = mask_stats(noisy_in, y, lag)
        print(f"{tag:26s} {m.get('si_med',0):8.1f} {m.get('sp_med',0):7.1f} {m.get('sp_p10',0):7.1f} "
              f"{m.get('sp_frac_lt6',0)*100:6.1f}% {m.get('sp_within_std',0):6.1f} {m.get('sp_time_std',0):6.1f}")


if __name__ == "__main__":
    main()

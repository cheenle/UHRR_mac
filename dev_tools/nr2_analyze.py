#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NR2 (EMNR) 深度分析 v3 —— 延迟对齐 + 真实频响 + 语音失真度量。

要点：
  * 严格按生产节拍（20ms 批推 256 样本块）；
  * 先用带限噪声标定链路群延迟，再做对齐后的频响/失真分析；
  * 一条配置同时给出：(a) 白噪频响 |H(f)|，(b) 静音段降噪量，(c) 语音段谱失真。

用法:
  python3 dev_tools/nr2_analyze.py            # 关键配置对比
  python3 dev_tools/nr2_analyze.py --wav 输出文件
"""
import ctypes, os, sys, time, wave, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode, WDSPMeterType, _wdsp

SR, BS = 48000, 256
HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "nr2_out")
PROD = dict(agc=WDSPAGCMode.MED, panel=0.06, bp=(300.0, 2700.0))


# ---------------------------------------------------------------- 频响/延迟
def bandpass_noise(n, sr=SR, lo=250.0, hi=2900.0, seed=11):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1.0 / sr)
    X[(f < lo) | (f > hi)] = 0.0
    y = np.fft.irfft(X, n)
    return y / np.sqrt(np.mean(y ** 2))


def find_lag(x, y, maxlag=20000):
    """互相关求延迟（用平滑包络初估 + 原始信号精修）"""
    k = 512
    ex = np.convolve(np.abs(x), np.ones(k) / k, 'same')
    ey = np.convolve(np.abs(y), np.ones(k) / k, 'same')
    n = min(len(ex), len(ey)) // 2
    c = np.correlate(ey[:n], ex[:n // 2], 'full')
    lag = int(np.argmax(c)) - (n // 2 - 1)
    lag = max(0, min(lag, maxlag))
    best, bl = -1e18, lag
    for d in range(max(0, lag - 512), min(len(y) - 1, lag + 512)):
        a = x[1000:14000]
        b = y[1000 + d:14000 + d]
        if len(b) < len(a):
            break
        v = float(np.dot(a, b))
        if v > best:
            best, bl = v, d
    return bl


def tf_estimate(x, y, lag, n=4096, hop=1024, sr=SR):
    """对齐后逐帧 H(f)，返回 (f, |H| 平均, 相干)"""
    L = min(len(x), len(y) - lag) - n
    nf = L // hop
    win = np.hanning(n)
    idx = np.arange(n)[None, :] + hop * np.arange(nf)[:, None]
    X = np.fft.rfft(x[idx] * win, axis=1)
    Y = np.fft.rfft(y[idx + lag] * win, axis=1)
    Sxx = np.mean(np.abs(X) ** 2, axis=0)
    Sxy = np.mean(X.conj() * Y, axis=0)
    Syy = np.mean(np.abs(Y) ** 2, axis=0)
    H = Sxy / (Sxx + 1e-30)
    coh = np.abs(Sxy) ** 2 / (Sxx * Syy + 1e-30)
    return np.fft.rfftfreq(n, 1.0 / sr), H, coh


# ---------------------------------------------------------------- 处理
def process(x, emnr=False, gm=0, npe=0, ae=1, psi=10.0, zeta=0.75,
            agc=None, panel=1.0, bp=None, nb=False, anf=False, pace=True, want_meter=False):
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
    _wdsp.SetRXAEMNRRun(ctypes.c_int(0), ctypes.c_int(1 if emnr else 0))
    if emnr:
        _wdsp.SetRXAEMNRgainMethod(ctypes.c_int(0), ctypes.c_int(gm))
        _wdsp.SetRXAEMNRnpeMethod(ctypes.c_int(0), ctypes.c_int(npe))
        _wdsp.SetRXAEMNRaeRun(ctypes.c_int(0), ctypes.c_int(ae))
        _wdsp.SetRXAEMNRPosition(ctypes.c_int(0), ctypes.c_int(0))
        _wdsp.SetRXAEMNRaePsi(ctypes.c_int(0), ctypes.c_double(psi))
        _wdsp.SetRXAEMNRaeZetaThresh(ctypes.c_int(0), ctypes.c_double(zeta))
    _wdsp.SetRXASNBARun(ctypes.c_int(0), ctypes.c_int(1 if nb else 0))
    _wdsp.SetRXAANFRun(ctypes.c_int(0), ctypes.c_int(1 if anf else 0))
    if bp:
        p.set_bandpass(*bp)
    else:
        _wdsp.SetRXABandpassRun(ctypes.c_int(0), ctypes.c_int(0))

    n = len(x) // BS
    out = np.zeros(n * BS)
    meter = np.zeros(n)
    t0 = time.monotonic()
    err2 = 0
    for b in range(n):
        blk = x[b * BS:(b + 1) * BS]
        p._in_buffer[0::2] = blk
        p._in_buffer[1::2] = 0.0
        e = ctypes.c_int(0)
        _wdsp.fexchange0(ctypes.c_int(0),
                         p._in_buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                         p._out_buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                         ctypes.byref(e))
        if e.value == -2:
            err2 += 1
            out[b * BS:(b + 1) * BS] = blk
        else:
            out[b * BS:(b + 1) * BS] = p._out_buffer[0::2]
        if want_meter:
            meter[b] = p.get_meter(WDSPMeterType.AGC_GAIN)
        if pace:
            d = t0 + (b + 1) * BS / SR - time.monotonic()
            if d > 0:
                time.sleep(d)
    p.close()
    return out, err2, meter


# ---------------------------------------------------------------- 语音度量
def stft(x, n=1024, hop=256):
    win = np.hanning(n)
    nf = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(nf)[:, None]
    return np.abs(np.fft.rfft(x[idx] * win, axis=1)) + 1e-12


def speech_metrics(clean, noisy, out, lag):
    """clean/noisy 与 out（已按 lag 对齐剪切）"""
    o = out[lag:lag + len(clean)]
    n = noisy[:len(clean)]
    c = clean[:len(clean)]
    Mo, Mn, Mc = stft(o), stft(n), stft(c)
    nf = min(len(Mo), len(Mn), len(Mc))
    Mo, Mn, Mc = Mo[:nf], Mn[:nf], Mc[:nf]
    ec = np.sum(Mc ** 2, axis=1)
    sp = ec > np.percentile(ec, 65) * 0.05          # 语音帧
    si = ec <= np.percentile(ec, 20) * 0.5          # 静音帧
    eo, en = np.sum(Mo ** 2, axis=1), np.sum(Mn ** 2, axis=1)
    d = lambda a, b: 10 * np.log10(max(a, 1e-20)) - 10 * np.log10(max(b, 1e-20))
    return dict(
        rms_out=20 * np.log10(np.sqrt(np.mean(o ** 2)) + 1e-12),
        peak=float(np.max(np.abs(o))),
        nr_db=float(np.mean([d(a, b) for a, b in zip(eo[si], en[si])])) if si.any() else 0,
        sig_db=float(np.mean([d(a, b) for a, b in zip(eo[sp], np.sum(Mc[sp] ** 2, axis=1))])) if sp.any() else 0,
        lsd=float(np.mean(np.sqrt(np.mean((20 * np.log10(Mo[sp] / Mc[sp])) ** 2, axis=1)))) if sp.any() else 0,
        rough=float(np.mean(np.std(20 * np.log10(Mo[sp] / Mn[sp]), axis=1))) if sp.any() else 0,
        musical=float(np.std(10 * np.log10(eo[si] + 1e-20))) if si.any() else 0,
        n_speech=int(sp.sum()), n_sil=int(si.sum()))


def save_wav(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def load_speech(seconds=6.0, peak=0.25):
    src = os.path.join(os.path.dirname(HERE), "cq.wav")
    with wave.open(src, "rb") as w:
        d = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
        r = w.getframerate()
    n_out = int(len(d) * SR / r)
    X = np.fft.rfft(d); Y = np.zeros(n_out // 2 + 1, complex)
    k = min(len(X), len(Y)); Y[:k] = X[:k]
    d = np.fft.irfft(Y, n_out) * (n_out / len(d))
    d = d[:int(seconds * SR)]
    return d / np.max(np.abs(d)) * peak


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--snr", type=float, default=10.0)
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)

    sp = load_speech(args.seconds)
    nz = bandpass_noise(len(sp)) * np.sqrt(np.mean(sp ** 2)) * 10 ** (-args.snr / 20.0) * np.sqrt(2)
    noisy = sp + nz
    print(f"clean {20*np.log10(np.sqrt(np.mean(sp**2))):.1f}dB  noisy {20*np.log10(np.sqrt(np.mean(noisy**2))):.1f}dB  "
          f"({args.seconds:.0f}s, 带内SNR={args.snr}dB)")

    # ---- 频响（噪声激励，标定延迟）----
    print("\n--- 频响 / 延迟（白噪激励）---")
    probe = bandpass_noise(int(SR * 2.0))
    for tag, kw in [("NR2off", dict()), ("NR2on gm0", dict(emnr=True)), ("NR2on gm2", dict(emnr=True, gm=2))]:
        y, e2, _ = process(probe, **kw)
        lag = find_lag(probe, y)
        f, H, coh = tf_estimate(probe, y, lag)
        def g(f0):
            if f0 < 300: return np.nan
            m = (f >= f0 * 0.9) & (f <= f0 * 1.1)
            return 20 * np.log10(np.abs(H[m]).mean() + 1e-12)
        print(f"  {tag:10s} lag={lag:5d}  |H|: 400Hz={g(400):+.1f} 1k={g(1000):+.1f} "
              f"1.5k={g(1500):+.1f} 2k={g(2000):+.1f} 2.5k={g(2500):+.1f} dB  "
              f"平均相干={np.mean(coh[(f>300)&(f<2700)]):.2f}")

    # ---- 语音失真 ----
    print("\n--- 语音失真 / 降噪（生产链路: AGC=MED + bp1 300-2700）---")
    cases = [("NR2_OFF", dict(emnr=False, **PROD)),
             ("L1_gm0_ae0", dict(emnr=True, gm=0, npe=0, ae=0, **PROD)),
             ("L2_gm0_ae1", dict(emnr=True, gm=0, npe=0, ae=1, **PROD)),
             ("L2_gm2_ae1", dict(emnr=True, gm=2, npe=0, ae=1, **PROD)),
             ("L3_gm1_npe1", dict(emnr=True, gm=1, npe=1, ae=1, **PROD)),
             ]
    if args.full:
        cases += [("gm0_ae1_psi20", dict(emnr=True, gm=0, ae=1, psi=20.0, zeta=0.5, **PROD)),
                  ("gm0_ae1_psi4", dict(emnr=True, gm=0, ae=1, psi=4.0, **PROD)),
                  ("gm2_npe1_ae1", dict(emnr=True, gm=2, npe=1, ae=1, **PROD)),
                  ("NR2ON_noAGC", dict(emnr=True, gm=0, ae=1, panel=1.0, bp=(300., 2700.))),
                  ("NR2OFF_noAGC", dict(emnr=False, panel=1.0, bp=(300., 2700.)))]

    print(f"{'case':14s} {'peak':>6s} {'rms':>7s} {'NR(dB)':>7s} {'sig(dB)':>8s} "
          f"{'LSD':>6s} {'粗糙':>6s} {'music':>6s} {'err2':>4s}")
    for tag, kw in cases:
        out, e2, mtr = process(noisy, pace=True, want_meter=True, **kw)
        lag = find_lag(noisy, out)
        if lag > 0:
            m = speech_metrics(sp, noisy, out, lag)
        else:
            m = speech_metrics(sp, noisy, out, 0)
        save_wav(os.path.join(OUTDIR, f"v3_{tag}.wav"), out)
        print(f"{tag:14s} {m['peak']:6.3f} {m['rms_out']:7.1f} {m['nr_db']:7.1f} {m['sig_db']:8.1f} "
              f"{m['lsd']:6.1f} {m['rough']:6.1f} {m['musical']:6.1f} {e2:4d}   lag={lag}")


if __name__ == "__main__":
    main()

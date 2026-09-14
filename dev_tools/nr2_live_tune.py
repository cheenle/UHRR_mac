#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用真实频段噪声 + 真实语音做 NR2 参数寻优。

输入:
  --noise  /tmp/live_rx.wav   实时 RX 噪声床（右声道，48k）
  --speech cq.wav             干净语音参考（16k → 48k）
输出:
  dev_tools/nr2_out/tune_*.wav + 指标表 + 推荐配置

指标（受控，有干净参考）:
  voice_Δ : 语音帧能量变化(dB，越接近 0 越不"吃语音")
  noise_Δ : 静音帧噪声变化(dB，越负降噪越强)
  LSD     : 语音帧对数谱失真(dB，相对干净语音 = "变形"量)
  jitter  : 静音帧残余的时间抖动(dB，音乐噪声)
"""
import argparse, ctypes, os, sys, time, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode, WDSPNR2Level, _wdsp

SR, BS = 48000, 256
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "nr2_out")
MARK = int(0.5 * SR)


def load_wav(path, seconds=None):
    with wave.open(path, "rb") as w:
        d = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
        r = w.getframerate(); ch = w.getnchannels()
        if ch == 2:
            d = d.reshape(-1, 2)[:, 1]
    if r != SR:
        n = int(len(d) * SR / r)
        X = np.fft.rfft(d); Y = np.zeros(n // 2 + 1, complex)
        k = min(len(X), len(Y)); Y[:k] = X[:k]
        d = np.fft.irfft(Y, n) * (n / len(d))
    return d[:int(seconds * SR)] if seconds else d


def band_rms(x, lo=300, hi=2700):
    X = np.abs(np.fft.rfft(x)); f = np.fft.rfftfreq(len(x), 1 / SR)
    m = (f >= lo) & (f <= hi)
    return np.sqrt(np.sum(X[m] ** 2)) / len(x)


def run(x, level, agc_top=20.0, panel=0.35, max_atten=None, agc_on=True, dry=0.0):
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=True,
                      enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED,
                      agc_top_db=agc_top, panel_gain=panel)
    p.set_bandpass(300.0, 2700.0)
    p.set_nr2_level(level)
    if max_atten is not None or dry:
        p.set_nr2_voice_protection(max_atten, dry)
    if not agc_on:
        _wdsp.SetRXAAGCMode(ctypes.c_int(0), ctypes.c_int(0))
        _wdsp.SetRXAAGCFixed(ctypes.c_int(0), ctypes.c_double(0.0))
        _wdsp.SetRXAPanelGain1(ctypes.c_int(0), ctypes.c_double(1.0))
    n = len(x) // BS
    out = np.zeros(n * BS)
    t0 = time.monotonic()
    for b in range(n):
        out[b * BS:(b + 1) * BS] = p.process(x[b * BS:(b + 1) * BS].astype(np.float64))
        d = t0 + (b + 1) * BS / SR - time.monotonic()
        if d > 0:
            time.sleep(d)
    p.close()
    return out


def lag(x, y, maxlag=12000):
    a = x[:MARK]; best, bl = -1e18, 0
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


def metrics(ci, ni, y, lg, start):
    L = min(len(ci) - start, len(y) - lg - start)
    o, c, n = y[lg + start:lg + start + L], ci[start:start + L], ni[start:start + L]
    Mo, Mn, Mc = stft(o), stft(n), stft(c)
    nf = min(len(Mo), len(Mn), len(Mc)); Mo, Mn, Mc = Mo[:nf], Mn[:nf], Mc[:nf]
    ec = np.sum(Mc ** 2, axis=1)
    sp = ec > np.percentile(ec, 65) * 0.05
    si = ec <= np.percentile(ec, 20) * 0.5
    eo, en = np.sum(Mo ** 2, axis=1), np.sum(Mn ** 2, axis=1)
    db = lambda v: 10 * np.log10(max(v, 1e-20))
    return dict(
        voice=float(np.mean([db(a) - db(b) for a, b in zip(eo[sp], en[sp])])) if sp.any() else 0.0,
        noise=float(np.mean([db(a) - db(b) for a, b in zip(eo[si], en[si])])) if si.any() else 0.0,
        lsd=float(np.mean(np.sqrt(np.mean((20 * np.log10(Mo[sp] / Mc[sp])) ** 2, axis=1)))) if sp.any() else 0.0,
        lsd_in=float(np.mean(np.sqrt(np.mean((20 * np.log10(Mn[sp] / Mc[sp])) ** 2, axis=1)))) if sp.any() else 0.0,
        jitter=float(np.std(10 * np.log10(eo[si] + 1e-20))) if si.any() else 0.0,
        peak=float(np.max(np.abs(o))))


def live_noise_metrics(noise_in, y):
    """无参考：只比噪声床的输出/输入（现场降噪量）与残余抖动"""
    lg = lag(np.concatenate([np.zeros(MARK), noise_in]), np.concatenate([np.zeros(MARK), y])) if False else 0
    a, b = stft(noise_in), stft(y)
    nf = min(len(a), len(b)); a, b = a[:nf], b[:nf]
    ea, eb = np.sum(a ** 2, axis=1), np.sum(b ** 2, axis=1)
    db = lambda v: 10 * np.log10(max(v, 1e-20))
    return dict(nr=float(np.mean([db(x) - db(y2) for x, y2 in zip(eb, ea)])),
                jitter=float(np.std(10 * np.log10(eb + 1e-20))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--noise", default="/tmp/live_rx.wav")
    ap.add_argument("--speech", default=os.path.join(os.path.dirname(HERE), "cq.wav"))
    ap.add_argument("--snr", type=float, default=10.0)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    nb = load_wav(args.noise)
    sp = load_wav(args.speech)
    sp = sp / np.max(np.abs(sp)) * 0.25
    L = len(sp)
    nz = nb[:L].copy()
    # 噪声按带内 SNR 缩放
    target = band_rms(sp) * 10 ** (-args.snr / 20)
    nz = nz * (target / max(band_rms(nz), 1e-12))
    noisy = sp + nz
    print(f"语音 {L/SR:.1f}s（{os.path.basename(args.speech)}） + 实时噪声 {os.path.basename(args.noise)} "
          f"→ 带内 SNR {args.snr:.0f} dB")
    print(f"实时噪声床自身: RMS={20*np.log10(np.sqrt(np.mean(nb**2))):.1f} dBFS  "
          f"带内={20*np.log10(band_rms(nb)):.1f} dBFS")

    mark = (np.random.default_rng(99).standard_normal(MARK) * 0.1)
    prep = lambda s: np.concatenate([mark, np.zeros(BS), s])
    ci, ni = prep(sp), prep(noisy)
    start = MARK + BS

    cases = [("NR2 OFF", dict(level=0)),
             ("L1 (max-6)", dict(level=1)),
             ("L2 (max-12) 默认", dict(level=2)),
             ("L3 (max-16)", dict(level=3)),
             ("L4 (max-20)", dict(level=4)),
             ("L2 +max-9", dict(level=2, max_atten=-9.0)),
             ("L2 +max-15", dict(level=2, max_atten=-15.0)),
             ("L2 +dry0.2", dict(level=2, dry=0.2)),
             ("L2 AGC关", dict(level=2, agc_on=False)),
             ("L2 AGC顶10dB", dict(level=2, agc_top=10.0))]
    if args.quick:
        cases = cases[:5]

    print(f"\n{'配置':20s} {'peak':>6s} {'voiceΔ':>7s} {'noiseΔ':>7s} {'SNR提升':>8s} {'LSD':>6s} {'(无NR)':>7s} {'抖动':>6s}")
    rows = []
    for tag, kw in cases:
        y = run(ni, **kw)
        lg = lag(ni, y)
        m = metrics(ci, ni, y, lg, start)
        m["tag"] = tag
        m["snr_gain"] = -(m["noise"] + m["voice"])
        rows.append(m)
        with wave.open(os.path.join(OUT, f"tune_{tag.split()[0]}_{abs(hash(tag))%1000}.wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
        print(f"{tag:20s} {m['peak']:6.3f} {m['voice']:7.1f} {m['noise']:7.1f} {m['snr_gain']:8.1f} "
              f"{m['lsd']:6.1f} {m['lsd_in']:7.1f} {m['jitter']:6.1f}")

    # 现场（纯实时噪声，无参考）
    print(f"\n现场实时噪声（无语音，直接看降噪量与残余抖动）")
    print(f"{'配置':20s} {'降噪dB':>8s} {'残余抖动dB':>10s}")
    live = np.concatenate([np.zeros(MARK), nb[:int(6 * SR)]])
    live_in = live.copy()
    for tag, kw in [("NR2 OFF", dict(level=0)), ("L1 (max-6)", dict(level=1)), ("L2 (max-12)", dict(level=2)),
                    ("L4 (max-20)", dict(level=4)), ("L2 AGC关", dict(level=2, agc_on=False))]:
        y = run(live, **kw)
        lg = lag(live, y)
        mm = live_noise_metrics(live_in[MARK:], y[lg + MARK:lg + MARK + len(live) - MARK])
        print(f"{tag:20s} {mm['nr']:8.1f} {mm['jitter']:10.1f}")

    print(f"\n推荐：{max(rows, key=lambda r: r['snr_gain'] + (0 if r['voice'] > -4 else -99))['tag']}"
          f"  （SNR提升最大且 voiceΔ > -4dB）")
    print(f"WAV: {OUT}/tune_*.wav")


if __name__ == "__main__":
    main()

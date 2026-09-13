#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产链路 A/B 终测：用于 NR2 优化决策。
- 实时节拍(1x)（与实际生产一致）
- 记录 fexchange0 的 -2 事件位置，在事件之间分段对齐，避免时间跳变污染度量
- 指标：静音段噪声(相对输入)、语音段谱失真 LSD(相对干净参考)、残余抖动
"""
import ctypes, os, sys, time, wave, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wdsp_wrapper as W
LIB = os.environ.get("WDSP_LIB")
if LIB:
    W._wdsp = ctypes.CDLL(LIB)
_wdsp = W._wdsp
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode  # noqa: E402

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
    d = d[:int(seconds * SR)]
    return d / np.max(np.abs(d)) * peak


def band_noise(n, lo=250.0, hi=2950.0, seed=11, amp=1.0):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1.0 / SR)
    X[(f < lo) | (f > hi)] = 0.0
    y = np.fft.irfft(X, n)
    return y / np.sqrt(np.mean(y ** 2)) * amp


def run_prod(x, *, emnr, agc=WDSPAGCMode.MED, panel=0.06, bp=(300.0, 2700.0),
             floor_db=None, dry=None, gm=0, npe=0, ae=1, psi=12.0, zeta=0.65,
             agc_top_db=None, speed=1.0):
    """生产链路：与 audio_interface.PyAudioCapture + wdsp_wrapper 一致"""
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=False,
                      enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED)
    _wdsp.SetRXAAGCMode(ctypes.c_int(0), ctypes.c_int(agc))
    _wdsp.SetRXAAGCAttack(ctypes.c_int(0), ctypes.c_int(4))
    _wdsp.SetRXAAGCDecay(ctypes.c_int(0), ctypes.c_int(250))
    _wdsp.SetRXAAGCHang(ctypes.c_int(0), ctypes.c_int(250))
    if agc_top_db is not None:
        _wdsp.SetRXAAGCTop(ctypes.c_int(0), ctypes.c_double(agc_top_db))
    _wdsp.SetRXAPanelGain1(ctypes.c_int(0), ctypes.c_double(panel))
    if emnr:
        _wdsp.SetRXAEMNRRun(ctypes.c_int(0), ctypes.c_int(1))
        _wdsp.SetRXAEMNRgainMethod(ctypes.c_int(0), ctypes.c_int(gm))
        _wdsp.SetRXAEMNRnpeMethod(ctypes.c_int(0), ctypes.c_int(npe))
        _wdsp.SetRXAEMNRaeRun(ctypes.c_int(0), ctypes.c_int(ae))
        _wdsp.SetRXAEMNRPosition(ctypes.c_int(0), ctypes.c_int(0))
        _wdsp.SetRXAEMNRaePsi(ctypes.c_int(0), ctypes.c_double(psi))
        _wdsp.SetRXAEMNRaeZetaThresh(ctypes.c_int(0), ctypes.c_double(zeta))
        if floor_db is not None and hasattr(_wdsp, "SetRXAEMNRmaxAttenDb"):
            _wdsp.SetRXAEMNRmaxAttenDb(ctypes.c_int(0), ctypes.c_double(floor_db))
        if dry is not None and hasattr(_wdsp, "SetRXAEMNRdry"):
            _wdsp.SetRXAEMNRdry(ctypes.c_int(0), ctypes.c_double(dry))
    if bp and emnr:                 # 与生产一致：bp1 只在有 NR 模块运行时有效
        p.set_bandpass(*bp)
    n = len(x) // BS
    out = np.zeros(n * BS)
    errs = []
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
        if e.value == -2:
            errs.append(b)
            out[b * BS:(b + 1) * BS] = blk      # wrapper 真实行为
        else:
            out[b * BS:(b + 1) * BS] = p._out_buffer[0::2]
        d = t0 + (b + 1) * BS / SR / speed - time.monotonic()
        if d > 0:
            time.sleep(d)
    p.close()
    return out, errs


def local_lag(x, y, center, span=600, w=8000):
    best, bl = -1e18, center
    for d in range(max(0, center - span), center + span):
        v = float(np.dot(x[:w], y[d:d + w]))
        if v > best:
            best, bl = v, d
    return bl


def stft(x, n=1024, hop=256):
    win = np.hanning(n)
    nf = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(nf)[:, None]
    return np.abs(np.fft.rfft(x[idx] * win, axis=1)) + 1e-12


def measure(ci, ni, y, errs, ref_lag=6144):
    """分段对齐后统计"""
    # 事件点（样本）→ 分段
    cuts = [0] + [(b + 1) * BS for b in errs] + [len(ni)]
    Mo_all, Mn_all, Mc_all = [], [], []
    n_used = 0
    lags = []
    for i in range(len(cuts) - 1):
        s, e = cuts[i], cuts[i + 1]
        if e - s < 20000:
            continue
        seg = ni[s:e]
        lag = local_lag(seg, y[s:], ref_lag + (s - s))
        lag += s
        L = min(len(seg), len(y) - lag)
        if L < 16000:
            continue
        lags.append(lag - s)
        o = y[lag:lag + L]
        Mo_all.append(stft(o)); Mn_all.append(stft(ni[s:s + L])); Mc_all.append(stft(ci[s:s + L]))
        n_used += 1
    if not Mo_all:
        return None
    Mo = np.vstack(Mo_all); Mn = np.vstack(Mn_all); Mc = np.vstack(Mc_all)
    ec = np.sum(Mc ** 2, axis=1)
    sp = ec > np.percentile(ec, 65) * 0.05
    si = ec <= np.percentile(ec, 20) * 0.5
    eo, en = np.sum(Mo ** 2, axis=1), np.sum(Mn ** 2, axis=1)
    db = lambda v: 10 * np.log10(max(v, 1e-20))
    return dict(
        segs=n_used, lags=lags,
        nr=float(np.mean([db(a) - db(b) for a, b in zip(eo[si], en[si])])),
        spd=float(np.mean([db(a) - db(b) for a, b in zip(eo[sp], en[sp])])),
        lsd=float(np.mean(np.sqrt(np.mean((20 * np.log10(Mo[sp] / Mc[sp])) ** 2, axis=1)))),
        lsdn=float(np.mean(np.sqrt(np.mean((20 * np.log10(Mn[sp] / Mc[sp])) ** 2, axis=1)))),
        jit=float(np.std(10 * np.log10(eo[si] + 1e-20))),
        snr_gain=float(np.mean([db(a) - db(b) for a, b in zip(eo[sp], en[sp])])
                       - np.mean([db(a) - db(b) for a, b in zip(eo[si], en[si])])))


def save(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snr", type=float, default=8.0)
    ap.add_argument("--secs", type=float, default=8.0)
    ap.add_argument("--speed", type=float, default=1.0)
    args = ap.parse_args()
    outdir = os.path.join(HERE, "nr2_out"); os.makedirs(outdir, exist_ok=True)
    sp = load_speech(os.path.join(os.path.dirname(HERE), "cq.wav"), args.secs)
    nz = band_noise(len(sp)) * np.sqrt(np.mean(sp ** 2)) * 10 ** (-args.snr / 20) * np.sqrt(2)
    noisy = sp + nz
    mark = band_noise(MARK, seed=99, amp=0.1)
    prep = lambda s: np.concatenate([mark, np.zeros(PAD), s])
    ci, ni = prep(sp), prep(noisy)
    print(f"语音 {len(sp)/SR:.1f}s 带内SNR={args.snr}dB  clean={20*np.log10(np.sqrt(np.mean(sp**2))):.1f}dBFS  "
          f"speed={args.speed}x  库={LIB or '系统库'}")
    print(f"{'配置':30s} {'peak':>6s} {'NR静音':>7s} {'语音Δ':>7s} {'LSD':>6s} {'(无NR)':>7s} {'抖动':>6s} {'err2':>5s}")
    cases = [("1) NR2 OFF (生产)", dict(emnr=False)),
             ("2) NR2 ON  gm0/ae1 (生产)", dict(emnr=True)),
             ("3) ON + floor -15dB", dict(emnr=True, floor_db=-15.0)),
             ("4) ON + floor -12dB", dict(emnr=True, floor_db=-12.0)),
             ("5) ON + dry 0.15", dict(emnr=True, dry=0.15)),
             ("6) ON + dry 0.25", dict(emnr=True, dry=0.25)),
             ("7) ON + AGC顶+20dB", dict(emnr=True, agc_top_db=20.0)),
             ("8) 4)+7)", dict(emnr=True, floor_db=-12.0, agc_top_db=20.0)),
             ]
    for tag, kw in cases:
        y, errs = run_prod(ni, speed=args.speed, **kw)
        m = measure(ci, ni, y, errs)
        save(os.path.join(outdir, f"prod_{tag[:2].strip()}.wav"), y)
        if m is None:
            print(f"{tag:30s} 测量失败(分段过短) err2={len(errs)}")
            continue
        print(f"{tag:30s} {np.max(np.abs(y)):6.3f} {m['nr']:7.1f} {m['spd']:7.1f} {m['lsd']:6.1f} "
              f"{m['lsdn']:7.1f} {m['jit']:6.1f} {len(errs):5d}  段={m['segs']} 延迟={m['lags']}")


if __name__ == "__main__":
    main()

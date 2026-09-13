#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
掩码下限（最大衰减限制）验证 —— 用生产链路 + 语音段精确对齐。

对齐：marker + 语音段双层标定（fex 的 -2 事件会让延迟跳变，故直接用语音段
      [1.0s,2.5s] 区间做滑窗相关，逐 config 独立标定）。

度量：
  NR_pause : 静音段噪声抑制 (dB)                 —— 降噪收益
  sp_delta  : 语音段能量变化 (dB)                —— 语音被削多少（越接近 0 越好）
  LSD      : 语音段相对干净参考的谱失真 (dB)      —— "变形"程度
  jitter   : 静音段残余的时间抖动 (dB)            —— 音乐噪声/水音
"""
import ctypes, os, sys, time, wave, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wdsp_wrapper as W

LIB = os.environ.get("WDSP_LIB", "/tmp/wdsp_dbg/libwdsp.dylib")
W._wdsp = ctypes.CDLL(LIB)
_wdsp = W._wdsp
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode  # noqa: E402

SR, BS = 48000, 256
HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "nr2_out")
MARK = int(0.5 * SR)
PAD = int(0.2 * SR)


def load_speech(path, seconds=7.0, peak=0.25):
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


def band_noise(n, lo=200.0, hi=3000.0, seed=11, amp=1.0):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1.0 / SR)
    X[(f < lo) | (f > hi)] = 0.0
    y = np.fft.irfft(X, n)
    return y / np.sqrt(np.mean(y ** 2)) * amp


def run(x, *, emnr=True, gm=0, npe=0, ae=1, psi=10.0, zeta=0.75, floor_db=None,
        dry=None, agc=WDSPAGCMode.MED, panel=0.06, bp=(300.0, 2700.0), agc_top_db=None, pace=True):
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=False,
                      enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED)
    if agc is None:
        _wdsp.SetRXAAGCMode(ctypes.c_int(0), ctypes.c_int(0))
        _wdsp.SetRXAAGCFixed(ctypes.c_int(0), ctypes.c_double(0.0))
    else:
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
        _wdsp.SetRXAEMNRaePsi(ctypes.c_int(0), ctypes.c_double(psi))
        _wdsp.SetRXAEMNRaeZetaThresh(ctypes.c_int(0), ctypes.c_double(zeta))
        if floor_db is not None:
            _wdsp.SetRXAEMNRmaxAttenDb(ctypes.c_int(0), ctypes.c_double(floor_db))
        if dry is not None:
            _wdsp.SetRXAEMNRdry(ctypes.c_int(0), ctypes.c_double(dry))
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


def align_lag(x, y, lo=None, hi=None, span=20000):
    """用语音段 [lo,hi) 做滑窗相关标定延迟"""
    lo = MARK + PAD if lo is None else lo
    hi = lo + span if hi is None else hi
    a = x[lo:hi]
    best, bl = -1e18, 0
    for d in range(0, min(len(y) - len(a), 40000), 4):
        v = float(np.dot(a, y[d:d + len(a)]))
        if v > best:
            best, bl = v, d
    for d in range(max(0, bl - 6), bl + 7):
        v = float(np.dot(a, y[d:d + len(a)]))
        if v > best:
            best, bl = v, d
    return bl - lo     # 相对输入原位的延迟


def stft(x, n=1024, hop=256):
    win = np.hanning(n)
    nf = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(nf)[:, None]
    return np.abs(np.fft.rfft(x[idx] * win, axis=1)) + 1e-12


def metrics(clean, noisy, out, lag, skip=0):
    o = out[skip + lag: skip + lag + len(clean) - skip]
    c = clean[skip:]; n = noisy[skip:]
    Mo, Mn, Mc = stft(o), stft(n), stft(c)
    nf = min(len(Mo), len(Mn), len(Mc)); Mo, Mn, Mc = Mo[:nf], Mn[:nf], Mc[:nf]
    ec = np.sum(Mc ** 2, axis=1)
    sp = ec > np.percentile(ec, 65) * 0.05
    si = ec <= np.percentile(ec, 20) * 0.5
    eo, en = np.sum(Mo ** 2, axis=1), np.sum(Mn ** 2, axis=1)
    db = lambda v: 10 * np.log10(max(v, 1e-20))
    return dict(
        nr=float(np.mean([db(a) - db(b) for a, b in zip(eo[si], en[si])])),
        sp_delta=float(np.mean([db(a) - db(b) for a, b in zip(eo[sp], np.sum(Mn[sp] ** 2, axis=1))])),
        lsd=float(np.mean(np.sqrt(np.mean((20 * np.log10(Mo[sp] / Mc[sp])) ** 2, axis=1)))),
        lsd_noisy=float(np.mean(np.sqrt(np.mean((20 * np.log10(Mn[sp] / Mc[sp])) ** 2, axis=1)))),
        jitter=float(np.std(10 * np.log10(eo[si] + 1e-20))),
        peak=float(np.max(np.abs(o))))


def save(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snr", type=float, default=8.0)
    ap.add_argument("--wav", default=None, help="改用外部 wav 作为语音源")
    args = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    speech = load_speech(args.wav or os.path.join(os.path.dirname(HERE), "cq.wav"))
    nz = band_noise(len(speech)) * np.sqrt(np.mean(speech ** 2)) * 10 ** (-args.snr / 20) * np.sqrt(2)
    noisy = speech + nz
    mark = band_noise(MARK, seed=99, amp=0.1)
    prep = lambda s: np.concatenate([mark, np.zeros(PAD), s])
    ci, ni = prep(speech), prep(noisy)
    print(f"语音 {len(speech)/SR:.1f}s  带内SNR={args.snr}dB  clean={20*np.log10(np.sqrt(np.mean(speech**2))):.1f}dBFS")

    print("\n【生产链路: AGC=MED + bp1(300-2700) + panel=0.06】")
    print(f"{'配置':30s} {'peak':>6s} {'NR静音':>7s} {'语音Δ':>7s} {'LSD':>6s} {'(无NR)':>7s} {'抖动':>6s}")
    cases = [("NR2 OFF", dict(emnr=False)),
             ("EMNR 原样 (floor=0)", dict(emnr=True)),
             ("floor -18dB", dict(emnr=True, floor_db=-18.0)),
             ("floor -15dB", dict(emnr=True, floor_db=-15.0)),
             ("floor -12dB", dict(emnr=True, floor_db=-12.0)),
             ("floor -9dB", dict(emnr=True, floor_db=-9.0)),
             ("floor -6dB", dict(emnr=True, floor_db=-6.0)),
             ("dry混合 0.15 + floor-12", dict(emnr=True, floor_db=-12.0, dry=0.15)),
             ("AGC上限+20dB (floor-12)", dict(emnr=True, floor_db=-12.0, agc_top_db=20.0)),
             ("AGC上限+20dB (原样EMNR)", dict(emnr=True, agc_top_db=20.0)),
             ]
    for tag, kw in cases:
        y = run(ni, **kw)
        lag = align_lag(ni, y)
        m = metrics(ci, ni, y, lag, skip=0)
        save(os.path.join(OUTDIR, f"floor_{tag.replace(' ', '_').replace('/','')}.wav"), y)
        print(f"{tag:30s} {m['peak']:6.3f} {m['nr']:7.1f} {m['sp_delta']:7.1f} {m['lsd']:6.1f} "
              f"{m['lsd_noisy']:7.1f} {m['jitter']:6.1f}   lag={lag}")


if __name__ == "__main__":
    main()

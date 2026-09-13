#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EMNR 内部状态探针：直接 dump lambda_y / lambda_d / p / sigma2N / mask / alphaHat。
需要调试版库（含 emnr_dump 导出），通过环境变量 WDSP_LIB 指定。
"""
import ctypes, os, sys, time, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wdsp_wrapper as W

LIB = os.environ.get("WDSP_LIB", "/tmp/wdsp_dbg/libwdsp.dylib")
W._wdsp = ctypes.CDLL(LIB)
_wdsp = W._wdsp
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode  # noqa: E402

_dump = _wdsp.emnr_dump
_dump.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_int)]

SR, BS = 48000, 256


def dump(what, n=2049):
    buf = (ctypes.c_double * n)()
    msize = ctypes.c_int(0)
    _dump(ctypes.c_int(0), ctypes.c_int(what), buf, ctypes.byref(msize))
    return np.frombuffer(buf, dtype=np.float64, count=msize.value).copy()


def run(x, *, emnr=True, gm=0, npe=0, ae=1, psi=10.0, zeta=0.75, bp=None, agc=None, panel=1.0,
        snapshots=()):
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=False,
                      enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED)
    if agc is None:
        _wdsp.SetRXAAGCMode(ctypes.c_int(0), ctypes.c_int(0))
        _wdsp.SetRXAAGCFixed(ctypes.c_int(0), ctypes.c_double(0.0))
    else:
        _wdsp.SetRXAAGCMode(ctypes.c_int(0), ctypes.c_int(agc))
    _wdsp.SetRXAPanelGain1(ctypes.c_int(0), ctypes.c_double(panel))
    if emnr:
        _wdsp.SetRXAEMNRRun(ctypes.c_int(0), ctypes.c_int(1))
        _wdsp.SetRXAEMNRgainMethod(ctypes.c_int(0), ctypes.c_int(gm))
        _wdsp.SetRXAEMNRnpeMethod(ctypes.c_int(0), ctypes.c_int(npe))
        _wdsp.SetRXAEMNRaeRun(ctypes.c_int(0), ctypes.c_int(ae))
        _wdsp.SetRXAEMNRaePsi(ctypes.c_int(0), ctypes.c_double(psi))
        _wdsp.SetRXAEMNRaeZetaThresh(ctypes.c_int(0), ctypes.c_double(zeta))
    if bp:
        p.set_bandpass(*bp)
    else:
        _wdsp.SetRXABandpassRun(ctypes.c_int(0), ctypes.c_int(0))
    n = len(x) // BS
    out = np.zeros(n * BS)
    snaps = {}
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
        if b in snapshots:
            snaps[b] = {k: dump(k, 2049) for k in (0, 1, 2, 3, 4, 5, 6)}
        d = t0 + (b + 1) * BS / SR - time.monotonic()
        if d > 0:
            time.sleep(d)
    p.close()
    return out, snaps


def synth_speech(n=SR * 4):
    """确定性"类语音"：150Hz F0 的谐波 + 250/700/1800Hz 共振峰 + 音节包络"""
    t = np.arange(n) / SR
    f0 = 150.0
    sig = np.zeros(n)
    for h in range(1, 30):
        f = f0 * h
        if f > 3200:
            break
        # 共振峰包络
        g = 0.5 + 1.5 * np.exp(-((f - 700) / 300) ** 2) + 1.0 * np.exp(-((f - 1800) / 400) ** 2) \
            + 0.6 * np.exp(-((f - 250) / 150) ** 2)
        sig += g / h * np.sin(2 * np.pi * f * t + h)
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 3.5 * t) ** 2
    env = np.where(env > 0.35, env, 0.02)
    sig = sig * env
    return sig / np.max(np.abs(sig)) * 0.25


def main():
    fbin = np.fft.rfftfreq(4096, 1.0 / SR)
    print(f"库: {LIB}\n")

    print("=" * 100)
    print("【1】稳态单音 1kHz A=0.2 —— 纯信号、零噪声")
    t = np.arange(SR * 4) / SR
    tone = 0.2 * np.sin(2 * np.pi * 1000 * t)
    y, snaps = run(tone, snapshots=(600,))
    k = int(round(1000 / fbin[1]))
    s = snaps[600]
    print(f"  bin{k} (1kHz): lambda_y={s[0][k]:.4g}  lambda_d={s[1][k]:.4g}  gamma={s[0][k]/max(s[1][k],1e-30):.3f}"
          f"  p={s[3][k]:.4g}  mask={s[2][k]:.4g}")
    print(f"  全带: lambda_y 中位={np.median(s[0]):.3g}  lambda_d 中位={np.median(s[1]):.3g}  "
          f"mask 中位={np.median(s[2]):.4g} (={20*np.log10(max(np.median(s[2]),1e-12)):.1f}dB)  mask最大={s[2].max():.4g}")
    print(f"  sigma2N 中位={np.median(s[4]):.3g}   p 中位={np.median(s[3]):.3g}  prev_gamma 中位={np.median(s[5]):.3g}")

    print("=" * 100)
    print("【2】类语音合成信号（共振峰 + 音节包络），无噪声")
    sp = synth_speech()
    y, snaps = run(sp, snapshots=(600,))
    s = snaps[600]
    ly, ld, mk = s[0], s[1], s[2]
    strong = np.argsort(ly)[-40:]
    print(f"  最强 40 个 bin: lambda_y 中位={np.median(ly[strong]):.4g}  lambda_d 中位={np.median(ld[strong]):.4g}  "
          f"gamma 中位={np.median(ly[strong]/np.maximum(ld[strong],1e-30)):.3f}")
    print(f"  这些 bin 的 mask 中位={np.median(mk[strong]):.4g} ({20*np.log10(max(np.median(mk[strong]),1e-12)):.1f}dB)")
    print(f"  全带 mask 中位={np.median(mk):.4g}  mask>0.5 的 bin 数={np.sum(mk>0.5)}/{len(mk)}")
    # 主要共振峰 bin
    for f0 in (250, 700, 1800, 3000):
        kk = int(round(f0 / fbin[1]))
        w = slice(max(0, kk - 2), kk + 3)
        print(f"    {f0:5d}Hz: lambda_y={ly[w].mean():10.4g} lambda_d={ld[w].mean():10.4g} "
              f"gamma={ly[w].mean()/max(ld[w].mean(),1e-30):8.2f} mask={mk[w].mean():.4f}")

    print("=" * 100)
    print("【3】真实 SSB 语音（cq.wav）+ 带内噪声 10dB SNR")
    with wave.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cq.wav"), "rb") as w:
        d = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
        r = w.getframerate()
    n_out = int(len(d) * SR / r)
    X = np.fft.rfft(d); Y = np.zeros(n_out // 2 + 1, complex)
    kk = min(len(X), len(Y)); Y[:kk] = X[:kk]
    d = np.fft.irfft(Y, n_out) * (n_out / len(d))
    d = d / np.max(np.abs(d)) * 0.25
    rng = np.random.default_rng(1)
    nz = rng.standard_normal(len(d))
    N = np.fft.rfft(nz); fr = np.fft.rfftfreq(len(d), 1.0 / SR)
    N[(fr < 250) | (fr > 2900)] = 0
    nz = np.fft.irfft(N, len(d)); nz = nz / np.sqrt(np.mean(nz ** 2)) * np.sqrt(np.mean(d ** 2)) * 10 ** (-10 / 20) * np.sqrt(2)
    sig = d + nz
    y, snaps = run(sig, snapshots=(1000,))
    s = snaps[1000]
    ly, ld, mk = s[0], s[1], s[2]
    order = np.argsort(ly)
    print(f"  lambda_y 分位: p50={np.median(ly):.3g} p90={np.percentile(ly,90):.3g} p99={np.percentile(ly,99):.3g}")
    print(f"  lambda_d 分位: p50={np.median(ld):.3g} p90={np.percentile(ld,90):.3g} p99={np.percentile(ld,99):.3g}")
    print(f"  mask 分位: p10={np.percentile(mk,10):.4g} p50={np.median(mk):.4g} p90={np.percentile(mk,90):.4g} "
          f"max={mk.max():.4g}")
    hi = order[-100:]   # 语音最强的 100 bin
    lo = order[:100]    # 最弱的 100 bin
    print(f"  最强100bin: gamma 中位={np.median(ly[hi]/np.maximum(ld[hi],1e-30)):8.2f}  mask 中位={np.median(mk[hi]):.4f}")
    print(f"  最弱100bin: gamma 中位={np.median(ly[lo]/np.maximum(ld[lo],1e-30)):8.4f}  mask 中位={np.median(mk[lo]):.4f}")


if __name__ == "__main__":
    main()

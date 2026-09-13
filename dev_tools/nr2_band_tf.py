#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A5：SSB 带通频响（白噪激励，延迟对齐）。

验收（NR2=OFF，带通由 nbp0 承担）：300-2700 通带 |H| >= -8 dB（含 nbp0 固有 -6 dB）；
<200 Hz 与 >3.5 kHz 均 <= -30 dB。NR2=ON 只断言阻带（通带值即 NR 的降噪量）。
（修复前：nbp 固定在 -4150/-150，等效 150-4150 Hz，阻带只有 -6~-8 dB。）
"""
import ctypes, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode, _wdsp

SR, BS = 48000, 256
MARK = int(0.5 * SR)


def run(x, nr2):
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=nr2,
                      enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED)
    _wdsp.SetRXAAGCMode(ctypes.c_int(0), ctypes.c_int(0))
    _wdsp.SetRXAAGCFixed(ctypes.c_int(0), ctypes.c_double(0.0))
    _wdsp.SetRXAPanelGain1(ctypes.c_int(0), ctypes.c_double(1.0))
    p.set_bandpass(300.0, 2700.0)
    if nr2:
        p.set_nr2_level(1)              # MIN：把 NR 对频响测量的干扰降到最小
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


def tf(mark_in, x, y, n=8192, hop=2048):
    a = mark_in[:MARK]
    best, lag = -1e18, 0
    for d in range(0, 12000, 2):
        v = float(np.dot(a, y[d:d + MARK]))
        if v > best:
            best, lag = v, d
    win = np.hanning(n)
    nf = (min(len(x), len(y) - lag) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(nf)[:, None]
    X = np.fft.rfft(x[idx] * win, axis=1)
    Y = np.fft.rfft(y[idx + lag] * win, axis=1)
    Sxy = np.mean(X.conj() * Y, axis=0)
    Sxx = np.mean(np.abs(X) ** 2, axis=0)
    return np.fft.rfftfreq(n, 1.0 / SR), np.abs(Sxy / (Sxx + 1e-30)), lag


if __name__ == "__main__":
    rng = np.random.default_rng(7)
    mark = rng.standard_normal(MARK) * 0.1
    x = np.concatenate([mark, np.zeros(BS), rng.standard_normal(SR) * 0.1])
    ok = True
    for nr2 in (False, True):
        y = run(x, nr2)
        f, H, lag = tf(mark, x, y)

        def g(lo, hi):
            m = (f >= lo) & (f < hi)
            return 20 * np.log10(np.mean(H[m]) + 1e-12) if m.any() else -99.0

        lo_band, pass_band, hi_band = g(50, 200), g(300, 2700), g(3500, 7000)
        # NR2=OFF：带通形状必须成立（nbp0 承担带通）。
        # NR2=ON ：噪声探测下通带必然被 NR 压低，故只断言阻带，通带仅作参考。
        # 通带绝对电平含 nbp0 的固有 -6 dB（上游设计：NR 开启时由 bp1 的 +6 dB 补偿），
        # 生产链路里该电平差被 AGC 归一化，故只验"形状"：通带 >= -8 dB。
        if nr2:
            good = (lo_band <= -30) and (hi_band <= -30)
            note = f"(通带 {pass_band:+.1f} dB = NR 对噪声的降噪量，非形状判据)"
        else:
            good = (lo_band <= -30) and (pass_band >= -8) and (hi_band <= -30)
            note = "(通带含 nbp0 固有 -6 dB)"
        ok = ok and good
        print(f"NR2={'on ' if nr2 else 'off'} lag={lag:5d} | "
              f"<200Hz={lo_band:+6.1f} 300-2700={pass_band:+6.1f} "
              f">3.5k={hi_band:+6.1f} dB  {'PASS' if good else 'FAIL'} {note}")
    print("A5", "PASS" if ok else "FAIL")

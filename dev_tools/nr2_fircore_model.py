#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 numpy 逐行复现 WDSP 的 fir_bandpass + fircore 分区重叠保留算法，
判断 bp1 在 gain=1.0 时输出静音到底是
  (a) fir_bandpass 脉冲本身的问题，还是
  (b) fircore 的 mask 状态管理(cset/masks_ready)问题。
"""
import numpy as np

TWOPI = 2 * np.pi
PI = np.pi


def fir_bandpass(N, f_low, f_high, samplerate, wintype, rtype, scale):
    """WDSP fir.c::fir_bandpass 的等价实现（rtype=1 复数脉冲）"""
    c_impulse = np.zeros(2 * N, dtype=np.float64)   # 交错 I/Q
    ft = (f_high - f_low) / (2.0 * samplerate)
    ft_rad = TWOPI * ft
    w_osc = PI * (f_high + f_low) / samplerate
    m = 0.5 * (N - 1)
    delta = PI / m
    if N & 1:
        if rtype == 0:
            c_impulse[N >> 1] = scale * 2.0 * ft
        else:
            c_impulse[N - 1] = scale * 2.0 * ft
    for i in range((N + 1) // 2, N):
        j = N // 2 - 1 - (i - (N + 1) // 2)
        posi = i - m
        posj = j - m
        sinc = np.sin(ft_rad * posi) / (PI * posi)
        c = np.cos(delta * i)
        if wintype == 0:      # BH 4-term
            window = 0.21747 + c * (-0.45325 + c * (0.28256 + c * (-0.04672)))
        elif wintype == 1:    # BH 7-term
            window = (0.063964424114390378
                      + c * (-0.23993864599352804
                      + c * (0.35015956323820469
                      + c * (-0.24774111897080783
                      + c * (0.085438256055858031
                      + c * (-0.012320203369293225
                      + c * (0.00043778825791773474)))))))
        else:
            window = 1.0
        coef = scale * sinc * window
        if rtype == 0:
            c_impulse[i] = coef * np.cos(posi * w_osc)
            c_impulse[j] = coef * np.cos(posj * w_osc)
        else:
            c_impulse[2 * i] = coef * np.cos(posi * w_osc)
            c_impulse[2 * i + 1] = -coef * np.sin(posi * w_osc)
            c_impulse[2 * j] = coef * np.cos(posj * w_osc)
            c_impulse[2 * j + 1] = -coef * np.sin(posj * w_osc)
    return c_impulse


class FirCore:
    """WDSP firmin.c::FIRCORE 的等价实现（plan_fircore/calc_fircore/xfircore）"""

    def __init__(self, size, nc, impulse_iq, mp=False):
        self.size = size           # 256
        self.nc = nc               # 2048
        self.impulse = impulse_iq.copy()
        self.nfor = nc // size     # 8
        self.idxmask = self.nfor - 1
        self.buffidx = 0
        self.cset = 0
        self.masks_ready = 0
        self.fftin = np.zeros(size, dtype=complex)   # 只保留上一块（size），当前块放后 half
        self.fftout = [np.zeros(2 * size, dtype=complex) for _ in range(self.nfor)]
        self.fmask = [[np.zeros(2 * size, dtype=complex) for _ in range(self.nfor)] for _ in range(2)]
        self.accum = np.zeros(2 * size, dtype=complex)
        self.calc(flip=1)

    def calc(self, flip):
        imp = self.impulse.reshape(-1, 2)
        imp = imp[:, 0] + 1j * imp[:, 1]
        for i in range(self.nfor):
            # 对应 C: memcpy(&maskgen[2*size], &imp[2*size*i], size*sizeof(complex))
            # maskgen 是 double*，&maskgen[2*size] 即 complex 下标 size；前 size 个 complex 保持 0
            maskgen = np.zeros(2 * self.size, dtype=complex)
            maskgen[self.size:] = imp[self.size * i: self.size * i + self.size]
            # fftw 前向未归一化 == np.fft.fft；脉冲已含 scale=gain/(2*size)
            self.fmask[1 - self.cset][i] = np.fft.fft(maskgen)
        self.masks_ready = 1
        if flip:
            self.cset = 1 - self.cset
            self.masks_ready = 0

    def update(self):
        """setUpdate_fircore"""
        if self.masks_ready:
            self.cset = 1 - self.cset
            self.masks_ready = 0

    def process(self, blk_real):
        x = np.concatenate([self.fftin, np.zeros(self.size, dtype=complex)])
        if len(blk_real) != self.size:
            raise ValueError
        x[self.size:] = blk_real
        F = np.fft.fft(x)
        self.fftout[self.buffidx] = F
        k = self.buffidx
        acc = np.zeros(2 * self.size, dtype=complex)
        for j in range(self.nfor):
            acc += F * self.fmask[self.cset][j]
            k = (k + self.idxmask) & self.idxmask
        self.buffidx = (self.buffidx + 1) & self.idxmask
        self.fftin = x[self.size:].copy()
        return (2 * self.size) * np.fft.ifft(acc)   # fftw 逆变换同样未归一化


def measure(size=256, nc=2048, gain=1.0, fl=300.0, fh=2700.0, rate=48000, wintype=1, amp=0.2):
    imp = fir_bandpass(nc, fl, fh, rate, wintype, 1, gain / (2.0 * size))
    core = FirCore(size, nc, imp)
    nblk = rate // size
    out = np.zeros(nblk * size)
    t = np.arange(nblk * size) / rate
    x = amp * np.sin(2 * np.pi * 1000 * t)
    for b in range(nblk):
        acc = core.process(x[b * size:(b + 1) * size])
        out[b * size:(b + 1) * size] = acc[:size].real
    seg = out[rate // 2:]
    X = np.fft.rfft(seg * np.hanning(len(seg)))
    fr = np.fft.rfftfreq(len(seg), 1 / rate)
    k = np.argmin(abs(fr - 1000))
    a = 2 * abs(X[k]) / np.sum(np.hanning(len(seg)))
    return a, imp


def fir_summary(imp, rate=48000):
    c = imp.reshape(-1, 2)
    z = c[:, 0] + 1j * c[:, 1]
    return (np.abs(z).max(), np.sum(c[:, 0]), np.sum(c[:, 1]), np.sum(np.abs(z) ** 2))


for gain in (1.0, 2.0):
    a, imp = measure(gain=gain)
    mx, sI, sQ, e = fir_summary(imp)
    print(f"gain={gain:3.1f}: fircore 输出 1kHz 幅度={a:.6f} ({20*np.log10(max(a,1e-15)/0.2):+7.2f} dB)  "
          f"|h|max={mx:.3g} Σh_I={sI:.4g} Σh_Q={sQ:.4g} Σ|h|²={e:.4g}")
# 换 wintype / 频率再试
for wt in (0, 1):
    for (fl, fh) in ((300.0, 2700.0), (-4150.0, -150.0)):
        a, imp = measure(gain=1.0, wintype=wt, fl=fl, fh=fh)
        print(f"  wintype={wt} fl={fl:8.1f} fh={fh:8.1f} gain=1.0 → {20*np.log10(max(a,1e-15)/0.2):+8.2f} dB")

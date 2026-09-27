#!/usr/bin/env python3
"""联合最小二乘拟合天线阻抗模型 Z_ant(f) = R(f)+jX(f), 3.5-7.3MHz。

数据三类:
 1. bypass 扫频 SWR 幅值 (3.8-3.9 / 6.0-7.0 MHz), SWR<=1.05 的量化点剔除
 2. 学习库调谐锚点: 已学 (sw,ind,cap) 实现 swr_avg -> 模型预测的调谐后 SWR 应等于它
 3. 硬约束: 6.5MHz 谐振 Z=50+j0 (6.42-6.58 bypass SWR=1.00 平台)

输出: 60m 各频点的估计 Z_ant 与两种拓扑的最优 (ind,cap)。
"""
import json, math
import numpy as np
from scipy.optimize import least_squares

L_STEP = 0.1e-6
C_STEP = 10e-12
F_REF = 5.5e6


def z_in(f, z, sw, ind, cap):
    """给定天线阻抗与调谐器设置, 计算调谐器输入阻抗。"""
    w = 2 * math.pi * f
    L, C = ind * L_STEP, cap * C_STEP
    if sw == 0:  # LC: 串联 L, 负载侧并联 C
        return 1j * w * L + 1 / (1 / z + 1j * w * C)
    else:        # CL: 源侧并联 C, 串联 L
        return 1 / (1 / (1j * w * L + z) + 1j * w * C)


def swr_of(z):
    g = abs((z - 50) / (z + 50))
    if g >= 0.9999:
        return 1000.0 + 1000.0 * (g - 1)  # R<=0 非无源区, 给连续大梯度
    return (1 + g) / (1 - g)


def solve_net(f, z, sw):
    w = 2 * math.pi * f
    best = None
    for ind in range(0, 128):
        zl = 1j * w * ind * L_STEP
        for cap in range(0, 128):
            zc = 1j * w * cap * C_STEP
            if sw == 0:
                zin = zl + 1 / (1 / z + zc)
            else:
                zin = 1 / (1 / (zl + z) + zc)
            g = abs((zin - 50) / (zin + 50))
            s = (1 + g) / (1 - g)
            if best is None or s < best[2]:
                best = (ind, cap, s)
    return best


def load_data():
    bypass = []   # (f, swr)
    for fn in ('sweep_20260927_195943.json', 'sweep_20260927_200731.json',
               'sweep_20260927_200404.json'):
        d = json.load(open('antenna_sweeps/' + fn))
        for p in d['points']:
            s = p['swr']
            if s and 1.05 < s < 60:
                bypass.append((p['freq_khz'] * 1e3, s))
    anchors = []  # (f, sw, ind, cap, swr_avg, n)
    for r in json.load(open('atr1000_tuner.json'))['records']:
        if r.get('sample_count', 0) > 0 and 3.5e6 <= r['freq'] <= 7.3e6:
            anchors.append((r['freq'], r['sw'], r['ind'], r['cap'],
                            max(r['swr_avg'], 1.01), r['sample_count']))
    return bypass, anchors


def make_model(p):
    def zant(f):
        x = (f - F_REF) / 1e6
        R = p[0] + p[1] * x + p[2] * x * x
        X = p[3] + p[4] * x + p[5] * x * x
        return complex(R, X)
    return zant


def main():
    bypass, anchors = load_data()
    print(f'data: {len(bypass)} bypass SWR pts, {len(anchors)} tuner anchors')

    def resid(p):
        zant = make_model(p)
        r = []
        for f, s in bypass:
            r.append(math.log(swr_of(zant(f)) / s) * 1.0)
        for f, sw, ind, cap, s, n in anchors:
            pred = swr_of(z_in(f, zant(f), sw, ind, cap))
            wgt = min(1.0, math.sqrt(n) / 8.0)  # 大样本锚点权重高
            r.append(math.log(pred / s) * wgt)
        # 硬约束 6.5MHz 谐振
        z65 = zant(6.5e6)
        r.append((z65.real - 50) / 2.0)
        r.append(z65.imag / 2.0)
        # R 非负软约束 (定长)
        for f in (3.8e6, 4.5e6, 5.3e6, 6.0e6, 7.0e6):
            R = zant(f).real
            r.append(max(0.0, 1.0 - R) / 5.0)
        return r

    p0 = [25, 15, 5, 15, -20, 5]
    sol = least_squares(resid, p0, method='lm', max_nfev=20000)
    zant = make_model(sol.x)
    print('fit cost=%.4f  p=%s' % (sol.cost, np.round(sol.x, 2)))

    print('\n== 拟合残差抽查 (bypass) ==')
    for f, s in bypass[::10]:
        print(f'  {f/1e3:7.0f} kHz  meas={s:5.2f}  model={swr_of(zant(f)):5.2f}')
    print('== 锚点复核 ==')
    for f, sw, ind, cap, s, n in anchors:
        pred = swr_of(z_in(f, zant(f), sw, ind, cap))
        print(f'  {f/1e6:7.3f} sw{sw} L{ind}/C{cap}  learned_swr={s:4.2f}  model_pred={pred:4.2f}  Z={zant(f).real:5.1f}{zant(f).imag:+6.1f}j  n={n}')

    print('\n== 60m L/C 拟合 (联合模型) ==')
    for ft in (5.300e6, 5.330e6, 5.3515e6, 5.360e6, 5.3665e6, 5.370e6, 5.400e6):
        z = zant(ft)
        a, b = solve_net(ft, z, 0), solve_net(ft, z, 1)
        topo, best, alt = ('LC', a, b) if a[2] <= b[2] else ('CL', b, a)
        print(f'{ft/1e6:9.4f}  Z={z.real:6.1f}{z.imag:+6.1f}j  bypassSWR={swr_of(z):5.2f}  '
              f'-> {topo} L={best[0]} C={best[1]} (SWR~{best[2]:.2f})   [alt L{alt[0]}/C{alt[1]} swr{alt[2]:.2f}]')


if __name__ == '__main__':
    main()

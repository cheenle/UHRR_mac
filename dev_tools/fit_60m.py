#!/usr/bin/env python3
"""从 ATR-1000 学习库锚点反推天线复阻抗, 内插到 60m 并正解 L 网络。

拓扑 (atr1000_proxy 协议):
  sw=0 "LC": 源端 50Ω -- 串联 L --+-- 天线; 节点对地并联 C  (适用 R_load > 50 场景)
  sw=1 "CL": 源端 50Ω --+-- 串联 L -- 天线; 源端节点对地并联 C (适用 R_load < 50)

反推:
  sw=0: 1/Z_ant = 1/(50 - jωL) - jωC
  sw=1: Z_ant = 1/(1/50 - jωC) - jωL

步进: L = ind * 0.1µH, C = cap * 10pF (与 fit_tuner_params.py 一致)
"""
import json, math, cmath

L_STEP = 0.1e-6
C_STEP = 10e-12
F1 = 6.5e6  # 6.42-6.58 bypass SWR=1.00 平台 -> 串联谐振点


def z_ant_from_lc(f, ind, cap):
    w = 2 * math.pi * f
    L, C = ind * L_STEP, cap * C_STEP
    # 1/Z_ant = 1/(50 - jwL) - jwC
    y = 1 / (50 - 1j * w * L) - 1j * w * C
    return 1 / y


def z_ant_from_cl(f, ind, cap):
    w = 2 * math.pi * f
    L, C = ind * L_STEP, cap * C_STEP
    # Z_ant = 1/(1/50 - jwC) - jwL
    return 1 / (1 / 50 - 1j * w * C) - 1j * w * L


def solve_lc(f, z):
    """sw=0: 找 (L,C) 使 Z_in = jwL + 1/(1/z + jwC) = 50。返回 (ind, cap, swr) 最优整数解。"""
    w = 2 * math.pi * f
    # 解析: 令 Y = 1/z = G + jB。输入导纳匹配要求并联 C 后 1/(Y+jwC) 实部路径...
    # 直接数值搜索全量程取最优
    best = None
    for ind in range(0, 128):
        zl = 1j * w * ind * L_STEP
        for cap in range(0, 128):
            zc = 1j * w * cap * C_STEP
            zin = zl + 1 / (1 / z + zc)
            g = abs((zin - 50) / (zin + 50))
            swr = (1 + g) / (1 - g)
            if best is None or swr < best[2]:
                best = (ind, cap, swr)
    return best


def solve_cl(f, z):
    """sw=1: Z_in = 1/(1/(jwL+z) + jwC) = 50。"""
    w = 2 * math.pi * f
    best = None
    for ind in range(0, 128):
        zl = 1j * w * ind * L_STEP
        for cap in range(0, 128):
            zc = 1j * w * cap * C_STEP
            zin = 1 / (1 / (zl + z) + zc)
            g = abs((zin - 50) / (zin + 50))
            swr = (1 + g) / (1 - g)
            if best is None or swr < best[2]:
                best = (ind, cap, swr)
    return best


def swr_of(z):
    g = abs((z - 50) / (z + 50))
    return (1 + g) / (1 - g)


def main():
    db = json.load(open('atr1000_tuner.json'))['records']
    anchors = []  # (freq_Hz, Z, src)
    for r in db:
        if r.get('sample_count', 0) <= 0:
            continue
        f = r['freq']
        if not (3.5e6 <= f <= 7.3e6):
            continue
        if r['sw'] == 0:
            z = z_ant_from_lc(f, r['ind'], r['cap'])
        else:
            z = z_ant_from_cl(f, r['ind'], r['cap'])
        anchors.append((f, z, f"L{r['ind']}/C{r['cap']}/sw{r['sw']}/n{r['sample_count']}/swr{r['swr_avg']:.2f}"))
    # 强约束: 6500kHz 谐振
    anchors.append((6.5e6, 50 + 0j, 'RESONANCE(bypass SWR 1.00)'))
    anchors.sort()

    print('== 反推的天线阻抗锚点 ==')
    pts = []
    for f, z, src in anchors:
        print(f'{f/1e6:7.3f} MHz  R={z.real:7.1f}  X={z.imag:+7.1f}  |SWR|bypass={swr_of(z):6.2f}  [{src}]')
        pts.append((f, z))

    # 同频合并(中位), 然后线性内插
    import statistics
    merged = {}
    for f, z in pts:
        merged.setdefault(f, []).append(z)
    xs = sorted(merged)
    Rs = [statistics.median(z.real for z in merged[f]) for f in xs]
    Xs = [statistics.median(z.imag for z in merged[f]) for f in xs]

    def interp(f, ys):
        if f <= xs[0]:
            f0, f1 = xs[0], xs[1]; y0, y1 = ys[0], ys[1]
        elif f >= xs[-1]:
            f0, f1 = xs[-2], xs[-1]; y0, y1 = ys[-2], ys[-1]
        else:
            for i in range(len(xs) - 1):
                if xs[i] <= f <= xs[i + 1]:
                    f0, f1 = xs[i], xs[i + 1]; y0, y1 = ys[i], ys[i + 1]
                    break
        return y0 + (y1 - y0) * (f - f0) / (f1 - f0)

    # 内插形状校验: 与扫频 bypass SWR 幅值对比
    print('\n== 形状校验: 内插 Z -> bypass SWR vs 实测扫频 ==')
    for fn in ('sweep_20260927_195943.json', 'sweep_20260927_200731.json', 'sweep_20260927_200404.json'):
        d = json.load(open('antenna_sweeps/' + fn))
        for p in d['points'][:99]:
            f = p['freq_khz'] * 1e3
            if f < xs[0] or f > xs[-1]:
                continue
            z = complex(interp(f, Rs), interp(f, Xs))
            print(f'  {p["freq_khz"]:7.0f} kHz  meas={p["swr"]:5.2f}  interp={swr_of(z):5.2f}')

    print('\n== 60m 目标频率 L/C 拟合 ==')
    print(f'{"freq":>9} {"Z_ant est":>18} {"topo":>5} {"L":>4} {"C":>4} {"SWR_est":>7}  alt')
    targets = [5.300e6, 5.330e6, 5.3515e6, 5.360e6, 5.3665e6, 5.370e6, 5.400e6]
    for ft in targets:
        z = complex(interp(ft, Rs), interp(ft, Xs))
        a = solve_lc(ft, z)
        b = solve_cl(ft, z)
        if a[2] <= b[2]:
            best, alt, topo = a, b, 'LC'
        else:
            best, alt, topo = b, a, 'CL'
        alt_topo = 'CL' if topo == 'LC' else 'LC'
        print(f'{ft/1e6:9.4f}  {z.real:7.1f}{z.imag:+7.1f}j  {topo:>5} {best[0]:4d} {best[1]:4d} {best[2]:7.2f}  '
              f'{alt_topo} L{alt[0]}/C{alt[1]} swr{alt[2]:.2f}  bypassSWR={swr_of(z):.2f}')


if __name__ == '__main__':
    main()

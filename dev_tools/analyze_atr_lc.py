#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反演 atr1000_tuner.json 中每组 LC/CL 继电器参数所对应的天线负载阻抗。

换算（经通讯日志与协议文档双重确认）：
  L = ind x 0.1 uH   (7 位继电器, 0-12.7 uH)
  C = cap x 10 pF    (7 位继电器, 0-1270 pF)

拓扑约定（N7DDC 显示惯例，与本库学习数据自洽）：
  sw=0 "LC": 从电台侧看先串 L 后并 C -> C 在天线侧 (适用于 R_parallel > 50)
  sw=1 "CL": C 在电台侧并联, L 串向天线          (适用于 R_series  < 50)

阻抗反演（匹配后输入 = 50+j0）：
  LC: Z_L = 1 / (1/(50 - j*w*L) - j*w*C)
  CL: Z_L = 1/(0.02 - j*w*C) - j*w*L
"""
import json, cmath, math

with open('atr1000_tuner.json') as f:
    records = json.load(f)['records']

def band_of(f_mhz):
    for lo, hi, name in [(3.5,4.0,'80m'),(7.0,7.3,'40m'),(14.0,14.35,'20m'),
                         (18.068,18.168,'17m'),(21.0,21.45,'15m'),(24.89,24.99,'12m'),
                         (28.0,29.7,'10m')]:
        if lo <= f_mhz <= hi:
            return name
    return '??'

def swr_of(z):
    g = abs((z - 50) / (z + 50))
    return (1 + g) / (1 - g) if g < 1 else float('inf')

rows = []
for r in records:
    f = r['freq'] / 1e6
    w = 2 * math.pi * r['freq']
    L = r['ind'] * 0.1e-6
    C = r['cap'] * 10e-12
    if r['sw'] == 0:  # LC: C 在天线侧
        zl = 1 / (1 / (50 - 1j * w * L) - 1j * w * C)
    else:             # CL: C 在电台侧
        zl = 1 / (0.02 - 1j * w * C) - 1j * w * L
    R, X = zl.real, zl.imag
    if R <= 0:
        continue
    rp = (R * R + X * X) / R          # 并联等效电阻
    # 自洽性: LC 要求负载并联等效 >= 50; CL 要求负载串联电阻 <= 50
    ok = (rp >= 50) if r['sw'] == 0 else (R <= 50)
    q_net = math.sqrt(max(rp, 50) / 50 - 1) if r['sw'] == 0 else math.sqrt(max(50 / max(R, 1), 1) - 1)
    rows.append((f, band_of(f), 'LC' if r['sw'] == 0 else 'CL',
                 r['ind'] * 0.1, r['cap'] * 10, R, X, rp, swr_of(zl),
                 r['swr_avg'], r['sample_count'], q_net, ok))

rows.sort()
print(f"{'freq':>9} {'band':>4} {'net':>3} {'L_uH':>5} {'C_pF':>5} | "
      f"{'R':>7} {'X':>8} {'R_par':>7} {'裸SWR':>6} | {'学SWR':>5} {'n':>5} {'Q':>4} {'自洽':>3}")
for f, b, net, L, C, R, X, rp, s0, sl, n, q, ok in rows:
    print(f"{f:9.3f} {b:>4} {net:>3} {L:5.1f} {C:5.0f} | "
          f"{R:7.1f} {X:+8.1f} {rp:7.1f} {s0:6.2f} | {sl:5.2f} {n:5d} {q:4.1f} {'Y' if ok else 'N':>3}")

# 波段汇总
print('\n=== 波段汇总 ===')
from collections import defaultdict
bands = defaultdict(list)
for row in rows:
    bands[row[1]].append(row)
order = ['80m', '40m', '20m', '17m', '15m', '12m', '10m']
for b in order:
    rs = bands.get(b, [])
    if not rs:
        continue
    good = [r for r in rs if r[12]]  # 自洽
    print(f"\n[{b}] 记录 {len(rs)} 条, 自洽 {len(good)} 条")
    for r in rs:
        flag = '' if r[12] else '  <-- 与拓扑约定不自洽/存疑'
        print(f"  {r[0]:8.3f}MHz {r[2]} L={r[3]:.1f}uH C={r[4]:.0f}pF -> "
              f"Z={r[5]:.0f}{r[6]:+.0f}j  裸SWR={r[8]:.2f}{flag}")

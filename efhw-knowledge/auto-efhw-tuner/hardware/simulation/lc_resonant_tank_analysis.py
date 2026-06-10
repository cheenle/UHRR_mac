#!/usr/bin/env python3
"""
V3.0 Fuchs ATU — LC 谐振特性计算 + V2.0 对比
替代 ngspice AC 扫频 — 解析计算 f_res, XL, Q_u, Q_loaded, Eff, B_peak
关键发现: V3.0 点对点飞线杂散电容远低于 V2.0 PCB 走线 (4pF vs 10pF)
"""

import math

L2 = 2.058e-6
Z_in = 50
n = 7
k = 0.93
P_in = 100
A_e = 1.27e-4
N2 = 14

def Q_u(f):
    if f < 10e6: return 160
    elif f < 20e6: return 155 - (f - 10e6) * 1e-6
    else: return max(120, 145 - (f - 20e6) * 1.5e-6)

def f_res(C): return 1.0 / (2 * math.pi * math.sqrt(L2 * C))

def analyze(C_stray, label):
    print(f"\n{'='*70}")
    print(f"  {label}  (C_stray = {C_stray*1e12:.0f} pF)")
    print(f"{'='*70}")
    print(f"{'Cap(pF)':>8s} {'f_res(MHz)':>12s} {'XL(Ω)':>8s} {'Q_u':>6s} {'Q_L':>6s} {'Eff(%)':>8s} {'B_peak(mT)':>12s}")
    print("-" * 72)

    for C_pF in range(10, 520, 30):
        C = C_pF * 1e-12 + C_stray
        f = f_res(C)
        if f > 30e6 or f < 6.5e6: continue
        XL = 2 * math.pi * f * L2
        Qu = Q_u(f)
        Z_out_ideal = Z_in * (n * k)**2
        Q_loaded = Z_out_ideal / XL if XL > 0 else 50
        efficiency = (1 - Q_loaded / Qu) * 100 if Qu > 0 else 0
        V_in_peak = math.sqrt(P_in * Z_in) * math.sqrt(2)
        V_sec = V_in_peak * n
        B_peak = V_sec / (4.44 * f * N2 * A_e) * 1000
        print(f"{C_pF:8.0f} {f/1e6:12.2f} {XL:8.1f} {Qu:6.0f} {Q_loaded:6.1f} {efficiency:8.1f} {B_peak:12.1f}")

    print(f"\n{'Freq(MHz)':>10s} {'Optimal C(pF)':>15s}")
    print("-" * 30)
    for f_target in [7.100, 10.125, 14.200, 18.118, 21.200, 24.940, 28.500]:
        C_opt = 1.0 / ((2 * math.pi * f_target * 1e6)**2 * L2) * 1e12 - C_stray * 1e12
        note = "✓" if C_opt > 10 else "✗ C<10pF, 不可达"
        print(f"{f_target:10.3f} {C_opt:15.1f}   {note}")

# V3.0: 点对点飞线, 杂散电容极小
analyze(4e-12, "V3.0 Fuchs (point-to-point wiring, C_stray=4pF)")

# V2.0: PCB HV走线对地, 杂散电容较大
analyze(10e-12, "V2.0 STM32 (PCB HV trace, C_stray=10pF)")

# 限界情况: 杂散电容为0 (理论极限)
analyze(0, "Theoretical limit (C_stray=0, impossible in practice)")

# === 匝数比优化 ===
print(f"\n{'='*70}")
print(f"  匝数比优化: Efficiency vs Turns Ratio")
print(f"{'='*70}")
print(f"{'N2':>4s} {'Ratio':>7s} {'Z_out(Ω)':>10s} {'Eff@7MHz':>10s} {'Eff@14MHz':>10s} {'Eff@28MHz':>10s}")
print("-" * 55)
for N2_test in range(11, 17):
    n_test = N2_test / 2.0
    L2_test = (N2_test**2) * (10.5e-9)
    Z_out_test = Z_in * (n_test * k)**2
    for f_test, f_label in [(7.1e6, "@7MHz"), (14.2e6, "@14MHz"), (28.5e6, "@28MHz")]:
        XL_test = 2 * math.pi * f_test * L2_test
        Qu_test = Q_u(f_test)
        Q_loaded_test = Z_out_test / XL_test
        eff = (1 - Q_loaded_test / Qu_test) * 100
        if f_label == "@7MHz":
            print(f"{N2_test:4d} {n_test:5.1f}:1 {Z_out_test:10.0f} {eff:10.1f}", end="")
        elif f_label == "@14MHz":
            print(f" {eff:10.1f}", end="")
        else:
            print(f" {eff:10.1f}")

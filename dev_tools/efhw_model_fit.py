#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EFHW(49:1 UNUN) 天调侧参数推演与 SWR 曲线 — 基于 ATR-1000 最近 15 天学习数据

方法（2026-09-27 版，放弃全局物理拟合，改为实测锚定）:
  1. 学习记录 -> 天调端口阻抗 (L=ind*0.1uH, C=cap*10pF; LC=C在天线侧, CL=C在电台侧)
     LC: Z = 1 / (1/(50 - j*w*L) - j*w*C)   CL: Z = 1/(0.02 - j*w*C) - j*w*L
  2. 波段内局部线性模型 Z(f) = a + b*f  (40m/20m/15m, 锚点密集, 可信)
  3. 全局参考模型 (开路stub + 49:1 + Lm//Cs2 + 馈线) 仅用于带间形状的虚线参考
  4. ATR-1000 量化网络全搜索 -> 各频点可达 SWR 与推荐 LC 参数

注意: 学习记录中同一组 (L,C) 覆盖一段频率时, 反演阻抗在该段内恒定
(量化假象), 局部斜率只由不同组合之间的差异决定。
"""
import json, math, time, os
import numpy as np

C0 = 299792458.0
VF_COAX = 0.66
NOW = time.time()
CUT = NOW - 15 * 86400

# ---------- 1. 最近 15 天记录 -> 阻抗 ----------
# 合并 mrrc_modern 的学习库: 同一台 ATR-1000 + 同一根 EFHW (40/20/15m 参数两侧一致可证)
recs = json.load(open('atr1000_tuner.json'))['records']
MODERN_JSON = '../mrrc_modern/atr1000_tuner.json'
try:
    recs = recs + json.load(open(MODERN_JSON))['records']
    print(f"(已合并 {MODERN_JSON})")
except FileNotFoundError:
    pass
fresh = []
for r in recs:
    if r['last_update'] < CUT:
        continue
    # 排除 mrrc_modern 3850kHz 假学习记录: L=2/C=12 是 TX 停后 ~1s 的 SWR=1.00 误采
    # (09-26 06:38 同参数复测 SWR=13.42, full tune 最好仅 3.86)
    if r['freq'] == 3850000 and r['ind'] == 2 and r['cap'] == 12:
        print("  ! 排除 3850kHz L=2/C=12 假学习记录 (TX停后误采, 见交叉分析报告 §2)")
        continue
    f = r['freq']
    w = 2 * math.pi * f
    L = r['ind'] * 0.1e-6
    Cc = r['cap'] * 10e-12
    if r['sw'] == 0:
        z = 1 / (1 / (50 - 1j * w * L) - 1j * w * Cc)
    else:
        z = 1 / (0.02 - 1j * w * Cc) - 1j * w * L
    if z.real <= 0:
        continue
    fresh.append(dict(f=f, z=complex(z), n=r['sample_count'], r=r,
                      date=time.strftime('%m-%d', time.localtime(r['last_update']))))
fresh.sort(key=lambda x: x['f'])
print(f"最近15天锚点 {len(fresh)} 个 (cutoff {time.strftime('%m-%d', time.localtime(CUT))})")
for it in fresh:
    weak = '  (弱: n<5)' if it['n'] < 5 else ''
    print(f"  {it['f']/1e6:8.3f}MHz {'LC' if it['r']['sw']==0 else 'CL'} "
          f"L={it['r']['ind']*0.1:4.1f} C={it['r']['cap']*10:4.0f}pF n={it['n']:4d} "
          f"swr={it['r']['swr_avg']:.2f} {it['date']}  Z={it['z'].real:6.1f}{it['z'].imag:+7.1f}j{weak}")

def swr(z):
    z = np.asarray(z, dtype=complex)
    g = np.abs((z - 50) / (z + 50))
    return (1 + g) / (1 - g)

# ---------- 2. 波段内局部线性模型 ----------
def band_anchors(lo, hi, nmin=5):
    return [(it['f'], it['z'], it['n']) for it in fresh
            if lo <= it['f'] / 1e6 <= hi and it['n'] >= nmin]

local = {}
for name, lo, hi in [('40m', 7.0, 7.3), ('20m', 14.0, 14.35), ('15m', 21.0, 21.45)]:
    pts = band_anchors(lo, hi)
    if len(pts) >= 3:
        f = np.array([p[0] for p in pts])
        z = np.array([p[1] for p in pts])
        w = np.sqrt(np.array([p[2] for p in pts], float))
        # 按不同 (L,C) 组合去重后的加权线性拟合
        br = np.polyfit(f / 1e6, z.real, 1, w=w)
        bi = np.polyfit(f / 1e6, z.imag, 1, w=w)
        local[name] = (br, bi, lo, hi)
        print(f"\n局部模型 [{name}]: R = {br[0]:+.2f}/MHz {br[1]:+.1f},  X = {bi[0]:+.2f}/MHz {bi[1]:+.1f}")

def local_z(name, f_mhz):
    br, bi, _, _ = local[name]
    return complex(np.polyval(br, f_mhz), np.polyval(bi, f_mhz))

# ---------- 3. 全局参考模型 (仅带间参考, Lm 固定 4.3uH = 2^2 x AL(2643251002)=1075nH) ----------
# 用户实测 UNUN: Fair-Rite 2643251002 (43材料), 2:14 匝 -> 磁化电感 2^2*1075nH = 4.3uH
LM_H = 4.3e-6
from scipy.optimize import differential_evolution, least_squares

FA = np.array([it['f'] for it in fresh if it['n'] >= 5])
ZA = np.array([it['z'] for it in fresh if it['n'] >= 5])
WA = np.sqrt(np.array([it['n'] for it in fresh if it['n'] >= 5], float))

def gmodel(p, f):
    f1, z0w, al, q, cs2_pf, d = p
    w = 2 * np.pi * f
    x = f / (f1 * 1e6)
    g = al + 1j * np.pi * x * (1 + q * (x - 1))
    z_wire = z0w / np.tanh(g)
    z_wire2 = 1 / (1 / z_wire + 1j * w * cs2_pf * 1e-12)
    z_unun = 1 / (1 / (1j * w * LM_H) + 49.0 / z_wire2)
    t = np.tan(w * d / (C0 * VF_COAX))
    return 50.0 * (z_unun + 1j * 50 * t) / (50 + 1j * z_unun * t)

def gresid(p):
    dz = (gmodel(p, FA) - ZA) / (50 + np.abs(ZA))
    return np.concatenate([dz.real, dz.imag]) * np.repeat(WA, 2)

gbounds = [(6.90, 7.20), (300, 900), (0.05, 0.80), (-0.03, 0.03), (0.0, 30.0), (2.0, 80.0)]
de = differential_evolution(lambda p: float(np.sum(gresid(p) ** 2)), gbounds,
                            maxiter=1000, popsize=18, tol=1e-11, seed=42, polish=False)
gsol = least_squares(gresid, de.x, bounds=([b[0] for b in gbounds], [b[1] for b in gbounds]),
                     max_nfev=60000)
gp = gsol.x
print(f"\n全局参考模型: f1={gp[0]:.3f}MHz Z0w={gp[1]:.0f} al={gp[2]:.3f} "
      f"q={gp[3]*100:+.2f}% Cs2={gp[4]:.1f}pF d={gp[5]:.1f}m (cost={gsol.cost:.2f}, 仅参考)")

# ---------- 4. ATR-1000 量化网络全搜索 ----------
Ls = np.arange(0, 128) * 0.1e-6
Cs = np.arange(0, 128) * 10e-12
LL, CC = np.meshgrid(Ls, Cs, indexing='ij')

def best_tune(f, zl):
    w = 2 * np.pi * f
    zin_lc = 1j * w * LL + 1 / (1j * w * CC + 1 / zl)
    zin_cl = 1 / (1j * w * CC + 1 / (1j * w * LL + zl))
    s_lc = swr(zin_lc.ravel()).reshape(LL.shape)
    s_cl = swr(zin_cl.ravel()).reshape(LL.shape)
    i_lc = np.unravel_index(np.argmin(s_lc), s_lc.shape)
    i_cl = np.unravel_index(np.argmin(s_cl), s_cl.shape)
    if s_lc[i_lc] <= s_cl[i_cl]:
        return float(s_lc[i_lc]), ('LC', i_lc[0] * 0.1, i_lc[1] * 10)
    return float(s_cl[i_cl]), ('CL', i_cl[0] * 0.1, i_cl[1] * 10)

# ---------- 5. 关键频点推演 (直接锚点 > 波段内局部模型 > 全局模型外推) ----------
def z_at(f_mhz):
    # 50kHz 内有直接测量锚点时, 锚点优先 (含弱锚点, 弱锚点单独标注)
    near = [it for it in fresh if abs(it['f'] / 1e6 - f_mhz) <= 0.05]
    if near:
        it = max(near, key=lambda x: x['n'])
        return it['z'], ('弱锚点' if it['n'] < 5 else '直接锚点')
    for name, (_, _, lo, hi) in local.items():
        if lo <= f_mhz <= hi:
            return local_z(name, f_mhz), '局部锚定'
    return complex(gmodel(gp, np.array([f_mhz * 1e6]))[0]), '外推(参考模型)'

keys = [3.55, 3.75, 3.90, 7.03, 7.045, 7.074, 10.10, 10.12,
        14.074, 14.20, 14.27, 18.10, 21.074, 21.20, 21.40, 24.915, 28.074, 28.50, 29.00]
keyrows = []
print(f"\n{'MHz':>7} {'Z(Ω)':>16} {'裸SWR':>6} {'可达SWR':>7}  推荐LC参数          来源")
for m in keys:
    z, src = z_at(m)
    s0 = float(swr(z))
    s1, (net, luh, cpf) = best_tune(m * 1e6, z)
    keyrows.append((m, z, s0, s1, net, luh, cpf, src))
    print(f"{m:7.3f} {z.real:7.1f}{z.imag:+8.1f}j {s0:6.2f} {s1:7.2f}  "
          f"{net} L={luh:4.1f}uH C={cpf:4.0f}pF   {src}")

# ---------- 6. 波段指标: SWR<=2 带宽 / X=0 谐振外推 ----------
print("\n波段内指标 (局部模型):")
band_metrics = {}
for name, (br, bi, lo, hi) in local.items():
    ff = np.linspace(lo, hi, 2001)
    zz = np.polyval(br, ff) + 1j * np.polyval(bi, ff)
    ss = swr(zz)
    ok = ff[ss <= 2.0]
    # X=0 外推 (谐振方向指示)
    if bi[0] != 0:
        f_x0 = -bi[1] / bi[0]
    else:
        f_x0 = float('nan')
    band_metrics[name] = dict(swr_min=float(ss.min()), f_at_swr_min=float(ff[np.argmin(ss)]),
                              swr_at_lo=float(ss[0]), swr_at_hi=float(ss[-1]),
                              s2_lo=float(ok.min()) if len(ok) else None,
                              s2_hi=float(ok.max()) if len(ok) else None,
                              f_x0_extrap=float(f_x0))
    print(f"  [{name}] 裸SWR min={ss.min():.2f}@{ff[np.argmin(ss)]:.3f}MHz, "
          f"带缘 {ss[0]:.2f}/{ss[-1]:.2f}, "
          f"SWR≤2区间: {f'{ok.min():.3f}-{ok.max():.3f}MHz' if len(ok) else '无'}, "
          f"X=0外推: {f_x0:.2f}MHz")

# ---------- 7. 绘图 ----------
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

freqs = np.linspace(7e6, 30e6, 921)
fm = freqs / 1e6
z_ref = gmodel(gp, freqs)
swr_ref = swr(z_ref)
swr_tuned_ref = np.array([best_tune(f, z)[0] for f, z in zip(freqs, z_ref)])

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11.5, 8.5), sharex=True,
                               gridspec_kw={'height_ratios': [3, 2]})
bands = [(7.0, 7.3, '40m'), (10.1, 10.15, '30m'), (14.0, 14.35, '20m'),
         (18.068, 18.168, '17m'), (21.0, 21.45, '15m'), (24.89, 24.99, '12m'), (28.0, 29.7, '10m')]
for ax in (ax1, ax2):
    for lo, hi, name in bands:
        ax.axvspan(lo, hi, color='orange', alpha=0.10)
    ax.grid(alpha=0.3)

ax1.plot(fm, np.minimum(swr_ref, 12), color='steelblue', ls='--', lw=1.2,
         label='裸 SWR 参考模型（带间未锚定，仅形状参考）')
for name, (br, bi, lo, hi) in local.items():
    ff = np.linspace(lo, hi, 300)
    zz = np.polyval(br, ff) + 1j * np.polyval(bi, ff)
    ax1.plot(ff, swr(zz), 'b-', lw=2.2,
             label='裸 SWR 局部锚定模型' if name == '40m' else None)
ax1.plot(fm, swr_tuned_ref, 'g-', lw=1.2, label='ATR-1000 调谐后可达 SWR（量化全搜索, 参考模型）')
fa_mhz = np.array([it['f'] for it in fresh]) / 1e6
za = np.array([it['z'] for it in fresh])
na = np.array([it['n'] for it in fresh])
ax1.scatter(fa_mhz, swr(za), s=18 + 6 * np.sqrt(na), c='r', zorder=5,
            label='学习点反演裸 SWR（点径∝√样本数）')
for m, lab in [(7.074, 'FT8'), (14.074, 'FT8'), (21.074, 'FT8'), (28.074, 'FT8')]:
    ax1.axvline(m, color='purple', ls=':', lw=0.8, alpha=0.6)
ax1.axhline(2.0, color='gray', ls='--', lw=0.8)
ax1.text(29.75, 2.08, 'SWR=2', fontsize=8, color='gray')
ax1.axhline(1.5, color='gray', ls=':', lw=0.8)
ax1.text(29.75, 1.53, 'SWR=1.5', fontsize=8, color='gray')
ax1.set_ylim(0.9, 12)
ax1.set_ylabel('SWR（天调端口）')
ax1.set_title('EFHW（~21m 导线 + 新 49:1 UNUN）天调端口 SWR 曲线 7–30MHz\n'
              f'数据: ATR-1000 双学习库(mrrc+mrrc_modern)最近15天{len(fresh)}条锚点 | 80m 旧记录已作废(更换UNUN)，不参与')
ax1.legend(loc='upper right', fontsize=8.5)

ax2.plot(fm, z_ref.real, color='steelblue', ls='--', lw=1.0)
ax2.plot(fm, z_ref.imag, color='salmon', ls='--', lw=1.0)
for name, (br, bi, lo, hi) in local.items():
    ff = np.linspace(lo, hi, 300)
    ax2.plot(ff, np.polyval(br, ff), 'b-', lw=2.0, label='R 局部锚定' if name == '40m' else None)
    ax2.plot(ff, np.polyval(bi, ff), 'r-', lw=2.0, label='X 局部锚定' if name == '40m' else None)
ax2.scatter(fa_mhz, za.real, c='b', s=14, alpha=0.6)
ax2.scatter(fa_mhz, za.imag, c='r', s=14, alpha=0.6)
ax2.axhline(0, color='k', lw=0.5)
ax2.axhline(50, color='gray', ls=':', lw=0.6)
ax2.set_ylim(-300, 300)
ax2.set_xlabel('频率 (MHz)')
ax2.set_ylabel('天调端口阻抗 (Ω)')
ax2.legend(fontsize=8.5)
plt.tight_layout()
os.makedirs('docs/current/antenna', exist_ok=True)
out_png = 'docs/current/antenna/efhw_swr_7-30mhz_2026-09-27.png'
plt.savefig(out_png, dpi=140)
print(f"\n图: {out_png}")

with open('docs/current/antenna/efhw_model_keypoints_2026-09-27.json', 'w') as fp:
    json.dump({
        'generated': time.strftime('%Y-%m-%d %H:%M %z'),
        'window_days': 15,
        'anchors': [{'mhz': it['f'] / 1e6, 'sw': it['r']['sw'], 'ind': it['r']['ind'],
                     'cap': it['r']['cap'], 'n': it['n'], 'swr_avg': it['r']['swr_avg'],
                     'z_real': it['z'].real, 'z_imag': it['z'].imag, 'date': it['date']}
                    for it in fresh],
        'local_models': {k: {'r_slope': v[0][0], 'r_int': v[0][1],
                             'x_slope': v[1][0], 'x_int': v[1][1]} for k, v in local.items()},
        'band_metrics': band_metrics,
        'global_ref': {'f1_mhz': gp[0], 'z0w': gp[1], 'alpha_l': gp[2], 'q': gp[3],
                       'cs2_pf': gp[4], 'coax_m': gp[5], 'cost': gsol.cost},
        'keypoints': [{'mhz': m, 'z_real': z.real, 'z_imag': z.imag, 'swr_bare': s0,
                       'swr_tuned': s1, 'net': net, 'l_uh': l, 'c_pf': c,
                       'source': src} for m, z, s0, s1, net, l, c, src in keyrows],
    }, fp, indent=2, ensure_ascii=False,
       default=lambda o: o.item() if hasattr(o, 'item') else float(o))
print("数据: docs/current/antenna/efhw_model_keypoints_2026-09-27.json")

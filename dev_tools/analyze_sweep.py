#!/usr/bin/env python3
"""天线扫频结果分析：裸 SWR 曲线、谐振点提取、与模型对比。

用法: venv/bin/python dev_tools/analyze_sweep.py [sweep.json]
默认读 antenna_sweeps/latest.json。
输出: antenna_sweeps/analysis_<ts>.png + 终端摘要
"""
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

BAND_ORDER = ["40m", "30m", "20m", "17m", "15m", "12m", "10m"]


def load_sweep(path):
    with open(path) as f:
        d = json.load(f)
    return d


def find_resonances(freqs, swrs, band):
    """局部最小值 + 全局最低"""
    res = []
    for i in range(1, len(swrs) - 1):
        if swrs[i] <= swrs[i - 1] and swrs[i] < swrs[i + 1] and swrs[i] < 3.0:
            res.append((freqs[i], swrs[i]))
    if not res and len(swrs):
        i = int(np.argmin(swrs))
        res.append((freqs[i], swrs[i]))
    return res


def split_dropouts(points):
    """把孤立 SWR<=1.01 且同波段相邻点都 >1.35 的点判为电表反射通道掉读。

    真谐振在 10kHz 步进下必然平滑过渡（15m 的 1.00 平台邻点都在 1.0-1.3，
    不会被误杀）；掉读点的特征是在 2.x-5.x 的背景里突然插一根 1.00。
    相邻的多个掉读点会互相"掩护"，所以按连续 1.00 游程处理：
    游程长度 ≤3 且游程两侧最近的非 1.00 点都 >1.35 → 整个游程判掉读。
    （真谐振平台如 15m 有 16 点宽、边缘渐变，30kHz 内从 2.7 跳到 1.00
    再跳回去在这副天线上物理不可能。）
    返回 (有效点, 掉读点)。
    """
    bands = {}
    for p in points:
        bands.setdefault(p["band"], []).append(p)
    drop_ids = set()
    for band, ps in bands.items():
        # 无载波点（功率 <1W）直接无效
        for p in ps:
            if p.get("power_w", 0) < 1.0:
                drop_ids.add(id(p))
        n = len(ps)
        i = 0
        while i < n:
            if ps[i]["swr"] > 1.01:
                i += 1
                continue
            j = i
            while j + 1 < n and ps[j + 1]["swr"] <= 1.01:
                j += 1
            run = ps[i:j + 1]
            lo = ps[i - 1]["swr"] if i > 0 else None
            hi = ps[j + 1]["swr"] if j + 1 < n else None
            neighbors = [x for x in (lo, hi) if x is not None]
            if len(run) <= 3 and neighbors and min(neighbors) > 1.35:
                drop_ids.update(id(p) for p in run)
            i = j + 1
    valid = [p for p in points if id(p) not in drop_ids]
    dropped = [p for p in points if id(p) in drop_ids]
    return valid, dropped


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "antenna_sweeps/latest.json"
    d = load_sweep(path)
    # 已清洗文件里掉读点被移到 dropped_points；未清洗的（旧）文件现场过滤
    raw_pts = d["points"]
    valid_pts, dropped_pts = split_dropouts(raw_pts)
    if dropped_pts:
        print(f"已剔除电表掉读点 {len(dropped_pts)} 个"
              f"（孤立 SWR=1.00，邻点均 >1.35）")
    pts = valid_pts
    note = d.get("note", "")
    ts = d.get("started_at", "")

    bands = {}
    for p in pts:
        bands.setdefault(p["band"], []).append(p)

    fig, axes = plt.subplots(4, 2, figsize=(15, 16))
    axes = axes.flatten()
    summary = []
    for ax, band in zip(axes, BAND_ORDER):
        if band not in bands:
            ax.set_visible(False)
            continue
        ps = sorted(bands[band], key=lambda p: p["freq_khz"])
        f = np.array([p["freq_khz"] / 1000.0 for p in ps])
        s = np.array([p["swr"] for p in ps])
        pw = np.array([p["power_w"] for p in ps])
        ax.plot(f, s, "o-", ms=3, lw=1.2, color="#1f77b4")
        ax.axhline(1.5, color="g", ls="--", lw=0.8, alpha=0.7)
        ax.axhline(2.0, color="orange", ls="--", lw=0.8, alpha=0.7)
        ax.axhline(3.0, color="r", ls="--", lw=0.8, alpha=0.7)
        ax.set_title(f"{band}  ({f[0]:.3f}-{f[-1]:.3f} MHz)", fontsize=11)
        ax.set_ylabel("SWR")
        ax.grid(alpha=0.3)
        ax.set_ylim(0, max(4, min(s.max() * 1.1, 25)))
        res = find_resonances(f * 1000, s, band)
        for rf, rs in res:
            ax.annotate(f"{rf/1000:.3f}M\nSWR={rs:.2f}", (rf / 1000, rs),
                        textcoords="offset points", xytext=(0, 8),
                        fontsize=8, ha="center", color="darkred")
        imin = int(np.argmin(s))
        summary.append((band, f[0], f[-1], f[imin], s[imin],
                        float(np.median(s)), float(np.median(pw)),
                        int((s <= 1.5).sum()), int((s <= 2.0).sum()), len(s)))
    for ax in axes[len(bands):]:
        ax.set_visible(False)
    fig.suptitle(f"EFHW 裸 SWR 扫频（ATR-1000 bypass） {ts}  {note}", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out_png = path.replace(".json", "_analysis.png")
    fig.savefig(out_png, dpi=110)
    print(f"图已保存: {out_png}\n")

    print(f"{'波段':<5} {'范围MHz':>17} {'最低SWR点':>18} {'SWR中位':>7} {'功率中位W':>9} {'≤1.5':>5} {'≤2.0':>5} {'点数':>4}")
    for band, f0, f1, bf, bs, med, pw, n15, n20, n in summary:
        print(f"{band:<5} {f0:>7.3f}-{f1:<7.3f} {bf:>7.3f}M SWR={bs:<5.2f} {med:>7.2f} {pw:>9.1f} "
              f"{n15:>3}/{n:<3} {n20:>3}/{n:<3} {n:>4}")

    # 谐振点汇总（跨段）
    print("\n各段内谐振/最低点:")
    for band in BAND_ORDER:
        if band not in bands:
            continue
        ps = sorted(bands[band], key=lambda p: p["freq_khz"])
        f = np.array([p["freq_khz"] for p in ps])
        s = np.array([p["swr"] for p in ps])
        for rf, rs in find_resonances(f, s, band):
            print(f"  {band}: {rf/1000:.4f} MHz  SWR={rs:.2f}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""天调参数拟合填充：为没有学习记录的频点生成拟合 (sw, ind, cap)。

依据:
- atr1000_tuner.json 里实测学习锚点（sample_count 加权，坏点剔除）
- 同波段内 ind/cap 随频率近似线性，用加权最小二乘拟合；
  单锚点波段做常数延拓；无锚点波段（30m/80m）不填，留待真实调谐学习。

安全设计:
- 只写空位（±5kHz 内无记录的 10kHz 栅格点），绝不动实测记录
- 拟合记录带 "source": "fit" 标记 + sample_count=0 + needs_verify=true，
  真实学习（learn()）会自然覆盖；拟合偏差大时 SWR 守卫会触发完整调谐并学习纠正
- 写入前备份原文件，原子替换

用法:
  venv/bin/python dev_tools/fit_tuner_params.py            # dry-run，只打印
  venv/bin/python dev_tools/fit_tuner_params.py --apply    # 实际写入
"""
import json
import os
import shutil
import sys
import time

TUNER_JSON = "atr1000_tuner.json"

# 业余波段 (起止 kHz, 含端点)
BANDS = {
    "40m": (7000, 7300),
    "30m": (10100, 10150),
    "20m": (14000, 14350),
    "17m": (18068, 18168),
    "15m": (21000, 21450),
    "12m": (24890, 24990),
    "10m": (28000, 29700),
}
GRID_KHZ = 10          # 填充栅格（find_best ±5kHz 必命中）
MIN_SAMPLES_ANCHOR = 5  # 锚点最少样本数，低于此视为不可靠


def band_of(freq_khz):
    for name, (a, b) in BANDS.items():
        if a <= freq_khz <= b:
            return name
    return None


def wlinear_fit(xs, ys, ws):
    """加权线性拟合 y = a*x + b；点数不足时退化为加权均值"""
    n = len(xs)
    if n == 0:
        return None
    if n == 1:
        return (0.0, ys[0])
    sw = sum(ws)
    mx = sum(w * x for x, w in zip(xs, ws)) / sw
    my = sum(w * y for y, w in zip(ys, ws)) / sw
    sxx = sum(w * (x - mx) ** 2 for x, w in zip(xs, ws))
    if sxx < 1e-9:
        return (0.0, my)
    sxy = sum(w * (x - mx) * (y - my) for x, y, w in zip(xs, ys, ws))
    a = sxy / sxx
    return (a, my - a * mx)


def reject_outliers(anchors):
    """同波段内按 ind 残差剔除离群锚点（如扫频污染产生的假学习）。
    返回 (可信锚点, 被剔除锚点)。锚点 <3 个时不剔除。"""
    if len(anchors) < 3:
        return anchors, []
    xs = [a["freq"] / 1000.0 for a in anchors]
    for field in ("ind", "cap"):
        ys = [a[field] for a in anchors]
        ws = [max(1, a.get("sample_count", 1)) ** 0.5 for a in anchors]
        fit = wlinear_fit(xs, ys, ws)
        if fit is None:
            break
        a_, b_ = fit
        resid = [abs(y - (a_ * x + b_)) for x, y in zip(xs, ys)]
        med = sorted(resid)[len(resid) // 2] or 1.0
        keep, drop = [], []
        for rec, r in zip(anchors, resid):
            (keep if r <= max(3.0 * med, 4.0) else drop).append(rec)
        if keep and len(keep) >= len(anchors) - 1 or not keep:
            # 一次剔太多就不剔（防止误杀）
            if keep:
                return keep, drop
            return anchors, []
        anchors = keep
        xs = [a["freq"] / 1000.0 for a in anchors]
    return anchors, drop


def main():
    apply = "--apply" in sys.argv
    with open(TUNER_JSON) as f:
        db = json.load(f)
    records = db["records"]
    by_band = {}
    for r in records:
        b = band_of(r["freq"] // 1000)
        if b:
            by_band.setdefault(b, []).append(r)

    existing_keys = {str(r["freq"] // 1000) for r in records}
    new_records = []
    report = []

    for band, (lo, hi) in BANDS.items():
        anchors = [r for r in by_band.get(band, [])
                   if r.get("sample_count", 0) >= MIN_SAMPLES_ANCHOR
                   and not (r["ind"] == 0 and r["cap"] == 0)]
        anchors_all = by_band.get(band, [])
        if not anchors:
            report.append((band, 0, 0, "跳过（无可信锚点）", None, None))
            continue
        # 同一波段内 sw 配置须一致，否则拟合无意义（取样本数最多的配置）
        sw_groups = {}
        for r in anchors:
            sw_groups.setdefault(r["sw"], []).append(r)
        sw_mode = max(sw_groups, key=lambda k: sum(x["sample_count"] for x in sw_groups[k]))
        anchors = sw_groups[sw_mode]
        anchors, dropped = reject_outliers(anchors)
        if not anchors:
            report.append((band, 0, 0, f"跳过（sw={sw_mode} 配置锚点均被剔除）", None, None))
            continue

        xs = [r["freq"] / 1000.0 for r in anchors]
        ws = [max(1, r["sample_count"]) ** 0.5 for r in anchors]
        fi = wlinear_fit(xs, [r["ind"] for r in anchors], ws)
        fc = wlinear_fit(xs, [r["cap"] for r in anchors], ws)

        filled = 0
        fk = lo
        while fk <= hi:
            key = str(fk)
            # 附近 ±5kHz 有实测记录就不填
            if not any(str(fk + d) in existing_keys for d in range(-5, 6)):
                ind = int(round(fi[0] * fk + fi[1]))
                cap = int(round(fc[0] * fk + fc[1]))
                ind = max(0, min(128, ind))
                cap = max(0, min(130, cap))
                if not (ind == 0 and cap == 0):
                    new_records.append({
                        "freq": fk * 1000,
                        "sw": sw_mode,
                        "ind": ind,
                        "cap": cap,
                        "swr_avg": 1.5,
                        "swr_min": 1.5,
                        "swr_max": 1.5,
                        "sample_count": 0,
                        "last_update": time.time(),
                        "needs_verify": True,
                        "source": "fit",
                    })
                    existing_keys.add(key)
                    filled += 1
            fk += GRID_KHZ
        note = f"sw={'CL' if sw_mode else 'LC'} 锚点{len(anchors_all)}个(可信{len(anchors)}"
        if dropped:
            note += f"，剔除{len(dropped)}: {','.join(str(d['freq']//1000) for d in dropped)}"
        note += f") ind={fi[0]:+.4f}/kHz·f{fi[1]:+.1f} cap={fc[0]:+.4f}/kHz·f{fc[1]:+.1f}"
        report.append((band, len(anchors), filled, note, fi, fc))

    print(f"{'波段':<5} {'锚点':>4} {'拟合填充':>4}  说明")
    for band, na, nf, note, _, _ in report:
        print(f"{band:<5} {na:>4} {nf:>4}  {note}")
    print(f"\n合计新增拟合记录: {len(new_records)} 条")

    if not apply:
        print("\n[dry-run] 未写入。加 --apply 实际写入（会先备份）。")
        for r in new_records[:8]:
            print(f"  例: {r['freq']//1000}kHz sw={r['sw']} ind={r['ind']} cap={r['cap']}")
        return

    backup = TUNER_JSON + f".bak_fit_{time.strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(TUNER_JSON, backup)
    db["records"] = records + new_records
    db["records"].sort(key=lambda x: x["freq"])
    db["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    tmp = TUNER_JSON + ".tmp"
    with open(tmp, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    os.replace(tmp, TUNER_JSON)
    print(f"已写入 {len(new_records)} 条拟合记录，备份: {backup}")


if __name__ == "__main__":
    main()

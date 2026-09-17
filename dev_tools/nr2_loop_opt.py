#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NR2（EMNR）“水声”闭环自验证优化器  V2。

与 V1 的差别（V1 的教训）：
  * wdsp 是多线程实时引擎：喂数快于实时会把内部队列打爆（-2 饥饿/丢块），结果不可复现
    → 必须**实时节拍**（speed=1.0）。为控时长用 9 s 短片段 + 多进程并行（每个进程独立 dylib 实例）。
  * 输出相对输入有处理时延 → 先用带内包络互相关对齐（±64 帧），再算 eat/env_corr。
  * AGC 的静态增益与泵动会污染"输出/输入"型度量（实测把 14dB 的钳位差异压成 3dB）
    → 闭环全程 AGC=OFF（胜者再用 AGC=MED 复核一遍）。
  * -2 饥饿块是原样直通（wrapper 真实行为）→ 对齐后把这些帧从统计里掩蔽掉。

水声四件套（无参考）：
  flicker_ratio 静音段音乐噪声闪烁比（处理后/原始，≤1.3 好；NR 把噪声谱“打散”成孤峰 → 水声/音乐噪声）
  holes_pct     语音帧频谱空洞占比（>15dB 的 bin；水下声/空洞感）
  nr_db         静音段降噪深度（收益；≥8dB 才算有效降噪）
  env_corr      语音段带内包络相关（泵动/拖尾；→1 好）

score（越小越好）= 6*max(0, flicker_ratio-1.2) + 0.05*holes_pct + 0.5*max(0,8-nr_db) + 8*(1-env_corr)

用法：
  python3 dev_tools/nr2_loop_opt.py --quick   # 1 条录音粗筛
  python3 dev_tools/nr2_loop_opt.py           # 2 条录音完整搜索
"""
import argparse, glob, json, os, subprocess, sys, time, wave, hashlib
import numpy as np
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "nr2_out", "loop")
CACHE = "/tmp/nr2_loop_cache"
SR = 48000
BAND = (300.0, 2700.0)
SECS = 9.0
LAG_FRAMES = 64

DEFAULT = dict(emnr=True, gm=0, npe=0, ae=1, psi=12.0, zeta=0.65, floor_db=-12.0, dry=0.0,
               agc=0)  # 生产 L2 的 NR 参数；AGC 关闭做归因（AGC 的泵动会污染衰减/空洞度量）
ATTENS = [-6.0, -9.0, -12.0, -16.0, -20.0]
PSIS = [8.0, 12.0, 20.0]
ZETAS = [0.50, 0.65, 0.80]
DRYS = [0.0, 0.15, 0.30]


# ───────────────────────────────────────────────────────────────────────────
# 子进程：装载 harness + 单次评测（对齐 + 掩蔽）
# ───────────────────────────────────────────────────────────────────────────
_P = {}

def _init():
    import wdsp_wrapper as W  # noqa: F401  每进程加载一次 dylib
    from nr2_prod_ab import run_prod, save, SR  # noqa: F401
    _P["run_prod"] = run_prod
    _P["save"] = save


def _stft(x, n=1024, hop=256):
    win = np.hanning(n)
    nf = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(nf)[:, None]
    return np.abs(np.fft.rfft(x[idx] * win, axis=1)) + 1e-12


def _band_bins():
    f = np.fft.rfftfreq(1024, 1.0 / SR)
    return np.where((f >= BAND[0]) & (f <= BAND[1]))[0]


def _eval_one(job):
    """job = (tmpid, wave_bytes, kw, static_gain_db) → 指标 dict"""
    import wave as _w, tempfile
    tmpid, wb, kw, static_gain = job
    p = os.path.join(tempfile.gettempdir(), f"nr2loop_{tmpid}.wav")
    if not os.path.exists(p):
        open(p, "wb").write(wb)
    with _w.open(p, "rb") as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
    run_prod = _P["run_prod"]

    y, errs = run_prod(x, speed=1.0, **kw)          # 实时节拍（保真）
    bb = _band_bins()
    Mn, Mo = _stft(x), _stft(y)

    # ── 包络互相关对齐：out 滞后于 raw（out[t] ≈ raw[t-L]）→ 找 L 使 raw[:N-L] ≈ out[L:] ──
    env_n = np.sum(Mn[:, bb] ** 2, 1)
    env_o = np.sum(Mo[:, bb] ** 2, 1)
    zen, zeo = env_n - env_n.mean(), env_o - env_o.mean()
    lags = range(0, LAG_FRAMES)
    cors = [float(np.dot(zen[: len(zen) - l], zeo[l:]) /
                  (np.linalg.norm(zen[: len(zen) - l]) * np.linalg.norm(zeo[l:]) + 1e-12)) for l in lags]
    lag = int(np.argmax(cors))

    # ── -2 饥饿帧掩蔽（直通块 ±2 帧）──
    nf = Mn.shape[0]
    bad = np.zeros(nf, bool)
    for b in errs:                                   # 块 b 覆盖样本 [b·256,(b+1)·256) = 帧 [b, b+1)
        f0 = max(0, b - 2)
        f1 = min(nf, b + 6)                          # stft 窗 1024=4 hop，向后多掩几帧
        bad[f0:f1] = True
    Mo2 = Mo[lag:]
    Mn2 = Mn[: nf - lag] if lag else Mn
    bad2 = bad[lag:]
    keep = ~bad2
    if keep.sum() < nf * 0.6:
        keep = np.ones(nf - lag, bool)              # 饥饿太多就别掩了

    # ── VAD（QSB 稳健：分位数）──
    e = 10 * np.log10(np.sum(Mn2[:, bb] ** 2, 1) + 1e-20)
    noise_p, speech_p = np.percentile(e, 20), np.percentile(e, 62)
    pause = (e <= noise_p + 4.0) & keep
    speech = (e >= speech_p) & keep
    if pause.sum() < 6 or speech.sum() < 6:
        return None

    db = lambda a: 10 * np.log10(np.maximum(a, 1e-20))
    nr_out = float(np.mean(db(np.sum(Mo2[pause][:, bb] ** 2, 1)) - db(np.sum(Mn2[pause][:, bb] ** 2, 1))))
    nr_db = static_gain - nr_out      # 静音段相对“NR-OFF 链条”的降噪深度（正=有用）
    # 音乐噪声指数：先把每帧谱按帧行归一（剥掉 QSB 共模衰落），再看各 bin 时间维 log 幅度抖动
    fr_n = np.sum(Mn2[:, bb] ** 2, 1) + 1e-20
    fr_o = np.sum(Mo2[:, bb] ** 2, 1) + 1e-20
    lg_n = np.log(Mn2[:, bb] / np.sqrt(fr_n)[:, None])
    lg_o = np.log(Mo2[:, bb] / np.sqrt(fr_o)[:, None])
    fl_raw = float(np.mean(np.std(lg_n[pause], 0)))
    fl_out = float(np.mean(np.std(lg_o[pause], 0)))
    fl_ratio = fl_out / max(fl_raw, 1e-6)
    att = 20 * np.log10(Mo2[speech][:, bb] / Mn2[speech][:, bb]) - static_gain
    eat = float(np.mean(att < -8.0) * 100.0)      # 语音被吃（每 bin 钳位 maxAtten，>8dB 即已接近地板）
    zo = np.sum(Mo2[speech][:, bb] ** 2, 1); zn = np.sum(Mn2[speech][:, bb] ** 2, 1)
    z = lambda v: (v - v.mean()) / (v.std() + 1e-12)
    env_corr = float(np.corrcoef(z(zo), z(zn))[0, 1])
    spd = float(np.mean(db(np.sum(Mo2[speech][:, bb] ** 2, 1)) - db(np.sum(Mn2[speech][:, bb] ** 2, 1))))
    score = (5.0 * max(0.0, fl_ratio - 1.3) + 0.04 * eat
             + 0.5 * max(0.0, 8.0 - nr_db) + 8.0 * (1.0 - env_corr))   # 深度不足 8dB 才罚
    return dict(nr_db=round(nr_db, 2), flicker_ratio=round(fl_ratio, 3), flicker_raw=round(fl_raw, 3),
                eat_pct=round(eat, 1), env_corr=round(env_corr, 3), spd_db=round(spd, 2),
                lag_frames=lag, score=round(score, 3))


def _wav_bytes(x):
    import io, wave as _w
    buf = io.BytesIO()
    with _w.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


# ───────────────────────────────────────────────────────────────────────────
# 主流程
# ───────────────────────────────────────────────────────────────────────────
def main():
    from nr2_prod_ab import run_prod, save   # 生产一致 harness（实时节拍）
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)

    # 素材：自动挑“语音占比高”的录音（全噪声素材对 eat/env 无区分度）
    recs = sorted(glob.glob(os.path.join(ROOT, "recordings", "*.mp3")), key=os.path.getsize, reverse=True)
    cand = []
    for r in recs[:12]:
        wav = os.path.join(CACHE, os.path.basename(r) + ".48k.wav")
        if not os.path.exists(wav):
            rc = subprocess.call(["ffmpeg", "-y", "-loglevel", "error", "-i", r,
                                  "-ac", "1", "-ar", str(SR), "-f", "wav", wav])
            if rc != 0:
                subprocess.run(["afconvert", "-f", "WAVE", "-d", f"LEI16@{SR}", "-c", "1", r, wav])
        try:
            with wave.open(wav, "rb") as w:
                n = w.getnframes()
            if n < int(SECS * SR):
                continue
            with wave.open(wav, "rb") as w:
                d = np.frombuffer(w.readframes(int(SECS * SR)), dtype=np.int16).astype(np.float64) / 32768.0
            Mn = _stft(d); bb = _band_bins()
            e = 10 * np.log10(np.sum(Mn[:, bb] ** 2, 1) + 1e-20)
            sf = float(np.mean(e >= np.percentile(e, 62)))          # 语音占比
            cand.append((sf, os.path.basename(r), d))
        except Exception as ex:
            print(f"  跳过 {os.path.basename(r)}: {ex}")
    cand.sort(key=lambda t: -t[0])
    print("素材语音占比:", [(n[:22], round(sf, 2)) for sf, n, _ in cand[:4]])
    clips = []
    for sf, name, d in cand:
        if sf < 0.10:
            continue
        clips.append((name, d / max(np.max(np.abs(d)), 1e-9) * 0.25))
        if len(clips) >= (1 if a.quick else 2):
            break
    if not clips:
        print("❌ 没有语音占比合格的录音"); return 1
    print(f"（每条 {SECS:.0f}s，实时节拍）\n")

    jobs_kw = []
    results = []
    t0 = time.time()
    pool = ProcessPoolExecutor(max_workers=5, initializer=_init)

    # 静态增益基线：NR-OFF + AGC=OFF（每条素材一次）
    static_gain = []
    for i, (_, c) in enumerate(clips):
        yb, _ = run_prod(c, speed=1.0, emnr=False, agc=0)
        Mn0, Mo0 = _stft(c), _stft(yb)
        bb0 = _band_bins()
        en0 = np.sum(Mn0[:, bb0] ** 2, 1); eo0 = np.sum(Mo0[:, bb0] ** 2, 1)
        g = float(np.median(10 * np.log10((eo0 + 1e-20) / (en0 + 1e-20))))
        static_gain.append(g)
    print(f"静态增益基线（NR-OFF 链条）: {[round(g, 1) for g in static_gain]} dB\n")

    def probe(kw, tag):
        futs = [pool.submit(_eval_one, (f"{tag}{i}", _wav_bytes(c), kw, static_gain[i]))
                for i, (_, c) in enumerate(clips)]
        ms = [f.result() for f in futs]
        ms = [m for m in ms if m]
        if not ms:
            print(f"  {cfg(kw)}  ✗ 无法度量"); return 1e9
        s = float(np.mean([m["score"] for m in ms]))
        m0 = ms[0]
        results.append(dict(tag=tag, **{k: kw.get(k) for k in ("psi", "zeta", "floor_db", "dry", "alpha", "npmax")}, **m0))
        print(f"  {cfg(kw)}  score={s:6.3f}  nr={m0['nr_db']:>6} flicker×{m0['flicker_ratio']:>5} "
              f"eat={m0['eat_pct']:>5}% env={m0['env_corr']:>5} spd={m0['spd_db']:>6} lag={m0['lag_frames']}")
        return s

    def cfg(kw):
        al = kw.get('alpha'); nm = kw.get('npmax')
        return (f"atten={kw['floor_db']:>5} psi={kw['psi']:>4} zeta={kw['zeta']:.2f} dry={kw['dry']:.2f}"
                f" alpha={al if al else 'stock'} npmax={nm if nm else 'stock'}")

    print("── 基线 ──")
    s_default = probe(DEFAULT, "def")

    print("── Stage A：atten × psi（zeta/dry 固定）──")
    stageA = []
    for at in ATTENS:
        for ps in PSIS:
            if (at, ps) == (DEFAULT["floor_db"], DEFAULT["psi"]):
                stageA.append((s_default, dict(DEFAULT))); continue
            kw = dict(DEFAULT, floor_db=at, psi=ps)
            stageA.append((probe(kw, "A"), kw))
    stageA.sort(key=lambda t: t[0])
    top = [kw for _, kw in stageA[:2]]

    print("── Stage B：top2 × zeta × dry ──")
    stageB = [(s_default, dict(DEFAULT))]
    for kw in top:
        for ze in ZETAS:
            for dr in DRYS:
                kw2 = dict(kw, zeta=ze, dry=dr)
                if (kw2["psi"], kw2["zeta"], kw2["dry"], kw2["floor_db"]) == \
                   (DEFAULT["psi"], DEFAULT["zeta"], DEFAULT["dry"], DEFAULT["floor_db"]):
                    continue
                stageB.append((probe(kw2, "B"), kw2))
    stageB.sort(key=lambda t: t[0])
    best_kw = stageB[0][1]

    print("── Stage C：最优 atten/psi/zeta 上扫 alpha × npmax（C 层去水旋钮，需新 dylib）──")
    stageC = [(stageB[0][0], dict(best_kw))]
    for al in (None, 0.996, 0.998):
        for nm in (None, 0.98, 0.99):
            if al is None and nm is None:
                continue
            kw3 = dict(best_kw, alpha=al, npmax=nm)
            stageC.append((probe(kw3, "C"), kw3))
    stageC.sort(key=lambda t: t[0])
    best_kw, s_best = stageC[0][1], stageC[0][0]

    print(f"\n默认 score={s_default:.3f} → 最优 score={s_best:.3f}")
    print(f"最优: {cfg(best_kw)}\n")

    # A/B 试听（顺序跑，实时节拍）
    for name, c in clips:
        yd, _ = run_prod(c, speed=1.0, **DEFAULT)
        yb, _ = run_prod(c, speed=1.0, **best_kw)
        stem = os.path.join(OUT, "ab_" + os.path.splitext(name)[0][:24])
        save(stem + "_0raw.wav", c); save(stem + "_1default.wav", yd); save(stem + "_2best.wav", yb)
        print(f"  A/B → {stem}_[0raw|1default|2best].wav")

    results.sort(key=lambda r: r.get("score", 1e9))
    json.dump(dict(best={k: best_kw[k] for k in ("psi", "zeta", "floor_db", "dry")},
                   default={k: DEFAULT[k] for k in ("psi", "zeta", "floor_db", "dry")},
                   score_default=s_default, score_best=s_best,
                   elapsed_s=round(time.time() - t0, 1), results=results),
              open(os.path.join(OUT, "loop_report.json"), "w"), ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "loop_report.md"), "w") as f:
        f.write(f"# NR2 水声闭环优化 V2  {time.strftime('%F %T')}\n\n")
        f.write(f"- 默认(L2) score={s_default:.3f} → 最优 score={s_best:.3f}\n")
        f.write(f"- 最优：atten={best_kw['floor_db']} psi={best_kw['psi']} zeta={best_kw['zeta']} dry={best_kw['dry']}\n\n")
        f.write("| atten | psi | zeta | dry | nr_db | flicker× | eat% | env | score |\n|---|---|---|---|---|---|---|---|---|\n")
        for r in results[:15]:
            f.write(f"| {r['floor_db']} | {r['psi']} | {r['zeta']} | {r['dry']} | {r.get('nr_db')} | "
                    f"{r.get('flicker_ratio')} | {r.get('eat_pct')} | {r.get('env_corr')} | {r.get('score')} |\n")
    print(f"报告 → {OUT}/loop_report.md | 用时 {time.time()-t0:.0f}s")
    pool.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())

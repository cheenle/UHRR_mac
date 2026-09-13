#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A6：制造 fexchange0 饥饿，检查 -2 时是否注入原始输入。

方法：以"突发"方式喂入（32 块连推，再按实时节拍等待），必然让 DSP 线程落后。
判据：
  * 旧行为  → 饥饿块输出 == 该块原始输入（`return audio_data`），可精确识别；PASS 要求 0 次
  * 新行为  → 饥饿块输出 == 上一块输出（保持）；PASS 要求至少 1 次饥饿且 0 次"等于原始输入"
额外报告：突然的电平突起（> +6 dB 邻域中位）数量。
"""
import os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode

SR, BS = 48000, 256
BURST = 32

p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=True,
                  enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED)
p.set_bandpass(300.0, 2700.0)
p.set_nr2_level(2)
rng = np.random.default_rng(3)
n = SR * 3
x = rng.standard_normal(n) * 0.1

t0 = time.monotonic()
outs, ins = [], []
i = 0
while i < n - BS:
    for _ in range(BURST):                      # 突发：DSP 线程必然落后 → 饥饿
        if i >= n - BS:
            break
        blk = x[i:i + BS]
        outs.append(p.process(blk.astype(np.float64)))
        ins.append(blk)
        i += BS
    d = t0 + i / SR - time.monotonic()          # 每突发后按实时节拍等待
    if d > 0:
        time.sleep(d)
p.close()

rms = np.array([np.sqrt(np.mean(b ** 2)) for b in outs])
identical_to_input = [b for b in range(len(outs)) if len(outs[b]) == BS and np.array_equal(outs[b], ins[b])]
same_as_prev = [b for b in range(1, len(outs)) if np.array_equal(outs[b], outs[b - 1])]
spikes = []
for b in range(len(rms)):
    lo, hi = max(0, b - 20), min(len(rms), b + 21)
    nb = np.median(np.delete(rms[lo:hi], b - lo)) if hi - lo > 1 else np.median(rms)
    if nb > 0 and rms[b] > nb * 2.0:
        spikes.append((b, round(float(20 * np.log10(rms[b] / nb)), 1)))
print(f"块数={len(outs)} starved_blocks={getattr(p, 'starved_blocks', 'N/A')}")
print(f"输出==原始输入的块: {len(identical_to_input)} {identical_to_input[:8]}")
print(f"输出==上一块输出的块: {len(same_as_prev)} {same_as_prev[:8]}")
print(f"电平突起(> +6dB): {len(spikes)} {spikes[:8]}")
starved = getattr(p, "starved_blocks", None)
ok = (len(identical_to_input) == 0) and (len(spikes) == 0) and (starved is None or starved > 0)
print("A6", "PASS" if ok else "FAIL")

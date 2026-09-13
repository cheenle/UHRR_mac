# NR2（EMNR）SSB 语音保护优化 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 让 NR2 不再"整段削语音"（每 bin 最大衰减限制 + 增益级重排），同时消除 `bp1` 静音地雷与 `fexchange0` 饥饿 click。

**架构：** C 端给 EMNR 增加"每 bin 最大衰减/干湿混合"，并新增 `SetRXANBPFreqs` 让 SSB 带通改由始终可用的 `nbp0` 承担；Python 端把 NR2 等级映射到该上限、给 AGC 补偿增益封顶、修正 panel/AGC 参数、`-2` 时保持上一块输出。

**技术栈：** C（WDSP fork，`make` + FFTW3）、Python 3（ctypes 绑定、numpy）、INI 配置。

**依据规格：** `docs/superpowers/specs/2026-09-13-nr2-ssb-optimization-design.md`

> ⚠️ **版本控制警告（必读）**：`DSP/wdsp` 在主仓库里是一个 **失效的 gitlink**（mode 160000、指向不存在的 commit 49084f5、无 `.gitmodules`、目录内无 `.git`）。**对该目录内 C 源码的修改不会出现在主仓库 `git status` 里**。因此任务 2/3 必须把改动额外导出为 **patch 文件**（`DSP/patches/*.patch`，该路径受主仓库跟踪）并提交，否则改动会丢失。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `DSP/wdsp/emnr.h` | EMNR 结构体：新增 `max_atten` / `dry` 字段 | 修改 |
| `DSP/wdsp/emnr.c` | EMNR：字段初始化、掩码下限/干湿生效点、两个新 setter | 修改 |
| `DSP/wdsp/nbp.h` | 声明 `SetRXANBPFreqs` | 修改 |
| `DSP/wdsp/nbp.c` | 实现 `SetRXANBPFreqs`（复用 `calc_nbp_impulse`） | 修改 |
| `DSP/patches/2026-09-13-nr2-ssb-voice-protection.patch` | C 改动的可提交载体 + 应用说明 | 创建 |
| `wdsp_wrapper.py` | 绑定新 API、NR2 等级映射、AGC 封顶/panel、`-2` 保块、带通改走 nbp | 修改 |
| `audio_interface.py` | 读新配置键 + 配置哈希同步 | 修改 |
| `MRRC.conf` / `windows/MRRC.conf.template` | 新增配置键（带注释） | 修改 |
| `dev_tools/nr2_tone_gain.py` | A1：单音穿透增益（等级阶梯） | 创建 |
| `dev_tools/nr2_band_tf.py` | A5：SSB 带通频响 | 创建 |
| `dev_tools/nr2_starve.py` | A6：`-2` 饥饿时是否保持上一块 | 创建 |
| `CHANGELOG.md` | 记录电平变化与新参数 | 修改 |
| `docs/superpowers/specs/2026-09-13-nr2-ssb-optimization-design.md` | 规格一致性修正（`nr2_max_atten_db` 改为"可选覆盖"语义） | 修改 |

**不涉及**：`Dockerfile`（镜像本就不含 `libwdsp`，WDSP 在容器内不可用属既有状态）、前端 JS（等级 0–4 已覆盖主轴）。

---

## 任务 1：先写会失败的验收脚本（A1 / A5 / A6）

**文件：**
- 创建：`dev_tools/nr2_tone_gain.py`
- 创建：`dev_tools/nr2_band_tf.py`
- 创建：`dev_tools/nr2_starve.py`

- [ ] **步骤 1：写 `dev_tools/nr2_tone_gain.py`（A1）**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1：单音穿透增益（走生产 wrapper 路径：WDSPProcessor + set_bandpass + set_nr2_level）。
验收：level 2 时 1kHz 净增益应 >= -18 dB（修复前为 -37 dB）。"""
import ctypes, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode, _wdsp

SR, BS = 48000, 256


def tone_gain(level, seconds=2.0, amp=0.2):
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=True,
                      enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED)
    p.set_bandpass(300.0, 2700.0)
    p.set_nr2_level(level)
    n = int(SR * seconds)
    t = np.arange(n) / SR
    x = amp * np.sin(2 * np.pi * 1000.0 * t)
    out = np.zeros(n)
    t0 = time.monotonic()
    for b in range(n // BS):
        blk = x[b * BS:(b + 1) * BS]
        out[b * BS:(b + 1) * BS] = p.process(blk.astype(np.float64))
        d = t0 + (b + 1) * BS / SR - time.monotonic()
        if d > 0:
            time.sleep(d)
    p.close()
    seg = out[n // 2:]
    X = np.fft.rfft(seg * np.hanning(len(seg)))
    fr = np.fft.rfftfreq(len(seg), 1 / SR)
    k = int(np.argmin(abs(fr - 1000)))
    a = 2 * abs(X[k]) / np.sum(np.hanning(len(seg)))
    return 20 * np.log10(max(a, 1e-12) / amp)


if __name__ == "__main__":
    print(f"{'level':>6s} {'1kHz 净增益(dB)':>16s}")
    for lv in (0, 1, 2, 3, 4):
        print(f"{lv:6d} {tone_gain(lv):16.1f}")
```

- [ ] **步骤 2：写 `dev_tools/nr2_band_tf.py`（A5）**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A5：SSB 带通频响（白噪激励）。验收：300-2700 通带 |H|>= -3 dB，<200Hz 与 >3.5kHz <= -30 dB。"""
import ctypes, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode, _wdsp

SR, BS = 48000, 256
MARK = int(0.5 * SR)


def run(x, nr2):
    p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=nr2,
                      enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED)
    _wdsp.SetRXAAGCMode(ctypes.c_int(0), ctypes.c_int(0))
    _wdsp.SetRXAAGCFixed(ctypes.c_int(0), ctypes.c_double(0.0))
    _wdsp.SetRXAPanelGain1(ctypes.c_int(0), ctypes.c_double(1.0))
    p.set_bandpass(300.0, 2700.0)
    if nr2:
        p.set_nr2_level(1)          # MIN：最大限度减少 NR 对频响测量的干扰
    n = len(x) // BS
    out = np.zeros(n * BS)
    t0 = time.monotonic()
    for b in range(n):
        out[b * BS:(b + 1) * BS] = p.process(x[b * BS:(b + 1) * BS].astype(np.float64))
        d = t0 + (b + 1) * BS / SR - time.monotonic()
        if d > 0:
            time.sleep(d)
    p.close()
    return out


def tf(mark_in, x, y, n=8192, hop=2048):
    a = mark_in[:MARK]
    best, lag = -1e18, 0
    for d in range(0, 12000, 2):
        v = float(np.dot(a, y[d:d + MARK]))
        if v > best:
            best, lag = v, d
    win = np.hanning(n)
    nf = (min(len(x), len(y) - lag) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(nf)[:, None]
    X = np.fft.rfft(x[idx] * win, axis=1)
    Y = np.fft.rfft(y[idx + lag] * win, axis=1)
    Sxy = np.mean(X.conj() * Y, axis=0)
    Sxx = np.mean(np.abs(X) ** 2, axis=0)
    return np.fft.rfftfreq(n, 1.0 / SR), np.abs(Sxy / (Sxx + 1e-30)), lag


if __name__ == "__main__":
    rng = np.random.default_rng(7)
    mark = rng.standard_normal(MARK) * 0.1
    x = np.concatenate([mark, np.zeros(BS), rng.standard_normal(SR) * 0.1])
    for nr2 in (False, True):
        y = run(x, nr2)
        f, H, lag = tf(mark, x, y)
        def g(lo, hi):
            m = (f >= lo) & (f < hi)
            return 20 * np.log10(np.mean(H[m]) + 1e-12) if m.any() else -99.0
        print(f"NR2={'on ' if nr2 else 'off'} lag={lag:5d} | "
              f"<200Hz={g(50,200):+6.1f} 300-2700={g(300,2700):+6.1f} "
              f">3.5k={g(3500,7000):+6.1f} dB")
```

- [ ] **步骤 3：写 `dev_tools/nr2_starve.py`（A6）**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A6：故意快喂制造 fexchange0 饥饿，检查 -2 时是否会注入原始输入（+18dB 突发）。
验收：饥饿块附近的输出块 RMS 不超过邻域中位数的 +6 dB；且 starved_blocks 计数 > 0。"""
import os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode

SR, BS = 48000, 256

p = WDSPProcessor(sample_rate=SR, buffer_size=BS, mode=WDSPMode.USB, enable_nr2=True,
                  enable_nb=False, enable_anf=False, agc_mode=WDSPAGCMode.MED)
p.set_bandpass(300.0, 2700.0)
p.set_nr2_level(2)
rng = np.random.default_rng(3)
n = SR * 3
x = rng.standard_normal(n) * 0.1
t0 = time.monotonic()
blocks = []
starved_at = []
for b in range(n // BS):
    before = getattr(p, "starved_blocks", 0)
    out = p.process(x[b * BS:(b + 1) * BS].astype(np.float64))
    if getattr(p, "starved_blocks", 0) > before:
        starved_at.append(b)
    blocks.append(out)
    d = t0 + (b + 1) * BS / SR / 3.0 - time.monotonic()      # 3x 实时 → 制造饥饿
    if d > 0:
        time.sleep(d)
p.close()
rms = np.array([np.sqrt(np.mean(b ** 2)) for b in blocks])
med = np.median(rms[rms > 0]) if np.any(rms > 0) else 0.0
print(f"块数={len(blocks)} 饥饿块数={len(starved_at)} 中位RMS={med:.5f}")
bad = []
for b in starved_at:
    lo, hi = max(0, b - 20), min(len(rms), b + 21)
    nb = np.median(np.delete(rms[lo:hi], b - lo)) if hi - lo > 1 else med
    if nb > 0 and rms[b] > nb * 2.0:
        bad.append((b, 20 * np.log10(rms[b] / nb)))
print(f"超过邻域中位 +6dB 的饥饿块: {len(bad)} {bad[:8]}")
print("PASS" if starved_at and not bad else "FAIL")
```

- [ ] **步骤 4：运行三个脚本，确认当前（修复前）失败**

运行：
```bash
python3 dev_tools/nr2_tone_gain.py
python3 dev_tools/nr2_band_tf.py
python3 dev_tools/nr2_starve.py
```
预期（修复前）：
- `nr2_tone_gain.py`：level 2 约 **−37 dB**（远低于 −18 dB 门槛）→ FAIL
- `nr2_band_tf.py`：NR2 off 一列 `<200Hz` 与 `>3.5k` 只有 −6~−8 dB（nbp 原频点 −4150/−150），带通不是 300–2700 → FAIL
- `nr2_starve.py`：饥饿块出现 **+18 dB 级**突发 → FAIL

- [ ] **步骤 5：Commit**

```bash
git add dev_tools/nr2_tone_gain.py dev_tools/nr2_band_tf.py dev_tools/nr2_starve.py
git commit -m "test(nr2): 新增 A1/A5/A6 验收脚本（当前均失败）"
```

---

## 任务 2：C 端 EMNR 语音保护（max_atten + dry）

**文件：**
- 修改：`DSP/wdsp/emnr.h`（`struct _emnr._g`）
- 修改：`DSP/wdsp/emnr.c`（`create_emnr`、`calc_gain`、文件末尾）
- 创建：`DSP/patches/2026-09-13-nr2-ssb-voice-protection.patch`
- 修改：`dev_tools/nr2_floor_scan.py:78`、`dev_tools/nr2_prod_ab.py:68-71`（API 改名）

- [ ] **步骤 1：备份原始树（用于生成 patch）**

```bash
rm -rf /tmp/wdsp_pristine && mkdir -p /tmp/wdsp_pristine && \
  cp DSP/wdsp/emnr.c DSP/wdsp/emnr.h DSP/wdsp/nbp.c DSP/wdsp/nbp.h /tmp/wdsp_pristine/
```

- [ ] **步骤 2：`DSP/wdsp/emnr.h` 加字段**

在 `struct _g { ... double gf1p5; ... }` 中 `double gf1p5;` 之后插入：

```c
		double gf1p5;
		double max_atten;		// 每 bin 最大衰减（线性掩码下限）；0 = 不限制
		double dry;				// 干湿混合：mask' = dry + (1-dry)*mask；0 = 纯湿
```

- [ ] **步骤 3：`DSP/wdsp/emnr.c` — 默认值 + 生效点 + setter**

3a) `create_emnr()` 中 `a->g.ae_run = ae_run;` 之后：

```c
	a->g.ae_run = ae_run;
	a->g.max_atten = 0.0;		// 0 = 不限制（保持旧行为，向后兼容）
	a->g.dry = 0.0;
	calc_emnr (a);
```

3b) `calc_gain()` 末尾 `if (a->g.ae_run) aepf(a);` 之后：

```c
	if (a->g.ae_run) aepf(a);
	if (a->g.dry > 0.0 || a->g.max_atten > 0.0)
	{
		int m;
		for (m = 0; m < a->g.msize; m++)
		{
			double mk = a->mask[m];
			if (a->g.dry > 0.0) mk = a->g.dry + (1.0 - a->g.dry) * mk;
			if (a->g.max_atten > 0.0 && mk < a->g.max_atten) mk = a->g.max_atten;
			a->mask[m] = mk;
			a->g.prev_mask[m] = mk;		// 决策导向环保持一致
		}
	}
```

3c) 文件末尾（`SetRXAEMNRaePsi` 之后）追加：

```c
PORT
void SetRXAEMNRmaxAttenDb (int channel, double db)
{
	EnterCriticalSection (&ch[channel].csDSP);
	// db < 0 → 掩码下限 10^(db/20)；db >= 0 → 不限制（关闭）
	rxa[channel].emnr.p->g.max_atten = (db < 0.0) ? pow (10.0, db / 20.0) : 0.0;
	LeaveCriticalSection (&ch[channel].csDSP);
}

PORT
void SetRXAEMNRdry (int channel, double dry)
{
	EnterCriticalSection (&ch[channel].csDSP);
	rxa[channel].emnr.p->g.dry = (dry > 0.0) ? ((dry < 1.0) ? dry : 1.0) : 0.0;
	LeaveCriticalSection (&ch[channel].csDSP);
}
```

- [ ] **步骤 4：重编译并安装**

```bash
cd DSP/wdsp && make CFLAGS="-I/opt/local/include" && \
  nm -gU libwdsp.dylib | grep -E "SetRXAEMNRmaxAttenDb|SetRXAEMNRdry" && \
  sudo cp libwdsp.dylib /usr/local/lib/libwdsp.dylib && cd - && \
  shasum -a 256 /usr/local/lib/libwdsp.dylib DSP/wdsp/libwdsp.dylib
```
预期：两个符号存在；两处 sha256 相同。

- [ ] **步骤 5：探针 API 改名**

`dev_tools/nr2_floor_scan.py:78` 与 `dev_tools/nr2_prod_ab.py:69`：
`SetRXAEMNRmaskFloor` → `SetRXAEMNRmaxAttenDb`（语义一致：参数都是 dB）。

- [ ] **步骤 6：运行 A1，确认通过**

运行：`python3 dev_tools/nr2_tone_gain.py`
预期：level 0 ≈ −6 dB；level 1 ≈ −9±2 dB；**level 2 ≈ −15±3 dB（≥ −18 dB 门槛）**；level 3/4 更低。
（此时 wrapper 尚未把等级映射到上限，故等级阶梯可能还是平坦的；若平坦，在任务 4 后复跑。）

- [ ] **步骤 7：生成 patch 并提交**

```bash
mkdir -p DSP/patches && \
diff -u /tmp/wdsp_pristine/emnr.h DSP/wdsp/emnr.h >  DSP/patches/2026-09-13-nr2-ssb-voice-protection.patch; \
diff -u /tmp/wdsp_pristine/emnr.c DSP/wdsp/emnr.c >> DSP/patches/2026-09-13-nr2-ssb-voice-protection.patch; true
git add DSP/patches/2026-09-13-nr2-ssb-voice-protection.patch dev_tools/nr2_floor_scan.py dev_tools/nr2_prod_ab.py
git commit -m "feat(wdsp): EMNR 每bin最大衰减+干湿混合 (A1 通过)"
```

---

## 任务 3：C 端 `SetRXANBPFreqs` + 带通切换（消除 bp1 静音地雷）

**文件：**
- 修改：`DSP/wdsp/nbp.h`、`DSP/wdsp/nbp.c`
- 修改：`wdsp_wrapper.py`（`set_bandpass`）
- 修改：`DSP/patches/2026-09-13-nr2-ssb-voice-protection.patch`（追加）

- [ ] **步骤 1：`DSP/wdsp/nbp.h` 声明**

`extern void setMp_nbp (NBP a);` 之后加：

```c
extern void SetRXANBPFreqs (int channel, double f_low, double f_high);
```

- [ ] **步骤 2：`DSP/wdsp/nbp.c` 实现（追加到文件末尾）**

```c
PORT
void SetRXANBPFreqs (int channel, double f_low, double f_high)
{
	NBP a = rxa[channel].nbp0.p;
	EnterCriticalSection (&ch[channel].csDSP);
	if ((f_low != a->flow) || (f_high != a->fhigh))
	{
		a->flow  = f_low;
		a->fhigh = f_high;
		calc_nbp_impulse (a);						// fnfrun=0: fir_bandpass；fnfrun=1: fir_mbandpass
		setImpulse_fircore (a->p, a->impulse, 1);	// 1 = 立即激活
		_aligned_free (a->impulse);
	}
	LeaveCriticalSection (&ch[channel].csDSP);
}
```

- [ ] **步骤 3：`wdsp_wrapper.py::set_bandpass()` 改走 nbp，不再开 bp1**

```python
    def set_bandpass(self, low_freq: float, high_freq: float):
        """
        Set SSB bandpass (Hz).

        走 always-on 的 nbp0 FIR（`SetRXANBPFreqs`），不再依赖 bp1：
        bp1 在"非 NR 模块驱动"状态下会输出全零（实测 NR2 关闭 → RX 静音），
        且其增益/掩码激活路径不可靠。bp1 的开关完全交给 WDSP 的 RXAbp1Set。
        """
        if not self._initialized:
            return

        try:
            if hasattr(_wdsp, "SetRXANBPFreqs"):
                _wdsp.SetRXANBPFreqs(ctypes.c_int(self.channel),
                                     ctypes.c_double(low_freq), ctypes.c_double(high_freq))
            else:   # 旧库回退（无 nbp setter）：仍用 bp1
                _wdsp.SetRXABandpassRun(ctypes.c_int(self.channel), ctypes.c_int(1))
                _wdsp.SetRXABandpassFreqs(ctypes.c_int(self.channel),
                                          ctypes.c_double(low_freq), ctypes.c_double(high_freq))
            self._bandpass_low = low_freq
            self._bandpass_high = high_freq
            print(f"🔧 WDSP Bandpass: {low_freq}Hz - {high_freq}Hz (nbp0)")
        except Exception as e:
            print(f"⚠️ Bandpass setup error: {e}")
```

- [ ] **步骤 4：重编译 + 安装**

```bash
cd DSP/wdsp && make CFLAGS="-I/opt/local/include" && \
  nm -gU libwdsp.dylib | grep SetRXANBPFreqs && \
  sudo cp libwdsp.dylib /usr/local/lib/libwdsp.dylib && cd -
```

- [ ] **步骤 5：运行 A5 与 A4（场景静音）**

运行：
```bash
python3 dev_tools/nr2_band_tf.py
for s in A C D; do python3 dev_tools/nr2_scenario_probe.py $s; done
```
预期：`nr2_band_tf.py` 两行都是 `<200Hz ≤ −30 dB`、`300-2700 ≥ −3 dB`、`>3.5k ≤ −30 dB`（A5 PASS）；
`A/C/D` 场景全部 `✅ 音频正常`（A4 PASS）。

- [ ] **步骤 6：追加 patch + Commit**

```bash
diff -u /tmp/wdsp_pristine/nbp.h DSP/wdsp/nbp.h >>  DSP/patches/2026-09-13-nr2-ssb-voice-protection.patch; \
diff -u /tmp/wdsp_pristine/nbp.c DSP/wdsp/nbp.c >> DSP/patches/2026-09-13-nr2-ssb-voice-protection.patch; true
git add DSP/patches/2026-09-13-nr2-ssb-voice-protection.patch wdsp_wrapper.py
git commit -m "feat(wdsp): SetRXANBPFreqs，SSB 带通改由 nbp0 承担（消除 bp1 静音地雷，A4/A5 通过）"
```

---

## 任务 4：Python 增益级与 `-2` 健壮性

**文件：**
- 修改：`wdsp_wrapper.py`

- [ ] **步骤 1：`__init__` 新增参数与状态**

签名追加（默认值保持向后兼容）：

```python
                 nr2_ae_psi: float = 12.0,
                 nr2_ae_zeta_thresh: float = 0.65,
                 nr2_max_atten_db: float = None,
                 nr2_dry: float = 0.0,
                 agc_top_db: float = 20.0,
                 panel_gain: float = 0.35):
```

`__init__` 体内（`self._nr2_ae_zeta_thresh = nr2_ae_zeta_thresh` 之后）：

```python
        self._nr2_max_atten_db = nr2_max_atten_db   # None → 跟随 set_nr2_level 等级表
        self._nr2_dry = nr2_dry
        self._agc_top_db = agc_top_db
        self._panel_gain = panel_gain
        self._last_output = None                    # -2 饥饿时保持上一块输出
        self.starved_blocks = 0                     # 饥饿计数（诊断用）
```

- [ ] **步骤 2：等级表（模块级常量，放在 `WDSPMeterType` 之后）**

```python
class WDSPNR2Level:
    """SSB 语音保护等级：以"每 bin 最大衰减"为主轴（证据见规格 §1）。"""
    MAX_ATTEN_DB = {1: -6.0, 2: -12.0, 3: -16.0, 4: -20.0}
    PSI          = {1: 8.0,  2: 12.0,  3: 14.0,  4: 18.0}
    ZETA_THRESH  = {1: 0.70, 2: 0.65,  3: 0.60,  4: 0.55}
```

- [ ] **步骤 3：`_setup_nr2()` 应用默认上限**

`self.set_nr2_ae(...)` 之后加：

```python
            # 语音保护：限制每 bin 最大衰减（默认取 level 2 的 -12dB，或配置覆盖）
            self._apply_nr2_voice_protection(2)
```

- [ ] **步骤 4：新增 `_apply_nr2_voice_protection()` 与两个 setter**

在 `set_nr2_ae()` 之后插入：

```python
    def _apply_nr2_voice_protection(self, level: int):
        """按等级（或配置覆盖）设置每 bin 最大衰减 / 干湿混合。"""
        try:
            if hasattr(_wdsp, "SetRXAEMNRmaxAttenDb"):
                db = (self._nr2_max_atten_db if self._nr2_max_atten_db is not None
                      else WDSPNR2Level.MAX_ATTEN_DB.get(level, -12.0))
                _wdsp.SetRXAEMNRmaxAttenDb(ctypes.c_int(self.channel), ctypes.c_double(db))
            if hasattr(_wdsp, "SetRXAEMNRdry") and self._nr2_dry > 0.0:
                _wdsp.SetRXAEMNRdry(ctypes.c_int(self.channel), ctypes.c_double(self._nr2_dry))
        except Exception as e:
            print(f"⚠️ NR2 voice protection error: {e}")

    def set_nr2_voice_protection(self, max_atten_db: float = None, dry: float = None):
        """运行时调'语气保真度'：max_atten_db<0 限制每 bin 衰减；dry=0~1 干湿混合。"""
        if max_atten_db is not None:
            self._nr2_max_atten_db = max_atten_db
        if dry is not None:
            self._nr2_dry = dry
        self._apply_nr2_voice_protection(self._nr2_level if getattr(self, '_nr2_level', 0) else 2)

    def set_agc_top(self, db: float):
        """限制 AGC 最大补偿增益（默认 +20dB），避免把 NR2 残渣放大到满量程。"""
        if not self._initialized:
            return
        try:
            _wdsp.SetRXAAGCTop(ctypes.c_int(self.channel), ctypes.c_double(db))
            self._agc_top_db = db
        except Exception as e:
            print(f"⚠️ AGC top error: {e}")
```

- [ ] **步骤 5：`set_nr2_level()` 用等级表驱动 psi/zeta/上限**

替换其 `else:` 分支中"设置 psi/zeta"与"保持 AE"部分：

```python
                # 等级驱动：最大衰减为主轴，psi/zeta 为辅助
                self._nr2_ae_psi = WDSPNR2Level.PSI.get(level, 12.0)
                self._nr2_ae_zeta_thresh = WDSPNR2Level.ZETA_THRESH.get(level, 0.65)
                _wdsp.SetRXAEMNRaePsi(ctypes.c_int(self.channel), ctypes.c_double(self._nr2_ae_psi))
                _wdsp.SetRXAEMNRaeZetaThresh(ctypes.c_int(self.channel),
                                             ctypes.c_double(self._nr2_ae_zeta_thresh))
                self._apply_nr2_voice_protection(level)
```

并在 `level == 0` 分支把 `self._nr2_enabled = False` 之后的打印更新为 `🔧 WDSP NR2: OFF`（保持现状）。

- [ ] **步骤 6：`_init_wdsp()` / `set_agc_mode()` 用配置的 panel 与 AGC 顶**

- `_init_wdsp()`：`SetRXAPanelGain1(..., 0.06)` → `ctypes.c_double(self._panel_gain)`
- `set_agc_mode()`：末尾 `SetRXAPanelGain1(..., 0.06)` → `self._panel_gain`；并在设置完 attack/decay/hang 后加 `self.set_agc_top(self._agc_top_db)`
- `set_agc_mode()` 的 `WDSPAGCMode.OFF` 分支：`SetRXAAGCFixed(c_int(ch), c_double(1.0))` → `c_double(0.0)`（0 dB = 线性 1.0）
- AGC 时间常数（SSB）：`MED` → attack 6 / decay 500 / hang 500（`SLOW` → 6/750/750，其余保持）

- [ ] **步骤 7：`process()` 的 `-2` 改为保持上一块**

```python
            # error -2：输出未就绪（DSP 线程落后）。绝不注入原始输入——
            # 原始输入比处理后高约 18dB，会造成 5.3ms 响 click 与时间线跳变。
            if error.value == -2:
                self.starved_blocks += 1
                if self.starved_blocks % 200 == 1:
                    print(f"⚠️ WDSP 输出饥饿(-2) 累计 {self.starved_blocks} 次，保持上一块输出")
                if self._last_output is not None and len(self._last_output) == len(audio_data):
                    return self._last_output.copy()
                return np.zeros_like(audio_data)
            elif error.value != 0:
                print(f"⚠️ WDSP processing error: {error.value}")
```

并在成功路径末尾（`return output[:len(audio_data)]` 之前）：

```python
            result = output[:len(audio_data)]
            self._last_output = result
            return result
```

- [ ] **步骤 8：运行 A6 / A1 / A3**

```bash
python3 dev_tools/nr2_starve.py
python3 dev_tools/nr2_tone_gain.py
python3 dev_tools/nr2_prod_ab.py --secs 8
```
预期：A6 `PASS`（无 +6dB 以上突发，`starved_blocks > 0`）；A1 等级阶梯呈 −6/−9/−15/−19/−23 dB 左右；A3 中 NR2 ON(level2) `语音Δ ≥ −6 dB` 且 `NR静音 ≤ −12 dB`。

- [ ] **步骤 9：Commit**

```bash
git add wdsp_wrapper.py
git commit -m "feat(wdsp): NR2 等级映射到最大衰减 + AGC 封顶/panel/-2 保块（A1/A3/A6 通过）"
```

---

## 任务 5：配置、文档、规格一致性

**文件：**
- 修改：`audio_interface.py`
- 修改：`MRRC.conf`、`windows/MRRC.conf.template`
- 修改：`CHANGELOG.md`
- 修改：`docs/superpowers/specs/2026-09-13-nr2-ssb-optimization-design.md`

- [ ] **步骤 1：`audio_interface.py` 读新键**

`PyAudioCapture.wdsp_config` 里追加：

```python
                    'nr2_max_atten_db': config['WDSP'].getfloat('nr2_max_atten_db', None),
                    'nr2_dry': config['WDSP'].getfloat('nr2_dry', 0.0),
                    'agc_top_db': config['WDSP'].getfloat('agc_top_db', 20.0),
                    'panel_gain': config['WDSP'].getfloat('panel_gain', 0.35),
```

- [ ] **步骤 2：配置哈希同步（`_wdsp_config_hash`）**

在元组末尾追加：

```python
                                    cfg.get('agc_top_db', 20.0),
                                    cfg.get('panel_gain', 0.35),
                                    cfg.get('nr2_max_atten_db'),
                                    cfg.get('nr2_dry', 0.0),
```

- [ ] **步骤 3：创建与更新分支都传新参数**

创建处：

```python
                                        self.wdsp_processor = WDSPProcessor(
                                            sample_rate=wdsp_sr, buffer_size=wdsp_bs,
                                            mode=WDSPMode.USB,
                                            enable_nr2=cfg['nr2_enabled'],
                                            enable_nb=cfg['nb_enabled'],
                                            enable_anf=cfg['anf_enabled'],
                                            agc_mode=cfg['agc_mode'],
                                            nr2_ae_psi=cfg.get('nr2_ae_psi', 12.0),
                                            nr2_ae_zeta_thresh=cfg.get('nr2_ae_zeta_thresh', 0.65),
                                            nr2_max_atten_db=cfg.get('nr2_max_atten_db'),
                                            nr2_dry=cfg.get('nr2_dry', 0.0),
                                            agc_top_db=cfg.get('agc_top_db', 20.0),
                                            panel_gain=cfg.get('panel_gain', 0.35),
                                        )
```

更新分支追加：

```python
                                        self.wdsp_processor.set_agc_top(cfg.get('agc_top_db', 20.0))
                                        self.wdsp_processor.set_nr2_voice_protection(
                                            cfg.get('nr2_max_atten_db'), cfg.get('nr2_dry', 0.0))
```

- [ ] **步骤 4：`MRRC.conf` 与 `windows/MRRC.conf.template`**

两处在 `nr2_ae_zeta_thresh` 之后加（**默认注释掉 = 跟随等级表**）：

```ini
# NR2 语气保真度：每 bin 最大衰减(dB)。取消注释即"钉死"该上限，不再跟随 nr2_level 等级表
# 例：-6 极保真 / -12 推荐 / -20 强降噪。0 = 不限制(旧行为)
#nr2_max_atten_db = -12
# NR2 干湿混合(0~1)：>0 时 mask'=dry+(1-dry)*mask，比硬下限更平滑
nr2_dry = 0.0
# AGC 最大补偿增益(dB)：限制"先砍后狂补"的增益级（旧行为约 80）
agc_top_db = 20
# 输出电势 panel：AGC 输出(~0.98) × 此值；旧值 0.06（音量会明显变大，如有需要可调回）
panel_gain = 0.35
```

- [ ] **步骤 5：`CHANGELOG.md` 顶部加条目**

在 `## [V6.0.0]` 之前插入：

```markdown
## [未发布]

### 🔧 WDSP NR2（EMNR）SSB 语音保护

- 修复 NR2"声音变形过度"：EMNR 的最小统计噪声估计会把语音自身当噪声（实测单音 `gamma=0.97`、掩码 `0.022`），导致语音被整段削 10~33 dB 且几乎不区分信噪比；现限制每 bin 最大衰减（默认 −12 dB，等级 0–4 = −6/−12/−16/−20 dB）。
- 新增 `nr2_max_atten_db`（可选覆盖）、`nr2_dry`（干湿混合）、`agc_top_db`（AGC 补偿封顶，默认 +20 dB）、`panel_gain`（默认 0.35）。**注意：`panel_gain` 由 0.06 改为 0.35，RX 音量约提升 15 dB**。
- 修复 `bp1` 带通在非 NR 状态输出全零导致的 "NR2 关闭后 RX 静音"；SSB 带通改由 always-on 的 `nbp0` 承担，并移到 NR 之前（噪声估计更准）。
- 修复 `fexchange0` 输出饥饿时用原始输入顶替（比处理后高约 18 dB）造成的响 click，改为保持上一块输出并计数告警。
- 修正 `SetRXAAGCFixed` 单位（原按线性传 1.0 实为 +1 dB，现传 0.0=0 dB）。
```

- [ ] **步骤 6：规格一致性修正**

`docs/superpowers/specs/2026-09-13-nr2-ssb-optimization-design.md` §3.4：把 `nr2_max_atten_db = -12` 改为注释形态并说明"默认跟随等级表，取消注释即钉死"。

- [ ] **步骤 7：语法/导入检查**

```bash
python3 -m py_compile wdsp_wrapper.py audio_interface.py && echo OK
python3 -c "import configparser;c=configparser.ConfigParser();c.read('MRRC.conf');print(c['WDSP'])"
python3 dev_tools/test_installation.py 2>&1 | tail -5
```

- [ ] **步骤 8：Commit**

```bash
git add audio_interface.py MRRC.conf windows/MRRC.conf.template CHANGELOG.md \
        docs/superpowers/specs/2026-09-13-nr2-ssb-optimization-design.md
git commit -m "feat(config): NR2 语音保护/AGC 封顶/panel 配置项 + CHANGELOG"
```

---

## 任务 6：全量验收 A1–A9 与交付

- [ ] **步骤 1：跑 A1–A6**

```bash
python3 dev_tools/nr2_tone_gain.py          # A1
python3 dev_tools/nr2_mask.py               # A2（需 debug 库：见步骤 3）
python3 dev_tools/nr2_prod_ab.py --secs 8   # A3
for s in A C D; do python3 dev_tools/nr2_scenario_probe.py $s; done   # A4
python3 dev_tools/nr2_band_tf.py            # A5
python3 dev_tools/nr2_starve.py             # A6
```
预期：A1 阶梯达标；A3 `语音Δ ≥ −6 dB`、`NR ≤ −12 dB`；A4 三场景有声；A5 通带/阻带达标；A6 PASS。

- [ ] **步骤 2：A7 回退路径**

```bash
python3 - <<'EOF'
# 用配置回退到旧行为，确认与修复前一致（单音 level2 ≈ -37dB）
import subprocess, textwrap
print("见 dev_tools/nr2_floor_scan.py 的 '无(0.0)' 行（max_atten=0）")
EOF
python3 dev_tools/nr2_floor_scan.py | head -12
```
预期：`无(0.0)` 行的单音增益仍 ≈ −37 dB，证明上限=0 时行为可回退。

- [ ] **步骤 3：A2 内部状态（调试库，可选但推荐）**

```bash
bash dev_tools/wdsp_debug_build.sh     # 见下：构建 /tmp/wdsp_dbg（含 emnr_dump，不进生产源码）
WDSP_LIB=/tmp/wdsp_dbg/libwdsp.dylib python3 dev_tools/nr2_internals.py | head -12
```
预期：单音 bin 的 `mask ≥ 0.15`（修复前 0.022）。

`dev_tools/wdsp_debug_build.sh` 内容：

```bash
#!/usr/bin/env bash
# 构建"带内部 dump"的临时调试库（不改动生产源码）；供 nr2_internals.py 使用
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf /tmp/wdsp_dbg
cp -a "$ROOT/DSP/wdsp" /tmp/wdsp_dbg
python3 - "$ROOT" <<'PY'
import sys
root = sys.argv[1]
p = '/tmp/wdsp_dbg/emnr.c'
s = open(p).read()
s = s.rstrip() + '''

PORT void emnr_dump (int channel, int what, double* out, int* msize)
{
	EMNR a = rxa[channel].emnr.p;
	int k;
	*msize = a->msize;
	for (k = 0; k < a->msize; k++)
	{
		switch (what)
		{
		case 0: out[k] = a->g.lambda_y[k];   break;
		case 1: out[k] = a->g.lambda_d[k];   break;
		case 2: out[k] = a->mask[k];         break;
		case 3: out[k] = a->np.p[k];         break;
		case 4: out[k] = a->np.sigma2N[k];   break;
		case 5: out[k] = a->g.prev_gamma[k]; break;
		case 6: out[k] = a->np.alphaHat[k];  break;
		}
	}
}
'''
open(p, 'w').write(s)
PY
cd /tmp/wdsp_dbg && make CFLAGS="-I/opt/local/include"
echo "调试库: /tmp/wdsp_dbg/libwdsp.dylib"
```
（需 `chmod +x dev_tools/wdsp_debug_build.sh` 并提交。）

- [ ] **步骤 4：A8 回归**

```bash
python3 dev_tools/test_installation.py 2>&1 | tail -8
python3 dev_tools/nr2_scenario_probe.py E      # NF/NB 路径仍工作
```
外加人工：MRRC 启动 → RX 有声、切 NR2 关/开无静音、PTT/TX、ATR-1000 仪表刷新正常（需用户在工作机上确认；**不要擅自重启正在使用的电台服务**）。

- [ ] **步骤 5：A9 试听产物**

`dev_tools/nr2_prod_ab.py` 已写出 `dev_tools/nr2_out/prod_*.wav`（修复前/后对照）；把它们交给用户试听确认。

- [ ] **步骤 6：最终提交**

```bash
git add dev_tools/wdsp_debug_build.sh dev_tools/nr2_*.py
git commit -m "test(nr2): 调试库构建脚本 + 探针工具集（A1-A9 验收）"
git log --oneline -6
```

---

## 自检记录

- **规格覆盖度**：§3.1→任务 2；§3.2→任务 3；§3.3→任务 4；§3.4→任务 5；§3.6 打包→任务 3/6（Docker 不适用已说明）；§4 A1–A9→任务 1/6；§5 回退→任务 6 步骤 2/3。
- **占位符扫描**：无 TODO/待定；每个代码步骤都给了完整代码与预期输出。
- **类型一致性**：`SetRXAEMNRmaxAttenDb` / `SetRXAEMNRdry` / `SetRXANBPFreqs`（C 与 Python 命名一致）；`_apply_nr2_voice_protection` / `set_nr2_voice_protection` / `set_agc_top` / `_last_output` / `starved_blocks` 在任务 4 内定义并在任务 5/6 使用，命名前后一致。
- **规格偏差（已知并记录）**：`nr2_max_atten_db` 采用"可选覆盖"语义（默认注释掉，等级表为默认来源），与规格 §3.4 的写法不同 → 任务 5 步骤 6 同步修正规格。

# WDSP NR2 降噪/数码音平衡优化 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重写 NR2 级别体系消除数码音，简化配置暴露

**Architecture:** 修改 `wdsp_wrapper.py` 中 `set_nr2_level()` 和 `_setup_nr2()` 的参数表，将默认统计模型从 Gamma 切换到 Gaussian，NR2 位置从 AGC 后改为 AGC 前；精简 `MRRC.conf` WDSP 节

**Tech Stack:** Python 3, ctypes (WDSP C library)

---

### Task 1: 重写 `_setup_nr2()` 初始参数 + Position 修复

**Files:**
- Modify: `wdsp_wrapper.py:228-250`

- [ ] **Step 1: 修改 `_setup_nr2()` — 默认参数改为 Gaussian + Position=0**

将 `_setup_nr2()` 中硬编码的初始化参数替换：

```python
def _setup_nr2(self):
    """Setup Spectral Noise Reduction (NR2) - 默认 Gaussian 温和降噪"""
    try:
        _wdsp.SetRXAANRRun(ctypes.c_int(self.channel), ctypes.c_int(0))

        _wdsp.SetRXAEMNRRun(ctypes.c_int(self.channel), ctypes.c_int(1))

        # 默认参数: Gaussian(自然), OSMS(平滑), AE=ON(消音乐噪音)
        _wdsp.SetRXAEMNRgainMethod(ctypes.c_int(self.channel), ctypes.c_int(0))
        _wdsp.SetRXAEMNRnpeMethod(ctypes.c_int(self.channel), ctypes.c_int(0))
        _wdsp.SetRXAEMNRaeRun(ctypes.c_int(self.channel), ctypes.c_int(1))
        # Position=0: 在 AGC 之前降噪，避免 AGC 放大残留噪声
        _wdsp.SetRXAEMNRPosition(ctypes.c_int(self.channel), ctypes.c_int(0))

        self._nr2_enabled = True
        self._nr2_level = 2  # 默认温和
        print(f"   NR2 (EMNR) configured - Gaussian, OSMS, AE=ON, Pre-AGC (温和)")
    except Exception as e:
        print(f"   ⚠️ NR2 setup error: {e}")
```

- [ ] **Step 2: 验证语法** — `python3 -c "import py_compile; py_compile.compile('wdsp_wrapper.py', doraise=True)"`

---

### Task 2: 重写 `set_nr2_level()` 四级参数表

**Files:**
- Modify: `wdsp_wrapper.py:252-301`

- [ ] **Step 1: 替换 `set_nr2_level()` 方法体**

```python
def set_nr2_level(self, level: int):
    """
    Set NR2 intensity level.

    Args:
        level: 0-4
            0 = OFF
            1 = MIN  — Gaussian + OSMS + AE=OFF (极温和，无处理痕迹)
            2 = LOW  — Gaussian + OSMS + AE=ON  (温和，日常推荐)
            3 = MED  — Gaussian(log) + MMSE + AE=ON (中等噪声)
            4 = HIGH — Gaussian(log) + MMSE + AE=ON (强噪声，优先可懂度)
    """
    if not self._initialized:
        return

    try:
        if level == 0:
            _wdsp.SetRXAEMNRRun(ctypes.c_int(self.channel), ctypes.c_int(0))
            _wdsp.SetRXAANRRun(ctypes.c_int(self.channel), ctypes.c_int(0))
            self._nr2_enabled = False
            self._nr2_level = 0
            print(f"🔧 WDSP NR2: OFF")
        else:
            _wdsp.SetRXAANRRun(ctypes.c_int(self.channel), ctypes.c_int(0))
            _wdsp.SetRXAEMNRRun(ctypes.c_int(self.channel), ctypes.c_int(1))

            # Level → (gainMethod, npeMethod, aeRun)
            # gainMethod: 0=Gaussian, 1=Gaussian(log)
            # npeMethod: 0=OSMS(最优平滑), 1=MMSE
            params = {
                1: (0, 0, 0),  # 极温和: Gaussian + OSMS, 无AE
                2: (0, 0, 1),  # 温和:   Gaussian + OSMS + AE
                3: (1, 1, 1),  # 中等:   Gaussian(log) + MMSE + AE
                4: (1, 1, 1),  # 强力:   Gaussian(log) + MMSE + AE
            }
            gain_method, npe_method, ae_run = params.get(level, (0, 0, 1))

            _wdsp.SetRXAEMNRgainMethod(ctypes.c_int(self.channel), ctypes.c_int(gain_method))
            _wdsp.SetRXAEMNRnpeMethod(ctypes.c_int(self.channel), ctypes.c_int(npe_method))
            _wdsp.SetRXAEMNRaeRun(ctypes.c_int(self.channel), ctypes.c_int(ae_run))
            # 保持 Position=0 (AGC 前)
            _wdsp.SetRXAEMNRPosition(ctypes.c_int(self.channel), ctypes.c_int(0))

            self._nr2_enabled = True
            self._nr2_level = level
            level_names = {1: 'MIN(极温和)', 2: 'LOW(温和)', 3: 'MED(中等)', 4: 'HIGH(强力)'}
            print(f"🔧 WDSP NR2: {level_names.get(level, level)} (gain={gain_method}, npe={npe_method}, ae={ae_run})")
    except Exception as e:
        print(f"⚠️ NR2 level error: {e}")
```

- [ ] **Step 2: 验证语法** — `python3 -c "import py_compile; py_compile.compile('wdsp_wrapper.py', doraise=True)"`

---

### Task 3: 精简 `MRRC.conf` WDSP 配置节

**Files:**
- Modify: `MRRC.conf` WDSP section

- [ ] **Step 1: 替换 `[WDSP]` 节**

找到 `[WDSP]` 节，替换为简化版本：

```ini
[WDSP]
# WDSP 数字信号处理（Warren Pratt's DSP Library）
# 编译安装: https://github.com/g0orx/wdsp
enabled = True
sample_rate = 48000
buffer_size = 256

# 降噪级别: 0=关, 1=极温和, 2=温和(推荐), 3=中等, 4=强力
nr2_level = 2

# 噪声抑制器（脉冲干扰: 电器火花、雷电等）
nb_enabled = True

# 自动陷波器（CW 干扰音）
anf_enabled = False

# AGC 模式: 0=关, 1=长, 2=慢, 3=中(推荐), 4=快
agc_mode = 3

# 带通滤波器 (Hz) - SSB 语音核心频段
bandpass_low = 300.0
bandpass_high = 2700.0
```

- [ ] **Step 2: 确认旧参数已移除** — 确认 `nr2_gain_method`、`nr2_npe_method`、`nr2_ae_run` 三个键已不在 WDSP 节中

---

### Task 4: 验证兼容性

**Files:**
- Read: `audio_interface.py:186-190`

- [ ] **Step 1: 确认 `audio_interface.py` 读取的配置键不包含已移除的三个参数**

```bash
grep -n "nr2_gain_method\|nr2_npe_method\|nr2_ae_run" audio_interface.py
```
期望：无输出（或确认这些键在 config 读取逻辑中有默认值兜底）

- [ ] **Step 2: 若 `audio_interface.py` 仍引用已移除键，添加默认值兜底**

检查第 180-181 行附近的读取逻辑。如果引用 `nr2_gain_method`、`nr2_npe_method`、`nr2_ae_run`，保留读取但加 `.getint(..., default)` 确保不报错。

- [ ] **Step 3: 运行 Python 语法检查**

```bash
python3 -c "import py_compile; py_compile.compile('wdsp_wrapper.py', doraise=True); print('OK')"
python3 -c "import py_compile; py_compile.compile('audio_interface.py', doraise=True); print('OK')"
```

---

### Task 5: 提交

- [ ] **Step 1: 提交变更**

```bash
git add wdsp_wrapper.py MRRC.conf
git commit -m "fix: WDSP NR2 级别重写 — Gaussian 替代 Gamma 消除数码音

NR2 四级参数表重构为 Gaussian/OSMS 体系，消除音乐噪音和数码音。
NR2 Position 从 AGC 后改为 AGC 前，避免 AGC 放大残留噪声。
MRRC.conf 精简，移除底层参数(nr2_gain_method/npe_method/ae_run)，
内置于 level 体系，用户只需选 0-4。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

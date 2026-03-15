# MRRC 数字信号处理 (DSP) 文档

**版本**: V4.9.0 (2026-03-14)  
**更新**: 添加项目目录库路径支持，优化日志输出

## 概述

MRRC (Mobile Remote Radio Control) 集成了 **WDSP (Warren Pratt's Digital Signal Processing)** 库，为短波 SSB 语音通信提供专业级的音频处理功能。

WDSP 是 OpenHPSDR 项目的高性能 DSP 库，被广泛应用于 Thetis、piHPSDR 等专业业余无线电软件中。

---

## 已实现的 DSP 功能

### 1. 降噪 (NR/NR2)

| 算法 | 名称 | 特点 | 推荐使用场景 |
|------|------|------|-------------|
| **NR2** | 频谱降噪 (Spectral) | 基于谱减法，语音保真度高 | **SSB 语音通信（推荐）** |
| NR | LMS 自适应降噪 | 计算量小，实时性好 | 通用背景噪声 |

**用户反馈**："NR2 让 SSB 听起来像 FM，效果非常出色" — Thetis 用户

### 2. 噪声抑制器 (NB/NB2)

- **NB**: 噪声抑制器，消除脉冲干扰（电器火花、雷电等）
- **NB2**: 高级频谱噪声抑制

### 3. 自动陷波器 (ANF)

自动检测并消除单频干扰（如 CW 报音、载波干扰）。

### 4. 自动增益控制 (AGC)

| 模式 | 名称 | 攻击时间 | 衰减时间 | 适用场景 |
|------|------|---------|---------|---------|
| OFF | 关闭 | - | - | 信号强且稳定 |
| LONG | 长 | 4ms | 2000ms | 弱信号 DX |
| SLOW | 慢 | 4ms | 500ms | 一般 SSB |
| **MED** | **中** | **4ms** | **250ms** | **常规通信（推荐）** |
| FAST | 快 | 2ms | 100ms | 快速变化信号 |

### 5. 带通滤波器

可配置低切和高切频率，默认 SSB 优化：
- 低切：300 Hz
- 高切：2700 Hz

---

## 架构与流程

### 音频处理链路

```
电台音频 (48kHz)
    ↓
PyAudio 采集
    ↓
DC 去除 → AGC 预放大 → 软削波保护
    ↓
Int16 转换
    ↓
WDSP 处理 (48kHz)
    ├── NR2 频谱降噪
    ├── NB 噪声抑制
    ├── ANF 自动陷波
    └── AGC 自动增益
    ↓
Opus 编码 (16kHz/20kbps)
    ↓
WebSocket 传输
    ↓
前端解码播放
```

### 关键设计决策

1. **采样率 48kHz**: WDSP 在 48kHz 下效果最佳，保留完整语音频段
2. **处理顺序**: WDSP 在 Int16 转换后、Opus 编码前执行
3. **与 RNNoise 的关系**: WDSP 替代 RNNoise，效果更适合 SSB 语音
4. **缓冲区**: 256 样本缓冲区，平衡延迟与处理效率

---

## 配置说明

### MRRC.conf 配置

```ini
[WDSP]
# WDSP 数字信号处理模块（Warren Pratt's DSP Library）
# 提供专业的业余无线电音频处理功能，替代 RNNoise
# 需要先编译安装 WDSP 库: https://github.com/g0orx/wdsp
enabled = True

# 采样率，支持 16000 或 48000（推荐 48000）
sample_rate = 48000

# 处理缓冲区大小 (128, 256, 512, 1024)
buffer_size = 256

# ===== 噪声抑制 =====
# NR2: 频谱降噪（推荐用于SSB语音）
nr2_enabled = True

# 噪声抑制器（脉冲干扰）
nb_enabled = True

# 自动陷波器（消除CW干扰音）
anf_enabled = False

# ===== AGC 自动增益控制 =====
# 模式: 0=OFF, 1=LONG, 2=SLOW, 3=MED, 4=FAST
agc_mode = 3

# ===== 带通滤波器 =====
# 低切频率 (Hz)
bandpass_low = 300.0
# 高切频率 (Hz)
bandpass_high = 2700.0
```

### 前端控制

在移动端界面：
1. 打开菜单 → 设置
2. 找到"🎛️ WDSP 数字处理"部分
3. 可实时控制：
   - WDSP 主开关
   - NR2 频谱降噪
   - NB 噪声抑制
   - ANF 自动陷波
   - AGC 模式

---

## 安装 WDSP 库

### macOS

```bash
# 克隆仓库
cd /tmp
git clone https://github.com/g0orx/wdsp.git
cd wdsp

# 编译（需要 fftw3）
brew install fftw
make

# 安装到系统
cp libwdsp.dylib /usr/local/lib/
```

### Linux

```bash
cd /tmp
git clone https://github.com/g0orx/wdsp.git
cd wdsp

# Debian/Ubuntu
sudo apt-get install libfftw3-dev

# 编译
make
sudo cp libwdsp.so /usr/local/lib/
sudo ldconfig
```

---

## 效果对比

### WDSP vs RNNoise

| 特性 | WDSP (NR2) | RNNoise |
|------|-----------|---------|
| 算法类型 | 频谱减法 (Spectral) | 神经网络 |
| 语音保真度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 降噪深度 | 15-20 dB | 10-15 dB |
| 延迟 | 低 (< 20ms) | 中 (30-50ms) |
| CPU 占用 | 低 | 中 |
| SSB 优化 | ✅ 专门优化 | ❌ 通用语音 |
| 参数可调 | ✅ 多项参数 | ❌ 固定模型 |

**结论**: 对于短波 SSB 语音通信，WDSP 的 NR2 算法明显优于 RNNoise。

### 不同降噪算法对比

| 算法 | 降噪增益 | 语音保真度 | 最佳场景 |
|------|---------|-----------|---------|
| NR2 (频谱) | 15-20 dB | 极高 | **SSB 语音（推荐）** |
| NR (LMS) | 10-15 dB | 高 | 通用背景噪声 |
| NB | - | - | 脉冲干扰 |
| ANF | - | - | 单频干扰 |

---

## 故障排查

### WDSP 未加载

```
⚠️ WDSP 已启用但库不可用
```

**解决**:
```bash
# 检查库是否存在
ls /usr/local/lib/libwdsp.*

# 如果不存在，重新编译安装
cd /tmp/wdsp && make && sudo cp libwdsp.* /usr/local/lib/
```

### 音频无输出

WDSP 需要预热（约 10 帧）才能正常输出。这是正常的，因为 WDSP 使用 ring buffer 机制。

### 效果不明显

1. 检查 `enabled = True` 是否设置
2. 确认 `nr2_enabled = True` 已启用
3. 调整 `bandpass_low` 和 `bandpass_high` 匹配当前模式
4. 检查 AGC 模式是否合适

---

## 技术参考

### WDSP API 关键函数

```c
// 创建通道
OpenChannel(channel, in_size, dsp_size, input_rate, dsp_rate, output_rate, type, state, ...)

// 处理音频
fexchange0(channel, in_buffer, out_buffer, &error)

// 设置 NR2
SetRXAEMNRRun(channel, 1)        // 启用
SetRXAEMNRgainMethod(channel, 0) // 增益方法
SetRXAEMNRnpeMethod(channel, 1)  // NPE 方法
SetRXAEMNRPosition(channel, 1)   // 位置 (0=AGC前, 1=AGC后)

// 设置 AGC
SetRXAAGCMode(channel, mode)     // 模式 0-4
SetRXAAGCAttack(channel, attack) // 攻击时间
SetRXAAGCDecay(channel, decay)   // 衰减时间

// 获取 S-meter
GetRXAMeter(channel, S_PK)
```

### 参考资料

- [WDSP GitHub](https://github.com/g0orx/wdsp)
- [OpenHPSDR](https://openhpsdr.org/)
- [Thetis Wiki](https://github.com/TAPR/OpenHPSDR-Thetis/wiki)

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| V4.9.0 | 2026-03-14 | 语音助手、CW实时解码、SDR界面、多实例支持 |
| V4.7.0 | 2026-03-10 | 优化库路径加载，支持项目目录直接运行；清理调试日志输出 |
| V4.6.1 | 2026-03-10 | 修复WDSP初始化BUG，优化PanelGain和NR2参数 |
| V4.6.0 | 2026-03-09 | 初始 WDSP 集成，支持 NR2/NB/ANF/AGC |

---

*WDSP 集成让 MRRC 的音频质量达到专业业余无线电软件水准。*
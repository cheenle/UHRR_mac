# WDSP 数字信号处理详解

**版本**: V4.7.0 (2026-03-10)  
**更新**: 库路径优化，日志清理

## 概述

WDSP (Warren Pratt's Digital Signal Processing) 是 OpenHPSDR 项目的高性能 DSP 库，被广泛应用于 Thetis、piHPSDR 等专业业余无线电软件。MRRC 集成了 WDSP，提供专业级的音频降噪和处理能力。

### 核心功能

| 功能 | 缩写 | 说明 |
|------|------|------|
| 频谱降噪 | NR2 | 基于谱减法，专门针对 SSB 语音优化 |
| 噪声抑制 | NB | 消除脉冲干扰（雷电、电器火花） |
| 自动陷波 | ANF | 消除单频干扰（CW 报音） |
| 自动增益 | AGC | 自动调节输出电平 |

---

## 参数详解

### 1. NR2 频谱降噪 (EMNR)

**原理**：频谱减法，将噪声频谱从信号中分离

#### NR2 强度 (nr2_level)

| 级别 | 数值范围 | 效果 | 适用场景 |
|------|----------|------|----------|
| 关闭 | 0 | 无降噪 | 干净信号 |
| L1 | 1 | 温和降噪 | 轻微底噪 |
| L2 | 2 | 中等降噪 | 一般底噪 |
| L3 | 3 | 强降噪 | 较强底噪 |
| L4 | 4 | 最强降噪 | 极强底噪 |

**注意**：过高的 NR2 级别会导致"音乐噪音"（Musical Noise），即在安静时段出现类似水珠的杂音。

#### NR2 Gain Method

| 值 | 名称 | 效果 |
|----|------|------|
| 0 | Gaussian | 最保守，适合语音 |
| 1 | Gaussian(log) | 中等 |
| 2 | Gamma | 激进，降噪更强 |

**推荐**：语音通信使用 **0**

#### NR2 NPE Method

| 值 | 名称 | 效果 |
|----|------|------|
| 0 | OSMS | 最优平滑，适合平稳噪声 |
| 1 | MMSE | 最小均方误差 |

**推荐**：使用 **0**

#### NR2 Auto-Equalization (aeRun)

- **开启**：自动均衡，消除"音乐噪音"
- **关闭**：可能有更多失真

**推荐**：**必须开启**

---

### 2. NB 噪声抑制器

**原理**：检测并消除脉冲型干扰

| 状态 | 效果 |
|------|------|
| 开启 | 消除雷电、电器开关等脉冲噪声 |
| 关闭 | 保留原始信号 |

**推荐**：底噪环境良好时关闭，脉冲干扰多时开启

---

### 3. ANF 自动陷波

**原理**：自动检测并消除单频连续干扰

| 状态 | 效果 |
|------|------|
| 开启 | 消除 CW 报音、载波干扰 |
| 关闭 | 保留原始信号 |

**推荐**：有 CW 干扰时开启

---

### 4. AGC 自动增益控制

**原理**：自动调节输出电平，保持音量稳定

| 模式 | 值 | 响应速度 | 适用场景 |
|------|-----|----------|----------|
| OFF | 0 | 无（固定增益） | 录音、直通 |
| LONG | 1 | 最慢（6ms 攻击） | 稳定信号 |
| SLOW | 2 | 慢（4ms 攻击） | SSB 推荐 |
| MED | 3 | 中等（4ms 攻击） | 默认推荐 |
| FAST | 4 | 快（2ms 攻击） | 快速衰落 |

#### AGC OFF 模式

当 AGC 设置为 OFF 时：
- 使用固定增益（默认 1.0）
- 无自动增益调节
- 适合连接外部压缩器
- **MRRC 特殊处理**：自动设置 PanelGain1 = 0.1 防止内部放大

#### AGC 目标电平

- **默认值**：-3.0 dB
- 数值越小，输出越响

---

## 配置方案推荐

### 方案一：安静环境（推荐）

适用于底噪较小的电台环境

```ini
[WDSP]
enabled = True
nr2_enabled = True
nr2_level = 2
nr2_gain_method = 0
nr2_npe_method = 0
nr2_ae_run = True
nb_enabled = False
anf_enabled = False
agc_mode = 2  # SLOW
```

### 方案二：嘈杂环境

适用于底噪较大的情况

```ini
[WDSP]
enabled = True
nr2_enabled = True
nr2_level = 3
nr2_gain_method = 0
nr2_npe_method = 0
nr2_ae_run = True
nb_enabled = True
anf_enabled = True
agc_mode = 3  # MED
```

### 方案三：最强降噪

适用于严重底噪

```ini
[WDSP]
enabled = True
nr2_enabled = True
nr2_level = 4
nr2_gain_method = 2  # 激进
nr2_npe_method = 0
nr2_ae_run = True
nb_enabled = True
anf_enabled = True
agc_mode = 3
```

### 方案四：无失真直通

适用于追求最原始音质

```ini
[WDSP]
enabled = True
nr2_enabled = False
nb_enabled = False
anf_enabled = False
agc_mode = 0  # OFF
```

---

## 内部机制说明

### WDSP 增益结构

```
输入 → PanelGain1 → NR2/NB/ANF → AGC → 输出
                    ↓
              内部放大约 16x
```

**关键发现**：WDSP 内部会将信号放大约 16 倍，这是导致削波失真的根本原因。

### MRRC 特殊处理

为防止削波失真，MRRC 初始化时自动设置：

1. **PanelGain1 = 0.1**：抵消内部 16x 放大
2. **AGC OFF 时 SetRXAAGCFixed(1.0)**：固定增益，无额外放大

---

## 性能测试数据

### SNR 提升对比

| 配置 | 峰值 | SNR | SNR 提升 |
|------|------|-----|-----------|
| 原始 | 0.081 | 5.5dB | - |
| NR2 L0 (关闭) | 0.087 | ~5.5dB | 0dB |
| NR2 L3 | 0.093 | 12.4dB | **+6.8dB** |

### 峰值对比

| 配置 | 原始峰值 | WDSP 峰值 | 放大倍数 |
|------|----------|-----------|----------|
| 未修复 | 0.081 | 2.58 | 31.8x ❌ |
| 修复后 | 0.081 | 0.087 | 1.07x ✅ |

---

## 故障排查

### 问题：开启 WDSP 后声音失真

**原因**：WDSP 内部放大导致削波

**解决**：
1. 确保使用 AGC OFF 模式（agc_mode = 0）
2. 或使用 SLOW/MED 模式

### 问题：NR2 产生"音乐噪音"

**原因**：NR2 强度过高

**解决**：
1. 降低 nr2_level
2. 确保 nr2_ae_run = True

### 问题：底噪反而变大

**原因**：WDSP 增益设置不当

**解决**：
1. 检查 PanelGain1 是否正确设置
2. 尝试不同的 AGC 模式

### 问题：CW 干扰未消除

**原因**：ANF 未开启

**解决**：
1. 设置 anf_enabled = True

---

## 前端控制

### 移动端界面

访问 `mobile_modern.html` → 设置 → WDSP 数字处理

- WDSP 处理：主开关
- NR2：降噪级别（0-4）
- NB：噪声抑制
- ANF：自动陷波
- AGC：模式选择

### 高级设置页面

访问 `wdsp_settings.html`

可调整更多高级参数：
- NR2 Gain Method
- NR2 NPE Method
- NR2 Auto-Equalization
- 带通滤波器频率

---

## 参考文献

- WDSP 官方仓库：https://github.com/g0orx/wdsp
- OpenHPSDR 项目
- piHPSDR 文档

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| V4.7.0 | 2026-03-10 | 添加项目目录库路径支持；清理调试日志；AGC参数优化 |
| V4.6.1 | 2026-03-10 | 修复初始化BUG，优化PanelGain和NR2参数 |
| V4.6.0 | 2026-03-09 | 初始WDSP集成 |

# WDSP NR2 降噪/数码音平衡优化

**日期**: 2026-05-31
**状态**: 已批准
**范围**: `wdsp_wrapper.py` + `MRRC.conf`

## 问题

NR2 频谱降噪产生"数码音/水下音"（音乐噪音），用户无法在降噪强度和自然音质之间找到平衡。

## 根因

1. **gainMethod=2 (Gamma)** — 过于激进的统计模型，对语音频谱包络估计错误，产生孤立频谱峰（音乐噪音）
2. **npeMethod=1 (MMSE)** — 在 AGC 之后处理已放大的噪声，加剧伪影
3. **4 个 NR2 级别参数无区分度** — level 2-4 使用完全相同的参数
4. **带通滤波器被禁用** — 缺少频段限制，NR2 在全频段做无效噪声估计
5. **NR2 Position=1 (AGC 后)** — AGC 先放大噪声，NR2 再处理已放大的噪声

## 方案

### wdsp_wrapper.py 变更

**`set_nr2_level()` 重写**：

| Level | gainMethod | npeMethod | aeRun | 场景 |
|-------|-----------|-----------|-------|------|
| 0 | — | — | — | 关闭 |
| 1 | 0 (Gaussian) | 0 (OSMS) | OFF | 极温和，无处理痕迹 |
| 2 | 0 (Gaussian) | 0 (OSMS) | ON  | 温和，日常推荐 |
| 3 | 1 (Gaussian/log) | 1 (MMSE) | ON  | 中等噪声 |
| 4 | 1 (Gaussian/log) | 1 (MMSE) | ON  | 强噪声，优先可懂度 |

**NR2 Position 改为 0**（AGC 前），第244行：`SetRXAEMNRPosition(channel, 1)` → `SetRXAEMNRPosition(channel, 0)`

### MRRC.conf 变更

精简 WDSP 节，移除暴露的底层参数（`nr2_gain_method`、`nr2_npe_method`、`nr2_ae_run`），参数内置于 level 体系：

```ini
[WDSP]
enabled = True
sample_rate = 48000
buffer_size = 256
nr2_level = 2
nb_enabled = True
anf_enabled = False
agc_mode = 3
bandpass_low = 300.0
bandpass_high = 2700.0
```

## 不变项

- 前端 JS 无需改动（`setWDSPNR2Level` 接口不变）
- `audio_interface.py` 无需改动（配置读取兼容）
- 向后兼容：config 旧参数会被忽略，不影响运行

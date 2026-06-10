# SWR Meter 模块 — 从 ModularTuner 复用

## 源文件位置

从 `ModularTuner/code/tuner/` 复制以下文件到本目录:

```
swrmeter.cpp      — Tandem Match 定向耦合器采样
swrmeter.h        — SWRMeter 类定义
complex.cpp       — 复数运算
complex.h         — Complex 类
frequencyCounter.cpp — 频率计数器 (TIM4_CH4, PB9)
frequencyCounter.h
```

## 校准参数 (EFHW Tuner 专用)

ModularTuner 原版使用 5V Arduino ADC。STM32 ADC 为 **3.3V / 12-bit**:

| 参数 | 原版 (5V/10-bit) | 本设计 (3.3V/12-bit) |
|------|:---------------:|:-------------------:|
| ADC 满量程 | 1023 | 4095 |
| LSB 电压 | 4.88 mV | 0.81 mV |
| FWD 满功率 (100W) 期望 ADC | ~800 | ~3200 |
| REV 零反射时期望 ADC | <10 | <5 |

**注意事项**:
1. SWR 桥分压电阻需根据 3.3V ADC 重新计算 (原版按 5V 设计)
2. 建议 FWD/REV 检波器输出端加分压电阻 (如 10kΩ + 10kΩ) 适配 3.3V
3. `swr_calib_parms` 的 offset/scale 需重新台架校准

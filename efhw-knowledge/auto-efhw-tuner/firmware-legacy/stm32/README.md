# EFHW Auto Tuner 100W — STM32F103 固件

> 基于 **profdc9/ModularTuner** (Copyright 2018 Daniel Marks, CC-BY-SA 4.0)
> 适配: BG1SB (2026-06-08) — 纯电容 EFHW 专用版

---

## 架构概览

```
efhw_tuner_stm32.ino          ← 主程序 (setup/loop/调谐算法/串口控制台)
tuner_config.h                ← 引脚映射 + 全部参数

lib/
├── swrmeter/                 ← 从 ModularTuner 直接复用
│   ├── swrmeter.h/cpp        ← Tandem Match 检波器 (保留原版)
│   ├── complex.h/cpp         ← 复数运算
│   └── frequencyCounter.h/cpp ← 频率计数器
│
├── capbank/                  ← 🆕 替代 ModularTuner RelayModule
│   └── capbank.h/cpp         ← 7位电容阵列 GPIO 直驱 + 缓存
│
├── post/                     ← 🆕 上电自检
│   └── post.h/cpp            ← 4阶段 POST (DC/ADC/继电器/SWR)
│
└── diag/                     ← 🆕 运行时诊断
    └── diag.h/cpp            ← 故障检测 + 健康状态机
```

## 从 ModularTuner 复用的文件

直接从 `ModularTuner/code/tuner/` 复制以下文件到 `lib/swrmeter/`:

| 文件 | 改动 |
|------|:----:|
| `swrmeter.cpp` / `swrmeter.h` | **无改动** — API 完全匹配 |
| `complex.cpp` / `complex.h` | 无改动 |
| `frequencyCounter.cpp` / `frequencyCounter.h` | 无改动 |
| `flashstruct.cpp` / `flashstruct.h` | 改动: Flash 页地址适配 |
| `mini-printf.c` / `mini-printf.h` | 无改动 |
| `debugmsg.cpp` / `debugmsg.h` | 可选 (调试用) |

## 相比 ModularTuner 的裁剪

| 删除的模块 | 原因 |
|-----------|------|
| `RelayModule.cpp/h` (多模块 MCP23017 I2C) | → 替换为 `capbank.cpp` GPIO 直驱 |
| `LNetwork.cpp/h` (L/T/Pi 网络切换) | → EFHW 仅需固定 42.25:1 自耦变压器 |
| `interface.cpp/h` (LCD 1602 界面) | → 室外无屏幕 |
| `remote.cpp/h` (HC-12 无线) | → 无此需求 |
| `consoleio.cpp/h` (控制台 I/O) | → 简化串口命令 |
| `tinycl.cpp/h` (命令行解析器) | → 简化串口命令 |
| `structconf.cpp/h` (结构化配置) | → 硬编码 `tuner_config.h` |
| 电台控制 (Icom/Kenwood/Yaesu) | → 无 CAT 需求 |

## 关键设计决策

1. **GPIO 直驱 vs I2C 扩展**: ModularTuner 使用 MCP23017 I2C 扩展芯片驱动继电器。本项目改用 STM32 GPIO 直驱 (PA8-14 经 ULN2003A)，减少元件、降低故障点。
2. **SWD 保留**: PA13/PA14 在开发阶段保持 SWD 功能，电容阵列 bit5/bit6 改用 PB3/PB4 备用引脚。
3. **纯电容扫描**: 删除 ModularTuner 的 7 配置切换 + 多继电器模块 + 二分搜索，替换为 128 步全扫描 + 早期退出 (SWR<1.05)。
4. **Flash 存储**: 复用 ModularTuner 的 `flashstruct` 将缓存持久化到 STM32 内部 Flash (页 0x0801FC00)。

## 编译

```bash
# Arduino IDE:
#   Board: "Generic STM32F103C series" → "BluePill F103C8"
#   Upload method: "STLink" 或 "Serial"
#
# PlatformIO:
#   platform = ststm32
#   board = bluepill_f103c8
#   framework = arduino
```

## 许可

- 原始 ModularTuner 代码: CC-BY-SA 4.0 (Daniel Marks, KW4TI)
- 本项目修改部分: GPL-3.0

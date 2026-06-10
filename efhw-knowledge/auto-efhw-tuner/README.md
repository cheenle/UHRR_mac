# EFHW Fuchs ATU V3.0 — ESP32-S3 连续伺服调谐适配器

> 基于 F5NPV Fuchs 并联 LC 耦合器理论 × ESP-IDF v5.x 原生 C
> 硬件许可: CERN-OHL-S 2.0 | 固件许可: GPL-3.0
> **在线 SDD**: [ybr387rz.mule.page](https://ybr387rz.mule.page/) — 14章完整软件设计规格书
> **版本历史**: [CHANGELOG.md](CHANGELOG.md)

## 项目简介

一台**室外架设、Bias-T 同轴馈电、WiFi 远程全自动调谐**的 100W 末端馈电半波天线适配器。ESP32-S3 驱动 MG996R 伺服电机控制空气可变电容连续调谐，SWR 感知完全委托给 MRRC 侧的 ATR1000，ATU 是纯执行机构。

## 核心技术指标

| 参数 | 值 |
|------|-----|
| MCU | ESP32-S3-WROOM-1 (240MHz 双核 Xtensa LX7, 16MB Flash) |
| 频率 | 40m–10m (7.0–29.7 MHz, WARC 全覆盖) |
| 功率 | 100W PEP SSB/CW |
| 磁芯 | T200-6 ×1 (Type 6 羰基铁粉, μ=8) |
| 匝数比 | 2:14 → 49:1 阻抗比 → 匹配 ~2,450Ω |
| 电容 | 发射机级空气可变 10-500pF, ≥5kV或片距≥1.5mm, 伺服连续驱动 |
| 调谐方式 | 粗扫 37 点 @5°/步(0-180°) + 细扫 30 步 @1°/步 |
| 调谐时间 | < 10s (全扫描) / < 1s (NVS 缓存命中) |
| SWR 感知 | 无板载 SWR — 完全由 MRRC ATR1000 远程提供 |
| 通信 | WiFi 2.4GHz WebSocket → MRRC 深度集成 |
| 供电 | Bias-T 同轴馈电 13.8V DC |
| 防护 | IP66 铝壳 + 2.2MΩ 静电泄放 + 预留HV火花隙/DNP |
| PCB | 140×50mm 低压控制+电源板, RF高压谐振区板外硬线 |
| 成本 | ~¥430/套 |
| 固件 | ESP-IDF v5.x C, 12 源文件, ~2800 行 |

## 目录结构

```
auto-efhw-tuner/
├── README.md                       ← 本文件
├── CHANGELOG.md                    ← 版本历史 (V1.0→V2.0→V3.0)
├── firmware-esp32/                 ← V3.0 ESP32-S3 固件
│   ├── CMakeLists.txt              ← ESP-IDF 项目构建
│   ├── sdkconfig.defaults          ← SDK 配置 (WiFi/NVS/分区/WDT)
│   ├── partitions.csv              ← Flash 分区表 (含 nvs_tune)
│   └── main/
│       ├── atu_main.c              ← app_main() → 3 FreeRTOS 任务 + LED heartbeat
│       ├── atu_config.h            ← 编译时常量 + 引脚映射 + 类型定义
│       ├── protocol.h/c            ← JSON 协议 (cJSON) — 6 种消息类型
│       ├── ws_client.h/c           ← WebSocket 长连 + JSON 命令分派 (350行)
│       ├── tune_engine.h/c         ← 调谐状态机: 缓存查→粗扫→细扫→锁定 (250行)
│       ├── servo_ctrl.h/c          ← LEDC PWM 50Hz + MOSFET 断电 (100行)
│       ├── nvs_cache.h/c           ← 频率→位置 ±50kHz 模糊查找 (120行)
│       ├── health_mon.h/c          ← Bias-V ADC + 核心温度 + 健康FSM (100行)
│       └── CMakeLists.txt          ← 组件构建
├── firmware-legacy/                ← V1.0 PIC + V2.0 STM32 固件 (历史归档)
│   └── README.md
├── hardware/                       ← 硬件设计文件
│   ├── SCH_Description.md          ← V3.0 原理图 (4 Sheet: Power/MCU/HV_Tank/Protection)
│   ├── PCB_Description.md          ← V3.0 PCB/物理布局 (低压PCB + 板外RF/HV区)
│   ├── EFHW_TUNER_BOM_FUCHS.csv    ← V3.0 BOM (ESP32-S3 + T200-6 + 发射机级电容)
│   └── simulation/                 ← SPICE + 解析仿真
│       ├── README.md               ← 仿真索引 (LC/热/Bias-T/PCB)
│       ├── lc_resonant_tank_analysis.md  ← T200-6 LC 解析分析
│       ├── lc_resonant_tank_analysis.py  ← Python 谐振计算脚本
│       ├── thermal_analysis.md     ← 热分析 (T200-6/MOSFET/DC-DC/伺服)
│       ├── bias_tee_spice.cir      ← Bias-T 同轴馈电 (RF+DC)
│       └── pcb_transmission_lines.md ← PCB 传输线参数
├── docs/                           ← 工程文档
│   ├── SDD.md                      ← 软件设计文档 (14章, IBM TeamSD v2.3.2)
│   ├── FDE.md                      ← 当前可检测故障边界 + 工程风险控制
│   ├── V3_MIGRATION_CHECKLIST.md   ← V3.0 验证清单 (11大类)
│   ├── assembly_test_manual.md     ← V3.0 装配、测试、故障排查手册
│   └── tune_sequence.png           ← 端到端调谐时序图
└── bias-tee/                       ← 室内 Bias-T 注入盒
    └── bias_tee_design.md          ← 独立子设计 (原理图+BOM+测试)
```

## 快速开始

### 如果你是...

**固件开发者**：
1. 阅读 [`docs/SDD.md`](docs/SDD.md) 了解架构和接口，或直接看在线版 [ybr387rz.mule.page](https://ybr387rz.mule.page/)
2. 阅读 [`docs/FDE.md`](docs/FDE.md) 了解故障检测策略
3. 安装 ESP-IDF v5.x: `brew install esp-idf` (macOS) 或参考 [ESP-IDF 文档](https://docs.espressif.com/projects/esp-idf/en/stable/)
4. `cd firmware-esp32 && idf.py set-target esp32s3 && idf.py build`
5. USB-C 连接 ESP32-S3 → `idf.py flash && idf.py monitor`

**硬件制作者**：
1. 阅读 [`hardware/SCH_Description.md`](hardware/SCH_Description.md) (原理图)
2. 阅读 [`hardware/PCB_Description.md`](hardware/PCB_Description.md) (PCB 布局)
3. 从 [`hardware/EFHW_TUNER_BOM_FUCHS.csv`](hardware/EFHW_TUNER_BOM_FUCHS.csv) 采购物料
4. KiCad 中按 PCB_Description 坐标级规格绘制 → DRC → Gerber

**DIY 爱好者**：
1. 按 [`docs/assembly_test_manual.md`](docs/assembly_test_manual.md) 逐步焊接装配
2. 按 [`docs/V3_MIGRATION_CHECKLIST.md`](docs/V3_MIGRATION_CHECKLIST.md) 逐项验证
3. 烧录固件 → WiFi 配置 → MRRC 联调 → 全频段扫描

## 文档体系

| 文档 | 内容 | 位置 |
|------|------|------|
| **在线 SDD** | 14章完整软件设计规格书 (暗色主题, 侧栏导航, 架构图全渲染) | [ybr387rz.mule.page](https://ybr387rz.mule.page/) |
| SDD (源码) | 14章 IBM TeamSD: 架构/接口/状态机/时序/部署 | [`docs/SDD.md`](docs/SDD.md) |
| FDE | 当前固件可检测项、不可检测风险、台架验证矩阵 | [`docs/FDE.md`](docs/FDE.md) |
| 验证清单 | 11大类固件/硬件/MRRC联调/现场验证 | [`docs/V3_MIGRATION_CHECKLIST.md`](docs/V3_MIGRATION_CHECKLIST.md) |
| 装配手册 | 工具清单 → 焊接 → 磁环绕制 → 伺服安装 → 测试 | [`docs/assembly_test_manual.md`](docs/assembly_test_manual.md) |
| 原理图 | 4 Sheet: Power/MCU/HV_Tank/Protection (Netlist 级) | [`hardware/SCH_Description.md`](hardware/SCH_Description.md) |
| PCB 布局 | 140×50mm低压板 + 壳体内RF/HV物理布局 + DRC 规则 | [`hardware/PCB_Description.md`](hardware/PCB_Description.md) |
| BOM | 完整物料清单 | [`hardware/EFHW_TUNER_BOM_FUCHS.csv`](hardware/EFHW_TUNER_BOM_FUCHS.csv) |
| 仿真 | LC 谐振/热分析/Bias-T/PCB 传输线 | [`hardware/simulation/`](hardware/simulation/) |
| Bias-T 设计 | 室内注入盒独立子设计 | [`bias-tee/bias_tee_design.md`](bias-tee/bias_tee_design.md) |
| 版本历史 | V1.0 PIC → V2.0 STM32 → V3.0 Fuchs | [`CHANGELOG.md`](CHANGELOG.md) |
| 历史固件 | V1.0 PIC + V2.0 STM32 源码归档 | [`firmware-legacy/`](firmware-legacy/) |

## 关联项目文件

- `../README.md` — EFHW 综合知识库 (EFHW 原理, 磁芯选型, V3.0 Fuchs ATU 总览)
- `../references/aa5tb_efha_analysis.md` — AA5TB 原始理论深度解析
- `../atu_fuchs_handler.py` — MRRC 侧 Fuchs ATU WebSocket handler

## 社区与贡献

本项目是 BG1SB EFHW 知识库的工程落地子项目。欢迎：
- 提交 Issue 报告 Bug/改进建议
- 分享你的建造经验/调试图
- 贡献不同磁芯/频段的扩展设计

---

> 🏗️ 状态: 固件完成 (12源文件, ~2800行C) | PCB 待打样 | 台架测试待进行
> 📅 最后更新: 2026-06-09

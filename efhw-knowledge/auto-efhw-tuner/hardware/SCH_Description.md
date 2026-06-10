# EFHW Fuchs ATU V3.0 — 原理图描述文档 (Schematic Description)

> **Document ID**: SCH-EFHW-FUCHS-V3.0
> **MCU**: ESP32-S3-WROOM-1 (Xtensa LX7 双核 240MHz)
> **PCB**: EFHW-FUCHS-PCB-V3.0 (140×50mm, 2-layer FR4)
> **Design Tool**: KiCad V7+
> **Status**: Design Complete

---

## 1. 原理图层次结构

```
Root Sheet: EFHW_Fuchs_ATU_V3

├── Sheet 1/4: POWER (电源管理)
│   Bias-T DC提取 → 1N4007防反 → LM2940CT-12(12V) → 屏蔽型DC-DC(6V) → AMS1117-3.3(3.3V)
│
├── Sheet 2/4: MCU (ESP32-S3 控制)
│   ESP32-S3-WROOM-1 + USB Serial/JTAG + Bias-V ADC + 伺服接口 + 指示
│
├── Sheet 3/4: HV_TANK (高压谐振回路)
│   T200-6 单磁芯 2:14 耦合器 + 发射机级空气可变电容 10-500pF (伺服驱动)
│
└── Sheet 4/4: PROTECTION (保护电路)
    2.2MΩ 静电泄放 + 预留HV火花隙/DNP + 天线/地网端子
```
---

## 2. Sheet 1/4: POWER — 电源管理

### 2.1 电路描述

同轴电缆芯线同时承载 RF 和 13.8V DC。L_bias 扼流圈分离 DC，经 1N4007 防反接后送入 LM2940CT-12 稳压到 12V。12V 轨输入屏蔽型 DC-DC 模块降压为 6V 供伺服电机。AMS1117-3.3 LDO 将 12V 降压为 3.3V 供 ESP32-S3。

**V3.0 新增**: LM2596 12V→6V DC-DC (伺服供电，最大 3A 堵转电流)。

### 2.2 完整 Netlist

| Net | 连接点 | 类型 | 预期电压 | 预期电流 |
|-----|--------|------|---------|---------|
| `COAX_CENTER` | J1(SO-239芯线) → C_block(热端) → L_bias(热端) | RF+DC叠加 | 0-100V RF + 13.8V DC | ≤2A RF + 0.3A DC |
| `RF_50OHM_IN` | C_block(冷端) → T200-6初级(热端) | 纯RF (隔直后) | 0-100V RF | ≤2A RF |
| `DC_RAW` | L_bias(冷端) → D1(阳极) | 脉动DC | 13.8V (±2V) | ≤350mA |
| `DC_12V_PRE` | D1(阴极) → U2(LM2940, IN) | 防反后DC | 13.3V | ≤350mA |
| **`VCC_12V`** | U2(OUT) → U4(LM2596, IN) → U3(AMS1117, IN) | 稳压12V | 12.0V ±0.5V | ≤300mA |
| **`VCC_6V`** | U4(OUT) → Q1(IRF9540, Source) | 伺服供电 | 6.0V | ≤3A (堵转) |
| **`VCC_SERVO`** | Q1(Drain) → HDR_SERVO Pin2 | 伺服VCC (可切断) | 6.0V (调谐时)/0V (空闲) | ≤3A |
| **`VCC_3V3`** | U3(OUT) → ESP32-S3 VDD | 稳压3.3V | 3.30V ±0.1V | ≤100mA |
| `GND` | 全板统一地平面 | 0V | — |

### 2.3 元件清单

| 位号 | 元件 | 值 | 封装 | 功能 |
|------|------|-----|------|------|
| J1 | SO-239 M座 | 法兰安装 | Panel | RF+DC 输入 |
| C_block1,2 | 隔直电容 | 10nF/2KV/C0G-NP0或银云母 ×2 | 1206/径向 | 隔DC通RF |
| L_bias | RF扼流圈 | FT37-43 绕15匝 (~95µH) | 磁环 TH | 隔RF通DC |
| D1 | 防反二极管 | 1N4007 | DO-41 | 防反接 |
| U2 | 12V 稳压器 | LM2940CT-12 (LDO, 压差0.5V) | TO-220 | 13.8V→12V |
| U4 | DC-DC降压 | 屏蔽型 LM2596/MP1584 模块 | 模块 | 12V→6V 伺服供电, 低EMI |
| U3 | 3.3V 稳压器 | AMS1117-3.3 (LDO) | SOT-223 | 12V→3.3V |
| C_in_12V, C_out_12V | 电解 | 47µF/25V ×2 | D6.3mm | 12V 滤波 |
| C_in_3V3, C_out_3V3 | 钽/陶瓷 | 10µF/16V + 100nF | 0805 | 3.3V 滤波 |
| C_in_6V, C_out_6V | 电解+陶瓷 | 100µF/16V + 100nF | D8mm+0805 | 6V 滤波 |
| C_SERVO_BULK | 钽/固态电解 | 100µF/10V 低ESR | 伺服排针旁 | 伺服启动/堵转瞬态储能 |

---

## 3. Sheet 2/4: MCU — ESP32-S3 控制

### 3.1 电路描述

ESP32-S3-WROOM-1 作为唯一 MCU。双核 240MHz Xtensa LX7, 512KB SRAM, 16MB Flash。内置 WiFi 2.4GHz + USB Serial/JTAG。ADC1 监测 Bias-T 电压。LEDC 外设输出伺服 PWM。GPIO 控制伺服供电 MOSFET。

### 3.2 引脚分配

| GPIO | 功能 | 方向 | 连接 | 备注 |
|------|------|:----:|------|------|
| GPIO0 | BOOT | IN | 10kΩ 上拉 + 按钮对地 | 按住=下载模式 |
| GPIO1 | SERVO_PWM | OUT | HDR_SERVO Pin3 → MG996R Signal | LEDC_CH0, 50Hz |
| GPIO2 | SERVO_PWR_EN | OUT | 2N2222A Base (经1kΩ) → Q1 Gate下拉 | HIGH=伺服上电, LOW=伺服断电 |
| GPIO3 | UART0 TX | OUT | 调试串口 (可选) | 115200bps |
| GPIO4 | UART0 RX | IN | 调试串口 (可选) | |
| GPIO5 | ADC_BIAS_V | IN | R_bias_div1+R_bias_div2 分压点 (5.7:1) | ADC1_CH4, 12-bit |
| GPIO6 | STATUS_LED | OUT | LED (经1kΩ限流) | 常亮=连接, 闪烁=断开 |
| GPIO7 | BUZZER | OUT | 有源蜂鸣器 (经 NPN 2N2222A) | |
| GPIO18 | USB D- | I/O | USB Serial/JTAG | 烧录+调试 |
| GPIO19 | USB D+ | I/O | USB Serial/JTAG | 烧录+调试 |

### 3.3 Bias-T 电压监测

```
VCC_12V ──── R_bias_div1(47kΩ) ──┬── GPIO5 (ADC1_CH4)
                                  │
                            R_bias_div2(10kΩ)
                                  │
                                 GND

分压比: 10kΩ / (47kΩ+10kΩ) = 0.175
12V × 0.175 = 2.1V → 安全在 3.3V ADC 范围内
```

### 3.4 元件清单

| 位号 | 元件 | 值 | 封装 | 功能 |
|------|------|-----|------|------|
| U1 | MCU 模块 | ESP32-S3-WROOM-1 (16MB) | SMD 模组 | 主控 |
| R_bias_div1, R_bias_div2 | 分压电阻 | 47kΩ + 10kΩ 1% | 0805 | Bias-V 5.7:1 |
| C_bias_div | 滤波电容 | 100nF NPO | 0805 | 分压点滤波 |
| R_led | LED限流 | 1kΩ | 0805 | |
| Q_buzzer | NPN | 2N2222A | TO-92 | 蜂鸣器驱动 |
| R_buzzer_base | 基极电阻 | 1kΩ | 0805 | |
| HDR_SERVO | 排针 | 1×3 Pin 2.54mm 弯脚 | TH | GND/VCC/Signal |
| C_byp_mcu | 去耦 | 100nF ×2 | 0805 | VDD 去耦 |

---

## 4. Sheet 3/4: HV_TANK — 高压谐振回路

### 4.1 磁芯: T200-6 单只

| 参数 | 值 |
|------|-----|
| 型号 | T200-6 (Amidon/Micrometals Type 6, 羰基铁粉) |
| 材质 | Carbonyl Iron Powder, μ=8 |
| 尺寸 | OD=50.8mm, ID=31.8mm, HT=14.0mm |
| AL | ~10.5 nH/N² |
| 匝数比 | **2T 初级 : 14T 次级** |
| 阻抗比 | (14/2)² = **49:1** |
| 输入 | 50Ω |
| 输出匹配 | 50 × 49 ≈ **2,450Ω** |
| 次级电感 | 14² × 10.5 ≈ **2.06μH** |
| B_peak @100W/7.1MHz | **12.7 mT** (vs B_sat 600 mT → 47× 裕度) |
| 线径 初级 | 0.8mm 聚氨酯漆包线 |
| 线径 次级 | 0.5mm 聚氨酯漆包线 |

### 4.2 可变电容 + 伺服

| 参数 | 值 |
|------|-----|
| 类型 | 发射机级空气介质可变电容 |
| 范围 | 10–500 pF |
| 耐压 | 工作耐压≥5kV 或片距≥1.5mm; 普通收音机电容不得用于100W最终版 |
| 伺服 | MG996R (6V, 金属齿轮, 10kg·cm, 0.17s/60°) |
| 减速 | 齿轮组 3:1~6:1 (伺服 0-180° → 电容轴 0-180°) |
| 断电 | IRF9540 P-MOSFET + NPN栅极下拉: GPIO2 HIGH=供电, LOW=切断; 上电默认断电 |
| 控制 | LEDC_CH0 (GPIO1), 50Hz, 16-bit |

**调谐范围验证** (L=2.06μH, C=10-500pF):
- f_max = 1/(2π√(2.06×10⁻⁶ × 10×10⁻¹²)) = 35.1 MHz ✓
- f_min = 1/(2π√(2.06×10⁻⁶ × 500×10⁻¹²)) = 4.96 MHz ✓
- 覆盖 40m (7.0 MHz) 至 10m (29.7 MHz)

### 4.3 RF 接线 (点对点，不在 PCB 上)

```
SO-239 芯线 → 10nF×2 2kV C0G/NP0或银云母隔直 → T200-6 初级2匝热端
T200-6 初级2匝冷端 → SO-239 外壳 (GND)
T200-6 次级14匝热端 → 可变电容定片 + ANT 端子
T200-6 次级14匝冷端 → GND + 可变电容动片
可变电容动片 → GND
```

**关键**: RF二次侧高压路径采用 1.5mm² 以上硬铜线或PTFE高压线直接连接，不经过控制PCB走线。T200-6 磁环用尼龙扎带/绝缘支架固定在底板上。可变电容和伺服电机安装在铝壳底板上，通过齿轮组耦合。所有RF热端端点打磨圆滑, 与PCB和低压线束保持≥15mm空气距离。

---

## 5. Sheet 4/4: PROTECTION — 保护电路

- **HV_GAP**: 预留可调空气火花隙或3-5kV低电容GDT, 默认DNP, 台架确认不误触发后再装
- **R_bleed**: 2.2MΩ 2W 3KV 金属釉膜无感电阻，天线端对地 (静电泄放)
- **隔直**: C_block1/2 (10nF 2KV C0G/NP0或银云母 ×2)，TRX 端

低压90V/200V GDT不得默认并接在RF热端到地, 否则可能在正常调谐RF电压下放电并破坏匹配。高压保护以足够耐压的发射机级可变电容、圆滑短硬线、足够空气间距和静电泄放为主。

---

## 6. 全局互联

### 星形接地

```
          GND_CHASSIS (J1 外壳 / 铝壳)
               │
    ┌──────────┼──────────┐
    │          │          │
GND_PCB      GND_ANT    GND_VAR_CAP
(PCB地平面)  (天线GND)   (可变电容动片)
    │
    └── 单点接机箱地在 SO-239 安装点
```

---

> **关联文档**: [`PCB_Description.md`](PCB_Description.md) · [`EFHW_TUNER_BOM_FUCHS.csv`](EFHW_TUNER_BOM_FUCHS.csv)

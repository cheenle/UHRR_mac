# EFHW Fuchs ATU V3.0 — Software Design Description (SDD)

> **Document ID**: SDD-EFHW-FUCHS-V3.0
> **Version**: V3.0
> **Date**: 2026-06-09
> **Status**: Released
> **Online**: https://ybr387rz.mule.page/
> **Methodology**: IBM Team Solution Design (TeamSD) v2.3.2
> **MCU**: ESP32-S3-WROOM-1 (Xtensa LX7 双核 240MHz, 16MB Flash)
> **Framework**: ESP-IDF v5.x (Native C, FreeRTOS)
> **License**: GPL-3.0 (Firmware) / CERN-OHL-S 2.0 (Hardware)

---

## Document Index

| # | Chapter | Key Content |
|---|---------|-------------|
| 1 | Executive Summary | Fuchs ATU V3.0 概览、性能指标、架构分层 |
| 2 | Business Direction | 目标用户、痛点与解决方案 |
| 3 | Project Definition | 属性、范围、里程碑 |
| 4 | System Context | 新上下文图: ATR1000→MRRC→WiFi→ATU |
| 5 | Non-Functional Requirements | 性能/可靠性/WiFi/安全 |
| 6 | Use Case Model | UC-001 ~ UC-005 |
| 7 | Subject Area Model | 实体、状态机(Fuchs状态+调谐阶段) |
| 8 | Architecture Decisions | AD-001 ~ AD-006 |
| 9 | Architecture Overview | 4 FreeRTOS 任务 + 事件驱动模型 |
| 10 | Service Model | 5模块接口契约 |
| 11 | Component Model | 组件清单+端到端调谐序列 |
| 12 | Operational Model | 部署拓扑 (室外IP66)、OTA双槽 |
| 13 | Feasibility Assessment | Flash/RAM预算、风险 |
| 14 | Version History | 文档修订记录 |

---

# 1. Executive Summary

## 1.1 Project Overview

**EFHW Fuchs ATU V3.0** 是一台室外架设、Bias-T 同轴馈电、WiFi 远程自动调谐的末端馈电半波天线适配器。基于 F5NPV Fuchs 并联 LC 耦合器理论，以 ESP32-S3 驱动伺服电机控制空气可变电容连续调谐。SWR 感知完全委托给 MRRC 侧的 ATR1000，ATU 是纯执行机构。


## 1.2 Key Performance Metrics

| Metric | Target |
|--------|--------|
| 调谐时间 | < 10s (36步粗扫 + 30步细扫, 每步80ms) |
| 调谐缓存召回 | < 1s (NVS命中直接定位) |
| 电容分辨率 | 连续 (伺服 0.5° 精度 → ~1.4pF @ 500pF/180°) |
| MCU 算力 | 240 MHz 双核 Xtensa LX7 |
| Flash 用量 | 16MB total → ~1.2MB 固件 |
| RAM 用量 | 512KB SRAM → ~80KB |
| 调谐缓存 | 16KB NVS 分区 → ~2000 条目 → 40m-10m 每 50kHz |
| WiFi | 2.4GHz 802.11 b/g/n, WebSocket 长连接 |
| 成本 | ~¥430/套 (含发射机级高压电容) |

## 1.3 Architecture Layers

```
┌──────────────────────────────────────────────────┐
│  Application: atu_main.c                          │
│  app_main() → 3 FreeRTOS tasks → LED heartbeat    │
├──────────────────────────────────────────────────┤
│  Service: ws_client · tune_engine · health_mon    │
│  (WebSocket长连/MRRC协议) (缓查→粗扫→细扫)       │
├──────────────────────────────────────────────────┤
│  Domain: servo_ctrl · nvs_cache · protocol        │
│  (LEDC PWM/MOSFET断电) (NVS ±50kHz查) (cJSON)     │
├──────────────────────────────────────────────────┤
│  HAL: ESP-IDF (GPIO·ADC·LEDC·WiFi·NVS·WDT)       │
└──────────────────────────────────────────────────┘
```

---

# 2. Business Direction

## 2.1 Target Users & Pain Points

| Persona | Pain Point | V3.0 Solution |
|---------|-----------|---------------|
| FT8 多频段跳频者 | 换频需重新匹配 | 缓存命中 <1s 定位 |
| DX/Contest 爱好者 | 追求极致 TX 效率 | 连续调谐实现 SWR<1.1:1 |
| 远程/无人站点 | 走到室外/爬到阁楼手动调 | WiFi远程完全免接触 |
| 便携/野外操作者 | 设备越简单越好 | 无SWR桥/无继电器 (最少故障点) |

## 2.2 Key Differentiators

- **伺服连续调谐** (180°×0.5°精度) — 无档位跳变, 锁定后断电消抖
- **远程 SWR 感知** — ATR1000 via MRRC, ATU 无板载 SWR 桥
- **WiFi 无线控制** — WebSocket 长连接, 完全免接触
- **ESP32-S3 单芯片** — 240MHz 双核, 固件全部 ESP-IDF 原生 C
- **最少故障点** — 1 伺服 + 1 MOSFET (无继电器/无 SWR 桥)
- **工程裕度优先** — 成本提高到约¥430/套, 换取高压电容和低EMI电源裕度

---

# 3. Project Definition

| Attribute | Value |
|-----------|-------|
| Project Name | EFHW Fuchs ATU V3.0 |
| Project Type | Embedded firmware + analog RF hardware |
| MCU | ESP32-S3-WROOM-1 (16MB Flash) |
| Framework | ESP-IDF v5.x (Native C, FreeRTOS) |
| Core | T200-6 ×1 (Carbonyl Iron Type 6, μ=8) |
| Frequency | 40m–10m (7.0–29.7 MHz, WARC全覆盖) |
| Power | 100W PEP (SSB/CW) |
| License | GPL-3.0 (Firmware) / CERN-OHL-S 2.0 (Hardware) |

## Milestones

| M# | Date | Deliverable |
|----|------|-------------|
| M1 | 2026-06-08 | 设计规格 + 实施计划 |
| M2 | 2026-06-08 | ESP32-S3 固件 v1.0 (12源文件, ~2800行C) |
| M3 | TBD | PCB 打样 + 台架测试 |
| M4 | TBD | 现场 7×24h FT8 验证 |

---

# 4. System Context

## 4.1 System Diagram

```
[Radio 100W]──coax──[Bias-T: C+choke+13.8V]──coax(20m)──┐
                                                          │
┌─────────────────────────────────────────────────────────┼────┐
│  EFHW Fuchs ATU (IP66 AL Enclosure 160×110×70mm)       │    │
│                                                         │    │
│  ┌────────────────┐  ┌────────────┐  ┌──────────────┐  │    │
│  │ Bias-T Extract │  │ ESP32-S3   │  │ Fuchs LC     │  │    │
│  │ L_bias FT37-43 │  │ WiFi STA   │  │ Coupler      │──┼────┤→ Ant ~20m
│  │ LM2940→DC-DC   │  │ WebSocket  │  │ T200-6 2:14T │  │    │
│  │ →AMS1117       │  │ LEDC PWM   │  │ Air Var Cap  │  │    │
│  └────────────────┘  │ ADC Bias-V │  │ 10-500pF     │  │    │
│                      │ GPIO Ctrl  │  │ MG996R Servo │  │    │
│                      └──────┬─────┘  └──────────────┘  │    │
│                             │ WiFi                      │    │
│  Protection: 2.2MΩ bleeder + HV spark-gap footprint   │    │
└─────────────────────────────┼───────────────────────────┘    │
                              │                                │
                    ┌─────────┴─────────┐                      │
                    │  Home WiFi Router │                      │
                    └─────────┬─────────┘                      │
                              │                                │
                    ┌─────────┴─────────┐                      │
                    │   MRRC Server      │                     │
                    │   ATR1000 → SWR    │                     │
                    │   WebUI ATU Panel  │                     │
                    └────────────────────┘                     │
```

## 4.2 External Interfaces

| Interface | Physical | Signal/Protocol |
|-----------|----------|-----------------|
| RF IN | SO-239 M座 | 50Ω, 1.8-30MHz, ≤100W + 13.8V DC |
| Antenna OUT | M5 304SS bolt + PTFE | ~2,450Ω, RF热端按≥5kV物理间距设计 |
| WiFi | ESP32-S3 PCB天线 | 2.4GHz 802.11 b/g/n, WPA2 |
| WebSocket | TCP/ws over WiFi | JSON 协议 (见 protocol.h) |
| USB | ESP32-S3 USB Serial/JTAG | 烧录 + 调试, 115200bps |

## 4.3 Data Flow

| Flow | Path |
|------|------|
| SWR采样 | **不在ATU上。** ATR1000 → MRRC → WebSocket → ESP32-S3 |
| 调谐命令 | Browser → MRRC → WebSocket → ESP32-S3 → 伺服PWM |
| 电容控制 | ESP32-S3 LEDC_CH0 (GPIO1) → MG996R → 齿轮 → 可变电容 |
| Bias-V 监测 | VCC_12V → 47k+10k分压 → GPIO5 ADC1_CH4 (12-bit) |
| 事件上报 | ESP32-S3 → WebSocket → MRRC → Browser UI |
| 固件更新 | MRRC → WiFi → ESP32-S3 OTA (双槽) |

---

# 5. Non-Functional Requirements

## 5.1 Performance

| ID | Requirement | Target | Implementation |
|----|------------|--------|----------------|
| P01 | 全扫描调谐 | < 10s | 37个粗扫采样点(0-180°@5°)+30步细扫 × 80ms/步 + SWR往返 ~100ms |
| P02 | 缓存命中调谐 | < 1s | NVS查→直接定位伺服 |
| P03 | 伺服定位精度 | ±0.5° | 16-bit PWM, 180°满量程 |
| P04 | WiFi重连 | < 10s | 自动重连, 间隔 3s |
| P05 | WebSocket心跳 | 30s | Ping/Pong 保持长连接 |

## 5.2 Reliability & Safety

| ID | Requirement | Implementation |
|----|------------|----------------|
| R01 | 禁止大功率调谐 | fwd_pwr > 15W → 中止+伺服归零 (由MRRC检测) |
| R02 | RF丢失保护 | fwd_pwr < 0.5W → 中止 (由MRRC检测) |
| R03 | 伺服堵转风险 | 当前硬件无真实位置/电流反馈; 通过调谐超时、SWR不收敛和人工巡检发现 |
| R04 | 看门狗 | ESP32-S3 Task WDT 5s + RTC WDT |
| R05 | 调谐后伺服断电 | MOSFET切断6V供电; NPN下拉方案为 GPIO2 LOW=断电, HIGH=供电 |
| R06 | NVS 写失败 | 日志记录, RAM缓存继续工作 |

## 5.3 Environmental

| ID | Requirement | Target |
|----|------------|--------|
| E01 | 工作温度 | -20°C ~ +60°C |
| E02 | 防护 | IP66 |
| E03 | WiFi 距离 | 距路由器 30m 内稳定 (2.4GHz穿墙能力) |

---

# 6. Use Case Model

### UC-001: Auto-Tune via MRRC (主用例)

```
Actor: HAM Operator (点击Web UI "Auto Tune" 按钮, 发射5W CW)
Precondition: ATU WiFi已连接, MRRC在线, fwd_pwr ∈ [0.5W, 15W]
Postcondition: 伺服锁定最优位置, SWR < 1.2:1

Basic Flow:
1. 用户点击 "Auto Tune" → MRRC读ATR1000 SWR
2. MRRC发送 tune_start {freq_hz, swr, fwd_pwr_w} → ESP32-S3
3. ESP32-S3查NVS缓存:
   - 命中 → 伺服直接定位, 上报 tune_done (< 1s)
   - 未命中 → 启动粗扫
4. 粗扫: 伺服 0°→180° @ 5°/步, 共37个采样点
   每步: 伺服移动 → 等待SWR (MRRC→ATR1000→回传, ~100ms)
   记录 min_SWR 位置
   SWR < 1.05 → 提前退出
5. 如果 min_SWR > 1.5: 细扫 ±15° @ 1°/步
6. 锁定最优位置 → 写入NVS → 伺服断电 → 上报 tune_done
```

### UC-002: Cache Hit Quick Re-Tune

```
Actor: HAM Operator (回到之前调谐过的频段)
Flow:
1. NVS查找 ±50kHz → 命中
2. 伺服直接定位到缓存位置
3. 上报 tune_done (< 1s)
4. 如果用户发现 SWR > 2.0 → 手动再次触发全扫描
```

### UC-003: WiFi Lost Graceful

```
Actor: Network (WiFi 断开)
Flow:
1. WiFi事件 DISCONNECTED → connected = false
2. LED 快闪 (200ms周期) 指示断连
3. 每10秒自动重试连接
4. 重连成功后自动恢复 WebSocket
5. 断连期间调谐命令无法执行 → MRRC提示 "ATU offline"
6. NVS缓存本地保留 (不受网络影响)
```

### UC-004: OTA Firmware Update

```
Actor: HAM Operator (通过MRRC推送固件)
Flow:
1. MRRC通知ESP32-S3 "有新固件"
2. ESP32-S3通过HTTPS从MRRC下载新固件到 ota_1 分区
3. 校验OK → 设置启动分区 → 重启
4. 启动失败 → 自动回滚到 ota_0
```

### UC-005: Health Monitor Runtime

```
Actor: System (每10秒自动)
Flow:
1. 读 Bias-T 电压 (<10V 或 >15V → DEGRADED)
2. 读核心温度 (>80°C → DEGRADED)
3. Bias-T异常会上报 health_alert 到 MRRC; 温度异常当前仅更新本地健康状态
4. 当前实现仅在 HEALTHY/DEGRADED 间切换, 尚未强制禁止调谐
```

---

# 7. Subject Area Model

## 7.1 Domain Entities

| Entity | Attributes | Persistence |
|--------|-----------|-------------|
| **ServoState** | current_angle(0-180, commanded only) | RAM |
| **TuneCache** | 2000+ entries{freq_khz→servo_pos} | NVS Flash (nvs_tune分区 24KB) |
| **WSConnection** | connected(bool), ws_handle | RAM |
| **HealthState** | HEALTHY/DEGRADED/SAFE, bias_voltage, core_temp | RAM |
| **TuneSession** | freq_hz, phase, best_pos, best_swr, coarse_step, fine_step | RAM (transient) |

## 7.2 ATU State Machine

```
         POWER-ON ──WiFi连──▶ ATU_IDLE
                                   │
                      tune_start   │  bypass / abort
                                   ▼
                              ATU_SWEEPING (粗扫)
                                   │
                    cache hit /    │  coarse done
                    SWR < 1.05     │
                         │         │
                         │    ┌────┴────┐
                         │    │ SWR>1.5 │ SWR≤1.5
                         │    ▼         │
                         │ ATU_FINE_TUNING
                         │    │         │
                         │    └────┬────┘
                         ▼         ▼
                       ATU_LOCKED (调谐完成, 伺服断电)
                                   │
                          freq change / manual re-tune
                                   │
                                   ▼
                              ATU_IDLE
```

## 7.3 Health FSM

Current firmware implements `SYS_HEALTHY` and `SYS_DEGRADED` transitions for Bias-V/temp checks. `SYS_SAFE` exists in the enum but is not yet latched or enforced.

```
  POST ──▶ SYS_HEALTHY
               │
  voltage fault/temp fault
               ▼
          SYS_DEGRADED (仍可调谐, 仅告警)
               │
  planned: critical (连续3次调谐失败 / WDT触发)
               ▼
           SYS_SAFE (planned: 伺服归零, 禁调谐)
               │
    ONLY exit: power cycle + 健康恢复
```

---

# 8. Architecture Decisions

### AD-001: ESP32-S3 单芯片架构

| Field | Value |
|-------|-------|
| **Decision** | **ESP32-S3-WROOM-1** 单芯片 (替代 F5NPV 的 ESP8266+Arduino Nano 双MCU) |
| **Rationale** | 双核240MHz, 512KB SRAM, WiFi/BLE, LEDC PWM (伺服), 12-bit ADC (Bias-V), USB/JTAG, 16MB Flash (OTA双槽+NVS缓存) |
| **Alternatives** | ESP8266 (老旧, 无LEDC), ESP32-C3 (单核, 无USB/JTAG) |
| **Impact** | 固件从Arduino框架迁移到ESP-IDF原生C; 全部功能单芯片实现 |

### AD-002: Fuchs 拓扑 (并联LC)

| Field | Value |
|-------|-------|
| **Decision** | **T200-6 单磁芯 2:14T + 发射机级空气可变电容 10-500pF** (F5NPV/M0UKD系) |
| **Rationale** | Type 6低μ(8)高频Q>150; 连续调谐实现SWR<1.1:1; 单电容覆盖40m-10m; RF电容峰值可能达到数kV, 必须使用发射机级电容 |
| **Impact** | T200-6 单磁芯方案; B_peak 校核通过 (12.7mT vs 600mT 饱和, 47× 裕度); 机械体积和成本由高压电容主导 |

### AD-003: 无板载SWR (远程ATR1000)

| Field | Value |
|-------|-------|
| **Decision** | **ATU不采样SWR**, 完全依赖MRRC侧的ATR1000通过WebSocket提供 |
| **Rationale** | 删掉Tandem Match桥(BAT41/FT37-43/校准电位器), 减少BOM和故障点; 调谐精度由ATR1000保证(优于自制SWR桥) |
| **Impact** | 调谐每步延迟取决于网络往返(~50-100ms); 断网时不可调谐(设计取舍: 室外IP66用WiFi) |

### AD-004: 伺服连续调谐

| Field | Value |
|-------|-------|
| **Decision** | **MG996R伺服驱动空气可变电容连续调谐** |
| **Rationale** | F5NPV验证过的方案; 连续可调; 调谐后断电消抖; 仅2个故障点(伺服+MOSFET) |
| **Impact** | 全扫描 ~8s; 需要齿轮减速匹配; 当前硬件无真实堵转反馈, 需靠调谐超时/SWR不收敛和人工巡检兜底 |

### AD-005: 固件框架 — ESP-IDF vs Arduino

| Field | Value |
|-------|-------|
| **Decision** | **ESP-IDF v5.x 原生C** (非Arduino) |
| **Rationale** | LEDC PWM / ADC oneshot / NVS分区 / OTA双槽 / Task WDT 用IDF API更可控; Arduino封装层增加开销 |
| **Impact** | 需要完整的ESP-IDF工具链; 所有代码为原生C实现 |

### AD-006: NVS调谐缓存

| Field | Value |
|-------|-------|
| **Decision** | **专用nvs_tune分区(24KB)** 存储频率→位置映射, ±50kHz匹配 |
| **Rationale** | 冷启动全扫描后, 同频段秒级切换; 2000条目覆盖40m-10m每50kHz; NVS掉电不丢失 |
| **Impact** | 占用一个Flash分区; 首次使用某频段需全扫(建立缓存) |

---

# 9. Architecture Overview

## 9.1 Module Decomposition

```
atu_main.c  ← 应用层 (app_main / FreeRTOS tasks / LED heartbeat)
    │
    ├── atu_config.h         ← 全部编译时常量+引脚映射+类型定义
    │
    ├── ws_client.h/c        ← WebSocket 通信层
    │   WiFi STA管理 · WS长连接 · JSON命令分派 · 发送队列
    │
    ├── tune_engine.h/c      ← 调谐算法域
    │   缓存查→粗扫(36步@5°)→细扫(30步@1°)→锁定
    │   功率安全检查 · 早期退出 · 结果上报
    │
    ├── servo_ctrl.h/c       ← 伺服驱动域
    │   LEDC PWM 50Hz 16bit · MG996R角度控制 · MOSFET断电
    │
    ├── nvs_cache.h/c        ← 持久化域
    │   频率→位置映射 · ±50kHz模糊查找 · NVS读写
    │
    ├── health_mon.h/c       ← 健康监控域
    │   Bias-V ADC · 核心温度 · 健康FSM
    │
    └── protocol.h/c         ← 协议域
        JSON parse (cJSON) · JSON build · 6种消息类型
```

## 9.2 FreeRTOS Tasks

| Task | Priority | Stack | Role |
|------|:--------:|:-----:|------|
| **ws_client_task** | 3 (高) | 8192 | WiFi连接+WebSocket收发+JSON命令分派+发送队列处理 |
| **tune_engine_task** | 2 | 4096 | 事件驱动: 接收SWR更新 → 步进伺服 → 上报进度 |
| **health_mon_task** | 1 (低) | 3072 | 每10s: Bias-V ADC + 核心温度 + 健康FSM |

Tasks间通信: `send_queue` (FreeRTOS Queue, ws_client→WS发送) + 直接函数调用 (ws_client→tune_engine via tune_engine_feed_swr)

## 9.3 Key Design Patterns

| Pattern | Implementation |
|---------|---------------|
| **Event-Driven Tuning** | SWR通过WebSocket异步到达 → tune_engine_feed_swr() 步进状态机 |
| **Callback** | tune_engine → ws_client_send() 上报进度/结果 |
| **Queue** | ws_client_send() 线程安全 (FreeRTOS Queue) |
| **Early Exit** | SWR < 1.05 提前结束粗扫 |
| **Power-Cut Idle** | 调谐完成/空闲: MOSFET切断伺服6V供电 |
| **Watchdog** | ESP Task WDT 5s + RTC WDT |
| **Dual-Slot OTA** | ota_0 / ota_1 交替升级, 失败自动回滚 |

---

# 10. Service Model

### 10.1 ws_client — WebSocket Client

| Operation | Signature | Pre-condition | Post-condition |
|-----------|-----------|--------------|----------------|
| task | `ws_client_task(void*)` | — | WiFi STA + WS forever loop |
| send | `bool ws_client_send(const char*)` | WiFi+WS connected | JSON入队+发送 |
| is_connected | `bool ws_client_is_connected(void)` | — | true/false |

**处理命令**: tune_start → tune_engine_start() · swr_update → tune_engine_feed_swr() · tune_abort → tune_engine_abort() · set_bypass → servo_set_angle(0) · get_status → proto_build_status_report()

### 10.2 tune_engine — Tuning Engine

| Operation | Returns | WCET |
|-----------|---------|------|
| `tune_engine_init()` | — | < 1ms |
| `tune_engine_start(freq, swr)` | — | NVS查+直接定位 < 5ms |
| `tune_engine_feed_swr(swr, pwr)` | — | 状态转移 < 5ms + 伺服移动80ms |
| `tune_engine_abort()` | — | < 80ms |

**状态转移**: 每次 feed_swr 调用推动状态机一步 (coarse_step++ 或 fine_step++), 然后设置 swr_pending=true 等待下一个SWR。

### 10.3 servo_ctrl — Servo Controller

| Operation | Pre-condition | Post-condition |
|-----------|--------------|----------------|
| `servo_init()` | — | LEDC+PWM+GPIO就绪, 伺服断电 |
| `servo_set_angle(deg)` | 伺服已供电 | 角度更新, delay 80ms |
| `servo_power_on()` | — | MOSFET导通, 伺服VCC=6V |
| `servo_power_off()` | — | MOSFET关断, 伺服VCC=0V |

### 10.4 nvs_cache — Tune Cache

| Operation | WCET |
|-----------|------|
| `nvs_cache_init()` | < 50ms |
| `nvs_cache_lookup(freq_hz, *pos)` | O(tolerance) ≈ 11次NVS读 |
| `nvs_cache_save(freq_hz, pos)` | < 50ms (含Flash写) |

### 10.5 health_mon — Health Monitor

| Check | Period | WCET |
|-------|--------|------|
| Bias-V ADC read + 校准 | 10s | < 1ms |
| Core temperature read | 10s | < 1ms |
| Health FSM update | 10s | < 1µs |

---

# 11. Component Model

## 11.1 Component Inventory

| Component | Source | Responsibility |
|-----------|--------|----------------|
| atu_main | BG1SB (C) | app_main, task creation, LED heartbeat |
| ws_client | BG1SB (C, 350行) | WiFi+WS管理, JSON分派 |
| tune_engine | BG1SB (C, 250行) | 调谐状态机 |
| servo_ctrl | BG1SB (C, 100行) | PWM+MOSFET |
| nvs_cache | BG1SB (C, 120行) | 频率缓存持久化 |
| health_mon | BG1SB (C, 100行) | 健康巡检 |
| protocol | BG1SB (C, 150行) | JSON序列化/反序列化 |
| cJSON | DaveGamble (C, 3100行) | JSON解析库 v1.7.18 |

## 11.2 End-to-End Auto-Tune Sequence

```
Browser        MRRC Server        ATR1000        ESP32-S3 ATU     Servo
  │                │                  │                │             │
  ├─"Tune"────────→│                  │                │             │
  │                ├─read SWR────────→│                │             │
  │                │←─SWR=2.8────────┤                │             │
  │                ├─tune_start WS───────────────────→│             │
  │                │  {freq,swr,pwr}                  │             │
  │                │                  │                ├─NVS查→miss  │
  │                │                  │                ├─power_on───→│
  │                │                  │                ├─set_angle(0)→│
  │                │←─tune_progress───────────────────┤             │
  │                │  {cap_pct,pos,state}            │             │
  │                ├─read SWR────────→│                │             │
  │                │←─SWR=2.4────────┤                │             │
  │                ├─swr_update WS───────────────────→│             │
  │                │                  │                ├─记录min     │
  │                │                  │                ├─step→+5°   →│
  │                │  ... (重复36步) ...              │             │
  │                │←─tune_progress───────────────────┤             │
  │                │                  │                │             │
  │                │  ... (如果SWR>1.5, 细扫30步) ... │             │
  │                │                  │                │             │
  │                │←─tune_done───────────────────────┤             │
  │                │  {cap_pct:67,swr:1.15,ms:3400}   │             │
  │                │                  │                ├─save NVS    │
  │                │                  │                ├─power_off──→│
  │←─UI update─────┤                  │                │             │
  │  SWR=1.15 ●    │                  │                │             │
```

---

# 12. Operational Model

## 12.1 Deployment Topology

```
INDOOR:  [Radio]──[Bias-T Box: C+choke+13.8V]──coax 20m──┐
                                                           │
OUTDOOR:                                                   │
  ┌─ IP66 AL Box 160×110×70mm ─────────────────────────────┤
  │                                                        │
  │  SO-239 → 10nF×2 → T200-6(2:14T) → Air Var Cap → ANT M5
  │                                         │               │
  │                                    MG996R Servo         │
  │                                         │               │
  │  ┌─ PCB 140×50mm 低压控制板 ──────────┐│               │
  │  │ ESP32-S3 + LM2940 + shielded DC-DC ││               │
  │  │ IRF9540 MOSFET (伺服VCC开关)        │               │
  │  │ RF高压二次侧不走PCB                 │               │
  │  └─────────────────────────────────────┘│               │
  │  1.5mm breather hole + desiccant       │               │
  └─────────────────────────────────────────┘               │
                      │                                      │
          Counterpoise 2m → free-hanging                     │
```

## 12.2 Runtime Loop

Each FreeRTOS task has its own loop:

```
ws_client_task:
  block on send_queue (100ms timeout)
  → dequeue → esp_websocket_client_send_text()
  → every 60s: send status_report

tune_engine_task:
  block on delay (100ms) — purely event-driven
  → all work happens in tune_engine_feed_swr() callback

health_mon_task:
  every 10s: health_mon_tick()
  → ADC read → temp read → FSM update → alert if degraded

app_main (main loop):
  every 5s: LED = ws_client_is_connected() ? ON : fast-blink
```

## 12.3 Failure Recovery

| Event | Recovery |
|-------|----------|
| WDT reset | Boot → POST → reconnect WiFi → reload NVS |
| Brown-out | BOR reset → same as WDT |
| WiFi disconnect | Auto-reconnect every 10s; LED fast blink |
| WebSocket disconnect | Auto-reconnect after 3s; send queue drains |
| Servo stall | 当前硬件无法直接检测; 调谐超时/SWR不收敛 → servo power off, 人工检查 |
| NVS corruption | Auto-erase partition + reinit |
| OTA failure | Bootloader auto-rollback to previous slot |

---

# 13. Feasibility Assessment

## 13.1 Technical Risks

| Risk | Mitigation |
|------|------------|
| WiFi 室外稳定性 | 2.4GHz PCB天线; 距路由器30m内; 自动重连 |
| 伺服齿轮卡死 | 当前无位置/电流反馈; 调谐超时/SWR不收敛告警, 下一版增加电流检测或位置反馈 |
| 可变电容打火 | 使用发射机级空气电容(≥5kV或片距≥1.5mm), RF热端板外硬线, ≥15mm低压隔离 |
| T200-6 饱和 | B_peak 12.7mT vs 600mT饱和 (47×裕度) |
| 空气可变电容货源 | 优先发射机/军机拆机件或定制件; 普通收音机电容仅限低功率实验 |

## 13.2 Resource Budget

| Resource | Budget | Used | Free |
|----------|:------:|:----:|:----:|
| Flash | 16MB | ~1.2MB (固件+OTA双槽) | 92% |
| SRAM | 512KB | ~80KB (3 task stacks + cJSON) | 84% |
| GPIO | 45 | ~8 | 37 |
| ADC channels | 20 | 1 | 19 |
| NVS tune cache | 24KB | ~16KB (2000条目 × 8B) | 33% |
| Cost | ¥500 | ~¥430 | 高压电容升级后仍可控 |

---

# 14. Version History

| Version | Date | Changes |
|---------|------|---------|
| **V3.0** | **2026-06-08** | **Fuchs ATU — ESP32-S3 + T200-6 + MG996R 伺服调谐** |
| | | MCU: ESP32-S3-WROOM-1 (240MHz 双核 Xtensa LX7) |
| | | Core: T200-6 ×1 (μ=8) + 发射机级空气可变电容 10-500pF |
| | | SWR: 远程 ATR1000 via MRRC (无板载SWR桥) |
| | | 通信: WiFi WebSocket → MRRC 深度集成 |
| | | 固件: ESP-IDF v5.x 原生 C, 3 FreeRTOS 任务 |
| | | PCB: 140×50mm 低压控制板; RF高压谐振区板外点对点硬线 |
| | | 成本: ~¥430/套 |

---

> **关联文档**: [`FDE.md`](FDE.md) · [`../hardware/SCH_Description.md`](../hardware/SCH_Description.md) · [`../hardware/PCB_Description.md`](../hardware/PCB_Description.md)
> **固件源码**: [`../firmware-esp32/`](../firmware-esp32/) · **版本历史**: [`../CHANGELOG.md`](../CHANGELOG.md)

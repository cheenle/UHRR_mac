# Changelog — EFHW Auto Tuner

All notable changes to the EFHW Auto Tuner project.

---

## [V3.0] — 2026-06-08 — Fuchs ATU (Current)

### Architecture
- **MCU**: ESP32-S3-WROOM-1 (240MHz dual-core Xtensa LX7, 16MB Flash)
- **Core**: T200-6 ×1 (Type 6 Carbonyl Iron, μ=8), 2:14 turns → 49:1
- **Capacitor**: Transmitter-grade air variable 10-500pF, MG996R servo continuous drive
- **SWR Sensing**: Remote ATR1000 via MRRC (no onboard SWR bridge)
- **Communication**: WiFi 2.4GHz WebSocket → MRRC integration
- **Framework**: ESP-IDF v5.x Native C, FreeRTOS (3 tasks)
- **PCB**: 140×50mm low-voltage control board, RF HV point-to-point chassis wiring

### Key Decisions
- AD-001: ESP32-S3 single-chip (replaces ESP8266+Arduino Nano dual MCU)
- AD-002: Fuchs topology — parallel LC with T200-6 single core
- AD-003: No onboard SWR — fully delegated to MRRC ATR1000
- AD-004: Servo continuous tuning (replaces 7-relay 128-step array)
- AD-005: ESP-IDF native C (replaces Arduino framework)
- AD-006: NVS tune cache — 2000+ entries, ±50kHz fuzzy lookup

### Specs
- Frequency: 40m–10m (7.0–29.7 MHz, WARC全覆盖)
- Power: 100W PEP SSB/CW
- Tune time: <10s full sweep / <1s cache hit
- Cost: ~¥430/unit (high-voltage capacitor and low-EMI power parts included)
- Firmware: 12 source files, ~2800 lines C
- Enclosure: IP66 AL 160×110×70mm

### Docs
- SDD: 14-chapter IBM TeamSD v2.3.2 → [ybr387rz.mule.page](https://ybr387rz.mule.page/)
- FDE: current detection boundary + bench verification matrix
- BOM: EFHW_TUNER_BOM_FUCHS.csv
- Simulation: LC resonant tank (Python analytical), thermal analysis, Bias-T SPICE

---

## [V2.0] — 2026-06-08 — STM32F103 + ModularTuner

### Architecture
- **MCU**: STM32F103C8T6 Bluepill (72MHz ARM Cortex-M3)
- **Core**: T200-2 ×2 stacked (Type 2 Carbonyl Iron, μ=10), 2:13 turns → 42.25:1
- **Capacitor**: 7-relay 128-step binary array (10–1,997pF, 1pF resolution)
  - 10× 1812 3KV C0G MLCC
  - 7× Omron G5Q-14 relays
- **SWR Sensing**: Onboard Tandem Match directional coupler (FT37-43 + BAT41)
- **Communication**: Serial UART
- **Framework**: Arduino (libmaple core)
- **PCB**: 140×90mm dual-zone with 2.5mm isolation slot
- **Power**: Bias-T coax feed 12V DC
- **Enclosure**: IP66 die-cast AL 160×110×70mm

### Specs
- Frequency: 40m–10m (7.0–29.7 MHz)
- Power: 100W PEP SSB/CW
- Tune time: <0.2s (memory recall) / <2s (full sweep)
- Cost: ~¥390/unit
- 23 components + 12 functions FMEA

### Key Issues (addressed in V3.0)
- 7 relays = 7 mechanical failure points
- Onboard SWR bridge adds complexity and failure modes
- 128-step resolution limited by discrete capacitor values
- T200-2B double stack adds weight and cost
- Arduino framework limits low-level control

---

## [V1.0] — 2026-06-07 — PIC16F1938

### Architecture
- **MCU**: PIC16F1938-I/SO (8-bit, 32MHz, 28KB Flash)
- **Core**: T200-2 ×2 stacked (Type 2 Carbonyl Iron)
- **Capacitor**: 7-relay binary capacitor array
- **SWR Sensing**: Onboard Tandem Match directional coupler
- **Communication**: Serial UART
- **Framework**: MPLAB X IDE + XC8 compiler
- **PCB**: 140×90mm dual-zone with HV isolation slot

### Specs
- Frequency: 40m–10m
- Power: 100W PEP
- Cost: ~¥375/unit

### Key Issues (addressed in V2.0)
- PIC16F1938 limited RAM (1KB) and Flash (28KB)
- MPLAB X toolchain less accessible than Arduino
- No modular SWR meter library (built from scratch)

---

## Design Evolution Summary

| | V1.0 | V2.0 | V3.0 |
|---|---|---|---|
| MCU | PIC16F1938 32MHz | STM32F103 72MHz | ESP32-S3 240MHz dual |
| Core | T200-2 ×2 | T200-2 ×2 | T200-6 ×1 |
| Capacitor | 7-relay 128-step | 7-relay 128-step | Servo continuous |
| SWR | Onboard Tandem Match | Onboard Tandem Match | Remote ATR1000 |
| Comm | Serial UART | Serial UART | WiFi WebSocket |
| Framework | MPLAB XC8 | Arduino | ESP-IDF v5 C |
| PCB | 140×90mm | 140×90mm | 140×50mm |
| Failure Points | 9 | 9 | 2 |
| Cost | ¥375 | ¥390 | ¥430 |
| Firmware | 16 files | 3 files | 12 files ~2800 lines |

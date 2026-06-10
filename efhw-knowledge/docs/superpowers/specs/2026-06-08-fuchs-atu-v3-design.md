# V3.0 Fuchs EFHW Auto Tuner — Design Specification

**Date**: 2026-06-08
**Status**: Design Approved
**Reference**: F5NPV Fuchskreis Remote WiFi ATU, M0UKD EFHW Coupler, AA5TB Parallel LC Theory

---

## §1 System Architecture

ESP32-S3 single-chip WiFi ATU controller driving a servo-tuned Fuchs parallel LC coupler.
SWR sensing is delegated entirely to the MRRC-side ATR1000 — the ATU is a pure actuator.

```
  ┌─────────────────────────────────────────────────────────┐
  │                    Outdoor IP66 Enclosure                │
  │                                                         │
  │   ANT ──┬── GDT(90V) ──┬── T200-6 Toroid ──┬── SO-239  │
  │         │               │    Coupler          │  (TRX)   │
  │         │  2.2MΩ bleed  │   2T:14T            │          │
  │         │               │                     │          │
  │         │               ├── Variable Cap ─────┤          │
  │         │               │   10-500pF          │          │
  │         │               │   MG996R Servo      │          │
  │         │               │                     │          │
  │    ─────┼────────────────┼─────────────────────┤          │
  │         │                │                     │          │
  │    ┌────┴────────────────┴─────────────────────┴──┐       │
  │    │           ESP32-S3 (WROOM-1, 16MB Flash)      │       │
  │    │                                                │       │
  │    │  WiFi STA → WebSocket Client → MRRC Server     │       │
  │    │  Servo PWM (LEDC) + MOSFET power-cut           │       │
  │    │  Bias-T voltage monitor (ADC)                  │       │
  │    │  NVS tune cache, POST, Health Monitor, WDT     │       │
  │    └────────────────────────────────────────────────┘       │
  │                                                         │
  │    Power: Bias-T DC over coax (12-14V)                   │
  └─────────────────────────────────────────────────────────┘
                            │
                     WiFi (Station)
                            │
               ┌────────────┴────────────┐
               │    Home WiFi Router      │
               └────────────┬────────────┘
                            │
               ┌────────────┴────────────┐
               │    MRRC Server           │
               │    Tornado + WebSocket   │
               │    ATR1000 → SWR/PWR     │
               │    Web UI ATU Panel      │
               └─────────────────────────┘
```

### Key changes from V2.0 (STM32F103)

| Component | V2.0 | V3.0 Fuchs |
|---|---|---|
| MCU | STM32F103C8T6 | ESP32-S3-WROOM-1 |
| Core | T200-2B ×2 (μ=10) | T200-6 ×1 (μ=8) |
| Capacitor | 7-bit relay array (128 steps) | Servo-driven variable capacitor (continuous) |
| SWR sensing | Onboard Tandem Match bridge | MRRC ATR1000 (remote) |
| Communication | Serial debug | WiFi WebSocket → MRRC |
| Frequency | 40m–10m | 40m–10m |
| PCB | 140×90mm | 140×50mm |
| BOM cost | ~¥390 | ~¥255 |

---

## §2 RF Chain

### 2.1 T200-6 Coupler

| Parameter | Value |
|---|---|
| Core | T200-6 ×1 (Carbonyl Iron Type 6, μ=8, OD=50.8mm) |
| Primary (TRX side) | 2 turns, 0.8mm enameled copper wire |
| Secondary (ANT side) | 14 turns, 0.5mm enameled copper wire |
| Turns ratio | 2:14 → impedance ratio 1:49 → 50Ω : ~2,450Ω |
| Secondary inductance | ~2.06μH (AL≈10.5 nH/N²) |
| Frequency range (Type 6) | 10–50 MHz nominal |

**B_peak saturation check** (@ 100W PEP, 40m worst case):

- V_peak (secondary) = √(100 × 2450) × √2 ≈ 700V
- T200 A_e ≈ 1.27 cm²
- B_peak = 700 / (4.44 × 7×10⁶ × 14 × 1.27×10⁻⁴) ≈ 12.7 mT
- Type 6 B_sat ≈ 600–800 mT → **safety margin ~47×** ✓
- Single T200-6 is sufficient; no stacking required.

### 2.2 Variable Capacitor & Servo

| Parameter | Value |
|---|---|
| Type | Air-dielectric variable capacitor |
| Range | 10–500 pF |
| Voltage rating | ≥1kV (V_peak ≈ 700V @ 100W, margin 1.4×) |
| Servo | MG996R (metal gear, 6V, 10 kg·cm, 0.17s/60°) |
| Reduction | Gear train 3:1–6:1 (servo 180° → capacitor shaft 0–180°) |
| Power cut | GPIO-driven IRF9540 P-MOSFET cuts servo 6V after tuning |

**Tuning range verification** (L=2.06μH, C=10–500pF):

- f_max = 1/(2π√(2.06×10⁻⁶ × 10×10⁻¹²)) = **35.1 MHz** ✓
- f_min = 1/(2π√(2.06×10⁻⁶ × 500×10⁻¹²)) = **4.96 MHz** ✓
- Covers 40m (7.0 MHz) through 10m (29.7 MHz) with margin.

### 2.3 SWR Sensing — REMOVED

No onboard SWR bridge. The MRRC server reads SWR/FWD/REV from the ATR1000
and relays readings to the ESP32-S3 via WebSocket during tuning.

Tuning loop latency: MRRC → ATR1000 → MRRC → WiFi → ESP32-S3 ≈ 50–100 ms/step.

---

## §3 Digital Control (Hardware)

### 3.1 MCU Module

| Parameter | Selection |
|---|---|
| Module | ESP32-S3-WROOM-1 |
| Core | Xtensa LX7 dual-core 240MHz |
| RAM | 512KB SRAM + 8MB PSRAM |
| Flash | 16MB (OTA + tune cache + future web assets) |
| WiFi | 2.4GHz 802.11 b/g/n, PCB antenna |
| USB | Built-in USB Serial/JTAG (GPIO18/19) |

### 3.2 Pin Assignment

```
IO0  (GPIO0)   → BOOT button (download mode)
IO1  (GPIO1)   → Servo PWM (LEDC_CH0, 50Hz)
IO2  (GPIO2)   → Servo power MOSFET gate control
IO3  (GPIO3)   → UART0 TX (debug serial)
IO4  (GPIO4)   → UART0 RX (debug serial)
IO5  (GPIO5)   → Bias-T voltage monitor (ADC1_CH4)
IO6  (GPIO6)   → Status LED (WS2812B or standard)
IO7  (GPIO7)   → Buzzer (NPN driver)
IO18 (GPIO18)  → USB D- (Serial/JTAG)
IO19 (GPIO19)  → USB D+ (Serial/JTAG)
```

~8 GPIOs used; abundant I/O margin for future expansion (temperature sensor, door switch, etc.).

### 3.3 Servo Driver

```
ESP32-S3 GPIO1 ──→ 330Ω ──→ MG996R signal line (PWM, 50Hz)
                            MG996R VCC ←── 6V (LM2596 DC-DC)
                            MG996R GND ←── GND

ESP32-S3 GPIO2 ──→ 2N2222A ──→ IRF9540 P-MOSFET gate
                                (cuts servo 6V power after tuning)
```

F5NPV relay-based servo power cut replicated with MOSFET — eliminates servo jitter and EMI when idle.

### 3.4 Power Supply

| Rail | Source |
|---|---|
| 13.8V DC | Bias-T over coax → FT37-43 RFC (~95μH, 15T) → 1N4007 reverse protection |
| 12V | LM2940CT-12 LDO (TO-220) from 13.8V |
| 6V | LM2596 DC-DC buck module (12V→6V, 3A) for servo |
| 3.3V | AMS1117-3.3 LDO (SOT-223) for ESP32-S3 |

RFC inductor: FT37-43, 15 turns ≈ 95μH, in series between SO-239 center conductor and matching network input.

### 3.5 Protection (inherited from V2.0)

| Item | Spec |
|---|---|
| GDT | 90V DC breakdown, ≥5kA 8/20μs, antenna-to-ground |
| Bleed resistor | 2.2MΩ 2W metal-glaze non-inductive, antenna-to-ground |
| DC block | 10nF 1KV C0G ×2 (1206), TRX-side SO-239 |
| Reverse polarity | 1N4007 in series with Bias-T DC input |

---

## §4 Firmware Architecture

### 4.1 Framework

- **ESP-IDF v5.x** (native C, CMake build)
- esp_https_ota for firmware updates
- esp_log for leveled logging

### 4.2 FreeRTOS Tasks

| Task | Priority | Role |
|---|---|---|
| `ws_client` | 3 (high) | WebSocket persistent connection to MRRC, JSON parse/encode, heartbeat, reconnection |
| `tune_engine` | 2 | Servo sweep, binary search, position computation, NVS cache management |
| `servo_ctrl` | 2 | LEDC PWM output, MOSFET power-cut control, stall detection |
| `health_mon` | 1 (low) | 10s periodic: Bias voltage, watchdog, status LED, core temperature |

Inter-task communication: `command_queue` (FreeRTOS Queue of `cmd_t` structs).

### 4.3 MRRC ↔ ATU WebSocket Protocol (JSON)

**MRRC → ATU:**

| Command | Fields | Semantics |
|---|---|---|
| `tune_start` | `freq_hz`, `swr`, `fwd_pwr_w` | Initiate tuning cycle |
| `tune_abort` | — | Abort current sweep |
| `set_bypass` | — | Servo to min-C position (bypass) |
| `get_status` | — | Query position/cache/health |

**ATU → MRRC:**

| Event | Fields | Semantics |
|---|---|---|
| `tune_progress` | `cap_pct`, `servo_pos`, `state` | Real-time sweep progress |
| `tune_done` | `cap_pct`, `swr_final`, `elapsed_ms` | Tuning complete with result |
| `tune_error` | `error_code`, `message` | Timeout/stall/RF-lost |
| `status_report` | `pos`, `cache_hits`, `health`, `uptime` | Response to get_status |
| `health_alert` | `alert_code`, `value` | Asynchronous: over-temp, voltage anomaly |

### 4.4 Tuning Algorithm

```
tune_start(freq_hz, initial_swr):
  1. Check NVS cache → hit (±50kHz)? → direct position, report tune_done
  2. Coarse sweep: servo 0°→180°, step 5°, wait for MRRC SWR feedback
     → 36 steps, ~5s
     → Record min_SWR position
  3. Fine sweep (if min_SWR > 1.5):
     min_pos ±15°, step 1°
     → 30 steps, ~3s
  4. SWR < 2.0? → report tune_done, write NVS cache
     SWR > 2.0? → report tune_error("no_match"), servo to min-C
```

**Critical**: No local SWR sampling. Each servo step → ESP32-S3 waits for MRRC
to relay ATR1000 SWR reading via WebSocket. Round-trip ~50–100ms per step.

### 4.5 NVS Tune Cache

```c
typedef struct {
    uint32_t freq_hz;    // frequency key
    uint8_t  servo_pos;  // servo angle 0-180
    uint8_t  padding[3];
} tune_cache_entry_t;    // 8 bytes per entry

// 16KB NVS partition → ~2000 entries → 40m-10m at ~50kHz spacing
```

Cold start incurs a full sweep; subsequent band changes are sub-second from cache.

### 4.6 Health Monitor

| Check | Period | Fault action |
|---|---|---|
| Bias-T voltage | 10s | <10V or >15V → alert, servo to zero |
| Hardware WDT | 5s timeout | Auto-reset ESP32-S3 |
| Servo stall | Per movement | Position unchanged 3× → tune_error, power-cut |
| WiFi disconnect | Real-time | Auto-reconnect, cache preserved locally |
| Core temperature | 30s | >80°C → disable tuning, wait cooldown |

---

## §5 MRRC Integration

### 5.1 Connection Topology

ESP32-S3 connects as a WebSocket **client** to the MRRC server (peer to browser clients).
It does not serve its own web page — all interaction goes through MRRC.

ATR1000 → MRRC (SWR/PWR) → WebSocket → ESP32-S3 ATU → Servo

### 5.2 Server-Side

Extend `ATU_SERVER_WEBSOCKET.py` (or MRRC main Tornado server) with:

- Fuchs ATU WebSocket handler (`/atu` endpoint)
- Message relay: browser ↔ ESP32-S3
- SWR bridge: query ATR1000 on behalf of ATU during active tuning

### 5.3 Web UI — ATU Sub-panel

New collapsible panel in `www/index.html` (paired with `www/controls.js`):

- Real-time servo position bar (0°–180°)
- Current capacitance estimate (pF)
- SWR display with color indicator (green <1.5, yellow <2.0, red >2.0)
- Buttons: Auto Tune, Bypass, Save Preset
- SWR history sparkline (last 10 tunes)

### 5.4 End-to-End Tuning Flow

```
Browser          MRRC Server        ATR1000      ESP32-S3 ATU
  │                 │                  │              │
  ├─ "Tune" ──────→│                  │              │
  │                 ├─ read SWR ──────→│              │
  │                 │←─ SWR=2.8 ──────┤              │
  │                 ├─ tune_start ──────────────────→│
  │                 │  {freq:14200000,swr:2.8,pwr:5} │
  │                 │                  │              ├─ check cache
  │                 │                  │              ├─ step servo +5°
  │                 │←─ tune_progress ───────────────┤
  │                 │  {pos:15,state:sweeping}       │
  │                 ├─ read SWR ──────→│              │
  │                 │←─ SWR=1.8 ──────┤              │
  │                 ├─ swr_update ──────────────────→│
  │                 │                  │              ├─ continue...
  │                 │  ...             ...            │ (iterate)
  │                 │←─ tune_done ───────────────────┤
  │                 │  {cap_pct:67,swr:1.15,ms:3400} │
  │←─ UI update ────┤                  │              │
  │   SWR=1.15 ●    │                  │              │
```

### 5.5 controls.js Changes

```javascript
class FuchsATU {
  constructor(wsUrl)  // connect to MRRC /atu WebSocket
  startTune()         // send tune_start
  abortTune()         // send tune_abort
  setBypass()         // send set_bypass
  handleProgress(msg) // update progress bar in DOM
  handleDone(msg)     // display final SWR, cache indicator
  handleError(msg)    // show error toast
}
```

---

## §6 Enclosure & Mechanical

| Parameter | Value |
|---|---|
| Box | Die-cast aluminum, IP66, 160×110×70mm (same as V2.0) |
| ANT terminal | M5 304SS bolt + PTFE insulating washers + wing nut |
| TRX connector | SO-239 flange-mount, PTFE dielectric |
| Breather | 1.5mm hole bottom face + PTFE vent membrane |
| Mounting | U-bolt clamp, pole or wall mount |
| PCB | FR4 double-sided 140×50mm (reduced from 140×90mm) |

Internal layout:

```
  ┌──────────────────────────────────────────────┐
  │                    ANT (M5 bolt)               │
  │  ┌─────────────────────────────────────────┐ │
  │  │  GDT(90V)  2.2MΩ                        │ │
  │  │                                         │ │
  │  │  ┌──────────┐    ┌───────────────┐      │ │
  │  │  │ T200-6   │    │ Variable Cap  │      │ │
  │  │  │ Coupler  │    │ 10-500pF      │      │ │
  │  │  └──────────┘    │ MG996R ───────┘      │ │
  │  │                  │ (gear-coupled)       │ │
  │  │                  └───────────────────── │ │
  │  │                                         │ │
  │  │  ┌──────────────────────────────┐       │ │
  │  │  │ PCB: ESP32-S3 + PSU + Prot   │       │ │
  │  │  │      140×50mm                │       │ │
  │  │  └──────────────────────────────┘       │ │
  │  └─────────────────────────────────────────┘ │
  │                    SO-239 (TRX)              │
  └──────────────────────────────────────────────┘
```

---

## §7 BOM Estimate

| # | Category | Part | Spec | Qty | ¥/ea | ¥ Subtotal |
|---|---|---|---|---|---|---|
| U1 | MCU | ESP32-S3-WROOM-1 | 16MB Flash | 1 | 25 | 25 |
| U2 | PSU | LM2940CT-12 | 12V LDO TO-220 | 1 | 5 | 5 |
| U3 | PSU | AMS1117-3.3 | 3.3V LDO SOT-223 | 1 | 1 | 1 |
| U4 | DC-DC | LM2596 module | 12→6V 3A | 1 | 8 | 8 |
| T1 | Core | T200-6 | Type 6 μ=8 | 1 | 30 | 30 |
| - | Wire | 0.8mm + 0.5mm enameled | ~3m | 1 lot | 3 | 3 |
| C_var | Cap | Air variable 10-500pF | ≥1kV | 1 | 35 | 35 |
| SERVO | Servo | MG996R | Metal gear 6V | 1 | 18 | 18 |
| L_bias | RFC | FT37-43 15T | ~95μH | 1 | 3 | 3 |
| GDT1 | Protect | 90V GDT | 5kA 8/20μs | 1 | 8 | 8 |
| R_bleed | Protect | 2.2MΩ 2W non-inductive | Metal glaze | 1 | 3 | 3 |
| D1 | Protect | 1N4007 | Reverse protection | 1 | 0.2 | 0.2 |
| C_block | DC-block | 10nF 1KV C0G 1206 | ×2 parallel | 2 | 2.5 | 5 |
| Q1-Q2 | FET | IRF9540 + 2N2222A | Servo power cut | 1 each | 3 | 3 |
| J1 | Conn | SO-239 flange PTFE | | 1 | 8 | 8 |
| J2-J3 | Conn | M5 304SS bolt + PTFE washer | | 2 sets | 5 | 10 |
| LED | Ind | WS2812B or std LED | | 1 | 1 | 1 |
| BZ | Ind | 5V active buzzer | | 1 | 1 | 1 |
| | Misc | 0805 R/C ~15pcs | Decoupling/bias/filter | ~15 | 10 | 10 |
| | Encl | Die-cast Al box IP66 160×110×70 | | 1 | 35 | 35 |
| | PCB | FR4 2-layer 140×50mm | JLCPCB ×5 | 5 | 3 | 15 |
| | Consum | Conformal coat + gears + screws + glands | | 1 lot | 30 | 30 |
| | | | | | **TOTAL** | **~¥255** |

Cost reduction vs V2.0: ¥135 (35%) — primarily from removing 7× G5Q-14 relays, ULN2003A,
7× HV MLCCs, SWR bridge magnetics, and calibration trimmers.

---

## §8 Open Items (to resolve during implementation planning)

1. **Variable capacitor source**: Confirm specific SKU. Salvage from broadcast radios vs. new production unit. Must verify 10-500pF actual range and 1kV rating.
2. **Gear train ratio**: Depends on capacitor shaft rotation range (some are 180°, others 360°). Ratio selected to map MG996R 180° sweep to capacitor full range.
3. **Bias-T RFC inductor**: FT37-43 at 95μH — verify self-resonance is well above 30MHz to avoid parasitic effects on 10m.
4. **ATR1000 integration protocol**: Define exact API for MRRC to query ATR1000 SWR and relay to ATU. Confirm ATR1000 supports per-request polling at ~100ms intervals.
5. **ATU_SERVER_WEBSOCKET.py extension**: Decide whether to add Fuchs handler to existing ATU server or integrate into main MRRC Tornado server.
6. **OTA firmware update strategy**: ESP32-S3 pulls new firmware from MRRC server; define partition table layout for dual-slot OTA.

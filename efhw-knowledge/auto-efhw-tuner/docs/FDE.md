# EFHW Fuchs ATU V3.0 — Fault Detection & Engineering Notes

> **Document ID**: FDE-EFHW-FUCHS-V3.0
> **Version**: V3.0
> **Date**: 2026-06-09
> **Status**: Engineering draft, must be verified on bench
> **Scope**: What this hardware/firmware can actually detect, what it cannot detect, and how to verify the residual risks.

---

## 1. Detection Boundary

V3.0 deliberately removes the onboard SWR bridge, current sense, servo position feedback and relay array. The ATU is therefore a remote servo actuator, not a self-contained RF measuring instrument.

| Signal source | Available in firmware | Notes |
|------|:------:|------|
| MRRC/ATR1000 SWR and forward power | Yes | Provided by WebSocket `tune_start` / `swr_update` messages |
| Bias-T DC voltage | Yes | ADC1_CH4 through 47k/10k divider |
| ESP32 internal temperature | Yes | ESP-IDF temperature sensor, coarse die temperature only |
| WiFi / WebSocket connection state | Yes | ESP-IDF events and websocket callbacks |
| NVS errors | Yes | Return codes from NVS APIs |
| Servo command angle | Yes | Last commanded angle only |
| Servo actual shaft position | No | MG996R has no position feedback output |
| Servo current / stall current | No | No shunt/Hall/current monitor in V3.0 |
| RF voltage at variable capacitor | No | No HV probe or detector |
| RF current / transformer temperature | No | No RF/current/thermal sensors on tank |

**Implication**: Any FMEA item requiring actual servo movement, RF arc detection, transformer heating, or capacitor voltage sensing cannot be claimed as firmware-detectable in V3.0. It can only be inferred indirectly from SWR behavior or found during bench inspection.

---

## 2. Implemented Firmware Detection

These are backed by current firmware paths under `firmware-esp32/main/`.

| ID | Fault / Event | Detection path | Current response | Evidence |
|----|------|------|------|------|
| D01 | Tune overpower | `tune_engine_feed_swr()`: `fwd_pwr_w > TUNE_POWER_MAX_W` | Abort tune, set error, servo to 0°, power off, send `tune_error(overpower)` | `tune_engine.c` |
| D02 | RF lost during tune | `tune_engine_feed_swr()`: `fwd_pwr_w < TUNE_POWER_MIN_W` | Abort tune, set error, servo to 0°, power off, send `tune_error(no_rf)` | `tune_engine.c` |
| D03 | No acceptable match | Best SWR remains `>= TUNE_MAX_ACCEPT_SWR` at end of sweep | Send `tune_error(high_swr)`; do not save cache | `tune_engine.c` |
| D04 | Bias-T under/over voltage | `health_mon_tick()` ADC check outside `BIAS_V_MIN/MAX` | Send health alert, set `SYS_DEGRADED` while out of range | `health_mon.c` |
| D05 | ESP32 die temperature high | `temperature_sensor_get_celsius() > CORE_TEMP_MAX_C` | Set `SYS_DEGRADED`; currently no health alert JSON for temp | `health_mon.c` |
| D06 | WiFi disconnect | `WIFI_EVENT_STA_DISCONNECTED` | Mark disconnected, delay, reconnect | `ws_client.c` |
| D07 | WebSocket disconnect/error | `WEBSOCKET_EVENT_DISCONNECTED/ERROR` | Mark disconnected; IDF websocket auto-reconnect enabled | `ws_client.c` |
| D08 | Malformed JSON | `cJSON_Parse()` returns NULL or missing `cmd` | Drop message silently | `ws_client.c` |
| D09 | NVS partition init failure / version mismatch | `nvs_flash_init_partition()` return code | Erase tune partition and reinit | `nvs_cache.c` |
| D10 | NVS save/commit failure | `nvs_set_u8()` / `nvs_commit()` return code | Log error, continue without persisted cache | `nvs_cache.c` |
| D11 | Task lockup | ESP-IDF WDT if enabled by project config | Reset by ESP-IDF | SDK config / runtime |

---

## 3. Not Firmware-Detectable In V3.0

These risks are real, but current hardware has no sensor path to detect them directly.

| ID | Fault | Why firmware cannot prove it | Practical detection | Engineering control |
|----|------|------|------|------|
| N01 | Servo mechanical stall | Only commanded angle is known; actual shaft position/current are unknown | Bench observation, abnormal noise, SWR not changing during sweep | Good mechanical alignment, gear guard, current sensor in next revision |
| N02 | Servo stripped gear / coupler slip | PWM command can change while capacitor does not move | SWR curve flat across commanded sweep; visual inspection | Locking hardware, witness marks on shaft/gears, periodic inspection |
| N03 | IRF9540 open / 2N2222 open | No VCC_SERVO ADC measurement | Bench measure HDR_SERVO VCC during `servo_power_on()` | Add servo rail divider/test point; verify before RF testing |
| N04 | IRF9540 short | Firmware cannot measure servo rail when idle | Servo buzz/heat when idle; bench measure VCC_SERVO after power-off | Gate pull-up to source, idle current check |
| N05 | Variable capacitor arc-over | No RF voltage/light/acoustic sensor | SWR sudden jump, visible marks, audible snap during low-power test | Transmitter-grade capacitor, smooth HV wiring, adequate spacing, dry enclosure |
| N06 | T200-6 overheating | No tank temperature sensor | IR camera / thermal probe after key-down test | 5W tune limit, duty-cycle limit, post-build thermal test |
| N07 | HV_GAP misfire | No RF detector around gap | Visible/audible discharge, erratic SWR | Default DNP; install only after bench confirmation |
| N08 | Water ingress | No humidity sensor | Inspection, corrosion, unstable ADC/WiFi | IP66 seals, PTFE vent, desiccant, maintenance interval |

Do not expose any of these as guaranteed `servo_stall` or `arc_detected` firmware errors unless new sensors are added.

---

## 4. High-Risk Engineering Items

### 4.1 HV Variable Capacitor Arc-Over

| Item | Detail |
|------|------|
| Failure mode | Plate arc-over, contamination tracking, or permanent plate short |
| Severity | High: can damage capacitor, detune antenna, carbonize supports |
| Detection rating | Poor in firmware; must be bench/visual/audio/SWR inferred |
| Primary control | Use transmitter-grade air variable capacitor, working voltage >=5kV or plate spacing >=1.5mm |
| Layout control | RF hot end off-PCB, >=15mm clearance to low-voltage wiring, rounded solder joints, dry enclosure |
| Protection | `HV_GAP` footprint only; default DNP; no 90V/200V GDT on RF hot end |
| Test | 40m first, <=5W tune power, dark-room visual/audible arc check, inspect plates after test |

### 4.2 Servo / Gear Train Failure

| Item | Detail |
|------|------|
| Failure mode | Stall, gear tooth skip, set screw slip, capacitor end-stop collision |
| Severity | Medium/High: ATU cannot tune or may force capacitor plates |
| Detection rating | Poor in firmware; no position/current feedback |
| Primary control | Mechanical end-stop margin, gear backlash 0.1-0.2mm, full 0-180° dry run before RF |
| Test | Manual sweep 0°, 90°, 180°; verify capacitor Cmin/Cmax and no end-stop binding |
| Next revision | Add servo current sense or position feedback; then implement real stall detection |

### 4.3 WiFi / MRRC Dependency

| Item | Detail |
|------|------|
| Failure mode | WiFi/MRRC/ATR1000 unavailable |
| Severity | Medium: ATU cannot perform new tune; cached mechanical position remains physical |
| Detection rating | Good for WiFi/WS disconnect, external for ATR1000 availability |
| Current control | Auto reconnect; LED indication; NVS cache survives reboot |
| Residual risk | No offline SWR fallback in V3.0 |

### 4.4 Bias-T Supply Fault

| Item | Detail |
|------|------|
| Failure mode | DC rail too low/high, long coax drop, supply transient |
| Severity | Medium: servo weak, ESP32 unstable, DC-DC stress |
| Detection rating | Good for 12V rail through ADC divider |
| Current control | Health alert and `SYS_DEGRADED`; tune disable is not yet enforced in code |
| Test | Sweep supply to 9V and 16V; verify alert and state transition |

---

## 5. State Handling Reality Check

Current `sys_health_t` has `SYS_HEALTHY`, `SYS_DEGRADED`, and `SYS_SAFE`, but the implemented health monitor only toggles between healthy and degraded for ADC/temp conditions. It does not currently count tune failures, enforce a safe latch, or block tuning.

| State | Implemented behavior | Not yet implemented |
|------|------|------|
| `SYS_HEALTHY` | Default state when Bias-V/temp are normal | None |
| `SYS_DEGRADED` | Set when Bias-V out of range or temp too high; clears when normal | Does not automatically block tune |
| `SYS_SAFE` | Enum exists | No latch logic, no 3-fail counter, no recovery rule |

If `SYS_SAFE` is required, add explicit code before documenting it as a delivered safety feature.

---

## 6. Bench Verification Matrix

| Test | Method | Expected result | Pass criteria |
|------|------|------|------|
| Servo power polarity | Measure HDR_SERVO VCC while calling `servo_power_on/off` | ON=6V, OFF=0V | Confirms GPIO2 HIGH enables P-MOS gate pulldown path |
| Dry servo travel | Command 0°, 90°, 180° without RF | Smooth motion, no end-stop bind | Cmin/Cmax reached with mechanical margin |
| NVS save/lookup | Tune/save at one frequency, reboot, tune same frequency | Cache hit, direct position | No full sweep on same frequency |
| NVS fuzzy lookup | Tune 14.200MHz, request 14.205MHz | Cache hit within tolerance | Nearest cache used |
| Overpower abort | Send `swr_update` with `fwd_pwr_w=100` during tune | `tune_error(overpower)` and servo off | No further sweep movement |
| RF lost abort | Send `swr_update` with `fwd_pwr_w=0.1` during tune | `tune_error(no_rf)` and servo off | No further sweep movement |
| High-SWR failure | Tune into dummy/non-resonant setup | `tune_error(high_swr)` | No NVS save for failed tune |
| Bias low alert | Bias supply at 9V | Health alert and `SYS_DEGRADED` | Restores when voltage normal |
| Bias high alert | Bias supply at 16V | Health alert and `SYS_DEGRADED` | Restores when voltage normal |
| WiFi reconnect | Power-cycle AP | Disconnect indication, reconnect after AP returns | WS resumes |
| HV arc margin | 40m, <=5W tune, observe in dark | No arc/snap/tracking | Inspect capacitor and HV wiring |
| HV_GAP DNP check | Confirm not installed by default | No low-voltage GDT across RF hot end | Prevents normal RF misfire |

---

## 7. Maintenance Schedule

| Interval | Action |
|------|------|
| Monthly | Review MRRC SWR trends; listen for servo/gear noise during a short dry sweep |
| 6 months | Open enclosure: inspect gear wear, set screws, RF hot-end clearance, capacitor plates, arc marks, moisture, desiccant |
| Annual | Verify Cmin/Cmax, re-check Bias-V ADC calibration, erase/rebuild NVS cache if mappings look stale |
| After any arc event | Stop using at 100W; clean/inspect capacitor and insulators; repeat low-power dark-room test |

---

## 8. Design Actions For Next Revision

| Priority | Action | Reason |
|------|------|------|
| High | Add servo rail voltage sense or current sense | Enables real detection of MOSFET open/short and servo stall current |
| High | Add tune timeout / SWR-update timeout in `tune_engine` | Prevent indefinite wait if MRRC stops sending updates mid-sweep |
| Medium | Implement `SYS_SAFE` latch and 3-fail counter | Makes documented health FSM enforceable |
| Medium | Add optional local low-accuracy SWR bridge | Removes complete dependency on WiFi/MRRC for emergency tuning |
| Low | Add humidity or enclosure leak indicator | Improves outdoor maintenance planning |

---

> **Related documents**: [`SDD.md`](SDD.md) · [`../hardware/SCH_Description.md`](../hardware/SCH_Description.md) · [`../hardware/PCB_Description.md`](../hardware/PCB_Description.md) · [`V3_MIGRATION_CHECKLIST.md`](V3_MIGRATION_CHECKLIST.md)

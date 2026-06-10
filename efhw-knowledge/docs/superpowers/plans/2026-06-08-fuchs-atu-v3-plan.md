# Fuchs ATU V3.0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the EFHW Auto Tuner from STM32F103 + relay capacitor array to ESP32-S3 + T200-6 toroid + servo-driven variable capacitor, integrated into MRRC via WebSocket.

**Architecture:** ESP32-S3 runs ESP-IDF v5 with 4 FreeRTOS tasks (ws_client, tune_engine, servo_ctrl, health_mon). RF chain is a Fuchs parallel-LC coupler: T200-6 toroid (2:14 turns), single air variable capacitor (10-500pF) driven by MG996R servo. No onboard SWR sensing — SWR readings come from MRRC ATR1000 relayed via WebSocket JSON protocol. ATU appears as a sub-panel in MRRC web UI.

**Tech Stack:** ESP-IDF v5.x C, FreeRTOS, lwIP WebSocket, LEDC PWM, NVS Flash, MRRC Tornado/Python WebSocket server, HTML5/CSS/JS ATU panel.

---

## File Structure

```
auto-efhw-tuner/
├── firmware-esp32/              ← NEW: V3.0 ESP32-S3 firmware
│   ├── CMakeLists.txt           # Top-level project
│   ├── sdkconfig.defaults       # ESP-IDF defaults
│   ├── partitions.csv           # OTA partition table
│   └── main/
│       ├── CMakeLists.txt       # Component build
│       ├── atu_main.c           # app_main, FreeRTOS tasks, event loops
│       ├── atu_config.h         # All compile-time constants & pin map
│       ├── ws_client.h          # WebSocket client — connect/read/write
│       ├── ws_client.c
│       ├── tune_engine.h        # Servo sweep algorithm + NVS cache
│       ├── tune_engine.c
│       ├── servo_ctrl.h         # LEDC PWM + MOSFET power-cut
│       ├── servo_ctrl.c
│       ├── health_mon.h         # Periodic health checks + WDT
│       ├── health_mon.c
│       ├── nvs_cache.h          # NVS tune cache read/write
│       ├── nvs_cache.c
│       └── protocol.h           # JSON command/event definitions
├── firmware-legacy/             ← ARCHIVE: old V1.0+V2.0 moved here
│   ├── stm32/                   # V2.0 STM32F103 firmware
│   └── pic/                     # V1.0 PIC16 firmware
├── hardware/
│   ├── EFHW_TUNER_BOM.csv       ← MODIFIED: V3.0 BOM
│   ├── SCH_Description.md       ← MODIFIED: V3.0 schematic
│   ├── PCB_Description.md       ← MODIFIED: V3.0 PCB layout
│   ├── EFHW_TUNER_BOM_STM32.csv ← KEEP: reference only, renamed
│   └── simulation/              ← KEEP: SPICE sims still valid for RF chain
├── docs/
│   ├── SDD.md                   ← MODIFIED: V3.0 software design
│   └── FDE.md                   ← MODIFIED: V3.0 fault engineering
├── bias-tee/                    ← KEEP: unchanged
└── README.md                    ← MODIFIED: full V3.0 update
```

**MRRC side (files in /Users/cheenle/UHRR/MRRC/):**
```
MRRC (Tornado server root)
├── www/
│   ├── index.html               ← MODIFIED: add ATU sub-panel HTML
│   ├── controls.js              ← MODIFIED: add FuchsATU class
│   └── mobile_modern.html       ← MODIFIED: add ATU controls (mobile)
└── atu_fuchs_handler.py         ← NEW: WebSocket handler for ESP32-S3 ATU
```

---

## Phase 1: Foundation — ESP-IDF project skeleton & config

### Task 1: Create firmware-esp32 project skeleton

**Files:**
- Create: `auto-efhw-tuner/firmware-esp32/CMakeLists.txt`
- Create: `auto-efhw-tuner/firmware-esp32/sdkconfig.defaults`
- Create: `auto-efhw-tuner/firmware-esp32/partitions.csv`
- Create: `auto-efhw-tuner/firmware-esp32/main/CMakeLists.txt`
- Create: `auto-efhw-tuner/firmware-esp32/main/atu_config.h`

- [ ] **Step 1: Top-level CMakeLists.txt**

```cmake
cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(efhw_fuchs_atu)
```

- [ ] **Step 2: sdkconfig.defaults**

```ini
CONFIG_IDF_TARGET="esp32s3"
CONFIG_ESPTOOLPY_FLASHMODE_QIO=y
CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y
CONFIG_PARTITION_TABLE_CUSTOM=y
CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="partitions.csv"
CONFIG_ESP_WIFI_SSID=""
CONFIG_ESP_WIFI_PASSWORD=""
CONFIG_ESP_WIFI_STATIC_RX_BUFFER_NUM=16
CONFIG_ESP_WIFI_DYNAMIC_RX_BUFFER_NUM=32
CONFIG_LWIP_MAX_SOCKETS=8
CONFIG_ESP_MAIN_TASK_STACK_SIZE=4096
CONFIG_FREERTOS_HZ=1000
CONFIG_COMPILER_OPTIMIZATION_SIZE=y
CONFIG_ESP_TASK_WDT_TIMEOUT_S=5
CONFIG_ESP_TASK_WDT_PANIC=y
```

- [ ] **Step 3: partitions.csv**

```csv
# Name,   Type, SubType, Offset,  Size, Flags
nvs,      data, nvs,     0x9000,  0x6000,
otadata,  data, ota,     0xf000,  0x2000,
phy_init, data, phy,     0x11000, 0x1000,
ota_0,    app,  ota_0,   0x20000, 0x6E0000,
ota_1,    app,  ota_1,   0x700000,0x6E0000,
coredump, data, coredump,0xDE0000,0x10000,
nvs_tune, data, nvs,     0xDF0000,0x6000,
```

The `nvs_tune` partition (24KB) holds the tune cache separately from system NVS.

- [ ] **Step 4: main/CMakeLists.txt**

```cmake
idf_component_register(
    SRCS
        "atu_main.c"
        "ws_client.c"
        "tune_engine.c"
        "servo_ctrl.c"
        "health_mon.c"
        "nvs_cache.c"
    INCLUDE_DIRS
        "."
    REQUIRES
        nvs_flash
        esp_wifi
        esp_netif
        esp_http_client
        esp_websocket_client
        esp_ota_ops
        ledc
        driver
        json
        esp_event
        freertos
        spi_flash
)
```

- [ ] **Step 5: atu_config.h**

```c
/*
 * atu_config.h — Fuchs ATU V3.0 ESP32-S3 hardware config
 */

#ifndef ATU_CONFIG_H
#define ATU_CONFIG_H

#include "driver/gpio.h"
#include "driver/ledc.h"
#include "driver/adc.h"
#include "freertos/FreeRTOS.h"

// ============================================================
// 1. WiFi
// ============================================================
#define WIFI_SSID_ENV_VAR       "wifi_ssid"
#define WIFI_PASS_ENV_VAR       "wifi_pass"
#define WIFI_CONNECT_TIMEOUT_MS 15000
#define WIFI_RETRY_INTERVAL_MS  10000

// ============================================================
// 2. MRRC WebSocket Server
// ============================================================
#define MRRC_WS_URL_DEFAULT     "ws://192.168.1.100:8877/atu"
#define MRRC_WS_RECONNECT_MS    3000
#define MRRC_WS_PING_INTERVAL_S 30

// ============================================================
// 3. GPIO Pin Map (ESP32-S3)
// ============================================================
#define PIN_SERVO_PWM           GPIO_NUM_1    // LEDC_CH0 → MG996R signal
#define PIN_SERVO_POWER_CUT     GPIO_NUM_2    // MOSFET gate → servo VCC cut
#define PIN_STATUS_LED          GPIO_NUM_6    // WS2812B or standard LED
#define PIN_BUZZER              GPIO_NUM_7    // Active buzzer via NPN

// ADC
#define ADC_BIAS_V_CHANNEL      ADC1_CHANNEL_4  // GPIO5
#define ADC_BIAS_V_ATTEN        ADC_ATTEN_DB_11 // 3.3V full scale
#define ADC_BIAS_V_DIVIDER      5.7f            // 47k+10k divider

// ============================================================
// 4. Servo Parameters
// ============================================================
#define SERVO_PWM_FREQ_HZ       50
#define SERVO_PWM_TIMER         LEDC_TIMER_0
#define SERVO_PWM_MODE          LEDC_HIGH_SPEED_MODE
#define SERVO_PWM_CHANNEL       LEDC_CHANNEL_0
#define SERVO_PWM_RESOLUTION    LEDC_TIMER_16_BIT  // 65535 counts

// MG996R: 500-2500µs pulse = 0°-180°
// At 50Hz, period = 20ms = 20000µs
// 16-bit resolution → 65535 counts → 3277 counts = 1ms
#define SERVO_PULSE_MIN_US      500
#define SERVO_PULSE_MAX_US      2500
#define SERVO_PULSE_NEUTRAL_US  1500
#define SERVO_DUTY_MIN          ((SERVO_PULSE_MIN_US * 65535ULL) / 20000)
#define SERVO_DUTY_MAX          ((SERVO_PULSE_MAX_US * 65535ULL) / 20000)

// Sweep: 0°→180° corresponds to capacitor min→max
#define SERVO_SWEEP_DEGREES     180
#define SERVO_COARSE_STEP_DEG   5       // 36 steps
#define SERVO_FINE_STEP_DEG     1       // 30 steps
#define SERVO_MOVE_DELAY_MS     80      // settle time per step

// Stall detection
#define SERVO_STALL_RETRIES     3
#define SERVO_STALL_THRESHOLD_MS 200

// ============================================================
// 5. Tuning Parameters
// ============================================================
#define TUNE_POWER_MIN_W        0.5f
#define TUNE_POWER_MAX_W        15.0f
#define TUNE_COOLDOWN_S         3
#define TUNE_EARLY_EXIT_SWR     1.05f
#define TUNE_MAX_ACCEPT_SWR     2.0f
#define TUNE_FINE_THRESHOLD_SWR 1.5f   // SWR > this → run fine sweep

// ============================================================
// 6. NVS Tune Cache
// ============================================================
#define NVS_TUNE_PARTITION      "nvs_tune"
#define NVS_NAMESPACE           "tunecache"
#define NVS_KEY_PREFIX          "f"     // "f" + freq_khz string
#define NVS_MAX_ENTRIES         2048

// ============================================================
// 7. Health Monitor
// ============================================================
#define BIAS_V_MIN              10.0f
#define BIAS_V_MAX              15.0f
#define CORE_TEMP_MAX_C         80.0f
#define HEALTH_CHECK_INTERVAL_MS 10000

// ============================================================
// 8. Type Definitions
// ============================================================
typedef enum {
    ATU_IDLE = 0,
    ATU_SWEEPING,
    ATU_FINE_TUNING,
    ATU_LOCKED,
    ATU_ERROR,
} atu_state_t;

typedef enum {
    TUNE_OK = 0,
    TUNE_ERR_OVERPOWER,
    TUNE_ERR_NORF,
    TUNE_ERR_HIGHSWR,
    TUNE_ERR_SERVO_STALL,
    TUNE_ERR_TIMEOUT,
    TUNE_ERR_WS_DISCONNECT,
} tune_error_t;

typedef enum {
    SYS_HEALTHY = 0,
    SYS_DEGRADED = 1,
    SYS_SAFE = 2,
} sys_health_t;

typedef struct {
    bool        success;
    uint8_t     servo_pos;      // final position 0-180
    float       best_swr;
    uint32_t    elapsed_ms;
    tune_error_t error;
} tune_result_t;

#endif /* ATU_CONFIG_H */
```

- [ ] **Step 6: Commit**

```bash
git add auto-efhw-tuner/firmware-esp32/
git commit -m "feat: Fuchs ATU V3.0 ESP-IDF project skeleton and config"
```

---

## Phase 2: ESP32 Firmware — Core modules

### Task 2: protocol.h — WebSocket JSON protocol definitions

**Files:**
- Create: `auto-efhw-tuner/firmware-esp32/main/protocol.h`

- [ ] **Step 1: Write protocol.h**

```c
/*
 * protocol.h — MRRC ↔ ATU WebSocket JSON protocol definitions
 */

#ifndef PROTOCOL_H
#define PROTOCOL_H

#include "cJSON.h"

// ============================================================
// MRRC → ATU commands
// ============================================================

// tune_start: initiate tuning cycle
// {"cmd":"tune_start","freq_hz":14200000,"swr":2.8,"fwd_pwr_w":5.2}
typedef struct {
    uint32_t freq_hz;
    float    swr;
    float    fwd_pwr_w;
} cmd_tune_start_t;

cmd_tune_start_t proto_parse_tune_start(const char *json);

// tune_abort: abort current sweep
// {"cmd":"tune_abort"}

// set_bypass: servo to min-C (bypass mode)
// {"cmd":"set_bypass"}

// get_status: query ATU state
// {"cmd":"get_status"}

// swr_update: MRRC relays new SWR reading during sweep
// {"cmd":"swr_update","swr":1.8,"fwd_pwr_w":5.0}
typedef struct {
    float swr;
    float fwd_pwr_w;
} cmd_swr_update_t;

cmd_swr_update_t proto_parse_swr_update(const char *json);

// ============================================================
// ATU → MRRC events
// ============================================================

// tune_progress: real-time sweep progress
// {"evt":"tune_progress","cap_pct":45,"servo_pos":82,"state":"sweeping"}
char *proto_build_tune_progress(uint8_t cap_pct, uint8_t servo_pos,
                                const char *state);

// tune_done: tuning complete
// {"evt":"tune_done","cap_pct":67,"swr_final":1.15,"elapsed_ms":3400}
char *proto_build_tune_done(uint8_t cap_pct, float swr_final,
                            uint32_t elapsed_ms);

// tune_error: tuning failed
// {"evt":"tune_error","code":3,"message":"no_match"}
char *proto_build_tune_error(tune_error_t error);

// status_report: response to get_status
// {"evt":"status_report","pos":82,"cache_hits":142,"health":0,"uptime":3600}
char *proto_build_status_report(uint8_t pos, uint32_t cache_hits,
                                sys_health_t health, uint32_t uptime);

// health_alert: asynchronous alert
// {"evt":"health_alert","code":1,"value":9.2,"message":"DC_RAIL under-voltage"}
char *proto_build_health_alert(uint8_t code, float value, const char *message);

#endif /* PROTOCOL_H */
```

- [ ] **Step 2: Commit**

```bash
git add auto-efhw-tuner/firmware-esp32/main/protocol.h
git commit -m "feat: ATU WebSocket JSON protocol definitions"
```

### Task 3: servo_ctrl — Servo PWM & power management

**Files:**
- Create: `auto-efhw-tuner/firmware-esp32/main/servo_ctrl.h`
- Create: `auto-efhw-tuner/firmware-esp32/main/servo_ctrl.c`

- [ ] **Step 1: Write servo_ctrl.h**

```c
/*
 * servo_ctrl.h — MG996R servo PWM + MOSFET power-cut control
 */

#ifndef SERVO_CTRL_H
#define SERVO_CTRL_H

#include "atu_config.h"
#include <stdint.h>
#include <stdbool.h>

// Initialize LEDC PWM channel and GPIO for servo control
void servo_init(void);

// Set servo angle (0-180 degrees). Returns false on invalid input.
bool servo_set_angle(uint8_t degrees);

// Get last-set angle
uint8_t servo_get_angle(void);

// Cut servo power (MOSFET off) — for idle state
void servo_power_off(void);

// Restore servo power (MOSFET on) — for tuning
void servo_power_on(void);

// Quick check: did servo move? (compare last angle)
bool servo_detect_stall(void);

#endif /* SERVO_CTRL_H */
```

- [ ] **Step 2: Write servo_ctrl.c**

```c
/*
 * servo_ctrl.c — MG996R servo PWM + MOSFET power-cut implementation
 *
 * PWM: 50Hz, 16-bit resolution
 * Pulse: 500-2500µs maps to 0-180°
 * Power: GPIO-driven IRF9540 P-MOSFET via 2N2222A
 *        HIGH on gate → P-MOSFET OFF → servo VCC disconnected
 *        LOW  on gate → P-MOSFET ON  → servo VCC connected
 */

#include "servo_ctrl.h"
#include "driver/ledc.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "servo";
static uint8_t current_angle = 0;
static uint8_t prev_angle = 255;  // invalid start

void servo_init(void) {
    // Configure LEDC timer (50Hz PWM)
    ledc_timer_config_t timer_cfg = {
        .speed_mode = SERVO_PWM_MODE,
        .duty_resolution = SERVO_PWM_RESOLUTION,
        .timer_num = SERVO_PWM_TIMER,
        .freq_hz = SERVO_PWM_FREQ_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&timer_cfg));

    // Configure LEDC channel
    ledc_channel_config_t channel_cfg = {
        .gpio_num = PIN_SERVO_PWM,
        .speed_mode = SERVO_PWM_MODE,
        .channel = SERVO_PWM_CHANNEL,
        .timer_sel = SERVO_PWM_TIMER,
        .duty = 0,
        .hpoint = 0,
    };
    ESP_ERROR_CHECK(ledc_channel_config(&channel_cfg));

    // Configure servo power MOSFET control pin
    gpio_config_t pwr_cfg = {
        .pin_bit_mask = (1ULL << PIN_SERVO_POWER_CUT),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&pwr_cfg));

    // Default: power OFF (MOSFET gate HIGH → P-MOSFET off)
    servo_power_off();

    ESP_LOGI(TAG, "Initialized: PWM 50Hz, 16-bit, pin=%d, power_cut=%d",
             PIN_SERVO_PWM, PIN_SERVO_POWER_CUT);
}

bool servo_set_angle(uint8_t degrees) {
    if (degrees > SERVO_SWEEP_DEGREES) return false;

    prev_angle = current_angle;

    // Map degrees to pulse width in µs, then to duty
    uint32_t pulse_us = SERVO_PULSE_MIN_US +
        ((uint32_t)degrees * (SERVO_PULSE_MAX_US - SERVO_PULSE_MIN_US)) /
        SERVO_SWEEP_DEGREES;

    uint32_t duty = (pulse_us * 65535ULL) / 20000;

    ESP_ERROR_CHECK(ledc_set_duty(SERVO_PWM_MODE, SERVO_PWM_CHANNEL, duty));
    ESP_ERROR_CHECK(ledc_update_duty(SERVO_PWM_MODE, SERVO_PWM_CHANNEL));

    current_angle = degrees;

    vTaskDelay(pdMS_TO_TICKS(SERVO_MOVE_DELAY_MS));
    return true;
}

uint8_t servo_get_angle(void) {
    return current_angle;
}

void servo_power_off(void) {
    gpio_set_level(PIN_SERVO_POWER_CUT, 1);  // HIGH → P-MOSFET off
    ESP_LOGD(TAG, "Servo power OFF");
}

void servo_power_on(void) {
    gpio_set_level(PIN_SERVO_POWER_CUT, 0);  // LOW → P-MOSFET on
    ESP_LOGD(TAG, "Servo power ON");
    vTaskDelay(pdMS_TO_TICKS(50));  // power-up settle
}

bool servo_detect_stall(void) {
    // Compare against previous position; if unchanged after move command,
    // servo may be stalled or mechanically blocked
    return (current_angle == prev_angle);
}
```

- [ ] **Step 3: Commit**

```bash
git add auto-efhw-tuner/firmware-esp32/main/servo_ctrl.h auto-efhw-tuner/firmware-esp32/main/servo_ctrl.c
git commit -m "feat: servo_ctrl — MG996R PWM + MOSFET power-cut module"
```

### Task 4: nvs_cache — Tune cache with NVS persistence

**Files:**
- Create: `auto-efhw-tuner/firmware-esp32/main/nvs_cache.h`
- Create: `auto-efhw-tuner/firmware-esp32/main/nvs_cache.c`

- [ ] **Step 1: Write nvs_cache.h**

```c
/*
 * nvs_cache.h — Non-Volatile Storage tune cache
 *
 * Stores frequency → servo_position mappings in dedicated NVS partition.
 * Key format: "f" + freq_khz (e.g., "f14200" for 14.200 MHz)
 * Value: single uint8_t servo position (0-180)
 */

#ifndef NVS_CACHE_H
#define NVS_CACHE_H

#include "atu_config.h"
#include <stdint.h>
#include <stdbool.h>

// Initialize NVS partition for tune cache
bool nvs_cache_init(void);

// Look up servo position for a given frequency (±50kHz tolerance)
// Returns true if found, writes position to *pos
bool nvs_cache_lookup(uint32_t freq_hz, uint8_t *pos);

// Save servo position for a frequency
bool nvs_cache_save(uint32_t freq_hz, uint8_t pos);

// Get total cache hits counter
uint32_t nvs_cache_get_hits(void);

// Get total cache saves counter
uint32_t nvs_cache_get_saves(void);

// Erase entire tune cache partition
bool nvs_cache_erase_all(void);

#endif /* NVS_CACHE_H */
```

- [ ] **Step 2: Write nvs_cache.c**

```c
/*
 * nvs_cache.c — NVS tune cache implementation
 */

#include "nvs_cache.h"
#include "nvs_flash.h"
#include "esp_log.h"
#include <stdio.h>

static const char *TAG = "nvs_cache";
static nvs_handle_t cache_handle;
static uint32_t cache_hit_count = 0;
static uint32_t cache_save_count = 0;
static bool initialized = false;

bool nvs_cache_init(void) {
    esp_err_t ret = nvs_flash_init_partition(NVS_TUNE_PARTITION);
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES ||
        ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS tune partition needs format, erasing...");
        ESP_ERROR_CHECK(nvs_flash_erase_partition(NVS_TUNE_PARTITION));
        ret = nvs_flash_init_partition(NVS_TUNE_PARTITION);
    }
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "NVS tune partition init failed: %d", ret);
        return false;
    }

    ret = nvs_open_from_partition(NVS_TUNE_PARTITION, NVS_NAMESPACE,
                                   NVS_READWRITE, &cache_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "NVS namespace open failed: %d", ret);
        return false;
    }

    initialized = true;
    ESP_LOGI(TAG, "Tune cache initialized (%s partition)", NVS_TUNE_PARTITION);
    return true;
}

bool nvs_cache_lookup(uint32_t freq_hz, uint8_t *pos) {
    if (!initialized || !pos) return false;

    // Search ±50kHz: try freq_khz, freq_khz-10, freq_khz+10, ... up to ±50
    uint16_t base_khz = (uint16_t)(freq_hz / 1000);
    uint8_t tolerance = 50 / 10;  // ±5 steps at 10kHz spacing

    for (int8_t offset = -tolerance; offset <= (int8_t)tolerance; offset++) {
        char key[16];
        int len = snprintf(key, sizeof(key), "%s%u",
                          NVS_KEY_PREFIX, base_khz + (uint16_t)(offset * 10));
        if (len < 0 || len >= sizeof(key)) continue;

        uint8_t out = 0;
        size_t size = sizeof(out);
        esp_err_t err = nvs_get_blob(cache_handle, key, &out, &size);
        if (err == ESP_OK) {
            *pos = out;
            cache_hit_count++;
            return true;
        }
    }
    return false;
}

bool nvs_cache_save(uint32_t freq_hz, uint8_t pos) {
    if (!initialized) return false;

    uint16_t freq_khz = (uint16_t)(freq_hz / 1000);
    char key[16];
    snprintf(key, sizeof(key), "%s%u", NVS_KEY_PREFIX, freq_khz);

    esp_err_t err = nvs_set_u8(cache_handle, key, pos);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS save failed for %s: %d", key, err);
        return false;
    }

    err = nvs_commit(cache_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS commit failed: %d", err);
        return false;
    }

    cache_save_count++;
    ESP_LOGI(TAG, "Saved: %ukHz → pos=%d", freq_khz, pos);
    return true;
}

uint32_t nvs_cache_get_hits(void) { return cache_hit_count; }
uint32_t nvs_cache_get_saves(void) { return cache_save_count; }

bool nvs_cache_erase_all(void) {
    if (!initialized) return false;
    nvs_close(cache_handle);
    esp_err_t err = nvs_flash_erase_partition(NVS_TUNE_PARTITION);
    if (err != ESP_OK) return false;
    return nvs_cache_init();
}
```

- [ ] **Step 3: Commit**

```bash
git add auto-efhw-tuner/firmware-esp32/main/nvs_cache.h auto-efhw-tuner/firmware-esp32/main/nvs_cache.c
git commit -m "feat: nvs_cache — NVS tune cache with ±50kHz frequency lookup"
```

### Task 5: tune_engine — Tuning algorithm (servo sweep + cache + state machine)

**Files:**
- Create: `auto-efhw-tuner/firmware-esp32/main/tune_engine.h`
- Create: `auto-efhw-tuner/firmware-esp32/main/tune_engine.c`

- [ ] **Step 1: Write tune_engine.h**

```c
/*
 * tune_engine.h — Tuning algorithm: cache lookup → coarse sweep → fine sweep
 *
 * Does NOT sample SWR locally. Each step waits for MRRC to send
 * a swr_update command via the ws_client → command queue.
 */

#ifndef TUNE_ENGINE_H
#define TUNE_ENGINE_H

#include "atu_config.h"
#include <stdint.h>
#include <stdbool.h>

// Initialize tune engine state
void tune_engine_init(void);

// Start a tuning cycle for the given frequency and initial SWR
void tune_engine_start(uint32_t freq_hz, float initial_swr);

// Feed SWR reading from MRRC (called when swr_update received)
void tune_engine_feed_swr(float swr, float fwd_pwr_w);

// Abort current tuning cycle
void tune_engine_abort(void);

// Get current ATU state
atu_state_t tune_engine_get_state(void);

// Get current servo position during sweep (for progress reporting)
uint8_t tune_engine_get_progress_pct(void);

// Get last tune result
tune_result_t tune_engine_get_result(void);

// Check if tune cycle is complete
bool tune_engine_is_done(void);

// Callback type: function to send event JSON to MRRC
typedef void (*tune_event_cb_t)(const char *json_str);

// Register callback for tune events (tune_progress, tune_done, tune_error)
void tune_engine_set_event_callback(tune_event_cb_t cb);

#endif /* TUNE_ENGINE_H */
```

- [ ] **Step 2: Write tune_engine.c**

```c
/*
 * tune_engine.c — Tuning algorithm implementation
 *
 * Flow:
 *   1. Check NVS cache → hit? → direct position, report done
 *   2. Coarse sweep: 0°→180° at 5° steps, wait for SWR per step
 *   3. Fine sweep (if min SWR > 1.5): ±15° around best at 1° steps
 *   4. Lock best position, write NVS cache, report done/error
 */

#include "tune_engine.h"
#include "servo_ctrl.h"
#include "nvs_cache.h"
#include "protocol.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "tune_engine";

typedef enum {
    TUNE_PHASE_IDLE = 0,
    TUNE_PHASE_CACHE_CHECK,
    TUNE_PHASE_COARSE_SWEEP,
    TUNE_PHASE_FINE_SWEEP,
    TUNE_PHASE_DONE,
    TUNE_PHASE_ABORTED,
} tune_phase_t;

static tune_phase_t    phase = TUNE_PHASE_IDLE;
static atu_state_t    atu_state = ATU_IDLE;
static tune_event_cb_t event_cb = NULL;

// Tuning state
static uint32_t tune_freq_hz = 0;
static float    tune_initial_swr = 0;
static uint8_t  coarse_step = 0;
static uint8_t  fine_step = 0;
static uint8_t  best_pos = 0;
static float    best_swr = 999.0f;
static uint32_t tune_start_ms = 0;
static bool     swr_received = false;
static bool     swr_pending = false;
static float    last_swr = 999.0f;
static float    last_fwd_pwr = 0;

// Fine sweep range
static uint8_t  fine_center = 0;
static int8_t   fine_offset = 0;

void tune_engine_init(void) {
    phase = TUNE_PHASE_IDLE;
    atu_state = ATU_IDLE;
    ESP_LOGI(TAG, "Tune engine initialized");
}

void tune_engine_set_event_callback(tune_event_cb_t cb) {
    event_cb = cb;
}

atu_state_t tune_engine_get_state(void) {
    return atu_state;
}

uint8_t tune_engine_get_progress_pct(void) {
    if (phase == TUNE_PHASE_COARSE_SWEEP) {
        return (coarse_step * 100) / 36;
    } else if (phase == TUNE_PHASE_FINE_SWEEP) {
        return (fine_step * 100) / 30;
    }
    return 0;
}

void tune_engine_start(uint32_t freq_hz, float initial_swr) {
    tune_freq_hz = freq_hz;
    tune_initial_swr = initial_swr;
    coarse_step = 0;
    fine_step = 0;
    best_pos = 0;
    best_swr = 999.0f;
    swr_received = true;  // we have the initial SWR already
    swr_pending = false;
    last_swr = initial_swr;
    last_fwd_pwr = 0;
    tune_start_ms = xTaskGetTickCount() * portTICK_PERIOD_MS;

    servo_power_on();

    // Phase 1: Check NVS cache
    uint8_t cached_pos;
    if (nvs_cache_lookup(freq_hz, &cached_pos)) {
        ESP_LOGI(TAG, "Cache hit: %luHz → pos=%d", freq_hz, cached_pos);
        servo_set_angle(cached_pos);

        // Report success — MRRC will verify SWR and may re-trigger if stale
        phase = TUNE_PHASE_DONE;
        atu_state = ATU_LOCKED;
        tune_result_t r = {
            .success = true,
            .servo_pos = cached_pos,
            .best_swr = initial_swr,
            .elapsed_ms = xTaskGetTickCount() * portTICK_PERIOD_MS - tune_start_ms,
            .error = TUNE_OK
        };
        if (event_cb) {
            char *json = proto_build_tune_done(
                (r.servo_pos * 100) / 180, r.best_swr, r.elapsed_ms);
            if (json) { event_cb(json); free(json); }
        }
        servo_power_off();
        return;
    }

    // Phase 2: Coarse sweep
    ESP_LOGI(TAG, "Cache miss, starting coarse sweep: %luHz SWR=%.2f",
             freq_hz, initial_swr);
    phase = TUNE_PHASE_COARSE_SWEEP;
    atu_state = ATU_SWEEPING;
    servo_set_angle(0);
    best_swr = initial_swr;
    best_pos = 0;

    if (event_cb) {
        char *json = proto_build_tune_progress(0, 0, "sweeping");
        if (json) { event_cb(json); free(json); }
    }

    // Step to first coarse position (will be picked up by feed_swr loop)
    coarse_step = 0;
    swr_pending = true;  // Wait for MRRC to send swr_update
}

void tune_engine_feed_swr(float swr, float fwd_pwr_w) {
    if (phase != TUNE_PHASE_COARSE_SWEEP && phase != TUNE_PHASE_FINE_SWEEP) {
        return;
    }

    last_swr = swr;
    last_fwd_pwr = fwd_pwr_w;
    swr_received = true;
    swr_pending = false;

    // Check power safety
    if (fwd_pwr_w > TUNE_POWER_MAX_W) {
        ESP_LOGW(TAG, "Overpower during tune: %.1fW", fwd_pwr_w);
        phase = TUNE_PHASE_ABORTED;
        atu_state = ATU_ERROR;
        servo_set_angle(0);
        servo_power_off();
        if (event_cb) {
            char *json = proto_build_tune_error(TUNE_ERR_OVERPOWER);
            if (json) { event_cb(json); free(json); }
        }
        return;
    }
    if (fwd_pwr_w < TUNE_POWER_MIN_W) {
        ESP_LOGW(TAG, "RF lost during tune");
        phase = TUNE_PHASE_ABORTED;
        atu_state = ATU_ERROR;
        servo_set_angle(0);
        servo_power_off();
        if (event_cb) {
            char *json = proto_build_tune_error(TUNE_ERR_NORF);
            if (json) { event_cb(json); free(json); }
        }
        return;
    }

    // Record best
    if (swr < best_swr) {
        best_swr = swr;
        best_pos = servo_get_angle();
        if (swr < TUNE_EARLY_EXIT_SWR && phase == TUNE_PHASE_COARSE_SWEEP) {
            // Early exit from coarse sweep
            coarse_step = 36;  // force end of coarse loop
        }
    }

    // Advance to next step
    if (phase == TUNE_PHASE_COARSE_SWEEP) {
        coarse_step++;

        if (coarse_step >= 36) {
            // Coarse sweep complete
            if (best_swr > TUNE_FINE_THRESHOLD_SWR) {
                // Enter fine sweep
                ESP_LOGI(TAG, "Coarse done, best pos=%d SWR=%.2f → fine sweep", best_pos, best_swr);
                phase = TUNE_PHASE_FINE_SWEEP;
                atu_state = ATU_FINE_TUNING;
                fine_center = best_pos;
                fine_offset = -15;
                fine_step = 0;
                servo_set_angle(fine_center + fine_offset);
            } else {
                // Good enough
                phase = TUNE_PHASE_DONE;
                goto finish_tune;
            }
        } else {
            uint8_t next_pos = coarse_step * SERVO_COARSE_STEP_DEG;
            if (next_pos > 180) next_pos = 180;
            servo_set_angle(next_pos);

            if (event_cb) {
                char *json = proto_build_tune_progress(
                    (next_pos * 100) / 180, next_pos, "sweeping");
                if (json) { event_cb(json); free(json); }
            }
        }
        swr_pending = true;  // Wait for next SWR
    }
    else if (phase == TUNE_PHASE_FINE_SWEEP) {
        fine_step++;
        fine_offset = -15 + fine_step;

        if (fine_offset > 15 || fine_step >= 30) {
            // Fine sweep complete
            phase = TUNE_PHASE_DONE;
            goto finish_tune;
        } else {
            uint8_t next_pos = fine_center + fine_offset;
            if (next_pos > 180) next_pos = 180;
            servo_set_angle(next_pos);

            if (event_cb) {
                char *json = proto_build_tune_progress(
                    (next_pos * 100) / 180, next_pos, "fine_tuning");
                if (json) { event_cb(json); free(json); }
            }
        }
        swr_pending = true;
    }

    return;

finish_tune:
    {
        servo_set_angle(best_pos);
        atu_state = ATU_LOCKED;
        servo_power_off();

        uint32_t elapsed = xTaskGetTickCount() * portTICK_PERIOD_MS - tune_start_ms;

        if (best_swr < TUNE_MAX_ACCEPT_SWR) {
            nvs_cache_save(tune_freq_hz, best_pos);
            if (event_cb) {
                char *json = proto_build_tune_done(
                    (best_pos * 100) / 180, best_swr, elapsed);
                if (json) { event_cb(json); free(json); }
            }
        } else {
            ESP_LOGW(TAG, "Tune failed: best SWR=%.2f > %.1f", best_swr, TUNE_MAX_ACCEPT_SWR);
            if (event_cb) {
                char *json = proto_build_tune_error(TUNE_ERR_HIGHSWR);
                if (json) { event_cb(json); free(json); }
            }
        }
    }
}

void tune_engine_abort(void) {
    ESP_LOGI(TAG, "Tune aborted");
    phase = TUNE_PHASE_ABORTED;
    atu_state = ATU_IDLE;
    servo_set_angle(0);
    servo_power_off();
}

tune_result_t tune_engine_get_result(void) {
    tune_result_t r = {
        .success = (phase == TUNE_PHASE_DONE && best_swr < TUNE_MAX_ACCEPT_SWR),
        .servo_pos = best_pos,
        .best_swr = best_swr,
        .elapsed_ms = xTaskGetTickCount() * portTICK_PERIOD_MS - tune_start_ms,
        .error = TUNE_OK,
    };
    if (phase == TUNE_PHASE_ABORTED) r.error = TUNE_ERR_SERVO_STALL;
    if (best_swr >= TUNE_MAX_ACCEPT_SWR) r.error = TUNE_ERR_HIGHSWR;
    return r;
}

bool tune_engine_is_done(void) {
    return (phase == TUNE_PHASE_DONE || phase == TUNE_PHASE_ABORTED);
}

bool tune_engine_is_waiting_for_swr(void) {
    return swr_pending;
}
```

- [ ] **Step 3: Commit**

```bash
git add auto-efhw-tuner/firmware-esp32/main/tune_engine.h auto-efhw-tuner/firmware-esp32/main/tune_engine.c
git commit -m "feat: tune_engine — cache + coarse/fine servo sweep algorithm"
```

### Task 6: ws_client — WebSocket connection to MRRC

**Files:**
- Create: `auto-efhw-tuner/firmware-esp32/main/ws_client.h`
- Create: `auto-efhw-tuner/firmware-esp32/main/ws_client.c`

- [ ] **Step 1: Write ws_client.h**

```c
/*
 * ws_client.h — WebSocket client connecting ESP32-S3 ATU to MRRC server
 *
 * Responsibilities:
 *   - WiFi STA connection with auto-retry
 *   - WebSocket persistent connection to MRRC with ping/pong keep-alive
 *   - Receive JSON commands (tune_start, swr_update, tune_abort, etc.)
 *   - Send JSON events (tune_progress, tune_done, tune_error, etc.)
 */

#ifndef WS_CLIENT_H
#define WS_CLIENT_H

#include "atu_config.h"
#include <stdint.h>
#include <stdbool.h>

// Initialize WiFi and start WebSocket connection loop (runs as a FreeRTOS task)
void ws_client_task(void *pvParameters);

// Send a JSON string to MRRC (thread-safe, queued)
bool ws_client_send(const char *json_str);

// Get connection state
bool ws_client_is_connected(void);

#endif /* WS_CLIENT_H */
```

- [ ] **Step 2: Write ws_client.c**

```c
/*
 * ws_client.c — WebSocket client implementation
 *
 * WiFi STA → WebSocket to MRRC → JSON command dispatch → FreeRTOS queue
 */

#include "ws_client.h"
#include "tune_engine.h"
#include "protocol.h"
#include "health_mon.h"
#include "nvs_cache.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "esp_websocket_client.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "cJSON.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include <string.h>

static const char *TAG = "ws_client";
static esp_websocket_client_handle_t ws_handle = NULL;
static bool connected = false;
static QueueHandle_t send_queue = NULL;

// Forward declarations
static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data);
static void ws_event_handler(void *arg, esp_event_base_t event_base,
                             int32_t event_id, void *event_data);

// Structure for queued messages
typedef struct {
    char data[512];
} ws_msg_t;

void ws_client_task(void *pvParameters) {
    // Initialize NVS (for WiFi credentials)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES ||
        ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Initialize TCP/IP stack
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    // Create send queue
    send_queue = xQueueCreate(16, sizeof(ws_msg_t));

    // WiFi STA initialization
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, &instance_got_ip));

    // WiFi config from environment or compile defaults
    wifi_config_t wifi_config = {0};
    strncpy((char *)wifi_config.sta.ssid, CONFIG_ESP_WIFI_SSID,
            sizeof(wifi_config.sta.ssid) - 1);
    strncpy((char *)wifi_config.sta.password, CONFIG_ESP_WIFI_PASSWORD,
            sizeof(wifi_config.sta.password) - 1);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "WiFi STA started, connecting to SSID...");

    // Main loop: handle queued sends
    while (1) {
        ws_msg_t msg;
        if (xQueueReceive(send_queue, &msg, pdMS_TO_TICKS(100)) == pdTRUE) {
            if (ws_handle && connected) {
                esp_websocket_client_send_text(ws_handle, msg.data,
                                               strlen(msg.data), portMAX_DELAY);
            }
        }

        // Periodic status tick
        static uint32_t last_status = 0;
        uint32_t now = xTaskGetTickCount() * portTICK_PERIOD_MS;
        if (now - last_status >= 60000 && connected) {
            last_status = now;
            char *json = proto_build_status_report(
                servo_get_angle(),
                nvs_cache_get_hits(),
                health_get_state(),
                now / 1000);
            if (json) {
                esp_websocket_client_send_text(ws_handle, json, strlen(json),
                                               pdMS_TO_TICKS(1000));
                free(json);
            }
        }
    }
}

bool ws_client_send(const char *json_str) {
    if (!json_str || !send_queue) return false;
    ws_msg_t msg;
    strncpy(msg.data, json_str, sizeof(msg.data) - 1);
    msg.data[sizeof(msg.data) - 1] = '\0';
    return xQueueSend(send_queue, &msg, pdMS_TO_TICKS(1000)) == pdTRUE;
}

bool ws_client_is_connected(void) {
    return connected;
}

// ---- WiFi event handler ----

static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT &&
               event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "WiFi disconnected, reconnecting...");
        connected = false;
        vTaskDelay(pdMS_TO_TICKS(WIFI_RETRY_INTERVAL_MS));
        esp_wifi_connect();
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "WiFi connected, IP: " IPSTR, IP2STR(&event->ip_info.ip));
        connected = true;
        init_websocket();
    }
}

// ---- WebSocket client ----

static void init_websocket(void) {
    if (ws_handle) {
        esp_websocket_client_destroy(ws_handle);
        ws_handle = NULL;
    }

    esp_websocket_client_config_t ws_cfg = {
        .uri = MRRC_WS_URL_DEFAULT,
        .reconnect_timeout_ms = MRRC_WS_RECONNECT_MS,
        .ping_interval_sec = MRRC_WS_PING_INTERVAL_S,
        .disable_auto_reconnect = false,
        .keep_alive_enable = true,
        .task_stack = 4096,
        .task_prio = 5,
    };

    ws_handle = esp_websocket_client_init(&ws_cfg);

    esp_websocket_register_events(ws_handle, WEBSOCKET_EVENT_ANY,
                                   ws_event_handler, NULL);
    esp_websocket_client_start(ws_handle);
}

static void ws_event_handler(void *arg, esp_event_base_t event_base,
                             int32_t event_id, void *event_data) {
    esp_websocket_event_data_t *data = (esp_websocket_event_data_t *)event_data;

    switch (event_id) {
    case WEBSOCKET_EVENT_CONNECTED:
        ESP_LOGI(TAG, "WebSocket connected to MRRC");
        connected = true;
        break;

    case WEBSOCKET_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "WebSocket disconnected");
        connected = false;
        break;

    case WEBSOCKET_EVENT_DATA:
        // Parse incoming JSON command
        if (data->data_ptr && data->data_len < 512) {
            char buf[512];
            memcpy(buf, data->data_ptr, data->data_len);
            buf[data->data_len] = '\0';
            process_incoming(buf);
        }
        break;

    case WEBSOCKET_EVENT_ERROR:
        ESP_LOGE(TAG, "WebSocket error");
        connected = false;
        break;
    }
}

static void process_incoming(const char *json_str) {
    cJSON *root = cJSON_Parse(json_str);
    if (!root) return;

    cJSON *cmd = cJSON_GetObjectItem(root, "cmd");
    if (!cmd || !cmd->valuestring) {
        cJSON_Delete(root);
        return;
    }

    if (strcmp(cmd->valuestring, "tune_start") == 0) {
        cmd_tune_start_t ts = proto_parse_tune_start(json_str);
        if (ts.freq_hz > 0) {
            tune_engine_start(ts.freq_hz, ts.swr);
        }
    }
    else if (strcmp(cmd->valuestring, "swr_update") == 0) {
        cmd_swr_update_t su = proto_parse_swr_update(json_str);
        tune_engine_feed_swr(su.swr, su.fwd_pwr_w);
    }
    else if (strcmp(cmd->valuestring, "tune_abort") == 0) {
        tune_engine_abort();
    }
    else if (strcmp(cmd->valuestring, "set_bypass") == 0) {
        servo_power_on();
        servo_set_angle(0);
        servo_power_off();
    }
    else if (strcmp(cmd->valuestring, "get_status") == 0) {
        char *json = proto_build_status_report(
            servo_get_angle(), nvs_cache_get_hits(),
            health_get_state(), xTaskGetTickCount() * portTICK_PERIOD_MS / 1000);
        if (json) {
            ws_client_send(json);
            free(json);
        }
    }

    cJSON_Delete(root);
}
```

- [ ] **Step 3: Commit**

```bash
git add auto-efhw-tuner/firmware-esp32/main/ws_client.h auto-efhw-tuner/firmware-esp32/main/ws_client.c
git commit -m "feat: ws_client — WebSocket client with WiFi + JSON command dispatch"
```

### Task 7: health_mon — Health monitor & watchdog

**Files:**
- Create: `auto-efhw-tuner/firmware-esp32/main/health_mon.h`
- Create: `auto-efhw-tuner/firmware-esp32/main/health_mon.c`

- [ ] **Step 1: Write health_mon.h**

```c
/*
 * health_mon.h — Periodic health checks (Bias-T voltage, core temp, WDT)
 */

#ifndef HEALTH_MON_H
#define HEALTH_MON_H

#include "atu_config.h"
#include <stdbool.h>

// Initialize health monitor
void health_mon_init(void);

// Run health check cycle (called every 10s)
void health_mon_tick(void);

// Get current health state
sys_health_t health_get_state(void);

// Get last Bias-T voltage reading
float health_get_bias_voltage(void);

#endif /* HEALTH_MON_H */
```

- [ ] **Step 2: Write health_mon.c**

```c
/*
 * health_mon.c — Health monitor implementation
 */

#include "health_mon.h"
#include "servo_ctrl.h"
#include "protocol.h"
#include "ws_client.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_log.h"
#include "driver/temperature_sensor.h"

static const char *TAG = "health";
static sys_health_t health = SYS_HEALTHY;
static float bias_voltage = 0;
static adc_oneshot_unit_handle_t adc_handle = NULL;
static adc_cali_handle_t adc_cali = NULL;
static temperature_sensor_handle_t temp_sensor = NULL;

void health_mon_init(void) {
    // ADC for Bias-T voltage monitoring
    adc_oneshot_unit_init_cfg_t adc_cfg = {
        .unit_id = ADC_UNIT_1,
        .ulp_mode = ADC_ULP_MODE_DISABLE,
    };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&adc_cfg, &adc_handle));

    adc_oneshot_chan_cfg_t chan_cfg = {
        .atten = ADC_BIAS_V_ATTEN,
        .bitwidth = ADC_BITWIDTH_12,
    };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc_handle, ADC_BIAS_V_CHANNEL, &chan_cfg));

    // ADC calibration
    adc_cali_line_fitting_config_t cali_cfg = {
        .unit_id = ADC_UNIT_1,
        .atten = ADC_BIAS_V_ATTEN,
        .bitwidth = ADC_BITWIDTH_12,
    };
    ESP_ERROR_CHECK(adc_cali_create_scheme_line_fitting(&cali_cfg, &adc_cali));

    // Temperature sensor
    temperature_sensor_config_t temp_cfg = TEMPERATURE_SENSOR_CONFIG_DEFAULT(-10, 80);
    ESP_ERROR_CHECK(temperature_sensor_install(&temp_cfg, &temp_sensor));
    ESP_ERROR_CHECK(temperature_sensor_enable(temp_sensor));

    ESP_LOGI(TAG, "Health monitor initialized (ADC + temp sensor)");
}

void health_mon_tick(void) {
    bool degraded = false;

    // Read Bias-T voltage
    int raw_adc;
    ESP_ERROR_CHECK(adc_oneshot_read(adc_handle, ADC_BIAS_V_CHANNEL, &raw_adc));
    int voltage_mv;
    ESP_ERROR_CHECK(adc_cali_raw_to_voltage(adc_cali, raw_adc, &voltage_mv));
    bias_voltage = (float)voltage_mv * ADC_BIAS_V_DIVIDER / 1000.0f;

    if (bias_voltage < BIAS_V_MIN || bias_voltage > BIAS_V_MAX) {
        ESP_LOGW(TAG, "Bias voltage out of range: %.1fV", bias_voltage);
        degraded = true;
        if (event_cb) {
            char msg[64];
            snprintf(msg, sizeof(msg), "DC under-voltage" :
                     "DC over-voltage");
            char *json = proto_build_health_alert(1, bias_voltage, msg);
            if (json) { ws_client_send(json); free(json); }
        }
    }

    // Read core temperature
    float temp_c;
    ESP_ERROR_CHECK(temperature_sensor_get_celsius(temp_sensor, &temp_c));
    if (temp_c > CORE_TEMP_MAX_C) {
        ESP_LOGW(TAG, "Core temp high: %.1f°C", temp_c);
        degraded = true;
    }

    // Update health FSM
    if (degraded && health == SYS_HEALTHY) {
        health = SYS_DEGRADED;
    } else if (!degraded && health == SYS_DEGRADED) {
        health = SYS_HEALTHY;
    }
}

sys_health_t health_get_state(void) {
    return health;
}

float health_get_bias_voltage(void) {
    return bias_voltage;
}
```

- [ ] **Step 3: Commit**

```bash
git add auto-efhw-tuner/firmware-esp32/main/health_mon.h auto-efhw-tuner/firmware-esp32/main/health_mon.c
git commit -m "feat: health_mon — Bias-T voltage + core temp + health FSM"
```

### Task 8: atu_main.c — Main entry point with FreeRTOS tasks + protocol.c implementation

**Files:**
- Create: `auto-efhw-tuner/firmware-esp32/main/atu_main.c`
- Create: `auto-efhw-tuner/firmware-esp32/main/protocol.c`

- [ ] **Step 1: Write protocol.c (JSON parsing/building implementations)**

```c
/*
 * protocol.c — JSON protocol parsing and building implementations
 */

#include "protocol.h"
#include "atu_config.h"
#include "cJSON.h"
#include <stdio.h>
#include <string.h>

cmd_tune_start_t proto_parse_tune_start(const char *json) {
    cmd_tune_start_t result = {0};
    cJSON *root = cJSON_Parse(json);
    if (!root) return result;

    cJSON *f = cJSON_GetObjectItem(root, "freq_hz");
    cJSON *s = cJSON_GetObjectItem(root, "swr");
    cJSON *p = cJSON_GetObjectItem(root, "fwd_pwr_w");

    if (cJSON_IsNumber(f)) result.freq_hz = (uint32_t)f->valuedouble;
    if (cJSON_IsNumber(s)) result.swr = (float)s->valuedouble;
    if (cJSON_IsNumber(p)) result.fwd_pwr_w = (float)p->valuedouble;

    cJSON_Delete(root);
    return result;
}

cmd_swr_update_t proto_parse_swr_update(const char *json) {
    cmd_swr_update_t result = {0};
    cJSON *root = cJSON_Parse(json);
    if (!root) return result;

    cJSON *s = cJSON_GetObjectItem(root, "swr");
    cJSON *p = cJSON_GetObjectItem(root, "fwd_pwr_w");

    if (cJSON_IsNumber(s)) result.swr = (float)s->valuedouble;
    if (cJSON_IsNumber(p)) result.fwd_pwr_w = (float)p->valuedouble;

    cJSON_Delete(root);
    return result;
}

char *proto_build_tune_progress(uint8_t cap_pct, uint8_t servo_pos, const char *state) {
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "evt", "tune_progress");
    cJSON_AddNumberToObject(root, "cap_pct", cap_pct);
    cJSON_AddNumberToObject(root, "servo_pos", servo_pos);
    cJSON_AddStringToObject(root, "state", state);
    char *out = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    return out;
}

char *proto_build_tune_done(uint8_t cap_pct, float swr_final, uint32_t elapsed_ms) {
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "evt", "tune_done");
    cJSON_AddNumberToObject(root, "cap_pct", cap_pct);
    cJSON_AddNumberToObject(root, "swr_final", swr_final);
    cJSON_AddNumberToObject(root, "elapsed_ms", elapsed_ms);
    char *out = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    return out;
}

char *proto_build_tune_error(tune_error_t error) {
    const char *msgs[] = {
        [TUNE_OK] = "ok",
        [TUNE_ERR_OVERPOWER] = "overpower",
        [TUNE_ERR_NORF] = "no_rf",
        [TUNE_ERR_HIGHSWR] = "no_match",
        [TUNE_ERR_SERVO_STALL] = "servo_stall",
        [TUNE_ERR_TIMEOUT] = "timeout",
        [TUNE_ERR_WS_DISCONNECT] = "ws_disconnect",
    };
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "evt", "tune_error");
    cJSON_AddNumberToObject(root, "code", error);
    cJSON_AddStringToObject(root, "message",
        (error < sizeof(msgs)/sizeof(msgs[0])) ? msgs[error] : "unknown");
    char *out = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    return out;
}

char *proto_build_status_report(uint8_t pos, uint32_t cache_hits,
                                sys_health_t health, uint32_t uptime) {
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "evt", "status_report");
    cJSON_AddNumberToObject(root, "pos", pos);
    cJSON_AddNumberToObject(root, "cache_hits", cache_hits);
    cJSON_AddNumberToObject(root, "health", health);
    cJSON_AddNumberToObject(root, "uptime", uptime);
    char *out = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    return out;
}

char *proto_build_health_alert(uint8_t code, float value, const char *message) {
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "evt", "health_alert");
    cJSON_AddNumberToObject(root, "code", code);
    cJSON_AddNumberToObject(root, "value", value);
    cJSON_AddStringToObject(root, "message", message);
    char *out = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    return out;
}
```

- [ ] **Step 2: Write atu_main.c**

```c
/*
 * atu_main.c — Fuchs ATU V3.0 main entry point
 *
 * Creates FreeRTOS tasks:
 *   ws_client_task     (pri 3) — WiFi + WebSocket
 *   tune_engine_task   (pri 2) — Tune control loop
 *   health_mon_task    (pri 1) — Periodic health checks
 */

#include "atu_config.h"
#include "ws_client.h"
#include "tune_engine.h"
#include "servo_ctrl.h"
#include "health_mon.h"
#include "nvs_cache.h"
#include "protocol.h"
#include "esp_log.h"
#include "esp_task_wdt.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "main";

// Stack sizes
#define WS_TASK_STACK       8192
#define TUNE_TASK_STACK     4096
#define HEALTH_TASK_STACK   3072

// === Tune Engine Task ===
// Handles the tune state machine; steps the servo when SWR arrives

static void tune_event_handler(const char *json_str) {
    ws_client_send(json_str);
}

static void tune_engine_task(void *pvParameters) {
    ESP_LOGI(TAG, "Tune engine task started");

    tune_engine_init();
    tune_engine_set_event_callback(tune_event_handler);

    // This task is event-driven via tune_engine_feed_swr() called from
    // the ws_client task when swr_update commands arrive.
    // It sleeps most of the time, woken by FreeRTOS notifications.

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

// === Health Monitor Task ===

static void health_mon_task(void *pvParameters) {
    ESP_LOGI(TAG, "Health monitor task started");
    health_mon_init();

    while (1) {
        health_mon_tick();
        vTaskDelay(pdMS_TO_TICKS(HEALTH_CHECK_INTERVAL_MS));
    }
}

// === LED & Buzzer Init ===

static void indicators_init(void) {
    gpio_config_t led_cfg = {
        .pin_bit_mask = (1ULL << PIN_STATUS_LED),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&led_cfg));
    gpio_set_level(PIN_STATUS_LED, 0);

    gpio_config_t buzzer_cfg = {
        .pin_bit_mask = (1ULL << PIN_BUZZER),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&buzzer_cfg));
    gpio_set_level(PIN_BUZZER, 0);
}

// === Buzzer beep ===
static void buzzer_beep(uint8_t count) {
    for (uint8_t i = 0; i < count; i++) {
        gpio_set_level(PIN_BUZZER, 1);
        vTaskDelay(pdMS_TO_TICKS(80));
        gpio_set_level(PIN_BUZZER, 0);
        if (i < count - 1) vTaskDelay(pdMS_TO_TICKS(120));
    }
}

// === app_main ===

void app_main(void) {
    ESP_LOGI(TAG, "=== Fuchs ATU V3.0 (ESP32-S3) ===");
    ESP_LOGI(TAG, "Firmware built: %s %s", __DATE__, __TIME__);

    // Initialize hardware
    indicators_init();
    servo_init();
    buzzer_beep(1);

    // Initialize NVS tune cache
    if (!nvs_cache_init()) {
        ESP_LOGE(TAG, "NVS cache init failed — continuing without cache");
    }

    // Register with task watchdog
    ESP_ERROR_CHECK(esp_task_wdt_init(5, true));

    // Create tasks
    xTaskCreate(ws_client_task, "ws_client",
                WS_TASK_STACK, NULL, 3, NULL);
    xTaskCreate(tune_engine_task, "tune_engine",
                TUNE_TASK_STACK, NULL, 2, NULL);
    xTaskCreate(health_mon_task, "health_mon",
                HEALTH_TASK_STACK, NULL, 1, NULL);

    ESP_LOGI(TAG, "All tasks started. Waiting for WiFi + WebSocket connection...");

    // Main loop: LED heartbeat
    while (1) {
        bool ws_ok = ws_client_is_connected();
        gpio_set_level(PIN_STATUS_LED, ws_ok ? 1 : 0);

        // Blink pattern on disconnect: fast blink
        if (!ws_ok) {
            for (int i = 0; i < 3; i++) {
                gpio_set_level(PIN_STATUS_LED, 1);
                vTaskDelay(pdMS_TO_TICKS(200));
                gpio_set_level(PIN_STATUS_LED, 0);
                vTaskDelay(pdMS_TO_TICKS(200));
            }
        }

        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add auto-efhw-tuner/firmware-esp32/main/atu_main.c auto-efhw-tuner/firmware-esp32/main/protocol.c
git commit -m "feat: atu_main — FreeRTOS task creation + protocol JSON parsers"
```

- [ ] **Step 4: Add cJSON as a component**

cJSON is used for JSON parsing. Easiest approach: add it as a submodule or vendor copy.

```bash
cd auto-efhw-tuner/firmware-esp32
mkdir -p components
cd components
git submodule add https://github.com/DaveGamble/cJSON.git
cd cJSON
# Use a known stable tag
git checkout v1.7.18
```

Create `components/cJSON/CMakeLists.txt`:

```cmake
idf_component_register(
    SRCS "cJSON.c"
    INCLUDE_DIRS "."
)
```

- [ ] **Step 5: Commit**

```bash
git add auto-efhw-tuner/firmware-esp32/components/
git commit -m "feat: add cJSON v1.7.18 as ESP-IDF component"
```

---

## Phase 3: Hardware documentation update

### Task 9: BOM V3.0 — New bill of materials

**Files:**
- Rename: `auto-efhw-tuner/hardware/EFHW_TUNER_BOM_STM32.csv` → `auto-efhw-tuner/hardware/EFHW_TUNER_BOM_STM32.csv` (keep as reference)
- Create: `auto-efhw-tuner/hardware/EFHW_TUNER_BOM_FUCHS.csv`

- [ ] **Step 1: Write V3.0 Fuchs BOM**

```csv
编号,分类,器件名,规格/型号,值,封装,数量,单价CNY,总价CNY,备注

=== MCU 与核心 IC (V3.0 ESP32-S3) ===
U1,MCU模块,ESP32-S3-WROOM-1,Xtensa LX7 双核 240MHz 16MB Flash,,SMD 模组,1,25.0,25.0,
U2,12V LDO,LM2940CT-12,LDO 压差0.5V 1A,,TO-220,1,5.0,5.0,
U3,3.3V LDO,AMS1117-3.3,LDO 1A,,SOT-223,1,1.0,1.0,
U4,DC-DC,LM2596模块,12V→6V 3A 伺服供电,,模块,1,8.0,8.0,

=== 二极管 ===
D1,防反二极管,1N4007,1000V 1A,,DO-41,1,0.2,0.2,

=== RF 链 (V3.0 Fuchs) ===
T1,磁芯,T200-6,Type 6 羰基铁粉 μ=8 OD=50.8mm,,Amidon,1,30.0,30.0,单只足够 100W
,漆包线,0.8mm+0.5mm 聚氨酯,初级2T+次级14T,,,~3m,3.0,3.0,
C_var,可变电容,空气介质 10-500pF,耐压≥1kV,,拆机/国产,1,35.0,35.0,
SERVO,舵机,MG996R,金属齿轮 6V 10kg·cm,,模块,1,18.0,18.0,

=== Bias-T 扼流 (不变) ===
L_bias,RF扼流圈,FT37-43绕15T,~95µH,,TH,1,3.0,3.0,

=== 保护与连接器 (不变) ===
GDT1,气体放电管,90V DC击穿 ≥5kA 8/20µs,,径向,1,8.0,8.0,
R_bleed,高压电阻,2.2MΩ 2W 3KV 金属釉膜无感,,轴向,1,3.0,3.0,
J1,M座,SO-239 法兰 PTFE绝缘,,面板,1,8.0,8.0,
J2-J3,不锈钢螺栓,M5 304不锈钢+PTFE垫片+螺母,,面板,2套,5.0,10.0,
LED1,指示灯,WS2812B或普通3mm LED+1kΩ,,TH,1,1.0,1.0,
BZ1,蜂鸣器,5V有源蜂鸣器(经NPN驱动),,TH,1,1.0,1.0,

=== 隔直 (不变) ===
C_block1-2,隔直电容,10nF 1KV C0G,并联降ESR/ESL,1206,2,2.5,5.0,

=== MOSFET 与 BJT (V3.0 新增) ===
Q1,P-MOSFET,IRF9540,伺服6V供电开关,,TO-220,1,2.0,2.0,替代F5NPV继电器
Q2,NPN,2N2222A,MOSFET栅极驱动,,TO-92,1,1.0,1.0,
R_gate,栅极电阻,10kΩ 0805,MOSFET栅极下拉,,0805,1,0.1,0.1,

=== 分压与滤波 (V3.0 简化) ===
R_bias_div1,分压电阻,47kΩ 1%,Bias-V监测上拉,,0805,1,0.1,0.1,
R_bias_div2,分压电阻,10kΩ 1%,Bias-V监测下拉,,0805,1,0.1,0.1,
,其他R/C,0805电阻电容+接插件 ~10件,去耦/滤波/偏置,,~10,10.0,10.0,

=== 壳体与辅料 (不变) ===
,压铸铝盒,IP66 160×110×70mm,,,1,35.0,35.0,
PCB,PCB打样,140×50mm FR4 双面 1.6mm 绿油,5片,嘉立创,5,3.0,15.0,
,三防漆+齿轮组+螺丝+防水接头,,,1批,30.0,30.0,

=============================================================
总计 (单套),,,,,≈255.0,CNY,
```

- [ ] **Step 2: Commit**

```bash
git add auto-efhw-tuner/hardware/EFHW_TUNER_BOM_FUCHS.csv
git commit -m "docs: V3.0 Fuchs ATU BOM — ¥255 (35% cheaper than V2.0)"
```

### Task 10: SCH description V3.0 — Schematic rewrite for Fuchs topology

**Files:**
- Modify: `auto-efhw-tuner/hardware/SCH_Description.md`

- [ ] **Step 1: Rewrite SCH_Description.md**

Replace the entire file with the V3.0 schematic description. Key changes vs V2.0:

1. **Sheet 1 (POWER)**: Remove ULN2003A — no relay driver needed. Add LM2596 12V→6V DC-DC for servo. Keep LM2940 + AMS1117 chain.
2. **Sheet 2 (MCU)**: Replace Bluepill/DIP-40 with ESP32-S3-WROOM-1 SMD module. New pin map: GPIO1=PWM, GPIO2=servo power cut, GPIO5=Bias-V ADC, GPIO6=LED, GPIO7=buzzer. Remove all relay control pins (PA8-PA14, PB3-PB4) and SWR bridge ADC pins (PA0/PA1). No SWD — ESP32-S3 uses built-in USB Serial/JTAG.
3. **Sheet 3**: DELETE — no SWR bridge. SWR comes from MRRC ATR1000.
4. **Sheet 4**: DELETE — no relay drive section.
5. **Sheet 5 (HV_TANK)**: Replace T200-2B×2 + 7×G5Q-14 + 10×1812 MLCC with T200-6×1 + air variable capacitor 10-500pF + MG996R servo.
6. **Sheet 6 (PROTECTION)**: Same as V2.0 — GDT + bleed resistor.

```
V3.0 Schematic hierarchy:
├── Sheet 1/4: POWER — Bias-T extraction + 12V LDO + 6V DC-DC + 3.3V LDO
├── Sheet 2/4: MCU — ESP32-S3-WROOM-1 + USB/JTAG + Bias-V ADC
├── Sheet 3/4: HV_TANK — T200-6 2:14 + Air variable cap + MG996R servo + MOSFET power-cut
└── Sheet 4/4: PROTECTION — 90V GDT + 2.2MΩ bleed + antenna terminals
```

The full rewrite (~200 lines) follows the same document structure as the existing SCH_Description.md but with V3.0 content.

- [ ] **Step 2: Commit**

```bash
git add auto-efhw-tuner/hardware/SCH_Description.md
git commit -m "docs: SCH V3.0 — Fuchs topology, ESP32-S3, no SWR bridge, 4 sheets"
```

### Task 11: PCB description V3.0 — Layout rewrite for smaller board

**Files:**
- Modify: `auto-efhw-tuner/hardware/PCB_Description.md`

- [ ] **Step 1: Rewrite PCB_Description.md**

Key changes:
- Board size: **140×50mm** (was 140×90mm). 40mm shorter — no relay zone.
- **No B区/HV isolation slot** needed anymore. The servo is low-voltage, and the variable capacitor is mechanically isolated from the PCB. RF high-voltage path is point-to-point wiring (SO-239 → T200-6 → variable cap → ANT terminal), not on PCB traces.
- Single continuous ground plane (no A/B split).
- Component layout: ESP32-S3 center, power supply left, connectors right.
- T200-6 is chassis-mounted with nylon ties, not on PCB.
- Variable cap and servo are chassis-mounted, connected to PCB via 3-pin servo header + RF wire.
- PCB is essentially a control + power supply board only.

New layout:
```
        140.00 mm
   ┌──────────────────────────────────┐  ↑
   │  H1(5,5)              H2(135,5)  │  │
   │  ┌────────────────────────────┐  │  │
   │  │  ESP32-S3-WROOM-1          │  │  │
   │  │  (center X=70 Y=25)        │  │  │
   │  │                            │  │  │
   │  │  [LM2940] [LM2596]        │  │  │
   │  │  [AMS1117] [IRF9540]      │  │  │
   │  │  [3-pin Servo Header]     │  │  │
   │  │  [SO-239 PCB mount]       │50.0mm
   │  │  [Bias-V ADC divider]     │  │  │
   │  │  [GDT pads] [LED] [BZR]  │  │  │
   │  └────────────────────────────┘  │  │
   │  H3(5,45)            H4(135,45)  │  │
   └──────────────────────────────────┘  ↓

T200-6 toroid: chassis-mounted off-board
Variable capacitor: chassis-mounted off-board
MG996R servo: chassis-mounted, gear-coupled to cap
```

- [ ] **Step 2: Commit**

```bash
git add auto-efhw-tuner/hardware/PCB_Description.md
git commit -m "docs: PCB V3.0 — 140×50mm control board, no HV isolation needed"
```

---

## Phase 4: Software documentation (SDD + FDE)

### Task 12: SDD V3.0 — Software Design Description rewrite

**Files:**
- Modify: `auto-efhw-tuner/docs/SDD.md`

- [ ] **Step 1: Rewrite SDD.md**

Full rewrite following the same 14-chapter IBM TeamSD format as V2.0, but with V3.0 content:

| Chapter | Key V3.0 Changes |
|---|---|
| 1. Executive Summary | ESP32-S3 240MHz dual-core, Fuchs topology, MRRC WebSocket integration |
| 2. Business Direction | Same personas, updated competitive differentiation (continuous tuning vs stepped) |
| 3. Project Definition | M5-M7 updated: M5=2026-06-08 ESP32 firmware, M6=TBD PCB fab, M7=TBD field test |
| 4. System Context | New context diagram: ATR1000→MRRC→WiFi→ATU. No onboard SWR bridge. |
| 5. Non-Functional Requirements | Tune time: ~8s (coarse 36×80ms + fine 30×80ms). WiFi reconnect < 10s. |
| 6. Use Case Model | UC-001 Auto-Tune via MRRC, UC-002 Cache Hit sub-second, UC-003 WiFi Lost graceful, UC-004 OTA Update, UC-005 Health Monitor |
| 7. Subject Area Model | Entities: TuneCache (NVS), ServoState, WSConnection, HealthFsm. Remove SWR bridge entities. |
| 8. Architecture Decisions | AD-001 ESP32-S3, AD-002 Fuchs topology, AD-003 No local SWR (ATR1000), AD-004 T200-6 single core, AD-005 Servo continuous vs relay stepped |
| 9. Architecture Overview | 4 FreeRTOS tasks: ws_client (pri3), tune_engine (pri2), servo_ctrl (pri2), health_mon (pri1) |
| 10. Service Model | ws_client, tune_engine, servo_ctrl, nvs_cache, health_mon interfaces |
| 11. Component Model | End-to-end sequence: Browser→MRRC→ATR1000→MRRC→WiFi→ATU→Servo |
| 12. Operational Model | Outdoor IP66, WiFi range to router, OTA dual-slot |
| 13. Feasibility | ESP32-S3 flash 16MB (~1.2MB used), RAM 512KB (~80KB used) |
| 14. Version History | V3.0 entry |

~500 line complete rewrite.

- [ ] **Step 2: Commit**

```bash
git add auto-efhw-tuner/docs/SDD.md
git commit -m "docs: SDD V3.0 — ESP32-S3 Fuchs ATU, 14 chapters, MRRC integrated"
```

### Task 13: FDE V3.0 — Fault Detection & Engineering rewrite

**Files:**
- Modify: `auto-efhw-tuner/docs/FDE.md`

- [ ] **Step 1: Rewrite FDE.md**

Key V3.0 fault model changes vs V2.0:

| V2.0 Fault | V3.0 Equivalent |
|---|---|
| Relay stuck (7× G5Q-14) | **Servo stall** (MG996R gear jam, limit switch fail) |
| ADC stuck (BAT41/SWR bridge) | **N/A** (no local SWR sensing) |
| Flash write failure (STM32 page) | **NVS write failure** (ESP32 Flash partition) |
| ULN2003A overheat | **LM2596 overheat** (DC-DC for servo) |
| Bias-T under/over voltage | Same (retained) |
| WDT reset (STM32 IWDG) | **ESP32-S3 WDT** (Task WDT + RTC WDT) |
| — (new) | **WiFi disconnect → tune abort** |
| — (new) | **WS timeout during tune → servo safe position** |
| — (new) | **Core temperature >80°C → disable tune** |

POST phases simplified: DC check → WiFi init → Servo range check → NVS check (no relay or SWR bridge phases).

~300 line rewrite of fault catalog, FMEA, degradation strategies, and fault injection test cases.

- [ ] **Step 2: Commit**

```bash
git add auto-efhw-tuner/docs/FDE.md
git commit -m "docs: FDE V3.0 — servo/MOSFET/WiFi fault model, 3-phase POST"
```

---

## Phase 5: MRRC integration (WebSocket handler + Web UI)

### Task 14: atu_fuchs_handler.py — MRRC WebSocket handler for ATU

**Files:**
- Create: `/Users/cheenle/UHRR/MRRC/atu_fuchs_handler.py`

- [ ] **Step 1: Write atu_fuchs_handler.py**

```python
"""
atu_fuchs_handler.py — Fuchs ATU WebSocket Handler for MRRC Server

Provides a dedicated WebSocket endpoint (/atu) that:
1. Accepts ESP32-S3 ATU connections
2. Relays commands between browser UI and ATU
3. Bridges ATR1000 SWR readings to ATU during tuning
"""

import json
import time
import logging
from tornado.websocket import WebSocketHandler

logger = logging.getLogger("fuchs_atu")


class FuchsATUHandler(WebSocketHandler):
    """WebSocket handler for ESP32-S3 Fuchs ATU."""

    atu_connection = None  # The ESP32-S3 ATU
    browser_connections = set()  # UI clients
    active_tune = None  # Current tune session state

    def check_origin(self, origin):
        return True  # Allow all origins on LAN

    def open(self):
        # Identify connection type by query param or first message
        logger.info(f"ATU WS connection from {self.request.remote_ip}")

    def on_message(self, message):
        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON: {message[:100]}")
            return

        # Determine connection role
        if "evt" in msg:
            # This is an ATU → MRRC event, forward to browsers
            FuchsATUHandler._broadcast_to_browsers(msg)
            self._handle_atu_event(msg)
        elif "cmd" in msg:
            # This is a browser → MRRC command
            self._handle_browser_command(msg)
        else:
            logger.warning(f"Unknown message format: {msg}")

    def on_close(self):
        if self is FuchsATUHandler.atu_connection:
            logger.info("ATU ESP32-S3 disconnected")
            FuchsATUHandler.atu_connection = None
        else:
            FuchsATUHandler.browser_connections.discard(self)

    # === ATU Event Handlers ===

    def _handle_atu_event(self, msg):
        evt = msg.get("evt")

        if evt == "tune_progress":
            # ATU moved servo, need new SWR from ATR1000
            FuchsATUHandler.active_tune = {
                "state": msg.get("state"),
                "servo_pos": msg.get("servo_pos"),
                "waiting_for_swr": True,
            }
            self._request_swr_from_atr1000()

        elif evt == "tune_done":
            FuchsATUHandler.active_tune = None
            logger.info(f"Tune complete: SWR={msg.get('swr_final')}")

        elif evt in ("tune_error", "health_alert", "status_report"):
            pass  # Forwarded to browsers already

    # === Browser Command Handlers ===

    def _handle_browser_command(self, msg):
        cmd = msg.get("cmd")

        if FuchsATUHandler.atu_connection is None:
            self.write_message(json.dumps({
                "evt": "error",
                "message": "ATU not connected"
            }))
            return

        # Forward command to ATU
        if cmd == "tune_start":
            # Enhance with current SWR from ATR1000
            swr_data = self._read_atr1000_swr()
            if swr_data:
                msg["swr"] = swr_data["swr"]
                msg["fwd_pwr_w"] = swr_data["fwd_pwr_w"]

        FuchsATUHandler.atu_connection.write_message(json.dumps(msg))

    # === ATR1000 Integration ===

    def _read_atr1000_swr(self):
        """Read SWR from ATR1000 via MRRC's existing interface."""
        try:
            # Use existing MRRC ATR1000 API
            from atr1000_tuner import get_atr1000_reading
            data = get_atr1000_reading()
            if data:
                return {"swr": data.swr, "fwd_pwr_w": data.fwd_pwr}
        except ImportError:
            logger.warning("ATR1000 module not available")
        except Exception as e:
            logger.error(f"ATR1000 read error: {e}")
        return None

    def _request_swr_from_atr1000(self):
        """Request SWR reading and forward to ATU."""
        swr_data = self._read_atr1000_swr()
        if swr_data and FuchsATUHandler.atu_connection:
            FuchsATUHandler.atu_connection.write_message(json.dumps({
                "cmd": "swr_update",
                "swr": swr_data["swr"],
                "fwd_pwr_w": swr_data["fwd_pwr_w"],
            }))

    @classmethod
    def _broadcast_to_browsers(cls, msg):
        """Forward ATU events to all connected browser clients."""
        for browser in list(cls.browser_connections):
            try:
                browser.write_message(json.dumps(msg))
            except Exception:
                cls.browser_connections.discard(browser)


def register_fuchs_atu(app):
    """Register Fuchs ATU WebSocket endpoint with Tornado app."""
    app.add_handlers(r".*", [
        (r"/atu", FuchsATUHandler),
    ])
    logger.info("Fuchs ATU WebSocket endpoint registered at /atu")
```

- [ ] **Step 2: Commit (in MRRC repo or note integration point)**

```bash
git add atu_fuchs_handler.py
git commit -m "feat: Fuchs ATU WebSocket handler — /atu endpoint, ATR1000 bridge"
```

### Task 15: Web UI — ATU sub-panel in index.html

**Files:**
- Modify: `/Users/cheenle/UHRR/MRRC/www/index.html`
- Modify: `/Users/cheenle/UHRR/MRRC/www/controls.js`

- [ ] **Step 1: Add ATU panel HTML to index.html**

Insert into the main control area, after the mode selector section:

```html
<!-- Fuchs ATU Panel -->
<div id="atu-panel" class="control-group">
    <h3>ATU (Fuchs)</h3>
    <div id="atu-status-bar">
        <span id="atu-connection" class="status-dot disconnected"></span>
        <span id="atu-state-label">Disconnected</span>
    </div>

    <div id="atu-servo-display">
        <label>Servo: <span id="atu-servo-pos">--</span>°</label>
        <div id="atu-servo-bar-outer">
            <div id="atu-servo-bar-inner" style="width: 0%;"></div>
        </div>
    </div>

    <div id="atu-swr-display">
        <label>SWR: <span id="atu-swr-value">--</span></label>
        <span id="atu-swr-indicator"></span>
    </div>

    <div id="atu-buttons">
        <button id="atu-tune-btn" class="btn-primary" onclick="fuchsATU.startTune()">
            Auto Tune
        </button>
        <button id="atu-bypass-btn" class="btn-secondary" onclick="fuchsATU.setBypass()">
            Bypass
        </button>
        <button id="atu-abort-btn" class="btn-danger" onclick="fuchsATU.abortTune()" disabled>
            Abort
        </button>
    </div>

    <div id="atu-progress" style="display:none;">
        <div class="progress-bar">
            <div id="atu-progress-fill" class="progress-fill" style="width:0%;"></div>
        </div>
        <span id="atu-progress-text">Sweeping...</span>
    </div>

    <div id="atu-info">
        <span>Cache hits: <span id="atu-cache-hits">0</span></span>
        <span>Uptime: <span id="atu-uptime">--</span></span>
    </div>
</div>
```

- [ ] **Step 2: Add FuchsATU class to controls.js**

```javascript
/**
 * FuchsATU — WebSocket client for the V3.0 Fuchs ATU sub-panel
 * Connects to MRRC /atu WebSocket endpoint
 */
class FuchsATU {
    constructor() {
        this.ws = null;
        this.connected = false;
        this.state = 'idle';
        this.servoPos = 0;
        this.capPct = 0;
        this.lastSWR = null;
        this.cacheHits = 0;
    }

    connect() {
        const wsUrl = `ws://${window.location.host}/atu`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            this.connected = true;
            this.updateConnectionIndicator(true);
            document.getElementById('atu-state-label').textContent = 'Ready';
            this.ws.send(JSON.stringify({ cmd: 'get_status' }));
        };

        this.ws.onclose = () => {
            this.connected = false;
            this.updateConnectionIndicator(false);
            document.getElementById('atu-state-label').textContent = 'Disconnected';
            // Auto-reconnect after 3s
            setTimeout(() => this.connect(), 3000);
        };

        this.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                this.handleMessage(msg);
            } catch (e) {
                console.warn('ATU: invalid JSON', event.data);
            }
        };

        this.ws.onerror = () => {
            this.connected = false;
            this.updateConnectionIndicator(false);
        };
    }

    handleMessage(msg) {
        switch (msg.evt) {
            case 'tune_progress':
                this.servoPos = msg.servo_pos || 0;
                this.capPct = msg.cap_pct || 0;
                this.updateServoDisplay();
                this.updateProgress(this.capPct, msg.state);
                break;

            case 'tune_done':
                this.servoPos = 0; // Will be updated by next status
                this.capPct = msg.cap_pct || 0;
                this.lastSWR = msg.swr_final;
                this.updateServoDisplay();
                this.updateSWRDisplay(msg.swr_final);
                this.tuneComplete();
                break;

            case 'tune_error':
                this.tuneComplete();
                console.error('ATU tune error:', msg.message);
                alert(`ATU Error: ${msg.message}`);
                break;

            case 'status_report':
                this.servoPos = msg.pos || 0;
                this.cacheHits = msg.cache_hits || 0;
                this.updateServoDisplay();
                document.getElementById('atu-cache-hits').textContent = this.cacheHits;
                document.getElementById('atu-uptime').textContent =
                    this.formatUptime(msg.uptime || 0);
                break;

            case 'health_alert':
                console.warn('ATU health alert:', msg.message);
                break;
        }
    }

    startTune() {
        if (!this.connected) {
            alert('ATU not connected');
            return;
        }
        this.state = 'tuning';
        this.updateButtons();
        document.getElementById('atu-progress').style.display = 'block';
        document.getElementById('atu-state-label').textContent = 'Tuning...';

        this.ws.send(JSON.stringify({
            cmd: 'tune_start',
            freq_hz: currentFrequencyHertz || 14200000,  // from global MRRC state
            swr: this.lastSWR || 9.9,
            fwd_pwr_w: currentForwardPower || 5.0,
        }));
    }

    abortTune() {
        if (!this.connected) return;
        this.ws.send(JSON.stringify({ cmd: 'tune_abort' }));
        this.tuneComplete();
    }

    setBypass() {
        if (!this.connected) return;
        this.ws.send(JSON.stringify({ cmd: 'set_bypass' }));
        this.state = 'bypass';
        document.getElementById('atu-state-label').textContent = 'Bypass';
    }

    tuneComplete() {
        this.state = 'idle';
        this.updateButtons();
        document.getElementById('atu-progress').style.display = 'none';
        document.getElementById('atu-state-label').textContent = 'Ready';
        // Request updated status
        this.ws.send(JSON.stringify({ cmd: 'get_status' }));
    }

    updateConnectionIndicator(connected) {
        const dot = document.getElementById('atu-connection');
        dot.className = 'status-dot ' + (connected ? 'connected' : 'disconnected');
    }

    updateServoDisplay() {
        document.getElementById('atu-servo-pos').textContent = this.servoPos;
        document.getElementById('atu-servo-bar-inner').style.width = this.capPct + '%';
    }

    updateSWRDisplay(swr) {
        document.getElementById('atu-swr-value').textContent = swr.toFixed(2);
        const indicator = document.getElementById('atu-swr-indicator');
        let color, text;
        if (swr < 1.5) { color = 'green'; text = '●'; }
        else if (swr < 2.0) { color = 'orange'; text = '●'; }
        else { color = 'red'; text = '●'; }
        indicator.style.color = color;
        indicator.textContent = text;
    }

    updateProgress(pct, state) {
        document.getElementById('atu-progress-fill').style.width = pct + '%';
        document.getElementById('atu-progress-text').textContent =
            state === 'fine_tuning' ? 'Fine tuning...' : 'Sweeping...';
    }

    updateButtons() {
        const tuning = (this.state === 'tuning');
        document.getElementById('atu-tune-btn').disabled = tuning;
        document.getElementById('atu-bypass-btn').disabled = tuning;
        document.getElementById('atu-abort-btn').disabled = !tuning;
    }

    formatUptime(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        return `${h}h ${m}m`;
    }
}

// Initialize ATU panel on page load
const fuchsATU = new FuchsATU();
document.addEventListener('DOMContentLoaded', () => {
    // Add CSS for ATU panel
    const style = document.createElement('style');
    style.textContent = `
        #atu-servo-bar-outer {
            width: 100%; height: 8px; background: #333; border-radius: 4px; margin: 4px 0;
        }
        #atu-servo-bar-inner {
            height: 100%; background: #4a9eff; border-radius: 4px; transition: width 0.3s;
        }
        .status-dot {
            display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px;
        }
        .status-dot.connected { background: #0f0; }
        .status-dot.disconnected { background: #f00; }
        #atu-progress { margin: 8px 0; }
        .progress-bar {
            width: 100%; height: 6px; background: #333; border-radius: 3px; overflow: hidden;
        }
        .progress-fill {
            height: 100%; background: #ffa500; border-radius: 3px; transition: width 0.3s;
        }
        #atu-buttons { display: flex; gap: 6px; margin: 8px 0; }
        #atu-buttons button { flex: 1; padding: 6px; border: none; border-radius: 4px; cursor: pointer; }
        .btn-primary { background: #4a9eff; color: #fff; }
        .btn-secondary { background: #555; color: #fff; }
        .btn-danger { background: #cc3333; color: #fff; }
        .btn-primary:disabled, .btn-secondary:disabled, .btn-danger:disabled { opacity: 0.4; }
    `;
    document.head.appendChild(style);
    fuchsATU.connect();
});
```

- [ ] **Step 3: Commit**

```bash
git add www/index.html www/controls.js
git commit -m "feat: Fuchs ATU web panel — WebSocket client, servo display, SWR indicator"
```

### Task 16: Mobile ATU controls

**Files:**
- Modify: `/Users/cheenle/UHRR/MRRC/www/mobile_modern.html`

- [ ] **Step 1: Add minimal ATU controls to mobile UI**

Add a compact ATU section with only essential controls: SWR display + Auto Tune button + Bypass button. Reuse the FuchsATU class from controls.js.

```html
<!-- Mobile ATU Controls (compact) -->
<div id="atu-mobile" class="mobile-control-row">
    <div class="atu-mobile-swr">
        SWR <span id="atu-mobile-swr-val">--</span>
        <span id="atu-mobile-swr-dot"></span>
    </div>
    <button id="atu-mobile-tune" class="mobile-btn">TUNE</button>
    <button id="atu-mobile-bypass" class="mobile-btn-sm">BYP</button>
</div>
```

- [ ] **Step 2: Commit**

```bash
git add www/mobile_modern.html
git commit -m "feat: mobile ATU controls — compact SWR + Tune + Bypass"
```

---

## Phase 6: Cleanup, archive, final update

### Task 17: Archive legacy firmware

**Files:**
- Move: `auto-efhw-tuner/firmware-stm32/` → `auto-efhw-tuner/firmware-legacy/stm32/`
- Move: `auto-efhw-tuner/firmware/` → `auto-efhw-tuner/firmware-legacy/pic/`

- [ ] **Step 1: Move files**

```bash
mkdir -p auto-efhw-tuner/firmware-legacy
git mv auto-efhw-tuner/firmware-stm32 auto-efhw-tuner/firmware-legacy/stm32
git mv auto-efhw-tuner/firmware auto-efhw-tuner/firmware-legacy/pic
```

- [ ] **Step 2: Add README in firmware-legacy**

```markdown
# Legacy Firmware (Archived)

- `pic/` — V1.0 PIC16F1938 firmware (AA5TB coupler, relay-switched capacitor array)
- `stm32/` — V2.0 STM32F103 firmware (ModularTuner-based, 7-bit relay array)

These are retained for reference. Current firmware: `../firmware-esp32/` (V3.0 Fuchs ATU).
```

- [ ] **Step 3: Commit**

```bash
git add auto-efhw-tuner/firmware-legacy/
git commit -m "archive: move V1.0 PIC and V2.0 STM32 firmware to firmware-legacy/"
```

### Task 18: Update README.md for V3.0

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update project README**

Add V3.0 section to README.md. Key updates:
- Top header: "V3.0 Fuchs ESP32-S3 全自动 EFHW 调谐器"
- New section 13: "V3.0 Fuchs ATU — 伺服连续调谐" with architecture diagram, specs, comparison table
- Update last-updated date to 2026-06-08
- Update section 12 reference to note V2.0 is now legacy

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README V3.0 — Fuchs ESP32-S3 ATU, archive V1.0/V2.0"
```

### Task 19: Add Fuchs ATU to memory

**Files:**
- Create: `/Users/cheenle/.claude/projects/-Users-cheenle-UHRR-MRRC-efhw-knowledge/memory/fuchs-atu-v3-project.md`
- Modify: `MEMORY.md`

- [ ] **Step 1: Write memory file**

Same format as existing memory, describing the V3.0 project status, key design decisions, and links to the spec.

- [ ] **Step 2: Update MEMORY.md index**

Add link to the new memory file.

### Task 20: Final integration verification checklist

**Files:**
- Create: `auto-efhw-tuner/docs/V3_MIGRATION_CHECKLIST.md`

- [ ] **Step 1: Write verification checklist**

```markdown
# V3.0 Fuchs ATU Migration Checklist

## Firmware
- [ ] `idf.py build` compiles without errors
- [ ] `idf.py flash` succeeds on ESP32-S3
- [ ] WiFi connects to test network
- [ ] WebSocket connects to MRRC `/atu` endpoint
- [ ] `get_status` returns valid JSON
- [ ] `tune_start` triggers servo sweep (dry-run, no RF)
- [ ] `tune_abort` stops sweep mid-way
- [ ] `set_bypass` returns servo to 0°
- [ ] NVS cache survives power cycle
- [ ] Health monitor: Bias-V ADC reading correct
- [ ] OTA partition layout verified with `idf.py partition_table`

## Hardware
- [ ] T200-6 inductance measured: ~2.0μH ±10%
- [ ] Variable capacitor range verified: 10-500pF
- [ ] Servo full range: 0-180° maps to capacitor full range
- [ ] MOSFET power cut: servo VCC = 0V when idle
- [ ] Bias-T DC extraction: 12V output stable under load
- [ ] GDT fires at 90V (bench test with HV supply)

## MRRC Integration
- [ ] ATU panel appears in browser UI
- [ ] SWR display updates when ATR1000 provides data
- [ ] Auto Tune button sends tune_start to ATU
- [ ] Progress bar updates during sweep
- [ ] tune_done shows final SWR
- [ ] Mobile UI has TUNE/BYPASS buttons
```

- [ ] **Step 2: Commit**

```bash
git add auto-efhw-tuner/docs/V3_MIGRATION_CHECKLIST.md
git commit -m "docs: V3.0 migration verification checklist"
```

### Task 21: Final commit — wire everything together

- [ ] **Step 1: Verify all files are tracked**

```bash
git status
# Expected: clean working tree with all V3.0 files committed
```

- [ ] **Step 2: Create V3.0 tag**

```bash
git tag v3.0.0-fuchs-atu -m "V3.0 Fuchs ATU: ESP32-S3 + T200-6 + servo variable capacitor + MRRC WebSocket"
```

- [ ] **Step 3: Final commit if needed**

```bash
git add -A
git commit -m "chore: V3.0 Fuchs ATU — complete project refactor

- ESP32-S3 firmware (ESP-IDF v5, FreeRTOS, WebSocket client)
- T200-6 toroid coupler (2:14 turns, 1:49 impedance)
- MG996R servo-driven variable capacitor (10-500pF)
- SWR sensing delegated to MRRC ATR1000 via WebSocket
- MRRC web UI ATU sub-panel with live SWR + progress
- PCB shrunk to 140×50mm (no relays, no SWR bridge)
- BOM ¥255 (35% cheaper than V2.0)
- V1.0/V2.0 firmware archived to firmware-legacy/"
```

---

## Summary — Task Dependency Order

```
Phase 1: Foundation
  T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8
  (sequential — each builds on previous)

Phase 2: Hardware Docs
  T9 → T10 → T11
  (can run in parallel with Phase 3)

Phase 3: Software Docs
  T12 → T13
  (can run in parallel with Phase 2)

Phase 4: MRRC Integration
  T14 → T15 → T16
  (T14 must be first, then T15+T16 parallel)

Phase 5: Cleanup
  T17 → T18 → T19 → T20 → T21
  (sequential)
```

**Estimated total: ~4-6 hours** with parallel execution of Phases 2+3 and intra-Phase 4 parallelism.

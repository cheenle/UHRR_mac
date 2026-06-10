/*
 * atu_config.h — Fuchs ATU V3.0 ESP32-S3 hardware configuration
 */

#ifndef ATU_CONFIG_H
#define ATU_CONFIG_H

#include "driver/gpio.h"
#include "driver/ledc.h"
#include "freertos/FreeRTOS.h"

// ============================================================
// 1. WiFi
// ============================================================
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
#define PIN_SERVO_PWM           GPIO_NUM_1
#define PIN_SERVO_POWER_EN      GPIO_NUM_2
#define PIN_STATUS_LED          GPIO_NUM_6
#define PIN_BUZZER              GPIO_NUM_7

// ADC
#define ADC_BIAS_V_CHANNEL      ADC_CHANNEL_4
#define ADC_BIAS_V_ATTEN        ADC_ATTEN_DB_11
#define ADC_BIAS_V_DIVIDER      5.7f
#define ADC_BIAS_V_UNIT         ADC_UNIT_1

// ============================================================
// 4. Servo Parameters
// ============================================================
#define SERVO_PWM_FREQ_HZ       50
#define SERVO_PWM_TIMER         LEDC_TIMER_0
#define SERVO_PWM_MODE          LEDC_LOW_SPEED_MODE
#define SERVO_PWM_CHANNEL       LEDC_CHANNEL_0
#define SERVO_PWM_RESOLUTION    LEDC_TIMER_16_BIT

#define SERVO_PULSE_MIN_US      500
#define SERVO_PULSE_MAX_US      2500
#define SERVO_PULSE_NEUTRAL_US  1500
#define SERVO_DUTY_MIN          ((SERVO_PULSE_MIN_US * 65535ULL) / 20000)
#define SERVO_DUTY_MAX          ((SERVO_PULSE_MAX_US * 65535ULL) / 20000)

#define SERVO_SWEEP_DEGREES     180
#define SERVO_COARSE_STEP_DEG   5
#define SERVO_FINE_STEP_DEG     1
#define SERVO_MOVE_DELAY_MS     80
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
#define TUNE_FINE_THRESHOLD_SWR 1.5f

// ============================================================
// 6. NVS Tune Cache
// ============================================================
#define NVS_TUNE_PARTITION      "nvs_tune"
#define NVS_NAMESPACE           "tunecache"
#define NVS_KEY_PREFIX          "f"

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
    bool         success;
    uint8_t      servo_pos;
    float        best_swr;
    uint32_t     elapsed_ms;
    tune_error_t error;
} tune_result_t;

#endif /* ATU_CONFIG_H */

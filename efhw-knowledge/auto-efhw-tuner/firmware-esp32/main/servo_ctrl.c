/*
 * servo_ctrl.c — MG996R servo PWM + MOSFET power-cut implementation
 *
 * PWM: 50Hz, 16-bit resolution
 * Pulse: 500-2500µs maps to 0-180°
 * Power: GPIO-driven IRF9540 P-MOSFET via 2N2222A gate pulldown
 *        HIGH on GPIO → P-MOSFET ON  → servo VCC connected
 *        LOW  on GPIO → P-MOSFET OFF → servo VCC disconnected
 */

#include "servo_ctrl.h"
#include "driver/ledc.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "servo";
static uint8_t current_angle = 0;

void servo_init(void) {
    ledc_timer_config_t timer_cfg = {
        .speed_mode = SERVO_PWM_MODE,
        .duty_resolution = SERVO_PWM_RESOLUTION,
        .timer_num = SERVO_PWM_TIMER,
        .freq_hz = SERVO_PWM_FREQ_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&timer_cfg));

    ledc_channel_config_t channel_cfg = {
        .gpio_num = PIN_SERVO_PWM,
        .speed_mode = SERVO_PWM_MODE,
        .channel = SERVO_PWM_CHANNEL,
        .timer_sel = SERVO_PWM_TIMER,
        .duty = 0,
        .hpoint = 0,
    };
    ESP_ERROR_CHECK(ledc_channel_config(&channel_cfg));

    gpio_config_t pwr_cfg = {
        .pin_bit_mask = (1ULL << PIN_SERVO_POWER_EN),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&pwr_cfg));

    servo_power_off();

    ESP_LOGI(TAG, "Initialized: PWM 50Hz, pin=%d, power_en=%d",
             PIN_SERVO_PWM, PIN_SERVO_POWER_EN);
}

bool servo_set_angle(uint8_t degrees) {
    if (degrees > SERVO_SWEEP_DEGREES) return false;

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
    gpio_set_level(PIN_SERVO_POWER_EN, 0);
    ESP_LOGD(TAG, "Servo power OFF");
}

void servo_power_on(void) {
    gpio_set_level(PIN_SERVO_POWER_EN, 1);
    ESP_LOGD(TAG, "Servo power ON");
    vTaskDelay(pdMS_TO_TICKS(50));
}

bool servo_detect_stall(void) {
    /* No position or current feedback is available on this board revision. */
    return false;
}

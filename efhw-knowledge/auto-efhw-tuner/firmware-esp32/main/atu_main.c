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

#define WS_TASK_STACK       8192
#define TUNE_TASK_STACK     4096
#define HEALTH_TASK_STACK   3072

/* ================================================================
 * Tune Engine Task — event-driven via tune_engine_feed_swr()
 * ================================================================ */

static void tune_event_handler(const char *json_str) {
    ws_client_send(json_str);
}

static void tune_engine_task(void *pvParameters) {
    ESP_LOGI(TAG, "Tune engine task started");

    tune_engine_init();
    tune_engine_set_event_callback(tune_event_handler);

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

/* ================================================================
 * Health Monitor Task
 * ================================================================ */

static void health_mon_task(void *pvParameters) {
    ESP_LOGI(TAG, "Health monitor task started");
    health_mon_init();

    while (1) {
        health_mon_tick();
        vTaskDelay(pdMS_TO_TICKS(HEALTH_CHECK_INTERVAL_MS));
    }
}

/* ================================================================
 * LED & Buzzer
 * ================================================================ */

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

static void buzzer_beep(uint8_t count) {
    for (uint8_t i = 0; i < count; i++) {
        gpio_set_level(PIN_BUZZER, 1);
        vTaskDelay(pdMS_TO_TICKS(80));
        gpio_set_level(PIN_BUZZER, 0);
        if (i < count - 1) vTaskDelay(pdMS_TO_TICKS(120));
    }
}

/* ================================================================
 * app_main
 * ================================================================ */

void app_main(void) {
    ESP_LOGI(TAG, "=== Fuchs ATU V3.0 (ESP32-S3) ===");
    ESP_LOGI(TAG, "Firmware built: %s %s", __DATE__, __TIME__);

    /* Initialize hardware */
    indicators_init();
    servo_init();
    buzzer_beep(1);

    /* Initialize NVS tune cache */
    if (!nvs_cache_init()) {
        ESP_LOGE(TAG, "NVS cache init failed — continuing without cache");
    }

    /* Register with task watchdog */
    ESP_ERROR_CHECK(esp_task_wdt_init(5, true));

    /* Create tasks */
    xTaskCreate(ws_client_task, "ws_client",
                WS_TASK_STACK, NULL, 3, NULL);
    xTaskCreate(tune_engine_task, "tune_engine",
                TUNE_TASK_STACK, NULL, 2, NULL);
    xTaskCreate(health_mon_task, "health_mon",
                HEALTH_TASK_STACK, NULL, 1, NULL);

    ESP_LOGI(TAG, "All tasks started.");

    /* Main loop: LED heartbeat */
    while (1) {
        bool ws_ok = ws_client_is_connected();
        gpio_set_level(PIN_STATUS_LED, ws_ok ? 1 : 0);

        /* Blink on disconnect */
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

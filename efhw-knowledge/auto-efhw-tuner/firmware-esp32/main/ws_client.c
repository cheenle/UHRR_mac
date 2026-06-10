/*
 * ws_client.c — WebSocket client implementation
 *
 * WiFi STA → WebSocket to MRRC → JSON command dispatch → FreeRTOS queue
 */

#include "ws_client.h"
#include "tune_engine.h"
#include "servo_ctrl.h"
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

/* Structure for queued outbound messages */
typedef struct {
    char data[512];
} ws_msg_t;

/* Forward declarations */
static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data);
static void ws_event_handler(void *arg, esp_event_base_t event_base,
                             int32_t event_id, void *event_data);
static void init_websocket(void);
static void process_incoming(const char *json_str);

/* ================================================================
 * Public API
 * ================================================================ */

bool ws_client_is_connected(void) {
    return connected;
}

bool ws_client_send(const char *json_str) {
    if (!json_str || !send_queue) return false;
    ws_msg_t msg;
    strncpy(msg.data, json_str, sizeof(msg.data) - 1);
    msg.data[sizeof(msg.data) - 1] = '\0';
    return xQueueSend(send_queue, &msg, pdMS_TO_TICKS(1000)) == pdTRUE;
}

/* ================================================================
 * Main WiFi + WebSocket task
 * ================================================================ */

void ws_client_task(void *pvParameters) {
    /* Initialize NVS (for WiFi credentials) */
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES ||
        ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    /* Initialize TCP/IP stack */
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    /* Create send queue */
    send_queue = xQueueCreate(16, sizeof(ws_msg_t));

    /* WiFi STA initialization */
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL,
        &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL,
        &instance_got_ip));

    /* WiFi config — SSID/password from sdkconfig or compile-time */
    wifi_config_t wifi_config = {0};
    strncpy((char *)wifi_config.sta.ssid, CONFIG_ESP_WIFI_SSID,
            sizeof(wifi_config.sta.ssid) - 1);
    strncpy((char *)wifi_config.sta.password, CONFIG_ESP_WIFI_PASSWORD,
            sizeof(wifi_config.sta.password) - 1);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "WiFi STA started");

    /* Main loop: process send queue */
    while (1) {
        ws_msg_t msg;
        if (xQueueReceive(send_queue, &msg, pdMS_TO_TICKS(100)) == pdTRUE) {
            if (ws_handle && connected) {
                esp_websocket_client_send_text(ws_handle, msg.data,
                                               strlen(msg.data), portMAX_DELAY);
            }
        }

        /* Periodic status report (every 60s) */
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
                ws_client_send(json);
                free(json);
            }
        }
    }
}

/* ================================================================
 * WiFi event handler
 * ================================================================ */

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
        ESP_LOGI(TAG, "WiFi connected, IP: " IPSTR,
                 IP2STR(&event->ip_info.ip));
        init_websocket();
    }
}

/* ================================================================
 * WebSocket client
 * ================================================================ */

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

    default:
        break;
    }
}

/* ================================================================
 * Incoming command dispatch
 * ================================================================ */

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
            health_get_state(),
            xTaskGetTickCount() * portTICK_PERIOD_MS / 1000);
        if (json) {
            ws_client_send(json);
            free(json);
        }
    }

    cJSON_Delete(root);
}

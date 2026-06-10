/*
 * nvs_cache.c — NVS tune cache implementation
 */

#include "nvs_cache.h"
#include "nvs_flash.h"
#include "esp_log.h"
#include <stdio.h>
#include <string.h>

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

    uint16_t base_khz = (uint16_t)(freq_hz / 1000);
    int8_t tolerance = 5;  /* ±50kHz at 10kHz steps */

    for (int8_t delta = 0; delta <= tolerance; delta++) {
        int8_t offset_count = (delta == 0) ? 1 : 2;
        for (int8_t i = 0; i < offset_count; i++) {
            int8_t offset = (i == 0) ? delta : -delta;
            int32_t search_khz = (int32_t)base_khz + ((int32_t)offset * 10);
            if (search_khz <= 0 || search_khz > UINT16_MAX) continue;

            char key[16];
            int len = snprintf(key, sizeof(key), "%s%u",
                               NVS_KEY_PREFIX, (uint16_t)search_khz);
            if (len < 0 || len >= (int)sizeof(key)) continue;

            uint8_t out = 0;
            esp_err_t err = nvs_get_u8(cache_handle, key, &out);
            if (err == ESP_OK) {
                *pos = out;
                cache_hit_count++;
                return true;
            }
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

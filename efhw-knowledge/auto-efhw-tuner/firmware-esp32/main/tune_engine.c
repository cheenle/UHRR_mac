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

static tune_phase_t   phase = TUNE_PHASE_IDLE;
static atu_state_t    atu_state = ATU_IDLE;
static tune_event_cb_t event_cb = NULL;

static uint32_t tune_freq_hz = 0;
static float    tune_initial_swr = 0;
static uint8_t  coarse_step = 0;
static uint8_t  fine_step = 0;
static uint8_t  best_pos = 0;
static float    best_swr = 999.0f;
static uint32_t tune_start_ms = 0;
static bool     swr_pending = false;

static uint8_t  fine_center = 0;

#define COARSE_MAX_STEP (SERVO_SWEEP_DEGREES / SERVO_COARSE_STEP_DEG)

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
        return (coarse_step * 100) / COARSE_MAX_STEP;
    } else if (phase == TUNE_PHASE_FINE_SWEEP) {
        return (fine_step * 100) / 30;
    }
    return 0;
}

bool tune_engine_is_done(void) {
    return (phase == TUNE_PHASE_DONE || phase == TUNE_PHASE_ABORTED);
}

bool tune_engine_is_waiting_for_swr(void) {
    return swr_pending;
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

void tune_engine_start(uint32_t freq_hz, float initial_swr) {
    tune_freq_hz = freq_hz;
    tune_initial_swr = initial_swr;
    coarse_step = 0;
    fine_step = 0;
    best_pos = 0;
    best_swr = 999.0f;
    swr_pending = false;
    tune_start_ms = xTaskGetTickCount() * portTICK_PERIOD_MS;

    servo_power_on();

    /* Phase 1: Check NVS cache */
    uint8_t cached_pos;
    if (nvs_cache_lookup(freq_hz, &cached_pos)) {
        ESP_LOGI(TAG, "Cache hit: %luHz → pos=%d", freq_hz, cached_pos);
        servo_set_angle(cached_pos);
        phase = TUNE_PHASE_DONE;
        atu_state = ATU_LOCKED;
        uint32_t elapsed = xTaskGetTickCount() * portTICK_PERIOD_MS - tune_start_ms;
        if (event_cb) {
            char *json = proto_build_tune_done(
                (cached_pos * 100) / 180, initial_swr, elapsed);
            if (json) { event_cb(json); free(json); }
        }
        servo_power_off();
        return;
    }

    /* Phase 2: Coarse sweep */
    ESP_LOGI(TAG, "Cache miss, starting coarse sweep: %luHz SWR=%.2f",
             freq_hz, initial_swr);
    phase = TUNE_PHASE_COARSE_SWEEP;
    atu_state = ATU_SWEEPING;
    servo_set_angle(0);
    best_swr = initial_swr;
    best_pos = 0;
    coarse_step = 0;

    if (event_cb) {
        char *json = proto_build_tune_progress(0, 0, "sweeping");
        if (json) { event_cb(json); free(json); }
    }

    swr_pending = true;
}

void tune_engine_feed_swr(float swr, float fwd_pwr_w) {
    if (phase != TUNE_PHASE_COARSE_SWEEP && phase != TUNE_PHASE_FINE_SWEEP) {
        return;
    }

    swr_pending = false;

    /* Safety checks */
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

    /* Track best */
    if (swr < best_swr) {
        best_swr = swr;
        best_pos = servo_get_angle();
        if (swr < TUNE_EARLY_EXIT_SWR && phase == TUNE_PHASE_COARSE_SWEEP) {
            coarse_step = COARSE_MAX_STEP;  /* force end of coarse loop */
        }
    }

    /* Advance sweep */
    if (phase == TUNE_PHASE_COARSE_SWEEP) {
        coarse_step++;

        if (coarse_step > COARSE_MAX_STEP) {
            if (best_swr > TUNE_FINE_THRESHOLD_SWR) {
                ESP_LOGI(TAG, "Coarse done, best pos=%d SWR=%.2f → fine sweep",
                         best_pos, best_swr);
                phase = TUNE_PHASE_FINE_SWEEP;
                atu_state = ATU_FINE_TUNING;
                fine_center = best_pos;
                fine_step = 0;
                servo_set_angle(fine_center > 15 ? fine_center - 15 : 0);
            } else {
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
        swr_pending = true;
    }
    else if (phase == TUNE_PHASE_FINE_SWEEP) {
        fine_step++;
        int8_t fine_offset = (int8_t)fine_step - 15;

        if (fine_step >= 30 || fine_offset > 15) {
            phase = TUNE_PHASE_DONE;
            goto finish_tune;
        } else {
            int16_t next_pos = (int16_t)fine_center + fine_offset;
            if (next_pos < 0) next_pos = 0;
            if (next_pos > 180) next_pos = 180;
            servo_set_angle((uint8_t)next_pos);

            if (event_cb) {
                char *json = proto_build_tune_progress(
                    ((uint8_t)next_pos * 100) / 180, (uint8_t)next_pos,
                    "fine_tuning");
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
            ESP_LOGW(TAG, "Tune failed: best SWR=%.2f > %.1f",
                     best_swr, TUNE_MAX_ACCEPT_SWR);
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

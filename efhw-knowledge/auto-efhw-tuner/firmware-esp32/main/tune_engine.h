/*
 * tune_engine.h — Tuning algorithm: cache lookup → coarse sweep → fine sweep
 */

#ifndef TUNE_ENGINE_H
#define TUNE_ENGINE_H

#include "atu_config.h"
#include <stdint.h>
#include <stdbool.h>

void tune_engine_init(void);
void tune_engine_start(uint32_t freq_hz, float initial_swr);
void tune_engine_feed_swr(float swr, float fwd_pwr_w);
void tune_engine_abort(void);

atu_state_t tune_engine_get_state(void);
uint8_t tune_engine_get_progress_pct(void);
tune_result_t tune_engine_get_result(void);
bool tune_engine_is_done(void);
bool tune_engine_is_waiting_for_swr(void);

typedef void (*tune_event_cb_t)(const char *json_str);
void tune_engine_set_event_callback(tune_event_cb_t cb);

#endif /* TUNE_ENGINE_H */

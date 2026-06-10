/*
 * protocol.h — MRRC ↔ ATU WebSocket JSON protocol definitions
 */

#ifndef PROTOCOL_H
#define PROTOCOL_H

#include "atu_config.h"
#include "cJSON.h"
#include <stdint.h>

// ============================================================
// MRRC → ATU commands
// ============================================================

typedef struct {
    uint32_t freq_hz;
    float    swr;
    float    fwd_pwr_w;
} cmd_tune_start_t;

cmd_tune_start_t proto_parse_tune_start(const char *json);

typedef struct {
    float swr;
    float fwd_pwr_w;
} cmd_swr_update_t;

cmd_swr_update_t proto_parse_swr_update(const char *json);

// ============================================================
// ATU → MRRC events
// ============================================================

char *proto_build_tune_progress(uint8_t cap_pct, uint8_t servo_pos,
                                const char *state);

char *proto_build_tune_done(uint8_t cap_pct, float swr_final,
                            uint32_t elapsed_ms);

char *proto_build_tune_error(tune_error_t error);

char *proto_build_status_report(uint8_t pos, uint32_t cache_hits,
                                sys_health_t health, uint32_t uptime);

char *proto_build_health_alert(uint8_t code, float value, const char *message);

#endif /* PROTOCOL_H */

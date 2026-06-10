/*
 * protocol.c — JSON protocol parsing and building implementations
 */

#include "protocol.h"
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

char *proto_build_tune_progress(uint8_t cap_pct, uint8_t servo_pos,
                                const char *state) {
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "evt", "tune_progress");
    cJSON_AddNumberToObject(root, "cap_pct", cap_pct);
    cJSON_AddNumberToObject(root, "servo_pos", servo_pos);
    cJSON_AddStringToObject(root, "state", state);
    char *out = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    return out;
}

char *proto_build_tune_done(uint8_t cap_pct, float swr_final,
                            uint32_t elapsed_ms) {
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
    static const char *msgs[] = {
        [TUNE_OK]               = "ok",
        [TUNE_ERR_OVERPOWER]    = "overpower",
        [TUNE_ERR_NORF]         = "no_rf",
        [TUNE_ERR_HIGHSWR]      = "no_match",
        [TUNE_ERR_SERVO_STALL]  = "servo_stall",
        [TUNE_ERR_TIMEOUT]      = "timeout",
        [TUNE_ERR_WS_DISCONNECT]= "ws_disconnect",
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

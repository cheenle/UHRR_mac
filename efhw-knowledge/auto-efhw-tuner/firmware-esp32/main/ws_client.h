/*
 * ws_client.h — WebSocket client connecting ESP32-S3 ATU to MRRC server
 */

#ifndef WS_CLIENT_H
#define WS_CLIENT_H

#include "atu_config.h"
#include <stdint.h>
#include <stdbool.h>

void ws_client_task(void *pvParameters);
bool ws_client_send(const char *json_str);
bool ws_client_is_connected(void);

#endif /* WS_CLIENT_H */

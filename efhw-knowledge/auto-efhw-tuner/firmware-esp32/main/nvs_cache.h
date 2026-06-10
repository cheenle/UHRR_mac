/*
 * nvs_cache.h — Non-Volatile Storage tune cache
 */

#ifndef NVS_CACHE_H
#define NVS_CACHE_H

#include "atu_config.h"
#include <stdint.h>
#include <stdbool.h>

bool nvs_cache_init(void);
bool nvs_cache_lookup(uint32_t freq_hz, uint8_t *pos);
bool nvs_cache_save(uint32_t freq_hz, uint8_t pos);
uint32_t nvs_cache_get_hits(void);
uint32_t nvs_cache_get_saves(void);
bool nvs_cache_erase_all(void);

#endif /* NVS_CACHE_H */

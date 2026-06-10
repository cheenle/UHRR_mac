/*
 * health_mon.h — Periodic health checks (Bias-T voltage, core temp, WDT)
 */

#ifndef HEALTH_MON_H
#define HEALTH_MON_H

#include "atu_config.h"
#include <stdbool.h>

void health_mon_init(void);
void health_mon_tick(void);
sys_health_t health_get_state(void);
float health_get_bias_voltage(void);

#endif /* HEALTH_MON_H */

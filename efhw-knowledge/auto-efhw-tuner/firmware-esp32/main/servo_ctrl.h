/*
 * servo_ctrl.h — MG996R servo PWM + MOSFET power-cut control
 */

#ifndef SERVO_CTRL_H
#define SERVO_CTRL_H

#include "atu_config.h"
#include <stdint.h>
#include <stdbool.h>

void servo_init(void);
bool servo_set_angle(uint8_t degrees);
uint8_t servo_get_angle(void);
void servo_power_off(void);
void servo_power_on(void);
bool servo_detect_stall(void);

#endif /* SERVO_CTRL_H */

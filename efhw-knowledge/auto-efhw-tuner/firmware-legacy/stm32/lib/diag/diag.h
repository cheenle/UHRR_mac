/*
 * diag.h — 运行时故障诊断 — STM32 适配版
 */

#ifndef DIAG_H
#define DIAG_H

#include <Arduino.h>
#include "../../tuner_config.h"

typedef enum {
  FAULT_NONE = 0,
  FAULT_DC_RAIL,
  FAULT_ADC_STUCK,
  FAULT_SWR_SENSOR,
  FAULT_TUNE_FAIL,
  FAULT_RELAY_STUCK,
} fault_code_t;

typedef struct {
  bool      health_changed;
  sys_health_t new_health;
  uint8_t   failed_relays;
  uint8_t   fault_count;
} diag_result_t;

class DiagMonitor {
  sys_health_t health;
  uint8_t      fault_log[16];   // 简化日志
  uint8_t      fault_idx;

public:
  DiagMonitor();

  sys_health_t getHealth() { return health; }
  void setHealth(sys_health_t h);

  diag_result_t runChecks();
  void logFault(fault_code_t code, uint8_t data0, uint8_t data1);
};

#endif

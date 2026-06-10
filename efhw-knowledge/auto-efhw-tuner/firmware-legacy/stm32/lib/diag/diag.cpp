/*
 * diag.cpp — 运行时诊断实现
 */

#include "diag.h"

DiagMonitor::DiagMonitor() {
  health = SYS_HEALTHY;
  fault_idx = 0;
  memset(fault_log, 0, sizeof(fault_log));
}

void DiagMonitor::setHealth(sys_health_t h) {
  health = h;
}

diag_result_t DiagMonitor::runChecks() {
  diag_result_t result = {false, health, 0, 0};

  // SWR 传感器合理性检查
  uint16_t fwd = analogRead(PIN_FWD_PWR);
  uint16_t rev = analogRead(PIN_REV_PWR);
  if (rev > fwd * 2 && fwd > 100) {  // REV 不应该远大于 FWD
    logFault(FAULT_SWR_SENSOR, fwd >> 4, rev >> 4);
    result.health_changed = true;
    result.new_health = SYS_DEGRADED;
    setHealth(SYS_DEGRADED);
  }

  // ADC 卡死检测
  static uint16_t last_fwd = 0xFFFF;
  static uint8_t  stuck_count = 0;
  if (fwd == last_fwd && last_fwd != 0xFFFF) {
    stuck_count++;
    if (stuck_count > ADC_STUCK_THRESH) {
      logFault(FAULT_ADC_STUCK, 0, 0);
      result.health_changed = true;
      result.new_health = SYS_DEGRADED;
      setHealth(SYS_DEGRADED);
      stuck_count = 0;
    }
  } else {
    stuck_count = 0;
  }
  last_fwd = fwd;

  result.fault_count = fault_idx;
  return result;
}

void DiagMonitor::logFault(fault_code_t code, uint8_t data0, uint8_t data1) {
  fault_log[fault_idx % 16] = (uint8_t)code;
  fault_idx++;
}

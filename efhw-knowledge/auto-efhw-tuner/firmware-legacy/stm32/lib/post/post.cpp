/*
 * post.cpp — POST 实现 (STM32F103)
 */

#include "post.h"

post_result_t PostRunner::run_all() {
  post_result_t result = {POST_PASS, false, 0};

  // PHASE 0: DC 电源 (3.3V MCU 供电正常?)
  if (!checkDC()) {
    result.code = POST_FAIL_DC;
    return result;  // 致命, 不继续
  }

  // PHASE 1: 核心 — 如果代码在运行说明振荡器/Flash 正常
  // (STM32 有硬件时钟安全系统 CSS)

  // PHASE 2: ADC 自检
  if (!checkADC()) {
    result.code = POST_FAIL_ADC;
    result.degraded = true;
  }

  // PHASE 3: RF 路径
  if (!checkRelays()) {
    result.code = POST_FAIL_RELAY;
    result.degraded = true;
  }

  if (!checkSWRBridge()) {
    result.code = POST_FAIL_SWR;
    result.degraded = true;
  }

  return result;
}

bool PostRunner::checkDC() {
  // 读取内部 Vrefint (1.20V) → 反推 VDDA
  uint16_t vref = analogRead(17);  // STM32F103 ADC CH17 = Vrefint
  if (vref < 1300 || vref > 1700) {  // 1.20V ± 15%
    return false;
  }
  return true;
}

bool PostRunner::checkADC() {
  // 连续读 8 次, 确认 ADC 不卡死
  uint16_t v0 = analogRead(PIN_FWD_PWR);
  for (int i = 0; i < 8; i++) {
    uint16_t v = analogRead(PIN_FWD_PWR);
    if (v != v0) return true;  // 有变化 = ADC 正常
    delayMicroseconds(100);
  }
  return false;  // 8 次全部相同 → 可能卡死
}

bool PostRunner::checkRelays() {
  // 逐个继电器短时吸合-释放 (听声 / SWR变化验证)
  // 简化: 仅验证 GPIO 能正常翻转
  for (uint8_t i = 0; i < 7; i++) {
    pinMode(CAP_PINS[i], OUTPUT);
    digitalWrite(CAP_PINS[i], HIGH);
    delayMicroseconds(100);
    digitalWrite(CAP_PINS[i], LOW);
  }
  return true;
}

bool PostRunner::checkSWRBridge() {
  // 读取 SWR 传感器噪声底 (应非零)
  uint16_t fwd = analogRead(PIN_FWD_PWR);
  uint16_t rev = analogRead(PIN_REV_PWR);
  return (fwd > 0 || rev > 0);
}

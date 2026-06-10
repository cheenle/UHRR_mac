/*
 * post.h — 上电自检 (POST) — STM32 适配版
 *
 * 4 阶段 POST: DC电源 → 核心系统 → 外设 → RF路径
 */

#ifndef POST_H
#define POST_H

#include <Arduino.h>
#include "../../tuner_config.h"

typedef enum {
  POST_PASS = 0,
  POST_DEGRADED,
  POST_FAIL_DC,
  POST_FAIL_ADC,
  POST_FAIL_RELAY,
  POST_FAIL_SWR,
} post_code_t;

typedef struct {
  post_code_t code;
  bool        degraded;    // 降级但可运行
  uint8_t     failed_relays; // 失效继电器掩码
} post_result_t;

class PostRunner {
public:
  // 运行完整 POST (4 阶段)
  post_result_t run_all();

  // 单阶段检查
  bool checkDC();
  bool checkADC();
  bool checkRelays();
  bool checkSWRBridge();
};

#endif

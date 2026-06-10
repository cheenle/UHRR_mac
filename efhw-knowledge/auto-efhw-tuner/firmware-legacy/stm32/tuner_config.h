/*
 * tuner_config.h — EFHW Tuner STM32 硬件引脚 & 参数配置
 */

#ifndef TUNER_CONFIG_H
#define TUNER_CONFIG_H

#include <Arduino.h>

// ============================================================
// 1. 系统参数
// ============================================================
#define TUNE_POWER_MIN_W      0.5f    // 调谐最低功率 (W)
#define TUNE_POWER_MAX_W      15.0f   // 调谐最高功率 (W, 超过则中止)
#define PWR_CALIB_FACTOR      12.0f   // 功率校准系数 (平方律)
#define RELAY_SETTLE_MS       12      // G5Q-14 继电器稳定时间 (ms)
#define TUNE_COOLDOWN_TICKS   20      // 调谐冷却间隔 (×100ms = 2s)
#define SWR_EARLY_EXIT        1.05f   // SWR 早期退出阈值
#define SWR_SAVE_MAX          3.0f    // SWR 保存上限

// ============================================================
// 2. STM32F103 引脚映射
// ============================================================

// --- SWR 检波器 (Tandem Match) ---
// 复用 ModularTuner SWRMeter 默认引脚
#define PIN_FWD_PWR       PA0   // 正向功率 ADC
#define PIN_REV_PWR       PA1   // 反向功率 ADC
#define PIN_CUR_PWR       PA2   // 电流功率 ADC (可选)

// --- 电容阵列继电器 (7位, PA8-PA14 经 ULN2003A) ---
// PA15 被 JTAG 占用, 禁用 JTAG 后释放
#define PIN_CAP_BIT0      PA8   // 10pF
#define PIN_CAP_BIT1      PA9   // 22pF
#define PIN_CAP_BIT2      PA10  // 47pF
#define PIN_CAP_BIT3      PA11  // 100pF
#define PIN_CAP_BIT4      PA12  // 220pF
#define PIN_CAP_BIT5      PA13  // 470pF (SWD 复用, 需注意)
#define PIN_CAP_BIT6      PA14  // 1000pF (SWD 复用, 需注意)
// 注意: PA13/PA14 是 SWD 调试口, 如果不需要调试可在程序内重新配置为 GPIO
// 开发阶段保留 SWD, 使用 PB3/PB4/PB5 替代 PA13/PA14

// --- 备用引脚方案 (如果保留 SWD 调试) ---
#define PIN_CAP_BIT5_ALT  PB3   // 470pF (如果PA13用于SWD)
#define PIN_CAP_BIT6_ALT  PB4   // 1000pF (如果PA14用于SWD)

// --- 频率计数器 ---
#define PIN_FREQ_COUNTER  PB9   // 频率计数输入 (TIM4_CH4)

// --- Bias-T 电压监测 ---
#define PIN_BIAS_V_SENSE  PA4   // 12V 分压监测 ADC
#define BIAS_V_DIVIDER    5.7f  // 分压比 (12V → 2.1V @ 3.3V ADC)

// --- 指示 ---
#define PIN_BUZZER        PB12  // 蜂鸣器
#define PIN_LED           PB13  // 状态 LED

// --- ULN2003A 使能 ---
#define PIN_ULN_ENABLE    PB14  // ULN2003A 全局使能 (可选)

// ============================================================
// 3. 电容阵列参数
// ============================================================
// 7位二进制权值 (pF)
#define CAP_BIT0_PF  10
#define CAP_BIT1_PF  22
#define CAP_BIT2_PF  47
#define CAP_BIT3_PF  100
#define CAP_BIT4_PF  220
#define CAP_BIT5_PF  470
#define CAP_BIT6_PF  1000
#define CAP_ARRAY_BITS 7

// 电容阵列引脚列表
const uint8_t CAP_PINS[7] = {
  PIN_CAP_BIT0, PIN_CAP_BIT1, PIN_CAP_BIT2, PIN_CAP_BIT3,
  PIN_CAP_BIT4,
  PIN_CAP_BIT5_ALT,   // 使用备用引脚保留SWD
  PIN_CAP_BIT6_ALT
};

// ============================================================
// 4. 故障检测阈值
// ============================================================
#define V12_MIN             10.0f   // 12V 轨最低正常电压
#define V12_MAX             15.0f   // 12V 轨最高正常电压
#define ADC_STUCK_THRESH    8       // ADC 连续相同读数→卡死
#define RELAY_FAIL_COUNT    3       // ≥3 继电器失效→SAFE

// ============================================================
// 5. 类型定义
// ============================================================
typedef enum {
  TUNER_IDLE = 0,
  TUNER_TUNING,
  TUNER_LOCKED,
} tuner_state_t;

typedef enum {
  TUNE_OK = 0,
  TUNE_ERR_OVERPOWER,
  TUNE_ERR_NORF,
  TUNE_ERR_HIGHSWR,
} tune_error_t;

typedef struct {
  bool     success;
  uint8_t  best_cap;
  float    best_swr;
  tune_error_t error;
} tune_result_t;

typedef struct {
  float fwd_pwr;
  float rev_pwr;
  float swr;
  uint32_t freq_hz;
} swr_reading_t;

typedef enum {
  SYS_HEALTHY  = 0,
  SYS_DEGRADED = 1,
  SYS_SAFE     = 2,
} sys_health_t;

#endif

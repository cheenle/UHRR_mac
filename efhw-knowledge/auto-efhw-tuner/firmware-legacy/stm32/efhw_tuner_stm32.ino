/*
 * efhw_tuner_stm32.ino — EFHW 全自动谐振调谐器 STM32F103 固件
 * ==============================================================
 * 基于: profdc9/ModularTuner (Copyright (c) 2018 Daniel Marks, CC-BY-SA 4.0)
 * 适配: BG1SB (2026-06-08) — 纯电容 EFHW 专用版
 *
 * 改动:
 *   - 删除多模块 RelayModule → 替换为 CapBank 7位直驱
 *   - 删除 LCD / I2C / 电台控制 / 无线遥控
 *   - 删除电感矩阵 + 多配置切换
 *   - 替换调谐算法: exhaustive_tune() → cap_sweep_tune()
 *   - 新增: Bias-T 电压监测 / POST 自检 / 故障诊断
 *   - 保留: SWRMeter (Tandem Match 检波) / FrequencyCounter / Flash存储 / 缓存
 *
 * 硬件:
 *   MCU:  STM32F103C8T6 (Bluepill), 72MHz
 *   ADC:  12-bit, 3.3V Vref
 *   磁芯: T200-2B ×2 (羰基铁粉 Type 2, μ=10)
 *   电容: 7位 128档 1812 3KV C0G (10-1997pF)
 *   继电器: 7 × G5Q-14 12VDC (PA8-PA15 经 ULN2003A)
 *   保护: 90V GDT + 2.2MΩ 静电泄放
 */

#include "tuner_config.h"
#include "lib/swrmeter/swrmeter.h"
#include "lib/capbank/capbank.h"
#include "lib/post/post.h"
#include "lib/diag/diag.h"

// ============================================================
// 全局对象
// ============================================================
SWRMeter swrMeter;
CapBank  capBank;
TuneCache tuneCache;
PostRunner postRunner;
DiagMonitor diagMon;

// ============================================================
// 运行状态
// ============================================================
tuner_state_t  tuner_state = TUNER_IDLE;
swr_reading_t  last_swr;
uint32_t       last_tune_freq_hz = 0;
uint8_t        tune_cooldown = 0;
uint8_t        consecutive_tune_fails = 0;
uint32_t       uptime_seconds = 0;
uint32_t       last_diag_time = 0;

// ============================================================
// SETUP
// ============================================================
void setup() {
  // 1. 禁用 JTAG, 释放 PA15/PB3/PB4 为 GPIO
  afio_cfg_debug_ports(AFIO_DEBUG_SW_ONLY);

  // 2. 初始化串口 (调试用, 115200bps)
  Serial.begin(115200);
  delay(100);

  // 3. SWR 检波器初始化
  swrMeter.setup();
  swrMeter.setImpedance(50.0f);

  // 4. 电容阵列初始化
  capBank.setup();

  // 5. 上电自检
  post_result_t post = postRunner.run_all();

  // 6. 加载 Flash 存储的状态
  if (!loadFlashState()) {
    tuneCache.clear();
    capBank.setValue(0);  // 安全状态: 所有继电器释放
  }

  // 7. Bias-T 电压检查
  float v12 = readBiasVoltage();
  if (v12 < 10.0f || v12 > 15.0f) {
    diagMon.logFault(FAULT_DC_RAIL, v12, 0);
    capBank.setValue(0);
  }

  // 8. POST 结果处理
  if (post != POST_PASS) {
    diagMon.setHealth(post.degraded ? SYS_DEGRADED : SYS_SAFE);
    signalPostResult(post);
  }

  Serial.println("EFHW Tuner STM32 ready.");
  signalBeep(1);
}

// ============================================================
// MAIN LOOP
// ============================================================
void loop() {
  uint32_t now = millis();

  // ---- 频率/功率采样 (每 100ms) ----
  static uint32_t last_sample = 0;
  if (now - last_sample >= 100) {
    last_sample = now;
    swrMeter.sampleSWR();
    last_swr.fwd_pwr = swrMeter.fwdPower();
    last_swr.rev_pwr = swrMeter.revPower();
    last_swr.swr     = swrMeter.SWR();
    last_swr.freq_hz = readFrequency();
  }

  // ---- 自动调谐触发 ----
  float adj_fwd = adjustPower(last_swr.fwd_pwr);
  if (adj_fwd > TUNE_POWER_MIN_W && adj_fwd < TUNE_POWER_MAX_W) {
    if (tune_cooldown > 0) tune_cooldown--;

    if (tune_cooldown == 0 &&
        tuner_state == TUNER_IDLE &&
        diagMon.getHealth() != SYS_SAFE) {

      // 检测频段变化 → 触发调谐
      uint32_t freq = last_swr.freq_hz;
      if (freq > 0 && abs((int32_t)(freq - last_tune_freq_hz)) > 50000) {
        tuner_state = TUNER_TUNING;
        tune_result_t result = cap_sweep_tune();

        if (result.success) {
          last_tune_freq_hz = freq;
          consecutive_tune_fails = 0;
          tuneCache.save(freq, result.best_cap);
          signalBeep(1);
        } else {
          consecutive_tune_fails++;
          if (consecutive_tune_fails >= 3) {
            diagMon.setHealth(SYS_SAFE);
            diagMon.logFault(FAULT_TUNE_FAIL, consecutive_tune_fails, 0);
          }
          signalBeep(3);
        }
        tuner_state = TUNER_IDLE;
        tune_cooldown = TUNE_COOLDOWN_TICKS;
      }
    }
  }

  // ---- 运行时诊断 (每 10s) ----
  if (now - last_diag_time >= 10000) {
    last_diag_time = now;
    diag_result_t d = diagMon.runChecks();
    if (d.health_changed) {
      signalBeep(d.new_health == SYS_SAFE ? 5 : 2);
    }
  }

  // ---- 串口命令处理 ----
  if (Serial.available()) {
    processSerialCommand();
  }

  // ---- 心跳 ----
  uptime_seconds = now / 1000;
}

// ============================================================
// 电容扫描调谐算法 (替代 ModularTuner 的 exhaustive_tune)
// ============================================================
tune_result_t cap_sweep_tune() {
  tune_result_t result = {0};
  float min_swr = 999.0f;
  uint8_t best_cap = 0;
  float fwd, rev, swr;

  Serial.println("Tuning: capacitor sweep 0-127...");

  // 安全检查
  swrMeter.sampleSWR();
  fwd = adjustPower(swrMeter.fwdPower());
  if (fwd > TUNE_POWER_MAX_W) {
    result.success = false;
    result.error = TUNE_ERR_OVERPOWER;
    capBank.setValue(0);
    return result;
  }

  // 全扫描 128 档
  for (uint8_t c = 0; c < 128; c++) {
    capBank.setValue(c);
    delay(RELAY_SETTLE_MS);

    // 实时功率检查
    swrMeter.sampleSWR();
    fwd = adjustPower(swrMeter.fwdPower());
    if (fwd > TUNE_POWER_MAX_W) {
      capBank.setValue(0);
      result.success = false;
      result.error = TUNE_ERR_OVERPOWER;
      return result;
    }
    if (fwd < TUNE_POWER_MIN_W) {
      capBank.setValue(0);
      result.success = false;
      result.error = TUNE_ERR_NORF;
      return result;
    }

    rev = swrMeter.revPower();
    swr = (fwd + rev) / (fwd - rev + 0.001f);

    if (swr < min_swr) {
      min_swr = swr;
      best_cap = c;
      if (swr < 1.05f) break;  // 早期退出
    }
  }

  // 锁定最优值
  capBank.setValue(best_cap);
  delay(RELAY_SETTLE_MS);

  result.success = (min_swr < 3.0f);
  result.best_cap = best_cap;
  result.best_swr = min_swr;
  result.error = result.success ? TUNE_OK : TUNE_ERR_HIGHSWR;

  Serial.print("Tune done: cap=");
  Serial.print(best_cap);
  Serial.print(" SWR=");
  Serial.println(min_swr);

  return result;
}

// ============================================================
// 辅助函数
// ============================================================
float adjustPower(float raw) {
  return PWR_CALIB_FACTOR * raw * raw;
}

uint32_t readFrequency() {
  // 频率计数器 (复用 ModularTuner FrequencyCounter)
  // 简化: 使用定时器捕获
  return 0;  // placeholder
}

float readBiasVoltage() {
  // 读取 Bias-T 供电电压 (分压后 ADC)
  uint16_t adc = analogRead(PIN_BIAS_V_SENSE);
  return adc * (3.3f / 4096.0f) * BIAS_V_DIVIDER;
}

void signalBeep(uint8_t count) {
  for (uint8_t i = 0; i < count; i++) {
    digitalWrite(PIN_BUZZER, HIGH);
    delay(80);
    digitalWrite(PIN_BUZZER, LOW);
    if (i < count - 1) delay(120);
  }
}

void processSerialCommand() {
  // 调试控制台 (简化版)
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  if (cmd == "status") {
    Serial.print("SWR="); Serial.print(last_swr.swr);
    Serial.print(" FWD="); Serial.print(adjustPower(last_swr.fwd_pwr));
    Serial.print("W CAP="); Serial.print(capBank.getValue());
    Serial.print(" HEALTH="); Serial.println(diagMon.getHealth());
  } else if (cmd == "tune") {
    cap_sweep_tune();
  } else if (cmd == "bypass") {
    capBank.setValue(0);
  } else if (cmd == "help") {
    Serial.println("status | tune | bypass | help");
  }
}

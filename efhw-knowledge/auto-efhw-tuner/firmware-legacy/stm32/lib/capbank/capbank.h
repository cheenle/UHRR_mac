/*
 * capbank.h — 7位二进制电容阵列驱动 (替代 ModularTuner RelayModule)
 *
 * 直接 GPIO 驱动 (不经 MCP23017 I2C 扩展), 含回读验证。
 * 7 个继电器 → 128 档电容 (10-1997pF, 步进 ~10-15pF)。
 */

#ifndef CAPBANK_H
#define CAPBANK_H

#include <Arduino.h>
#include "../../tuner_config.h"

class CapBank {
  uint8_t  current_value;    // 当前电容值 (0-127)
  uint8_t  failed_mask;      // 失效继电器位掩码
  uint8_t  pin_map[7];       // 引脚映射

public:
  CapBank();

  // 初始化: 配置 GPIO, 全部继电器释放
  void setup();

  // 设置电容值 (0-127), 失败重试3次, 回读验证
  bool setValue(uint8_t value);

  // 读取当前电容值
  uint8_t getValue() { return current_value; }

  // 单独控制某一位 (用于诊断)
  void setBit(uint8_t bit, bool on);

  // GPIO 回读验证
  bool verifyWrite(uint8_t expected);

  // 获取失效继电器掩码
  uint8_t getFailedMask() { return failed_mask; }

  // 获取可用档位数量
  uint8_t getAvailableBits();

private:
  // 将7位值映射到 GPIO 输出
  void applyBits(uint8_t value);
};

// ============================================================
// 频率-电容缓存 (TuneCache)
// ============================================================
#define CACHE_ENTRIES 200
#define CACHE_KHZ_SPACING 10

typedef struct {
  uint16_t freq_khz;
  uint8_t  cap_value;
} cache_entry_t;

class TuneCache {
  cache_entry_t entries[CACHE_ENTRIES];

public:
  TuneCache();

  // 清空缓存
  void clear();

  // 查找频率对应的电容值 (返回索引, -1=未找到)
  int  find(uint32_t freq_hz);

  // 保存
  void save(uint32_t freq_hz, uint8_t cap_value);

  // 加载
  bool load(uint32_t freq_hz, uint8_t &cap_value);
};

#endif

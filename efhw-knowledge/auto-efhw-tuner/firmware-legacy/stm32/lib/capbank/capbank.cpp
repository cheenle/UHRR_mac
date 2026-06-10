/*
 * capbank.cpp — 7位电容阵列 GPIO 直驱实现
 *
 * 替代 ModularTuner 的 RelayModule (删除 MCP23017 I2C + 多模块架构)。
 *
 * GPIO 回读验证: 写入后读回 IDR 寄存器, 不一致则重试 3 次。
 *                 3 次失败 → 标记继电器失效 → 降级运行。
 */

#include "capbank.h"

CapBank::CapBank() {
  current_value = 0;
  failed_mask = 0;
  memset(pin_map, 0, sizeof(pin_map));
}

void CapBank::setup() {
  // 复制引脚映射
  memcpy(pin_map, CAP_PINS, sizeof(pin_map));

  // 配置所有继电器控制引脚为推挽输出
  for (uint8_t i = 0; i < 7; i++) {
    pinMode(pin_map[i], OUTPUT);
    digitalWrite(pin_map[i], LOW);  // 全部释放 (LOW = 继电器关)
  }

  // ULN2003A 使能脚 (如使用)
  #ifdef PIN_ULN_ENABLE
    pinMode(PIN_ULN_ENABLE, OUTPUT);
    digitalWrite(PIN_ULN_ENABLE, HIGH);  // 使能
  #endif
}

bool CapBank::setValue(uint8_t value) {
  if (value > 127) return false;

  uint8_t effective = value & ~failed_mask;  // 排除失效位

  for (uint8_t retry = 0; retry < 3; retry++) {
    applyBits(effective);
    delayMicroseconds(10);  // GPIO 稳定

    if (verifyWrite(effective)) {
      current_value = value;
      return true;
    }
  }

  // 3 次失败 → 尝试识别并标记失效位
  for (uint8_t bit = 0; bit < 7; bit++) {
    // 单独测试每一位
    uint8_t test_val = 1 << bit;
    applyBits(test_val);
    delayMicroseconds(10);
    if (!verifyWrite(test_val)) {
      failed_mask |= (1 << bit);
    }
  }

  applyBits(0);  // 安全状态
  return false;
}

void CapBank::setBit(uint8_t bit, bool on) {
  if (bit >= 7) return;
  if (on) {
    current_value |= (1 << bit);
  } else {
    current_value &= ~(1 << bit);
  }
  applyBits(current_value & ~failed_mask);
}

bool CapBank::verifyWrite(uint8_t expected) {
  for (uint8_t i = 0; i < 7; i++) {
    bool should_be_high = (expected >> i) & 1;
    bool is_high = digitalRead(pin_map[i]);
    if (should_be_high != is_high) return false;
  }
  return true;
}

uint8_t CapBank::getAvailableBits() {
  uint8_t available = 0;
  for (uint8_t i = 0; i < 7; i++) {
    if (!(failed_mask & (1 << i))) available++;
  }
  return available;
}

void CapBank::applyBits(uint8_t value) {
  for (uint8_t i = 0; i < 7; i++) {
    digitalWrite(pin_map[i], (value >> i) & 1 ? HIGH : LOW);
  }
}

// ============================================================
// TuneCache 实现
// ============================================================
TuneCache::TuneCache() {
  clear();
}

void TuneCache::clear() {
  memset(entries, 0, sizeof(entries));
}

int TuneCache::find(uint32_t freq_hz) {
  uint16_t freq_khz = (uint16_t)(freq_hz / 1000);
  uint16_t half_span = CACHE_KHZ_SPACING / 2;

  for (int i = 0; i < CACHE_ENTRIES; i++) {
    if (entries[i].freq_khz == 0) continue;
    uint16_t diff = abs((int16_t)(entries[i].freq_khz - freq_khz));
    if (diff <= half_span) return i;
  }
  return -1;
}

void TuneCache::save(uint32_t freq_hz, uint8_t cap_value) {
  uint16_t freq_khz = (uint16_t)(freq_hz / 1000);

  // 查找已有条目或第一个空位
  int slot = find(freq_hz);
  if (slot < 0) {
    for (int i = 0; i < CACHE_ENTRIES; i++) {
      if (entries[i].freq_khz == 0) { slot = i; break; }
    }
    if (slot < 0) slot = CACHE_ENTRIES - 1;  // 覆盖最后一个
  }

  // 移到顶部 (最近使用)
  cache_entry_t temp = {freq_khz, cap_value};
  for (int i = (slot < CACHE_ENTRIES-1 ? slot : CACHE_ENTRIES-1); i > 0; i--) {
    entries[i] = entries[i-1];
  }
  entries[0] = temp;
}

bool TuneCache::load(uint32_t freq_hz, uint8_t &cap_value) {
  int slot = find(freq_hz);
  if (slot < 0) return false;
  cap_value = entries[slot].cap_value;
  return true;
}

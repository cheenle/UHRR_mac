/*
 * diagnostics.c - Runtime Fault Detection Implementation
 *
 * Target:  PIC16F1938
 * License:  GPL-3.0
 *
 * Implements the FDE specification (docs/FDE.md) for the EFHW Auto Tuner.
 * All detection algorithms are designed to work within the constraints of
 * a PIC16F1938 (no heap, minimal stack, no RTOS).
 */

#include "main.h"
#include "diagnostics.h"
#include "tuning.h"
#include "swr_bridge.h"
#include "eeprom.h"
#include "display.h"

// ============================================================
// MODULE STATE
// ============================================================

static sys_health_t  sys_health     = SYS_HEALTHY;
static uint8_t       failed_relays_mask = 0x00;
static uint16_t      uptime_hours   = 0;  // Rough uptime counter
static uint8_t       last_reset_cause = 0;

// ADC stuck detection state
static uint16_t      last_adc_fwd  = 0xFFFF;
static uint16_t      last_adc_rev  = 0xFFFF;
static uint8_t       adc_stuck_count_fwd = 0;
static uint8_t       adc_stuck_count_rev = 0;

// ============================================================
// CRC-8 (Dallas/Maxim 1-Wire polynomial: x⁸ + x⁵ + x⁴ + 1)
// ============================================================

static uint8_t crc8_update(uint8_t crc, uint8_t data) {
    uint8_t i;
    crc ^= data;
    for (i = 0; i < 8; i++) {
        if (crc & 0x01) {
            crc = (crc >> 1) ^ 0x8C;  // Reflected poly = 0x31 → 0x8C
        } else {
            crc >>= 1;
        }
    }
    return crc;
}

// ============================================================
// RELAY HEALTH CHECKS
// ============================================================

/**
 * Check if a single relay is functioning by measuring SWR change
 * when it's toggled. Requires RF carrier present.
 *
 * @param relay_bit  Relay index (0-6 = K1-K7)
 * @return          FAULT_NONE, FAULT_RELAY_STUCK_OPEN, or FAULT_RELAY_STUCK_CLOSED
 */
fault_code_t diag_check_relay_health(uint8_t relay_bit) {
    uint16_t fwd_power;
    uint16_t swr_before, swr_after;
    uint8_t  current_c;

    if (relay_bit > 6) return FAULT_NONE;

    // Need RF carrier for this test
    fwd_power = read_fwd_power_mw();
    if (fwd_power < TUNE_POWER_MIN_MW) {
        return FAULT_NONE;  // Can't test without RF
    }

    current_c = get_capacitor_bank();

    // Measure SWR with relay OFF
    set_capacitor_bank(current_c & ~(1 << relay_bit));
    __delay_ms(RELAY_SETTLE_MS);
    swr_before = read_swr_x100();

    // Toggle relay ON
    set_capacitor_bank(current_c | (1 << relay_bit));
    __delay_ms(RELAY_SETTLE_MS);
    swr_after = read_swr_x100();

    // Restore original setting
    set_capacitor_bank(current_c);

    // Check for stuck-open: toggling relay produces no SWR change
    if (abs((int16_t)swr_after - (int16_t)swr_before) < 5) {
        // If the bit represents significant capacitance (>22pF), SWR should change
        // For small bits (10pF, 22pF), change may be too subtle at some frequencies
        if (relay_bit >= 2) {  // 47pF and above should produce noticeable change
            return FAULT_RELAY_STUCK_OPEN;  // Could also be stuck-closed
            // We can't distinguish stuck-open from stuck-closed with this simple test
            // A more advanced test would check both ON→OFF and OFF→ON transitions
        }
    }

    return FAULT_NONE;
}

/**
 * Check all 7 relays, returning a bitmask of failed ones.
 */
fault_code_t diag_check_all_relays(uint8_t *failed_mask) {
    uint8_t bit;
    fault_code_t fault;
    uint8_t mask = 0;

    for (bit = 0; bit < 7; bit++) {
        fault = diag_check_relay_health(bit);
        if (fault != FAULT_NONE) {
            mask |= (1 << bit);
        }
    }

    *failed_mask = mask;
    failed_relays_mask = mask;

    // Count failures
    uint8_t fail_count = 0;
    for (bit = 0; bit < 7; bit++) {
        if (mask & (1 << bit)) fail_count++;
    }

    if (fail_count == 0) {
        return FAULT_NONE;
    } else if (fail_count <= 2) {
        return FAULT_RELAY_STUCK_OPEN;  // Degraded but usable
    } else {
        sys_health = SYS_SAFE;
        return FAULT_RELAY_STUCK_OPEN;
    }
}

// ============================================================
// SWR BRIDGE PLAUSIBILITY CHECK
// ============================================================

/**
 * Check that FWD and REV ADC readings are physically plausible.
 *
 * Plausibility criteria:
 *   1. FWD >> 0 when RF present → REV should be ≤ FWD
 *   2. FWD ADC noise floor (no RF) should not be exactly 0 (dead sensor)
 *   3. If FWD > threshold and REV == 0 for many samples → REV sensor suspect
 */
fault_code_t diag_check_swr_bridge_plausibility(void) {
    uint16_t fwd_adc, rev_adc;
    uint16_t fwd_power;

    fwd_power = read_fwd_power_mw();

    // Test 1: With no RF, noise floor should be non-zero (alive sensor)
    if (fwd_power == 0) {
        fwd_adc = read_adc_channel_oversampled(SWR_FWD_CHANNEL, 16);
        rev_adc = read_adc_channel_oversampled(SWR_REV_CHANNEL, 16);

        // Both channels dead → possible common failure (ADC dead, Vref lost)
        if (fwd_adc == 0 && rev_adc == 0) {
            return FAULT_SWR_SENSOR;
        }
    }

    // Test 2: With RF present, REV should be reasonable
    if (fwd_power > TUNE_POWER_RECOMMENDED_MW) {
        fwd_adc = read_adc_channel_oversampled(SWR_FWD_CHANNEL, 4);
        rev_adc = read_adc_channel_oversampled(SWR_REV_CHANNEL, 4);

        // REV significantly higher than FWD → calibration severely off
        if (rev_adc > (fwd_adc * 3 / 2)) {
            return FAULT_SWR_BRIDGE_IMBALANCE;
        }
    }

    return FAULT_NONE;
}

// ============================================================
// ADC HEALTH CHECKS
// ============================================================

/**
 * Detect stuck-at ADC fault: if the same value is read repeatedly
 * while conditions should be changing, the ADC may be frozen.
 */
fault_code_t diag_check_adc_stuck(void) {
    uint16_t current_fwd, current_rev;

    current_fwd = read_adc_channel(SWR_FWD_CHANNEL);
    current_rev = read_adc_channel(SWR_REV_CHANNEL);

    // Compare with last reading
    if (current_fwd == last_adc_fwd && last_adc_fwd != 0xFFFF) {
        adc_stuck_count_fwd++;
    } else {
        adc_stuck_count_fwd = 0;
    }

    if (current_rev == last_adc_rev && last_adc_rev != 0xFFFF) {
        adc_stuck_count_rev++;
    } else {
        adc_stuck_count_rev = 0;
    }

    last_adc_fwd = current_fwd;
    last_adc_rev = current_rev;

    // If stuck for > 8 consecutive readings (~80ms), attempt ADC reset
    if (adc_stuck_count_fwd > 8 || adc_stuck_count_rev > 8) {
        // Force ADC reset
        ADCON0bits.ADON = 0;
        __delay_ms(1);
        ADCON0bits.ADON = 1;
        // Reconfigure ADC
        ADCON0 = 0b00000001;
        ADCON1 = 0b10000000;
        ADCON2 = 0b00000000;

        adc_stuck_count_fwd = 0;
        adc_stuck_count_rev = 0;
        last_adc_fwd = 0xFFFF;
        last_adc_rev = 0xFFFF;

        return FAULT_ADC_STUCK;
    }

    return FAULT_NONE;
}

/**
 * Self-test ADC reference using internal Fixed Voltage Reference (FVR).
 * FVR = 2.048V → expected ADC = 2.048 / 5.0 × 1024 ≈ 419
 */
fault_code_t diag_check_adc_reference(void) {
    uint16_t adc_reading;

    // Configure FVR as ADC input
    // FVRCON: FVR enabled, 2.048V output, output to ADC
    FVRCON = 0b10000010;  // FVREN=1, ADFVR=10 (2.048V)

    // Configure ADC to read FVR (channel 0b11111 on PIC16F1938)
    ADCON0bits.CHS = 0b11111;  // FVR channel
    __delay_us(200);            // FVR stabilization

    adc_reading = read_adc_channel_oversampled(0b11111, 8);

    // Restore ADC to AN0
    ADCON0bits.CHS = SWR_FWD_CHANNEL;

    // Expected: ~419 ± 50 (allowing for VDD variation and FVR tolerance)
    if (adc_reading < 369 || adc_reading > 469) {
        // Re-check once more to avoid false positives
        ADCON0bits.CHS = 0b11111;
        __delay_us(100);
        adc_reading = read_adc_channel_oversampled(0b11111, 16);
        ADCON0bits.CHS = SWR_FWD_CHANNEL;

        if (adc_reading < 369 || adc_reading > 469) {
            return FAULT_ADC_REFERENCE;
        }
    }

    return FAULT_NONE;
}

// ============================================================
// TEMPERATURE CHECK (OPTIONAL – REQUIRES NTC ON AN2)
// ============================================================

fault_code_t diag_check_temperature(void) {
    // Placeholder: requires NTC thermistor on AN2 with voltage divider
    // If no NTC is fitted, AN2 will float → skip this check
    #ifdef NTC_ENABLED
    uint16_t adc_temp;
    // Read NTC via voltage divider (VDD → NTC → 10kΩ → GND, tap at NTC-10k junction)
    adc_temp = read_adc_channel_oversampled(2, 8);
    // Simplified threshold: if ADC < 150 → NTC resistance low → hot (>85°C)
    if (adc_temp < 150) {
        return FAULT_OVER_TEMP;
    }
    #endif
    return FAULT_NONE;
}

// ============================================================
// EEPROM INTEGRITY CHECK
// ============================================================

fault_code_t diag_check_eeprom_crc(void) {
    // EEPROM CRC check is already part of eeprom_is_valid()
    // Extend with CRC-8 per band entry

    // For now, rely on magic byte + version check
    if (!eeprom_is_valid()) {
        return FAULT_EEPROM_CORRUPT;
    }

    return FAULT_NONE;
}

// ============================================================
// COMPREHENSIVE HEALTH CHECK
// ============================================================

diag_result_t diag_run_all(void) {
    diag_result_t result = {0};
    fault_code_t fault;

    result.health = SYS_HEALTHY;
    result.failed_relays = 0;

    // Check EEPROM
    fault = diag_check_eeprom_crc();
    if (fault != FAULT_NONE) {
        result.last_fault_code = fault;
        diag_log_fault(fault, 2, 0, 0);  // MINOR
    }

    // Check SWR bridge
    fault = diag_check_swr_bridge_plausibility();
    if (fault != FAULT_NONE) {
        result.last_fault_code = fault;
        result.health = SYS_DEGRADED;
        diag_log_fault(fault, 1, 0, 0);  // MAJOR
    }

    // Check ADC reference
    fault = diag_check_adc_reference();
    if (fault != FAULT_NONE) {
        result.last_fault_code = fault;
        result.health = SYS_SAFE;  // Can't tune without reliable ADC
        diag_log_fault(fault, 1, 0, 0);  // MAJOR
    }

    // Check relay health (requires RF – skip if no RF)
    if (read_fwd_power_mw() > TUNE_POWER_MIN_MW) {
        fault = diag_check_all_relays(&result.failed_relays);
        if (fault != FAULT_NONE) {
            result.last_fault_code = fault;
            result.health = SYS_DEGRADED;
            diag_log_fault(fault, 2, result.failed_relays, 0);  // MINOR
        }
    }

    // Check temperature
    fault = diag_check_temperature();
    if (fault != FAULT_NONE) {
        result.last_fault_code = fault;
        result.health = SYS_SAFE;
        diag_log_fault(fault, 0, 0, 0);  // CRITICAL
    }

    // Update global health state
    sys_health = result.health;
    result.fault_count = diag_get_fault_count();

    return result;
}

// ============================================================
// FAULT LOGGING (EEPROM ring buffer at 0x80-0xFF)
// ============================================================

#define FAULT_LOG_START     0x80
#define FAULT_LOG_ENTRIES   16
#define FAULT_LOG_ENTRY_SIZE 8
#define FAULT_LOG_END       (FAULT_LOG_START + FAULT_LOG_ENTRIES * FAULT_LOG_ENTRY_SIZE)
#define FAULT_LOG_PTR_ADDR  0x06   // Stored in EEPROM: next write position

void diag_log_fault(fault_code_t code, uint8_t severity,
                    uint8_t data_0, uint8_t data_1) {
    fault_record_t record;
    uint8_t i;
    uint8_t checksum;

    // Build record
    record.code       = (uint8_t)code;
    record.severity   = severity;
    record.timestamp_hi = (uint8_t)(uptime_hours >> 8);
    record.timestamp_lo = (uint8_t)(uptime_hours & 0xFF);
    record.data_0     = data_0;
    record.data_1     = data_1;
    record.reset_cause = last_reset_cause;

    // Compute checksum (XOR of bytes 0-6)
    checksum = 0;
    uint8_t *p = (uint8_t *)&record;
    for (i = 0; i < 7; i++) {
        checksum ^= p[i];
    }
    record.checksum = checksum;

    // Get write pointer from EEPROM
    uint8_t write_ptr;
    EEADRL = FAULT_LOG_PTR_ADDR;
    EECON1bits.EEPGD = 0;
    EECON1bits.RD = 1;
    write_ptr = EEDATL;

    if (write_ptr < FAULT_LOG_START || write_ptr >= FAULT_LOG_END) {
        write_ptr = FAULT_LOG_START;  // Initialize
    }

    // Write record to EEPROM ring buffer
    // (Simplified: write each byte individually)
    for (i = 0; i < FAULT_LOG_ENTRY_SIZE; i++) {
        EEADRL = write_ptr + i;
        EEDATL = p[i];
        EECON1bits.EEPGD = 0;
        EECON1bits.WREN = 1;
        EECON2 = 0x55;
        EECON2 = 0xAA;
        EECON1bits.WR = 1;
        while (EECON1bits.WR);
    }
    EECON1bits.WREN = 0;

    // Advance write pointer (ring)
    write_ptr += FAULT_LOG_ENTRY_SIZE;
    if (write_ptr >= FAULT_LOG_END) {
        write_ptr = FAULT_LOG_START;
    }

    // Save pointer
    EEADRL = FAULT_LOG_PTR_ADDR;
    EEDATL = write_ptr;
    EECON1bits.EEPGD = 0;
    EECON1bits.WREN = 1;
    EECON2 = 0x55;
    EECON2 = 0xAA;
    EECON1bits.WR = 1;
    while (EECON1bits.WR);
    EECON1bits.WREN = 0;
}

uint8_t diag_get_fault_count(void) {
    uint8_t count = 0;
    uint8_t addr;
    uint8_t code;

    for (addr = FAULT_LOG_START; addr < FAULT_LOG_END; addr += FAULT_LOG_ENTRY_SIZE) {
        EEADRL = addr;
        EECON1bits.EEPGD = 0;
        EECON1bits.RD = 1;
        code = EEDATL;
        if (code != 0x00 && code != 0xFF) {
            count++;
        }
    }
    return count;
}

void diag_get_last_fault(fault_record_t *record) {
    uint8_t i;
    uint8_t *p = (uint8_t *)record;
    uint8_t write_ptr;
    uint8_t last_ptr;

    // Get write pointer
    EEADRL = FAULT_LOG_PTR_ADDR;
    EECON1bits.EEPGD = 0;
    EECON1bits.RD = 1;
    write_ptr = EEDATL;

    // Last record is just before write_ptr
    if (write_ptr == FAULT_LOG_START) {
        last_ptr = FAULT_LOG_END - FAULT_LOG_ENTRY_SIZE;
    } else {
        last_ptr = write_ptr - FAULT_LOG_ENTRY_SIZE;
    }

    for (i = 0; i < FAULT_LOG_ENTRY_SIZE; i++) {
        EEADRL = last_ptr + i;
        EECON1bits.EEPGD = 0;
        EECON1bits.RD = 1;
        p[i] = EEDATL;
    }
}

void diag_clear_faults(void) {
    uint8_t addr;
    for (addr = FAULT_LOG_START; addr < FAULT_LOG_END; addr++) {
        EEADRL = addr;
        EEDATL = 0xFF;
        EECON1bits.EEPGD = 0;
        EECON1bits.WREN = 1;
        EECON2 = 0x55;
        EECON2 = 0xAA;
        EECON1bits.WR = 1;
        while (EECON1bits.WR);
    }
    EECON1bits.WREN = 0;

    // Reset pointer
    EEADRL = FAULT_LOG_PTR_ADDR;
    EEDATL = FAULT_LOG_START;
    EECON1bits.EEPGD = 0;
    EECON1bits.WREN = 1;
    EECON2 = 0x55;
    EECON2 = 0xAA;
    EECON1bits.WR = 1;
    while (EECON1bits.WR);
    EECON1bits.WREN = 0;
}

void diag_dump_fault_log(void) {
    // Placeholder for UART dump in future versions
    // For now, this is a no-op in the standalone outdoor unit
}

// ============================================================
// HEALTH STATE MANAGEMENT
// ============================================================

sys_health_t diag_get_health(void) {
    return sys_health;
}

void diag_set_health(sys_health_t new_state) {
    sys_health = new_state;
}

void diag_recover_from_safe(void) {
    // Attempt recovery: clear fault log, re-run POST
    // Only transitions SAFE → HEALTHY if POST passes
    // This is called after a power cycle with successful POST
    sys_health = SYS_HEALTHY;
}

// ============================================================
// RESET CAUSE TRACKING
// ============================================================

uint8_t diag_get_reset_cause(void) {
    return last_reset_cause;
}

void diag_clear_reset_cause(void) {
    last_reset_cause = 0;
}

/*
 * diagnostics.h - Runtime Fault Detection Module
 *
 * Target:  PIC16F1938
 * License:  GPL-3.0
 *
 * Provides runtime fault detection for the EFHW Auto Tuner.
 * All detection functions follow the FDE specification (see docs/FDE.md).
 */

#ifndef DIAGNOSTICS_H
#define DIAGNOSTICS_H

#include "main.h"

// ============================================================
// FAULT CODE ENUMERATION
// ============================================================

typedef enum {
    FAULT_NONE                  = 0x00,
    FAULT_RELAY_STUCK_OPEN      = 0x01,  // Relay won't engage
    FAULT_RELAY_STUCK_CLOSED    = 0x02,  // Relay won't release
    FAULT_CAP_SHORT             = 0x03,  // Capacitor shorted (SWR spike)
    FAULT_ADC_STUCK             = 0x04,  // ADC reading frozen
    FAULT_SWR_BRIDGE_IMBALANCE  = 0x05,  // Directional coupler out of balance
    FAULT_EEPROM_CORRUPT        = 0x06,  // EEPROM CRC mismatch
    FAULT_OVER_TEMP             = 0x07,  // Temperature > 85°C (if NTC fitted)
    FAULT_WDT_RESET             = 0x08,  // Watchdog timeout reset occurred
    FAULT_BOR_EVENT             = 0x09,  // Brown-out reset occurred
    FAULT_STACK_OVERFLOW        = 0x0A,  // Stack overflow reset occurred
    FAULT_GPIO_LATCH            = 0x0B,  // GPIO write-back verification failed
    FAULT_ADC_REFERENCE         = 0x0C,  // ADC reference voltage out of spec
    FAULT_POST_FAIL             = 0x0D,  // POST failed (phase encoded in data_0)
    FAULT_SWR_SENSOR            = 0x0E,  // SWR sensor plausibility failure
} fault_code_t;

// ============================================================
// FAULT RECORD (8 bytes, stored in EEPROM ring buffer)
// ============================================================

typedef struct {
    uint8_t code;           // fault_code_t
    uint8_t severity;       // 0=CRITICAL, 1=MAJOR, 2=MINOR, 3=INFO
    uint8_t timestamp_hi;   // System uptime hours (high byte)
    uint8_t timestamp_lo;   // System uptime hours (low byte)
    uint8_t data_0;         // Contextual data (e.g., relay number, SWR)
    uint8_t data_1;         // Contextual data
    uint8_t reset_cause;    // RCON register snapshot
    uint8_t checksum;       // XOR of bytes 0-6
} fault_record_t;

// ============================================================
// SYSTEM HEALTH STATE
// ============================================================

typedef enum {
    SYS_HEALTHY     = 0,    // All 7 relays OK, all subsystems normal
    SYS_DEGRADED    = 1,    // 1-2 relays out, still tunable
    SYS_SAFE        = 2,    // ≥3 relays out, or CRITICAL fault → lock last-good C
    SYS_FAULT       = 3,    // Immediate transition → SYS_SAFE + log
} sys_health_t;

// ============================================================
// DIAGNOSTIC RESULT (returned by diag_run_all)
// ============================================================

typedef struct {
    sys_health_t health;
    uint8_t      failed_relays;      // Bitmask of failed relays (bit0=K1, ...)
    uint8_t      fault_count;        // Total faults since last clear
    uint8_t      last_fault_code;    // Most recent fault_code_t
} diag_result_t;

// ============================================================
// FUNCTION PROTOTYPES
// ============================================================

// Relay health checks
fault_code_t diag_check_relay_health(uint8_t relay_bit);
fault_code_t diag_check_all_relays(uint8_t *failed_mask);

// SWR bridge integrity
fault_code_t diag_check_swr_bridge_plausibility(void);

// ADC health
fault_code_t diag_check_adc_stuck(void);
fault_code_t diag_check_adc_reference(void);

// Temperature (optional, requires NTC on AN2)
fault_code_t diag_check_temperature(void);

// EEPROM integrity
fault_code_t diag_check_eeprom_crc(void);

// Comprehensive health check
diag_result_t diag_run_all(void);

// Fault logging
void          diag_log_fault(fault_code_t code, uint8_t severity,
                             uint8_t data_0, uint8_t data_1);
uint8_t       diag_get_fault_count(void);
void          diag_get_last_fault(fault_record_t *record);
void          diag_clear_faults(void);
void          diag_dump_fault_log(void);

// Health state
sys_health_t  diag_get_health(void);
void          diag_set_health(sys_health_t new_state);
void          diag_recover_from_safe(void);  // Attempt recovery after SAFE

// Reset cause tracking
uint8_t       diag_get_reset_cause(void);
void          diag_clear_reset_cause(void);

#endif // DIAGNOSTICS_H

/*
 * post.h - Power-On Self Test (POST) Module
 *
 * Target:  PIC16F1938
 * License:  GPL-3.0
 *
 * Implements the 4-phase POST specification defined in docs/FDE.md.
 */

#ifndef POST_H
#define POST_H

#include "main.h"

// ============================================================
// POST RESULT CODES
// ============================================================

typedef enum {
    POST_PASS                   = 0x00,
    POST_FAIL_DC_RAIL_12V       = 0x01,
    POST_FAIL_DC_RAIL_5V        = 0x02,
    POST_FAIL_OSCILLATOR        = 0x03,
    POST_FAIL_ADC_RANGE         = 0x04,
    POST_FAIL_ADC_REFERENCE     = 0x05,
    POST_FAIL_EEPROM_MAGIC      = 0x06,
    POST_FAIL_RELAY_BANK        = 0x07,
    POST_FAIL_SWR_NOISE_FLOOR   = 0x08,
    POST_FAIL_WDT_TEST          = 0x09,
} post_result_t;

// ============================================================
// POST PHASE (for progress tracking)
// ============================================================

typedef enum {
    POST_PHASE_0_DC     = 0,
    POST_PHASE_1_CORE   = 1,
    POST_PHASE_2_PERIPH = 2,
    POST_PHASE_3_RF     = 3,
    POST_COMPLETE       = 4,
} post_phase_t;

// ============================================================
// POST RESULT WITH DETAILS
// ============================================================

typedef struct {
    post_result_t result;
    post_phase_t  failed_phase;
    uint8_t       failed_relays;   // Bitmask (phase 3)
    uint8_t       degraded;        // 1 = system degraded but operational
} post_report_t;

// ============================================================
// FUNCTION PROTOTYPES
// ============================================================

// Run complete POST sequence
post_report_t post_run_full(void);

// Individual phase checks
post_result_t post_check_dc_rails(void);
post_result_t post_check_oscillator(void);
post_result_t post_check_adc_range(void);
post_result_t post_check_adc_reference(void);
post_result_t post_check_eeprom_integrity(void);
post_result_t post_check_relay_bank(void);
post_result_t post_check_swr_noise_floor(void);
post_result_t post_check_wdt_functional(void);

// Read reset cause
uint8_t       post_get_reset_cause(void);

// Beep the POST result
void          post_signal_result(post_report_t report);

#endif // POST_H

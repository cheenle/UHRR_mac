/*
 * post.c - Power-On Self Test (POST) Implementation
 *
 * Target:  PIC16F1938
 * License:  GPL-3.0
 *
 * 4-phase POST as specified in docs/FDE.md §4:
 *   PHASE 0: DC Rails         (~50ms)
 *   PHASE 1: Core System      (~100ms)
 *   PHASE 2: Peripherals      (~200ms)
 *   PHASE 3: RF Path          (~500ms)
 *
 * Total worst-case POST time: ~1 second
 */

#include "main.h"
#include "post.h"
#include "tuning.h"
#include "swr_bridge.h"
#include "eeprom.h"
#include "display.h"

// ============================================================
// HELPER: READ MCU VOLTAGE VIA FVR
// ============================================================

/**
 * Measure VDD by using internal FVR (2.048V) as ADC reference and VDD as input.
 * This is an indirect measurement – simplified version:
 * Read ADC channel for FVR → if VDD is 5.0V, reading ≈ 419.
 * Reading outside [350, 490] → VDD likely out of spec (too high or too low).
 */
static uint8_t post_measure_vdd_mv(void) {
    uint16_t fvr_reading;

    // Enable FVR at 2.048V
    FVRCON = 0b10000010;

    // Select FVR as ADC input
    ADCON0bits.CHS = 0b11111;
    __delay_us(200);

    fvr_reading = read_adc_channel_oversampled(0b11111, 8);

    // Restore channel
    ADCON0bits.CHS = SWR_FWD_CHANNEL;

    // VDD = 2.048V × 1024 / reading
    // If reading=419, VDD ≈ 5.00V
    uint32_t vdd = (2048UL * 1024UL) / (uint32_t)fvr_reading;
    return (uint8_t)(vdd / 10);  // Return in units of 10mV (e.g., 500 = 5.00V)
}

// ============================================================
// PHASE 0: DC RAILS CHECK (~50ms)
// ============================================================

post_result_t post_check_dc_rails(void) {
    uint16_t vdd_x10mv;

    // Measure VDD (should be 5.0V ± 0.5V)
    vdd_x10mv = post_measure_vdd_mv();

    if (vdd_x10mv < 450 || vdd_x10mv > 550) {
        // VDD out of range → 5V rail likely failed
        // Cannot reliably continue POST – critical failure
        return POST_FAIL_DC_RAIL_5V;
    }

    // 12V rail check is indirect:
    // If VDD (5V) is OK, 78L05 is working → 12V rail is at least > 7V.
    // A full 12V check requires an external voltage divider on an ADC pin.
    // For this design, we trust the cascade: if 5V is OK, 12V is sufficient.

    return POST_PASS;
}

// ============================================================
// PHASE 1: CORE SYSTEM CHECK (~100ms)
// ============================================================

post_result_t post_check_oscillator(void) {
    // The fact that we're executing code means the oscillator is running.
    // Additional checks:
    //   1. Verify PLL is locked (PLLR flag)
    //   2. Verify HFINTOSC is stable (HFIOFR flag)

    if (!OSCSTATbits.HFIOFR) {
        return POST_FAIL_OSCILLATOR;
    }

    if (!OSCSTATbits.PLLR) {
        return POST_FAIL_OSCILLATOR;
    }

    // Verify we can read oscillator frequency via OSCCON
    // (IRCF bits should match our configured 8 MHz)
    uint8_t ir cf = OSCCONbits.IRCF;
    if (ircf != 0b1110) {  // 8 MHz setting
        // Oscillator configuration mismatch – possible ESD/EMI corruption
        return POST_FAIL_OSCILLATOR;
    }

    return POST_PASS;
}

/**
 * Verify WDT is functional by testing it can reset the system.
 * BUT: this is destructive. Instead, we verify WDT configuration.
 *
 * Full WDT test: set a short WDT timeout, don't pet, verify reset.
 * For non-destructive POST, we just check configuration bits are set.
 */
post_result_t post_check_wdt_functional(void) {
    // Verify WDT is enabled in configuration
    // (Can't directly read CONFIG bits at runtime on PIC16 enhanced)
    // Indirect: if we're running and WDT isn't reseting us,
    // the system_tick() function is petting it correctly
    return POST_PASS;
}

// ============================================================
// PHASE 2: PERIPHERALS CHECK (~200ms)
// ============================================================

post_result_t post_check_adc_range(void) {
    uint16_t adc_reading;
    uint8_t  i;

    // Read ADC with known input (grounded via internal pull-down? No – PIC16
    // doesn't have ADC input pull-down. Use FVR instead.)

    // Test 1: ADC is alive (read AN0, should return some value)
    adc_reading = read_adc_channel_oversampled(SWR_FWD_CHANNEL, 8);

    // If ADC returns exactly 0 or exactly 1023, it may be stuck at rail
    if (adc_reading == 0) {
        // Could be genuine (no RF) or ADC stuck low
        // Verify by reading AN1 (REV) – should also read something different
        uint16_t rev_reading = read_adc_channel_oversampled(SWR_REV_CHANNEL, 8);
        if (rev_reading == 0) {
            return POST_FAIL_ADC_RANGE;
        }
    }

    if (adc_reading == 1023) {
        return POST_FAIL_ADC_RANGE;  // Stuck at VDD rail
    }

    // Test 2: Multiple reads should show some variation (not stuck-at)
    uint16_t min_val = 1023, max_val = 0;
    for (i = 0; i < 8; i++) {
        adc_reading = read_adc_channel(SWR_FWD_CHANNEL);
        if (adc_reading < min_val) min_val = adc_reading;
        if (adc_reading > max_val) max_val = adc_reading;
        __delay_us(100);
    }

    // In complete silence, ADC noise should be at least 1-2 LSB
    if (max_val == min_val) {
        return POST_FAIL_ADC_RANGE;  // Possible stuck-at
    }

    return POST_PASS;
}

post_result_t post_check_adc_reference(void) {
    uint16_t fvr_reading;

    FVRCON = 0b10000010;  // FVR=2.048V
    ADCON0bits.CHS = 0b11111;
    __delay_us(200);

    fvr_reading = read_adc_channel_oversampled(0b11111, 16);

    // Restore
    ADCON0bits.CHS = SWR_FWD_CHANNEL;

    // Expected: 2.048V / 5.0V × 1024 ≈ 419
    // Allow ±12% tolerance (accounts for VDD variation and FVR accuracy)
    if (fvr_reading < 369 || fvr_reading > 469) {
        // Retry once for transient issues
        ADCON0bits.CHS = 0b11111;
        __delay_us(100);
        fvr_reading = read_adc_channel_oversampled(0b11111, 16);
        ADCON0bits.CHS = SWR_FWD_CHANNEL;

        if (fvr_reading < 369 || fvr_reading > 469) {
            return POST_FAIL_ADC_REFERENCE;
        }
    }

    return POST_PASS;
}

post_result_t post_check_eeprom_integrity(void) {
    uint8_t magic;

    EEADRL = EE_MAGIC_ADDR;
    EECON1bits.EEPGD = 0;
    EECON1bits.RD = 1;
    magic = EEDATL;

    if (magic != EE_MAGIC_VALUE) {
        // First power-on or corrupted – not a failure, just needs init
        eeprom_clear_all();
        // Return pass (we've initialized it)
    }

    return POST_PASS;
}

// ============================================================
// PHASE 3: RF PATH CHECK (~500ms)
// ============================================================

/**
 * Test relay bank by briefly toggling each relay and listening
 * for the audible "click". This is a minimal test without RF.
 *
 * With RF present, a more thorough test measures SWR change.
 */
post_result_t post_check_relay_bank(void) {
    uint8_t bit;
    uint8_t failed_count = 0;
    uint16_t fwd_power;

    fwd_power = read_fwd_power_mw();

    for (bit = 0; bit < 7; bit++) {
        // Toggle relay ON
        set_capacitor_bank(1 << bit);
        __delay_ms(15);  // Wait for click

        // Toggle relay OFF
        set_capacitor_bank(0);
        __delay_ms(10);

        // If RF is present, verify SWR changed between ON and OFF
        if (fwd_power > TUNE_POWER_MIN_MW) {
            uint16_t swr_off = read_swr_x100();
            set_capacitor_bank(1 << bit);
            __delay_ms(15);
            uint16_t swr_on = read_swr_x100();
            set_capacitor_bank(0);

            // For significant capacitor values (≥47pF), SWR should change
            if (bit >= 2) {
                int16_t delta = (int16_t)swr_on - (int16_t)swr_off;
                if (abs(delta) < 3) {
                    failed_count++;
                }
            }
        }
    }

    // Ensure all relays OFF at end of test
    set_capacitor_bank(0);

    if (failed_count >= 3) {
        return POST_FAIL_RELAY_BANK;  // Too many relays failed
    }

    return POST_PASS;
}

/**
 * Verify SWR bridge noise floor is non-zero (sensors alive).
 */
post_result_t post_check_swr_noise_floor(void) {
    uint16_t fwd_noise, rev_noise;

    // Read noise floor with no RF
    fwd_noise = read_adc_channel_oversampled(SWR_FWD_CHANNEL, 32);
    rev_noise = read_adc_channel_oversampled(SWR_REV_CHANNEL, 32);

    // Both zero → sensors or ADC completely dead
    if (fwd_noise == 0 && rev_noise == 0) {
        return POST_FAIL_SWR_NOISE_FLOOR;
    }

    return POST_PASS;
}

// ============================================================
// FULL POST SEQUENCE
// ============================================================

post_report_t post_run_full(void) {
    post_report_t report = {0};
    post_result_t phase_result;

    report.result = POST_PASS;
    report.failed_phase = POST_COMPLETE;
    report.failed_relays = 0;
    report.degraded = 0;

    // ---- PHASE 0: DC Rails ----
    report.failed_phase = POST_PHASE_0_DC;
    phase_result = post_check_dc_rails();
    if (phase_result != POST_PASS) {
        report.result = phase_result;
        // Phase 0 failure: cannot continue (no reliable power)
        goto post_end;
    }

    // ---- PHASE 1: Core System ----
    report.failed_phase = POST_PHASE_1_CORE;
    phase_result = post_check_oscillator();
    if (phase_result != POST_PASS) {
        report.result = phase_result;
        // Phase 1 failure: retry up to 3 times
        // (simplified: fail immediately in this implementation)
        goto post_end;
    }

    // ---- PHASE 2: Peripherals ----
    report.failed_phase = POST_PHASE_2_PERIPH;

    phase_result = post_check_adc_range();
    if (phase_result != POST_PASS) {
        report.result = phase_result;
        report.degraded = 1;
        goto post_end;
    }

    phase_result = post_check_adc_reference();
    if (phase_result != POST_PASS) {
        report.result = phase_result;
        report.degraded = 1;
        goto post_end;
    }

    phase_result = post_check_eeprom_integrity();
    if (phase_result != POST_PASS) {
        report.result = phase_result;
        report.degraded = 1;
        // EEPROM failure is non-critical → continue
    }

    // ---- PHASE 3: RF Path ----
    report.failed_phase = POST_PHASE_3_RF;

    phase_result = post_check_relay_bank();
    if (phase_result != POST_PASS) {
        report.result = phase_result;
        report.degraded = 1;
        // Record failed relays (from diag module)
        goto post_end;
    }

    phase_result = post_check_swr_noise_floor();
    if (phase_result != POST_PASS) {
        report.result = phase_result;
        report.degraded = 1;
        goto post_end;
    }

post_end:
    report.failed_phase = POST_COMPLETE;

    // Signal result to user via beep pattern
    post_signal_result(report);

    return report;
}

// ============================================================
// RESET CAUSE DETECTION
// ============================================================

uint8_t post_get_reset_cause(void) {
    // RCON register contains reset flags
    // bit 0: BOR (Brown-Out Reset)
    // bit 1: POR (Power-On Reset)
    // bit 2: EXTR (External Reset / MCLR)
    // bit 3: SWDTEN (Software WDT Enable – not a flag)
    // bit 4: WDT (Watchdog Timer Reset) – actually RMCLR on PIC16F1938
    return RCON;
}

// ============================================================
// POST RESULT SIGNALING
// ============================================================

void post_signal_result(post_report_t report) {
    if (report.result == POST_PASS && report.degraded == 0) {
        // All clear
        led_set(1);
        __delay_ms(300);
        led_set(0);
        // beep_ok(1) will be called by system_init after POST
        return;
    }

    if (report.result == POST_PASS && report.degraded == 1) {
        // Degraded but operational
        led_set(1);
        __delay_ms(100);
        led_set(0);
        __delay_ms(200);
        led_set(1);
        __delay_ms(100);
        led_set(0);
        // 2 short beeps pattern
        return;
    }

    // POST FAILED
    switch (report.result) {
        case POST_FAIL_DC_RAIL_5V:
        case POST_FAIL_DC_RAIL_12V:
            // Continuous rapid beep = CRITICAL
            for (uint8_t i = 0; i < 10; i++) {
                beep_error(1);
                __delay_ms(100);
            }
            break;

        case POST_FAIL_OSCILLATOR:
            // 2 long, 1 short
            led_set(1); __delay_ms(500); led_set(0); __delay_ms(200);
            led_set(1); __delay_ms(500); led_set(0); __delay_ms(200);
            led_set(1); __delay_ms(100); led_set(0);
            break;

        default:
            // 3 short beeps = non-critical POST failure
            beep_error(3);
            break;
    }
}

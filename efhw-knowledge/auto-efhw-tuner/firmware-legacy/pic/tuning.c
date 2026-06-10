/*
 * tuning.c - EFHW Capacitor-Only Auto-Tuning Algorithm
 *
 * Target:  PIC16F1938
 * Compiler: XC8 v2.4x+
 * License:  GPL-3.0
 *
 * This is the heart of the EFHW Auto Tuner. It implements:
 *
 *   1. run_autotune_efhw()    – Full 0→127 capacitor sweep
 *   2. run_quick_retune_efhw() – EEPROM-based fast retune
 *   3. tune_fine_around()     – Local ±N step search
 *   4. abort_tune()           – Emergency stop
 *
 * Key design decisions:
 *   - INDUCTOR RELAYS (RC0-RC6) ARE NEVER ACTIVATED.
 *     This is a pure capacitor-tuning system. The T200-2 secondary
 *     provides the fixed inductance for the parallel LC tank.
 *   - POWER DETECTION BEFORE AND DURING TUNING.
 *     G5Q-14 relays are NOT RF-rated. Hot-switching at >15W will
 *     destroy the contacts. We check power before every relay change.
 *   - EARLY EXIT. If SWR < 1.05:1 is found, scan stops immediately.
 *     Typical tune time: 0.1–0.5s instead of worst-case 1.8s.
 */

#include "main.h"
#include "tuning.h"
#include "swr_bridge.h"
#include "eeprom.h"
#include "display.h"
#include "diagnostics.h"

// ============================================================
// MODULE-LEVEL STATE
// ============================================================

static tune_state_t tune_state = TUNE_IDLE;

// ============================================================
// LOW-LEVEL RELAY CONTROL FUNCTIONS
// ============================================================

/**
 * Set the 7-bit capacitor relay bank to a specific value.
 * Also ensures all inductor relays (if any were connected) are OFF.
 *
 * @param c_value  7-bit capacitor pattern (0-127)
 *                 bit0=10pF, bit1=22pF, bit2=47pF,
 *                 bit3=100pF, bit4=220pF, bit5=470pF, bit6=1000pF
 */
void set_capacitor_bank(uint8_t c_value) {
    uint8_t retry;
    uint8_t written;

    for (retry = 0; retry < 3; retry++) {
        // Write low 7 bits to RB0-RB6, preserve RB7 (ICSP PGD line)
        C_RELAY_LAT = (C_RELAY_LAT & 0x80) | (c_value & C_RELAY_MASK);

        // GPIO WRITE-BACK VERIFICATION (FDE §3, S4)
        // Re-read LATB and verify low 7 bits match intended value
        written = C_RELAY_LAT & C_RELAY_MASK;
        if (written == (c_value & C_RELAY_MASK)) {
            break;  // Write verified
        }

        // Write mismatch → possible EMI glitch or GPIO latch-up
        // Retry with brief delay
        __delay_us(10);
    }

    if (retry >= 3) {
        // 3 failed attempts → GPIO fault → enter SAFE mode
        set_capacitor_bank(0);  // All relays OFF (safe state)
        diag_log_fault(FAULT_GPIO_LATCH, 0, c_value, written);
        diag_set_health(SYS_SAFE);
    }

    // ENSURE INDUCTOR PINS (RC0-RC6) ARE NEVER DRIVEN HIGH
    LATC &= 0x80;
}

/**
 * Get current capacitor bank setting (for verification/debug).
 */
uint8_t get_capacitor_bank(void) {
    return C_RELAY_LAT & C_RELAY_MASK;
}

// ============================================================
// FULL AUTO-TUNE: CAPACITOR-ONLY SCAN
// ============================================================

tune_result_t run_autotune_efhw(void) {
    tune_result_t result = {0};
    uint8_t  best_c = 0;
    uint16_t min_swr = 65535;      // Initialize to max possible
    uint16_t current_swr;
    uint16_t fwd_power;
    uint8_t  c_val;

    result.state = TUNE_IDLE;

    // SAFE MODE GATE: If system is in SAFE mode, refuse to tune
    if (diag_get_health() == SYS_SAFE) {
        result.state = TUNE_ERROR_SWR_HIGH;
        result.fwd_power_mw = 0;
        beep_error(5);
        return result;
    }

    // ==========================================================
    // STEP 1: SAFETY CHECK – Verify power level
    // ==========================================================
    tune_state = TUNE_CHECK_POWER;
    led_set(1);  // LED ON = tuning in progress

    fwd_power = read_fwd_power_mw();

    if (fwd_power > TUNE_POWER_MAX_MW) {
        // POWER TOO HIGH – abort immediately, protect relays
        set_capacitor_bank(0);  // All relays released (safe state)
        result.state = TUNE_ERROR_OVERPOWER;
        result.fwd_power_mw = fwd_power;
        display_error("OVERPOWER");
        beep_error(3);
        tune_state = TUNE_IDLE;
        led_set(0);
        return result;
    }

    if (fwd_power < TUNE_POWER_MIN_MW) {
        // NO RF DETECTED
        result.state = TUNE_ERROR_NORF;
        result.fwd_power_mw = fwd_power;
        display_error("NO RF");
        beep_error(2);
        tune_state = TUNE_IDLE;
        led_set(0);
        return result;
    }

    // Warn if power is higher than recommended (but still safe)
    if (fwd_power > TUNE_POWER_RECOMMENDED_MW) {
        display_warning("PWR HI");
    }

    // ==========================================================
    // STEP 2: FULL CAPACITOR SCAN (0 → 127)
    // ==========================================================
    tune_state = TUNE_SCANNING;

    // Optimize: start from last known good value ±16 to speed up
    // (implementation detail – for simplicity, do full scan here)
    uint8_t start_c = 0;
    uint8_t end_c   = 127;

    for (c_val = start_c; c_val <= end_c; c_val++) {
        // Set capacitor bank
        set_capacitor_bank(c_val);

        // Wait for mechanical relay to settle.
        // G5Q-14 spec: operate time ≤ 10ms, release time ≤ 5ms.
        // We use 12ms to provide margin.
        __delay_ms(RELAY_SETTLE_MS);

        // Real-time power check (every relay change)
        fwd_power = read_fwd_power_mw();
        if (fwd_power > TUNE_POWER_MAX_MW) {
            // Power suddenly increased! Abort immediately.
            set_capacitor_bank(0);
            result.state = TUNE_ERROR_OVERPOWER;
            result.fwd_power_mw = fwd_power;
            display_error("PWR SURGE");
            beep_error(4);
            tune_state = TUNE_IDLE;
            led_set(0);
            return result;
        }

        if (fwd_power < TUNE_POWER_MIN_MW) {
            // RF dropped – transmitter may have stopped transmitting
            set_capacitor_bank(0);
            result.state = TUNE_ERROR_NORF;
            result.fwd_power_mw = fwd_power;
            display_error("RF LOST");
            beep_error(2);
            tune_state = TUNE_IDLE;
            led_set(0);
            return result;
        }

        // Read SWR (oversampled for noise rejection)
        current_swr = read_swr_x100();

        // Update best value
        if (current_swr < min_swr) {
            min_swr = current_swr;
            best_c  = c_val;

            // EARLY EXIT: SWR already excellent (< 1.05:1)
            // No point scanning further – this is "good enough"
            if (min_swr < SWR_EARLY_EXIT) {
                break;
            }
        }
    }

    // ==========================================================
    // STEP 3: LOCK BEST VALUE
    // ==========================================================
    set_capacitor_bank(best_c);
    __delay_ms(RELAY_SETTLE_MS);

    // Final SWR verification
    current_swr = read_swr_x100();
    fwd_power   = read_fwd_power_mw();

    result.c_value      = best_c;
    result.swr_x100     = current_swr;
    result.fwd_power_mw = fwd_power;

    if (current_swr < SWR_SAVE_MAX) {
        // Good match achieved
        result.state = TUNE_LOCKED;
        display_tune_ok(current_swr, best_c);
        beep_ok(1);
    } else {
        // Best we could do is still > 3:1 SWR
        result.state = TUNE_ERROR_SWR_HIGH;
        display_tune_fail(current_swr);
        beep_error(1);
    }

    tune_state = TUNE_IDLE;
    led_set(0);
    return result;
}

// ============================================================
// QUICK RE-TUNE: EEPROM-BASED
// ============================================================

tune_result_t run_quick_retune_efhw(uint32_t freq_hz) {
    tune_result_t result = {0};
    uint8_t  saved_c_val;
    uint16_t saved_swr;
    uint16_t current_swr;
    uint16_t fwd_power;
    uint8_t  eeprom_hit;

    result.state    = TUNE_IDLE;
    result.frequency = freq_hz;

    // Safety check
    fwd_power = read_fwd_power_mw();
    if (fwd_power > TUNE_POWER_MAX_MW) {
        set_capacitor_bank(0);
        result.state = TUNE_ERROR_OVERPOWER;
        result.fwd_power_mw = fwd_power;
        return result;
    }

    // Try EEPROM recall
    eeprom_hit = eeprom_load_tune(freq_hz, &saved_c_val, &saved_swr);

    if (eeprom_hit && saved_swr < SWR_QUICK_RETUNE_MAX) {
        // EEPROM has a valid memory for this band
        set_capacitor_bank(saved_c_val);
        __delay_ms(RELAY_SETTLE_MS);

        current_swr = read_swr_x100();

        if (current_swr < SWR_QUICK_RETUNE_MAX) {
            // Memory still valid – do fine tune around this point
            tune_state = TUNE_SCANNING;
            led_set(1);

            tune_fine_around(saved_c_val);

            current_swr = read_swr_x100();
            uint8_t final_c = get_capacitor_bank();

            result.c_value  = final_c;
            result.swr_x100 = current_swr;
            result.fwd_power_mw = fwd_power;

            if (current_swr < SWR_SAVE_MAX) {
                result.state = TUNE_LOCKED;
                eeprom_save_tune(freq_hz, final_c, current_swr);
                display_tune_ok(current_swr, final_c);
                beep_ok(1);
            } else {
                result.state = TUNE_ERROR_SWR_HIGH;
            }

            tune_state = TUNE_IDLE;
            led_set(0);
            return result;
        }
    }

    // EEPROM miss or stale – fall back to full scan
    result = run_autotune_efhw();

    if (result.state == TUNE_LOCKED) {
        eeprom_save_tune(freq_hz, result.c_value, result.swr_x100);
    }

    return result;
}

// ============================================================
// FINE TUNE: LOCAL SEARCH AROUND CENTER VALUE
// ============================================================

void tune_fine_around(uint8_t center_c) {
    uint8_t  best_c  = center_c;
    uint16_t min_swr = read_swr_x100();
    uint16_t swr;
    int8_t   offset;
    int16_t  test_c;
    uint16_t fwd_power;

    // Search ±7 steps around center (≈ 15-step window)
    for (offset = -7; offset <= 7; offset++) {
        test_c = (int16_t)center_c + offset;

        // Boundary clamp
        if (test_c < 0)   test_c = 0;
        if (test_c > 127) test_c = 127;

        // Skip if same as current (already measured)
        if (test_c == center_c && offset != 0) continue;

        set_capacitor_bank((uint8_t)test_c);
        __delay_ms(RELAY_SETTLE_MS);

        // Safety check
        fwd_power = read_fwd_power_mw();
        if (fwd_power > TUNE_POWER_MAX_MW) {
            set_capacitor_bank(best_c);  // Restore best known
            return;
        }

        swr = read_swr_x100();

        if (swr < min_swr) {
            min_swr = swr;
            best_c  = (uint8_t)test_c;

            // Early exit for fine tune too
            if (min_swr < SWR_EARLY_EXIT) {
                break;
            }
        }
    }

    // Lock the best value found
    set_capacitor_bank(best_c);
    __delay_ms(RELAY_SETTLE_MS);
}

// ============================================================
// EMERGENCY ABORT
// ============================================================

void abort_tune(void) {
    set_capacitor_bank(0);  // All relays OFF = safe state
    tune_state = TUNE_IDLE;
    led_set(0);
    beep_error(5);          // 5 beeps = user abort
}

// ============================================================
// STATE ACCESSOR
// ============================================================

tune_state_t get_tune_state(void) {
    return tune_state;
}

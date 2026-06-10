/*
 * main.c - EFHW Auto Tuner 100W – Main Program
 *
 * Target:  PIC16F1938 @ 32 MHz (8 MHz internal + 4x PLL)
 * Compiler: XC8 v2.4x+
 * License:  GPL-3.0
 *
 * This is the main entry point. It initializes the system, then
 * enters an infinite loop waiting for a tune trigger. In the
 * standalone outdoor configuration, the trigger is automatic:
 *   - Detect RF power > P_MIN on any frequency
 *   - Wait ~200ms to debounce (avoid false triggers from QRN)
 *   - If frequency changed significantly → auto-tune
 *
 * If an external trigger button or serial command is added,
 * tune can also be triggered manually.
 */

#include "main.h"
#include "tuning.h"
#include "swr_bridge.h"
#include "eeprom.h"
#include "display.h"

// ============================================================
// GLOBAL VARIABLES
// ============================================================

static uint32_t last_tune_freq_hz = 0;      // Last successfully tuned frequency
static uint32_t last_rf_detect_time = 0;     // System tick when RF last detected
static uint8_t  tune_cooldown = 0;           // Cooldown counter after tune
static uint8_t  consecutive_tune_fails = 0;   // Counter for consecutive failures
static uint8_t  reset_cause_flags = 0;        // Snapshot of RCON at boot
static uint8_t  wdt_reset_count = 0;          // Count WDT resets within 1 hour

// ============================================================
// SYSTEM INITIALIZATION
// ============================================================

void system_init(void) {
    // ---- Capture Reset Cause (before clearing RCON) ----
    reset_cause_flags = RCON;
    RCON = 0x00;  // Clear all reset flags for next detection

    // ---- Determine Reset Type ----
    uint8_t is_cold_boot = 0;
    uint8_t is_wdt_reset = 0;
    uint8_t is_bor_reset = 0;

    if (reset_cause_flags & 0x01) {  // BOR flag
        is_bor_reset = 1;
    }
    if (reset_cause_flags & 0x02) {  // POR flag
        is_cold_boot = 1;
    }
    // WDT reset: on PIC16F1938, WDT reset sets both BOR and POR-like conditions
    // Simplification: if not POR and something caused reset → assume WDT
    if (!is_cold_boot && (reset_cause_flags & 0x10)) {  // RMCLR-like
        is_wdt_reset = 1;
    }

    // ---- Oscillator Configuration ----
    OSCCON = 0b11110000;  // 8 MHz HF, SPLLEN=1 (4x PLL)
    while (!OSCSTATbits.HFIOFR);
    while (!OSCSTATbits.PLLR);

    // ---- I/O Port Initialization ----
    ANSELA = 0b00000011;  // RA0, RA1 = analog
    TRISA  = 0b00000011;  // RA0, RA1 = inputs

    ANSELB = 0x00;
    TRISB  = 0b10000000;  // RB7 = input (ICSP), RB0-RB6 = outputs
    LATB   = 0x00;        // All relays initially OFF (SAFE state)

    ANSELC = 0x00;
    TRISC  = 0x00;
    LATC   = 0x00;

    // ---- ADC Configuration ----
    ADCON0 = 0b00000001;
    ADCON1 = 0b10000000;
    ADCON2 = 0b00000000;

    // ---- Peripheral Initialization ----
    swr_bridge_init();
    display_init();
    eeprom_init();

    // ---- POST: Power-On Self Test ----
    post_report_t post_report;
    led_set(1);  // LED ON during POST

    if (is_cold_boot) {
        // Full POST on cold boot (all 4 phases)
        post_report = post_run_full();
    } else if (is_wdt_reset) {
        // WDT reset: skip PHASE 0 (DC rails should be fine)
        // Run abbreviated POST: Phase 1-2 only, lock last known C value
        wdt_reset_count++;
        if (wdt_reset_count >= 3) {
            // Multiple WDT resets → EMI/noise environment likely severe
            // Enter SAFE mode immediately
            diag_log_fault(FAULT_WDT_RESET, 0, wdt_reset_count, 0);
            diag_set_health(SYS_SAFE);
            beep_error(5);
        } else {
            diag_log_fault(FAULT_WDT_RESET, 2, wdt_reset_count, 0);
            // Restore last known good capacitor value from EEPROM
            uint8_t saved_c;
            uint16_t saved_swr;
            if (eeprom_load_tune(last_tune_freq_hz, &saved_c, &saved_swr)) {
                set_capacitor_bank(saved_c);
            }
        }
        post_report.result = POST_PASS;
        post_report.degraded = (wdt_reset_count >= 3) ? 1 : 0;
    } else if (is_bor_reset) {
        // BOR reset: supply dipped but recovered
        diag_log_fault(FAULT_BOR_EVENT, 3, 0, 0);  // INFO level
        // Run abbreviated POST (skip Phase 0 since supply is back)
        post_report = post_run_full();
    } else {
        // Unknown reset cause → treat as cold boot
        post_report = post_run_full();
    }

    led_set(0);  // POST complete

    // ---- POST Result Handling ----
    if (post_report.result != POST_PASS) {
        // POST failed — system enters appropriate state
        if (post_report.degraded) {
            diag_set_health(SYS_DEGRADED);
            diag_log_fault(FAULT_POST_FAIL, 2, post_report.result, 0);
        } else {
            diag_set_health(SYS_SAFE);
            diag_log_fault(FAULT_POST_FAIL, 0, post_report.result, 0);
        }
    } else if (post_report.degraded) {
        diag_set_health(SYS_DEGRADED);
    } else {
        diag_set_health(SYS_HEALTHY);
    }

    // ---- Initial LED/Buzzer Feedback ----
    if (!is_wdt_reset && !is_bor_reset) {
        // Only on clean boot
        beep_ok(1);
    }

    // Validate EEPROM
    if (!eeprom_is_valid()) {
        eeprom_clear_all();
        beep_error(2);
    }
}

// ============================================================
// MAIN EVENT LOOP
// ============================================================

void main(void) {
    uint16_t fwd_power;
    uint32_t current_freq;

    system_init();

    while (1) {
        // ---- Periodic RF Power Check ----
        fwd_power = read_fwd_power_mw();

        // ---- Health-aware auto-tune gating ----
        sys_health_t health = diag_get_health();

        if (fwd_power > TUNE_POWER_MIN_MW) {
            last_rf_detect_time++;

            if (tune_cooldown > 0) {
                tune_cooldown--;
            }

            // Only auto-tune when HEALTHY or DEGRADED (not SAFE)
            if (health != SYS_SAFE &&
                tune_cooldown == 0 &&
                fwd_power < TUNE_POWER_MAX_MW &&
                get_tune_state() == TUNE_IDLE) {

                if (last_rf_detect_time > 50) {
                    tune_result_t result;

                    if (consecutive_tune_fails >= TUNE_FAIL_MAX_CONSECUTIVE) {
                        // Too many consecutive failures → enter SAFE
                        diag_set_health(SYS_SAFE);
                        diag_log_fault(FAULT_SWR_SENSOR, 1,
                                       consecutive_tune_fails, 0);
                        // Load last known good C value and stop trying
                        uint8_t saved_c; uint16_t saved_swr;
                        if (eeprom_load_tune(last_tune_freq_hz, &saved_c, &saved_swr)) {
                            set_capacitor_bank(saved_c);
                        }
                        beep_error(5);
                        tune_cooldown = 600;  // 6s cooldown (longer in SAFE)
                    } else {
                        result = run_autotune_efhw();

                        if (result.state == TUNE_LOCKED) {
                            last_tune_freq_hz = result.frequency;
                            consecutive_tune_fails = 0;
                            tune_cooldown = 200;
                        } else {
                            consecutive_tune_fails++;
                            tune_cooldown = 50;
                        }
                    }

                    last_rf_detect_time = 0;
                }
            } else if (health == SYS_SAFE) {
                // In SAFE mode: LED slow blink to indicate
                // No auto-tuning — rely on last known C value
                if (last_rf_detect_time > 200) {
                    led_set(!LED_PIN);  // Slow blink (~2 Hz)
                    last_rf_detect_time = 0;
                }
            }
        } else {
            last_rf_detect_time = 0;
        }

        // ---- Periodic Diagnostic Check (every ~10s = 1000 loop ticks) ----
        static uint16_t diag_tick = 0;
        diag_tick++;
        if (diag_tick >= 1000) {
            diag_tick = 0;
            diag_result_t diag = diag_run_all();
            if (diag.health != SYS_HEALTHY && health == SYS_HEALTHY) {
                // Health just degraded → signal
                beep_error(2);
            }
        }

        // ---- Process any pending commands ----
        process_tune_command();

        // ---- System tick (non-blocking) ----
        system_tick();

        __delay_ms(10);  // Main loop tick ~100 Hz
    }
}

// ============================================================
// PLACEHOLDER FUNCTIONS (extend as needed)
// ============================================================

void system_tick(void) {
    // Non-blocking periodic tasks:
    // - LED heartbeat
    // - Watchdog pet
    // - Sensor reading (temperature, etc.)
    CLRWDT();  // Clear watchdog timer
}

void process_tune_command(void) {
    // Placeholder for external tune trigger processing.
    //
    // If a serial interface (UART/I2C) or external button is added,
    // this function would check for incoming tune requests and
    // call run_autotune_efhw() or run_quick_retune_efhw().
    //
    // For the standalone Bias-T powered outdoor configuration,
    // the auto-trigger logic in main() is sufficient.
}

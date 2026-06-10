/*
 * display.c - LED and Buzzer Status Indication
 *
 * Target:  PIC16F1938
 * License:  GPL-3.0
 *
 * Minimalist user interface for the outdoor auto-tuner.
 * Since the unit is mounted outdoors, there is no LCD display.
 * Status is communicated via:
 *   - LED: ON during tuning, OFF when idle
 *   - Buzzer: Beep patterns for OK/Error codes
 *
 * Beep Patterns:
 *   1 short beep  = Power-on OK, Tune success
 *   2 short beeps = Fresh EEPROM, RF lost
 *   3 short beeps = Overpower detected
 *   4 short beeps = Power surge during tune
 *   5 short beeps = User abort
 *   1 long beep   = SWR > 3:1 (could not tune)
 *
 * For debug/development, a UART serial output can be added
 * on spare pins (e.g., RC6/TX, RC7/RX).
 */

#include "main.h"
#include "display.h"

// ============================================================
// TIMING CONSTANTS
// ============================================================

#define BEEP_SHORT_MS   80
#define BEEP_LONG_MS    400
#define BEEP_GAP_MS     120
#define BEEP_BETWEEN_MS 300

// ============================================================
// INITIALIZATION
// ============================================================

void display_init(void) {
    // Buzzer and LED pins configured as outputs in system_init()
    BUZZER_TRIS = 0;  // Output
    LED_TRIS    = 0;  // Output
    BUZZER_PIN  = 0;  // Off
    LED_PIN     = 0;  // Off
}

// ============================================================
// BEEP PATTERNS
// ============================================================

static void beep_ms(uint16_t ms) {
    BUZZER_PIN = 1;
    for (uint16_t i = 0; i < ms; i++) {
        __delay_ms(1);
    }
    BUZZER_PIN = 0;
}

void beep_ok(uint8_t count) {
    for (uint8_t i = 0; i < count; i++) {
        beep_ms(BEEP_SHORT_MS);
        if (i < count - 1) {
            __delay_ms(BEEP_GAP_MS);
        }
    }
}

void beep_error(uint8_t count) {
    for (uint8_t i = 0; i < count; i++) {
        beep_ms(BEEP_SHORT_MS);
        if (i < count - 1) {
            __delay_ms(BEEP_GAP_MS);
        }
    }
}

// ============================================================
// LED CONTROL
// ============================================================

void led_set(uint8_t on) {
    LED_PIN = (on != 0) ? 1 : 0;
}

// ============================================================
// STATUS DISPLAY (MINIMAL – NO LCD)
// ============================================================

void display_tune_ok(uint16_t swr_x100, uint8_t c_val) {
    // Ensure LED is turned off at end of tune (done by caller)
    // beep_ok is called by the tuning function
    (void)swr_x100;  // Unused in minimal display
    (void)c_val;     // Unused in minimal display
}

void display_tune_fail(uint16_t swr_x100) {
    // Long beep to indicate SWR too high
    beep_ms(BEEP_LONG_MS);
    (void)swr_x100;
}

void display_error(const char *msg) {
    // In the outdoor unit, we can't display text.
    // Error is communicated via beep pattern from the caller.
    // msg is kept for debug builds where UART output is available.
    (void)msg;
}

void display_warning(const char *msg) {
    // Non-critical warning – brief LED flash
    led_set(1);
    __delay_ms(60);
    led_set(0);
    (void)msg;
}

/*
 * main.h - Global defines and function prototypes
 *
 * Target:  PIC16F1938
 * Compiler: XC8 v2.4x+
 * License:  GPL-3.0
 */

#ifndef MAIN_H
#define MAIN_H

#include <xc.h>
#include <stdint.h>
#include "config.h"

// ============================================================
// CONFIGURATION BITS (set in MPLAB X project properties or here)
// ============================================================
// #pragma config FOSC = INTOSC     // Internal oscillator
// #pragma config WDTE = OFF        // Watchdog timer disabled
// #pragma config PWRTE = ON        // Power-up timer enabled
// #pragma config MCLRE = ON        // MCLR pin enabled (for ICSP)
// #pragma config CP = OFF          // Code protection off
// #pragma config CPD = OFF         // Data code protection off
// #pragma config BOREN = ON        // Brown-out reset enabled
// #pragma config CLKOUTEN = OFF    // Clock output disabled
// #pragma config IESO = ON         // Internal/External switchover
// #pragma config FCMEN = ON        // Fail-safe clock monitor
// #pragma config WRT = OFF         // Flash write protection off
// #pragma config VCAPEN = OFF      // Voltage regulator cap disabled
// #pragma config PLLEN = ON        // 4x PLL enabled (for 32 MHz)
// #pragma config STVREN = ON       // Stack overflow/underflow reset
// #pragma config BORV = LO         // Brown-out low trip point
// #pragma config LVP = OFF         // Low-voltage programming off

// ============================================================
// GLOBAL TYPES AND STRUCTURES
// ============================================================

// Tuning state machine
typedef enum {
    TUNE_IDLE = 0,              // No tuning in progress
    TUNE_CHECK_POWER,           // Verifying RF power level
    TUNE_SCANNING,              // Scanning capacitor array
    TUNE_LOCKED,                // Best value found, locked
    TUNE_ERROR_OVERPOWER,       // Power too high – aborted
    TUNE_ERROR_NORF,            // No RF detected
    TUNE_ERROR_SWR_HIGH         // Cannot achieve SWR < 3:1
} tune_state_t;

// Band index for EEPROM table
typedef enum {
    BAND_40M = 0,
    BAND_30M = 1,
    BAND_20M = 2,
    BAND_17M = 3,
    BAND_15M = 4,
    BAND_12M = 5,
    BAND_10M = 6,
    BAND_UNKNOWN = 0xFF
} band_index_t;

// Tuning result structure
typedef struct {
    uint8_t   c_value;          // Capacitor setting (0-127)
    uint16_t  swr_x100;         // SWR × 100 (e.g., 115 = 1.15:1)
    uint32_t  frequency;        // Tuned frequency in Hz
    uint16_t  fwd_power_mw;     // Forward power during tune (mW)
    tune_state_t state;         // Result state
} tune_result_t;

// ============================================================
// GLOBAL FUNCTION PROTOTYPES
// ============================================================

// main.c
void system_init(void);
void system_tick(void);
void process_tune_command(void);

// tuning.c
tune_result_t run_autotune_efhw(void);
tune_result_t run_quick_retune_efhw(uint32_t freq_hz);
void         tune_fine_around(uint8_t center_c);
void         abort_tune(void);
tune_state_t get_tune_state(void);

// swr_bridge.c
void     swr_bridge_init(void);
uint16_t read_fwd_power_mw(void);
uint16_t read_rev_power_mw(void);
uint16_t read_swr_x100(void);
uint16_t read_adc_channel(uint8_t ch);
uint16_t read_adc_channel_oversampled(uint8_t ch, uint8_t samples);

// eeprom.c
void     eeprom_init(void);
uint8_t  eeprom_is_valid(void);
void     eeprom_save_tune(uint32_t freq_hz, uint8_t c_val, uint16_t swr_x100);
uint8_t  eeprom_load_tune(uint32_t freq_hz, uint8_t *c_val, uint16_t *swr_x100);
void     eeprom_clear_all(void);
band_index_t get_band_index(uint32_t freq_hz);

// display.c
void display_init(void);
void display_tune_ok(uint16_t swr_x100, uint8_t c_val);
void display_tune_fail(uint16_t swr_x100);
void display_error(const char *msg);
void display_warning(const char *msg);
void beep_ok(uint8_t count);
void beep_error(uint8_t count);
void led_set(uint8_t on);

// diagnostics.c (runtime fault detection — docs/FDE.md §5)
#include "diagnostics.h"

// post.c (power-on self test — docs/FDE.md §4)
#include "post.h"

#endif // MAIN_H

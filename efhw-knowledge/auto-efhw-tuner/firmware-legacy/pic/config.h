/*
 * config.h - User-configurable parameters for EFHW Auto Tuner 100W
 *
 * Target:  PIC16F1938
 * Compiler: XC8 v2.4x+
 * License:  GPL-3.0
 *
 * Modify the values in this file to adapt the tuner to your specific
 * hardware build, power levels, and operating preferences.
 */

#ifndef CONFIG_H
#define CONFIG_H

// ============================================================
// 1. SYSTEM CLOCK
// ============================================================
#define _XTAL_FREQ              32000000UL  // 32 MHz internal oscillator

// ============================================================
// 2. TUNING PARAMETERS
// ============================================================
#define TUNE_POWER_MAX_MW        15000       // Max safe tuning power (15W)
#define TUNE_POWER_MIN_MW        500         // Min detectable RF power (0.5W)
#define TUNE_POWER_RECOMMENDED_MW 3000       // Recommended tuning power (3W)

#define RELAY_SETTLE_MS          12          // G5Q-14 mechanical settle time + margin
#define ADC_SAMPLE_COUNT         8           // Oversampling count for SWR reading
#define SWR_EARLY_EXIT           105         // SWR×100 threshold: stop scan if <1.05:1
#define SWR_SAVE_MAX             300         // SWR×100 threshold: only save if <3.0:1
#define SWR_QUICK_RETUNE_MAX     200         // SWR×100 threshold: skip full scan if <2.0:1

// ============================================================
// 2b. FDE / POST PARAMETERS (see docs/FDE.md)
// ============================================================
#define WDT_TIMEOUT_MS           2000        // Watchdog timeout period (~2 seconds)
#define POST_PHASE_TIMEOUT_MS    2000        // Max time for entire POST sequence
#define ADC_STUCK_THRESHOLD      8           // Consecutive identical reads → stuck fault
#define RELAY_FAIL_COUNT_SAFE    3           // ≥N failed relays → enter SAFE mode
#define RELAY_FAIL_COUNT_DEGRADED 1          // ≥1 failed relay → enter DEGRADED mode
#define SWR_RELAY_DELTA_MIN      5           // Min SWR change (×100) when toggling relay
#define ADC_FVR_EXPECTED_MIN     369         // Low bound for FVR=2.048V @ VDD=5.0V
#define ADC_FVR_EXPECTED_MAX     469         // High bound for FVR=2.048V @ VDD=5.0V
#define VDD_MV_MIN               4500        // Minimum acceptable VDD (4.5V)
#define VDD_MV_MAX               5500        // Maximum acceptable VDD (5.5V)
#define OVER_TEMP_ADC_THRESHOLD  150         // NTC ADC reading threshold for ~85°C
#define TUNE_FAIL_MAX_CONSECUTIVE 3          // Consecutive tune failures → SAFE mode

// ============================================================
// 3. FREQUENCY BAND DEFINITIONS (Hz × 100)
// ============================================================
// Used for EEPROM band-to-capacitor-value mapping
#define BAND_40M_LOW             7000000UL
#define BAND_40M_HIGH            7300000UL
#define BAND_30M_LOW             10100000UL
#define BAND_30M_HIGH            10150000UL
#define BAND_20M_LOW             14000000UL
#define BAND_20M_HIGH            14350000UL
#define BAND_17M_LOW             18068000UL
#define BAND_17M_HIGH            18168000UL
#define BAND_15M_LOW             21000000UL
#define BAND_15M_HIGH            21450000UL
#define BAND_12M_LOW             24890000UL
#define BAND_12M_HIGH            24990000UL
#define BAND_10M_LOW             28000000UL
#define BAND_10M_HIGH            29700000UL

#define NUM_BANDS                7           // 40/30/20/17/15/12/10m

// ============================================================
// 4. ADC CALIBRATION (adjust after bench calibration)
// ============================================================
// ADC reference = VDD (5.0V nominal), 10-bit resolution
// SWR_FWD offset and scale are calibrated against known 50Ω load
#define ADC_FWD_OFFSET_50OHM     512         // ADC reading for FWD @ 50Ω 5W carrier
#define ADC_REV_NULL_50OHM       5           // ADC reading for REV @ perfect 50Ω match

// ============================================================
// 5. EEPROM LAYOUT
// ============================================================
#define EE_MAGIC_ADDR            0x00        // Magic number for EEPROM validity
#define EE_MAGIC_VALUE           0xA5        // Arbitrary magic byte
#define EE_VERSION_ADDR          0x01        // Data format version
#define EE_VERSION_VALUE         0x01        // Increment when format changes
#define EE_LAST_FREQ_H_ADDR      0x02        // Last tuned frequency (high byte)
#define EE_LAST_FREQ_L_ADDR      0x03        // Last tuned frequency (low byte)
#define EE_LAST_CVAL_ADDR        0x04        // Last capacitor value (0-127)
#define EE_LAST_SWR_ADDR         0x05        // Last SWR × 100
#define EE_BAND_TABLE_ADDR       0x10        // Start of band memory table
// Each band entry = 3 bytes: freq_high, freq_low, c_val
#define EE_BAND_ENTRY_SIZE       3

// ============================================================
// 6. HARDWARE PIN MAPPING (PIC16F1938)
// ============================================================
// Capacitor relay control: RB0-RB6 (7 bits, binary weighted)
#define C_RELAY_PORT             PORTB
#define C_RELAY_TRIS             TRISB
#define C_RELAY_LAT              LATB
#define C_RELAY_MASK             0x7F        // RB0-RB6

// SWR ADC inputs
#define SWR_FWD_CHANNEL          0           // AN0 (RA0)
#define SWR_REV_CHANNEL          1           // AN1 (RA1)

// Indicator / buzzer
#define BUZZER_PIN               LATC0       // RC0 (optional, active high buzzer)
#define BUZZER_TRIS              TRISC0
#define LED_PIN                  LATC1       // RC1 (optional, status LED)
#define LED_TRIS                 TRISC1

// ============================================================
// 7. CAPACITOR ARRAY VALUES (pF) - for display/reference
// ============================================================
// Binary weighted: bit0=10pF, bit1=22pF, bit2=47pF,
//                  bit3=100pF, bit4=220pF, bit5=470pF, bit6=1000pF
// Capacitance for c_val = sum of bits set
// These are for informational display only, not used in tuning algorithm
#define CAP_BIT0_PF              10
#define CAP_BIT1_PF              22
#define CAP_BIT2_PF              47
#define CAP_BIT3_PF              100
#define CAP_BIT4_PF              220
#define CAP_BIT5_PF              470
#define CAP_BIT6_PF              1000

#endif // CONFIG_H

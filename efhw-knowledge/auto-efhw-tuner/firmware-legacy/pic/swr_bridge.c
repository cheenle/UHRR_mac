/*
 * swr_bridge.c - SWR Measurement via Tandem Match Directional Coupler
 *
 * Target:  PIC16F1938 (10-bit ADC, AN0=FWD, AN1=REV)
 * License:  GPL-3.0
 *
 * Hardware: John Grebenkemper, KI6WX Tandem Match (QST Jan 1987)
 *
 *   FT37-43 core ×2, 10T secondary each
 *   BAT41 Schottky diode detector (matched pair)
 *   50Ω precision load resistors
 *   10kΩ multi-turn trim pot for FWD/REV balance
 *
 * SWR Calculation:
 *
 *   SWR = (1 + |Γ|) / (1 - |Γ|)
 *   |Γ| = sqrt(REV_power / FWD_power)  [for ideal coupler]
 *
 *   In practice, we measure DC voltages after diode detection:
 *   V_fwd ∝ sqrt(P_fwd), V_rev ∝ sqrt(P_rev)
 *   So: |Γ| ≈ V_rev / V_fwd  (first-order approximation)
 *
 *   SWR = (V_fwd + V_rev) / (V_fwd - V_rev)
 *
 *   This is valid when the coupler has good directivity (>25 dB)
 *   and the detectors are well-matched.
 *
 * ADC Configuration (10-bit, Vref = VDD = 5.0V):
 *   - Each LSB = 5.0V / 1024 = 4.88 mV
 *   - 3V full-scale signal → 614 counts effective
 *   - Oversampling with N=8 improves SNR by ~9 dB
 */

#include "main.h"
#include "swr_bridge.h"

// ============================================================
// CALIBRATION CONSTANTS (tune after bench calibration)
// ============================================================

// ADC reading for FWD when 5W CW into perfect 50Ω load
// This varies with actual diode Vf, trim pot setting, etc.
// Calibrate: connect 50Ω dummy load, apply 5W CW, record ADC value
#define CAL_FWD_ADC_5W_50OHM    512

// ADC reading for REV when 5W CW into perfect 50Ω load
// Should be near zero with well-balanced bridge
#define CAL_REV_ADC_5W_50OHM    5

// Reference power for calibration (mW)
#define CAL_REF_POWER_MW        5000

// Minimum FWD ADC reading to consider "RF present"
#define ADC_NOISE_FLOOR         10

// ============================================================
// INITIALIZATION
// ============================================================

void swr_bridge_init(void) {
    // AN0 (RA0) and AN1 (RA1) are configured as analog in system_init()
    // No additional analog pin config needed here

    // ADC is already configured in system_init()
    // We just ensure it's running
    ADCON0bits.ADON = 1;  // ADC ON
}

// ============================================================
// ADC READING FUNCTIONS
// ============================================================

/**
 * Read a single ADC channel (blocking, single conversion).
 *
 * @param ch  ADC channel number (0-10 for PIC16F1938)
 * @return    10-bit ADC result (0-1023)
 */
uint16_t read_adc_channel(uint8_t ch) {
    // Select channel
    ADCON0bits.CHS = ch & 0x0F;  // CHS<4:0>

    // Acquisition time (minimum ~2.4 μs for 10-bit, use 10 μs for safety)
    __delay_us(10);

    // Start conversion
    ADCON0bits.GO_nDONE = 1;

    // Wait for conversion complete (typical 11 TAD ≈ 13.75 μs @ FOSC/32)
    while (ADCON0bits.GO_nDONE);

    // Return 10-bit result (right-justified)
    return (uint16_t)((ADRESH << 8) | ADRESL);
}

/**
 * Read an ADC channel with oversampling for noise reduction.
 *
 * Oversampling by N gives:
 *   SNR improvement = 10*log10(N) dB
 *   Effective bits gained = log2(N) / 2 bits
 *
 * N=8 → ~9 dB SNR improvement, ~1.5 extra bits
 *
 * @param ch       ADC channel number
 * @param samples  Number of samples to average
 * @return         Averaged 10-bit ADC result
 */
uint16_t read_adc_channel_oversampled(uint8_t ch, uint8_t samples) {
    uint16_t sum = 0;
    uint8_t  i;

    for (i = 0; i < samples; i++) {
        sum += read_adc_channel(ch);
        __delay_us(50);  // Space out samples to decorrelate noise
    }

    return sum / samples;
}

// ============================================================
// POWER AND SWR MEASUREMENT
// ============================================================

/**
 * Read forward power in milliwatts.
 *
 * The Tandem Match detector output is a DC voltage proportional
 * to the square root of forward power (due to diode square-law
 * region at low levels, transitioning to linear at higher levels).
 *
 * Simplified power estimation:
 *   P_fwd ≈ P_ref × (ADC_fwd / ADC_ref)²
 */
uint16_t read_fwd_power_mw(void) {
    uint16_t adc_fwd;
    uint32_t power;  // Use 32-bit for intermediate math

    adc_fwd = read_adc_channel_oversampled(SWR_FWD_CHANNEL, ADC_SAMPLE_COUNT);

    if (adc_fwd < ADC_NOISE_FLOOR) {
        return 0;  // Below noise floor = no RF
    }

    // Power estimation using square-law approximation
    // P ≈ P_cal × (ADC / ADC_cal)²
    // Use 32-bit to avoid overflow: (adc² × P_cal) / ADC_cal²
    power = (uint32_t)adc_fwd * adc_fwd * CAL_REF_POWER_MW;
    power = power / ((uint32_t)CAL_FWD_ADC_5W_50OHM * CAL_FWD_ADC_5W_50OHM);

    if (power > 65535) {
        power = 65535;  // Clamp to uint16_t max
    }

    return (uint16_t)power;
}

/**
 * Read reverse power in milliwatts.
 */
uint16_t read_rev_power_mw(void) {
    uint16_t adc_rev;
    uint32_t power;

    adc_rev = read_adc_channel_oversampled(SWR_REV_CHANNEL, ADC_SAMPLE_COUNT);

    if (adc_rev < ADC_NOISE_FLOOR) {
        return 0;
    }

    power = (uint32_t)adc_rev * adc_rev * CAL_REF_POWER_MW;
    power = power / ((uint32_t)CAL_FWD_ADC_5W_50OHM * CAL_FWD_ADC_5W_50OHM);

    if (power > 65535) {
        power = 65535;
    }

    return (uint16_t)power;
}

/**
 * Read SWR × 100 (e.g., return 115 = SWR 1.15:1).
 *
 * Algorithm:
 *   SWR = (V_fwd + V_rev) / (V_fwd - V_rev)
 *
 *   This is the standard formula for a directional coupler.
 *   V_fwd and V_rev are DC voltages proportional to √P_fwd and √P_rev.
 *
 * Edge cases handled:
 *   - V_rev ≈ 0 → SWR ≈ 1.0 (perfect match)
 *   - V_fwd ≈ V_rev → SWR → ∞ (total reflection, return 999)
 *   - V_rev > V_fwd → SWR negative → return 999 (calibration error)
 */
uint16_t read_swr_x100(void) {
    uint16_t adc_fwd, adc_rev;
    uint32_t v_fwd, v_rev;
    uint32_t swr_x100;

    adc_fwd = read_adc_channel_oversampled(SWR_FWD_CHANNEL, ADC_SAMPLE_COUNT);
    adc_rev = read_adc_channel_oversampled(SWR_REV_CHANNEL, ADC_SAMPLE_COUNT);

    // Treat ADC readings directly as voltage (proportional to √P)
    v_fwd = adc_fwd;
    v_rev = adc_rev;

    // Clamp noise floor
    if (v_fwd < ADC_NOISE_FLOOR) {
        return 999;  // No forward power → can't measure SWR
    }

    if (v_rev < ADC_NOISE_FLOOR) {
        return 100;  // Effectively zero reflection → SWR ≈ 1.00:1
    }

    // Check for div-by-zero or negative denominator
    if (v_fwd <= v_rev) {
        // Total reflection or calibration error
        return 999;
    }

    // SWR = (V_fwd + V_rev) / (V_fwd - V_rev)
    // Multiply by 100 for 2 decimal places
    swr_x100 = (100UL * (v_fwd + v_rev)) / (v_fwd - v_rev);

    // Clamp to reasonable range
    if (swr_x100 > 999) {
        swr_x100 = 999;
    }
    if (swr_x100 < 100) {
        swr_x100 = 100;  // SWR can't be less than 1.00:1
    }

    return (uint16_t)swr_x100;
}

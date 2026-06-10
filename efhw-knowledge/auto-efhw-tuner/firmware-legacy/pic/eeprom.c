/*
 * eeprom.c - EEPROM Management for Frequency-Capacitor Memory
 *
 * Target:  PIC16F1938 (256 bytes internal EEPROM)
 * License:  GPL-3.0
 *
 * EEPROM Layout:
 *   Addr 0x00:   Magic byte (0xA5 = valid)
 *   Addr 0x01:   Data format version
 *   Addr 0x02-03: Last tuned frequency (16-bit, Hz×100)
 *   Addr 0x04:   Last capacitor value (0-127)
 *   Addr 0x05:   Last SWR × 100
 *   Addr 0x06-0x0F: Reserved
 *   Addr 0x10-0x1F: Band memory table (7 bands × 3 bytes)
 *     Each entry: [freq_high(1B), freq_low(1B), c_val(1B)]
 *     Frequency stored as (freq_MHz * 10) to fit in 8 bits
 *     e.g., 14.2 MHz → 142, 7.1 MHz → 71
 *   Addr 0x20-0xFF: Reserved for future use
 *
 * PIC16F1938 EEPROM characteristics:
 *   - 256 bytes
 *   - 1,000,000 erase/write cycles (typical)
 *   - Data retention > 40 years
 *   - Byte write time ~5 ms (handled by HW, polling EEPGD/WR bit)
 */

#include "main.h"
#include "eeprom.h"

// ============================================================
// LOW-LEVEL EEPROM ACCESS
// ============================================================

/**
 * Read a single byte from EEPROM.
 */
static uint8_t ee_read(uint8_t addr) {
    EEADRL = addr;       // Set address (low byte only, 0-255)
    EECON1bits.CFGS = 0; // Access EEPROM (not config)
    EECON1bits.EEPGD = 0; // Access EEPROM (not program flash)
    EECON1bits.RD = 1;   // Initiate read
    // Data available in EEDATL next instruction (single-cycle read)
    return EEDATL;
}

/**
 * Write a single byte to EEPROM.
 * Blocks until write complete (~5 ms typical).
 */
static void ee_write(uint8_t addr, uint8_t data) {
    // Wait for any previous write to complete
    while (EECON1bits.WR);

    EEADRL = addr;
    EEDATL = data;
    EECON1bits.CFGS = 0;   // EEPROM space
    EECON1bits.EEPGD = 0;  // EEPROM (not flash)
    EECON1bits.WREN = 1;   // Enable writes

    // Required unlock sequence for PIC16 enhanced mid-range
    EECON2 = 0x55;
    EECON2 = 0xAA;
    EECON1bits.WR = 1;     // Initiate write

    // Wait for write complete
    while (EECON1bits.WR);

    EECON1bits.WREN = 0;   // Disable writes (safety)
}

// ============================================================
// INITIALIZATION AND VALIDATION
// ============================================================

void eeprom_init(void) {
    // No special init needed – just verify magic byte on first use
    // Actual validation done in eeprom_is_valid()
}

/**
 * Check if EEPROM contains valid data.
 */
uint8_t eeprom_is_valid(void) {
    uint8_t magic = ee_read(EE_MAGIC_ADDR);
    return (magic == EE_MAGIC_VALUE) ? 1 : 0;
}

/**
 * Clear all EEPROM and write fresh headers.
 */
void eeprom_clear_all(void) {
    uint8_t i;

    // Write zeros to all band table entries
    for (i = EE_BAND_TABLE_ADDR; i < EE_BAND_TABLE_ADDR + (NUM_BANDS * EE_BAND_ENTRY_SIZE); i++) {
        ee_write(i, 0xFF);  // 0xFF = "no data" sentinel
    }

    // Clear last-tune data
    ee_write(EE_LAST_FREQ_H_ADDR, 0xFF);
    ee_write(EE_LAST_FREQ_L_ADDR, 0xFF);
    ee_write(EE_LAST_CVAL_ADDR, 0xFF);
    ee_write(EE_LAST_SWR_ADDR, 0xFF);

    // Write magic and version (AFTER clearing, so power-loss mid-clear
    // doesn't leave EEPROM appearing valid)
    ee_write(EE_MAGIC_ADDR, EE_MAGIC_VALUE);
    ee_write(EE_VERSION_ADDR, EE_VERSION_VALUE);
}

// ============================================================
// BAND INDEX MAPPING
// ============================================================

/**
 * Map a frequency (Hz) to a band index for EEPROM table lookup.
 *
 * In full implementation, this would use frequency counter hardware
 * to determine the operating frequency. For the baseline firmware,
 * a simplified approach using ADC-based frequency estimation or
 * external serial command is used.
 *
 * For now: frequency passed explicitly by run_quick_retune_efhw().
 */
band_index_t get_band_index(uint32_t freq_hz) {
    if (freq_hz >= BAND_40M_LOW && freq_hz <= BAND_40M_HIGH) return BAND_40M;
    if (freq_hz >= BAND_30M_LOW && freq_hz <= BAND_30M_HIGH) return BAND_30M;
    if (freq_hz >= BAND_20M_LOW && freq_hz <= BAND_20M_HIGH) return BAND_20M;
    if (freq_hz >= BAND_17M_LOW && freq_hz <= BAND_17M_HIGH) return BAND_17M;
    if (freq_hz >= BAND_15M_LOW && freq_hz <= BAND_15M_HIGH) return BAND_15M;
    if (freq_hz >= BAND_12M_LOW && freq_hz <= BAND_12M_HIGH) return BAND_12M;
    if (freq_hz >= BAND_10M_LOW && freq_hz <= BAND_10M_HIGH) return BAND_10M;
    return BAND_UNKNOWN;
}

// ============================================================
// SAVE / LOAD TUNING DATA
// ============================================================

/**
 * Save tuning result to EEPROM for later quick recall.
 *
 * @param freq_hz   Frequency in Hz
 * @param c_val     Capacitor setting (0-127)
 * @param swr_x100  SWR × 100
 */
void eeprom_save_tune(uint32_t freq_hz, uint8_t c_val, uint16_t swr_x100) {
    band_index_t band;
    uint16_t ee_addr;

    // Save last-tune quick-access fields
    ee_write(EE_LAST_FREQ_H_ADDR, (uint8_t)((freq_hz >> 8) & 0xFF));
    ee_write(EE_LAST_FREQ_L_ADDR, (uint8_t)(freq_hz & 0xFF));
    ee_write(EE_LAST_CVAL_ADDR, c_val);
    ee_write(EE_LAST_SWR_ADDR, (uint8_t)(swr_x100 > 255 ? 255 : swr_x100));

    // Save to band table
    band = get_band_index(freq_hz);
    if (band == BAND_UNKNOWN) {
        return;  // Frequency out of defined bands
    }

    ee_addr = EE_BAND_TABLE_ADDR + ((uint16_t)band * EE_BAND_ENTRY_SIZE);

    // Store as: [freq_MHz×10 high byte, freq_MHz×10 low byte, c_val]
    // freq_MHz×10 allows 0-255 → 0.0–25.5 MHz, enough for HF
    uint16_t freq_mhz_x10 = (uint16_t)(freq_hz / 100000);  // 14.2 MHz → 142
    ee_write(ee_addr,     (uint8_t)((freq_mhz_x10 >> 8) & 0xFF));
    ee_write(ee_addr + 1, (uint8_t)(freq_mhz_x10 & 0xFF));
    ee_write(ee_addr + 2, c_val);
}

/**
 * Load tuning data from EEPROM.
 *
 * @param freq_hz   Frequency to search for (Hz)
 * @param c_val     Output: capacitor setting
 * @param swr_x100  Output: SWR at time of save
 * @return          1 if valid data found, 0 otherwise
 */
uint8_t eeprom_load_tune(uint32_t freq_hz, uint8_t *c_val, uint16_t *swr_x100) {
    band_index_t band;
    uint16_t ee_addr;
    uint8_t  saved_c;

    // Check EEPROM validity
    if (!eeprom_is_valid()) {
        return 0;
    }

    band = get_band_index(freq_hz);
    if (band == BAND_UNKNOWN) {
        return 0;
    }

    ee_addr = EE_BAND_TABLE_ADDR + ((uint16_t)band * EE_BAND_ENTRY_SIZE);

    // Read saved capacitor value
    saved_c = ee_read(ee_addr + 2);

    // Check sentinel: 0xFF means "no data"
    if (saved_c == 0xFF || saved_c > 127) {
        return 0;
    }

    *c_val = saved_c;

    // Read saved SWR from last-tune field (global, not per-band)
    *swr_x100 = ee_read(EE_LAST_SWR_ADDR);
    if (*swr_x100 == 0xFF) {
        *swr_x100 = 200;  // Assume decent if unknown
    }

    return 1;
}

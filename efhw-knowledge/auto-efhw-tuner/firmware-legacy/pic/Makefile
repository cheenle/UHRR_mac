#
# Makefile reference for EFHW Auto Tuner 100W firmware
# =====================================================
# This is NOT a standalone Makefile – it documents the MPLAB X IDE
# build configuration. The actual build is done via MPLAB X project.
#
# For command-line builds (Linux/macOS), you can use:
#   xc8-cc -mcpu=16F1938 -O2 -std=c99 \
#          -D_XTAL_FREQ=32000000 \
#          main.c tuning.c swr_bridge.c eeprom.c display.c \
#          -o efhw_tuner.hex
#
# MPLAB X IDE Project Settings:
# =============================
# Device:         PIC16F1938
# Compiler:       XC8 (v2.40 or later)
# Optimization:   -O2 (speed optimized)
# C Standard:     C99
# Heap Size:      0 (no dynamic allocation)
# Stack Size:     256 bytes
#
# Configuration Bits (set in MPLAB X > Window > Target Memory Views):
#   FOSC     = INTOSC     (Internal oscillator)
#   WDTE     = OFF        (Watchdog disabled – or ON for outdoor reliability)
#   PWRTE    = ON         (Power-up timer 64ms)
#   MCLRE    = ON         (MCLR pin enabled)
#   CP       = OFF        (Code protection off for development)
#   BOREN    = ON         (Brown-out reset enabled)
#   CLKOUTEN = OFF        (CLKOUT disabled)
#   IESO     = ON         (Internal/external switchover)
#   FCMEN    = ON         (Fail-safe clock monitor)
#   WRT      = OFF        (Flash write protection off)
#   PLLEN    = ON         (4x PLL → 32 MHz)
#   STVREN   = ON         (Stack overflow reset)
#   BORV     = LO         (Brown-out voltage low trip)
#   LVP      = OFF        (High voltage programming only)
#
# Memory Usage (estimated, with XC8 -O2):
#   Program Flash: ~6-8 KB of 28 KB
#   RAM:          ~200 bytes of 1,024 bytes
#   EEPROM:       ~50 bytes of 256 bytes
#

# Source files
SOURCES = main.c tuning.c swr_bridge.c eeprom.c display.c

# Generated files
OUTPUT_HEX = efhw_tuner_100w.hex
OUTPUT_ELF = efhw_tuner_100w.elf

# Compiler
CC = xc8-cc
CFLAGS = -mcpu=16F1938 -O2 -std=c99 -D_XTAL_FREQ=32000000

.PHONY: all clean flash

all: $(OUTPUT_HEX)

$(OUTPUT_HEX): $(SOURCES) *.h
	$(CC) $(CFLAGS) $(SOURCES) -o $(OUTPUT_ELF)
	@echo "Build complete: $(OUTPUT_HEX)"

clean:
	rm -f $(OUTPUT_HEX) $(OUTPUT_ELF) *.o *.d *.p1 *.cmf *.cof *.hxl

# Flash using PICkit 4 (requires MPLAB X IPE or pk4cmd)
flash:
	@echo "Use MPLAB X IPE or: pk4cmd -P16F1938 -F$(OUTPUT_HEX) -M"

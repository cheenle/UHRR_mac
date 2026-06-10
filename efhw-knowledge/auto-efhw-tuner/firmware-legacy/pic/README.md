# EFHW Auto Tuner 100W - Firmware Source Code
# =============================================
# Based on N7DDC ATU-100 Extended Board firmware
# Modified for EFHW capacitor-only tuning (no inductor relays)
# Target: PIC16F1938, XC8 Compiler, MPLAB X IDE
# License: GPL-3.0
# =============================================

# Project Structure:
# firmware/
#   main.c              - Main program entry, system init, event loop
#   main.h              - Global defines, pin mappings, EEPROM layout
#   tuning.c            - Auto-tuning algorithm (capacitor-only scan)
#   tuning.h            - Tuning function prototypes
#   swr_bridge.c        - SWR measurement via ADC (Tandem Match detector)
#   swr_bridge.h        - SWR measurement prototypes
#   eeprom.c            - EEPROM read/write for frequency-capacitor memory
#   eeprom.h            - EEPROM function prototypes
#   display.c           - LED/ buzzer status indication
#   display.h           - Display function prototypes
#   config.h            - User-configurable parameters (thresholds, timing)
#   Makefile            - MPLAB X build configuration reference

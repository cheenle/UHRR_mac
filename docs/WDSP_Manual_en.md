# WDSP Digital Signal Processing Manual

**Version**: V4.9.1 (2026-03-15)  
**Update**: Library path optimization, log cleanup

## Overview

WDSP (Warren Pratt's Digital Signal Processing) is a high-performance DSP library from the OpenHPSDR project, widely used in professional amateur radio software like Thetis and piHPSDR. MRRC integrates WDSP to provide professional-grade audio noise reduction and processing capabilities.

### Core Functions

| Function | Abbreviation | Description |
|----------|-------------|-------------|
| Spectral Noise Reduction | NR2 | Spectral subtraction, specifically optimized for SSB voice |
| Noise Blanker | NB | Eliminates impulse interference (lightning, electrical sparks) |
| Automatic Notch Filter | ANF | Eliminates single-frequency interference (CW tones) |
| Automatic Gain Control | AGC | Automatically adjusts output level |

---

## Parameter Details

### 1. NR2 Spectral Noise Reduction (EMNR)

**Principle**: Spectral subtraction, separates noise spectrum from signal

#### NR2 Level

| Level | Value Range | Effect | Use Case |
|-------|-------------|--------|----------|
| Off | 0 | No noise reduction | Clean signal |
| L1 | 1 | Mild noise reduction | Light background noise |
| L2 | 2 | Medium noise reduction | Normal background noise |
| L3 | 3 | Strong noise reduction | Strong background noise |
| L4 | 4 | Strongest noise reduction | Very strong background noise |

**Note**: Excessive NR2 level will cause "musical noise" - clicking sounds similar to water droplets during quiet periods.

#### NR2 Gain Method

| Value | Name | Effect |
|-------|------|--------|
| 0 | Gaussian | Most conservative, suitable for voice |
| 1 | Gaussian(log) | Medium |
| 2 | Gamma | Aggressive, stronger noise reduction |

**Recommended**: Use **0** for voice communication

#### NR2 NPE Method

| Value | Name | Effect |
|-------|------|--------|
| 0 | OSMS | Optimal smoothing, suitable for steady noise |
| 1 | MMSE | Minimum mean square error |

**Recommended**: Use **0**

#### NR2 Auto-Equalization (aeRun)

- **On**: Auto-equalization, eliminates "musical noise"
- **Off**: May have more distortion

**Recommended**: **Must be on**

---

### 2. NB Noise Blanker

**Principle**: Detects and eliminates impulse-type interference

| State | Effect |
|-------|--------|
| On | Eliminates impulse noise like lightning, electrical switches |
| Off | Preserves original signal |

**Recommended**: Off when background noise is good, on when impulse interference is high

---

### 3. ANF Automatic Notch Filter

**Principle**: Automatically detects and eliminates single-frequency continuous interference

| State | Effect |
|-------|--------|
| On | Eliminates CW tones, carrier interference |
| Off | Preserves original signal |

**Recommended**: On when there is CW interference

---

### 4. AGC Automatic Gain Control

**Principle**: Automatically adjusts output level to keep volume stable

| Mode | Value | Response Speed | Use Case |
|------|-------|---------------|----------|
| OFF | 0 | None (fixed gain) | Recording, bypass |
| LONG | 1 | Slowest (6ms attack) | Stable signals |
| SLOW | 2 | Slow (4ms attack) | SSB recommended |
| MED | 3 | Medium (4ms attack) | Default recommended |
| FAST | 4 | Fast (2ms attack) | Fast fading |

#### AGC OFF Mode

When AGC is set to OFF:
- Uses fixed gain (default 1.0)
- No automatic gain adjustment
- Suitable for connecting external compressor
- **MRRC Special Handling**: Automatically sets PanelGain1 = 0.1 to prevent internal amplification

#### AGC Target Level

- **Default**: -3.0 dB
- Smaller values make output louder

---

## Recommended Configuration Profiles

### Profile 1: Quiet Environment (Recommended)

For radio environments with low background noise

```ini
[WDSP]
enabled = True
nr2_enabled = True
nr2_level = 2
nr2_gain_method = 0
nr2_npe_method = 0
nr2_ae_run = True
nb_enabled = False
anf_enabled = False
agc_mode = 2  # SLOW
```

### Profile 2: Noisy Environment

For situations with high background noise

```ini
[WDSP]
enabled = True
nr2_enabled = True
nr2_level = 3
nr2_gain_method = 0
nr2_npe_method = 0
nr2_ae_run = True
nb_enabled = True
anf_enabled = True
agc_mode = 3  # MED
```

### Profile 3: Maximum Noise Reduction

For severe background noise

```ini
[WDSP]
enabled = True
nr2_enabled = True
nr2_level = 4
nr2_gain_method = 2  # Aggressive
nr2_npe_method = 0
nr2_ae_run = True
nb_enabled = True
anf_enabled = True
agc_mode = 3
```

### Profile 4: Bypass (No Processing)

For追求最原始音质

```ini
[WDSP]
enabled = True
nr2_enabled = False
nb_enabled = False
anf_enabled = False
agc_mode = 0  # OFF
```

---

## Internal Mechanism Explanation

### WDSP Gain Structure

```
Input → PanelGain1 → NR2/NB/ANF → AGC → Output
                    ↓
            Internal amplification ~16x
```

**Key Finding**: WDSP internally amplifies the signal by approximately 16 times, which is the root cause of clipping distortion.

### MRRC Special Handling

To prevent clipping distortion, MRRC automatically sets during initialization:

1. **PanelGain1 = 0.1**: Counteracts internal 16x amplification
2. **AGC OFF Mode SetRXAAGCFixed(1.0)**: Fixed gain, no additional amplification

---

## Performance Test Data

### SNR Improvement Comparison

| Configuration | Peak | SNR | SNR Improvement |
|---------------|------|-----|-----------------|
| Original | 0.081 | 5.5dB | - |
| NR2 L0 (Off) | 0.087 | ~5.5dB | 0dB |
| NR2 L3 | 0.093 | 12.4dB | **+6.8dB** |

### Peak Comparison

| Configuration | Original Peak | WDSP Peak | Amplification |
|---------------|---------------|-----------|---------------|
| Unfixed | 0.081 | 2.58 | 31.8x ❌ |
| Fixed | 0.081 | 0.087 | 1.07x ✅ |

---

## Troubleshooting

### Problem: Sound Distortion After Enabling WDSP

**Cause**: WDSP internal amplification causes clipping

**Solution**:
1. Ensure using AGC OFF mode (agc_mode = 0)
2. Or use SLOW/MED mode

### Problem: NR2 Produces "Musical Noise"

**Cause**: NR2 level too high

**Solution**:
1. Lower nr2_level
2. Ensure nr2_ae_run = True

### Problem: Background Noise反而变大了

**Cause**: WDSP gain settings improper

**Solution**:
1. Check if PanelGain1 is correctly set
2. Try different AGC modes

### Problem: CW Interference Not Eliminated

**Cause**: ANF not enabled

**Solution**:
1. Set anf_enabled = True

---

## Frontend Control

### Mobile Interface

Visit `mobile_modern.html` → Settings → WDSP Digital Processing

- WDSP Processing: Main switch
- NR2: Noise reduction level (0-4)
- NB: Noise blanker
- ANF: Automatic notch filter
- AGC: Mode selection

### Advanced Settings Page

Visit `wdsp_settings.html`

Can adjust more advanced parameters:
- NR2 Gain Method
- NR2 NPE Method
- NR2 Auto-Equalization
- Bandpass filter frequency

---

## References

- WDSP Official Repository: https://github.com/g0orx/wdsp
- OpenHPSDR Project
- piHPSDR Documentation

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| V4.9.1 | 2026-03-15 | Multi-instance support deep optimization |
| V4.9.0 | 2026-03-14 | Voice assistant, CW mode, SDR interface |
| V4.7.0 | 2026-03-10 | Added project directory library path support; cleaned debug logs; AGC parameter optimization |
| V4.6.1 | 2026-03-10 | Fixed initialization bug, optimized PanelGain and NR2 parameters |
| V4.6.0 | 2026-03-09 | Initial WDSP integration |

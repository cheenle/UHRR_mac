# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [V4.3.4] - 2026-03-04
### 📚 ATR-1000 Integration Documentation

**Theme: Complete ATR-1000 Integration Guide**

### Added
- **IFLOW.md**: Added comprehensive ATR-1000 integration documentation
  - Architecture design diagram
  - Startup methods and configuration
  - Data protocol specification
  - Tuner storage module description
  - Performance optimization details
  - Troubleshooting guide

---

## [V4.3.3] - 2026-03-04
### ⚡ ATR-1000 Connection Pre-warming

**Theme: Reduce PTT Press Latency**

### Optimized
- **Pre-connection**: ATR-1000 WebSocket connection established on page load
- **Connection persistence**: Keep connection alive after TX ends
- **SYNC pre-warming**: Send SYNC every 2s when client connected (not just during TX)
- **Removed**: Connection close on TX stop - connection stays warm

### Effect
- PTT press to power display: ~1-2s → ~100-200ms
- First TX after page refresh: instant response

---

## [V4.3.2] - 2026-03-04
### 🐛 ATR-1000 Display Optimization

**Theme: Improve Real-time Display Responsiveness**

### Fixed
- **Frontend Display Update**: Always call `updateDisplay()` on data receive, remove change detection dependency
- **Proxy Log Output**: Restore broadcast logging when power > 0
- **Debug Console Log**: Add power/SWR change logging for troubleshooting

### Optimized
- Reduced unnecessary conditional checks in frontend message handler
- Cleaner log output (only show when actual power is present)

---

## [V4.3.1] - 2026-03-04
### 🐛 ATR-1000 Display Fix & Tuner Storage Module

**Theme: Real-time Power/SWR Display and Tuner Parameter Storage**

### Added
- **ATR-1000 Tuner Storage Module** (`atr1000_tuner.py`)
  - Store tuner parameters (LC/CL, inductance, capacitance) by frequency
  - Auto-load matching parameters when frequency changes
  - JSON file persistence (`atr1000_tuner.json`)

- **Relay Status Parsing** in ATR-1000 proxy
  - Parse SCMD_RELAY_STATUS (command 5)
  - Extract SW (LC/CL), inductance index, capacitance index
  - Display in frontend UI

- **Frontend UI**: Tuner operation buttons
  - "Tune" button: Start auto-tuning
  - "Save" button: Save current parameters
  - "Records" button: View saved parameters

### Fixed
- **ATR-1000 WebSocket Data Forwarding** in UHRR
  - Use `IOLoop.add_callback()` for thread-safe WebSocket writes
  - Fixed display lag on mobile devices

### Technical Details
- **Data Flow**: Proxy → Unix Socket → UHRR → WebSocket (IOLoop) → Frontend
- **Tuner Storage**: Frequency-based parameter lookup with ±50kHz tolerance
- **Commands**: `set_relay`, `tune`, `save_tuner` actions

---

## [V4.3.0] - 2026-03-04
### 🔌 ATR-1000 Architecture Separation

**Theme: Independent ATR-1000 Proxy for Better Performance**

### Added
- **Independent ATR-1000 Proxy Program** (`atr1000_proxy.py`)
  - Separate process that doesn't block UHRR main program
  - Unix Socket communication with UHRR (`/tmp/atr1000_proxy.sock`)
  - Auto-reconnect to ATR-1000 device
  - On-demand data requests (only when clients connected)

- **ATR-1000 WebSocket Endpoint** in UHRR
  - New route `/WSATR1000` for frontend communication
  - Bridges frontend WebSocket to independent proxy via Unix Socket

### Changed
- **Data Request Interval**: Optimized from 0.3s to 1.0s for lower CPU usage
- **Frontend ATR-1000 Module**: Re-enabled with improved polling management
  - Added `_pollInterval` variable for proper timer management
  - Added `stopDataPolling()` function

### Architecture
```
Frontend (mobile_modern.js)
    ↓ WebSocket (/WSATR1000)
UHRR Main Program
    ↓ Unix Socket (/tmp/atr1000_proxy.sock)
ATR-1000 Independent Proxy (atr1000_proxy.py)
    ↓ WebSocket
ATR-1000 Device (192.168.1.63:60001)
```

### Benefits
| Feature | Before | After |
|---------|--------|-------|
| PTT Release Delay | ~2 seconds | < 100ms |
| CPU Usage (ATR-1000) | High (0.3s interval) | Low (1.0s interval, on-demand) |
| Architecture | Coupled | Decoupled independent process |

### Usage
```bash
# Start ATR-1000 proxy (background)
python3 atr1000_proxy.py --device 192.168.1.63 --port 60001 &

# Start UHRR main program
./uhrr_control.sh start
```

---

## [V4.2.0] - 2026-03-02

### 🎙️ TX Audio Equalizer

**Theme: Shortwave Communication Voice Optimization**

### Added
- **TX EQ System**: Three-band equalizer for transmit audio optimization
  - Low frequency boost (lowshelf @ 200Hz)
  - Mid frequency enhancement (peaking @ 1000Hz)
  - High frequency attenuation (highshelf @ 2500Hz)

- **Four Presets for Shortwave Communication**:
  | Preset | Low | Mid | High | Description |
  |--------|-----|-----|------|-------------|
  | Default | 0dB | 0dB | 0dB | No processing |
  | HF Voice | +4dB | +6dB | -3dB | Enhanced mid/low for SW voice |
  | DX Weak | +6dB | +8dB | -6dB | Strong mid/low for weak signals |
  | Contest | +2dB | +4dB | -2dB | Balanced for quick QSOs |

- **Mobile UI**: TX Equalizer panel in menu with preset selection
- **Persistence**: EQ preset saved to Cookie

### Technical Details
- Audio chain: micSource → eqLow → eqMid → eqHigh → gain_node → processor
- Uses Web Audio API BiquadFilter nodes
- Real-time parameter adjustment support

---

## [V4.1.0] - 2026-03-01

### 🏷️ Project Rebranding

**Theme: Mobile First - MRRC (Mobile Remote Radio Control)**

### Changed
- **Project Name**: Renamed from "Universal HamRadio Remote (UHRR)" to "Mobile Remote Radio Control (MRRC)"
- **Design Philosophy**: Mobile-first approach with emphasis on "Amateur Radio, Anytime, Anywhere"
- **Documentation**: Complete rebranding across all README files

### Added
- **Bilingual README**: Language-switchable documentation (English/Chinese)
- **Mobile-First Tagline**: "随时随地，畅享业余无线电" / "Amateur Radio, Anytime, Anywhere"

### Highlights
| Feature | Description |
|---------|-------------|
| 📱 Mobile First | Optimized for touch, one-hand operation |
| 🌍 Remote Anywhere | Control your station from anywhere |
| ⚡ Ultra Low Latency | TX→RX switching < 100ms |

---

## [V4.0.1] - 2026-03-01

### 🎨 Mobile Interface Enhancement

**Theme: S-Meter & Audio Control Improvements**

### Added
- **Volume Control on Main Screen**: Real-time AF gain slider with visual feedback (0-100%)
- **S-Meter Signal Text Display**: Shows signal level (S0-S9+60) with dB value
- **Hidden Audio Elements**: C_af and SQUELCH elements for controls.js compatibility

### Changed
- **S-Meter Display**: Rewritten to use correct SP mapping table (S0-S9+60dB)
- **Audio Settings Panel**: Improved slider initialization from Cookie values
- **Cookie Loading**: Now syncs main screen volume slider on page load

### Fixed
- **S-Meter Mapping**: Corrected signal level to pixel position mapping
- **AF Gain Synchronization**: Bidirectional sync between main screen and settings panel
- **Audio Gain Control**: Properly calls AudioRX_SetGAIN() and AudioTX_SetGAIN()

### Technical Details
| Feature | Implementation |
|---------|---------------|
| S-Meter Range | S0 (0px) to S9+60 (240px) |
| AF Gain Range | 0-100% (maps to 0-1000 internal) |
| Cookie Sync | Real-time bidirectional |

---

## [V4.0.0] - 2026-03-01

### 🎯 Milestone Release

**Theme: Performance Optimization & Architecture Simplification**

### Added
- **TUNE Button**: Long-press to transmit 1kHz tone for antenna tuner adjustment
- **End-to-End Analysis Report**: Comprehensive performance analysis and optimization recommendations
- **Modern Mobile Interface**: Optimized for iPhone 15 and modern mobile browsers

### Changed
- **Frequency Step Buttons**: Changed from 1k/100/10Hz to 10k/5k/1kHz with improved layout
- **TX→RX Switching Latency**: Optimized from 2-3 seconds to <100ms
- **PTT Command Format**: Unified command format (`ptt:` → `setPTT:`)

### Fixed
- **TX→RX Switching Delay**: Fixed PTT command not reaching backend
- **Audio TX Stop Command**: Now properly triggers PTT release
- **Control TRX Command Format**: Corrected PTT command format in control_trx.js

### Removed
- **VPN Functionality**: Removed all VPN-related files and scripts
- **Bottom Navigation Bar**: Removed unused Radio/Memory/Settings/Digital buttons
- **Redundant Scripts**: Cleaned up unused VPN configuration scripts

### Performance
| Metric | V3.x | V4.0 | Improvement |
|--------|------|------|-------------|
| TX Latency | ~100ms | ~65ms | 35% faster |
| RX Latency | ~100ms | ~51ms | 49% faster |
| TX→RX Switch | 2-3s | <100ms | 95%+ faster |
| PTT Reliability | 95% | 99%+ | More reliable |

### Documentation
- Updated all architecture documents to v4.0.0
- Added comprehensive end-to-end analysis report
- Updated IFLOW.md with complete version history

---

## [V3.2.0] - 2025-01-15

### Added
- Mobile audio optimization
- TX→RX switching delay fix
- iOS Safari AudioContext suspend fix

### Fixed
- Mobile frequency/mode display update
- Mobile menu functionality (band, mode, filter, settings)

---

## [V3.1.0] - 2025-01-10

### Added
- Mobile audio and PTT optimization
- iPhone browser compatibility fixes

### Fixed
- Audio processing on mobile devices
- PTT button responsiveness

---

## [V3.0.0] - 2024-12-20

### Added
- Modern mobile interface (iPhone 15 optimized)
- AAC/ADPCM audio encoding support
- TCI protocol support
- NanoVNA vector network analyzer integration
- PWA support with manifest.json and service worker

### Changed
- Improved mobile touch interactions
- Enhanced audio quality

---

## [V2.0.0] - 2024-11-15

### Added
- System architecture redesign
- AudioWorklet low-latency playback
- Int16 encoding for 50% bandwidth reduction
- TLS encryption support
- User authentication

### Changed
- Migrated from ALSA to PyAudio for cross-platform support
- Optimized audio buffering

---

## [V1.0.0] - 2024-10-01

### Added
- Initial release based on F4HTB/Universal_HamRadio_Remote_HTML5
- Basic remote radio control functionality
- WebSocket-based audio streaming
- Hamlib/rigctld integration
- Web-based control interface

---

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).
Based on [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5).

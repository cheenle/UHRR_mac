# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

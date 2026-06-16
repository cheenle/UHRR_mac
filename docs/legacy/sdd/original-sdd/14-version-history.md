# 14. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| SDD V1.0 | 2026-03-15 | MRRC Team | Initial SDD document, IBM TeamSD methodology, 14 chapters |
| SDD V2.0 | 2026-05-02 | MRRC Team | Updated to V5.0.0: Mobile UI redesign, ATR-1000 anti-disconnect, Opus HPF support, spectrum analysis tool |
| SDD V2.1 | 2026-05-10 | MRRC Team | Updated to V5.1.0: RagChew TX audio preset, Web Audio full-chain processing |
| SDD V2.2 | 2026-05-18 | MRRC Team | Updated to V5.2.0: WDSP hash caching optimization, RX audio multi-node scheduling playback engine |

## Key Changes in V2.0 (V5.0.0)

### Updated Sections
- **Chapter 1**: Added V5.0 Mobile UI feature, updated architecture diagram
- **Chapter 3**: Added M6 (Mobile UI V5.0) and M7 (V5.0 Release) milestones
- **Chapter 6**: Added UC-009 (FT8 Automation) and UC-010 (Remote Service Management)
- **Chapter 8**: Added AD-008 (ATR-1000 Proxy Architecture) decision
- **Chapter 9**: Added 9.4 V5.0 Mobile Architecture section
- **Chapter 11**: Updated component inventory with new files
- **Chapter 13**: Updated risk and issue status based on production experience

### New Features Documented
- Mobile UI V5.0 complete redesign (modern CSS, responsive grid, touch-optimized)
- ATR-1000 anti-disconnect optimization
- Opus high-pass filter (HPF) support
- Spectrum analysis tool integration
- FT8/ULTRON digital mode integration
- Remote service management (SSH-based)

## Key Changes in V2.1 (V5.1.0)

### Updated Sections
- **Chapter 1**: Updated version info to V5.1.0
- **Chapter 7**: Added TX audio processing subject area for RagChew
- **Chapter 9**: Added Web Audio API full-chain audio processing architecture
- **Chapter 11**: Added RagChew audio nodes in component inventory

### New Features Documented
- RagChew TX audio preset (EQ + compressor + noise gate via Web Audio API)
- Low-cut 150Hz, mid-cut -2dB@500Hz, presence +3dB@2.4kHz, high-cut 3kHz
- Dynamic compressor 3:1 ratio for smooth volume leveling
- Noise gate with -50dB threshold for silent background
- Safari setValueAtTime compatibility fix (critical bug resolution)

## Key Changes in V2.2 (V5.2.0)

### Updated Sections
- **Chapter 1**: Updated version info to V5.2.0
- **Chapter 9**: Added multi-BufferSourceNode scheduling architecture for RX audio
- **Chapter 11**: Updated component inventory with RX playback engine changes

### New Features Documented
- RX audio multi-node scheduling playback engine (gap-free inter-frame alignment)
- WDSP config hash caching for reduced per-frame CPU overhead
- Opus frame-aligned capture buffer (960 samples @ 48kHz → 320 samples @ 16kHz)
- AudioContext resume handling for browser auto-suspend compatibility

---

*This document follows IBM Team Solution Design (TeamSD) methodology v2.3.2*
*Document ID: SDD-MRR-2026-001*

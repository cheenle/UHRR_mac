# 3. Project Definition (ENG 343)

## 3.1 Project Attributes

| Attribute | Value |
|-----------|-------|
| Project Name | MRRC (Mobile Remote Radio Control) |
| Project Type | Remote radio control system |
| Target Users | Amateur radio operators (HAM) |
| Deployment Platform | macOS / Linux / Windows |
| User Platform | Web browser (mobile / desktop) |
| Current Version | V5.0.0 |
| License | GPL-3.0 |
| Repository | github.com/cheenle/UHRR_mac |

## 3.2 Project Scope

### In Scope
- Mobile-optimized Web UI (V5.0 modern CSS framework)
- Desktop Web UI (responsive fallback)
- Tornado WebSocket server for real-time audio and control
- Cross-platform audio processing via PyAudio
- WDSP DSP integration (NR2/NB/ANF/AGC)
- ATR-1000 antenna tuner integration with smart learning
- AI voice assistant (Whisper + Qwen3-TTS)
- CW real-time decoding (ONNX frontend)
- FT8/ULTRON digital mode integration
- Multi-instance deployment support
- REST API for external software integration
- User authentication system
- SSL/TLS encryption

### Out of Scope
- Radio hardware development
- Native mobile app (iOS/Android)
- Cloud/SaaS hosting
- Panadapter/RTL-SDR spectrum display (planned future)

## 3.3 Success Criteria

| ID | Criterion | Measurement |
|----|-----------|-------------|
| SC1 | TX/RX switching delay < 100ms | Measured with timestamp logging |
| SC2 | PTT reliability >= 99% | PTT success / total attempts |
| SC3 | End-to-end audio delay < 100ms | Loopback measurement |
| SC4 | iOS Safari + Android Chrome support | Tested on current stable versions |
| SC5 | WDSP noise reduction >= 15dB | Spectral analysis comparison |

## 3.4 Major Milestones

| Milestone | Date | Deliverable |
|-----------|------|-------------|
| M1: Proof of Concept | 2024-10 | Basic TX/RX functionality |
| M2: Mobile Optimization | 2024-12 | mobile_modern.html interface |
| M3: DSP Integration | 2026-03 | WDSP NR2 noise reduction |
| M4: V4.9 Release | 2026-03-14 | Voice assistant, CW, multi-instance |
| M5: Audio Quality V4.8 | 2026-03 | Multi-format decoding, buffer optimization |
| M6: Mobile UI V5.0 | 2026-04 | Complete mobile redesign |
| M7: V5.0 Release | 2026-04-30 | ATR-1000 anti-disconnect, Opus HPF, spectrum analysis |

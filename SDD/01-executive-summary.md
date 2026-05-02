# 1. Executive Summary

## 1.1 Project Overview

**MRRC (Mobile Remote Radio Control)** is a professionally optimized web-based remote radio control system specifically designed for amateur radio operators. V5.0.0 represents a complete mobile UI overhaul while maintaining full desktop compatibility. The system enables HAM operators to remotely control radio equipment — including transmit (TX), receive (RX), frequency tuning, and parameter adjustment — through any modern web browser.

**Key Differentiator**: Mobile-first design with professional-grade DSP processing (WDSP), achieving sub-100ms TX/RX switching latency and 15-20dB noise reduction depth.

## 1.2 Design Goals

| Goal | Metric | Target |
|------|--------|--------|
| Mobile-first UI | Touch-optimized, PWA support, single-hand operation | V5.0 achieved |
| Ultra-low latency | TX/RX switching | < 100ms |
| PTT reliability | Press-to-transmit success rate | 99%+ |
| Professional DSP | WDSP NR2 spectral noise reduction | 15-20dB |
| End-to-end audio delay | Mic to speaker | < 100ms |
| System availability | Uptime | >= 99.5% |

## 1.3 Core Features

| Feature | Version | Description |
|---------|---------|-------------|
| Remote Radio Control | V1.0+ | Frequency, mode, VFO switching, PTT, S-meter |
| Real-time Audio Stream | V1.0+ | TX/RX bidirectional, Int16/Opus codec |
| DSP Processing | V4.8+ | WDSP: NR2/NB/ANF/AGC |
| Mobile UI V5.0 | V5.0 | Complete mobile redesign, modern CSS |
| ATR-1000 Integration | V4.5+ | Real-time power/SWR, smart learning, quick tune |
| AI Voice Assistant | V4.9 | Whisper ASR + Qwen3-TTS |
| CW Real-time Decode | V4.9 | ONNX frontend inference, QSO state machine |
| FT8/ULTRON | V4.9 | Digital mode automation, DXCC tracking |
| Multi-instance | V4.9 | Single server, multiple radios |
| Audio Recording | V4.8 | Browser-side recording, WAV/MP3 export |
| Remote Start/Stop | V4.8 | SSH-based service management |

## 1.4 Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│  Client Layer: Mobile/Desktop Browser, External Apps    │
├─────────────────────────────────────────────────────────┤
│  Service Layer: Tornado WebSocket Server (MRRC Main)    │
├─────────────────────────────────────────────────────────┤
│  Control Layer: Hamlib/rigctld, PyAudio, WDSP           │
├─────────────────────────────────────────────────────────┤
│  Device Layer: Radio Equipment, Audio Devices, ATR-1000 │
└─────────────────────────────────────────────────────────┘
```

## 1.5 Project Status

V5.0.0 is the current stable release. All core features are implemented and production-tested at `radio.vlsc.net:8877`. The mobile UI V5.0 represents a complete redesign of the user interface while maintaining full backend compatibility.

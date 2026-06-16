# 4. System Context (APP 011)

## 4.1 Users and System Interaction

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Users                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ HAM Operator │  │ HAM Operator │  │ External App │               │
│  │   (Mobile)   │  │  (Desktop)   │  │ (JTDX/WSJT)  │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                  │                  │                         │
│         ▼                  ▼                  ▼                         │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │                    MRRC System                         │            │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │            │
│  │  │ Web Browser │  │ WebSocket   │  │  REST API   │  │            │
│  │  │ (UI Layer)  │  │ (Audio/Ctrl)│  │   (:8080)   │  │            │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │            │
│  └─────────────────────────────────────────────────────────┘            │
│                               │                                         │
└───────────────────────────────┼─────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  Radio Device │     │ ATR-1000      │     │  rigctld      │
│  (IC-M710)    │     │ (Tuner)       │     │  (Hamlib)     │
└───────────────┘     └───────────────┘     └───────────────┘
```

## 4.2 External System Interfaces

| Interface | Protocol | Port/Path | Description |
|-----------|----------|-----------|-------------|
| Web UI | HTTPS/WSS | 443/8877 | Browser client, served by Tornado |
| REST API | HTTP | 8080 | External application integration |
| ATR-1000 Proxy | Unix Socket | /tmp/atr1000_*.sock | Internal proxy communication |
| ATR-1000 Device | WebSocket | 192.168.1.63:60001 | Tuner hardware connection |
| rigctld | TCP | 4532 | Radio CAT control via Hamlib |
| Voice Assistant | In-process | - | Whisper ASR + Qwen3-TTS, local invocation by MRRC |
| FT8/ULTRON | UDP | 2237 | JTDX/WSJT-X integration |

## 4.3 Data Flow

| Flow | Direction | Description |
|------|-----------|-------------|
| TX Audio | Client → Radio | Microphone → Opus encode → WebSocket → PyAudio output → Radio |
| RX Audio | Radio → Client | Radio → PyAudio capture → WDSP DSP → Opus encode → WebSocket → AudioWorklet → Speaker |
| Control | Client ↔ Radio | Frequency/mode/PTT commands via WebSocket → rigctld → Radio |
| Meter Data | Radio → Client | S-meter, power, SWR via ATR-1000 proxy → WebSocket → Browser |
| Tuner Learning | TX Event → JSON | SWR/power sampling → atr1000_tuner.json frequency-parameter mapping |

## 4.4 System Boundaries

| Boundary | Description |
|----------|-------------|
| Client Boundary | Web application in browser, PWA offline support, AudioWorklet audio processing |
| Service Boundary | Tornado WebSocket server, event-driven I/O loop, multi-client session management |
| Device Boundary | Radio hardware (serial CAT), ATR-1000 tuner (network WebSocket), audio devices (PyAudio) |
| Network Boundary | TLS termination at server, WSS for audio stream, HTTPS for static assets |

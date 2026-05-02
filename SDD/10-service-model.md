# 10. Service Model (ART 0582)

## 10.1 Service Portfolio

| Service | Type | Description |
|---------|------|-------------|
| WebUIService | Core | Web user interface, serves static assets and UI |
| AudioStreamService | Core | Real-time bidirectional audio streaming (TX/RX) |
| ControlService | Core | Radio frequency, mode, PTT control via Hamlib |
| DSPProcessingService | Core | WDSP digital signal processing (NR2/NB/ANF/AGC) |
| ATRProxyService | Support | ATR-1000 tuner proxy, power/SWR display, smart learning |
| AuthService | Support | User authentication, session validation |
| SessionService | Support | WebSocket session lifecycle, client management |
| APIService | Extended | REST API for ATR-1000 control and status (atr1000_api_server.py, port 8080) |
| VoiceAssistantService | Extended | AI voice recognition (Whisper) and synthesis (Qwen3-TTS), local process invoked by MRRC |
| CWDecoderService | Extended | Real-time CW Morse code decoding (ONNX/PyTorch) |
| FT8Service | Extended | FT8 digital mode automation via ULTRON |

## 10.2 Service Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Service Hierarchy                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                     User Service Layer                            │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │  │
│  │  │ Web UI      │  │ Voice       │  │ CW Decoder  │             │  │
│  │  │ Interface   │  │ Assistant   │  │ Interface   │             │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘             │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                     Business Service Layer                        │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │  │
│  │  │ Audio Stream│  │ Radio       │  │ ATR        │             │  │
│  │  │ Management  │  │ Control     │  │ Management │             │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘             │  │
│  │  ┌─────────────┐  ┌─────────────┐                              │  │
│  │  │ DSP         │  │ Session     │                              │  │
│  │  │ Processing  │  │ Management  │                              │  │
│  │  └─────────────┘  └─────────────┘                              │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                     Infrastructure Service Layer                  │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │  │
│  │  │ WebSocket   │  │ Audio I/O   │  │ Network    │             │  │
│  │  │ Transport   │  │ (PyAudio)   │  │ Communication│            │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘             │  │
│  │  ┌─────────────┐  ┌─────────────┐                              │  │
│  │  │ Hamlib      │  │ File       │                              │  │
│  │  │ Integration │  │ Storage    │                              │  │
│  │  └─────────────┘  └─────────────┘                              │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 10.3 Service Dependencies

```
                    ┌─────────────────────┐
                    │   WebUIService      │
                    └──────────┬──────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
           ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│AudioStreamService│ │ControlService    │ │ATRProxyService   │
└────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
          ┌─────────────────┐  ┌─────────────────┐
          │DSPProcessingSvc │  │SessionService   │
          └─────────────────┘  └────────┬────────┘
                                        │
                                        ▼
                                ┌───────────────┐
                                │AuthService    │
                                └───────────────┘

  Extended Services (optional):
  VoiceAssistantService → AudioStreamService
  CWDecoderService → AudioStreamService
  FT8Service → ControlService
```

## 10.4 Service Interface Summary

| Service | Input | Output | Protocol |
|---------|-------|--------|----------|
| WebUIService | HTTP GET | HTML/CSS/JS assets | HTTP/HTTPS |
| AudioStreamService | Audio frames (Opus/Int16) | Audio frames + meter data | WebSocket /WSCTRX |
| ControlService | JSON command strings | JSON response strings | WebSocket /WSCTRX |
| DSPProcessingService | Raw audio samples | Processed audio samples | In-process function call |
| ATRProxyService | Frequency sync, poll requests | Power/SWR data | Unix Socket → WebSocket /WSATR1000 |
| AuthService | Username, password | Auth token | HTTP POST |
| SessionService | WebSocket connection | Session lifecycle events | In-process |
| APIService | HTTP REST requests | JSON responses | HTTP :8080 |

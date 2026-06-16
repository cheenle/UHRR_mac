# 11. Component Model (ART 0515)

## 11.1 Component Inventory

| Component | Type | File | Responsibility |
|-----------|------|------|----------------|
| MRRCServer | Core | `MRRC` | Tornado main server, WebSocket handlers, HTTP routes |
| AudioCapture | Core | `audio_interface.py` | PyAudio audio capture, device enumeration |
| AudioPlayer | Core | `audio_interface.py` | PyAudio audio playback, device enumeration |
| WDSPProcessor | Core | `wdsp_wrapper.py` | WDSP DSP processing (NR2/NB/ANF/AGC) |
| AudioEncoder | Core | `MRRC`, `opus/` | Audio encoding (Int16/Opus) |
| AudioDecoder | Core | `MRRC`, `opus/` | Audio decoding (Int16/Float32/Opus) |
| HamlibClient | Core | `hamlib_wrapper.py` | rigctld TCP communication, radio control |
| ControlHandler | Core | `MRRC` | Control command parsing and dispatching |
| SessionManager | Support | `MRRC` | WebSocket session tracking, client state |
| AuthManager | Support | `MRRC` | SQLite user authentication (MRRC_users.db) |
| ATRProxyClient | Support | `MRRC`, `atr1000_proxy.py` | Unix Socket ATR-1000 proxy client |
| RESTAPIHandler | Extended | `MRRC`, `atr1000_api_server.py` | REST API endpoint handlers |
| VoiceAssistantClient | Extended | `voice_assistant_service.py` | Whisper ASR + Qwen3-TTS client |
| CWDecoder | Extended | `MRRC` (frontend: `www/cw_live.html`) | ONNX CW decoder, QSO state machine |

## 11.2 Component Interface Definitions

```
┌─────────────────┐
│  MRRCServer    │
├─────────────────┤
│ +start()       │
│ +stop()        │
│ +handle_ws()   │
│ +handle_http() │
└────────┬────────┘
         │
┌────────┼────────────────────────────────────────────────┐
│        ▼                                                 │
│ ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│ │AudioCapture │  │AudioPlayer  │  │ControlHandler    │  │
│ │+start()     │  │+play()      │  │+setFreq(freq)    │  │
│ │+stop()      │  │+stop()      │  │+setMode(mode)    │  │
│ │+read(buf)   │  │+write(buf)  │  │+setPTT(state)    │  │
│ └──────┬──────┘  └──────┬──────┘  └────────┬─────────┘  │
│        │                 │                  │            │
│        ▼                 ▼                  ▼            │
│ ┌─────────────┐  ┌───────────────────────┐  ┌────────┐  │
│ │AudioEncoder │  │    WDSPProcessor      │  │Hamlib  │  │
│ │+encode(buf) │  │+process(buffer)       │  │Client  │  │
│ │+decode(buf) │  │+setNR2(enabled,level) │  │+send() │  │
│ └──────┬──────┘  │+setAGC(mode)          │  │+recv() │  │
│        │         │+setANF(enabled)       │  └────────┘  │
│        │         │+setNB(enabled)        │              │
│        │         └───────────────────────┘              │
│        │                                               │
│        ▼                                               │
│ ┌─────────────┐  ┌───────────────────┐                │
│ │ATRProxyClnt │  │SessionManager     │                │
│ │+connect()   │  │+add_client(ws)    │                │
│ │+send(cmd)   │  │+remove_client(ws) │                │
│ │+recv()      │  │+broadcast(data)   │                │
│ └─────────────┘  └───────────────────┘                │
└───────────────────────────────────────────────────────┘
```

## 11.3 Component Collaboration Paths

| Collaboration | Path | Description |
|--------------|------|-------------|
| TX Audio Path | Mic → AudioCapture → AudioEncoder → MRRCServer → PyAudio Output → Radio | Browser microphone to radio transmission |
| RX Audio Path | Radio → PyAudio Input → WDSPProcessor → AudioEncoder → MRRCServer → WebSocket → Browser AudioWorklet → Speaker | Radio reception to browser speaker |
| Control Path | Browser → WebSocket → ControlHandler → HamlibClient → rigctld TCP → Radio CAT | UI control to radio parameter change |
| ATR Path | MRRCServer → ATRProxyClient (Unix Socket) → ATR-1000 Proxy → ATR-1000 Device (WebSocket :60001) | Meter data and tuner control |
| Voice Assistant | Browser → MRRC → VoiceAssistantClient (Whisper) → Qwen3-TTS → Browser | Voice command processing |
| CW Decoding | Radio → PyAudio → WebSocket → Browser (ONNX Runtime) → Text Display | Real-time Morse decoding |

## 11.4 File-to-Component Mapping

| Component | Primary File | Supporting Files |
|-----------|-------------|------------------|
| MRRCServer | `MRRC` | `MRRC.conf` |
| Audio Interface | `audio_interface.py` | PyAudio library |
| WDSP Processor | `wdsp_wrapper.py` | libwdsp |
| Hamlib Client | `hamlib_wrapper.py` | rigctld (Hamlib) |
| ATR Proxy | `atr1000_proxy.py` | `atr1000_tuner.json` |
| ATR API Server | `atr1000_api_server.py` | - |
| Voice Assistant | `voice_assistant_service.py` | Whisper, Qwen3-TTS |
| Opus Codec | `opus/` directory | libopus |
| Mobile UI V5.0 | `www/mobile_modern.html` | `mobile_modern.js`, `mobile_modern.css` |
| Desktop UI | `www/index.html` | `controls.js` |
| FT8/ULTRON | `ft8/ultron.py` | JTDX/WSJT-X |
| User Auth | `MRRC` (embedded) | `MRRC_users.db` |

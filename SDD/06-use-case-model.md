# 6. Use Case Model (ART 0508)

## 6.1 Actors

| Actor | Description |
|-------|-------------|
| HAM Operator | Amateur radio operator, controls radio via browser (mobile or desktop) |
| External App | Third-party software (JTDX, WSJT-X, flrig) via REST API |
| System Admin | Server administrator for deployment and maintenance |

## 6.2 Core Use Cases

### UC-001: Remote Transmit (TX)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       UC-001: Remote Transmit                            │
├─────────────────────────────────────────────────────────────────────────┤
│ Actor: HAM Operator                                                      │
│ Goal: Transmit voice to radio via browser microphone                     │
│ Precondition: WebSocket connected, power ON                              │
│ Postcondition: Audio successfully transmitted to radio                   │
│                                                                         │
│ Basic Flow:                                                              │
│ 1. User presses PTT button                                               │
│ 2. System sends PTT command to radio (with warm-up frames)               │
│ 3. User speaks, browser captures audio via Web Audio API                 │
│ 4. Audio encoded as Opus (16kHz, 20kbps)                                 │
│ 5. Transmitted via WebSocket to server                                   │
│ 6. Server decodes and plays to radio via PyAudio                         │
│ 7. User releases PTT                                                     │
│ 8. System stops transmission                                             │
│                                                                         │
│ Alternative Flows:                                                       │
│ 2a. PTT command failed: Retry 3 times, 50ms interval                     │
│ 4a. Audio encoding failed: Fallback to PCM raw format                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### UC-002: Remote Receive (RX)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       UC-002: Remote Receive                             │
├─────────────────────────────────────────────────────────────────────────┤
│ Actor: HAM Operator                                                      │
│ Goal: Receive radio audio and play in browser                            │
│ Precondition: WebSocket connected, power ON                              │
│ Postcondition: Audio successfully played in browser                      │
│                                                                         │
│ Basic Flow:                                                              │
│ 1. System captures audio from radio (PyAudio, 48kHz)                     │
│ 2. Audio processed: DC removal → AGC pre-amp → soft limiter              │
│ 3. Optional WDSP: NR2 → NB → ANF → AGC                                  │
│ 4. Audio encoded as Opus (16kHz, 20kbps)                                │
│ 5. Transmitted via WebSocket to browser                                  │
│ 6. Browser decodes Opus, plays via AudioWorklet                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### UC-003: Radio Parameter Control

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       UC-003: Radio Parameter Control                    │
├─────────────────────────────────────────────────────────────────────────┤
│ Actor: HAM Operator                                                      │
│ Goal: Control radio frequency, mode, and other parameters                │
│ Precondition: rigctld connected                                          │
│ Postcondition: Parameters successfully set                               │
│                                                                         │
│ Basic Flow:                                                              │
│ 1. User adjusts frequency/mode in UI                                     │
│ 2. Control command sent to MRRC via WebSocket                            │
│ 3. MRRC forwards command to rigctld                                      │
│ 4. rigctld controls radio via CAT interface                              │
│ 5. Execution result returned                                             │
│ 6. UI updated to reflect new state                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

## 6.3 Extended Use Cases

| ID | Use Case | Description |
|----|----------|-------------|
| UC-004 | Antenna Tuner Control | ATR-1000 power/SWR display, tuning, smart learning |
| UC-005 | Voice Assistant | AI speech recognition and control commands |
| UC-006 | CW Decoding | Real-time Morse code decoding with QSO state machine |
| UC-007 | Audio Recording | Browser-side QSO recording, WAV/MP3 export |
| UC-008 | Multi-instance Management | Multiple independent radio instances |
| UC-009 | FT8 Automation | ULTRON CQ, smart response, DXCC tracking |
| UC-010 | Remote Service Management | SSH-based start/stop/status of MRRC services |

## 6.4 Use Case Relationships

```
                    ┌─────────────────┐
                    │  HAM Operator  │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   UC-001 TX   │   │   UC-002 RX   │   │ UC-003 Control│
│  Remote TX    │   │  Remote RX    │   │ Radio Control │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                    ▼                 ▼
             ┌──────────┐     ┌──────────┐
             │ UC-004   │     │ UC-005   │
             │ ATU Ctrl │     │ Voice AI │
             └──────────┘     └──────────┘
                    │
                    ▼
             ┌──────────┐
             │ UC-006   │
             │ CW Decode│
             └──────────┘
```

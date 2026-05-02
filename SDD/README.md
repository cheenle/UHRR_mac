# MRRC SDD - Software Design Description

> **Mobile Remote Radio Control**
> IBM Team Solution Design (TeamSD) v2.3.2

---

## Document Index

| # | Chapter | ART Code | File |
|---|---------|----------|------|
| 1 | Executive Summary | - | [01-executive-summary.md](01-executive-summary.md) |
| 2 | Business Direction | BUS 411 | [02-business-direction.md](02-business-direction.md) |
| 3 | Project Definition | ENG 343 | [03-project-definition.md](03-project-definition.md) |
| 4 | System Context | APP 011 | [04-system-context.md](04-system-context.md) |
| 5 | Non-Functional Requirements | ART 0507 | [05-non-functional-requirements.md](05-non-functional-requirements.md) |
| 6 | Use Case Model | ART 0508 | [06-use-case-model.md](06-use-case-model.md) |
| 7 | Subject Area Model | APP 408 | [07-subject-area-model.md](07-subject-area-model.md) |
| 8 | Architecture Decisions | ART 0513 | [08-architecture-decisions.md](08-architecture-decisions.md) |
| 9 | Architecture Overview | ART 0512 | [09-architecture-overview.md](09-architecture-overview.md) |
| 10 | Service Model | ART 0582 | [10-service-model.md](10-service-model.md) |
| 11 | Component Model | ART 0515 | [11-component-model.md](11-component-model.md) |
| 12 | Operational Model | ART 0522 | [12-operational-model.md](12-operational-model.md) |
| 13 | Feasibility Assessment | ART 0530 | [13-feasibility-assessment.md](13-feasibility-assessment.md) |
| 14 | Version History | - | [14-version-history.md](14-version-history.md) |

---

## Quick Facts

| Attribute | Value |
|-----------|-------|
| **Document ID** | SDD-MRR-2026-001 |
| **Version** | V2.0 (V5.0.0) |
| **Date** | 2026-05-02 |
| **Status** | Released |
| **Methodology** | IBM TeamSD v2.3.2 |
| **Project** | MRRC - Mobile Remote Radio Control |

## System at a Glance

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        MRRC System Architecture V5.0.0                   │
├─────────────────────────────────────────────────────────────────────────┤
│  Client Layer                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  │
│  │ Mobile UI    │  │ Desktop UI   │  │ CW Decode    │  │ FT8 Ctrl │  │
│  │ mobile_modern │  │ modern.html  │  │ cw_live.html │  │ ft8_ultron│  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────┬─────┘  │
│         │                  │                 │                │        │
│         └──────────────────┴─────────────────┴────────────────┘        │
│                                    │                                     │
│                            HTTPS / WebSocket                             │
│                                    ▼                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  Service Layer                                                           │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │                      MRRC Main (Tornado)                       │      │
│  ├──────────────────────────────────────────────────────────────┤      │
│  │  /WSCTRX     - Main control + audio (PTT/frequency/mode)     │      │
│  │  /WSATR1000  - Tuner power/SWR real-time display             │      │
│  │  /WSCW       - CW backend decode (optional)                  │      │
│  └──────┬─────────────────────────────────────────────┬──────────┘      │
│         │                                             │                  │
│         ▼                                             ▼                  │
│  ┌─────────────────┐                         ┌──────────────────┐     │
│  │  rigctld        │                         │  ATR-1000 Proxy  │     │
│  │  (Hamlib)       │                         │  atr1000_proxy   │     │
│  └────────┬────────┘                         └────────┬─────────┘     │
│           │                                            │                │
│           ▼                                            ▼                │
│  ┌─────────────────┐                         ┌──────────────────┐     │
│  │  Transceiver    │                         │  ATR-1000 Tuner  │     │
│  │  IC-M710       │                         │  Power/SWR Meter │     │
│  └─────────────────┘                         └──────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | HTML5/CSS3/Vanilla JS | Web UI, zero dependencies |
| Backend | Python 3.12+ / Tornado | WebSocket server |
| Audio | PyAudio | Cross-platform I/O |
| DSP | WDSP | NR2/NB/ANF/AGC |
| Control | Hamlib/rigctld | Radio CAT interface |
| Codec | Opus | Low-latency audio (16kHz, 20kbps) |
| Voice AI | Whisper + Qwen3-TTS | Speech recognition/synthesis |
| CW Decode | ONNX Runtime | Browser-first Morse decoding |
| FT8 | ULTRON / JTDX | Digital mode automation |

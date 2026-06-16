# 7. Subject Area Model (APP 408)

## 7.1 Core Entity Relationships

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Core Entity Relationships                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────┐         ┌──────────┐         ┌──────────┐            │
│   │  Client  │────────▶│ Session   │◀────────│  Radio   │            │
│   │  Client  │         │  Session  │         │  Radio   │            │
│   └──────────┘         └────┬─────┘         └──────────┘            │
│                             │                                          │
│                             │ 1:N                                      │
│                             ▼                                          │
│                      ┌──────────────┐                                 │
│                      │   AudioFlow  │                                 │
│                      │  Audio Stream│                                 │
│                      └──────┬───────┘                                 │
│                             │                                          │
│              ┌──────────────┼──────────────┐                          │
│              │              │              │                          │
│              ▼              ▼              ▼                          │
│       ┌──────────┐  ┌──────────┐  ┌──────────┐                    │
│       │TXAudio   │  │RXAudio   │  │MeterData │                    │
│       │TX Audio  │  │RX Audio  │  │Meter Data│                    │
│       └──────────┘  └──────────┘  └──────────┘                    │
│                                                                         │
│       ┌──────────┐         ┌──────────┐                            │
│       │TunerRec  │◀────────│Frequency │                            │
│       │Tuner Rec │  Freq   │  Freq    │                            │
│       └──────────┘         └──────────┘                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 7.2 Entity Definitions

| Entity | Attributes | Description |
|--------|-----------|-------------|
| Client | id, type (mobile/desktop/api), platform, browser, ip_address | Connected client session |
| Session | id, client_id, start_time, auth_token, ws_connection | WebSocket session lifecycle |
| Radio | id, model (e.g. IC-M710), rigctld_host, rigctld_port, audio_device | Radio hardware configuration |
| AudioFlow | session_id, direction (TX/RX), codec (Int16/Opus), sample_rate, buffer_size | Audio stream configuration |
| TXAudio | flow_id, samples (bytes), timestamp, sequence_number | Transmit audio data frames |
| RXAudio | flow_id, samples (bytes), timestamp, wdsp_flags (NR2/NB/ANF/AGC) | Receive audio data frames |
| MeterData | freq_hz, mode, power_w, swr, smeter_dbm, timestamp | Real-time meter readings |
| TunerRecord | freq_hz, sw (switch), ind (inductor), cap (capacitor), swr_avg, swr_min, swr_max, sample_count, last_update, needs_verify | Smart ATU learning record |
| WDSPConfig | enabled, sample_rate, buffer_size, nr2_enabled, nr2_level, nb_enabled, anf_enabled, agc_mode | WDSP processing parameters |

## 7.3 Entity Relationships Summary

| Relationship | Cardinality | Description |
|-------------|-------------|-------------|
| Client → Session | 1:1 | Each client has one active session |
| Session → AudioFlow | 1:N | Each session can have multiple audio flows (TX and RX) |
| AudioFlow → TXAudio/RXAudio | 1:N | Each flow contains many audio frames |
| Radio → MeterData | 1:N | Each radio produces many meter readings |
| Frequency → TunerRecord | 1:1 (per freq) | Each frequency maps to one learned tuner configuration |
| Session → MeterData | 1:N | Each session receives meter data updates |

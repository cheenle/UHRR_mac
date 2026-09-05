# Current System Architecture

## Scope

This document describes the currently implemented MRRC runtime, based on the main entrypoints and code paths:

- `MRRC`
- `MRRC.conf`
- `www/index.html`
- `www/mobile_modern.html`
- JavaScript files loaded by those two pages
- Python modules imported by `MRRC`

## Runtime Components

| Layer | Component | Current Implementation |
| --- | --- | --- |
| Web server | `MRRC` | Tornado HTTPS server with HTTP routes, WebSocket routes, auth, config UI, static file serving |
| Desktop UI | `www/index.html` | Main desktop interface, loaded by `/` |
| Mobile UI | `www/mobile_modern.html` | Main mobile interface, loaded by `/mobile`; depends on hidden desktop-compatible DOM elements for `controls.js` |
| Shared browser logic | `www/controls.js` | Audio RX/TX, WebSocket setup, TRX control, frequency/mode/PTT UI sync |
| Mobile browser logic | `www/mobile_modern.js` | Mobile layout behavior, ATR-1000 display, memory channels, mobile control panels |
| PTT/TX flow | `www/modules/ptt_manager.js`, `www/tx_button_optimized.js` | Fast PTT path, release ACK retry, RX buffer flush, AudioWorklet flush, ATR TX hooks |
| Audio backend | `audio_interface.py` | PyAudio capture/playback, Opus RX/TX support, WDSP/RNNoise hooks, recording buffers |
| Radio control | `TRXRIG` in `MRRC`, `hamlib_wrapper.py` | rigctld socket commands for frequency, mode, PTT, S-meter |
| DSP | `wdsp_wrapper.py`, `DSP/wdsp/` | Optional WDSP processing: NR2, NB, ANF, NF, AGC, bandpass |
| Panadapter | `www/panadapter/` | Legacy UI route remains; RTL-SDR runtime dependency is disabled by default |
| ATR-1000 bridge | `ATR1000ProxyManager` in `MRRC` | Unix Socket client, bridges proxy data to `/WSATR1000` |
| ATR-1000 proxy | `atr1000_proxy.py` | Single device connection to ATR-1000, dynamic polling, learning, quick tune |
| ATR-1000 storage/API | `atr1000_tuner.py`, `atr1000_api_server.py` | JSON learning records and optional REST API through proxy socket |
| Recording | `audio_interface.py`, `www/recordings.html` | RX/TX recording buffers, `/api/recordings`, `/recordings/<file>` download |
| Channel memory | `memory_channels.json`, `/api/mem_channels` | Per-user 6-channel memory storage |
| Voice assistant | `voice_assistant_service.py` | Separate optional service, not part of the main `MRRC` Tornado routes |

## HTTP Routes

| Route | Handler | Purpose |
| --- | --- | --- |
| `/` | `MainHandler` | Reads and serves `www/index.html` |
| `/mobile` | `MobileHandler` | Reads and serves `www/mobile_modern.html` |
| `/login`, `/logout` | auth handlers | Login/logout when auth is enabled |
| `/CONFIG` | `ConfigHandler` | Web config editor; posts write `MRRC.conf` |
| `/test` | `TestRadioHandler` | Basic radio communication test |
| `/api/mem_channels` | `MemChannelsHandler` | Channel memory get/save |
| `/api/recordings` | `RecordingsListHandler` | Recording list |
| `/recordings/<file>` | `RecordingsDownloadHandler` | Recording download |
| `/(panfft.*)` | static handler | Serves `www/panadapter/` |
| `/(.*)` | static handler | Serves `www/` |

## WebSocket Routes

| Route | Handler | Purpose |
| --- | --- | --- |
| `/WSaudioRX` | `WS_AudioRXHandler` | Server-to-browser RX audio frames; supports Int16 and Opus mode negotiation |
| `/WSaudioTX` | `WS_AudioTXHandler` | Browser-to-server TX audio frames and TX init/stop messages |
| `/WSCTRX` | `WS_ControlTRX` | Frequency, mode, PTT, WDSP, tune, CQ, recording commands |
| `/WSpanFFT` | `WS_panFFTHandler` | Legacy FFT WebSocket; disabled by default without RTL-SDR dependency |
| `/WSATR1000` | `WS_ATR1000Handler` | ATR-1000 meter/relay/tune bridge |
| `/WSATU` | `WS_ATUAutoTunerHandler` | ATU automatic tuning command surface |

Note: `/WSFT8` and the FT8/CW decoder features were removed in V5.7.1.

## Main Data Flows

### RX Audio

```text
radio audio input -> PyAudioCapture -> optional WDSP/RNNoise -> Int16/Opus frames -> /WSaudioRX -> controls.js -> Opus decode if enabled -> AudioWorklet/ScriptProcessor -> speaker
```

### TX Audio

```text
browser microphone -> Web Audio API -> TX EQ/RagChew chain -> tx-capture AudioWorklet (ScriptProcessor fallback on iOS) -> 48kHz Opus tagged frames -> /WSaudioTX -> PyAudioPlayback -> radio audio output
```

### Radio Control

```text
browser controls -> /WSCTRX -> TRXRIG -> rigctld TCP -> radio CAT/PTT
```

`/WSCTRX` also carries the IC-M710 `setAGC`/`setRFGain` level commands (rigctld `L AGC`/`L RF` → icm710 NMEA `AGC ON/OFF`, `RFG 0-9`).

### ATR-1000

```text
ATR-1000 device -> WebSocket device protocol -> atr1000_proxy.py -> Unix Socket -> MRRC ATR1000ProxyManager -> /WSATR1000 -> mobile_modern.js display and tune hooks
```

The proxy answers from cache only; TX `stop` zeroes the cached power/SWR (no ghost readings during RX), and `MRRC` fast-polls (250 ms) off the CTRX PTT state, broadcasting on the IOLoop thread.

## Runtime Boundaries

The main `MRRC` process owns the HTTPS/WSS web application and direct radio/audio integration. The following are separate or optional:

- `atr1000_proxy.py`: separate ATR-1000 device proxy process.
- `atr1000_api_server.py`: optional REST API process for external tools.
- `voice_assistant_service.py`: separate voice assistant process, default port `8878`.
- `website/`: static marketing/documentation site, not served by the MRRC app.

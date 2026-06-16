# Capability Map

This map lists capabilities that are implemented in the current codebase and identifies their runtime surface.

## Primary Capabilities

| Capability | Status | Main Files | Runtime Surface |
| --- | --- | --- | --- |
| Desktop radio control | Implemented | `MRRC`, `www/index.html`, `www/controls.js` | `/`, `/WSCTRX`, `/WSaudioRX`, `/WSaudioTX` |
| Mobile radio control | Implemented | `MRRC`, `www/mobile_modern.html`, `www/mobile_modern.js`, `www/controls.js` | `/mobile`, static `/mobile_modern.html`, same WebSockets |
| Authentication | Implemented | `MRRC`, `MRRC.conf`, `MRRC_users.db` | `FILE` auth by default; redirects to `/login` |
| Frequency/mode/PTT | Implemented | `TRXRIG` in `MRRC`, `hamlib_wrapper.py` | `WSCTRX` commands: `setFreq`, `getFreq`, `setMode`, `getMode`, `setPTT`, `getPTT` |
| TX/RX audio | Implemented | `audio_interface.py`, `www/controls.js`, `www/modules/opus_*` | `/WSaudioRX`, `/WSaudioTX` |
| PTT safety and release recovery | Implemented | `www/modules/ptt_manager.js`, `www/tx_button_optimized.js`, `MRRC`, `audio_interface.py` | release ACK retry, queue flush, Opus accumulator flush, server TOT monitor |
| WDSP DSP controls | Implemented when library exists | `audio_interface.py`, `wdsp_wrapper.py`, `www/mobile_modern.js`, `www/controls.js` | `WSCTRX` `setWDSP*` commands |
| Panadapter FFT | Optional | `MRRC`, `www/panadapter/` | `/WSpanFFT`, `/panfft.html`; depends on RTL-SDR |
| ATR-1000 meter/tuner bridge | Implemented, separate proxy required | `MRRC`, `atr1000_proxy.py`, `atr1000_tuner.py`, `www/mobile_modern.js` | `/WSATR1000`, Unix Socket proxy |
| ATR-1000 REST API | Optional separate process | `atr1000_api_server.py`, `atr1000_tuner.py` | default `127.0.0.1:8080`; talks to proxy socket |
| Tune and CQ | Implemented | `MRRC`, `www/modules/tune_cq.js`, `www/tx_button_optimized.js` | `WSCTRX` actions `tune`, `cq`, `cq_complete` |
| Channel memory | Implemented | `MRRC`, `memory_channels.json`, `www/mobile_modern.js` | `/api/mem_channels` |
| Recording | Implemented | `audio_interface.py`, `MRRC`, `www/mobile_modern.js`, `www/recordings.html` | `WSCTRX` `startRecording/stopRecording`, `/api/recordings`, `/recordings/<file>` |
| FT8 browser bridge | Implemented | `MRRC`, `ft8_integration.py`, `www/ft8_ultron.html`, `www/ft8_ultron.js` | `/WSFT8`; JTDX/WSJT-X UDP 2238/2237 |
| CW live page | Browser page present | `www/cw_live.html`, `models/cw_decoder.onnx` | linked from mobile UI; uses CDN ONNX runtime |
| Multi-instance operation | Implemented in scripts/config convention | `mrrc_multi.sh`, `MRRC.radio*.conf`, `MRRC` | separate web/rigctld ports and Unix sockets |
| Docker single instance | Implemented | `Dockerfile`, `docker-compose.yml` | maps host `8877:8877`, mounts config/certs/data |

## Optional Or Peripheral Capabilities

| Capability | Current Boundary |
| --- | --- |
| Voice assistant | Separate service in `voice_assistant_service.py`, default port `8878`; not a route in main `MRRC` |
| Static website | `website/` and `deploy_website.sh`; not served by the MRRC runtime |
| EFHW knowledge base | `efhw-knowledge/`; useful project material, not needed for MRRC server startup |
| Video build tooling | `video_build/`; generated/tooling area, not part of MRRC runtime |
| Ant switch docs/tools | `ant_switch/`; separate integration/reference area |
| NanoVNA UI | `nanovna/`; separate static app/reference area |

## Critical Implementation Notes

- `www/mobile_modern.html` intentionally contains hidden desktop-compatible elements required by `www/controls.js`. Do not remove those as dead markup without runtime testing.
- `www/mobile_modern.js` depends on globals defined by `www/controls.js`; avoid redeclaring shared state.
- PTT release must clear server RX queues, the Python Opus accumulator, and browser audio buffers.
- `MRRC` `/CONFIG` posts always write `MRRC.conf`; this does not preserve a custom config path passed as `python3 MRRC <config-file>`.
- The current default port is `8877`; older tools and docs may still mention `8888`.
- Current TLS config uses `certs/radio.vlsc.net.pem` and `certs/radio.vlsc.net.key`, not root `UHRH.crt` and `UHRH.key`.

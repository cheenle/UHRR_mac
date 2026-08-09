# AGENTS.md

## Start Here
- Main app entrypoint is the executable Python/Tornado script `MRRC`; it reads `MRRC.conf` by default or `python3 MRRC <config-file>` for another config.
- Active default server port is `8877` from `MRRC.conf` and `docker-compose.yml`; older docs/tools may still say `8888`.
- Root `/` serves `www/index.html`; `/mobile` serves `www/mobile_modern.html`; static assets are served from `www/`.
- Auth defaults to `FILE` in `MRRC.conf`, so browser requests can redirect to `/login` unless authenticated.
- `/CONFIG` posts always write `MRRC.conf` and restart `./MRRC`; do not assume it preserves a custom config path used by `python3 MRRC <config-file>`.

## Run And Verify
- Start directly for local debugging with `python3 ./MRRC` or `./MRRC` after installing system/audio/radio deps.
- `./mrrc_control.sh start` starts `rigctld`, MRRC, then `atr1000_proxy.py`; edit its hard-coded device/model values before trusting it on new hardware.
- `mrrc_control.sh` currently invokes `Python "$SCRIPT_DIR/MRRC"` in `start_mrrc`; if service start fails, try direct `python3 ./MRRC` before debugging the app.
- Docker single-instance command is `docker compose up --build` or `docker-compose up --build`; it maps host `8877:8877`, mounts `MRRC.conf`, `certs/`, `atr1000_tuner.json`, `MRRC_users.db`, `logs/`, and `/dev`.
- Dockerfile copies only selected runtime files plus `www/`; if adding a backend module needed in containers, update `Dockerfile` explicitly.
- Multi-instance workflow uses `./mrrc_multi.sh create <name>`, edit `MRRC.<name>.conf`, then `./mrrc_multi.sh start <name>`; each instance needs unique web port, rigctld port, and Unix socket.
- `mrrc_multi.sh` uses a `detect_python()` helper to pick the interpreter for MRRC startup (no longer hardcodes `/opt/local/bin/python3.12`); instance names are validated to `[A-Za-z0-9_-]` to prevent shell→Python string-literal injection.

## Tests And Diagnostics
- No root manifest, root test runner, pre-commit config, or CI workflow is present; use focused dev tools instead of assuming pytest/npm for the whole repo.
- Dependency smoke test: `python3 dev_tools/test_installation.py`; it checks Python 3.7+, imports, `MRRC.conf`, and legacy root cert names `UHRH.crt`/`UHRH.key`.
- Audio device/capture/playback checks: `python3 dev_tools/test_audio.py` and `python3 dev_tools/test_audio_capture.py`; these require usable local audio devices.
- `dev_tools/test_connection.py` targets `https://localhost:8888/`, which does not match the current default `8877`; adjust before using it.
- Hardware-facing checks may require PortAudio/PyAudio, Hamlib/rigctld, serial devices, RTL-SDR, TLS certs, or ATR-1000 network access.

## Architecture Notes
- Radio control goes through `rigctld`/Hamlib via `hamlib_wrapper.py`; audio I/O goes through PyAudio abstractions in `audio_interface.py`.
- WebSocket endpoints are defined near the bottom of `MRRC`: `/WSaudioRX`, `/WSaudioTX`, `/WSCTRX`, `/WSpanFFT`, `/WSATR1000`, and `/WSATU`.
- `www/controls.js` owns shared browser control/audio behavior; `www/mobile_modern.js` depends on `controls.js` and should not redeclare its globals.
- Mobile HTML contains hidden desktop-compatible elements required by `controls.js`; do not remove them as dead markup without checking runtime dependencies.
- The active RX engine lives in `www/controls.js` with the `rx_worklet_processor.js` watermark buffer; `www/audio_rx.js` (V5.2 `BufferSourceNode` scheduler) is deprecated legacy and incompatible with the tagged wire format — no page should load it.
- TX capture runs on `tx_worklet_processor.js` (`tx-capture` AudioWorklet, 960-sample/20 ms frames posted to `OpusEncoderProcessor.pushSamples`); `MediaHandler._setupScriptProcessor` is the iOS/legacy fallback — both paths must stay functional.
- WDSP integration is in `wdsp_wrapper.py` plus `DSP/wdsp/`; macOS builds produce `libwdsp.dylib`, Linux builds produce `libwdsp.so`.
- ATR-1000 integration uses `atr1000_proxy.py` with a Unix socket defaulting to `/tmp/atr1000_proxy.sock`; multi-instance configs override this via `[INSTANCE_SETTINGS]`. The proxy answers from cache only (request/response); TX `stop` zeroes the cached power/SWR so RX never shows ghost readings, and `MRRC`'s `ATR1000ProxyManager` fast-polls (250 ms) off the CTRX PTT state, broadcasting meter JSON to `/WSATR1000` clients via the IOLoop thread only.

## Audio/PTT Guardrails
- TX/PTT timing is fragile; preserve the flow documented in `docs/legacy/audio/PTT_Audio_Postmortem_and_Best_Practices.md` and implemented in `www/tx_button_optimized.js`.
- `rx_worklet_processor.js` uses a **millisecond watermark** buffer (not legacy frame counts). Normal RX needs `prebufferMs` well above one frame; safe desktop config is `prebufferMs: 200, recoveryMs: 80, maxMs: 600`.
- TX-to-RX intentionally drops to a transient low-buffer window (`prebufferMs: 20`, ≈1 frame) in `tx_button_optimized.js`, then restores `prebufferMs: 200 / recoveryMs: 80 / maxMs: 600` after 200 ms; do not remove that timer.
- PTT release must clear all three queues: `client.Wavframes = []`, `PyAudioCapture._flush_opus_accumulator = True`, and JS `AudioWorklet.flush()` plus `AudioRX_audiobuffer = []`.
- `tune`, `cq`, and `toggleaudioRX()` stop/unmute paths must keep equivalent flush behavior because they can bypass the main `setPTT` cleanup path.
- `stream.read()` capture sizes should align to Opus frames; `audio_interface.py` reads 960 samples per call (20 ms at 48 kHz → exactly one 320-sample Opus frame after 3:1 decimation to 16 kHz).

## FT8/CW Removal (V5.7)
- FT8 and CW decoder features were removed entirely: `/WSFT8`, `WS_FT8Handler`, `ft8_integration.py` (JTDX/WSJT-X UDP bridge), `ft8_decoder.py`, the `www/ft8*`/`www/cw_*` pages, both `models/` + `www/models/` (cw_decoder.onnx), and the standalone `ft8/` ULTRON automation directory are all deleted. Radio-side CW *mode* (`setMode:CW`) is unaffected.
- The mobile quick row now hosts IC-M710 AGC/RF-gain controls wired to `/WSCTRX` `setAGC`/`setRFGain` (rigctld `L AGC`/`L RF` → icm710 NMEA `AGC ON/OFF`, `RFG 0-9`).

## Website
- Website source lives in `website/`; deploy with root `./deploy_website.sh [user@host] [remote_path]`.
- The executable deploy default is `cheenle@www.vlsc.net:/var/www/vlsc.net/mrrc`; `website/README.md` still mentions older `/var/www/html/mrrc` paths.
- `docs/legacy/tooling/CLAUDE.md` has the website nav/version/path gotchas; check it before changing many `website/*.html` pages.

## Existing Guidance
- `docs/legacy/methodology/aldv2/Aladdin_V2_Methodology.md` is the top-level engineering methodology; `.opencode/skills/aladdin-v2/SKILL.md` turns it into a repo-local OpenCode skill.
- `docs/legacy/tooling/CLAUDE.md` has broader architecture notes; prefer this file for compact OpenCode-specific gotchas.
- `docs/legacy/root/AOD.md`, `docs/legacy/root/DSP.md`, and `docs/legacy/operations/Multi_Instance_Setup.md` are useful when changing wiring, DSP, or multi-instance behavior.

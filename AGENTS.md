# AGENTS.md

## Start Here
- Main app entrypoint is the executable Python/Tornado script `MRRC`; it reads `MRRC.conf` by default or `python3 MRRC <config-file>` for another config.
- Active default server port is `8877` from `MRRC.conf` and `docker-compose.yml`; older docs/tools may still say `8888`.
- Root `/` serves `www/index.html`; `/mobile` serves `www/mobile_modern.html`; static assets are served from `www/`.
- Auth defaults to `FILE` in `MRRC.conf`, so browser requests can redirect to `/login` unless authenticated.

## Run And Verify
- Start directly for local debugging with `python3 ./MRRC` or `./MRRC` after installing system/audio/radio deps.
- `./mrrc_control.sh start` starts `rigctld`, MRRC, then `atr1000_proxy.py`; edit its hard-coded device/model values before trusting it on new hardware.
- `mrrc_control.sh` currently invokes `Python "$SCRIPT_DIR/MRRC"` in `start_mrrc`; if service start fails, try direct `python3 ./MRRC` before debugging the app.
- Docker single-instance command is `docker compose up --build` or `docker-compose up --build`; it maps host `8877:8877`, mounts `MRRC.conf`, `certs/`, `MRRC_users.db`, and `/dev`.
- Multi-instance workflow uses `./mrrc_multi.sh create <name>`, edit `MRRC.<name>.conf`, then `./mrrc_multi.sh start <name>`; each instance needs unique web port, rigctld port, and Unix socket.

## Tests And Diagnostics
- No root test runner or CI config is present; use focused dev tools instead of assuming pytest for the whole repo.
- Dependency smoke test: `python3 dev_tools/test_installation.py`; it checks Python 3.7+, imports, `MRRC.conf`, and legacy root cert names `UHRH.crt`/`UHRH.key`.
- Audio device/capture/playback checks: `python3 dev_tools/test_audio.py` and `python3 dev_tools/test_audio_capture.py`; these require usable local audio devices.
- `dev_tools/test_connection.py` targets `https://localhost:8888/`, which does not match the current default `8877`; adjust before using it.
- Hardware-facing checks may require PortAudio/PyAudio, Hamlib/rigctld, serial devices, RTL-SDR, TLS certs, or ATR-1000 network access.

## Architecture Notes
- Radio control goes through `rigctld`/Hamlib via `hamlib_wrapper.py`; audio I/O goes through PyAudio abstractions in `audio_interface.py`.
- WebSocket endpoints are defined near the bottom of `MRRC`: `/WSaudioRX`, `/WSaudioTX`, `/WSCTRX`, `/WSpanFFT`, `/WSATR1000`, `/WSATU`, and `/WSFT8`.
- `www/controls.js` owns shared browser control/audio behavior; `www/mobile_modern.js` depends on `controls.js` and should not redeclare its globals.
- Mobile HTML contains hidden desktop-compatible elements required by `controls.js`; do not remove them as dead markup without checking runtime dependencies.
- TX/PTT timing is fragile; preserve the flow documented in `docs/PTT_Audio_Postmortem_and_Best_Practices.md` and implemented in `www/tx_button_optimized.js`.
- RX playback was rewritten in V5.2 around scheduled `BufferSourceNode`s in `www/audio_rx.js`; avoid reintroducing gap-prone single-source playback.
- WDSP integration is in `wdsp_wrapper.py` plus `DSP/wdsp/`; macOS builds produce `libwdsp.dylib`, Linux builds produce `libwdsp.so`.
- ATR-1000 integration uses `atr1000_proxy.py` with a Unix socket defaulting to `/tmp/atr1000_proxy.sock`; multi-instance configs override this via `[INSTANCE_SETTINGS]`.

## Subprojects
- `ft8/` is ULTRON/FT8 automation, separate from the MRRC web server; see `ft8/CLAUDE.md` before changing it.
- `ft8/` Python scripts are mostly standard-library based (`python run_ultron.py`, `python ultron.py`, `python ultron_dxcc.py`); PHP variants use `php -c extra/php-lnx.ini ...`.
- `ft8/rdma/` is a packaged Python subproject with its own `pyproject.toml`, pytest/black/isort/flake8/mypy settings, and `src/` layout.

## FT8 Critical Gotchas (V5.3)
- **Big-endian protocol**: JTDX/WSJT-X UDP uses **big endian** (default Qt 5+ QDataStream byte order). All header fields (magic, schema, type) and body fields (string lengths, uint64, double, int32) use `>` format. String encoding is QByteArray: `[uint32 BE length][UTF-8 data]`, with `0xFFFFFFFF` for null.
- **Status field layout** (type 1): Id → DialFreq(quint64) → Mode → DXCall → Report → TxMode → TxEnabled(bool) → Transmitting(bool) → Decoding(bool) → RxDF(qint32) → TxDF(qint32) → DECall → DEGrid → DXGrid → TxWatchdog(bool) → SubMode → FastMode(bool) → TxFirst(bool). No dialog_name field between Id and freq.
- **Decode field layout** (type 2): Id → New(bool) → Time(quint32) → snr(qint32) → DeltaTime(double, 8B) → DeltaFreq(quint32) → Mode → Message → LowConfidence(bool) → OffAir(bool).
- **Port 2238 not 2237**: `ft8_integration.py` listens on **2238** to avoid conflicting with JTDX/WSJT-X (which owns 2237). User must configure JTDX's UDP secondary port to `127.0.0.1:2238`.
- **TX via Free Text**: CQ/Reply/RR73 commands send WSJT-X Free Text (type 9) packets to JTDX on port 2237. No audio path needed — JTDX generates the TX audio.
- **`ft8_decoder.py` is non-functional** — requires `PyFT8` library (not installed), returns empty decodes. All decode/status comes from JTDX/WSJT-X UDP forward.
- **Frontend dual paths**: `ft8_ultron.html` + `ft8_ultron.js` is the active UI (rewritten V5.3). `ft8.html` + `ft8.js` is legacy (waterfall, simulated TX).
- **PHP files in `ft8/`** (robot.php etc.) are legacy; all active development is Python.

## Audio Buffer Critical Patterns (V5.3.1)
- **`rx_worklet_processor.js` minimum buffer MUST NOT stay at 1**. When `targetMinFrames=1`, line 78 guard `this.targetMinFrames > 1` is always false → zero jitter protection → every transient network delay produces an audible gap. Safe default: `min: 2, max: 30`.
- **TX→RX uses a transient min:1 window**: After TX ends, `tx_button_optimized.js` sets `min: 1` for fast audio recovery, then a 200ms `setTimeout` restores `min: 2, max: 30`. Never remove that timer.
- **Three flush targets on PTT release**: (a) `client.Wavframes = []` — clear already-encoded frames; (b) `PyAudioCapture._flush_opus_accumulator = True` — clear raw PCM accumulator in capture thread; (c) JS-side `AudioWorklet.flush()` + `AudioRX_audiobuffer = []`. Missing any one causes stale frames to play after TX→RX switch.
- **`tune` and `cq` stop paths MUST duplicate the PTT-release flush logic** — they call `CTRX.setPTT("false")` directly, bypassing the `setPTT` handler that does cleanup.
- **`stream.read()` size should align to Opus frame boundaries**: 320 samples = 20ms @ 16kHz (one Opus frame). Avoid sizes that produce fractional frames per read (e.g. 480 = 1.5 frames).
- **`toggleaudioRX()` re-enables audio after mute** — it must flush buffers the same way TX stop does, or manual mute/unmute will replay stale frames.

## Existing Guidance
- `CLAUDE.md` has broader architecture notes; prefer this file for compact OpenCode-specific gotchas.
- `AOD.md`, `DSP.md`, and `docs/Multi_Instance_Setup.md` are useful when changing wiring, DSP, or multi-instance behavior.

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
- `mrrc_multi.sh` hardcodes `/opt/local/bin/python3.12` for MRRC startup; change or bypass it on systems without MacPorts Python there.

## Tests And Diagnostics
- No root manifest, root test runner, pre-commit config, or CI workflow is present; use focused dev tools instead of assuming pytest/npm for the whole repo.
- Dependency smoke test: `python3 dev_tools/test_installation.py`; it checks Python 3.7+, imports, `MRRC.conf`, and legacy root cert names `UHRH.crt`/`UHRH.key`.
- Audio device/capture/playback checks: `python3 dev_tools/test_audio.py` and `python3 dev_tools/test_audio_capture.py`; these require usable local audio devices.
- `dev_tools/test_connection.py` targets `https://localhost:8888/`, which does not match the current default `8877`; adjust before using it.
- Hardware-facing checks may require PortAudio/PyAudio, Hamlib/rigctld, serial devices, RTL-SDR, TLS certs, or ATR-1000 network access.
- `ft8/rdma/` is the only packaged Python subproject; run its focused checks from that directory, e.g. `pytest tests/test_ham_radio.py`, with its dev deps installed.

## Architecture Notes
- Radio control goes through `rigctld`/Hamlib via `hamlib_wrapper.py`; audio I/O goes through PyAudio abstractions in `audio_interface.py`.
- WebSocket endpoints are defined near the bottom of `MRRC`: `/WSaudioRX`, `/WSaudioTX`, `/WSCTRX`, `/WSpanFFT`, `/WSATR1000`, `/WSATU`, and `/WSFT8`.
- `www/controls.js` owns shared browser control/audio behavior; `www/mobile_modern.js` depends on `controls.js` and should not redeclare its globals.
- Mobile HTML contains hidden desktop-compatible elements required by `controls.js`; do not remove them as dead markup without checking runtime dependencies.
- RX playback was rewritten in V5.2 around scheduled `BufferSourceNode`s in `www/audio_rx.js`; avoid reintroducing gap-prone single-source playback.
- WDSP integration is in `wdsp_wrapper.py` plus `DSP/wdsp/`; macOS builds produce `libwdsp.dylib`, Linux builds produce `libwdsp.so`.
- ATR-1000 integration uses `atr1000_proxy.py` with a Unix socket defaulting to `/tmp/atr1000_proxy.sock`; multi-instance configs override this via `[INSTANCE_SETTINGS]`.

## Audio/PTT Guardrails
- TX/PTT timing is fragile; preserve the flow documented in `docs/legacy/audio/PTT_Audio_Postmortem_and_Best_Practices.md` and implemented in `www/tx_button_optimized.js`.
- `rx_worklet_processor.js` default minimum buffer must stay above 1 for normal RX. Safe desktop config is `min: 2, max: 30`.
- TX-to-RX intentionally uses a transient `min: 1` window in `tx_button_optimized.js`, then restores `min: 2, max: 30` after 200 ms; do not remove that timer.
- PTT release must clear all three queues: `client.Wavframes = []`, `PyAudioCapture._flush_opus_accumulator = True`, and JS `AudioWorklet.flush()` plus `AudioRX_audiobuffer = []`.
- `tune`, `cq`, and `toggleaudioRX()` stop/unmute paths must keep equivalent flush behavior because they can bypass the main `setPTT` cleanup path.
- `stream.read()` capture sizes should align to Opus frames; `audio_interface.py` uses 320 samples for 20 ms at 16 kHz.

## FT8 Critical Gotchas (V5.3)
- JTDX/WSJT-X UDP packets are big-endian Qt QDataStream style; `ft8_integration.py` uses `struct` format `>` and QByteArray strings as `[uint32 BE length][UTF-8 data]`, with `0xFFFFFFFF` for null.
- Status packet layout is `Id, DialFreq, Mode, DXCall, Report, TxMode, TxEnabled, Transmitting, Decoding, RxDF, TxDF, DECall, DEGrid, DXGrid, TxWatchdog, SubMode, FastMode, TxFirst`; there is no `dialog_name` between Id and frequency.
- Decode packet layout is `Id, New, Time, snr, DeltaTime, DeltaFreq, Mode, Message, LowConfidence, OffAir`.
- `ft8_integration.py` listens on UDP `2238` to avoid JTDX/WSJT-X owning `2237`; configure JTDX's UDP secondary port to `127.0.0.1:2238`.
- CQ/Reply/RR73 send WSJT-X Reply or Free Text packets back to JTDX on `2237`; JTDX generates TX audio, not MRRC audio streaming.
- Root `ft8_decoder.py` is not the active decode path: it depends on `PyFT8` and `decode_cycle()` currently returns `[]`. Decode/status data comes from the JTDX/WSJT-X UDP bridge.
- `www/ft8_ultron.html` plus `www/ft8_ultron.js` is the active FT8 UI linked from mobile; `www/ft8.html` plus `www/ft8.js` is legacy.
- `ft8/` is ULTRON automation, separate from the MRRC web server; Python scripts are mostly stdlib (`python run_ultron.py`, `python ultron.py`, `python ultron_dxcc.py`), while PHP legacy variants use `php -c extra/php-lnx.ini ...`.

## Website
- Website source lives in `website/`; deploy with root `./deploy_website.sh [user@host] [remote_path]`.
- The executable deploy default is `cheenle@www.vlsc.net:/var/www/vlsc.net/mrrc`; `website/README.md` still mentions older `/var/www/html/mrrc` paths.
- `docs/legacy/tooling/CLAUDE.md` has the website nav/version/path gotchas; check it before changing many `website/*.html` pages.

## Existing Guidance
- `docs/legacy/methodology/aldv2/Aladdin_V2_Methodology.md` is the top-level engineering methodology; `.opencode/skills/aladdin-v2/SKILL.md` turns it into a repo-local OpenCode skill.
- `docs/legacy/tooling/CLAUDE.md` has broader architecture notes; prefer this file for compact OpenCode-specific gotchas.
- `docs/legacy/root/AOD.md`, `docs/legacy/root/DSP.md`, and `docs/legacy/operations/Multi_Instance_Setup.md` are useful when changing wiring, DSP, or multi-instance behavior.

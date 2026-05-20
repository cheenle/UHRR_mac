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

## Existing Guidance
- `CLAUDE.md` has broader architecture notes; prefer this file for compact OpenCode-specific gotchas.
- `AOD.md`, `DSP.md`, and `docs/Multi_Instance_Setup.md` are useful when changing wiring, DSP, or multi-instance behavior.

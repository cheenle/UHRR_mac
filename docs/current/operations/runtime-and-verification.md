# Runtime And Verification

## Run Locally

Default direct startup:

```bash
python3 ./MRRC
```

Alternative:

```bash
./MRRC
```

With a custom config:

```bash
python3 ./MRRC MRRC.radio1.conf
```

Important: `/CONFIG` writes `MRRC.conf` and restarts `./MRRC`, so it is not safe to assume custom config paths are preserved through the web config UI.

## Default Access

| Surface | URL |
| --- | --- |
| Desktop | `https://localhost:8877/` |
| Mobile route | `https://localhost:8877/mobile` |
| Mobile static file | `https://localhost:8877/mobile_modern.html` |
| Recordings | `https://localhost:8877/recordings.html` |
| FT8 | `https://localhost:8877/ft8_ultron.html` |
| Config | `https://localhost:8877/CONFIG` |

Auth is enabled by default through `FILE`, so unauthenticated browser requests may redirect to `/login`.

## Required Runtime Dependencies

Core Python imports:

- `tornado`
- `numpy`
- `pyaudio`
- `opuslib` or local Opus path used by the project
- `configparser`
- `rtlsdr` for panadapter support

Hardware/system dependencies vary by feature:

- PortAudio/PyAudio for audio I/O.
- Hamlib/`rigctld` for radio control.
- serial device access for CAT control.
- RTL-SDR for panadapter.
- `libwdsp` for WDSP DSP.
- ATR-1000 network access and `atr1000_proxy.py` for tuner integration.
- JTDX/WSJT-X configured with UDP secondary port `127.0.0.1:2238` for FT8.

## Verification Commands

Dependency smoke test:

```bash
PYTHONPATH=. python3 dev_tools/test_installation.py
```

Notes:

- Running `python3 dev_tools/test_installation.py` without `PYTHONPATH=.` can fail root-module imports because the script starts with `dev_tools/` on `sys.path`.
- The test still checks legacy root certificate names `UHRH.crt` and `UHRH.key`; the current default config uses `certs/radio.vlsc.net.pem` and `certs/radio.vlsc.net.key`.

Syntax check for the main Python entrypoints:

```bash
python3 -m py_compile MRRC hamlib_wrapper.py audio_interface.py ft8_integration.py atr1000_api_server.py
```

SSL certificate inspection:

```bash
openssl x509 -in certs/radio.vlsc.net.pem -noout -subject -issuer -dates
```

## Docker

Single-instance Docker:

```bash
docker compose up --build
```

or:

```bash
docker-compose up --build
```

Current `docker-compose.yml` maps host `8877:8877` and mounts:

- `MRRC.conf`
- `certs/`
- `atr1000_tuner.json`
- `MRRC_users.db`
- `logs/`
- `/dev`

If a backend module becomes required inside containers, add it explicitly to `Dockerfile`; the Dockerfile copies selected runtime files plus `www/`, not the whole repository.

## Known Verification Caveats

| Area | Caveat |
| --- | --- |
| `dev_tools/test_connection.py` | Uses `https://localhost:8888/`, but current default is `8877` |
| `dev_tools/test_ssl_server.py` | Uses legacy root `UHRH.crt` and `UHRH.key` |
| `mrrc_control.sh` | `start_mrrc` currently invokes `Python "$SCRIPT_DIR/MRRC"`; direct `python3 ./MRRC` is the safer baseline |
| `ft8/.gitignore` | Contains malformed glob `.env.production"}` that makes `rg` report an ignore parsing error |
| hardware tests | May require audio devices, rigctld, serial access, SDR, ATR-1000, or TLS certs |

## Do Not Treat As Safe To Delete

These may look peripheral but are used by active routes or linked entrypoints:

- `www/ft8_ultron.html`
- `www/ft8_ultron.js`
- `ft8_integration.py`
- `ft8/base.json`
- `www/cw_live.html`
- `www/recordings.html`
- `atr1000_proxy.py`
- `atr1000_tuner.py`
- `atr1000_api_server.py`
- `memory_channels.json`
- `MRRC_users.db`
- `recordings/`
- `certs/`

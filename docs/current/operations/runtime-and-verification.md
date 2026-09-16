# Runtime And Verification

> 在生命周期中的位置：**验证方法库**（发版复核、升级验证、诊断判读）—— 见《[产品支持生命周期](product-support-lifecycle.md)》。

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
| Config | `https://localhost:8877/CONFIG` |

Auth is enabled by default through `FILE`, so unauthenticated browser requests may redirect to `/login`.

## Required Runtime Dependencies

Core Python imports:

- `tornado`
- `numpy`
- `pyaudio`
- `opuslib` or local Opus path used by the project
- `configparser`

Hardware/system dependencies vary by feature:

- PortAudio/PyAudio for audio I/O.
- Hamlib/`rigctld` for radio control.
- serial device access for CAT control.
- `libwdsp` for WDSP DSP.
- ATR-1000 network access and `atr1000_proxy.py` for tuner integration.

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
python3 -m py_compile MRRC hamlib_wrapper.py audio_interface.py atr1000_proxy.py atr1000_api_server.py
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
| hardware tests | May require audio devices, rigctld, serial access, SDR, ATR-1000, or TLS certs |

## Do Not Treat As Safe To Delete

These may look peripheral but are used by active routes or linked entrypoints:

- `www/recordings.html`
- `atr1000_proxy.py`
- `atr1000_tuner.py`
- `atr1000_api_server.py`
- `memory_channels.json`
- `MRRC_users.db`
- `recordings/`
- `certs/`

---

## 一键升级 / 热修清单的验证方法（Windows 安装版）

**前提**：`version.txt` 是唯一权威版本；所有升级状态在 `%LOCALAPPDATA%\MRRC\updates\`。

### 现状快照（一条命令）

```powershell
$p = "$env:LOCALAPPDATA\MRRC\updates"
"version.txt = " + (Get-Content 'C:\Program Files\MRRC\version.txt')
Get-Content "$p\state.json" -Raw -Encoding UTF8          # staged + lastResult
Get-ChildItem $p | Select-Object Name,Length,LastWriteTime
Get-ChildItem "$env:LOCALAPPDATA\MRRC\patch" -Recurse   # 热修覆盖层是否已应用
```

### 判定表

| 想确认什么 | 看哪里 | 正常表现 |
|---|---|---|
| 服务端升级接口是否正常 | 本机 `GET https://127.0.0.1:8877/api/update` | `{"ok": true, "installed": "6.1.x", "latest": "6.1.y", "pttActive": false}`（本机免口令） |
| 是否已下载好安装包 | `updates\state.json` 的 `staged` | `{version, sha256, path, size, at}`，且文件存在、大小一致 |
| 升级请求有没有被处理 | `updates\upgrade.request` 是否存在 | **正常会被立刻消费掉**；长期存在 = 启动器没在处理（见 RC-002 §6） |
| 下载是否在推进 | `updates\*.part<pid>` 的字节数 | 持续增长；**长期 0 字节 = 连接阶段卡住** |
| 安装是否真的跑了 | `updates\install-<ver>.log` | Inno 日志；结尾应有 `Installation process succeeded` / `Run entry` / `Deinitializing Setup` |
| 成败结论 | `updates\state.json` 的 `lastResult` | `{"status": "ok", "version": "6.1.y", "detail": "安装后启动确认成功"}` 才算成功 |
| 热修是否生效 | `%LOCALAPPDATA%\MRRC\patch\applied.json` + `patch\app\*.py` | 版本号与 `patch.json` 的 `latest` 一致，且文件内容含新代码 |

### 线上清单复核（维护者/排障）

```bash
curl -s https://www.vlsc.net/mrrc/downloads/latest.json | python3 -m json.tool
curl -s https://www.vlsc.net/mrrc/downloads/patch.json  | python3 -m json.tool
# 服务器侧哈希（权威；本机下载链路可能很慢）
ssh cheenle@www.vlsc.net 'cd /var/www/vlsc.net/mrrc/downloads && sha256sum MRRC-Setup*.exe'
```

### 真机端到端（可离线）

`dev_tools/vm_upgrade_e2e.ps1` + `MRRC_UPDATE_MANIFEST=file:///…/test-latest.json`
可完全不依赖站点网络地跑通"下载→校验→安装→重启→自证"。
详见 `docs/current/operations/release-process.md` §6。

### 用户报障时向用户要什么

启动器窗口里的 `[update]` 行 + `updates\state.json` + `updates\install-<ver>.log`；
最省事的办法是让用户点页面 **🐞 遇到问题 → 生成并上传**（会一并带走上述文件与服务端日志）。

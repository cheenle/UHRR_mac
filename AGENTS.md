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
- Windows installer build chain mirrors `../mrrc_modern`: run `packaging/windows/build.ps1` on a Windows build machine after placing the required native DLLs under `vendor/{opus,hamlib,wdsp}/windows/bin/x64/`. See `win_pack.md` for the full workflow.

## Tests And Diagnostics
- No root manifest, root test runner, pre-commit config, or CI workflow is present; use focused dev tools instead of assuming pytest/npm for the whole repo.
- Dependency smoke test: `python3 dev_tools/test_installation.py`; it checks Python 3.7+, imports, `MRRC.conf`, and legacy root cert names `UHRH.crt`/`UHRH.key`.
- Audio device/capture/playback checks: `python3 dev_tools/test_audio.py` and `python3 dev_tools/test_audio_capture.py`; these require usable local audio devices.
- `dev_tools/test_connection.py` targets `https://localhost:8888/`, which does not match the current default `8877`; adjust before using it.
- Hardware-facing checks may require PortAudio/PyAudio, Hamlib/rigctld, serial devices, RTL-SDR, TLS certs, or ATR-1000 network access.
- `mrrc_multi.sh` rotates logs on start: the previous instance's tail survives as `<log>.prev` — the first place to look after a crash/restart.
- Runtime log markers (F4/F4b, V6.0.2): `IOLoop watchdog armed` at startup; `⏱️ TX audio init: 枚举 Xs, p.open Xs` on every PTT (healthy <0.2s each); `📦 TX init took ... flushing N buffered frames` when F4b buffering engaged; `🚨 IOLoop stall` + full thread dump if the event loop wedges. TX modulation is verified fastest via ATR-1000 power readings (swinging 100W+ = modulated, flat ~7W carrier = silent TX).
- Bluetooth audio devices as macOS default output churn A2DP (`bluetoothd` `Jitter Buffer ... error 312`) and stall CoreAudio globally, slowing MRRC `p.open()`; see `docs/current/reliability/RC-001-ioloop-wedge-and-tx-silence.md` §7 for probes.

## Architecture Notes
- 电台型号有两套键、必须同步：UI/配置里的 `[HAMLIB] rig_model`（hamlib 规范名，如 `IC-M710`）与 rigctld 实际读取的 `[INSTANCE_SETTINGS] instance_rigctl_model`（数字，如 30003）。Device Config 保存时由 `rig_models.apply_to_config()` 两处一起写；机型表由 `rig_models.py` 从本机 hamlib 实时枚举（312 个），不要再硬编码型号列表。
- 「🐞 遇到问题」一键诊断包：生成/脱敏在 `support_bundle.py`（纯标准库、松散模块，可热修），服务端接口在 `MRRC` 的 `SupportApiHandler`（`/api/support/*`，IO 全走 executor），页面 `www/support.html`；接收端 `tools/support_receiver/server.py` 部署在 www.vlsc.net（`./deploy_support_receiver.sh`），维护者列表页与口令见 `docs/current/operations/support-bundle.md`。
- Radio control goes through `rigctld`/Hamlib via `hamlib_wrapper.py`; audio I/O goes through PyAudio abstractions in `audio_interface.py`.
- WebSocket endpoints are defined near the bottom of `MRRC`: `/WSaudioRX`, `/WSaudioTX`, `/WSCTRX`, `/WSpanFFT`, `/WSATR1000`, and `/WSATU`.
- `www/controls.js` owns shared browser control/audio behavior; `www/mobile_modern.js` depends on `controls.js` and should not redeclare its globals.
- Mobile HTML contains hidden desktop-compatible elements required by `controls.js`; do not remove them as dead markup without checking runtime dependencies.
- The active RX engine lives in `www/controls.js` with the `rx_worklet_processor.js` watermark buffer; `www/audio_rx.js` (V5.2 `BufferSourceNode` scheduler) is deprecated legacy and incompatible with the tagged wire format — no page should load it.
- TX capture runs on `tx_worklet_processor.js` (`tx-capture` AudioWorklet, 960-sample/20 ms frames posted to `OpusEncoderProcessor.pushSamples`); `MediaHandler._setupScriptProcessor` is the iOS/legacy fallback — both paths must stay functional.
- WDSP integration is in `wdsp_wrapper.py` plus `DSP/wdsp/`; macOS builds produce `libwdsp.dylib`, Linux builds produce `libwdsp.so`.
- 一键升级（Windows 安装版）：纯逻辑在 `upgrade_core.py`（清单/版本决策/原子下载校验/state.json+upgrade.request），启动器负责 `ShellExecuteW runas` 静默安装；服务端 `/api/update*`（仅本机免口令）；发布用 `dev_tools/make_latest_json.py`；开关 `[UPDATE] enabled/autoDownload`、`MRRC_NO_UPDATE_CHECK=1`。文档：`docs/current/operations/one-click-upgrade.md`。
- ATR-1000 是**可选**组件：`[ATR1000] enabled = auto|true|false`（auto = 配了 `instance_atr1000_device` 才启用；`MRRC_ATR1000=0/1` 可覆盖）。关闭时 `ATR1000_ENABLED=False` → 不启动代理管理器、不轮询、`/WSATR1000` 只回一条 `atr1000_status{enabled:false}` 让前端隐藏面板；代理连接失败/重连日志走 `_log_throttled()`（默认 5 分钟一条），别再直接 `logger.warning` 刷屏。
- ATR-1000 integration uses `atr1000_proxy.py` with a Unix socket defaulting to `/tmp/atr1000_proxy.sock`; multi-instance configs override this via `[INSTANCE_SETTINGS]`. The proxy answers from cache only (request/response); TX `stop` zeroes the cached power/SWR so RX never shows ghost readings, and `MRRC`'s `ATR1000ProxyManager` fast-polls (250 ms) off the CTRX PTT state, broadcasting meter JSON to `/WSATR1000` clients via the IOLoop thread only.
- **IOLoop thread-safety (V5.8.2)**: `tornado.ioloop.IOLoop.instance()` is a thread-dependent alias of `IOLoop.current()` in tornado 6.5. Background threads (ATR-1000 reconnect `Timer`, rigctld executor via `run_in_executor`, `PTTSafetyMonitor`) MUST use the main-thread-pinned global `MAIN_IOLOOP` (defined at module top) for `add_callback`/`add_timeout`, never `IOLoop.instance()` — calling it from a worker thread creates a separate asyncio loop whose queued callbacks never run (ATR meter/PTT broadcasts silently die, frontend shows only the initial snapshot).
- **TX init is async (F4/F4b, V6.0.2)**: `WS_AudioTXHandler` `m:` → `_start_tx_init_async` runs `TX_init` (incl. blocking `p.open()`) on a `run_in_executor` worker — never call `TX_init` synchronously from `on_message`. Frames arriving during init buffer into `_tx_pending_frames` (250-frame cap) and flush on completion; `s:`/`on_close` set `_tx_init_cancel` and clear the buffer; the discard path force-releases PTT. `audio_interface.py` caches the output-device index (`_output_device_index_cache`, validated by name on each hit). A heartbeat watchdog (`arm_ioloop_watchdog`, 2s/8s) dumps all thread stacks if the IOLoop wedges. Full story: `docs/current/reliability/RC-001-ioloop-wedge-and-tx-silence.md`.

## Windows Installer / One-Click Upgrade
- 安装版本唯一权威 = 安装目录 `version.txt`；升级逻辑在 `windows/launcher.py` + `upgrade_core.py`，
  运行时状态在 `%LOCALAPPDATA%\MRRC\updates\`（`state.json` / `upgrade.request` / `MRRC-Setup-<ver>.exe` / `install-<ver>.log`）。
- **唯一成功判据**：`state.json` 的 `lastResult.status == "ok"`（由新版启动时 `confirm_pending_upgrade()` 自证）。
- V6.0.10 及更早**没有**升级逻辑（需手动装一次 6.1.x）；发布时 `latest.json` 的 `previous` 必须在站点上真实存在
  —— 站点部署是 `rsync --delete`，**没进 git 的服务器文件会被清掉**。
- 热修通道只覆盖 `www/**`、`_APP_MODULES`（含 `upgrade_core.py`）与 `vendor`；
  `MRRC` 主脚本与 `windows/launcher.py` 在 PYZ 里，改动必须重发安装包。
- 发版流程见 `docs/current/operations/release-process.md`；升级排障见 `docs/current/operations/one-click-upgrade.md`；
  根因与 Windows 陷阱见 `docs/current/reliability/RC-002-launcher-upgrade-and-shutdown.md`。
- **VM 自动化实测陷阱**：SSH 会话结束会回收 `Start-Process` 的子进程（长任务用
  `schtasks /create … /RL HIGHEST /RU <user> /IT` 再 `/run`）；含中文的 `.ps1` 必须 **UTF-8 单 BOM**；
  `Tee-Object` 没有 `-Encoding`；`schtasks /tr` 里**别塞引号**；服务器 `/tmp` 是 454 MB tmpfs
  （大文件传 `~` 再 `sudo mv`）；VM 网络对 45 MB 下载不稳（验收可用 `MRRC_UPDATE_MANIFEST=file://…` 离线跑）。

## 支持自动化（support autopilot）
- 端到端闭环：**轮询接收端 → 取诊断包 → 调用 `pi` 分析 → 生成答复卡 → 发布公开答复页**，实现于
  `dev_tools/support_autopilot.py`；配套 skill `.pi/skills/mrrc-support-triage/SKILL.md`（判定规则/答复格式）。
- 命令：`--once [--publish]`、`--id <编号> [--force] [--publish]`、`--inspect <编号>`、`--status`、
  `--install-cron 10`（macOS crontab）；默认**不发布**（只出草稿到 `dist/support_answers/`）。
- 状态/日志：`~/.mrrc-support-autopilot/{state.json,autopilot.log}`；已处理 id 幂等跳过，半包（非 zip）标记 skip。
- 答复页：<https://www.vlsc.net/mrrc/answers/>（`website/answers/index.html`，可搜索、`#编号` 直达）。
- 约定：答复页是**公开**页面——只放可公开结论，不放用户数据；每条答复必须含"你要做的"可执行步骤；
  保守判定（材料不足 → `need_more_info`）；环境类问题（无声卡/无 rigctld/虚拟机）不判成产品缺陷。

## Audio/PTT Guardrails
- TX/PTT timing is fragile; preserve the flow documented in `docs/legacy/audio/PTT_Audio_Postmortem_and_Best_Practices.md` and implemented in `www/tx_button_optimized.js`.
- `rx_worklet_processor.js` uses a **millisecond watermark** buffer (not legacy frame counts). Normal RX needs `prebufferMs` well above one frame; safe desktop config is `prebufferMs: 200, recoveryMs: 80, maxMs: 600`.
- TX-to-RX intentionally drops to a transient low-buffer window (`prebufferMs: 20`, ≈1 frame) in `tx_button_optimized.js`, then restores `prebufferMs: 200 / recoveryMs: 80 / maxMs: 600` after 200 ms; do not remove that timer.
- PTT release must clear all three queues: `client.Wavframes = []`, `PyAudioCapture._flush_opus_accumulator = True`, and JS `AudioWorklet.flush()` plus `AudioRX_audiobuffer = []`.
- F4b added a fourth queue to that release contract: `WS_AudioTXHandler._tx_pending_frames` must be cleared on `s:`/`on_close`, and any discard path must force-release PTT (`setPTT("false")`) to cover the init race — see RC-001 §5 for why.
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
- `docs/current/reliability/` indexes the reliability/safety case series (RC-001: IOLoop wedge + BT-DAC-churn silent TX); consult it before touching TX init, the IOLoop, or macOS audio device handling.
- `docs/current/methodology/project-retrospective-2026-09.md` is the full project history retrospective (phases, problem taxonomy, validated methods, future outlook) — read it when planning larger direction changes.
- `docs/legacy/methodology/aldv2/Aladdin_V2_Methodology.md` is the top-level engineering methodology; `.opencode/skills/aladdin-v2/SKILL.md` turns it into a repo-local OpenCode skill.
- `docs/legacy/tooling/CLAUDE.md` has broader architecture notes; prefer this file for compact OpenCode-specific gotchas.
- `docs/legacy/root/AOD.md`, `docs/legacy/root/DSP.md`, and `docs/legacy/operations/Multi_Instance_Setup.md` are useful when changing wiring, DSP, or multi-instance behavior.

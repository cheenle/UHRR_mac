# Capability Map

This map lists capabilities that are implemented in the current codebase and identifies their runtime surface.

## Primary Capabilities

| Capability | Status | Main Files | Runtime Surface |
| --- | --- | --- | --- |
| Desktop radio control | Implemented | `MRRC`, `www/index.html`, `www/controls.js` | `/`, `/WSCTRX`, `/WSaudioRX`, `/WSaudioTX` |
| Mobile radio control | Implemented | `MRRC`, `www/mobile_modern.html`, `www/mobile_modern.js`, `www/controls.js` | `/mobile`, static `/mobile_modern.html`, same WebSockets |
| Authentication | Implemented | `MRRC`, `MRRC.conf`, `MRRC_users.db` | `FILE` auth by default; redirects to `/login` |
| Frequency/mode/PTT | Implemented | `TRXRIG` in `MRRC`, `hamlib_wrapper.py` | `WSCTRX` commands: `setFreq`, `getFreq`, `setMode`, `getMode`, `setPTT`, `getPTT` |
| Rig AGC/RF gain (IC-M710) | Implemented | `TRXRIG` in `MRRC` → rigctld `L AGC`/`L RF` → icm710 NMEA | `WSCTRX` commands: `setAGC`, `getAGC`, `setRFGain`, `getRFGain` (RF gain 9 steps) |
| TX/RX audio | Implemented | `audio_interface.py`, `www/controls.js`, `www/modules/opus_*` | `/WSaudioRX`, `/WSaudioTX` |
| PTT safety and release recovery | Implemented | `www/modules/ptt_manager.js`, `www/tx_button_optimized.js`, `MRRC`, `audio_interface.py` | release ACK retry, queue flush, Opus accumulator flush, server TOT monitor |
| WDSP DSP controls | Implemented when library exists | `audio_interface.py`, `wdsp_wrapper.py`, `www/mobile_modern.js`, `www/controls.js` | `WSCTRX` `setWDSP*` commands |
| Panadapter FFT | Optional | `MRRC`, `www/panadapter/` | `/WSpanFFT`, `/panfft.html`; depends on RTL-SDR |
| ATR-1000 meter/tuner bridge | Implemented, separate proxy required | `MRRC`, `atr1000_proxy.py`, `atr1000_tuner.py`, `www/mobile_modern.js` | `/WSATR1000`, Unix Socket proxy |
| ATR-1000 REST API | Optional separate process | `atr1000_api_server.py`, `atr1000_tuner.py` | default `127.0.0.1:8080`; talks to proxy socket |
| Tune and CQ | Implemented | `MRRC`, `www/modules/tune_cq.js`, `www/tx_button_optimized.js` | `WSCTRX` actions `tune`, `cq`, `cq_complete` |
| Channel memory | Implemented | `MRRC`, `memory_channels.json`, `www/mobile_modern.js` | `/api/mem_channels` |
| Recording | Implemented | `audio_interface.py`, `MRRC`, `www/mobile_modern.js`, `www/recordings.html` | `WSCTRX` `startRecording/stopRecording`, `/api/recordings`, `/recordings/<file>` |
| Multi-instance operation | Implemented in scripts/config convention | `mrrc_multi.sh`, `MRRC.radio*.conf`, `MRRC` | separate web/rigctld ports and Unix sockets |
| Docker single instance | Implemented | `Dockerfile`, `docker-compose.yml` | maps host `8877:8877`, mounts config/certs/data |
| One-click upgrade (Windows installer) | Implemented from V6.1.0 | `windows/launcher.py`, `upgrade_core.py`, `MRRC` (`UpdateApiHandler`), `www/update.html` | 页面菜单「⬆️ 软件更新」/ 桌面 ⬆️；启动器窗口按 `U`；`/api/update*`；清单 `downloads/latest.json` |
| Hotfix overlay (no-reinstall patching) | Implemented from V6.0.3 | `patch_overlay.py`, `windows/launcher.py`, `packaging/hotfix/` | `%LOCALAPPDATA%\MRRC\patch\{app,www,vendor}`；清单 `downloads/patch.json` |
| Support bundle (one-click diagnostics upload) | Implemented from V6.0.10 | `support_bundle.py`, `MRRC` (`SupportApiHandler`), `www/support.html`, `tools/support_receiver/server.py` | 页面/移动端「🐞 遇到问题」；`/api/support/{bundle,upload,save}`；接收端 `https://www.vlsc.net/mrrc/support/` |
| Rig model catalog (hamlib-aligned) | Implemented from V6.0.4 | `rig_models.py`, `MRRC` (`/api/devices`), `www/index.html` | 机型下拉（312 个，实时枚举本机 hamlib）+ `[HAMLIB] rig_model` 与 `[INSTANCE_SETTINGS] instance_rigctl_model` 双写 |
| Product support lifecycle (release → upgrade → diagnose → AI triage → answer) | Implemented from V6.1.12 | `dev_tools/release_windows.sh`, `windows/launcher.py` + `upgrade_core.py`, `support_bundle.py`, `dev_tools/support_autopilot.py`, `.pi/skills/mrrc-product-support/SKILL.md`, `website/answers/` | 站点清单 `latest.json`/`patch.json`；用户侧「⬆️ 软件更新」「🐞 遇到问题」；维护者侧 crontab 自动分诊 → 公开答复页 `/answers/` |
| Audio device diagnostics | Implemented | `audio_interface.py`, `MRRC` | `[AUDIO] diag`/`MRRC_AUDIO_DIAG`、`device_report()`、30s 音频健康行、`_match_devices` 主机 API 优先级 |

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

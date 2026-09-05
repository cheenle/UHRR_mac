# Mobile Remote Radio Control (MRRC) V6.0.0

[![English](https://img.shields.io/badge/lang-English-blue.svg)](README_en.md)
[![中文](https://img.shields.io/badge/lang-中文-red.svg)](README_CN.md)
[![Version](https://img.shields.io/badge/version-V6.0.0-green.svg)](CHANGELOG.md)

---

**Amateur Radio, Anytime, Anywhere.**

**随时随地，畅享业余无线电。**

A modern web-based remote control system optimized for mobile devices, enabling flexible operation of your amateur radio station from anywhere.

基于现代Web技术的远程电台控制系统，专为移动端优化，让您随时随地灵活操控业余电台。

> 🎉 **V6.0.0 更新**: Windows 安装包正式发布 — 首启自动生成本机登录账号与
> `MRRC Quick Start.txt`，修复 PyInstaller 安装版 `/mobile` 页面资源路径，移除
> `rtlsdr/pyrtlsdr/librtlsdr` 运行依赖，Windows 默认按 IC-M710 配置。

> 🎉 **V5.8.5 更新**: ATR-1000 天调自动学习全面修复 — 修复 `dispatch()` 嵌套函数未声明
> `global is_tx` 的回归（V5.7.1 引入），模块级 `is_tx` 不再恒为 False；学习入口改为按实测
> 功率判定发射（`power ≥ 3W`），面板直发/外部软件路径同样自动学习。

> 🎉 **V5.8.2 更新**: ATR-1000 功率/SWR 前端不显示修复（IOLoop 线程错位 — 主线程固定 MAIN_IOLOOP）、PTT 状态广播同根因修复
>
> 🎉 **V5.8.1 更新**: RX 时延/卡顿提升（IOLoop 去 rigctld 阻塞）、客户端水印 LAN 调参（200→100ms）、restart.sh 停不干净修复
>
> 🎉 **V5.8.0 更新**: ATR-1000 SWR>2 自动完整调谐守卫、学习/守卫功率阈值下调（LEARN 5→3W, 守卫 10→5W）
>
> 🎉 **V5.7.1 更新**: TX 采集迁移 AudioWorklet、PTT 尾音/预热帧修复、ATR-1000 幽灵功率修复、IC-M710 AGC/RF 增益控制（9-1 档）、FT8/CW 功能整体移除
>
> 🎉 **V5.7 更新**: RX/TX 音质全面优化（参考 mrrc_ft710）— Opus 码率 arm64 修复、标签帧、时间水印缓冲、软膝限幅、WDSP 48k + NR2 AE 调参、TX 48k/64kbps CBR、codebase 清理
>
> 历史版本: V5.3 网络监控与UI打磨 | V5.2.0 WDSP 哈希缓存优化 | V5.0.0 移动端UI现代化

---

## 🏗️ System Architecture / 系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Client Layer / 客户端层                           │
├───────────────────────────┬─────────────────────────────────────────────┤
│      Mobile Browser       │         External Software / API             │
│      移动端浏览器          │         外部软件 / API                       │
└─────────────┬─────────────┴──────────────────────┬──────────────────────┘
              │ HTTPS / WebSocket                  │ HTTP REST
              ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Service Layer / 服务层                             │
├───────────────────────────┬─────────────────────────────────────────────┤
│      MRRC Main Program    │         ATR-1000 API Server                 │
│      MRRC 主程序           │         RESTful API (:8080)                 │
│                           │                                             │
│  • Radio Control          │  • /api/v1/status    Status query          │
│  • Audio TX/RX            │  • /api/v1/relay     Relay control         │
│  • User Auth              │  • /api/v1/tune      Quick tune            │
└─────────────┬─────────────┴──────────────────────┬──────────────────────┘
              │                                    │
              │ rigctld + Audio                    │ Unix Socket
              ▼                                    ▼
┌───────────────────────────┐         ┌─────────────────────────────────────┐
│       Radio Device        │         │     ATR-1000 Proxy / 天调代理        │
│       电台设备             │         │       atr1000_proxy.py              │
│                           │         │                                     │
│  • Freq/Mode (rigctld)    │         │  • Single device connection         │
│  • PTT Control            │         │  • Dynamic polling: 600s/300s/TX 5s  │
│  • Audio TX/RX            │         │  • Smart Learning + Quick Tune      │
└───────────────────────────┘         └──────────────┬──────────────────────┘
                                                     │ WebSocket
                                                     ▼
                                     ┌─────────────────────────────────────┐
                                     │       ATR-1000 Tuner / 天调设备      │
                                     │                                     │
                                     │  • Power/SWR Display                │
                                     │  • Relay Params (SW/IND/CAP)        │
                                     └─────────────────────────────────────┘
```

**Key Points / 关键说明**:
- MRRC directly controls radio via rigctld + audio / MRRC 直接控制电台设备
- ATR-1000 Proxy only connects to tuner / 代理只连接天调设备

---

## 🏠 System Environment / 系统环境

> Complete MRRC system setup: Mobile device remote control station with ATR-1000 power meter and antenna tuner integration.

---

## 📸 Screenshots

### 📱 Mobile Interface

> Modern mobile UI optimized for iPhone/Android with touch-friendly controls, large PTT button, and real-time S-meter display.

---

### 🖥️ Desktop Interface

> Full-featured desktop interface with spectrum display, detailed controls, and comprehensive radio management.

---

## 🌐 Select Language / 选择语言

| Language | Description |
|----------|-------------|
| [**English**](README_en.md) | Documentation in English |
| [**中文**](README_CN.md) | 中文文档 |

---

## ✨ Key Features / 核心特性

| Feature | Description |
|---------|-------------|
| 📱 **Mobile First** | Optimized for iPhone/Android with touch-friendly UI |
| 🎛️ **Full Control** | Frequency, mode, PTT - complete station control |
| 🎤 **Real-time Audio** | Bidirectional streaming — TX 48kHz Opus, RX 16kHz low-jitter |
| 🎙️ **AI Voice Assistant** | Whisper ASR + Qwen3-TTS synthesis |
| 🎙️ **Audio Recording** | Record QSOs directly in browser (WAV/MP3) |
| 🌍 **Remote Anywhere** | Access your station from anywhere with internet |
| 🔒 **Secure Connection** | TLS encrypted HTTPS/WSS |
| ⚡ **Ultra Low Latency** | TX→RX switching < 100ms |
| 🎯 **One-Hand Operation** | PTT button optimized for mobile thumb reach |
| 🔧 **ATR-1000 Integration** | Smart tuner learning & quick tune |
| 🔌 **REST API** | Standalone API for external software integration |
| 🚀 **Remote Start** | SSH-based remote service management |
| 🖥️ **Multi-Instance** | Multiple independent radio instances on one server |
| 🖥️ **SDR Interface** | Modern SDR control interface |
| 🎙️ **RagChew TX Audio** | Warm, natural voice preset with EQ + compressor + noise gate |

---

## 🔧 ATR-1000 Smart Tuner / 天调智能学习

MRRC integrates with ATR-1000 antenna tuner for intelligent operation:

| Feature | Description |
|---------|-------------|
| 📊 **Real-time Monitor** | Power (0-200W) and SWR display |
| 🧠 **Smart Learning** | Auto-learn frequency-tuner mapping during TX |
| ⚡ **Quick Tune** | Auto-apply tuner params when frequency changes |
| 🎵 **Tune Assist** | Long-press Tune triggers full ATR-1000 tune when SWR > 1.6, updates memory if SWR improves, and restores old LC/CL/L/C if it does not |
| 💾 **Persistence** | Tuner records saved in JSON file |
| 🔌 **REST API** | External software can query/control tuner |

**How it works**:
```
Learning Flow:
TX Start → Sample SWR → SWR ≤ 1.5? → Record params → Save to JSON

Quick Tune Flow:
Freq Change → Lookup JSON → Found? → Apply params → Ready to TX!

Tune Assist Flow:
Tune Press → Sample SWR → SWR > 1.6? → Full tune → Improved? → Update memory / Restore old params
```

**API Example**:
```bash
# Quick tune to 7050 kHz
curl -X POST -d '{"freq_khz":7050}' http://localhost:8080/api/v1/tune

# Get current status
curl http://localhost:8080/api/v1/status
```

---

## 📊 Performance / 性能指标

| Metric | Value |
|--------|-------|
| TX Latency | ~65ms |
| RX Latency | ~51ms |
| TX→RX Switch | <100ms |
| PTT Reliability | 99%+ |
| Audio Recording | WAV/MP3, Auto-download |
| WDSP Processing | <20ms, 15-20dB NR2降噪 |
| ATR-1000 Polling (Idle) | 600s |
| ATR-1000 Polling (Active) | 300s |
| ATR-1000 Polling (TX) | 5s status check, no SYNC (device pushes METER) |

---

## 🚀 Quick Start / 快速开始

### Windows Installer / Windows 安装包（V6.0.0）

1. Download `MRRC-Setup.exe` from: <https://www.vlsc.net/mrrc/downloads/MRRC-Setup.exe>
2. Run the installer and launch `MRRC` from the Start Menu.
3. Accept the browser self-signed HTTPS warning once.
4. Read login info from `Login Info` in the Start Menu or:

```text
%LOCALAPPDATA%\MRRC\MRRC Quick Start.txt
```

Important Windows files:

```text
%LOCALAPPDATA%\MRRC\MRRC.conf              Main configuration
%LOCALAPPDATA%\MRRC\MRRC_users.db          Login users
%LOCALAPPDATA%\MRRC\MRRC Quick Start.txt   Login info and first-run help
```

IC-M710 rigctld example:

```powershell
rigctld.exe -m 30003 -r COM3 -s 4800 -C stop_bits=2 -T 127.0.0.1 -t 4532
```

See also: [Windows Installer Configuration Guide](docs/current/operations/windows-installer-config-guide.md)

### macOS/Linux Source Run

```bash
# 1. Start rigctld
rigctld -m 335 -r /dev/cu.usbserial-230 -s 4800

# 2. Start all services
./mrrc_control.sh start

# 3. Access from mobile browser
# https://your-domain/mobile_modern.html

# 4. (Optional) Start API Server
nohup python3 atr1000_api_server.py > atr1000_api.log 2>&1 &

# 5. (Optional) Remote start via SSH
./mrrc_remote_start.sh start
```

### 🎙️ Audio Recording / 音频录制

Access the recording page to record your QSOs:
```
https://your-domain/recordings.html
```

Features:
- Record RX audio directly in browser
- WAV format (lossless) or MP3 (compressed)
- Auto-download after recording
- Visual recording level indicator

---

## 📁 Project Structure / 项目结构

```
MRRC/
├── MRRC                    # Backend main program
├── MRRC.conf               # Configuration file
├── audio_interface.py      # PyAudio wrapper (V4.8.0: Multi-format decode)
├── hamlib_wrapper.py       # rigctld communication
├── wdsp_wrapper.py         # WDSP DSP processing
├── atr1000_proxy.py        # ATR-1000 proxy ⭐
├── atr1000_api_server.py   # REST API server ⭐
├── atr1000_tuner.py        # Tuner storage module
├── mrrc_control.sh         # Control script (V4.8.0: Enhanced)
├── mrrc_remote_start.sh    # Remote start via SSH (V4.8.0: New)
├── www/                    # Frontend
│   ├── mobile_modern.html  # Mobile UI
│   ├── mobile_modern.js    # Mobile UI logic
│   ├── controls.js         # Audio & control (V4.8.0: WDSP sync)
│   ├── recordings.html     # Audio recording page (V4.8.0: New)
│   └── panadapter/         # FFT/panadapter UI
├── certs/                  # TLS certificates
├── docs/current/           # Code-verified current documentation
├── docs/legacy/            # Historical/reference documentation
└── dev_tools/              # Test utilities
```

---

## 📄 License / 许可证

[GNU General Public License v3.0](LICENSE)

Based on [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5)

---

## 🔗 Links

- [English Documentation](README_en.md)
- [中文文档](README_CN.md)
- [Changelog](CHANGELOG.md)
- [Current Documentation Index](docs/README.md)
- [Current System Architecture](docs/current/architecture/current-system.md)
- [Current Capability Map](docs/current/design/capability-map.md)
- [Runtime & Verification](docs/current/operations/runtime-and-verification.md)
- [Windows Installer Configuration Guide](docs/current/operations/windows-installer-config-guide.md)
- [Legacy ATR-1000 Tuner Notes](docs/legacy/atr/ATR1000_Tuner_Auto_Learning.md)
- [Legacy Multi-Instance Setup](docs/legacy/operations/Multi_Instance_Setup.md)

---

**Latest Release: V6.0.0** (2026-09-05) | [View Changelog](CHANGELOG.md)

## 🖥️ Multi-Instance Support ⭐ New

MRRC V4.8+ supports running multiple independent instances on a single server, each connecting to different radio devices.

### Quick Start

```bash
# Create new instance
./mrrc_multi.sh create radio2

# Edit configuration (ports, serial device, audio)
vim MRRC.radio2.conf

# Start instance
./mrrc_multi.sh start radio2

# Access
# radio1: https://localhost:8891
# radio2: https://localhost:8892
```

### Key Features

| Feature | Description |
|---------|-------------|
| **Independent Ports** | Each instance uses independent Web and rigctld ports |
| **Independent Audio** | Support different sound cards |
| **Independent Tuner** | Each instance has its own Unix Socket and learning records |
| **Unified Management** | Manage all instances with `mrrc_multi.sh` script |

### Management Commands

```bash
./mrrc_multi.sh start radio2      # Start
./mrrc_multi.sh stop radio2       # Stop
./mrrc_multi.sh restart radio2    # Restart
./mrrc_multi.sh status radio2     # Check status
./mrrc_multi.sh logs radio2       # View logs
```

**Full Documentation**: [Multi-Instance Setup Guide](docs/legacy/operations/Multi_Instance_Setup.md)

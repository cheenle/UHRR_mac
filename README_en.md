# Mobile Remote Radio Control (MRRC)

[![English](https://img.shields.io/badge/lang-English-blue.svg)](README_en.md) [![中文](https://img.shields.io/badge/lang-中文-red.svg)](README_CN.md)

**Amateur Radio, Anytime, Anywhere.**

MRRC is a modern web-based remote control system optimized for mobile devices, enabling flexible operation of your amateur radio station from anywhere. Built with HTML5/JS frontend and Tornado + PyAudio + rigctld (Hamlib) backend.

> ✅ **Core Advantage**: Mobile-first design, TX→RX switching latency <100ms, PWA support for offline access, optimized for one-hand operation

## 🎯 Design Philosophy

**Mobile First, Radio Anywhere**

- 📱 **Mobile First**: Designed for touchscreens with large PTT buttons and thumb-friendly zones
- 🌍 **Anytime, Anywhere**: Control your station wherever internet is available
- ⚡ **Instant Response**: TX/RX switching <100ms, PTT reliability 99%+
- 🔒 **Secure Connection**: TLS encryption with user authentication

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Client Layer                                   │
├───────────────────────────┬─────────────────────────────────────────────┤
│      Mobile Browser       │         External Software / API             │
│  mobile_modern.html       │        Python / SDR / Loggers               │
│  (PWA, Touch Optimized)   │                                             │
└─────────────┬─────────────┴──────────────────────┬──────────────────────┘
              │ HTTPS / WebSocket                  │ HTTP REST (API)
              ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Service Layer                                   │
├───────────────────────────┬─────────────────────────────────────────────┤
│      MRRC Main Program    │         ATR-1000 API Server                 │
│   (Tornado WebSocket)     │      (RESTful API, :8080)                   │
│                           │                                             │
│  • Radio Control (rigctld)│  • /api/v1/status    Status query          │
│  • Audio TX/RX (PyAudio)  │  • /api/v1/relay     Relay control         │
│  • Freq Sync              │  • /api/v1/tune      Quick tune            │
│  • User Auth              │  • /api/v1/tuner     Learning records      │
└─────────────┬─────────────┴──────────────────────┬──────────────────────┘
              │                                    │
              │ rigctld + Audio                    │ Unix Socket
              │                                    │ /tmp/atr1000_proxy.sock
              ▼                                    ▼
┌───────────────────────────┐         ┌─────────────────────────────────────┐
│       Radio Device        │         │        ATR-1000 Proxy Layer         │
│   (IC-M710/IC-7300/etc)   │         │       atr1000_proxy.py              │
│                           │         │                                     │
│  • Freq/Mode (rigctld)    │         │  • Single device connection         │
│  • PTT Control            │         │  • Dynamic polling: 15s/5s/0.5s     │
│  • Audio TX/RX            │         │  • Smart Learning + Quick Tune      │
│  • S-Meter Reading        │         └──────────────┬──────────────────────┘
└───────────────────────────┘                        │ WebSocket
                                                     ▼
                                     ┌─────────────────────────────────────┐
                                     │       ATR-1000 Tuner Device         │
                                     │      (Power Meter + Auto Tuner)     │
                                     │                                     │
                                     │  • Real-time Power/SWR Display      │
                                     │  • Relay Params (SW/IND/CAP)        │
                                     └─────────────────────────────────────┘
```

**Architecture Notes**:
- **MRRC Main**: Directly controls radio device (Audio TX/RX + rigctld frequency control)
- **ATR-1000 Proxy**: Standalone proxy, only communicates with ATR-1000 tuner
- **API Server**: Calls Proxy via Unix Socket, no direct device connection

## 🧩 Core Components

### Backend Components

| Component | File | Function |
|-----------|------|----------|
| **MRRC Main** | `MRRC` | Tornado WebSocket server, radio control, audio stream, user auth |
| **Audio Interface** | `audio_interface.py` | PyAudio wrapper, audio capture and playback |
| **Hamlib Wrapper** | `hamlib_wrapper.py` | rigctld communication wrapper |
| **ATR-1000 Proxy** | `atr1000_proxy.py` | Tuner device proxy, smart learning, quick tune |
| **ATR-1000 API** | `atr1000_api_server.py` | RESTful API service for external software |
| **Tuner Storage** | `atr1000_tuner.py` | Frequency-parameter mapping storage |
| **TCI Client** | `tci_client.py` | TCI protocol support (specific radios) |

### Frontend Components

| Component | File | Function |
|-----------|------|----------|
| **Mobile UI** | `www/mobile_modern.html` | iPhone 15 optimized, PWA support |
| **Mobile Logic** | `www/mobile_modern.js` | Mobile WebSocket and UI logic |
| **Control Core** | `www/controls.js` | Audio processing, PTT control, WebSocket |
| **TX Optimizer** | `www/tx_button_optimized.js` | TX button timing optimization |
| **RX Player** | `www/rx_worklet_processor.js` | AudioWorklet low-latency playback |
| **ATU Display** | `www/atu.js` | Power/SWR real-time display |

## ✨ Features

### Mobile Core Features
- **Touch-Optimized Interface**: Large buttons, clear frequency display, real-time S-meter
- **One-Hand Operation**: PTT button positioned for comfortable thumb reach
- **PWA Support**: Add to home screen, offline access capability
- **Volume Control**: Direct AF gain adjustment on main screen

### Radio Control
- **Full Control**: Frequency, mode, PTT (press to transmit, release to stop)
- **VFO Switching**: Quick VFO A/B toggle
- **Band Selection**: One-tap switching between amateur bands
- **Antenna Tuner Support**: Long-press TUNE button to transmit 1kHz tone

### Audio System
- **Bidirectional Audio**: TX with Int16 encoding, RX with low-jitter AudioWorklet playback, 16kHz sample rate
- **Real-time S-Meter**: Accurate S0-S9+60dB signal strength display
- **Audio Filters**: Multiple filter configurations available
- **TX Equalizer**: 3-band EQ for TX audio, supports SSB voice/weak signal/contest modes

### ATR-1000 Smart Tuner ⭐ Core Feature
- **Real-time Power Display**: Forward power (0-200W) during TX, latency <200ms
- **SWR Monitoring**: Real-time SWR display (1.0-9.99)
- **Smart Learning**: Auto-learn frequency-tuner (SW/IND/CAP) mapping during TX
- **Quick Tune**: Auto-apply learned tuner params when frequency changes
- **Persistence**: Tuner records saved in JSON file, auto-loaded on restart
- **Standalone API**: RESTful API for external software integration

### Dynamic Polling Optimization
To prevent device hang from excessive requests, implemented dynamic polling:

| State | Polling Interval | Description |
|-------|------------------|-------------|
| Idle | 15 seconds | No client connected, reduced device load |
| Active | 5 seconds | Client connected, keep connection alive |
| TX | 0.5 seconds | During TX, fast power/SWR updates |

### Security & Connection
- **TLS/Certificates**: Support for custom certificate chain (fullchain + private key)
- **User Authentication**: FILE-based authentication to protect your station

## 🚀 Quick Start (macOS)

### 1. Dependencies
- Python 3.12+
- Hamlib/rigctld installed and available
- PyAudio (based on PortAudio)

### 2. Start rigctld
```bash
# Example, adjust according to your actual serial port/parameters
rigctld -m 335 -r /dev/cu.usbserial-230 -s 4800
```

### 3. Configure TLS Certificates (optional but recommended)
```bash
# Place certificates in certs/ directory
# certs/fullchain.pem (server certificate + intermediate certificate)
# certs/radio.vlsc.net.key (private key)
```

Edit `MRRC.conf`:
```ini
[SERVER]
port = 443
certfile = certs/fullchain.pem
keyfile = certs/radio.vlsc.net.key
auth = FILE
```

### 4. Start Services
```bash
# Using control script (recommended)
./mrrc_control.sh start

# Or start services individually
./mrrc_control.sh start-rigctld
./mrrc_control.sh start-mrrc
./mrrc_control.sh start-atr1000
```

### 5. Access
- **Mobile**: `https://<your-domain>/mobile_modern.html` ⭐ Recommended
- **Desktop**: `https://<your-domain>/`
- **ATR-1000 API**: `http://localhost:8080`

## 📁 Directory Structure

```
MRRC/
├── MRRC                        # Backend main program (Tornado WebSocket server)
├── MRRC.conf                   # System core configuration file
├── audio_interface.py          # PyAudio capture/playback wrapper
├── hamlib_wrapper.py           # rigctld communication helper
├── tci_client.py               # TCI protocol client implementation
├── atr1000_proxy.py            # ATR-1000 standalone proxy ⭐
├── atr1000_api_server.py       # ATR-1000 REST API service ⭐
├── atr1000_tuner.py            # Tuner storage module
├── atr1000_tuner.json          # Tuner parameter data file
├── mrrc_control.sh             # System control script (start/stop/status)
├── mrrc_monitor.sh             # System monitor script
├── www/                        # Frontend pages and scripts
│   ├── mobile_modern.html      # Modern mobile interface ⭐
│   ├── mobile_modern.js        # Mobile interface logic
│   ├── controls.js             # Audio and control main logic
│   ├── tx_button_optimized.js  # TX button event and timing optimization
│   ├── rx_worklet_processor.js # AudioWorklet player
│   ├── atu.js                  # ATU power and SWR display management
│   └── panadapter/             # Spectrum display module
├── certs/                      # TLS certificates directory
├── docs/                       # Technical documentation
├── dev_tools/                  # Test/debug scripts
└── nanovna/                    # NanoVNA vector network analyzer web UI
```

## ⚙️ Key Configuration

`MRRC.conf` main settings:
- `[SERVER] port`: Listening port (production recommendation: 443)
- `[SERVER] auth`: Authentication method (FILE)
- `[AUDIO] inputdevice/outputdevice`: Audio devices
- `[HAMLIB] rig_pathname/rig_model`: Radio serial port and model

## 📊 Performance Metrics

| Metric | Value |
|--------|-------|
| TX Latency | ~65ms |
| RX Latency | ~51ms |
| TX→RX Switch | <100ms |
| PTT Reliability | 99%+ |
| ATR-1000 Power Display Latency | <200ms |
| Idle Polling Interval | 15 seconds |

## 🔌 ATR-1000 API Usage

### Start API Service
```bash
# Ensure Proxy is running
./mrrc_control.sh start-atr1000

# Start API Server
nohup python3 atr1000_api_server.py > atr1000_api.log 2>&1 &
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/status` | Get current status |
| GET | `/api/v1/relay` | Get relay parameters |
| POST | `/api/v1/relay` | Set relay parameters |
| GET | `/api/v1/tuner/lookup` | Lookup tuner params |
| POST | `/api/v1/tune` | Quick tune |

### Usage Examples
```bash
# Get status
curl http://localhost:8080/api/v1/status

# Quick tune to 7050 kHz
curl -X POST -H "Content-Type: application/json" \
     -d '{"freq_khz":7050}' http://localhost:8080/api/v1/tune

# Set relay
curl -X POST -H "Content-Type: application/json" \
     -d '{"sw":1,"ind":30,"cap":27}' http://localhost:8080/api/v1/relay
```

## 📚 Documentation

- **[System Architecture Design](docs/System_Architecture_Design.md)**: Complete system architecture
- **[ATR-1000 Smart Tuner](docs/ATR1000_Tuner_Auto_Learning.md)**: Tuner learning and API detailed docs ⭐
- **[PTT/Audio Stability](docs/PTT_Audio_Postmortem_and_Best_Practices.md)**: Stability analysis and best practices
- **[Latency Optimization Guide](docs/latency_optimization_guide.md)**: TX/RX switching optimization details
- **[Mobile Interface Documentation](docs/mobile_modern_interface.md)**: Mobile UI design specifications

## 🔧 Troubleshooting

### Port Occupation
```bash
lsof -iTCP:443 -sTCP:LISTEN -n -P
kill -9 <PID>
```

### Certificate Error
```bash
# Standardize line breaks
sed -e 's/\r$//' input.pem > output.pem
```

### Mobile PTT Not Responding
1. Confirm microphone permission is granted
2. Check WebSocket connection status
3. Review browser console logs

### ATR-1000 Device Hang
1. Check if multiple processes are connecting to the device
2. Ensure V2 API Server is used (communicates via Proxy)
3. Verify dynamic polling intervals are in effect

## 📄 License

[GNU General Public License v3.0](LICENSE)

Based on [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5)

---

**MRRC - Mobile Remote Radio Control**  
*Amateur Radio, Anytime, Anywhere.*
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

### ATR-1000 Smart Tuner ⭐ Core Feature
- **Real-time Power Display**: Forward power (0-200W) during TX, latency <200ms
- **SWR Monitoring**: Real-time SWR display (1.0-9.99)
- **Smart Learning**: Auto-learn frequency-tuner (SW/IND/CAP) mapping during TX
- **Quick Tune**: Auto-apply learned tuner params when frequency changes
- **Persistence**: Tuner records saved in JSON file, auto-loaded on restart
- **Connection Preheat**: Pre-establish connection on page load for fast PTT response

**How it Works**:
```
Learning Flow:
TX Start → Sample SWR → SWR ≤ 1.5? → Record params → Save to JSON

Quick Tune Flow:
Freq Change → Lookup JSON → Found? → Apply params → Ready to TX!
```

**Supported Parameters**:
| Frequency | SW | L | C | SWR |
|-----------|-----|------|------|------|
| 7.050MHz | CL | 0.3uH | 270pF | 1.08 |
| 14.270MHz | LC | 0.1uH | 90pF | 1.22 |

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

### 4. Start Service
```bash
python ./MRRC
```

### 5. Access
- **Mobile**: `https://<your-domain>/mobile_modern.html` ⭐ Recommended
- **Desktop**: `https://<your-domain>/`

## 📱 Mobile Interface

| Interface | Purpose | Features |
|-----------|---------|----------|
| `mobile_modern.html` | Modern mobile UI | iPhone 15 optimized, PWA support, one-hand operation |
| `index.html` | Desktop full interface | Full-featured control, suitable for large screens |

## 📁 Directory Structure

```
MRRC/
├── www/                        # Frontend pages and scripts
│   ├── mobile_modern.html      # Mobile main interface ⭐
│   ├── mobile_modern.js        # Mobile logic
│   ├── controls.js             # Audio and control main logic
│   ├── tx_button_optimized.js  # TX button optimization
│   └── rx_worklet_processor.js # AudioWorklet player
├── MRRC                        # Backend main program
├── audio_interface.py          # PyAudio encapsulation
├── hamlib_wrapper.py           # rigctld communication
├── certs/                      # TLS certificates
├── docs/                       # Documentation
├── dev_tools/                  # Test utilities
└── nanovna/                    # NanoVNA integration
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

## 📚 Documentation

- **[System Architecture Design](docs/System_Architecture_Design.md)**: Complete system architecture
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

## 📄 License

[GNU General Public License v3.0](LICENSE)

Based on [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5)

---

**MRRC - Mobile Remote Radio Control**  
*Amateur Radio, Anytime, Anywhere.*

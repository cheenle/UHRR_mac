# Universal HamRadio Remote (UHRR)

A web-based remote control and audio streaming system for amateur radio. Frontend based on HTML5/JS, backend based on Tornado + PyAudio + rigctld (Hamlib). Optimized for macOS/mobile and TLS, with significantly improved TX/PTT timing and RX jitter.

> ✅ **Important**: TX to RX switching latency optimized from 2-3s to <100ms

## Features

- **Remote Control**: Frequency, mode, PTT, VFO switching, S-meter
- **Bidirectional Audio**: TX Int16 encoding, RX low-jitter playback (AudioWorklet), 16kHz sample rate
- **TLS Encryption**: Supports custom certificate chain
- **Mobile Support**: iPhone/Android dedicated interface ★
- **PTT Reliability**: Press to send, warm-up frames ensure transmission
- **Fast Switching**: TX/RX switching <100ms latency

## Quick Start

### 1. Install Dependencies
```bash
./uhrr_setup.sh install
```

### 2. Start rigctld
```bash
rigctld -m 30003 -r /dev/cu.usbserial-120 -s 4800 -C stop_bits=2
```

### 3. Start Service
```bash
./uhrr_control.sh start
```

### 4. Access
- Desktop: `https://<IP>/index.html`
- Mobile: `https://<IP>/mobile_modern.html` ★

## Mobile Interface (v3.2)

New optimized mobile interface for iPhone/Android:

| Feature | Description |
|---------|-------------|
| Band Selection | 160m-2m full band |
| Mode Selection | USB/LSB/CW/FM/AM/WFM |
| Step Selection | 10Hz-10kHz |
| Filter Selection | Wide/Narrow/Medium |
| Volume Control | Slider + Mute |
| PTT Button | Large with haptic feedback |

### iPhone Notes
- First-time use requires microphone permission
- If no sound, tap any button to activate AudioContext
- Recommend adding to home screen as PWA

## Directory Structure

```
UHRR_mac/
├── UHRR              # Backend main program
├── UHRR.conf         # Configuration file
├── audio_interface.py # PyAudio wrapper
├── hamlib_wrapper.py  # rigctld helper
├── tci_client.py      # TCI protocol
├── uhrr_control.sh   # Service control
├── uhrr_setup.sh     # Setup script
├── www/              # Frontend
│   ├── index.html           # Desktop
│   ├── mobile_modern.html   # Mobile ★
│   ├── controls.js          # Desktop logic
│   └── mobile_modern.js     # Mobile logic
├── certs/            # TLS certificates
├── dev_tools/        # Test tools
├── opus/             # Opus codec
└── nanovna/          # NanoVNA interface
```

## Service Management

```bash
./uhrr_control.sh start    # Start
./uhrr_control.sh stop     # Stop
./uhrr_control.sh restart  # Restart
./uhrr_control.sh status    # Status
./uhrr_control.sh logs     # Logs
```

## Configuration (UHRR.conf)

```ini
[SERVER]
port = 8877
certfile = certs/fullchain.pem
keyfile = certs/radio.vlsc.net.key

[AUDIO]
audio_input = USB Audio Device
audio_output = USB Audio Device

[HAMLIB]
rig_pathname = /dev/cu.usbserial-120
rig_model = IC_M710
rig_rate = 4800
```

## Common Issues

### Port in Use
```bash
lsof -iTCP:8877
kill -9 <PID>
```

### No Sound
- Check WebSocket connection status
- iPhone: Tap button to activate AudioContext
- Check volume settings

### PTT Not Responding
- Confirm connected (power button highlighted)
- Check microphone permission
- Check console for errors

## Version History

| Version | Date | Description |
|---------|------|-------------|
| v3.2 | 2026-03-01 | Mobile interface全面优化, iOS compatibility fix |
| v3.1 | 2025-xx | Mobile audio and PTT optimization |
| v3.0 | 2025-xx | TX/RX latency optimization, AudioWorklet |

## Technical Documentation

See `docs/` directory for detailed technical docs:
- System Architecture Design
- Latency Optimization Guide
- PTT/Audio Stability Analysis

## License

GPL-3.0, based on [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5)

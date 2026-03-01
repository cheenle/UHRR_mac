# Universal HamRadio Remote (UHRR)

A web-based remote control and audio streaming system for shortwave radios. The frontend is based on HTML5/JS, and the backend is based on Tornado + PyAudio + rigctld (Hamlib). This version has been fixed and optimized for macOS/mobile and TLS, and significantly improved TX/PTT timing and RX jitter.

> ✅ **Important Optimization**: Resolved TX to RX switching latency issue (optimized from 2-3s to <100ms), see [docs/latency_optimization_guide.md](docs/latency_optimization_guide.md) for details

## Features
- Browser-based operation: Frequency, mode, PTT (press to transmit immediately, release to stop immediately)
- Bidirectional audio: TX side Opus encoding, RX side low-jitter playback (AudioWorklet), sample rate 24 kHz
- TLS/Certificates: Supports own certificate chain (fullchain + private key)
- Backend: Tornado WebSocket, PyAudio capture/playback, rigctld radio control
- **Enhanced PTT Reliability Mechanism**: Send PTT command immediately upon press, and send warm-up frames to ensure backend receives audio data
- **Optimized TX/RX Switching**: Nearly real-time mode switching (<100ms latency)
- **Mobile Optimization**: UI and interaction optimized for touchscreen devices

## Quick Start (macOS)
1. Dependencies
   - Python 3.12+
   - Hamlib/rigctld installed and available
   - PyAudio (based on PortAudio)
2. Start rigctld (example, adjust according to your actual serial port/parameters):
   ```bash
   rigctld -m 335 -r /dev/cu.usbserial-230 -s 4800
   ```
3. Configure TLS certificates (optional but recommended)
   - Place your certificates in `certs/`:
     - `certs/fullchain.pem` (server certificate + intermediate certificate)
     - `certs/radio.vlsc.net.key` (private key)
   - Edit `UHRR.conf`:
     ```ini
     [SERVER]
     port = 443
     certfile = certs/fullchain.pem
     keyfile = certs/radio.vlsc.net.key
     ```
4. Start service
   ```bash
   python ./UHRR
   ```
   - Console should display `HTTP server started.`
   - If port is occupied, clean up old processes first
5. Access
   - `https://<your_domain_or_IP>/` (if using 443) or `https://<host>:8888/`

## Directory Structure Overview
- `www/`: Frontend pages and scripts
  - `controls.js`: Audio and control main logic (including TX Opus encoding, RX Worklet playback, bitrate display, PTT command confirmation and retry, etc.)
  - `tx_button_optimized.js`: TX button events and timing (including enhanced PTT reliability mechanism and latency optimization)
  - `rx_worklet_processor.js`: AudioWorklet player (low jitter)
- `UHRR`: Backend main program (Tornado + WebSocket + SSLContext)
- `audio_interface.py`: PyAudio capture/playback encapsulation and client distribution
- `hamlib_wrapper.py`: Auxiliary logic for rigctld communication
- `certs/`: Certificate related
  - `fullchain.pem`, `radio.vlsc.net.key` (production use)
  - `legacy/` stores historical certificates (migrated)
- `dev_tools/`: Test/debug scripts and pages (non-production)
- `logs/`: Runtime logs
- `docs/`: Technical documentation
  - `System_Architecture_Design.md`: System architecture design document
  - `PTT_Audio_Postmortem_and_Best_Practices.md`: PTT/audio stability postmortem
  - `latency_optimization_guide.md`: TX/RX switching latency optimization guide

## Key Configuration
- `UHRR.conf`
  - `[SERVER] port`: Listening port (production recommendation: 443)
  - `[SERVER] certfile/keyfile`: fullchain and private key paths
  - `[CTRL].interval_smeter_update`: S meter update interval
  - `[AUDIO] inputdevice/outputdevice`: Audio device names
  - `[HAMLIB] rig_pathname/rig_rate/rig_model`: Radio serial port and parameters

## Audio and Timing Strategy
- TX:
  - Frontend `OpusEncoderProcessor`: `opusRate = 24000`, `opusFrameDur = 60ms`
  - Backend `WS_AudioTXHandler` receives and plays; PTT timeout protection (automatically disconnects after 2s without data)
  - **Enhanced PTT Reliability Mechanism**: Send PTT command immediately upon press, and send 10 warm-up frames immediately to ensure backend receives audio data
- RX:
  - Backend `AudioRXHandler.tailstream` bulk delivery to reduce jitter
  - Frontend `AudioWorkletNode` playback, set buffer depth (optimized to 16/32 frames, balancing latency and stability)
  - **Optimized Buffer Management**: Immediately clear RX buffer when TX is released, achieving <100ms switching response

## TLS/Certificate Notes
- fullchain.pem should only contain "server certificate + intermediate certificate", do not拼root certificate
- If exported from Windows/certain panels, standardize line breaks (LF), remove trailing backslashes
- Backend uses `ssl.SSLContext` to load certificate chain and private key

## Common Troubleshooting
- Port occupation:
  ```bash
  lsof -iTCP:443 -sTCP:LISTEN -n -P
  kill -9 <PID>
  ```
- Certificate error (bad end line):
  - Use `sed -e 's/\r$//'` to standardize line breaks
  - Confirm `-----BEGIN/END CERTIFICATE-----` lines are complete
- TX press doesn't transmit immediately:
  - Confirm power button on page is on, WebSocket is connected
  - Backend uses enhanced PTT reliability mechanism: send PTT command immediately upon press, and send 10 warm-up frames immediately to ensure backend receives audio data
  - Backend uses count timeout method (10 consecutive times without receiving audio frames to extinguish PTT, each check interval 200ms) instead of time threshold method
- RX jitter:
  - Maintain 24k end-to-end consistency
  - Can adjust Worklet buffer (e.g., 16/32 or 32/64)
- TX to RX switching latency:
  - Optimized buffer clearing mechanism and PTT command processing, achieving <100ms switching response
  - See [Latency Optimization Guide](docs/latency_optimization_guide.md) for details

## Documentation
- **[System Architecture Design Document](docs/System_Architecture_Design.md)**: Complete system architecture design, component relationships, interface protocols, deployment solutions, and technical specifications
- **[PTT/Audio Stability Postmortem](docs/PTT_Audio_Postmortem_and_Best_Practices.md)**: In-depth analysis and best practices for TX/RX stability issues
- **[TX/RX Switching Latency Optimization Guide](docs/latency_optimization_guide.md)**: Detailed documentation of latency issue analysis and optimization solutions

## Development and Testing
- All test/debug scripts are located in `dev_tools/`, not included in production deployment
- Recommended to make experimental modifications in independent branches

## License and Compliance
- This project follows the **GNU General Public License v3.0 (GPL-3.0)** license
- **Project Source**: Based on the [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5) open source project for development and improvement
- **Modification Statement**: Stability optimization, architecture upgrade, and feature enhancement have been made to the original code, see [System Architecture Design Document](docs/System_Architecture_Design.md#142-项目来源声明) for details
- **Distribution Requirements**: Must provide complete source code and retain license and copyright notices
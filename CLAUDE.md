# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Universal HamRadio Remote HTML5 (MRRC) is a Python/Tornado-based server application with HTML5 frontend that provides a web interface for controlling amateur radio equipment (TRX) for both RX and TX operations. Originally designed for Raspberry Pi OS, now supports cross-platform operation including macOS and Windows. Users can access radio functions via web browsers using their computer's audio system for communication.

## Codebase Architecture

### Backend (Python/Tornado Server)
- **Main Server**: `MRRC` script - Tornado-based WebSocket server handling multiple client connections
- **Core Components**:
  - WebSocket handlers for audio streaming (RX/TX), control signals, and FFT data
  - Hamlib integration via `hamlib_wrapper.py` for radio control (frequency, mode, PTT)
  - Cross-platform audio interface via `audio_interface.py` (replaces ALSA-specific implementation)
  - PyAudio for cross-platform audio I/O (works on macOS, Linux, Windows)
  - RTL-SDR support for panadapter functionality
  - Configuration management via `MRRC.conf`
  - User authentication system in `MRRC_users.db`

### Frontend (HTML5/JavaScript)
- **Main Interface**: `www/index.html` - Comprehensive radio operation controls with responsive design
- **JavaScript Logic**: `www/controls.js` handling UI interactions and WebSocket communication
- **Visual Components**: Frequency display, meters, band shortcuts (160m through 70cm), mode selectors
- **Panadapter Functionality**: Located in `www/panadapter/` for spectrum display
- **Advanced Features**: Antenna Tuning Unit (ATU) integration with power/SWR monitoring
- **Audio Worklets**: Optimized audio processing with reduced jitter and latency

### Additional Services
- **ATU Server**: `ATU_SERVER_WEBSOCKET.py` - Separate WebSocket server for antenna tuning unit control
- **Codec Implementation**: `opus/` directory containing Opus codec for efficient audio compression

## Cross-Platform Support

### Audio Interface
- Originally used ALSA (Linux/Raspberry Pi) - now migrated to PyAudio for cross-platform compatibility
- `audio_interface.py` provides unified interface for audio capture/playback
- `enumerate_audio_devices()` function to detect available audio devices
- Supports macOS, Linux, and Windows with single codebase

### Radio Control
- Hamlib integration via ctypes wrapper (`hamlib_wrapper.py`)
- Supports various radio models through Hamlib library
- Serial communication for CAT interface control
- Dynamic library loading with fallback paths for different platforms

## Key Features

### Core Functionality
- Remote radio control via web browser
- Real-time RX/TX audio streaming with Opus codec compression
- Frequency control with band shortcuts (160m through 70cm)
- Mode selection (USB/LSB/CW/AM/FM)
- S-meter display and signal strength monitoring
- PTT (Push-to-Talk) control with visual indicators
- Audio gain control and squelch

### Advanced Features
- **Antenna Tuning Unit (ATU) Integration**: Power/SWR monitoring, tuning controls, frequency-based presets
- **Panadapter/Spectrum Display**: Real-time FFT visualization via RTL-SDR
- **Mobile Optimization**: Responsive design with touch-friendly controls
- **Cross-platform Audio**: Works on macOS, Linux, Windows with consistent performance
- **Voice Assistant**: Whisper ASR + Qwen3-TTS integration for voice control
- **CW Decoder**: ONNX-based real-time Morse code decoding with QSO state machine
- **Multi-Instance Support**: Single server, multiple independent radio instances

## Development Commands

### Running the Application
```bash
# Direct execution (ensure dependencies installed)
./MRRC

# Using Docker
docker-compose up --build

# Alternative Docker command (check docker-compose.yml for port mapping)
docker run -d --device=/dev/snd --device=/dev/ttyUSB0 -p 8888:8888 uhrh
```

### Testing & Debugging
```bash
# Run installation test
python3 dev_tools/test_installation.py

# Test audio components
python3 dev_tools/test_audio.py
python3 dev_tools/test_audio_capture.py

# Test server connectivity
python3 dev_tools/test_connection.py

# Audio quality test
bash dev_tools/test_audio_quality.sh

# Web-based debugging tools available in dev_tools/
```

### Dependencies Installation (macOS)
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required libraries
brew install portaudio hamlib rtl-sdr

# Install Python packages
pip3 install pyaudio numpy tornado pyserial pyrtlsdr
```

### Configuration
- **Main Configuration**: `MRRC.conf` - Contains server, audio, hamlib, and panadapter settings
- **Web Interface**: Access `/CONFIG` endpoint for web-based configuration
- **User Authentication**: `MRRC_users.db` SQLite database
- **SSL Certificates**: Located in `certs/` directory or root as `UHRH.crt`/`UHRH.key`

### Docker Build Process
- Dockerfile builds Hamlib from source (version 4.5.5)
- Alpine Linux base image with necessary audio/radio libraries
- Audio devices mapped via `--device=/dev/snd` in docker-compose.yml
- Serial devices mapped via `--device=/dev/ttyUSB0` for radio control

## File Structure

### Critical Files
- `MRRC`: Main server executable with WebSocket handlers and radio control
- `MRRC.conf`: Configuration file with multiple sections (SERVER, CTRL, AUDIO, HAMLIB, PANADAPTER)
- `audio_interface.py`: Cross-platform audio abstraction layer
- `hamlib_wrapper.py`: ctypes wrapper for Hamlib radio control
- `ATU_SERVER_WEBSOCKET.py`: Separate server for antenna tuning unit

### Web Interface (`www/`)
- `index.html`: Main interface with radio controls
- `controls.js`: Core JavaScript for UI interactions
- `tx_button_optimized.js`: Optimized PTT button logic
- `atu.js`, `atu_autotune.js`: Antenna tuning unit functionality
- `panadapter/`: Spectrum display implementation

### Audio Processing (`opus/`)
- Opus codec implementation for audio compression
- Encoder/decoder classes for bandwidth optimization

### Development Tools (`dev_tools/`)
- Multiple test utilities for debugging audio, connectivity, and services
- HTML/JS tools for audio quality testing
- Service verification scripts
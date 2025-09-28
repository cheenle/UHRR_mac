# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is Universal HamRadio Remote HTML5, a Python server and HTML5 frontend that provides a web interface to control amateur radio equipment (TRX) for both RX and TX operations. Users can access basic and advanced radio functions through a web browser, using their computer's speaker and microphone for communication.

## Codebase Architecture

### Backend (Python/Tornado)
- Main server: `UHRR` - A Tornado-based WebSocket server handling multiple connections
- Core components:
  - WebSocket handlers for audio streaming (RX/TX), control signals, and FFT data
  - Hamlib integration for radio control (frequency, mode, PTT)
  - ALSA audio interface for capturing and playing audio
  - RTL-SDR support for panadapter functionality
  - Configuration management via `UHRR.conf`
  - User authentication system

### Frontend (HTML5/JavaScript)
- Main interface: `www/index.html` with extensive controls for radio operation
- JavaScript logic: `www/controls.js` handling UI interactions and WebSocket communication
- Visual components: Frequency display, meters, band shortcuts, mode selectors
- Panadapter functionality in `www/panadapter/` for spectrum display

### Audio Processing
- Opus codec integration for efficient audio encoding/decoding
- Real-time audio streaming via WebSockets
- ALSA interface for hardware audio I/O

## Common Development Tasks

### Running the Application
```bash
# Direct execution
./UHRR

# Using Docker
docker-compose up --build
```

### Configuration
- Main configuration file: `UHRR.conf`
- Web-based configuration interface available at `/CONFIG`
- SSL certificates: `UHRH.crt` and `UHRH.key`

### Dependencies
- Python 3 with Tornado, Hamlib, ALSA audio, NumPy
- RTL-SDR support for panadapter feature
- Opus codec for audio compression
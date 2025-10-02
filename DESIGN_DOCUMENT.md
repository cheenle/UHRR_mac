# Universal HamRadio Remote HTML5 - Design Document

## 1. Overview

Universal HamRadio Remote HTML5 (UHRR) is a Python-based server application with an HTML5 frontend that provides a web interface for controlling amateur radio equipment. The system enables users to remotely operate their radio transceivers through a web browser, supporting both RX (receive) and TX (transmit) operations using the computer's speaker and microphone for communication.

## 2. System Architecture

### 2.1 High-Level Architecture

The system follows a client-server architecture:

```
[Web Browser] <-- HTTPS/WebSocket --> [UHRR Server] <-- Serial/CAT --> [Radio]
                                      ↑
                                      |
                              [Audio Interface]
                                      |
                              [Computer Audio]
```

### 2.2 Core Components

#### 2.2.1 Backend (Python/Tornado Server)
- **Main Server**: `UHRR` - A Tornado-based WebSocket server handling multiple connections
- **WebSocket Handlers**: 
  - Audio streaming (RX/TX)
  - Control signals (frequency, mode, PTT)
  - FFT data for panadapter functionality
- **Radio Control**: Hamlib integration for radio control via serial/CAT interface
- **Audio Processing**: ALSA or PyAudio interface for capturing and playing audio
- **Panadapter**: RTL-SDR support for spectrum display
- **Configuration**: Management via `UHRR.conf`

#### 2.2.2 Frontend (HTML5/JavaScript)
- **Main Interface**: `www/index.html` with extensive controls for radio operation
- **JavaScript Logic**: `www/controls.js` handling UI interactions and WebSocket communication
- **Visual Components**: Frequency display, meters, band shortcuts, mode selectors
- **Panadapter**: Spectrum display functionality in `www/panadapter/`

#### 2.2.3 Audio Processing
- **Codec**: Opus codec integration for efficient audio encoding/decoding
- **Real-time Streaming**: Via WebSockets with minimal latency
- **Hardware Interface**: ALSA (Linux) or PyAudio (cross-platform) for audio I/O

## 3. Detailed Component Analysis

### 3.1 Server Implementation (UHRR)

The main server is implemented in `UHRR` using Python and the Tornado framework. Key features include:

#### 3.1.1 WebSocket Handlers
- **WS_AudioRXHandler**: Handles incoming audio from the radio for playback in the browser
- **WS_AudioTXHandler**: Handles outgoing audio from the browser to the radio for transmission
- **WS_ControlTRX**: Manages radio control commands (frequency, mode, PTT)
- **WS_panFFTHandler**: Provides FFT data for the panadapter display

#### 3.1.2 Radio Control (TRXRIG)
- Implements the `TRXRIG` class for radio control
- Uses Hamlib for communication with radio equipment
- Supports frequency setting/getting, mode setting/getting, PTT control with enhanced reliability
- Includes signal strength monitoring
- Supports rigctld daemon for persistent connections
- Implements PTT command retry mechanisms (up to 3 attempts)
- Uses miss count timeout method for PTT auto-off (10 consecutive misses at 200ms intervals)

#### 3.1.3 Audio Processing
- Cross-platform audio interface using PyAudio (with ALSA fallback)
- Real-time audio capture and playback
- Opus codec for efficient audio compression
- Automatic stereo-to-mono conversion for better audio quality

#### 3.1.4 Panadapter Functionality
- RTL-SDR integration for spectrum monitoring
- FFT processing for frequency analysis
- Real-time waterfall and spectrum displays

### 3.2 Frontend Implementation

#### 3.2.1 Main Interface (index.html)
- Frequency display with digit-by-digit control
- Band shortcut buttons for common amateur radio bands
- Audio filter selection (LP, BP, custom)
- S-meter display for signal strength
- Mode selection (USB, LSB, CW, AM, FM)
- TX controls with PTT functionality

#### 3.2.2 JavaScript Logic (controls.js)
- WebSocket management for real-time communication
- UI event handling for all controls
- Audio processing using Web Audio API
- FFT visualization for panadapter
- Configuration management via cookies
- PTT command confirmation and retry mechanisms (up to 3 attempts)
- Enhanced TX button handling with pre-warmup frames

#### 3.2.3 Panadapter Interface (panfft.html/js)
- Real-time spectrum display
- Waterfall view for signal history
- Frequency zoom and centering
- Click-to-tune functionality

### 3.3 Audio Processing

#### 3.3.1 Codecs
- Opus codec for efficient audio compression
- Configurable bitrates and frame sizes
- Real-time encoding/decoding with low latency

#### 3.3.2 Audio Interfaces
- **PyAudio**: Cross-platform audio I/O with device enumeration
- **ALSA**: Linux-specific audio interface (fallback)
- Automatic device detection and configuration
- Stereo-to-mono conversion with signal detection

### 3.4 Radio Control

#### 3.4.1 Hamlib Integration
- Custom ctypes-based wrapper (`hamlib_wrapper.py`)
- Support for multiple radio models
- Serial communication via CAT interface
- rigctld daemon support for persistent connections

#### 3.4.2 Radio Features
- Frequency control with 1Hz resolution
- Mode selection (USB, LSB, CW, AM, FM)
- PTT control for transmit operations
- Signal strength monitoring
- Power state management

### 3.5 Configuration Management

#### 3.5.1 Configuration File (UHRR.conf)
The system uses an INI-style configuration file with the following sections:

- **[SERVER]**: Port, SSL certificates, authentication settings
- **[CTRL]**: Control update intervals, debug settings
- **[AUDIO]**: Audio input/output device selection
- **[HAMLIB]**: Radio model, serial port, communication parameters
- **[PANADAPTER]**: RTL-SDR settings, FFT parameters

#### 3.5.2 Web-based Configuration
- Built-in web interface for configuration management
- Device enumeration for audio and serial ports
- Real-time configuration updates with server restart

## 4. Communication Protocols

### 4.1 WebSocket Communication

The system uses multiple WebSocket connections for different purposes:

1. **Audio RX**: Continuous stream of received audio data
2. **Audio TX**: Transmission of microphone audio data
3. **Control TRX**: Radio control commands and status updates
4. **Panadapter FFT**: FFT data for spectrum display

### 4.2 Message Format

Control messages use a simple "action:data" format:
- `setFreq:14250000` - Set frequency to 14.250 MHz
- `getMode` - Request current mode
- `setPTT:true` - Enable transmit

### 4.3 Audio Streaming

Audio is streamed in real-time with the following characteristics:
- Sample rate: Configurable (typically 8kHz for voice)
- Format: 16-bit PCM or Opus-encoded
- Buffer size: Optimized for low latency
- Direction: Bidirectional (RX and TX)

## 5. Security Considerations

### 5.1 Authentication
- Optional authentication via FILE or PAM
- User database management
- Secure cookie handling

### 5.2 Encryption
- SSL/TLS encryption for all communications
- Certificate-based authentication
- Secure WebSocket connections (WSS)

## 6. Cross-Platform Support

### 6.1 Audio Backend
- **PyAudio**: Primary cross-platform audio interface
- **ALSA**: Linux fallback implementation

### 6.2 Radio Control
- **Hamlib ctypes wrapper**: Primary implementation
- Native Hamlib bindings: Alternative implementation

### 6.3 Platform Detection
- Automatic platform detection
- Backend selection based on availability
- Graceful degradation when components are missing

## 7. Performance Characteristics

### 7.1 Latency
- Audio: <50ms end-to-end latency
- Control: <100ms response time
- PTT: <50ms activation time with 100% reliability

### 7.2 Scalability
- Single radio per server instance
- Multiple browser clients possible
- Memory usage: <100MB under normal operation

### 7.3 Resource Usage
- CPU: 5-15% on typical hardware
- Memory: 50-100MB
- Network: 16-64 kbps for audio streaming

## 8. Deployment

### 8.1 Direct Execution
```bash
./UHRR
```

### 8.2 Docker Deployment
```bash
docker-compose up --build
```

### 8.3 System Requirements
- Python 3.7+
- Tornado web framework
- Hamlib for radio control
- PyAudio or ALSA for audio
- NumPy for signal processing
- RTL-SDR support (optional, for panadapter)

## 9. Future Enhancements

### 9.1 Planned Features
- Multi-radio support
- Advanced digital mode integration
- Remote configuration management
- Mobile-optimized interface
- Recording and playback functionality

### 9.2 Technical Improvements
- Enhanced error handling and recovery
- Improved audio quality algorithms
- Better cross-platform support
- Enhanced security features
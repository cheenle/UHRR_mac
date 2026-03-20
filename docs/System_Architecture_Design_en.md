# Mobile Remote Radio Control (MRRC) System Architecture Design Document

## Document Information
- **Version**: v4.9.1 (2026-03-15)
- **Author**: System Architecture Team
- **Status**: Production Ready
- **Classification**: Confidential/Internal

---

## 1. System Overview

### 1.1 System Positioning
**Mobile Remote Radio Control (MRRC)** is a mobile-first amateur radio remote control system designed with the "Mobile First, Radio Anywhere" philosophy, enabling amateur radio enthusiasts to remotely control radio equipment from anywhere using mobile devices or desktop browsers.

**Amateur Radio, Anytime, Anywhere.**

### 1.2 Core Values
- **📱 Mobile First**: Optimized for touch screens, supports one-handed operation, PWA offline access
- **🌍 Anywhere**: Control your station from anywhere with internet access
- **⚡ Ultra Low Latency**: TX/RX switching <100ms, PTT reliability 99%+
- **🔒 Secure Connection**: TLS encrypted transmission, user authentication protection
- **🎛️ Complete Control**: Full radio control including frequency, mode, PTT, antenna tuner
- **📊 Power Monitoring**: ATR-1000 integration, real-time power and SWR display
- **🎵 Audio Optimization**: TX equalizer, shortwave voice enhancement
- **💾 Tuner Storage**: Frequency-parameter intelligent matching
- **🔇 WDSP Noise Reduction**: Professional-grade NR2 spectral noise reduction, clearer SSB voice
- **🎙️ AI Voice Assistant**: Whisper speech recognition + Qwen3-TTS voice synthesis
- **📡 CW Real-time Decoding**: ONNX frontend inference, QSO state machine intelligent suggestions
- **🖥️ Multi-Instance Support**: Single server multiple radios independent control, differentiated tuner

### 1.3 System Scope
- Support for mainstream amateur radio equipment (via Hamlib rigctld)
- Mobile-first Web browser interface
- Real-time audio encoding/decoding and transmission
- TLS secure transmission
- User authentication and session management
- Spectrum display and monitoring
- ATR-1000 power meter/tuner integration
- TX transmit audio equalizer
- Intelligent tuner parameter storage
- AI voice assistant service (Whisper + Qwen3-TTS)
- CW real-time decoding (ONNX frontend inference)
- SDR modern control interface
- Multi-instance independent deployment support

---

## 2. Requirements Analysis

### 2.1 Business Requirements Analysis

#### 2.1.1 Business Background
Amateur radio enthusiasts face QRM interference and space limitations in urban environments, requiring remote operation solutions. Factors like the COVID-19 pandemic have increased demand for remote communication tools.

#### 2.1.2 Target Users
- Amateur radio enthusiasts (Ham Radio Operators)
- Radio clubs and organizations
- Users with remote operation needs
- Educational and training institutions

#### 2.1.3 Core Business Scenarios
1. **Remote Voice Communication**: Users conduct remote QSOs through browser
2. **Radio Parameter Control**: Remote adjustment of frequency, mode, power and other parameters
3. **Spectrum Monitoring**: Real-time view of radio spectrum and signal strength
4. **Multi-point Operation**: Support multiple clients simultaneously monitoring/controlling
5. **Power Monitoring**: Real-time display of transmit power and SWR

### 2.2 Functional Requirements Specification

#### 2.2.1 Radio Control Functions
- **Frequency Control**: Set and read radio operating frequency (VFO A/B support)
- **Mode Control**: USB/LSB/CW/AM/FM mode switching
- **Power Control**: Read and set transmit power
- **PTT Control**: Push-to-Talk button control
- **S-meter Reading**: Signal strength indication

#### 2.2.2 Audio Stream Functions
- **TX Audio**: Microphone input → Int16 encoding → WebSocket transmission → Backend decoding → Radio output
- **RX Audio**: Radio input → Backend capture → Int16 encoding → WebSocket transmission → Frontend decoding → Speaker output
- **Audio Quality**: 16kHz sample rate, Int16 format, 50% bandwidth optimization
- **Real-time**: TX/RX latency <100ms

#### 2.2.3 User Interface Functions
- **Web Interface**: HTML5-based responsive interface
- **Real-time Display**: Spectrum waterfall, FFT display, S-meter
- **Control Panel**: Frequency adjustment (optimized layout: up-add, down-subtract), mode selection, volume control
- **Status Indication**: Connection status, PTT status, audio levels
- **Power Display**: ATR-1000 real-time power/SWR

#### 2.2.4 System Management Functions
- **User Authentication**: Optional username/password authentication
- **Session Management**: Automatic timeout and cleanup
- **Configuration Management**: Web interface for system parameter configuration
- **Logging**: Operation and error logging

### 2.3 Non-Functional Requirements Specification

#### 2.3.1 Performance Requirements
- **Response Time**:
  - PTT operation response time <50ms (including confirmation and retry mechanism)
  - Audio end-to-end latency <100ms
  - Interface update frequency >20fps
  - Power display latency <200ms
- **Concurrent Capability**: Support multiple clients connecting simultaneously
- **Resource Usage**:
  - CPU usage <30% (single client)
  - Memory usage <100MB
  - Network bandwidth <100kbps (control) + 256kbps (audio)

#### 2.3.2 Reliability Requirements
- **Availability**: 99.5% (annualized)
- **Fault Recovery**: Automatic reconnection mechanism
- **Data Consistency**: Control command idempotency
- **Error Handling**: Graceful degradation and error recovery
- **PTT Reliability**: 100% immediate transmit success rate (guaranteed through warm-up frames, confirmation mechanism, and retry mechanism)

#### 2.3.3 Security Requirements
- **Transport Security**: TLS 1.2+ encrypted transmission
- **Authentication Mechanism**: Support certificate and password authentication
- **Access Control**: Role-based access control
- **Audit Logging**: Security event recording

#### 2.3.4 Scalability Requirements
- **Modular Design**: Loosely coupled component architecture
- **Protocol Extension**: Support for new radio equipment
- **Interface Extension**: Support for custom interface themes
- **Deployment Extension**: Support for multi-instance deployment

#### 2.3.5 Compatibility Requirements
- **Browser Support**: Chrome 60+, Firefox 55+, Safari 11+, Edge 79+
- **Operating Systems**: Linux, macOS, Windows
- **Mobile Devices**: iOS Safari, Android Chrome
- **Radio Equipment**: Compatible with all devices supported by Hamlib

#### 2.3.6 Maintainability Requirements
- **Code Quality**: Follow best practices, code coverage >80%
- **Documentation Completeness**: API documentation, deployment documentation, user manuals
- **Test Coverage**: Unit tests, integration tests, end-to-end tests
- **Deployment Convenience**: Docker containerization, one-click deployment support

---

## 3. System Architecture Design

### 3.1 System Architecture Diagram

```
                              ┌─────────────────────────────────────┐
                              │         Web Browser Client          │
                              │                                     │
                              │  ┌─────────────┐  ┌─────────────┐   │
                              │  │   UI Layer  │  │  Audio      │   │
                              │  │             │  │  Processing │   │
                              │  │ • Control   │  │ • Int16     │   │
                              │  │   Panel     │  │   Encoder   │   │
                              │  │ • Spectrum  │  │ • TX EQ     │   │
                              │  │   Display   │  │ • Real-time │   │
                              │  │ • Status    │  │   Transfer  │   │
                              │  │ • Power/    │  │ • Buffer    │   │
                              │  │   SWR       │  │   Management│   │
                              │  └─────────────┘  └─────────────┘   │
                              │                                     │
                              │  ┌─────────────┐  ┌─────────────┐   │
                              │  │WebSocket    │  │AudioWorklet │   │
                              │  │ Client      │  │  Player     │   │
                              │  │ • Control   │  │ • Low       │   │
                              │  │   Channel   │  │   Jitter    │   │
                              │  │ • Audio TX  │  │ • Zone      │   │
                              │  │ • Audio RX  │  │   Buffering │   │
                              │  │ • ATR-1000  │  │ • Pop       │   │
                              │  │             │  │   Prevention│   │
                              │  └─────────────┘  └─────────────┘   │
                              └─────────────────┬───────────────────┘
                                                │
                              ┌─────────────────┼───────────────────┐
                              │                 ▼                   │
                              │         HTTP/HTTPS + WebSocket      │
                              │              (TLS 1.2+)             │
                              │                                     │
                              └─────────────────┼───────────────────┘
                                                │
                              ┌─────────────────┼───────────────────┐
                              │                 ▼                   │
                              │       Server Side (Tornado)         │
                              │                                     │
                              │  ┌─────────────┐  ┌─────────────┐   │
                              │  │  Web Layer  │  │ Business    │   │
                              │  │             │  │ Logic       │   │
                              │  │ • Static    │  │ • WebSocket │   │
                              │  │   Files     │  │ • Routing   │   │
                              │  │ • Config    │  │ • Session   │   │
                              │  │   Interface │  │   Management│   │
                              │  └─────────────┘  └─────────────┘   │
                              │                                     │
                              │  ┌─────────────┐  ┌─────────────┐   │
                              │  │ Audio       │  │  Device     │   │
                              │  │ Service     │  │  Control    │   │
                              │  │             │  │             │   │
                              │  │ • PyAudio   │  │ • rigctld   │   │
                              │  │ • Int16     │  │ • Hamlib    │   │
                              │  │   Decode    │  │ • PTT       │   │
                              │  │ • Real-time │  │   Control   │   │
                              │  │   Capture   │  │             │   │
                              │  └─────────────┘  └─────────────┘   │
                              │                                     │
                              │  ┌─────────────┐  ┌─────────────┐   │
                              │  │ ATR-1000    │  │  Data       │   │
                              │  │  Bridge     │  │  Storage    │   │
                              │  │             │  │             │   │
                              │  │ • Unix      │  │ • Cert      │   │
                              │  │   Domain    │  │   Files     │   │
                              │  │ • Real-time │  │ • Config    │   │
                              │  │   Forward   │  │   Database  │   │
                              │  │             │  │ • Tuner     │   │
                              │  │             │  │   Storage   │   │
                              │  └─────────────┘  └─────────────┘   │
                              └─────────────────┬───────────────────┘
                                                │
                              ┌─────────────────┼───────────────────┐
                              │                 ▼                   │
                              │           External Systems & Devices│
                              │                                     │
                              │  ┌─────────────┐  ┌─────────────┐   │
                              │  │ Radio Device│  │ Audio Device│   │
                              │  │             │  │             │   │
                              │  │• Frequency  │  │ • Microphone│   │
                              │  │   Control   │  │ • Speaker   │   │
                              │  │• Mode       │  │ • Soundcard │   │
                              │  │   Switch    │  │   Interface │   │
                              │  │• PTT        │  │ • Real-time │   │
                              │  │   Operation │  │   Capture   │   │
                              │  │• S-meter    │  │             │   │
                              │  │   Read      │  │             │   │
                              │  └─────────────┘  └─────────────┘   │
                              │                                     │
                              │  ┌─────────────┐  ┌─────────────┐   │
                              │  │   rigctld   │  │ATR-1000    │   │
                              │  │             │  │  Proxy      │   │
                              │  │ • Device    │  │             │   │
                              │  │   Abstraction│ │ • Power    │   │
                              │  │ • Command   │  │   Monitor   │   │
                              │  │   Protocol  │  │ • SWR       │   │
                              │  │ • TCP       │  │   Display   │   │
                              │  │   Service   │  │ • Tuner     │   │
                              │  │             │  │   Control   │   │
                              │  └─────────────┘  └─────────────┘   │
                              └─────────────────────────────────────┘
```

### 3.2 Data Flow Diagram

```
Audio TX Flow:
Microphone → Web Audio API → TX Equalizer → Int16 Encoding → WebSocket(TX) → Server Decode → PyAudio → Radio

Audio RX Flow:
Radio → PyAudio Capture → WebSocket(RX) → Browser Decode → AudioWorklet → Speaker

Control Flow:
User Operation → WebSocket(Control) → Server → rigctld → Radio Device

Spectrum Flow:
Radio → rigctld → Server → WebSocket(Spectrum) → Browser FFT Display

ATR-1000 Power Flow:
ATR-1000 Device → Independent Proxy (atr1000_proxy.py) → Unix Socket → MRRC Bridge → WebSocket(/WSATR1000) → Mobile Display

Tuner Storage Flow:
Frequency Change → Lookup Tuner Parameters → atr1000_tuner.json → Load Parameters → ATR-1000 Device
```

### 3.3 Deployment Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                   Single Machine Deployment                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │ Web Browser │◄──►│ MRRC Server │◄──►│  rigctld    │        │
│  │ (Multiple   │    │  (Tornado)  │    │  (Hamlib)   │        │
│  │  Clients)   │    └─────────────┘    └─────────────┘        │
│  └─────────────┘          │                                    │
│         │                  ▼                                    │
│         │           ┌─────────────┐                            │
│         │           │ATR-1000 Proxy│                            │
│         │           │(Independent  │                            │
│         │           │  Process)    │                            │
│         │           └─────────────┘                            │
│         │                  │                                    │
│         │                  ▼                                    │
│         │           ┌─────────────┐                            │
│         │           │ATR-1000 Device│                          │
│         │           └─────────────┘                            │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────┐    ┌─────────────┐                            │
│  │ Audio Device│    │  Radio Device│                           │
│  │ (Microphone/│    │   (Serial/   │                           │
│  │   Speaker)   │    │    USB)      │                           │
│  └─────────────┘    └─────────────┘                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   Containerized Deployment                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │   Nginx     │◄──►│ Docker      │◄──►│  rigctld    │       │
│  │  (Reverse   │    │  Container  │    │  Container  │       │
│  │   Proxy)    │    │   (MRRC)    │    │  (Optional) │       │
│  └─────────────┘    └─────────────┘    └─────────────┘       │
│                           │                    │                │
│                           ▼                    ▼                │
│                       ┌─────────────┐    ┌─────────────┐       │
│                       │  Host Audio │    │   Host      │       │
│                       │  Device     │    │   Radio     │       │
│                       │  Mapping    │    │   Device    │       │
│                       │             │    │   Mapping   │       │
│                       └─────────────┘    └─────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

### 3.4 Architecture Design Principles

#### 3.4.1 Layered Architecture
- **Presentation Layer**: Web browser interface, responsible for user interaction and data display
- **Application Layer**: Tornado WebSocket server, handles business logic
- **Service Layer**: Core services like audio processing, device control
- **Data Access Layer**: Radio device interface, file system access

#### 3.4.2 Component-Based Design
- **High Cohesion**: Each component has single responsibility, complete internal logic
- **Low Coupling**: Components communicate through standard interfaces, easy to replace and test
- **Extensibility**: Supports dynamic loading and configuration-driven component extension

#### 3.4.3 Asynchronous Event-Driven
- **Event-Driven**: Based on Tornado async framework, supports high concurrency
- **Non-blocking I/O**: Audio processing and network communication use async mode
- **Reactive Design**: Interface responds to state changes in real-time

---

## 4. Component Design

### 4.1 Frontend Components

#### 4.1.1 UI Components (`www/`)
- **Responsibility**: Provide user interface and interaction logic
- **Tech Stack**: HTML5, CSS3, Vanilla JavaScript
- **Key Files**:
  - `mobile_modern.html`: Mobile main interface (recommended)
  - `index.html`: Desktop main interface
  - `controls.js`: Core control logic and audio processing
  - `tx_button_optimized.js`: PTT button optimization logic
  - `rx_worklet_processor.js`: AudioWorklet audio player
  - `mobile_modern.js`: Mobile interface logic
  - `mobile_modern.css`: Mobile interface styles

#### 4.1.2 Audio Processing Components
- **TX Equalizer**: Three-band audio equalizer
  - Low frequency boost: lowshelf @ 200Hz
  - Mid frequency enhancement: peaking @ 1000Hz
  - High frequency attenuation: highshelf @ 2500Hz
  - Presets: Default, HF Voice, DX Weak, Contest
- **Int16 Encoder**: TX audio encoding
  - Sample rate: 16kHz
  - Encoding format: Int16 PCM (50% bandwidth optimization)
  - Gain control: 1:1 input gain, supports soft limiting
- **RxPlayerProcessor**: RX audio decoding and playback
  - Playback technology: AudioWorkletNode
  - Buffer management: 16/32 frame zone control
  - Jitter suppression: Truncate when too deep, zero-fill when too shallow

#### 4.1.3 ATR-1000 Client Module (`mobile_modern.js`)
- **Connection Management**: Pre-connect on page load, maintain warm state
- **Data Reception**: Real-time update of power, SWR, relay status
- **Tuner Storage**: Automatic frequency-parameter matching and saving
- **Display Update**: Real-time power bar, SWR indicator
- **Dual Time Protection**: Ensure sync request minimum interval 500ms

#### 4.1.4 WebSocket Client
- **Connection Management**: Automatic reconnection and status monitoring
- **Message Routing**: Control, audio TX, audio RX, spectrum data, ATR-1000 separated processing
- **Error Handling**: Graceful degradation when connection is lost

### 4.2 Backend Components

#### 4.2.1 Web Server (`MRRC`)
- **Framework**: Tornado Web Framework
- **Concurrency Model**: Async I/O, supports thousands of concurrent connections
- **Routing Configuration**: Static files, WebSocket, configuration interface
- **Security**: SSLContext certificate chain loading

#### 4.2.2 Audio Processing Engine (`audio_interface.py`)
- **Capture Module**: PyAudioCapture (input device abstraction)
- **Playback Module**: PyAudioPlayback (output device abstraction)
- **Buffer Management**: Ring buffer, prevents memory leaks
- **Device Enumeration**: Supports multiple audio device selection

#### 4.2.3 Radio Control Interface (`hamlib_wrapper.py`)
- **Protocol**: Hamlib rigctld TCP protocol
- **Command Encapsulation**: Frequency, mode, PTT and other operations
- **Error Handling**: Automatic retry on connection loss
- **Status Synchronization**: Real-time status update and broadcast

#### 4.2.4 ATR-1000 Bridge (`MRRC`)
- **WebSocket Endpoint**: `/WSATR1000`
- **Unix Socket Client**: Connect to independent proxy program
- **Thread Safety**: IOLoop.add_callback() cross-thread communication
- **Batch Broadcast**: 50ms batch collection, broadcast latest data
- **Real-time Forwarding**: Power, SWR, relay status data

#### 4.2.5 ATR-1000 Independent Proxy (`atr1000_proxy.py`)
- **WebSocket Server**: Connect to ATR-1000 device
- **Unix Socket Server**: Accept MRRC connections
- **Protocol Parsing**: SCMD_METER_STATUS, SCMD_RELAY_STATUS
- **SYNC Mechanism**: 500ms during TX, 2s idle for warm-up
- **Auto Reconnect**: Auto-reconnect after device disconnection

#### 4.2.6 Tuner Storage Module (`atr1000_tuner.py`)
- **JSON Persistence**: Frequency-LC/CL parameter storage
- **Intelligent Matching**: Find closest frequency parameters (±50kHz tolerance)
- **Auto Save**: Auto-record after successful tuner adjustment

### 4.3 External System Integration

#### 4.3.1 rigctld (Hamlib)
- **Interface**: TCP port 4532
- **Command Format**: Standard Hamlib command set
- **Device Support**: 300+ amateur radio equipment

#### 4.3.2 ATR-1000 Power Meter/Tuner
- **Interface**: WebSocket (default 192.168.1.63:60001)
- **Protocol**: Binary protocol, SCMD command set
- **Data Types**: Power (0-200W), SWR (1.0-9.99), relay status
- **Control Functions**: TUNE tuner start, parameter reading

#### 4.3.3 Audio Devices
- **Input Devices**: Microphone, line input
- **Output Devices**: Speaker, line output
- **Sample Rate**: 16kHz (matching frontend)

#### 4.3.4 File System
- **Certificate Storage**: `certs/` directory
- **Configuration Storage**: `MRRC.conf`
- **Tuner Storage**: `atr1000_tuner.json`
- **Log Storage**: Log file directory

---

## 5. Interface and Protocol Definitions

### 5.1 WebSocket Message Protocol

#### 5.1.1 Control Channel (WSCTRX)
```
Message Format: <action>:<data>

Send to Server:
- setFreq:<frequency>     # Set frequency
- setMode:<mode>          # Set mode (USB/LSB/CW/AM/FM)
- setPTT:<state>          # PTT control (true/false)
- getFreq                 # Query frequency
- getMode                 # Query mode
- PING                    # Heartbeat

Server Response:
- getFreq:<frequency>     # Frequency query response
- getMode:<mode>          # Mode query response
- getPTT:<state>          # PTT status
- getSignalLevel:<level>  # S-meter value
- PONG                    # Heartbeat response
```

#### 5.1.2 Audio TX Channel (WSaudioTX)
```
Message Format: <type>:<data>

Client to Server:
- m:<rate,encode,op_rate,frame_dur>  # TX initialization parameters
- s:                                 # Stop TX
- <binary_audio_data>               # Int16 encoded audio data

Server Processing:
- Decode and output to radio audio device
- PTT timeout protection (counting method: turn off PTT after 10 consecutive failures × 200ms without receiving audio frames)
```

#### 5.1.3 Audio RX Channel (WSaudioRX)
```
Server to Client:
- <binary_audio_data>    # Int16 PCM audio data

Client Processing:
- Receive and cache to AudioBuffer
- AudioWorklet real-time playback
- Buffer depth control and jitter suppression
```

#### 5.1.4 Spectrum Channel (WSpanFFT)
```
Server to Client:
- <binary_fft_data>      # FFT spectrum data

Client Processing:
- Render waterfall and FFT display
- Real-time spectrum visualization update
```

#### 5.1.5 ATR-1000 Power Monitor Channel (WSATR1000)
```
Client to Server:
- {"action": "start"}    # Start data stream (send when TX starts)
- {"action": "stop"}     # Stop data stream (send when TX ends)

Server to Client:
- {"type": "atr1000_meter", "power": 100, "swr": 1.25, "vforward": 70.7, "vreflected": 7.07, "relay_status": {"lc": "LC", "inductance": 5, "capacitance": 3}}

Data Format Description:
- power: Forward power (watts, 0-200W)
- swr: Standing wave ratio (unitless, 1.0-9.99)
- vforward: Forward voltage
- vreflected: Reflected voltage
- relay_status: Relay status
  - lc: LC or CL combination
  - inductance: Inductance value
  - capacitance: Capacitance value

Connection Characteristics:
- Pre-establish connection on page load
- Maintain connection after TX ends (warm state)
- SYNC warm-up: Send every 2s when client connected
- During TX: Send SYNC every 500ms to ensure data stream
- Dual time protection: Ensure sync minimum interval 500ms

Client Processing:
- Real-time display of power and SWR data
- Update display color based on SWR value (green <1.5, yellow <2.0, red >2.0)
- Intelligent tuner parameter storage and matching
```

### 5.2 Audio Data Format

#### 5.2.1 TX Audio Format
- **Sample Rate**: 16kHz
- **Format**: Int16 PCM (-32768 to 32767)
- **Channels**: Mono
- **Transmission**: WebSocket binary transmission

#### 5.2.2 RX Audio Format
- **Sample Rate**: 16kHz (browser native)
- **Format**: Int16 PCM (converted to Float32 for playback)
- **Buffer**: AudioWorklet internal buffer management

#### 5.2.3 Audio Optimization Parameters
- **Sample Rate**: 16kHz (voice communication golden standard)
- **Data Format**: Int16 (50% bandwidth reduction)
- **Bitrate**: 256 kbps
- **Channels**: Mono

### 5.3 Control Command Format

#### 5.3.1 rigctld Commands
```
Standard Hamlib Commands:
F <frequency>           # Set frequency
f                       # Query frequency
M <mode> <passband>     # Set mode
m                       # Query mode
T 1/0                   # PTT control
l                       # Query signal strength
```

---

## 6. Deployment Architecture

### 6.1 Single Machine Deployment Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │◄──►│  MRRC Server    │◄──►│   rigctld       │
│                 │    │   (Tornado)     │    │   (Hamlib)      │
│ - HTML5 UI      │    │ - WebSocket     │    │ - Device        │
│ - Audio Codec   │    │ - Audio         │    │   Abstraction   │
│ - Real-time     │    │   Processing    │    │ - Command       │
│   Display       │    │ - TLS Security  │    │   Protocol      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Audio Device  │    │  Radio Device   │
                       │   (Microphone/  │    │   (Serial/      │
                       │    Speaker)      │    │    USB)         │
                       └─────────────────┘    └─────────────────┘
```

### 6.2 Containerized Deployment
- **Docker Image**: Contains all dependencies
- **Environment Variables**: Port, device path and other configurations
- **Persistence**: Certificate, configuration, log directory mounting

### 6.3 High Availability Deployment
- **Multi-Instance**: Load balancer distributes WebSocket connections
- **State Synchronization**: Redis cluster synchronizes session state
- **Failover**: Automatic detection and switching

---

## 7. Security Design

### 7.1 Transport Security
- **TLS Version**: TLS 1.2+ (mandatory)
- **Certificate Type**: X.509 server certificate
- **Certificate Chain**: Server certificate + intermediate certificate (excluding root)
- **Private Key Protection**: 600 permissions, root readable only

### 7.2 Authentication and Authorization
- **User Authentication**: Optional username/password authentication
- **Session Management**: Cookie-based session tracking
- **Access Control**: Role-based permission control
- **Audit Logging**: Authentication and operation logging

### 7.3 Input Validation
- **Command Validation**: All control command parameter validation
- **Audio Data**: Length and format checking
- **XSS Protection**: Content escaping and CSP policy

---

## 8. Performance Optimization Strategies

### 8.1 Real-time Optimization
- **Audio Latency**: <100ms end-to-end latency
- **Control Response**: PTT <50ms response time
- **Power Display**: <200ms latency
- **Buffer Strategy**: Audio buffer zone control, prevent jitter

### 8.2 Resource Optimization
- **Memory Management**: Audio buffer auto-cleanup, prevent memory leaks
- **CPU Optimization**: Async processing, reduce blocking operations
- **Network Optimization**: WebSocket compression, batch data transmission

### 8.3 Scalability Optimization
- **Component Decoupling**: Modular design, support dynamic extension
- **Configuration Driven**: Parameters adjustable via configuration file
- **Monitoring Metrics**: Performance metric collection and alerting

---

## 9. Quality Attribute Analysis

### 9.1 Reliability Analysis
- **Failure Modes**: Single point of failure, network interruption, device failure
- **Recovery Mechanisms**: Auto-reconnection, graceful degradation, state synchronization
- **Redundant Design**: Multi-client support, single point failure doesn't affect other users

### 9.2 Performance Analysis
- **Load Testing**: Support multi-client concurrency
- **Stress Testing**: Audio stream duration and concurrency
- **Benchmark Testing**: Latency, throughput, resource usage benchmarks

### 9.3 Security Analysis
- **Threat Modeling**: Identify potential attack vectors
- **Security Testing**: Penetration testing and vulnerability scanning
- **Compliance**: Compliance with relevant security standards

---

## 10. Technology Selection Rationale

### 10.1 Frontend Technology Stack
- **HTML5/CSS3/JavaScript**: Cross-platform compatibility, Web standards
- **Web Audio API**: Low-latency audio processing
- **AudioWorklet**: Audio thread processing, avoid main thread jitter
- **WebSocket**: Full-duplex real-time communication

### 10.2 Backend Technology Stack
- **Tornado**: High-performance async Web framework
- **PyAudio**: Cross-platform audio processing
- **Hamlib**: Standard amateur radio control library
- **SSLContext**: Standard TLS implementation

### 10.3 Deployment Technology Stack
- **Docker**: Containerized deployment
- **Linux**: Server operating system
- **Nginx**: Reverse proxy and load balancing

---

## 11. Risk Analysis and Mitigation

### 11.1 Technical Risks
- **Browser Compatibility**: Mitigation: Progressive enhancement, provide fallback solutions
- **Audio Latency**: Mitigation: Optimize buffer strategy, use AudioWorklet
- **Radio Compatibility**: Mitigation: Based on standard Hamlib, support device extension

### 11.2 Performance Risks
- **High Concurrency**: Mitigation: Async architecture, resource pooling
- **Memory Leaks**: Mitigation: Auto buffer cleanup, monitoring alerts
- **Network Jitter**: Mitigation: Buffer zone control, counting timeout mechanism

### 11.3 Security Risks
- **Certificate Configuration Error**: Mitigation: Automated verification scripts
- **Unauthorized Access**: Mitigation: Authentication and authorization mechanisms
- **Data Leakage**: Mitigation: TLS encryption, log anonymization

---

## 12. Maintenance and Monitoring

### 12.1 Monitoring Metrics
- **System Metrics**: CPU, memory, network I/O
- **Business Metrics**: Connection count, audio stream status, PTT success rate
- **Error Metrics**: Exception rate, timeout rate, failure rate
- **ATR-1000 Metrics**: Power, SWR, connection status

### 12.2 Log Management
- **Log Levels**: DEBUG, INFO, WARN, ERROR
- **Log Rotation**: Rotate by size and time
- **Log Analysis**: Structured logs, easy analysis

### 12.3 Deployment and Operations
- **Health Check**: Regular service status checks
- **Backup Strategy**: Configuration file and certificate backup
- **Upgrade Strategy**: Rolling upgrade, zero downtime

---

## 13. Future Evolution Roadmap

### 13.1 Short-term Optimization (1-3 months)
- Improve mobile adaptation
- Add audio quality setting options
- Optimize WebRTC audio transmission

### 13.2 Medium-term Extension (3-6 months)
- Support multiple radio devices
- Add CW mode support
- Implement cluster deployment

### 13.3 Long-term Vision (6+ months)
- Integrate SDR device support
- Implement distributed audio processing
- Develop mobile applications

---

## 14. License and Compliance Statements

### 14.1 License Information

This project is released under the **GNU General Public License v3.0 (GPL-3.0)**.

```
Mobile Remote Radio Control (MRRC) - Mobile Amateur Radio Remote Control System
Copyright (C) 2025-2026 MRRC Contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
```

### 14.2 Project Source Declaration

This project is developed and improved based on the following open source project:

**Original Project**: [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5)
- Author: Olivier Schmitt (F4HTB)
- License: GPL-3.0
- Description: Original HTML5 amateur radio remote control interface

**Major Improvements**:
- Stability optimization: Fixed PTT timing issues, improved audio stream processing
- Architecture upgrade: Introduced AudioWorklet, optimized WebSocket communication
- Feature enhancement: ATR-1000 integration, TX equalizer, tuner storage
- Platform adaptation: Optimized macOS compatibility, improved mobile support

### 14.3 Compliance Requirements

According to GPL-3.0 license requirements:

#### 14.3.1 Modification Declaration
This project makes the following major modifications to the original code:
- Refactored frontend audio processing logic (introduced AudioWorklet)
- Optimized backend PTT timeout mechanism (counting method instead of time threshold)
- Improved TLS certificate chain processing
- Added ATR-1000 power meter integration
- Added TX audio equalizer
- Added tuner parameter storage function

#### 14.3.2 Distribution Requirements
- **Source Code**: Complete source code must be provided
- **Modification Marking**: Modifications must be clearly marked
- **License**: Must include GPL-3.0 license text
- **Copyright Notice**: Must retain original copyright notice

#### 14.3.3 Usage Restrictions
- **Amateur Radio**: For amateur radio purposes only, comply with local laws and regulations
- **Remote Operation**: For legitimate remote radio operation only
- **Commercial Use**: Follow GPL-3.0 commercial use terms

### 14.4 Disclaimer

**Important Legal Notice**:
- This software is provided for amateur radio enthusiasts' learning and experimental use only
- Users must ensure compliance with radio management regulations in their country/region
- Authors are not responsible for any illegal use
- It is recommended to use within legitimate amateur radio frequency ranges

**Technical Disclaimer**:
- This software is provided "as is" without any express or implied warranties
- There may be technical risks during use, users bear the risk themselves
- It is recommended to verify functionality in test environment before actual operation

### 14.5 Contribution Guidelines

Community contributions are welcome, but please note:
- All contributions must follow GPL-3.0 license
- Contributed code must include appropriate copyright notices
- Major modifications should update version history and changelog
- Pull Requests via GitHub are recommended

---

## 15. Glossary

### 15.1 Radio Terminology
- **PTT**: Push-To-Talk
- **QSO**: Amateur Radio Communication
- **VFO**: Variable Frequency Oscillator
- **S-meter**: Signal Strength indicator
- **SWR**: Standing Wave Ratio
- **Hamlib**: Amateur Radio Equipment Control Library
- **rigctld**: Hamlib TCP server

### 15.2 Technical Terminology
- **WebSocket**: Full-duplex communication protocol
- **AudioWorklet**: Web Audio API audio work thread
- **Opus**: Audio codec
- **TLS**: Transport Layer Security
- **Tornado**: Python async Web framework

---

## 16. References

### 16.1 Technical Documentation
- **Hamlib Documentation**: https://hamlib.github.io/
- **Web Audio API Specification**: https://webaudio.github.io/web-audio-api/
- **Tornado Documentation**: https://www.tornadoweb.org/
- **RFC 6455**: WebSocket Protocol
- **RFC 5246**: TLS 1.2 Protocol

### 16.2 Open Source Projects
- **Upstream Project**: [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5)
- **Opus Codec**: https://opus-codec.org/
- **PyAudio**: https://people.csail.mit.edu/hubert/pyaudio/

---

## 17. Version History

| Version | Date | Major Changes | Status |
|---------|------|---------------|--------|
| v1.0.0 | 2024-12 | Initial version, based on F4HTB project | Released |
| v2.0.0 | 2025-01 | Stability optimization, TLS support, AudioWorklet | Production Ready |
| v3.0.0 | 2025-01 | Mobile optimization, AAC encoding, TCI protocol | Production Ready |
| v4.0.0 | 2026-03 | TX→RX delay optimization, architecture simplification, V4 milestone | Production Ready |
| v4.1.0 | 2026-03 | Project renamed MRRC, bilingual documentation | Production Ready |
| v4.2.0 | 2026-03 | TX EQ equalizer, shortwave voice optimization | Production Ready |
| v4.3.0 | 2026-03 | ATR-1000 architecture separation, independent proxy | Production Ready |
| v4.4.0 | 2026-03-05 | ATR-1000 real-time display major fix | Production Ready |
| v4.9.1 | 2026-03-15 | Multi-instance support deep optimization | Current Version |
| v4.9.0 | 2026-03-14 | Voice assistant, CW mode, SDR interface | Production Ready |
| v4.5.4 | 2026-03-06 | ATR-1000 real-time power display stable version | Historical Version |
| v4.5.4 | 2026-03-06 | Frequency adjustment button layout optimization | Current Version |

---

**End of Document**

*This architecture design document is released under the GPL-3.0 license, see LICENSE file for details.*

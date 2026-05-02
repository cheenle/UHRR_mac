# 8. Architecture Decisions (ART 0513)

## 8.1 Technical Selection Decisions

### AD-001: Web Framework Selection

| Attribute | Value |
|-----------|-------|
| Decision ID | AD-001 |
| Type | Architectural |
| Topic | Web framework selection |
| Decision | Adopt Tornado as backend web framework |

**Problem**: Need a Python async web framework with native WebSocket support for real-time audio streaming.

**Alternatives**:
- A1: Flask + SocketIO - Synchronous framework, lower performance
- A2: Django Channels - Too heavyweight, complex deployment
- A3: FastAPI - Emerging framework, ecosystem still maturing

**Rationale**:
- Tornado has native WebSocket support
- Mature and stable, active community
- Compatible with PyAudio event loop
- Single-threaded async model matches audio streaming pattern

**Impact**:
- Must use Tornado's IOLoop for async processing
- Requires special handling when integrating with PyAudio's blocking I/O

---

### AD-002: Audio Codec Selection

| Attribute | Value |
|-----------|-------|
| Decision ID | AD-002 |
| Type | Architectural |
| Topic | Audio codec selection |
| Decision | Int16 PCM as primary codec, Opus as optional |

**Problem**: Need a low-latency, high-quality audio codec for real-time radio communication.

**Alternatives**:
- A1: AAC - Higher latency, patent licensing issues
- A2: MP3 - High latency, unsuitable for real-time
- A3: Opus - Low latency (20ms frame), high quality, native browser support

**Rationale**:
- Opus is the WebRTC standard, natively supported by browsers
- Low latency (20ms frame length)
- High compression ratio (20kbps at 16kHz for SSB audio)
- Int16 PCM provides compatibility fallback

**Impact**:
- TX side uses Opus encoding
- RX side must support multiple decode formats (Int16/Float32/Opus)

---

### AD-003: DSP Noise Reduction

| Attribute | Value |
|-----------|-------|
| Decision ID | AD-003 |
| Type | Architectural |
| Topic | DSP noise reduction selection |
| Decision | Integrate WDSP library, use NR2 spectral noise reduction |

**Problem**: Need professional-grade noise reduction specifically optimized for SSB voice communication.

**Alternatives**:
- A1: RNNoise - General-purpose neural network noise reduction, mediocre for SSB
- A2: WebAudio filters - Limited effectiveness
- A3: WDSP NR2 - Specifically optimized for SSB by OpenHPSDR

**Rationale**:
- WDSP is a professional DSP library from OpenHPSDR project
- NR2 spectral noise reduction specifically optimized for SSB
- 15-20dB noise reduction depth with high voice fidelity
- Additional modules: NB (noise blanker), ANF (auto notch), AGC

**Impact**:
- Must install WDSP library (libwdsp)
- Requires 48kHz sample rate processing
- Adds computational overhead (~20ms processing latency)

---

### AD-004: Multi-Instance Architecture

| Attribute | Value |
|-----------|-------|
| Decision ID | AD-004 |
| Type | Architectural |
| Topic | Multi-instance support |
| Decision | Independent configuration files + Unix Socket isolation |

**Problem**: Need to support running multiple MRRC instances on a single server for multiple radios.

**Alternatives**:
- A1: Docker container isolation - Additional learning overhead
- A2: Port-based differentiation - Audio device sharing issues
- A3: Configuration file + Unix Socket isolation

**Rationale**:
- Independent configuration files per instance
- Unix Socket isolation avoids port conflicts
- Minimal code changes, reuses existing architecture

**Impact**:
- Each instance requires separate configuration file
- Each instance uses independent Unix Socket path for ATR-1000 proxy

---

### AD-005: PTT Reliability Mechanism

| Attribute | Value |
|-----------|-------|
| Decision ID | AD-005 |
| Type | Management |
| Topic | PTT reliability mechanism |
| Decision | Warm-up frame + retry mechanism |

**Problem**: PTT switching gaps cause audio dropout at the beginning of transmission.

**Alternatives**:
- A1: Direct PTT switching - Gap at TX start
- A2: Pre-buffered audio - Complex synchronization
- A3: Warm-up frames sent before actual audio

**Rationale**:
- Warm-up frames fill the switching gap
- Retry mechanism ensures PTT command delivery
- Simple implementation, high effectiveness

**Impact**:
- Adds ~50ms latency to PTT activation (acceptable)
- Improves PTT reliability to 99%+

---

### AD-006: Audio Buffer Strategy

| Attribute | Value |
|-----------|-------|
| Decision ID | AD-006 |
| Type | Operational |
| Topic | Audio buffer management |
| Decision | Small buffer (256 samples) with adaptive sizing |

**Problem**: Balance between latency (small buffer) and reliability (large buffer) for audio streaming.

**Alternatives**:
- A1: Fixed large buffer - Low latency but high risk of dropout
- A2: Fixed large buffer - Reliable but high latency
- A3: Adaptive buffer size based on network conditions

**Rationale**:
- 256-sample buffer at 48kHz = 5.3ms processing time
- Acceptable trade-off between latency and reliability
- AudioWorklet on client side provides additional buffering

**Impact**:
- Requires careful buffer management in both server and client
- Network jitter can cause audio gaps

---

### AD-007: CW Decoding Architecture

| Attribute | Value |
|-----------|-------|
| Decision ID | AD-007 |
| Type | Architectural |
| Topic | CW real-time decoding |
| Decision | Browser-first ONNX inference, backend PyTorch as fallback |

**Problem**: Real-time Morse code decoding with minimal server resource usage.

**Alternatives**:
- A1: Backend-only decoding - Server resource heavy
- A2: Browser-first with ONNX - Zero server cost, low latency
- A3: Cloud API - Network dependency, privacy concerns

**Rationale**:
- 2MB ONNX model runs directly in browser
- < 50ms inference latency
- Zero server-side dependencies
- Backend mode available as fallback (PyTorch + CUDA)

**Impact**:
- Frontend loads ONNX model on page load
- Requires modern browser with WebAssembly support

---

### AD-008: ATR-1000 Proxy Architecture

| Attribute | Value |
|-----------|-------|
| Decision ID | AD-008 |
| Type | Architectural |
| Topic | Antenna tuner integration |
| Decision | Independent proxy process (atr1000_proxy.py) with Unix Socket bridge |

**Problem**: ATR-1000 device connection must be exclusive. Multiple MRRC instances or third-party software cannot share a direct connection.

**Alternatives**:
- A1: Direct connection from MRRC - Single client limitation
- A2: Independent proxy with Unix Socket - Multi-client support
- A3: TCP proxy - Network overhead, security concerns

**Rationale**:
- Proxy process owns the exclusive device connection
- MRRC connects via Unix Socket (low overhead)
- Third-party software can connect via REST API
- Dynamic polling rates: idle 15s / active 5s / TX 0.5s

**Impact**:
- Additional process to manage
- Unix Socket path must be unique per instance

## 8.2 Decision Summary

| ID | Type | Topic | Status |
|----|------|-------|--------|
| AD-001 | Architectural | Tornado Web Framework | Implemented |
| AD-002 | Architectural | Int16/Opus Audio Codec | Implemented |
| AD-003 | Architectural | WDSP NR2 Noise Reduction | Implemented |
| AD-004 | Architectural | Multi-instance Deployment | Implemented |
| AD-005 | Management | PTT Reliability Mechanism | Implemented |
| AD-006 | Operational | Audio Buffer Strategy | Implemented |
| AD-007 | Architectural | CW Decoding (ONNX) | Implemented |
| AD-008 | Architectural | ATR-1000 Proxy Architecture | Implemented |

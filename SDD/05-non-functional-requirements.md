# 5. Non-Functional Requirements (ART 0507)

## 5.1 Performance Requirements

| ID | Requirement | Target | Priority | Verification |
|----|-------------|--------|----------|-------------|
| NFR-001 | TX/RX switching delay | < 100ms | Critical | Timestamp measurement |
| NFR-002 | PTT response time | < 50ms | Critical | Event loop profiling |
| NFR-003 | End-to-end audio delay | < 100ms | Critical | Loopback test |
| NFR-004 | Power display delay | < 200ms | High | WebSocket timing |
| NFR-005 | UI response time | < 200ms | Medium | Browser dev tools |
| NFR-006 | Concurrent clients | >= 10 | Medium | Load testing |

## 5.2 Availability Requirements

| ID | Requirement | Target | Priority | Verification |
|----|-------------|--------|----------|-------------|
| NFR-010 | System uptime | >= 99.5% | Critical | Server monitoring |
| NFR-011 | Recovery time | < 30s | High | Auto-restart test |
| NFR-012 | Auto-reconnect | Supported | High | Network interruption test |
| NFR-013 | PTT reliability | >= 99% | Critical | PTT success rate |

## 5.3 Security Requirements

| ID | Requirement | Target | Priority | Verification |
|----|-------------|--------|----------|-------------|
| NFR-020 | Transport encryption | TLS 1.2+ | Critical | SSL scan |
| NFR-021 | User authentication | Supported | High | Auth flow test |
| NFR-022 | Access control | Role-based | Medium | Permission audit |
| NFR-023 | Audit logging | Operation records | Medium | Log review |

## 5.4 Scalability Requirements

| ID | Requirement | Target | Priority | Verification |
|----|-------------|--------|----------|-------------|
| NFR-030 | Multi-instance deployment | Supported | High | Parallel instance test |
| NFR-031 | Modular design | Loose coupling | Medium | Code review |
| NFR-032 | New radio support | Extensible via Hamlib | Medium | Different radio test |

## 5.5 Compatibility Requirements

| ID | Requirement | Target | Priority | Verification |
|----|-------------|--------|----------|-------------|
| NFR-040 | Mobile browsers | iOS Safari, Android Chrome | Critical | Device testing |
| NFR-041 | Desktop browsers | Chrome, Firefox, Safari, Edge | High | Cross-browser testing |
| NFR-042 | Radio equipment | All Hamlib-supported radios | High | Hamlib compatibility list |
| NFR-043 | Operating systems | macOS, Linux, Windows | High | Cross-platform testing |

## 5.6 Capacity Requirements

| ID | Requirement | Target | Priority | Verification |
|----|-------------|--------|----------|-------------|
| NFR-050 | Network bandwidth | < 100kbps (control) + 256kbps (audio) | Medium | Bandwidth monitor |
| NFR-051 | Memory footprint | < 200MB | Medium | RSS measurement |
| NFR-052 | CPU usage | < 30% (single client) | Medium | Top/htop monitoring |

## 5.7 Audio Quality Requirements

| ID | Requirement | Target | Priority | Verification |
|----|-------------|--------|----------|-------------|
| NFR-060 | WDSP NR depth | 15-20dB | Critical | Spectral analysis |
| NFR-061 | Opus codec quality | 20kbps @ 16kHz | High | Subjective listening test |
| NFR-062 | Audio sample rate | 48kHz (processing), 16kHz (transport) | High | Audio interface config |
| NFR-063 | Audio format | Int16 PCM primary, Opus optional | High | Codec verification |

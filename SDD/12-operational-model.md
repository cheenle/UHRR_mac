# 12. Operational Model (ART 0522)

## 12.1 System Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MRRC System Topology                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        Node: MRRC Server                         │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │  OS: macOS/Linux                                            │ │   │
│  │  │  ┌───────────────────────────────────────────────────────┐  │ │   │
│  │  │  │  Python 3.12+                                        │  │ │   │
│  │  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │  │ │   │
│  │  │  │  │ MRRC   │ │ rigctld │ │atr1000_ │ │ voice   │  │  │ │   │
│  │  │  │  │Server  │ │         │ │ proxy   │ │assistant│  │  │ │   │
│  │  │  │  │ :8877  │ │ :4532   │ │ :60001  │ │ (local)│  │  │ │   │
│  │  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘  │  │ │   │
│  │  │  │       │          │           │           │        │  │ │   │
│  │  │  │       └──────────┼───────────┼───────────┘        │  │ │   │
│  │  │  │                  │           │                    │  │ │   │
│  │  │  │  ┌──────────────┴───────────┴──────────────┐      │  │ │   │
│  │  │  │  │     PyAudio / WDSP / Hamlib            │      │  │ │   │
│  │  │  │  └─────────────────────────────────────────┘      │  │ │   │
│  │  │  └───────────────────────────────────────────────────┘  │ │   │
│  │  │                                                              │   │
│  │  └─────────────────────────────────────────────────────────────┘   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                      │                                  │
│           ┌──────────────────────────┼──────────────────────────┐     │
│           │                          │                          │     │
│           ▼                          ▼                          ▼     │
│   ┌───────────────┐         ┌───────────────┐         ┌─────────────┐  │
│   │  Radio Device │         │ ATR-1000      │         │  Audio     │  │
│   │  IC-M710     │         │ Tuner         │         │  Device    │  │
│   │  Serial:     │         │ IP:           │         │  USB CODEC │  │
│   │  /dev/tty... │         │ 192.168.1.63  │         │            │  │
│   └───────────────┘         └───────────────┘         └─────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 12.2 Node Description

| Node | Type | Specs | Software |
|------|------|-------|----------|
| MRRC Server | Application server | 4+ CPU cores, 8+ GB RAM | Python 3.12+, Tornado |
| rigctld | Controller process | - | Hamlib |
| ATR-1000 Proxy | Proxy process | - | Python, atr1000_proxy.py |
| ATR-1000 API Server | REST API process | - | Python, atr1000_api_server.py (:8080) |
| ATR-1000 Device | Hardware tuner | 0-200W, 1.8-54MHz | Built-in firmware |
| Voice Assistant | AI service | GPU recommended | Whisper, Qwen3-TTS |
| Client | Browser | Modern browser | Chrome/Safari/Edge/Firefox |

## 12.3 Connection Matrix

| Source | Target | Protocol | Port/Path | Description |
|--------|--------|----------|-----------|-------------|
| Browser | MRRC Server | HTTPS/WSS | 443/8877 | Web UI and audio stream |
| MRRC Server | rigctld | TCP | 4532 | Radio CAT control |
| MRRC Server | ATR-1000 Proxy | Unix Socket | /tmp/atr1000_*.sock | Tuner data exchange |
| ATR-1000 Proxy | ATR-1000 Device | WebSocket | 60001 | Direct hardware communication |
| MRRC Server | Voice Assistant | In-process call | - | Local Python process, no HTTP |
| External App | ATR API Server | HTTP | 8080 | Third-party tuner control |

## 12.4 Deployment Configuration

| Environment | Configuration | Description |
|-------------|--------------|-------------|
| Development | HTTP, localhost, single instance | Local testing, no TLS |
| Production | HTTPS (TLS), domain name, multi-instance support | Live deployment with SSL certificates |
| Docker | Alpine Linux, Hamlib built from source | Containerized deployment, device mapping |

## 12.5 Process Management

| Process | Start Method | PID File | Log File |
|---------|-------------|----------|----------|
| MRRC | `./MRRC` | `atr1000.pid` | stdout/redirected |
| atr1000_proxy | `python3 atr1000_proxy.py` | `atr1000_radio1.pid` | `atr1000_radio1.log` |
| atr1000_api_server | `python3 atr1000_api_server.py` | - | stdout |
| rigctld | `rigctld -m <model> -r <port>` | - | Hamlib log |
| voice_assistant | `python3 voice_assistant_service.py` | - | Local process, no HTTP port |

## 12.6 SSL/TLS Configuration

| Component | Certificate Path | Key Path |
|-----------|-----------------|----------|
| MRRC Server | `certs/radio.vlsc.net.pem` | `certs/radio.vlsc.net.key` |
| Certificate Type | Let's Encrypt (ACME) | Auto-renewal via `acme_config.sh` |

## 12.7 Backup & Maintenance

| Item | Strategy | Description |
|------|----------|-------------|
| Configuration backup | Script: `backup_to_ssd.sh` | Periodic backup to external storage |
| Tuner data | `atr1000_tuner.json` | Auto-saved, no manual backup needed |
| Certificate backup | `certs/backup/` | Timestamped certificate copies |
| Log rotation | Manual/application-level | Log files grow over time, periodic cleanup needed |

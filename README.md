# Universal HamRadio Remote (UHRR)

[![English](https://img.shields.io/badge/lang-English-blue.svg)](README_en.md)
[![中文](https://img.shields.io/badge/lang-中文-red.svg)](README_CN.md)

---

A web-based remote control and audio streaming system for shortwave radios.

**面向短波电台的 Web 远程控制与音频流系统。**

---

## 🌐 Select Language / 选择语言

| Language | Description |
|----------|-------------|
| [**English**](README_en.md) | Documentation in English |
| [**中文**](README_CN.md) | 中文文档 |

---

## ✨ Highlights / 亮点

| Feature | Description |
|---------|-------------|
| 🎛️ **Browser Control** | Frequency, mode, PTT control via web browser |
| 🎤 **Bidirectional Audio** | Real-time TX/RX audio streaming (16kHz) |
| 📱 **Mobile Optimized** | Modern UI for iPhone/Android devices |
| 🔒 **TLS Encryption** | Secure HTTPS/WSS connections |
| ⚡ **Low Latency** | TX→RX switching < 100ms |

---

## 📊 Performance / 性能指标

| Metric | Value |
|--------|-------|
| TX Latency | ~65ms |
| RX Latency | ~51ms |
| TX→RX Switch | <100ms |
| PTT Reliability | 99%+ |

---

## 🚀 Quick Start / 快速开始

```bash
# 1. Start rigctld
rigctld -m 335 -r /dev/cu.usbserial-230 -s 4800

# 2. Start UHRR
python ./UHRR

# 3. Access via browser
# https://your-domain/
```

---

## 📁 Project Structure / 项目结构

```
UHRR_mac/
├── www/           # Frontend (HTML5/JS/CSS)
├── UHRR           # Backend (Tornado + WebSocket)
├── certs/         # TLS certificates
├── docs/          # Documentation
├── dev_tools/     # Test utilities
└── nanovna/       # NanoVNA integration
```

---

## 📄 License / 许可证

[GNU General Public License v3.0](LICENSE)

Based on [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5)

---

## 🔗 Links

- [English Documentation](README_en.md)
- [中文文档](README_CN.md)
- [Changelog](CHANGELOG.md)
- [System Architecture](docs/System_Architecture_Design.md)

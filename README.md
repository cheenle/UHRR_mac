# Mobile Remote Radio Control (MRRC)

[![English](https://img.shields.io/badge/lang-English-blue.svg)](README_en.md)
[![中文](https://img.shields.io/badge/lang-中文-red.svg)](README_CN.md)

---

**Amateur Radio, Anytime, Anywhere.**

**随时随地，畅享业余无线电。**

A modern web-based remote control system optimized for mobile devices, enabling flexible operation of your amateur radio station from anywhere.

基于现代Web技术的远程电台控制系统，专为移动端优化，让您随时随地灵活操控业余电台。

---

## 📸 Screenshots / 界面展示

### 📱 Mobile Interface / 移动端界面

<p align="center">
  <img src="screenshots/mobile_interface.png" alt="Mobile Interface" width="300">
</p>

> Modern mobile UI optimized for iPhone/Android with touch-friendly controls, large PTT button, and real-time S-meter display.

> 现代移动界面，专为iPhone/Android优化，触摸友好控制，大尺寸PTT按钮，实时S表显示。

### 🖥️ Desktop Interface / 桌面端界面

<p align="center">
  <img src="screenshots/desktop_interface.jpg" alt="Desktop Interface" width="600">
</p>

> Full-featured desktop interface with spectrum display, detailed controls, and comprehensive radio management.

> 全功能桌面界面，支持频谱显示、详细控制和全面的电台管理。

---

## 🌐 Select Language / 选择语言

| Language | Description |
|----------|-------------|
| [**English**](README_en.md) | Documentation in English |
| [**中文**](README_CN.md) | 中文文档 |

---

## ✨ Key Features / 核心特性

| Feature | Description |
|---------|-------------|
| 📱 **Mobile First** | Optimized for iPhone/Android with touch-friendly UI |
| 🎛️ **Full Control** | Frequency, mode, PTT - complete station control |
| 🎤 **Real-time Audio** | Bidirectional TX/RX streaming (16kHz) |
| 🌍 **Remote Anywhere** | Access your station from anywhere with internet |
| 🔒 **Secure Connection** | TLS encrypted HTTPS/WSS |
| ⚡ **Ultra Low Latency** | TX→RX switching < 100ms |
| 🎯 **One-Hand Operation** | PTT button optimized for mobile thumb reach |

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

# 2. Start MRRC Server
python ./UHRR

# 3. Access from mobile browser
# https://your-domain/mobile_modern.html
```

---

## 📁 Project Structure / 项目结构

```
MRRC/
├── www/           # Frontend (HTML5/JS/CSS)
│   ├── mobile_modern.html   # Mobile interface
│   ├── controls.js          # Audio & control logic
│   └── tx_button_optimized.js
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

# Mobile Remote Radio Control (MRRC)

[![English](https://img.shields.io/badge/lang-English-blue.svg)](README_en.md) [![中文](https://img.shields.io/badge/lang-中文-red.svg)](README_CN.md)

**随时随地，畅享业余无线电。**

MRRC 是一款专为移动端优化的业余电台远程控制系统。无论您身在何处，只需一部手机或平板，即可通过现代浏览器完整操控您的业余电台站。前端基于 HTML5/JS，后端基于 Tornado + PyAudio + rigctld（Hamlib）。

> ✅ **核心优势**：移动端优先设计，TX→RX切换延迟<100ms，PWA支持离线访问，专为单手操作优化

## 🎯 设计理念

**Mobile First, Radio Anywhere**

- 📱 **移动优先**：专为触摸屏设计，大尺寸PTT按钮，拇指操作区域优化
- 🌍 **随时随地**：互联网覆盖处即可操控您的电台
- ⚡ **即时响应**：TX/RX切换<100ms，PTT可靠性99%+
- 🔒 **安全连接**：TLS加密，用户认证保护

## ✨ 功能特性

### 移动端核心功能
- **触摸优化界面**：大按钮、清晰的频率显示、实时S表
- **单手操作**：PTT按钮位于拇指舒适区域
- **PWA支持**：可添加到主屏幕，支持离线访问
- **音量控制**：主界面直接调节AF增益

### 电台控制
- **完整控制**：频率、模式、PTT（按下立即发射、松开立即停止）
- **VFO切换**：支持VFO A/B快速切换
- **波段选择**：一键切换常用业余频段
- **天调支持**：TUNE按钮长按发射1kHz单音

### 音频系统
- **双向音频**：TX端Int16编码，RX端低抖动播放（AudioWorklet），采样率16kHz
- **实时S表**：准确显示S0-S9+60dB信号强度
- **音频滤波**：多种滤波器配置可选

### 安全与连接
- **TLS/证书**：支持自有证书链（fullchain + 私钥）
- **用户认证**：FILE认证支持，保护您的电台安全

## 🚀 快速开始（macOS）

### 1. 依赖
- Python 3.12+
- Hamlib/rigctld 已安装并可用
- PyAudio（基于 PortAudio）

### 2. 启动 rigctld
```bash
# 示例，按你的实际串口/参数调整
rigctld -m 335 -r /dev/cu.usbserial-230 -s 4800
```

### 3. 配置 TLS 证书（可选但推荐）
```bash
# 将证书放入 certs/ 目录
# certs/fullchain.pem（服务器证书 + 中间证书）
# certs/radio.vlsc.net.key（私钥）
```

编辑 `UHRR.conf`：
```ini
[SERVER]
port = 443
certfile = certs/fullchain.pem
keyfile = certs/radio.vlsc.net.key
auth = FILE
```

### 4. 启动服务
```bash
python ./UHRR
```

### 5. 访问
- **移动端**：`https://<你的域名>/mobile_modern.html` ⭐ 推荐
- **桌面端**：`https://<你的域名>/`

## 📱 移动端界面

| 界面 | 用途 | 特点 |
|------|------|------|
| `mobile_modern.html` | 现代移动界面 | iPhone 15优化，PWA支持，单手操作 |
| `index.html` | 桌面完整界面 | 全功能控制，适合大屏幕 |

## 📁 目录结构

```
MRRC/
├── www/                        # 前端页面与脚本
│   ├── mobile_modern.html      # 移动端主界面 ⭐
│   ├── mobile_modern.js        # 移动端逻辑
│   ├── controls.js             # 音频与控制主逻辑
│   ├── tx_button_optimized.js  # TX按钮优化
│   └── rx_worklet_processor.js # AudioWorklet播放器
├── UHRR                        # 后端主程序
├── audio_interface.py          # PyAudio封装
├── hamlib_wrapper.py           # rigctld通信
├── certs/                      # TLS证书
├── docs/                       # 技术文档
├── dev_tools/                  # 测试工具
└── nanovna/                    # NanoVNA集成
```

## ⚙️ 关键配置

`UHRR.conf` 主要配置项：
- `[SERVER] port`：监听端口（生产建议443）
- `[SERVER] auth`：认证方式（FILE）
- `[AUDIO] inputdevice/outputdevice`：音频设备
- `[HAMLIB] rig_pathname/rig_model`：电台串口与型号

## 📊 性能指标

| 指标 | 数值 |
|------|------|
| TX延迟 | ~65ms |
| RX延迟 | ~51ms |
| TX→RX切换 | <100ms |
| PTT可靠性 | 99%+ |

## 📚 文档

- **[系统架构设计](docs/System_Architecture_Design.md)**：完整的系统架构设计
- **[PTT/音频稳定性](docs/PTT_Audio_Postmortem_and_Best_Practices.md)**：稳定性分析与最佳实践
- **[延迟优化指南](docs/latency_optimization_guide.md)**：TX/RX切换延迟优化详解
- **[移动端界面文档](docs/mobile_modern_interface.md)**：移动端界面设计说明

## 🔧 常见问题

### 端口占用
```bash
lsof -iTCP:443 -sTCP:LISTEN -n -P
kill -9 <PID>
```

### 证书错误
```bash
# 规范换行
sed -e 's/\r$//' input.pem > output.pem
```

### 移动端PTT不响应
1. 确认麦克风权限已授权
2. 检查WebSocket连接状态
3. 查看浏览器控制台日志

## 📄 许可证

[GNU General Public License v3.0](LICENSE)

基于 [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5) 开源项目开发

---

**MRRC - Mobile Remote Radio Control**  
*Amateur Radio, Anytime, Anywhere.*
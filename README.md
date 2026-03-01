# Universal HamRadio Remote (UHRR)

面向业余无线电爱好者的 Web 远程控制与音频流系统。前端基于 HTML5/JS，后端基于 Tornado + PyAudio + rigctld（Hamlib）。本版本已针对 macOS/移动端和 TLS 做了修复与优化，并显著改善了 TX/PTT 时序与 RX 抖动。

> ✅ **重要优化**：TX到RX切换延迟已从2-3秒优化到<100ms

## 功能特性

- **远程控制**：频率、模式、PTT、VFO切换、S表读取
- **双向音频**：TX端Int16编码，RX端低抖动播放（AudioWorklet），采样率16kHz
- **TLS加密**：支持自有证书链
- **移动端支持**：iPhone/Android专用界面 ★
- **PTT可靠性**：按下即发，预热帧保证传输
- **快速切换**：TX/RX切换<100ms延迟

## 快速开始

### 1. 安装依赖
```bash
./uhrr_setup.sh install
```

### 2. 启动rigctld
```bash
rigctld -m 30003 -r /dev/cu.usbserial-120 -s 4800 -C stop_bits=2
```

### 3. 启动服务
```bash
./uhrr_control.sh start
```

### 4. 访问
- 桌面端：`https://<IP>/index.html`
- 移动端：`https://<IP>/mobile_modern.html` ★

## 移动端界面 (v3.2)

全新优化的移动端界面，专为iPhone/Android设计：

| 功能 | 说明 |
|------|------|
| 波段选择 | 160m-2m全波段 |
| 模式切换 | USB/LSB/CW/FM/AM/WFM |
| 步进选择 | 10Hz-10kHz |
| 滤波选择 | 宽/中/窄 |
| 音量控制 | 滑块+静音 |
| PTT按钮 | 大尺寸触感反馈 |

### iPhone使用注意
- 首次需授权麦克风权限
- 如无声音，点击任意按钮激活AudioContext
- 建议添加到主屏幕作为PWA应用

## 目录结构

```
UHRR_mac/
├── UHRR              # 后端主程序
├── UHRR.conf         # 配置文件
├── audio_interface.py # PyAudio封装
├── hamlib_wrapper.py  # rigctld辅助
├── tci_client.py      # TCI协议
├── uhrr_control.sh   # 服务控制
├── uhrr_setup.sh     # 安装脚本
├── www/              # 前端
│   ├── index.html           # 桌面端
│   ├── mobile_modern.html   # 移动端 ★
│   ├── controls.js          # 桌面逻辑
│   └── mobile_modern.js     # 移动端逻辑
├── certs/            # TLS证书
├── dev_tools/        # 测试工具
├── opus/             # Opus编解码
└── nanovna/         # NanoVNA界面
```

## 服务管理

```bash
./uhrr_control.sh start    # 启动
./uhrr_control.sh stop     # 停止
./uhrr_control.sh restart  # 重启
./uhrr_control.sh status    # 状态
./uhrr_control.sh logs     # 日志
```

## 配置文件 (UHRR.conf)

```ini
[SERVER]
port = 8877
certfile = certs/fullchain.pem
keyfile = certs/radio.vlsc.net.key

[AUDIO]
audio_input = USB Audio Device
audio_output = USB Audio Device

[HAMLIB]
rig_pathname = /dev/cu.usbserial-120
rig_model = IC_M710
rig_rate = 4800
```

## 常见问题

### 端口占用
```bash
lsof -iTCP:8877
kill -9 <PID>
```

### 无声音
- 检查WebSocket连接状态
- iPhone：点击按钮激活AudioContext
- 检查音量设置

### PTT不响应
- 确认已连接（电源按钮高亮）
- 检查麦克风权限
- 查看控制台错误

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v3.2 | 2026-03-01 | 移动端界面全面优化，iOS兼容性修复 |
| v3.1 | 2025-xx | 移动端音频和PTT优化 |
| v3.0 | 2025-xx | TX/RX延迟优化，AudioWorklet |

## 技术文档

详细技术文档请参阅 `docs/` 目录：
- 系统架构设计
- 延迟优化指南
- PTT/音频稳定性分析

## 许可证

GPL-3.0，基于 [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5)
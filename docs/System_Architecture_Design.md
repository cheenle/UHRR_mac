# Universal HamRadio Remote (UHRR) 系统架构设计

## 文档信息
- **版本**: v3.2
- **更新**: 2026-03-01
- **项目**: UHRR - 业余无线电远程控制系统

---

## 1. 系统概述

### 1.1 项目定位
UHRR (Universal HamRadio Remote) 是一个面向业余无线电爱好者的远程电台控制与音频流系统。通过现代Web技术实现远程操作，用户可通过浏览器界面远程控制电台设备，进行语音通话和参数调节。

### 1.2 核心特性
- **远程控制**: 频率、模式、PTT、VFO切换、S表读取
- **实时音频**: TX/RX双向音频流，16kHz采样，<100ms延迟
- **移动端支持**: iPhone/Android专用界面，触摸优化
- **PTT可靠性**: 按下即发，预热帧保证传输
- **TLS安全**: 支持自有证书链加密

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        客户端 (Browser)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  桌面端     │  │  移动端     │  │  AudioWorklet          │  │
│  │  index.html │  │mobile_modern│  │  rx_worklet_processor  │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │ WebSocket + TLS
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     服务器端 (Python/Tornado)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  WebSocket  │  │   PyAudio   │  │    Hamlib/rigctld      │  │
│  │   Handler   │  │  音频编解码  │  │    电台控制            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        电台设备 (Hardware)                       │
│              IC-7100 / IC-7300 / IC-9000 等                    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| 前端 | HTML5/CSS3/JavaScript | Web界面 |
| 前端 | Web Audio API | 音频处理 |
| 前端 | AudioWorklet | 低延迟音频播放 |
| 前端 | WebSocket | 实时通信 |
| 后端 | Python 3.12+ | 运行环境 |
| 后端 | Tornado | Web框架 |
| 后端 | PyAudio | 音频采集/播放 |
| 后端 | Hamlib/rigctld | 电台控制 |
| 部署 | macOS/类Unix | 操作系统 |

---

## 3. 核心模块

### 3.1 后端模块

#### 3.1.1 UHRR (主程序)
- **文件**: `UHRR`
- **功能**: Tornado WebSocket服务器
- **职责**:
  - WebSocket连接管理
  - 音频数据转发
  - 控制命令处理
  - 用户认证

#### 3.1.2 audio_interface.py
- **功能**: PyAudio封装
- **职责**:
  - 音频设备枚举
  - 音频采集 (RX)
  - 音频播放 (TX)
  - 多客户端分发

#### 3.1.3 hamlib_wrapper.py
- **功能**: rigctld通信辅助
- **职责**:
  - 电台命令封装
  - 频率/模式读取
  - PTT控制
  - S表数据获取

#### 3.1.4 tci_client.py
- **功能**: TCI协议客户端
- **职责**:
  - TCI命令发送
  - 状态解析
  - 支持TCI兼容电台

### 3.2 前端模块

#### 3.2.1 桌面端 (index.html + controls.js)
- **功能**: 传统桌面浏览器界面
- **特性**:
  - 完整电台控制
  - 频谱显示
  - S表可视化

#### 3.2.2 移动端 (mobile_modern.html + mobile_modern.js)
- **功能**: 现代移动端界面 ★ v3.2
- **特性**:
  - 波段选择 (160m-2m)
  - 模式切换 (USB/LSB/CW/FM/AM/WFM)
  - 步进选择 (10Hz-10kHz)
  - 滤波选择 (宽/中/窄)
  - 音量控制
  - 触摸优化

#### 3.2.3 音频处理
- **tx_button_optimized.js**: TX按钮优化，PTT控制
- **rx_worklet_processor.js**: AudioWorklet播放器
- **mobile_audio_direct_copy.js**: 移动端音频直连

---

## 4. 通信协议

### 4.1 控制协议
```json
// WebSocket JSON消息
{"cmd": "set_freq", "freq": 14100000}
{"cmd": "set_mode", "mode": "USB"}
{"cmd": "ptt", "state": true}
```

### 4.2 音频协议
- **格式**: Int16 (PCM 16-bit)
- **采样率**: 16kHz
- **帧大小**: 640字节 (20ms)
- **延迟目标**: <100ms

---

## 5. 配置文件

### 5.1 UHRR.conf
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

---

## 6. 部署架构

### 6.1 服务管理
```bash
./uhrr_control.sh start    # 启动
./uhrr_control.sh stop     # 停止
./uhrr_control.sh restart  # 重启
./uhrr_control.sh status   # 状态
./uhrr_control.sh logs     # 日志
```

### 6.2 服务依赖
```
1. rigctld (Hamlib) - 电台控制守护进程
2. UHRR (Tornado)  - 主服务
```

---

## 7. 性能优化

### 7.1 延迟优化
- TX/RX切换: <100ms
- 音频帧: 20ms
- 缓冲区: 动态调整

### 7.2 带宽优化
- Int16编码: 50%带宽减少
- 预热帧: 确保音频传输

### 7.3 移动端优化
- AudioContext用户交互激活
- 触摸事件双支持 (click + touchend)
- 大尺寸按钮 (最小56px)

---

## 8. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v3.2 | 2026-03-01 | 移动端界面全面优化 |
| v3.1 | 2025-xx | 移动端音频和PTT优化 |
| v3.0 | 2025-xx | TX/RX延迟优化 |

---

## 9. 目录结构

```
UHRR_mac/
├── UHRR                    # 后端主程序
├── UHRR.conf               # 配置文件
├── audio_interface.py      # PyAudio封装
├── hamlib_wrapper.py       # rigctld辅助
├── tci_client.py           # TCI协议
├── uhrr_control.sh         # 服务控制
├── uhrr_setup.sh           # 安装脚本
├── uhrr_monitor.sh        # 监控脚本
├── www/                    # 前端
│   ├── index.html          # 桌面端
│   ├── mobile_modern.html  # 移动端
│   ├── controls.js         # 桌面逻辑
│   ├── mobile_modern.js    # 移动端逻辑
│   └── rx_worklet_processor.js
├── certs/                  # TLS证书
├── dev_tools/              # 测试工具
├── docs/                   # 文档
├── opus/                   # Opus编解码
└── nanovna/               # NanoVNA界面
```

---

*文档版本: v3.2 | 最后更新: 2026-03-01*
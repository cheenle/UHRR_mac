# Mobile Remote Radio Control (MRRC) V4.9.3

[![English](https://img.shields.io/badge/lang-English-blue.svg)](README_en.md) [![中文](https://img.shields.io/badge/lang-中文-red.svg)](README_CN.md) [![版本](https://img.shields.io/badge/版本-V4.9.3-green.svg)](CHANGELOG.md)

**随时随地，畅享业余无线电。**

MRRC 是一款专为移动端优化的业余电台远程控制系统。无论您身在何处，只需一部手机或平板，即可通过现代浏览器完整操控您的业余电台站。前端基于 HTML5/JS，后端基于 Tornado + PyAudio + rigctld（Hamlib）。

> ✅ **核心优势**：移动端优先设计，TX→RX切换延迟<100ms，PWA支持离线访问，专为单手操作优化
>
> 🎉 **V4.9.3 更新亮点**：
> - 🔄 **第三方软件频率联动**：支持JTDX/flrig/wfview频率同步
> - 🎨 **蓝色系UI风格**：SDR风格蓝色专业配色
> - 📊 **S表显示优化**：独立分析器，不受音量控制影响
>
> 历史版本：V4.9.2 蓝色UI | V4.9.0 语音助手、CW解码、SDR界面

## 🎯 设计理念

**Mobile First, Radio Anywhere**

- 📱 **移动优先**：专为触摸屏设计，大尺寸PTT按钮，拇指操作区域优化
- 🌍 **随时随地**：互联网覆盖处即可操控您的电台
- ⚡ **即时响应**：TX/RX切换<100ms，PTT可靠性99%+
- 🔒 **安全连接**：TLS加密，用户认证保护

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            客户端层                                      │
├───────────────────────────┬─────────────────────────────────────────────┤
│     移动端浏览器           │           外部软件 / API                     │
│  mobile_modern.html       │        Python / SDR / 日志软件              │
│  (PWA, 触摸优化)          │                                             │
└─────────────┬─────────────┴──────────────────────┬──────────────────────┘
              │ HTTPS / WebSocket                  │ HTTP REST (API)
              ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           服务层                                         │
├───────────────────────────┬─────────────────────────────────────────────┤
│      MRRC 主程序           │         ATR-1000 API Server                 │
│   (Tornado WebSocket)     │      (RESTful API, :8080)                   │
│                           │                                             │
│  • 电台控制 (rigctld)      │  • /api/v1/status    状态查询              │
│  • 音频流 TX/RX (PyAudio)  │  • /api/v1/relay     继电器控制            │
│  • 频率同步               │  • /api/v1/tune      快速调谐               │
│  • 用户认证               │  • /api/v1/tuner     学习记录管理           │
└─────────────┬─────────────┴──────────────────────┬──────────────────────┘
              │                                    │
              │ rigctld + Audio                    │ Unix Socket
              │                                    │ /tmp/atr1000_proxy.sock
              ▼                                    ▼
┌───────────────────────────┐         ┌─────────────────────────────────────┐
│       电台设备             │         │        ATR-1000 代理层              │
│   (IC-M710/IC-7300/等)    │         │       atr1000_proxy.py              │
│                           │         │                                     │
│  • 频率/模式控制 (rigctld)│         │  • 唯一设备连接（避免冲突）          │
│  • PTT 控制              │         │  • 动态轮询：空闲15s/活跃5s/TX 0.5s │
│  • 音频 TX/RX            │         │  • 智能学习 + 快速调谐              │
│  • S表读取               │         └──────────────┬──────────────────────┘
└───────────────────────────┘                        │ WebSocket
                                                     ▼
                                     ┌─────────────────────────────────────┐
                                     │          ATR-1000 天调设备           │
                                     │       (功率计 + 自动天调)            │
                                     │                                     │
                                     │  • 实时功率/SWR 显示                │
                                     │  • 继电器参数 (SW/IND/CAP)          │
                                     └─────────────────────────────────────┘
```

**架构说明**：
- **MRRC 主程序**：直接控制电台设备（音频 TX/RX + rigctld 频率控制）
- **ATR-1000 Proxy**：独立代理，只与 ATR-1000 天调设备通信
- **API Server**：通过 Unix Socket 调用 Proxy，不直接连接设备

## 🧩 核心组件

### 后端组件

| 组件 | 文件 | 功能 |
|------|------|------|
| **MRRC 主程序** | `MRRC` | Tornado WebSocket 服务器，电台控制，音频流，用户认证 |
| **音频接口** | `audio_interface.py` | PyAudio 封装，音频采集与播放 |
| **Hamlib 封装** | `hamlib_wrapper.py` | rigctld 通信封装 |
| **ATR-1000 代理** | `atr1000_proxy.py` | 天调设备代理，智能学习，快速调谐 |
| **ATR-1000 API** | `atr1000_api_server.py` | RESTful API 服务，供外部软件调用 |
| **天调存储** | `atr1000_tuner.py` | 频率-参数映射存储与管理 |
| **TCI 客户端** | `tci_client.py` | TCI 协议支持（特定电台） |

### 前端组件

| 组件 | 文件 | 功能 |
|------|------|------|
| **移动端界面** | `www/mobile_modern.html` | iPhone 15 优化，PWA 支持 |
| **移动端逻辑** | `www/mobile_modern.js` | 移动端 WebSocket 与 UI 逻辑 |
| **控制核心** | `www/controls.js` | 音频处理，PTT 控制，WebSocket 通信 |
| **TX 优化** | `www/tx_button_optimized.js` | TX 按钮时序优化 |
| **RX 播放** | `www/rx_worklet_processor.js` | AudioWorklet 低延迟播放 |
| **ATU 显示** | `www/atu.js` | 功率/SWR 实时显示 |

## ✨ 功能特性

### 移动端核心功能
- **触摸优化界面**：大按钮、清晰的频率显示、实时S表
- **单手操作**：PTT按钮位于拇指舒适区域
- **专业DSP降噪**：集成WDSP库，提供NR2频谱降噪、噪声抑制、自动陷波等功能
- **PWA支持**：可添加到主屏幕，支持离线访问
- **音量控制**：主界面直接调节AF增益

### 电台控制
- **完整控制**：频率、模式、PTT（按下立即发射、松开立即停止）
- **VFO切换**：支持VFO A/B快速切换
- **波段选择**：一键切换常用业余频段
- **天调支持**：TUNE按钮长按发射1kHz单音

### 🎙️ 音频录制 (V4.8.0 新增)
- **浏览器内录制**：无需额外软件，直接录制QSO音频
- **双格式支持**：WAV (无损) 或 MP3 (压缩)
- **自动下载**：录制完成后自动下载到本地
- **电平指示**：实时显示录音电平
- **访问地址**：`https://<域名>/recordings.html`

### 🚀 远程启动 (V4.8.0 新增)
- **SSH远程管理**：通过SSH脚本远程启动/停止服务
- **服务状态检查**：远程查询服务运行状态
- **日志查看**：远程查看服务日志
- **使用脚本**：`./mrrc_remote_start.sh`

### 🎙️ AI 语音助手 (V4.9.0 新增)
- **Whisper 语音识别**：支持中文/英文语音转文字
- **Qwen3-TTS 语音合成**：自然语音合成播报
- **语音控制电台**：语音指令控制频率、模式等
- **呼号自动解释**：AI 识别呼号并给出解释
- **访问地址**：`https://<域名>/mobile_voice_assistant.html`

### 📡 CW 实时解码 (V4.9.0 新增)
- **ONNX 前端推理**：轻量级模型 (<2MB)，浏览器内实时解码
- **双模式架构**：支持音频流实时解码和录音文件解码
- **QSO 状态机**：智能建议回复内容
- **访问地址**：`https://<域名>/cw_live.html`

### 🖥️ SDR 现代界面 (V4.9.0 新增)
- **全新 SDR 控制界面**：现代化响应式设计
- **实时频谱显示**：瀑布图、频谱图
- **访问地址**：`https://<域名>/sdr_modern.html`

### 音频系统
- **双向音频**：TX端Int16编码，RX端低抖动播放（AudioWorklet），采样率16kHz
- **实时S表**：准确显示S0-S9+60dB信号强度
- **音频滤波**：多种滤波器配置可选
- **TX均衡器**：三段均衡器优化发射音频，支持短波语音/弱信号/比赛模式

### ATR-1000 天调智能学习 ⭐ 核心功能
- **实时功率显示**：发射时实时显示前向功率（0-200W），延迟 <200ms
- **SWR 监测**：实时显示驻波比（1.0-9.99）
- **智能学习**：发射时自动记录频率与天调参数（SW/IND/CAP）对应关系
- **快速调谐**：切换频率时自动应用已学习的天调参数
- **参数持久化**：学习记录保存在 JSON 文件，重启后自动加载
- **独立 API**：RESTful API 供外部软件调用

### 动态轮询优化
为避免设备因频繁请求而挂起，实现了动态轮询机制：

| 状态 | 轮询间隔 | 说明 |
|------|----------|------|
| 空闲 | 15秒 | 无客户端连接时，降低设备压力 |
| 活跃 | 5秒 | 有客户端连接，保持连接活跃 |
| TX 发射 | 0.5秒 | 发射期间快速更新功率/SWR |

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

编辑 `MRRC.conf`：
```ini
[SERVER]
port = 443
certfile = certs/fullchain.pem
keyfile = certs/radio.vlsc.net.key
auth = FILE
```

### 4. 启动服务
```bash
# 使用控制脚本（推荐）
./mrrc_control.sh start

# 或分别启动各服务
./mrrc_control.sh start-rigctld
./mrrc_control.sh start-mrrc
./mrrc_control.sh start-atr1000
```

### 5. 访问
- **移动端**：`https://<你的域名>/mobile_modern.html` ⭐ 推荐
- **桌面端**：`https://<你的域名>/`
- **音频录制**：`https://<你的域名>/recordings.html` 🎙️ V4.8.0
- **ATR-1000 API**：`http://localhost:8080`

### 6. 远程启动 (V4.8.0)
```bash
# 在远程服务器上配置好后，可通过SSH启动
./mrrc_remote_start.sh start

# 查看远程服务状态
./mrrc_remote_start.sh status

# 查看远程日志
./mrrc_remote_start.sh logs
```

## 📁 目录结构

```
MRRC/
├── MRRC                        # 后端主程序 (Tornado WebSocket 服务器)
├── MRRC.conf                   # 系统核心配置文件
├── audio_interface.py          # PyAudio 采集/播放封装 (V4.8.0: 多格式解码)
├── wdsp_wrapper.py             # WDSP数字信号处理库Python封装 ⭐
├── hamlib_wrapper.py           # 与 rigctld 通信的辅助逻辑
├── tci_client.py               # TCI 协议客户端实现
├── atr1000_proxy.py            # ATR-1000 独立代理程序 ⭐
├── atr1000_api_server.py       # ATR-1000 REST API 服务 ⭐
├── atr1000_tuner.py            # 天调存储模块
├── atr1000_tuner.json          # 天调参数数据文件
├── mrrc_control.sh             # 系统控制脚本（V4.8.0: 增强功能）
├── mrrc_remote_start.sh        # SSH远程启动脚本 (V4.8.0: 新增) ⭐
├── mrrc_monitor.sh             # 系统监控脚本
├── www/                        # 前端页面与脚本
│   ├── mobile_modern.html      # 现代移动端界面 ⭐
│   ├── mobile_modern.js        # 移动端界面逻辑 (V4.8.0: WDSP同步)
│   ├── controls.js             # 音频与控制主逻辑
│   ├── tx_button_optimized.js  # TX 按钮事件与时序优化
│   ├── rx_worklet_processor.js # AudioWorklet 播放器
│   ├── recordings.html         # 音频录制页面 (V4.8.0: 新增) 🎙️
│   ├── atu.js                  # ATU 功率和驻波比显示管理
│   └── panadapter/             # 频谱显示模块
├── certs/                      # TLS 证书目录
├── docs/                       # 技术文档
├── AOD.md                      # 架构概览文档 (V4.8.0: 新增)
├── DSP.md                      # DSP处理文档 (V4.8.0: 新增)
├── dev_tools/                  # 测试/调试脚本
└── nanovna/                    # NanoVNA 矢量网络分析仪 Web 界面
```

## ⚙️ 关键配置

`MRRC.conf` 主要配置项：
- `[SERVER] port`：监听端口（生产建议443）
- `[SERVER] auth`：认证方式（FILE）
- `[AUDIO] inputdevice/outputdevice`：音频设备
- `[HAMLIB] rig_pathname/rig_model`：电台串口与型号

### WDSP 降噪配置

```ini
[WDSP]
# WDSP 数字信号处理（推荐启用）
enabled = True
sample_rate = 48000          # 采样率
buffer_size = 256            # 缓冲区大小
nr2_enabled = True           # 频谱降噪（推荐）
nb_enabled = True            # 噪声抑制
anf_enabled = False          # 自动陷波
agc_mode = 3                 # AGC模式 (0=OFF, 1=LONG, 2=SLOW, 3=MED, 4=FAST)
bandpass_low = 300.0         # 低切频率 (Hz)
bandpass_high = 2700.0       # 高切频率 (Hz)
```

**安装WDSP库**（必须先安装才能使用）：
```bash
cd /tmp && git clone https://github.com/g0orx/wdsp.git
cd wdsp && make
sudo cp libwdsp.dylib /usr/local/lib/  # macOS
# sudo cp libwdsp.so /usr/local/lib/ && sudo ldconfig  # Linux
```

## 📊 性能指标

| 指标 | 数值 |
|------|------|
| TX延迟 | ~65ms |
| RX延迟 | ~51ms |
| TX→RX切换 | <100ms |
| PTT可靠性 | 99%+ |
| 音频录制 | WAV/MP3, 浏览器内录制 |
| WDSP处理延迟 | <20ms |
| WDSP降噪增益 | 15-20dB (NR2) |
| RX解码格式 | Int16/Float32 (自适应) |
| ATR-1000 功率显示延迟 | <200ms |
| 空闲轮询间隔 | 15秒 |

## 🔌 ATR-1000 API 使用

### 启动 API 服务
```bash
# 确保 Proxy 已启动
./mrrc_control.sh start-atr1000

# 启动 API Server
nohup python3 atr1000_api_server.py > atr1000_api.log 2>&1 &
```

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/v1/status` | 获取当前状态 |
| GET | `/api/v1/relay` | 获取继电器参数 |
| POST | `/api/v1/relay` | 设置继电器参数 |
| GET | `/api/v1/tuner/lookup` | 查找天调参数 |
| POST | `/api/v1/tune` | 快速调谐 |

### 使用示例
```bash
# 获取状态
curl http://localhost:8080/api/v1/status

# 快速调谐到 7050 kHz
curl -X POST -H "Content-Type: application/json" \
     -d '{"freq_khz":7050}' http://localhost:8080/api/v1/tune

# 设置继电器
curl -X POST -H "Content-Type: application/json" \
     -d '{"sw":1,"ind":30,"cap":27}' http://localhost:8080/api/v1/relay
```

## 📚 文档

- **[架构概览 AOD](AOD.md)**：系统架构快速参考 ⭐ V4.8.0
- **[DSP降噪文档](DSP.md)**：WDSP数字信号处理详细说明 ⭐
- **[系统架构设计](docs/System_Architecture_Design.md)**：完整的系统架构设计
- **[ATR-1000 天调智能学习](docs/ATR1000_Tuner_Auto_Learning.md)**：天调学习与 API 详细文档 ⭐
- **[PTT/音频稳定性](docs/PTT_Audio_Postmortem_and_Best_Practices.md)**：稳定性分析与最佳实践
- **[延迟优化指南](docs/latency_optimization_guide.md)**：TX/RX切换延迟优化详解
- **[移动端界面文档](docs/mobile_modern_interface.md)**：移动端界面设计说明
- **[多实例配置指南](docs/Multi_Instance_Setup.md)**：多电台实例配置详解 ⭐

---

**最新版本: V4.9.0** (2026-03-14) | [查看更新日志](CHANGELOG.md)

## 🖥️ 多实例支持（Multi-Instance）⭐ 新功能

MRRC V4.8+ 支持在同一台服务器上运行多个独立实例，每个实例可连接不同的电台设备。

### 快速开始

```bash
# 创建新实例
./mrrc_multi.sh create radio2

# 编辑配置（修改端口、串口、音频设备）
vim MRRC.radio2.conf

# 启动实例
./mrrc_multi.sh start radio2

# 访问
# radio1: https://localhost:8891
# radio2: https://localhost:8892
```

### 核心特性

| 特性 | 说明 |
|------|------|
| **独立端口** | 每个实例使用独立的 Web 端口和 rigctld 端口 |
| **独立音频** | 支持不同声卡设备 |
| **独立天调** | 每个实例有自己的 Unix Socket 和学习记录 |
| **统一管理** | 使用 `mrrc_multi.sh` 脚本统一管理 |

### 管理命令

```bash
./mrrc_multi.sh start radio2      # 启动
./mrrc_multi.sh stop radio2       # 停止
./mrrc_multi.sh restart radio2    # 重启
./mrrc_multi.sh status radio2     # 查看状态
./mrrc_multi.sh logs radio2       # 查看日志
```

**详细文档**：[多实例配置指南](docs/Multi_Instance_Setup.md)

---

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

### ATR-1000 设备挂起
1. 检查是否有多个进程同时连接设备
2. 确认使用 V2 API Server（通过 Proxy 通信）
3. 查看动态轮询间隔是否生效

## 📄 许可证

[GNU General Public License v3.0](LICENSE)

基于 [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5) 开源项目开发

---

**MRRC - Mobile Remote Radio Control**  
*Amateur Radio, Anytime, Anywhere.*

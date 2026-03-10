# MRRC 架构概览 (Architecture Overview Document)

**版本**: V4.8.0 (2026-03-10)  
**用途**: 快速了解 MRRC 系统架构、核心功能和数据流

---

## 📋 主要功能

1. **远程电台控制** - 频率/模式/VFO切换、PTT发射控制(99%+可靠性)、S表读取、频谱显示
2. **实时音频流** - TX/RX双向音频、Int16/ADPCM/Opus编码、端到端延迟<100ms、**WDSP专业降噪**
3. **DSP数字处理** - **WDSP库集成**：NR2频谱降噪(15-20dB)、NB噪声抑制、ANF自动陷波、AGC自动增益
4. **移动端优化** - iPhone/Android现代Web界面、PWA支持、触摸优化、离线访问
5. **ATR-1000天调集成** - 实时功率/SWR显示、智能学习、快速调谐、第三方软件联动
6. **🎙️ 音频录制 (V4.8.0)** - 浏览器内QSO录制、WAV/MP3格式、自动下载
7. **🚀 远程启动 (V4.8.0)** - SSH远程服务管理

---

## 🏗️ 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Client Layer / 客户端层                          │
├───────────────────────────┬─────────────────────────────────────────────┤
│      Mobile Browser       │         External Software / API             │
│ Desktop/Phone/Pad 浏览器  │         外部软件 / API: JTDX/WSJT etc       │
│                           │                                             │
│  • mobile_modern.html     │  • HTTP REST API (:8080)                    │
│  • recordings.html 🎙️     │  • /api/v1/status, /tune, /relay            │
│  • PWA Support            │                                             │
└─────────────┬─────────────┴──────────────────────┬──────────────────────┘
              │ HTTPS / WebSocket                  │ HTTP REST
              ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Service Layer / 服务层                            │
├───────────────────────────┬─────────────────────────────────────────────┤
│      MRRC Main Program    │         ATR-1000 API Server                 │
│      MRRC 主程序          │         RESTful API (:8080)                 │
│  (Tornado + WebSocket)    │                                             │
│                           │  • /api/v1/status    状态查询              │
│  • 电台控制 (rigctld)      │  • /api/v1/relay     继电器控制            │
│  • 音频流 TX/RX (PyAudio)  │  • /api/v1/tune      快速调谐               │
│  • WDSP DSP Processing     │  • /api/v1/tuner     学习记录管理           │
│  • 用户认证               │                                             │
└─────────────┬─────────────┴──────────────────────┬──────────────────────┘
              │                                    │
              │ rigctld + Audio                    │ Unix Socket
              │ + WDSP (NR2/NB/ANF/AGC)            │ /tmp/atr1000_proxy.sock
              ▼                                    ▼
┌───────────────────────────┐         ┌─────────────────────────────────────┐
│       Radio Device        │         │    ATR-1000 Proxy / 天调代理        │
│       IC-M710             │         │       atr1000_proxy.py              │
│                           │         │                                     │
│  • Freq/Mode (rigctld)    │         │  • 唯一设备连接（避免冲突）          │
│  • PTT Control            │         │  • 动态轮询：空闲15s/活跃5s/TX 0.5s │
│  • Audio TX/RX            │         │  • 智能学习 + 快速调谐              │
│  • S-Meter                │         │  • 频率-参数映射存储                │
└───────────────────────────┘         └──────────────┬──────────────────────┘
                                                     │ WebSocket
                                                     ▼
                                     ┌─────────────────────────────────────┐
                                     │      ATR-1000 Tuner / 天调设备      │
                                     │       (功率计 + 自动天调)            │
                                     │                                     │
                                     │  • 实时功率/SWR 显示 (0-200W)       │
                                     │  • 继电器参数 (SW/IND/CAP)          │
                                     │  • WebSocket协议 (:60001)           │
                                     └─────────────────────────────────────┘
```

---

## 🔊 音频处理流程

### TX 发射流程 (浏览器 → 电台)

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Browser   │ -> │  Web Audio  │ -> │  Encoding   │ -> │  WebSocket  │
│  Microphone │    │   (48kHz)   │    │  Int16/Opus │    │   (WSS)     │
└─────────────┘    └──────┬──────┘    └─────────────┘    └──────┬──────┘
                          │                                      │
                          ▼                                      ▼
                   ┌─────────────┐                        ┌─────────────┐
                   │ TX EQ滤波器  │                        │   MRRC      │
                   │ • 低切<100Hz │                        │  Backend    │
                   │ • 提升1500Hz │                        └──────┬──────┘
                   │ • 高切>2700Hz│                               │
                   └─────────────┘                               ▼
                                                           ┌─────────────┐
                                                           │  PyAudio    │
                                                           │  Output     │
                                                           │  (48kHz)    │
                                                           └──────┬──────┘
                                                                  ▼
                                                           ┌─────────────┐
                                                           │ Radio TX    │
                                                           └─────────────┘
```

### RX 接收流程 (电台 → 浏览器) V4.8.0

```
┌─────────────┐    ┌─────────────┐    ┌──────────────────────────────────┐
│  Radio RX   │ -> │  PyAudio    │ -> │        WDSP Processing           │
│  (48kHz)    │    │  Input      │    │  (wdsp_wrapper.py)               │
└─────────────┘    └──────┬──────┘    │                                  │
                          │           │  • DC Removal                     │
                          ▼           │  • AGC Pre-amplification          │
                   ┌─────────────┐    │  • Soft Limiter                   │
                   │ Float32     │    │  • NR2 Spectral Denoise (15-20dB) │
                   │ Buffer      │    │  • NB Noise Blanker               │
                   └──────┬──────┘    │  • ANF Auto Notch                 │
                          │           │  • AGC Auto Gain Control          │
                          ▼           └──────────────────────────────────┘
                   ┌─────────────┐                                  │
                   │ Int16/Float │                                  │
                   │ Conversion  │                                  │
                   │ (48kHz)     │                                  │
                   └──────┬──────┘                                  │
                          │                                         │
                          ▼                                         ▼
                   ┌─────────────┐                         ┌─────────────┐
                   │ Opus Encode │                         │  WebSocket  │
                   │ (16kHz)     │                         │   (WSS)     │
                   │ 20kbps      │                         └──────┬──────┘
                   └─────────────┘                                │
                                                                  ▼
                                                           ┌─────────────┐
                                                           │   Browser   │
                                                           │ AudioWorklet│
                                                           │ (RX Playback)
                                                           └─────────────┘
```

**V4.8.0 RX音频改进**:
- 支持多格式解码 (Int16/Float32 自适应)
- 改进缓冲区管理，减少音频断裂
- 优化WDSP处理延迟 <20ms

---

## 🎛️ WDSP DSP 处理流程

```
Radio Audio (48kHz Float32)
        ↓
┌─────────────────────────────────┐
│  DC Removal → AGC Pre-amp      │  audio_interface.py
│  → Soft Limiter                 │
└─────────────────────────────────┘
        ↓
Int16/Float32 Conversion (48kHz)
        ↓
┌─────────────────────────────────┐
│  WDSP Processing                │  wdsp_wrapper.py
│  ├── NR2 Spectral Denoise      │  (15-20dB noise reduction)
│  ├── NB Noise Blanker          │  (pulse interference)
│  ├── ANF Auto Notch            │  (CW/interference)
│  └── AGC Auto Gain Control     │  (4 modes)
└─────────────────────────────────┘
        ↓
Opus Encode (16kHz, 20kbps)
        ↓
WebSocket → Browser
```

### WDSP 配置参数

```ini
[WDSP]
enabled = True               # 主开关
sample_rate = 48000          # 采样率
buffer_size = 256            # 缓冲区

nr2_enabled = True           # 频谱降噪 (推荐开启)
nr2_level = 4                # 降噪强度 0-10
nr2_gain_method = 0          # 增益方法 (0=保守, 1=适中)
nr2_npe_method = 0           # 噪声估计 (0=OSMS最优平滑)
nr2_ae_run = True            # 抗音乐噪音 (必须开启)

nb_enabled = True            # 噪声抑制
anf_enabled = True           # 自动陷波

agc_mode = 3                 # AGC模式
# 0=OFF, 1=LONG, 2=SLOW, 3=MED, 4=FAST
```

---

## 🎙️ 音频录制架构 (V4.8.0 新增)

```
┌─────────────────────────────────────────────────────────────┐
│                    recordings.html                         │
│                      录音页面                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │ Web Audio   │ -> │  Recorder   │ -> │  Encoder    │    │
│  │   Stream    │    │   (JS)      │    │ WAV/MP3     │    │
│  └─────────────┘    └─────────────┘    └──────┬──────┘    │
│                                               │            │
│                                               ▼            │
│                                        ┌─────────────┐    │
│                                        │ Auto Download│    │
│                                        │ 自动下载     │    │
│                                        └─────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**功能特点**:
- 浏览器内录制，无需后端支持
- 支持 WAV (PCM) 和 MP3 (压缩) 格式
- 实时电平表显示
- 录制时长统计
- 一键下载

---

## 🚀 远程启动架构 (V4.8.0 新增)

```
┌─────────────────┐         SSH          ┌─────────────────┐
│   Local PC      │ ------------------>  │  Remote Server  │
│                 │   mrrc_remote_start  │                 │
│  ./mrrc_remote_ │                      │  ./mrrc_control │
│     start.sh    │                      │     .sh         │
└─────────────────┘                      └────────┬────────┘
                                                  │
                                                  ▼
                                          ┌─────────────────┐
                                          │  MRRC Services  │
                                          │  • rigctld      │
                                          │  • MRRC         │
                                          │  • atr1000_proxy│
                                          └─────────────────┘
```

**功能**:
- `start` - 远程启动所有服务
- `stop` - 远程停止服务
- `status` - 查询服务状态
- `logs` - 查看服务日志

---

## 📡 ATR-1000 天调数据流

### 智能学习流程

```
┌──────────┐     TX Start      ┌─────────────┐
│  User    │ ----------------> │  MRRC       │
│  Press   │                   │  Backend    │
│  PTT     │                   └──────┬──────┘
└──────────┘                          │
                                      ▼
                              ┌─────────────┐
                              │  Sync Freq  │
                              │  to Proxy   │
                              └──────┬──────┘
                                     │
                                     ▼
┌──────────┐    500ms采样    ┌─────────────┐    SWR≤1.5?   ┌──────────┐
│  Save    │ <------------- │  ATR-1000   │ <----------- │  Sample  │
│  Params  │   (5次确认)     │   Proxy     │   & Power>5W │  SWR/PWR │
│  to JSON │                │             │              │          │
└──────────┘                └─────────────┘              └──────────┘
```

### 快速调谐流程

```
┌──────────┐    Freq Change    ┌─────────────┐    Found?    ┌──────────┐
│  User    │ ----------------> │  Proxy      │ ----------> │  Apply   │
│  Change  │                   │  Lookup     │  (±10kHz)   │  Params  │
│  Band    │                   │  JSON       │             │  to ATU  │
└──────────┘                   └─────────────┘             └──────────┘
                                      │
                                      │ Not Found
                                      ▼
                               ┌─────────────┐
                               │  Wait for   │
                               │  Manual Tune│
                               └─────────────┘
```

---

## 📊 关键性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| TX延迟 | ~65ms | 浏览器→电台 |
| RX延迟 | ~51ms | 电台→浏览器 |
| TX→RX切换 | <100ms | 含WDSP处理 |
| PTT可靠性 | 99%+ | 预热帧机制 |
| WDSP处理 | <20ms | 48kHz采样 |
| WDSP降噪 | 15-20dB | NR2频谱降噪 |
| ATR-1000轮询 | 15s/5s/0.5s | 动态调整 |
| API响应 | <50ms | RESTful API |

---

## 🔗 相关文档

| 文档 | 说明 |
|------|------|
| [README_CN.md](README_CN.md) | 完整中文文档 |
| [README.md](README.md) | English Documentation |
| [DSP.md](DSP.md) | WDSP数字信号处理详解 |
| [docs/System_Architecture_Design.md](docs/System_Architecture_Design.md) | 详细系统架构设计 |
| [docs/ATR1000_Tuner_Auto_Learning.md](docs/ATR1000_Tuner_Auto_Learning.md) | ATR-1000天调文档 |
| [CHANGELOG.md](CHANGELOG.md) | 版本更新日志 |

---

**MRRC - Mobile Remote Radio Control**  
*V4.8.0 | Amateur Radio, Anytime, Anywhere.*
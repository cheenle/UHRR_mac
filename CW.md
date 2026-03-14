# CW 解码与回复系统架构设计方案

**版本**: V1.0  
**日期**: 2026-03-11  
**状态**: 设计阶段  

---

## 目录

1. [概述](#概述)
2. [技术调研](#技术调研)
3. [系统架构](#系统架构)
4. [核心组件](#核心组件)
5. [用户界面](#用户界面)
6. [HAM Radio 规范](#ham-radio-规范)
7. [实施计划](#实施计划)
8. [技术细节](#技术细节)
9. [文件清单](#文件清单)
10. [风险评估](#风险评估)

---

## 概述

### 功能目标

为 MRRC 系统新增专用的 CW (Continuous Wave / 摩尔斯电码) 通信页面，实现：

- **实时解码**: 基于深度学习的 CW 音频解码，准确率 >98%
- **智能回复**: 根据 HAM Radio 规范自动生成回复建议
- **完整控制**: 频率调整、波段选择、滤波器切换 (500Hz/1KHz/2.4KHz)
- **交互发送**: 文本编辑后转换为摩尔斯码发送

### 设计理念

**Browser-First AI**: 将 AI 解码能力下沉到浏览器端，零后端依赖，降低服务器负载，支持离线使用。

---

## 技术调研

### CW 解码开源方案对比

| 方案 | morseangel | web-deep-cw-decoder | morse-deep-learning |
|------|------------|---------------------|---------------------|
| **作者** | f4exb | e04 | MaorAssayag |
| **技术栈** | PyTorch LSTM | ONNX Runtime Web | PyTorch LSTM + Faster R-CNN |
| **模型大小** | ~5MB | **2MB (500k 参数)** | 41M 参数 |
| **部署位置** | 后端 Python | **浏览器端** | 后端 Python |
| **实时性** | 优秀 (<50ms) | 优秀 | 良好 |
| **准确性** | CER < 2% @ SNR>-5dB | 高精度 (实测优秀) | CER < 2% |
| **依赖** | PyTorch + PyAudio | ONNX Runtime Web | PyTorch + CUDA |
| **推荐度** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

### 推荐方案: 双模式架构

**设计决策**: 支持两种解码模式，用户可自由切换

| 模式 | 方案 | 适用场景 |
|------|------|----------|
| **前端解码** | web-deep-cw-decoder (ONNX) | 日常通信、低延迟、网络不稳定 |
| **后端解码** | morse-deep-learning (PyTorch) | 弱信号、高噪声、DX 通信 |

**选择理由**:

1. **灵活性**: 用户根据网络状况和信号质量选择
2. **降级方案**: 当浏览器不支持 ONNX 时自动切换后端
3. **性能互补**: 前端低延迟 vs 后端高准确率
4. **双阶段优势**: 后端 Faster R-CNN 检测 + BiLSTM 解码，适合复杂信号环境

### 前端解码: web-deep-cw-decoder

**适用场景**: 日常通信、移动设备、低延迟需求

**优势**:
- 超轻量模型: 仅 2MB
- 零后端依赖
- 推理延迟 <50ms

**技术架构**:

```
音频输入 (16kHz) → 频谱图生成 (STFT) → CRNN 编码器 → CTC 解码器 → 文本输出
```

### 后端解码: morse-deep-learning (MaorAssayag)

**适用场景**: 弱信号、高噪声、DX 通信、多信号环境

**优势**:
- **双阶段架构**: Faster R-CNN 检测 + BiLSTM 解码
- **大规模训练**: 5000万字符训练数据
- **高准确率**: CER < 2% @ SNR > -5dB
- **自动适应**: 无需手动设置 WPM

**技术架构**:

```
音频输入 → 频谱图生成 → Faster R-CNN (检测信号位置) → 裁剪 → BiLSTM+CTC (解码) → 文本输出
```

**模型组成**:

| 组件 | 架构 | 参数量 | 功能 |
|------|------|--------|------|
| 检测器 | Faster R-CNN ResNet50 | 41M | 检测信号起始/结束位置 |
| 解码器 | BiLSTM + CTC | 740K | 端到端字符识别 |
| **总计** | | **41.7M** | |

---

## 系统架构

### 双模式解码架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         浏览器端 (Mobile/PC)                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Decoder Mode Selector                         │  │
│  │                    [前端解码 ▼] [后端解码 ▼]                      │  │
│  └──────────────┬─────────────────────────────┬──────────────────────┘  │
│                 │                             │                         │
│                 ▼                             ▼                         │
│  ┌──────────────────────┐      ┌──────────────────────────────────┐  │
│  │   前端解码路径        │      │         后端解码路径              │  │
│  │  (ONNX Runtime)      │      │     (WebSocket → Python)         │  │
│  ├──────────────────────┤      ├──────────────────────────────────┤  │
│  │ ┌──────────────────┐ │      │                                  │  │
│  │ │ RX Audio Worklet │ │      │  ┌──────────────┐   ┌─────────┐  │  │
│  │ │    (16kHz)       │─┼──┐   │  │  Audio Buffer │   │ WebSocket│  │  │
│  │ └──────────────────┘ │  │   │  │  (队列)       │◄──│  /WSCW   │  │  │
│  │          │           │  │   │  └──────┬───────┘   └─────┬───┘  │  │
│  │          ▼           │  │   │         │                 │      │  │
│  │ ┌──────────────────┐ │  │   │         ▼                 ▼      │  │
│  │ │ Spectrogram      │ │  │   │  ┌─────────────┐   ┌──────────┐ │  │
│  │ │ Generator        │ │  │   │  │ morseangel  │   │ 后端 Python│ │  │
│  │ └──────────────────┘ │  │   │  │ Decoder     │   │ cw_decoder│ │  │
│  │          │           │  │   │  └──────┬──────┘   └─────┬────┘ │  │
│  │          ▼           │  │   │         │                 │      │  │
│  │ ┌──────────────────┐ │  └───┼─────────┘                 ▼      │  │
│  │ │ ONNX Model       │ │      │                    ┌──────────┐  │  │
│  │ │ Inference        │ │      │                    │ 文本输出  │  │  │
│  │ └──────────────────┘ │      │                    └────┬─────┘  │  │
│  │          │           │      │                         │        │  │
│  │          ▼           │      └─────────────────────────┘        │  │
│  │ ┌──────────────────┐ │                                         │  │
│  │ │ CTC Decoder      │ │                                         │  │
│  │ └──────────────────┘ │                                         │  │
│  └──────────────────────┘                                         │  │
│                 │                                                  │  │
│                 ▼                                                  │  │
│  ┌──────────────────────────────────────────────────────────────┐ │  │
│  │                      Decoded Text                              │ │  │
│  │                      (统一输出)                                │ │  │
│  └──────────────────────────────────────────────────────────────┘ │  │
│                                   │                                │  │
│                                   ▼                                │  │
│  ┌──────────────────────────────────────────────────────────────┐ │  │
│  │                      QSO Context Manager                       │ │  │
│  │                    (状态机 + 回复生成)                          │ │  │
│  └──────────────────────────────────────────────────────────────┘ │  │
└─────────────────────────────────────────────────────────────────────────┘
```
│  │  ┌─────────┐  │    └──────────────┘    │  Decoded Text    │         │
│  │  │Reply    │  │                        │  Buffer          │         │
│  │  │Editor   │  │                        └────────┬─────────┘         │
│  │  └─────────┘  │                                 │                   │
│  │       │       │                        ┌────────▼─────────┐         │
│  │       ▼       │                        │  QSO Context     │         │
│  │  ┌─────────┐  │                        │  Manager         │         │
│  │  │Send CW  │──┼───────────────────────►│  (状态机)         │         │
│  │  │Button   │  │                        └────────┬─────────┘         │
│  │  └─────────┘  │                                 │                   │
│  │       │       │                        ┌────────▼─────────┐         │
│  └───────┼───────┘                        │  Text-to-Morse   │         │
│          │                               │  Converter       │         │
│          │                               └────────┬─────────┘         │
│          │                                        │                   │
│          │                               ┌────────▼─────────┐         │
│          └──────────────────────────────►│  TX Audio        │         │
│                                          │  (Morse Tone)    │         │
│                                          └──────────────────┘         │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                          后端 (Python/Tornado)                          │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
│  │  WS_CWHandler │    │  Audio RX    │    │  Station Control         │  │
│  │  (WebSocket)  │◄───│  (16k PCM)   │    │  - setMode:CW            │  │
│  │               │    │              │    │  - setFilter:500Hz       │  │
│  └──────────────┘    └──────────────┘    │  - setKeyerSpeed         │  │
│         ▲                                 │  - setCWOffset           │  │
│         │                                 └──────────────────────────┘  │
│  ┌──────┴───────┐                                                      │
│  │  Hamlib      │                                                      │
│  │  rigctld     │                                                      │
│  └──────────────┘                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### 数据流图 (双模式)

#### 前端解码模式

```
电台音频
    │
    ▼
┌─────────────┐
│ PyAudio RX  │ (后端)
└──────┬──────┘
       │ 16kHz PCM
       ▼
┌─────────────┐
│ WebSocket   │
│ /WSCTRX     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ RX Worklet  │ (浏览器)
└──────┬──────┘
       │ Float32Array
       ├────────────────┐
       ▼                ▼
┌─────────────┐   ┌─────────────┐
│ 扬声器播放   │   │ CW Decoder  │
│             │   │ (ONNX)      │
└─────────────┘   └──────┬──────┘
                         │ 频谱图
                         ▼
                  ┌─────────────┐
                  │ ONNX Model  │
                  └──────┬──────┘
                         │ 字符概率
                         ▼
                  ┌─────────────┐
                  │ CTC Decode  │
                  └──────┬──────┘
                         │ 文本
                         ▼
                  ┌─────────────┐
                  │ QSO Manager │
                  └─────────────┘
```

#### 后端解码模式

```
电台音频
    │
    ▼
┌─────────────┐
│ PyAudio RX  │ (后端)
└──────┬──────┘
       │ 16kHz PCM
       ▼
┌─────────────┐     ┌─────────────────┐
│ WebSocket   │     │  morseangel     │
│ /WSCTRX     │────►│  Decoder Thread │
└──────┬──────┘     │  (PyTorch LSTM) │
       │             └────────┬────────┘
       │                      │ 解码文本
       │                      ▼
       │             ┌─────────────────┐
       │             │ 文本缓存/队列   │
       │             └────────┬────────┘
       │                      │
       ▼                      ▼
┌─────────────┐      ┌───────────────┐
│ RX Worklet  │      │  WebSocket    │
│ (扬声器)    │      │  /WSCW        │
└─────────────┘      └───────┬───────┘
                             │
                             ▼
                      ┌─────────────┐
                      │ QSO Manager │
                      │ (浏览器端)  │
                      └─────────────┘
```

---

## 核心组件

### 0. 解码模式管理器

**文件**: `www/cw_mode_manager.js`

**职责**: 管理前端/后端解码模式切换

```javascript
class CWModeManager {
  constructor() {
    this.mode = 'frontend'; // 'frontend' | 'backend'
    this.frontendDecoder = null;
    this.backendDecoder = null;
    this.audioRouter = null;
    this.onTextDecoded = null;
  }
  
  async init() {
    // 初始化前端解码器
    this.frontendDecoder = new CWDecoder();
    
    // 初始化后端解码器连接
    this.backendDecoder = new CWBackendDecoder();
    
    // 默认使用前端解码
    await this.setMode('frontend');
  }
  
  async setMode(mode) {
    if (mode === this.mode) return;
    
    console.log(`切换解码模式: ${this.mode} -> ${mode}`);
    
    // 停止当前模式
    await this.stopCurrentMode();
    
    // 启动新模式
    if (mode === 'frontend') {
      await this.startFrontendMode();
    } else if (mode === 'backend') {
      await this.startBackendMode();
    }
    
    this.mode = mode;
    
    // 通知 UI 更新
    this.onModeChanged?.(mode);
  }
  
  async startFrontendMode() {
    // 初始化 ONNX 模型
    if (!this.frontendDecoder.isInitialized) {
      await this.frontendDecoder.init();
    }
    
    // 音频直接流向 ONNX 解码器
    this.audioRouter.setTarget(this.frontendDecoder);
    
    // 设置解码回调
    this.frontendDecoder.onDecode = (text) => {
      this.onTextDecoded?.(text, 'frontend');
    };
  }
  
  async startBackendMode() {
    // 连接到后端解码 WebSocket
    await this.backendDecoder.connect();
    
    // 音频流向 WebSocket
    this.audioRouter.setTarget(this.backendDecoder);
    
    // 设置解码回调
    this.backendDecoder.onMessage = (msg) => {
      if (msg.type === 'decoded') {
        this.onTextDecoded?.(msg.text, 'backend');
      }
    };
  }
  
  async stopCurrentMode() {
    if (this.mode === 'frontend') {
      this.audioRouter.setTarget(null);
    } else if (this.mode === 'backend') {
      await this.backendDecoder.disconnect();
    }
  }
  
  // 自动选择最佳模式
  async autoSelectMode() {
    // 检查 ONNX 支持
    const onnxSupported = await this.checkONNXSupport();
    
    if (!onnxSupported) {
      console.log('ONNX 不支持，自动切换到后端解码');
      await this.setMode('backend');
      return;
    }
    
    // 检查网络状况
    const networkQuality = await this.checkNetworkQuality();
    
    if (networkQuality === 'poor') {
      console.log('网络质量差，使用前端解码');
      await this.setMode('frontend');
    } else {
      // 默认使用前端解码
      await this.setMode('frontend');
    }
  }
  
  async checkONNXSupport() {
    try {
      // 检查 ONNX Runtime Web 是否可用
      return typeof ort !== 'undefined' && 
             ort.InferenceSession !== undefined;
    } catch (e) {
      return false;
    }
  }
  
  async checkNetworkQuality() {
    // 通过 WebSocket 延迟判断网络质量
    const latency = await this.backendDecoder.measureLatency();
    if (latency < 50) return 'good';
    if (latency < 150) return 'fair';
    return 'poor';
  }
}
```

### 1. CW Decoder 模块 (前端)

**文件**: `www/cw_decoder.js`

**职责**: ONNX 模型加载和推理

```javascript
class CWDecoder {
  constructor() {
    this.session = null;
    this.sampleRate = 16000;
    this.fftSize = 512;
    this.hopLength = 256;
    this.buffer = new Float32Array(0);
    this.alphabet = 'abcdefghijklmnopqrstuvwxyz0123456789+/=';
  }
  
  async init(modelPath = '/models/cw_decoder.onnx') {
    this.session = await ort.InferenceSession.create(modelPath, {
      executionProviders: ['wasm'],
      graphOptimizationLevel: 'all'
    });
  }
  
  // 处理音频块 (从 Worklet 接收)
  processAudio(audioChunk) {
    // 1. 拼接缓冲区
    const newBuffer = new Float32Array(this.buffer.length + audioChunk.length);
    newBuffer.set(this.buffer);
    newBuffer.set(audioChunk, this.buffer.length);
    this.buffer = newBuffer;
    
    // 2. 检查是否有足够数据生成频谱图
    if (this.buffer.length < this.fftSize) return null;
    
    // 3. 生成频谱图
    const spectrogram = this.generateSpectrogram(this.buffer);
    
    // 4. 运行推理
    const output = this.runInference(spectrogram);
    
    // 5. CTC 解码
    const text = this.ctcDecode(output);
    
    // 6. 滑动窗口处理
    this.buffer = this.buffer.slice(-this.fftSize);
    
    return text;
  }
  
  generateSpectrogram(audioData) {
    // STFT 实现或使用 Web Audio API AnalyserNode
    const frames = [];
    for (let i = 0; i < audioData.length - this.fftSize; i += this.hopLength) {
      const frame = audioData.slice(i, i + this.fftSize);
      const windowed = this.applyHannWindow(frame);
      const fft = this.fft(windowed);
      frames.push(fft);
    }
    return this.normalize(frames);
  }
  
  ctcDecode(probabilities) {
    // 贪婪解码或波束搜索
    const greedy = true;
    if (greedy) {
      return this.greedyDecode(probabilities);
    }
    return this.beamSearchDecode(probabilities);
  }
}
```

### 2. QSO 上下文管理器

**文件**: `www/cw_qso.js`

**职责**: HAM Radio 通信状态机管理

```javascript
class CQSOContext {
  constructor(myCallsign) {
    this.myCallsign = myCallsign;
    this.state = 'IDLE'; // IDLE | RX_CALL | EXCHANGE | COMPLETE
    this.remoteCallsign = null;
    this.rstReceived = null;
    this.rstSent = '599';
    this.nameReceived = null;
    this.nameSent = null;
    this.qthReceived = null;
    this.qthSent = null;
    this.history = [];
    this.timestamp = null;
  }
  
  // 正则表达式模式
  static PATTERNS = {
    CALLSIGN: /\b([A-Z]{1,2}|[0-9][A-Z]|[A-Z][0-9])([0-9][A-Z]{1,3})\b/gi,
    RST: /\b([1-5][1-9][1-9])\b/g,
    QTH: /\bQTH\s+([A-Z]{2,20})\b/gi,
    NAME: /\bNAME\s+([A-Z]{2,20})\b/gi,
    DE: /\bDE\s+([A-Z0-9]+)\b/gi,
    QCODE: /\b(QRV|QTH|QSO|QSL|AGN|RPT|AR|SK|KN|BK)\b/gi
  };
  
  // 处理解码文本
  processText(text) {
    this.history.push({
      text: text,
      timestamp: Date.now(),
      direction: 'RX'
    });
    
    // 提取呼号
    const callsigns = text.match(CQSOContext.PATTERNS.CALLSIGN);
    if (callsigns && !this.remoteCallsign) {
      // 排除自己的呼号
      this.remoteCallsign = callsigns.find(c => 
        c.toUpperCase() !== this.myCallsign.toUpperCase()
      );
      if (this.remoteCallsign) {
        this.transitionTo('RX_CALL');
      }
    }
    
    // 提取 RST
    const rstMatch = text.match(CQSOContext.PATTERNS.RST);
    if (rstMatch && !this.rstReceived) {
      this.rstReceived = rstMatch[0];
    }
    
    // 提取 QTH
    const qthMatch = text.match(CQSOContext.PATTERNS.QTH);
    if (qthMatch && !this.qthReceived) {
      this.qthReceived = qthMatch[1];
    }
    
    // 提取 NAME
    const nameMatch = text.match(CQSOContext.PATTERNS.NAME);
    if (nameMatch && !this.nameReceived) {
      this.nameReceived = nameMatch[1];
    }
    
    // 检测结束标记
    if (text.includes('73') || text.includes('SK')) {
      this.transitionTo('COMPLETE');
    }
    
    return this.generateReply();
  }
  
  transitionTo(newState) {
    console.log(`QSO State: ${this.state} -> ${newState}`);
    this.state = newState;
    this.timestamp = Date.now();
  }
  
  // 生成回复建议
  generateReply() {
    switch(this.state) {
      case 'IDLE':
        return this.generateCQReply();
      case 'RX_CALL':
        return this.generateExchangeReply();
      case 'EXCHANGE':
        return this.generateConfirmReply();
      case 'COMPLETE':
        return '73 TU SK';
      default:
        return '';
    }
  }
  
  generateCQReply() {
    // 回答 CQ
    return `${this.remoteCallsign} DE ${this.myCallsign} UR ${this.rstSent} ${this.rstSent} ` +
           `NAME ${this.nameSent || 'OP'} ${this.nameSent || 'OP'} ` +
           `QTH ${this.qthSent || 'CHINA'} ${this.qthSent || 'CHINA'} HW?`;
  }
  
  generateExchangeReply() {
    // 确认交换
    return `R R UR ${this.rstReceived} ${this.nameReceived} ${this.qthReceived} ` +
           `OK TNX FER CALL`;
  }
  
  generateConfirmReply() {
    // 结束 QSO
    return `R R TNX FER NICE QSO ES GUD LUCK 73 73 ${this.myCallsign} SK`;
  }
}
```

### 3. 摩尔斯码编解码器

**文件**: `www/cw_morse.js`

**职责**: 文本与摩尔斯码互转

```javascript
const MORSE_CODE = {
  'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.',
  'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---',
  'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---',
  'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
  'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--',
  'Z': '--..',
  '1': '.----', '2': '..---', '3': '...--', '4': '....-', '5': '.....',
  '6': '-....', '7': '--...', '8': '---..', '9': '----.', '0': '-----',
  '.': '.-.-.-', ',': '--..--', '?': '..--..', '/': '-..-.', '@': '.--.-.',
  ' ': ' ' // 字间距
};

const REVERSE_MORSE = Object.fromEntries(
  Object.entries(MORSE_CODE).map(([k, v]) => [v, k])
);

class CWMorseCodec {
  // 文本转摩尔斯
  textToMorse(text) {
    return text.toUpperCase()
      .split('')
      .map(char => MORSE_CODE[char] || '')
      .join(' ');
  }
  
  // 摩尔斯转文本
  morseToText(morse) {
    return morse
      .split(' ')
      .map(code => REVERSE_MORSE[code] || '')
      .join('');
  }
  
  // 摩尔斯转时序 (用于音频生成)
  morseToTiming(morse, wpm = 20) {
    const dotDuration = 1.2 / wpm; // 秒
    const dahDuration = dotDuration * 3;
    const charSpace = dotDuration * 3;
    const wordSpace = dotDuration * 7;
    
    const timing = [];
    const chars = morse.split('');
    
    for (let i = 0; i < chars.length; i++) {
      const char = chars[i];
      
      if (char === '.') {
        timing.push({ type: 'tone', duration: dotDuration });
        timing.push({ type: 'silence', duration: dotDuration });
      } else if (char === '-') {
        timing.push({ type: 'tone', duration: dahDuration });
        timing.push({ type: 'silence', duration: dotDuration });
      } else if (char === ' ') {
        timing.push({ type: 'silence', duration: charSpace });
      }
    }
    
    return timing;
  }
}
```

### 4. CW 发送器

**文件**: `www/cw_transmit.js`

**职责**: 生成摩尔斯音频并控制 PTT

```javascript
class CWTransmitter {
  constructor(audioContext, wsConnection) {
    this.audioContext = audioContext;
    this.ws = wsConnection;
    this.wpm = 20;
    this.toneFrequency = 600; // Hz
    this.codec = new CWMorseCodec();
    this.isTransmitting = false;
  }
  
  // 设置发送参数
  setSpeed(wpm) {
    this.wpm = Math.max(10, Math.min(40, wpm));
  }
  
  setTone(freq) {
    this.toneFrequency = freq;
  }
  
  // 发送文本
  async sendText(text) {
    if (this.isTransmitting) {
      throw new Error('Already transmitting');
    }
    
    this.isTransmitting = true;
    
    try {
      // 1. PTT ON
      this.ws.send('setPTT:1');
      await this.delay(50); // PTT 延迟
      
      // 2. 生成摩尔斯音频
      const morse = this.codec.textToMorse(text);
      const timing = this.codec.morseToTiming(morse, this.wpm);
      
      // 3. 生成并发送音频
      await this.sendMorseAudio(timing);
      
      // 4. PTT OFF
      await this.delay(50);
      this.ws.send('setPTT:0');
      
    } finally {
      this.isTransmitting = false;
    }
  }
  
  // 生成摩尔斯音频
  async sendMorseAudio(timing) {
    const sampleRate = 16000;
    
    // 计算总时长
    const totalDuration = timing.reduce((sum, t) => sum + t.duration, 0);
    const numSamples = Math.ceil(totalDuration * sampleRate);
    
    // 创建音频缓冲区
    const buffer = this.audioContext.createBuffer(1, numSamples, sampleRate);
    const data = buffer.getChannelData(0);
    
    let sampleIndex = 0;
    
    for (const event of timing) {
      const eventSamples = Math.floor(event.duration * sampleRate);
      
      if (event.type === 'tone') {
        // 生成正弦波
        for (let i = 0; i < eventSamples; i++) {
          const t = i / sampleRate;
          // 添加淡入淡出避免咔哒声
          const envelope = this.getEnvelope(i, eventSamples);
          data[sampleIndex + i] = Math.sin(2 * Math.PI * this.toneFrequency * t) * envelope * 0.8;
        }
      } else {
        // 静音
        for (let i = 0; i < eventSamples; i++) {
          data[sampleIndex + i] = 0;
        }
      }
      
      sampleIndex += eventSamples;
    }
    
    // 转换为 Int16 并发送
    const int16Data = this.floatToInt16(data);
    this.sendAudioData(int16Data);
  }
  
  getEnvelope(sample, totalSamples) {
    const fadeSamples = 10; // 10 samples fade
    if (sample < fadeSamples) {
      return sample / fadeSamples;
    } else if (sample > totalSamples - fadeSamples) {
      return (totalSamples - sample) / fadeSamples;
    }
    return 1.0;
  }
  
  floatToInt16(floatArray) {
    const int16Array = new Int16Array(floatArray.length);
    for (let i = 0; i < floatArray.length; i++) {
      const s = Math.max(-1, Math.min(1, floatArray[i]));
      int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return int16Array;
  }
  
  sendAudioData(int16Data) {
    // 分块发送 (每块 320 samples = 20ms @ 16kHz)
    const chunkSize = 320;
    for (let i = 0; i < int16Data.length; i += chunkSize) {
      const chunk = int16Data.slice(i, i + chunkSize);
      const buffer = chunk.buffer;
      this.ws.send(buffer);
    }
  }
  
  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

### 5. 滤波器控制器

**文件**: `www/cw_filter.js`

**职责**: CW 滤波器切换 (500Hz/1KHz/2.4KHz)

```javascript
class CWFilterController {
  constructor(audioContext) {
    this.audioContext = audioContext;
    this.filterNode = null;
    this.currentBandwidth = '500';
  }
  
  createFilter(bandwidth) {
    // 移除旧滤波器
    if (this.filterNode) {
      this.filterNode.disconnect();
    }
    
    // 创建新的带通滤波器
    this.filterNode = this.audioContext.createBiquadFilter();
    this.filterNode.type = 'bandpass';
    
    const centerFreq = bandwidth === '2.4K' ? 1000 : 600;
    
    switch(bandwidth) {
      case '500':
        this.filterNode.frequency.value = 600;
        this.filterNode.Q.value = 1.2;
        break;
      case '1K':
        this.filterNode.frequency.value = 600;
        this.filterNode.Q.value = 0.6;
        break;
      case '2.4K':
        this.filterNode.frequency.value = 1000;
        this.filterNode.Q.value = 0.4;
        break;
    }
    
    this.currentBandwidth = bandwidth;
    return this.filterNode;
  }
  
  // 发送到后端同步
  async syncWithBackend(ws, bandwidth) {
    // 发送滤波器切换命令
    ws.send(`setFilterWidth:${bandwidth}`);
    
    // 后端需要实现对应的 hamlib 命令
    // 例如: rigctl -m 229 -r /dev/ttyUSB0 W CW ${bandwidth}
  }
}
```

---

## 用户界面

### 界面布局

```
┌─────────────────────────────────────────┐
│  🔙  CW Mode              [POWER ⏻]    │  ← 标题栏
├─────────────────────────────────────────┤
│  7.053.000 kHz     CW     500Hz [FILT]  │  ← 频率/模式/滤波器
├─────────────────────────────────────────┤
│  [前端解码 ▼] [信号强度 ●●●○○]           │  ← 解码模式选择 + 信号指示
├─────────────────────────────────────────┤
│  ┌─────────────────────────────────┐   │
│  │  ☰ Band  |  ▶ 20m  |  ▶ 40m   │   │  ← 波段选择菜单
│  └─────────────────────────────────┘   │
├─────────────────────────────────────────┤
│  ┌─────────────────────────────────┐   │
│  │                                 │   │
│  │     [频谱显示区域]                │   │
│  │     600Hz 中心频率               │   │
│  │     实时显示 CW 信号             │   │
│  │                                 │   │
│  └─────────────────────────────────┘   │
├─────────────────────────────────────────┤
│  ┌─────────────────────────────────┐   │
│  │  [10:23:45] CQ CQ CQ DE BH4XXX │   │  ← 解码文本显示区
│  │  [10:23:52] BH4XXX DE BH4YYY   │   │    (带时间戳，可滚动)
│  │  [10:23:58] UR 599 599 NAME...  │   │
│  └─────────────────────────────────┘   │
├─────────────────────────────────────────┤
│  ┌─────────────────────────────────┐   │
│  │  [AI建议]:                      │   │  ← AI 回复建议
│  │  BH4YYY DE BH4XXX R R UR 599... │   │
│  │                    [应用建议 ▼]  │   │
│  └─────────────────────────────────┘   │
├─────────────────────────────────────────┤
│  ┌─────────────────────────────────┐   │
│  │  BH4YYY DE BH4XXX R R UR 599... │   │  ← 回复编辑区
│  │                                 │   │    (用户可修改)
│  └─────────────────────────────────┘   │
├─────────────────────────────────────────┤
│  [▶ SEND CW]     [PTT 🔴]              │  ← 发送和 PTT 按钮
├─────────────────────────────────────────┤
│  [500Hz] [1KHz] [2.4KHz]  [Speed: 20]  │  ← 滤波器/速度控制
└─────────────────────────────────────────┘
```

### 交互状态图

```
页面加载
    │
    ▼
┌─────────┐
│ INITIAL │
└────┬────┘
     │
     ├──► 加载 ONNX 模型 ──► 显示进度条
     │
     ├──► 连接 WebSocket ──► 连接成功后
     │
     └──► 设置模式:CW ──► setMode:CW
              │
              ▼
┌─────────────────────┐
│     RX_LISTEN       │ ◄──── 默认状态
│   (接收解码中...)     │
└──────────┬──────────┘
           │
    检测到呼号
           │
           ▼
┌─────────────────────┐
│   SUGGEST_REPLY     │
│   (显示 AI 建议)     │
└──────────┬──────────┘
           │
    用户点击 SEND
           │
           ▼
┌─────────────────────┐
│    TX_SENDING       │
│   (发送摩尔斯码)     │
└──────────┬──────────┘
           │
    发送完成
           │
           ▼
     返回 RX_LISTEN
```

---

## HAM Radio 规范

### 标准 QSO 流程

```
阶段 1: 呼叫 (Calling)
━━━━━━━━━━━━━━━━━━━━━━━━━
对方: CQ CQ CQ DE BH4XXX BH4XXX K
AI建议: [BH4XXX DE {MY_CALL} UR 599 599 NAME {NAME} {NAME} QTH {QTH} {QTH} HW?]

阶段 2: 交换信息 (Exchange)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
对方: BH4YYY DE BH4XXX UR 599 599 NAME JOHN JOHN QTH SHANGHAI SHANGHAI HW?
AI建议: [BH4XXX DE {MY_CALL} R R UR 599 NAME JOHN QTH SHANGHAI OK TNX FER CALL]

阶段 3: 确认 (Confirmation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
对方: R R TNX FER CALL UR 5NN 5NN NAME BOB BOB QTH BEIJING BEIJING
AI建议: [R R TNX FER NICE QSO 73 73 {MY_CALL} SK]

阶段 4: 结束 (Sign-off)
━━━━━━━━━━━━━━━━━━━━━━━━
对方: R R TNX FER QSO 73 73 BH4XXX SK
AI建议: [73 TU SK]
```

### 常用 Q 简语

| 简语 | 含义 | 使用场景 |
|------|------|----------|
| **CQ** | 普遍呼叫 | 呼叫任意台站 |
| **DE** | 来自/这是 | 分隔呼号 |
| **K** | 请回答 | 结束语，邀请回复 |
| **R** | 收到 | 确认收到 |
| **UR** | 你的 | Your |
| **RST** | 信号报告 | 5(可读性)9(强度)9(音调) |
| **NAME** | 名字 | 交换操作员名字 |
| **QTH** | 地理位置 | 交换地点 |
| **HW?** | 抄收了吗? | How copy? |
| **AGN** | 再来一次 | Again |
| **AR** | 信息结束 | End of message |
| **SK** | 结束联络 | Silent key |
| **KN** | 邀请指定台回答 | Go ahead (specific) |
| **BK** | 打断/回话 | Break |
| **73** | 致敬/再见 | Best regards |
| **GL** | 祝好运 | Good luck |
| **DX** | 远距离通信 | Long distance |

### 呼号识别规则

```javascript
// 国际业余无线电呼号格式
// 前缀: 1-2字符 (国家代码)
// 分区: 1位数字
// 后缀: 1-3字符

const CALLSIGN_REGEX = /\b([A-Z]{1,2}|[0-9][A-Z]|[A-Z][0-9])([0-9][A-Z]{1,3})\b/gi;

// 示例有效呼号:
// BH4XXX - 中国
// JA1XXX - 日本
// VK2XXX - 澳大利亚
// W1XXX  - 美国
// G0XXX  - 英国
```

---

## 实施计划

### Phase 1: 基础架构 (Week 1-2)

| 任务 | 文件 | 工作量 | 依赖 |
|------|------|--------|------|
| 1.1 创建 CW 页面 HTML 结构 | `www/cw.html` | 2d | - |
| 1.2 设计 CW 专用 CSS 样式 | `www/cw.css` | 2d | 1.1 |
| 1.3 获取 ONNX 模型文件 | `models/cw_decoder.onnx` | 1d | - |
| 1.4 模型加载与初始化 | `www/cw_decoder.js` | 3d | 1.3 |
| 1.5 音频流路由 | `www/cw_audio.js` | 2d | - |

**交付物**: 可加载页面的基础框架

### Phase 2: 解码核心 (Week 3-4)

| 任务 | 文件 | 工作量 | 依赖 |
|------|------|--------|------|
| 2.1 频谱图生成 (STFT) | `www/cw_spectrogram.js` | 3d | 1.4 |
| 2.2 ONNX 推理封装 | `www/cw_inference.js` | 2d | 1.4 |
| 2.3 CTC 解码实现 | `www/cw_ctc_decode.js` | 2d | 2.2 |
| 2.4 文本后处理 | `www/cw_postprocess.js` | 2d | 2.3 |
| 2.5 解码器集成测试 | - | 1d | 2.4 |

**交付物**: 实时解码功能可用

### Phase 3: QSO 管理 (Week 5-6)

| 任务 | 文件 | 工作量 | 依赖 |
|------|------|--------|------|
| 3.1 QSO 状态机实现 | `www/cw_qso.js` | 3d | - |
| 3.2 呼号提取与验证 | `www/cw_callsign.js` | 2d | 3.1 |
| 3.3 回复生成器 | `www/cw_reply.js` | 2d | 3.1 |
| 3.4 历史记录管理 | `www/cw_history.js` | 2d | 3.1 |
| 3.5 QSO 流程测试 | - | 1d | 3.4 |

**交付物**: AI 建议回复功能

### Phase 4: 发送功能 (Week 7-8)

| 任务 | 文件 | 工作量 | 依赖 |
|------|------|--------|------|
| 4.1 摩尔斯码表 | `www/cw_morse.js` | 1d | - |
| 4.2 时序生成器 | `www/cw_timing.js` | 2d | 4.1 |
| 4.3 音频生成 (Tone) | `www/cw_tone.js` | 2d | 4.2 |
| 4.4 PTT 集成 | `www/cw_transmit.js` | 2d | 4.3 |
| 4.5 速度控制 | `www/cw_speed.js` | 1d | 4.4 |

**交付物**: 完整的发送功能

### Phase 5: 后端集成 (Week 9)

| 任务 | 文件 | 工作量 | 依赖 |
|------|------|--------|------|
| 5.1 扩展 WebSocket 命令 | `MRRC` | 2d | - |
| 5.2 滤波器控制后端 | `MRRC` | 1d | 5.1 |
| 5.3 侧音频率设置 | `MRRC` | 1d | 5.1 |
| 5.4 Keyer 速度同步 | `MRRC` | 1d | 5.1 |
| 5.5 集成测试与调试 | - | 2d | 全部 |

**交付物**: 完整可用的 CW 页面

### 里程碑时间线

```
Week 1-2:  [████] Phase 1 - 基础架构
Week 3-4:  [████] Phase 2 - 解码核心
Week 5-6:  [████] Phase 3 - QSO 管理
Week 7-8:  [████] Phase 4 - 发送功能
Week 9:    [██]   Phase 5 - 后端集成 + 测试
```

**总计**: 9 周 (可并行压缩至 5-6 周)

---

## 技术细节

### 1. 音频流分流

修改 `www/rx_worklet_processor.js`:

```javascript
class RXWorkletProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.cwDecoderPort = null;
    
    // 监听来自主线程的消息
    this.port.onmessage = (event) => {
      if (event.data.type === 'registerCWDecoder') {
        this.cwDecoderPort = event.data.port;
      }
    };
  }
  
  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    
    const audioData = input[0];
    
    // 原有: 发送到扬声器
    const output = outputs[0];
    for (let channel = 0; channel < output.length; channel++) {
      output[channel].set(audioData);
    }
    
    // 新增: 发送到 CW 解码器 (通过 MessageChannel)
    if (this.cwDecoderPort) {
      // 复制数据避免冲突
      const audioCopy = new Float32Array(audioData);
      this.cwDecoderPort.postMessage({
        type: 'audio',
        data: audioCopy
      }, [audioCopy.buffer]);
    }
    
    return true;
  }
}
```

### 2. ONNX 模型加载优化

```javascript
// 延迟加载策略
class ModelLoader {
  static async loadWithProgress(url, onProgress) {
    const response = await fetch(url);
    const contentLength = +response.headers.get('Content-Length');
    
    const reader = response.body.getReader();
    const chunks = [];
    let received = 0;
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      chunks.push(value);
      received += value.length;
      
      if (onProgress) {
        onProgress(received / contentLength);
      }
    }
    
    // 合并 chunks
    const blob = new Blob(chunks);
    const arrayBuffer = await blob.arrayBuffer();
    
    return arrayBuffer;
  }
}

// 使用示例
async function initDecoder() {
  showLoading('Loading CW Decoder Model (2MB)...');
  
  const modelData = await ModelLoader.loadWithProgress(
    '/models/cw_decoder.onnx',
    (progress) => {
      updateLoadingProgress(Math.round(progress * 100));
    }
  );
  
  const session = await ort.InferenceSession.create(modelData, {
    executionProviders: ['wasm'],
    wasmOptions: {
      numThreads: 4 // 多线程加速
    }
  });
  
  hideLoading();
  return session;
}
```

### 3. 滤波器实现细节

```javascript
// 双二阶带通滤波器
function createCWFilter(audioContext, bandwidth, centerFreq = 600) {
  const filter = audioContext.createBiquadFilter();
  filter.type = 'bandpass';
  
  // 计算 Q 值: Q = f0 / BW
  let bw;
  switch(bandwidth) {
    case '500': bw = 500; break;
    case '1K': bw = 1000; break;
    case '2.4K': bw = 2400; break;
    default: bw = 500;
  }
  
  filter.frequency.value = centerFreq;
  filter.Q.value = centerFreq / bw;
  
  return filter;
}

// 或使用级联滤波器获得更陡的滚降
function createSteepCWFilter(audioContext, bandwidth) {
  const lowpass = audioContext.createBiquadFilter();
  lowpass.type = 'lowpass';
  
  const highpass = audioContext.createBiquadFilter();
  highpass.type = 'highpass';
  
  const center = 600;
  const halfBw = bandwidth / 2;
  
  lowpass.frequency.value = center + halfBw;
  highpass.frequency.value = center - halfBw;
  
  // 串联: input -> highpass -> lowpass -> output
  return { highpass, lowpass };
}
```

### 4. WebSocket 消息格式

**新增命令**:

```javascript
// 客户端 -> 服务端
{
  "setMode": "CW",           // 设置模式为 CW
  "setFilterWidth": "500",   // 设置滤波器带宽: 500/1000/2400
  "setKeyerSpeed": 25,       // 设置 Keyer 速度: 10-40 WPM
  "setCWTone": 600,          // 设置侧音频率: 400-1000 Hz
  "setCWOffset": 600,        // 设置 CW 偏移频率
  "setPTT": 1                // PTT 控制
}

// 服务端 -> 客户端
{
  "mode": "CW",
  "filterWidth": "500",
  "keyerSpeed": 25,
  "cwTone": 600
}
```

---

## 文件清单

### 新增文件 (18个)

```
www/
├── cw.html                    # CW 主页面
├── cw.css                     # CW 专用样式
├── cw_main.js                 # 主入口和初始化
├── cw_mode_manager.js         # 解码模式管理器 (前端/后端切换)
├── cw_decoder.js              # ONNX 前端解码器封装
├── cw_backend_decoder.js      # 后端解码器 WebSocket 客户端
├── cw_spectrogram.js          # 频谱图生成
├── cw_inference.js            # 模型推理
├── cw_ctc_decode.js           # CTC 解码
├── cw_postprocess.js          # 文本后处理
├── cw_qso.js                  # QSO 状态机
├── cw_reply.js                # 回复生成器
├── cw_callsign.js             # 呼号提取验证
├── cw_morse.js                # 摩尔斯编解码
├── cw_timing.js               # 时序生成
├── cw_transmit.js             # TX 发送控制
├── cw_filter.js               # 滤波器控制
├── cw_audio.js                # 音频路由
└── cw_history.js              # QSO 历史记录

models/
├── cw_decoder.onnx            # ONNX 前端模型 (2MB)
├── cw_decoder_config.json     # ONNX 配置
├── faster_rcnn_model.pth      # Faster R-CNN 检测模型 (41M)
└── lstm_decoder.pth           # BiLSTM 解码模型 (740K)

后端/
├── cw_decoder_backend.py      # 后端解码服务 (Tornado + morse-deep-learning)
└── cw_decoder_service.py      # 解码服务守护进程
```

### 修改文件 (5个)

```
www/
├── rx_worklet_processor.js     # 添加 CW 音频分流
├── controls.js                 # 添加 CW 模式命令处理
└── mobile_modern.html          # 添加 CW 页面入口链接

后端/
├── MRRC                        # 添加 /WSCW WebSocket 路由
├── cw_decoder_backend.py       # 集成到主 MRRC 服务
└── mrrc_control.sh             # 添加 CW 解码服务启动/停止
```

### WebSocket 路由

| 路由 | 用途 | 模式 |
|------|------|------|
| `/WSCTRX` | 主控制 + 音频 | 通用 |
| `/WSCW` | CW 后端解码 | 仅后端解码模式 |
| `/WSATR1000` | ATR-1000 功率计 | 现有 |

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **ONNX 浏览器兼容性** | 中 | 高 | 1. 提供 WebGL 后端降级<br>2. 不支持时提示使用 Chrome/Safari<br>3. 准备 morseangel 后端方案 |
| **模型推理性能不足** | 低 | 中 | 1. 降低频谱图分辨率 (128->64 bins)<br>2. 使用 WebGL 后端加速<br>3. 降低推理频率 (50ms->100ms) |
| **解码准确性不理想** | 低 | 高 | 1. 集成 morseangel 作为后端备选<br>2. 提供手动纠错界面<br>3. 增加训练数据微调模型 |
| **实时性延迟过高** | 低 | 中 | 1. 使用 Web Worker offload 解码<br>2. 降低缓冲区大小<br>3. 优化 CTC 解码算法 |
| **HAMlib CW 命令兼容性** | 中 | 中 | 1. 测试各电台型号支持情况<br>2. 提供手动设置界面<br>3. 记录兼容性矩阵 |

### 备选方案

**如果浏览器端 ONNX 不可用**:

```
浏览器 ──WebSocket──► 后端 Python ──► morseangel 解码器
                      (5MB PyTorch 模型)
```

**性能对比**:

| 方案 | 延迟 | 依赖 | 复杂度 |
|------|------|------|--------|
| 浏览器 ONNX (首选) | <50ms | 无 | 低 |
| 后端 morseangel | <100ms | PyTorch | 中 |
| 混合方案 | <50ms | 可选 | 高 |

---

## 附录

### A. 参考资源

1. **web-deep-cw-decoder**: https://github.com/e04/web-deep-cw-decoder
   - 浏览器端 ONNX 模型
   - 2MB 轻量架构

2. **morseangel**: https://github.com/f4exb/morseangel
   - PyTorch LSTM 解码器
   - CER < 2% @ SNR>-5dB

3. **ONNX Runtime Web**: https://onnxruntime.ai/docs/get-started/with-javascript.html
   - 浏览器端推理框架

4. **ITU-R M.1677**: 国际摩尔斯电码标准
   - 时序规范
   - 字符编码

### B. 后端解码器集成 (morse-deep-learning)

#### B.1 依赖安装

```bash
# 安装 PyTorch (推荐 CUDA 版本以获得最佳性能)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 其他依赖
pip install scipy numpy matplotlib tqdm python-Levenshtein

# 下载 morse-deep-learning
 git clone https://github.com/MaorAssayag/morse-deep-learning-detect-and-decode.git
 cd morse-deep-learning-detect-and-decode
```

#### B.2 模型下载

由于项目未提供预训练模型，需要自行训练或从训练好的 checkpoint 加载：

```bash
# 创建模型目录
mkdir -p models

# 方式 1: 使用项目中的 notebook 训练
# 打开 morse-decoder-detector-dl.ipynb 运行训练

# 方式 2: 从 checkpoint 加载 (如果有)
# cp checkpoint_faster_rcnn.pth models/faster_rcnn_model.pth
# cp checkpoint_lstm.pth models/lstm_decoder.pth

# 方式 3: 使用简化版预训练模型 (TODO: 需要训练)
```

**模型组成**:

| 模型 | 文件名 | 参数量 | 用途 |
|------|--------|--------|------|
| Faster R-CNN | `faster_rcnn_model.pth` | 41M | 信号检测 |
| BiLSTM Decoder | `lstm_decoder.pth` | 740K | 字符解码 |

#### B.3 启动后端解码服务

```bash
# 独立启动
python cw_decoder_backend.py

# 或使用 systemd
sudo systemctl start mrrc-cw-decoder
```

#### B.4 双模式切换逻辑

```javascript
// 自动选择最佳模式
async selectOptimalMode() {
  const onnxSupported = await this.checkONNXSupport();
  const networkQuality = await this.checkNetworkQuality();
  
  if (!onnxSupported) {
    return 'backend';  // ONNX 不支持，使用后端
  }
  
  if (networkQuality === 'poor') {
    return 'frontend';  // 网络差，使用前端
  }
  
  // 默认使用前端，但允许用户手动切换到后端
  return 'frontend';
}
```

#### B.5 性能对比

| 指标 | 前端解码 (ONNX) | 后端解码 (morse-deep-learning) |
|------|----------------|-------------------------------|
| 延迟 | <50ms | <100ms |
| 准确率 (CER) | <3% | **<2% @ SNR>-5dB** |
| 弱信号表现 | 良好 | **优秀** |
| 检测能力 | 单信号 | **多信号检测 (Faster R-CNN)** |
| 训练数据 | 未公开 | **5000万字符** |
| 模型大小 | 2MB | **160MB** |
| GPU 需求 | 无 | **推荐 CUDA** |
| 网络依赖 | 无 | 有 |

### C. 性能目标

| 指标 | 目标值 | 测试方法 |
|------|--------|----------|
| 解码延迟 | <50ms | 音频输入到文本输出 |
| 字符错误率 (CER) | <5% | 标准 CW 测试音频 |
| 呼号识别率 | >95% | 实际 QSO 录音测试 |
| 发送时序精度 | ±10ms | 示波器测量 |
| 端到端延迟 | <100ms | PTT 到音频输出 |
| 模式切换时间 | <1s | 前端/后端切换 |

### C. 测试计划

1. **单元测试**: 各模块独立测试
2. **集成测试**: 完整 QSO 流程模拟
3. **电台测试**: 与真实电台通联测试
4. **兼容性测试**: iOS/Android/macOS/Windows
5. **性能测试**: 长时间运行稳定性

---

**文档版本**: V1.0  
**最后更新**: 2026-03-11  
**维护者**: MRRC 开发团队

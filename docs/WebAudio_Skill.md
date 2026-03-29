# Web Audio API 技能文档

> 本文档基于 W3C Web Audio API 1.1 规范，结合 MRRC 项目实际需求，为 AI 助手提供专业的 Web Audio 开发技能知识库。

---

## 一、核心概念与架构

### 1.1 音频上下文 (AudioContext)

AudioContext 是 Web Audio API 的核心入口，代表一个完整的音频处理图。

```javascript
// 创建音频上下文
const ctx = new AudioContext({
  sampleRate: 48000,      // 推荐：与硬件原生匹配
  latencyHint: 'interactive'  // 'balanced' | 'interactive' | 'playback'
});

// 关键属性
ctx.sampleRate        // 采样率 (Hz)
ctx.currentTime       // 当前时间 (秒)
ctx.state            // 'suspended' | 'running' | 'closed'
ctx.baseLatency      // 基础延迟 (秒)
ctx.outputLatency    // 输出延迟 (秒)
ctx.destination      // 最终输出节点
```

**状态管理**:
- 新建的 AudioContext 初始状态为 `suspended`
- iOS Safari 要求用户交互后才能 `resume()`
- 使用 `ctx.statechange` 事件监听状态变化

```javascript
// iOS 兼容模式
document.addEventListener('click', async () => {
  if (ctx.state === 'suspended') {
    await ctx.resume();
  }
}, { once: true });
```

### 1.2 渲染量子 (Render Quantum)

Web Audio 使用固定大小的处理块，称为"渲染量子"。

| 属性 | 值 | 说明 |
|------|-----|------|
| 默认大小 | 128 samples | 约 2.67ms @ 48kHz |
| 可配置 | 128, 256, 512, 1024, 2048, 4096 | renderQuantumSize |
| 延迟计算 | 128 / 48000 ≈ 2.67ms | 单个量子延迟 |

**MRRC 最佳实践**: 使用默认 128 samples，配合 AudioWorklet 实现最低延迟。

### 1.3 采样率策略

| 采样率 | 用途 | 说明 |
|--------|------|------|
| 48000 Hz | **推荐** | 现代硬件原生采样率，零重采样 |
| 44100 Hz | 传统 | CD 质量，可能触发重采样 |
| 16000 Hz | 语音 | Opus 编码优化，需重采样 |

**MRRC 策略**: 统一使用 48kHz，避免重采样延迟和混叠。

---

## 二、AudioNode 节点体系

### 2.1 节点类型概览

```
AudioNode (基类)
├── AudioSourceNode (源节点)
│   ├── OscillatorNode          // 振荡器
│   ├── AudioBufferSourceNode   // 缓冲区源
│   ├── MediaElementAudioSourceNode
│   ├── MediaStreamAudioSourceNode
│   └── AudioWorkletNode        // 自定义处理
│
├── AudioDestinationNode (目标节点)
│
├── AudioScheduledSourceNode
│
├── FilterNode (滤波器)
│   ├── BiquadFilterNode        // 二阶滤波器
│   └── IIRFilterNode           // 无限脉冲响应
│
├── EffectNode (效果器)
│   ├── GainNode                // 增益
│   ├── DelayNode               // 延迟
│   ├── ConvolverNode           // 卷积
│   ├── DynamicsCompressorNode  // 动态压缩
│   └── AnalyserNode            // 分析器
│
└── SpatialNode (空间音频)
    ├── PannerNode
    └── AudioListener
```

### 2.2 节点连接模式

```javascript
// 基本连接
source.connect(filter);
filter.connect(gain);
gain.connect(ctx.destination);

// 链式连接
source.connect(filter).connect(gain).connect(ctx.destination);

// 多输出
source.connect(destination1);
source.connect(destination2);

// 断开连接
source.disconnect();           // 断开所有
source.disconnect(destination); // 断开特定目标
```

### 2.3 通道处理

```javascript
// 通道计数
node.channelCount      // 当前通道数
node.channelCountMode  // 'max' | 'clamped-max' | 'explicit'
node.channelInterpretation  // 'speakers' | 'discrete'

// MRRC 配置 (单声道语音)
node.channelCount = 1;
node.channelCountMode = 'explicit';
node.channelInterpretation = 'speakers';
```

---

## 三、AudioWorklet 深度解析

### 3.1 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    Main Thread                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │           AudioWorkletNode                       │   │
│  │  - parameters (AudioParamMap)                   │   │
│  │  - port (MessagePort) ◄─────────────────────┐   │   │
│  └──────────────────────────────────────────────│───┘   │
└─────────────────────────────────────────────────│───────┘
                                    MessageChannel
┌─────────────────────────────────────────────────│───────┐
│                 AudioWorkletThread               │       │
│  ┌───────────────────────────────────────────────│───┐   │
│  │         AudioWorkletProcessor                  ▼   │   │
│  │  - port (MessagePort) ─────────────────────────    │   │
│  │  - process(inputs, outputs, parameters)            │   │
│  └────────────────────────────────────────────────────┘   │
│  ┌────────────────────────────────────────────────────┐   │
│  │       AudioWorkletGlobalScope                      │   │
│  │  - currentFrame, currentTime, sampleRate          │   │
│  │  - registerProcessor(name, ProcessorClass)        │   │
│  └────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

### 3.2 AudioWorkletNode (主线程)

```javascript
// 加载 Worklet 模块
await ctx.audioWorklet.addModule('processor.js');

// 创建节点
const node = new AudioWorkletNode(ctx, 'my-processor', {
  numberOfInputs: 1,
  numberOfOutputs: 1,
  outputChannelCount: [1],
  parameterData: { gain: 0.5 },
  processorOptions: { customData: {} }
});

// 访问参数
node.parameters.get('gain').value = 0.8;

// 消息通信
node.port.onmessage = (e) => console.log('From processor:', e.data);
node.port.postMessage({ type: 'control', data: {} });
```

### 3.3 AudioWorkletProcessor (渲染线程)

```javascript
// processor.js - 在 AudioWorkletGlobalScope 中运行
class MyProcessor extends AudioWorkletProcessor {
  // 静态参数定义
  static get parameterDescriptors() {
    return [
      {
        name: 'gain',
        defaultValue: 0.5,
        minValue: 0,
        maxValue: 1,
        automationRate: 'k-rate'  // 'a-rate' | 'k-rate'
      }
    ];
  }

  constructor(options) {
    super();
    // 初始化处理器
    this.buffer = new Float32Array(4096);
    this.writeIndex = 0;
  }

  // 核心处理方法 - 每个 render quantum 调用一次
  process(inputs, outputs, parameters) {
    // inputs[输入索引][通道索引] = Float32Array(128)
    // outputs[输出索引][通道索引] = Float32Array(128)
    
    const input = inputs[0];
    const output = outputs[0];
    const gain = parameters.gain[0];  // k-rate 参数

    for (let channel = 0; channel < input.length; channel++) {
      const inputChannel = input[channel];
      const outputChannel = output[channel];
      
      for (let i = 0; i < inputChannel.length; i++) {
        outputChannel[i] = inputChannel[i] * gain;
      }
    }

    // 返回 true 保持处理器活跃
    // 返回 false 允许在没有输入时休眠
    return true;
  }
}

// 注册处理器
registerProcessor('my-processor', MyProcessor);
```

### 3.4 内联 AudioWorklet (Blob URL)

MRRC 推荐使用 Blob URL 动态创建 Worklet，无需额外文件：

```javascript
const WORKLET_CODE = `
class OptimizedProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ringBuffer = new Float32Array(48000);  // 1秒缓冲
    this.writeIndex = 0;
    this.readIndex = 0;
  }

  process(inputs, outputs) {
    const input = inputs[0][0];
    const output = outputs[0][0];
    
    if (input) {
      // 写入环形缓冲区
      for (let i = 0; i < input.length; i++) {
        this.ringBuffer[this.writeIndex] = input[i];
        this.writeIndex = (this.writeIndex + 1) % this.ringBuffer.length;
      }
    }
    
    // 从缓冲区读取
    for (let i = 0; i < output.length; i++) {
      output[i] = this.ringBuffer[this.readIndex];
      this.readIndex = (this.readIndex + 1) % this.ringBuffer.length;
    }
    
    return true;
  }
}
registerProcessor('optimized-processor', OptimizedProcessor);
`;

// 创建 Blob URL
const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
const url = URL.createObjectURL(blob);

// 加载
await ctx.audioWorklet.addModule(url);
const node = new AudioWorkletNode(ctx, 'optimized-processor');
```

### 3.5 环形缓冲区实现

```javascript
class RingBuffer {
  constructor(capacity) {
    this.buffer = new Float32Array(capacity);
    this.capacity = capacity;
    this.writeIndex = 0;
    this.readIndex = 0;
    this.length = 0;
  }

  write(data) {
    for (let i = 0; i < data.length; i++) {
      this.buffer[this.writeIndex] = data[i];
      this.writeIndex = (this.writeIndex + 1) % this.capacity;
      if (this.length < this.capacity) this.length++;
    }
  }

  read(size) {
    const result = new Float32Array(size);
    for (let i = 0; i < size; i++) {
      if (this.length > 0) {
        result[i] = this.buffer[this.readIndex];
        this.readIndex = (this.readIndex + 1) % this.capacity;
        this.length--;
      } else {
        result[i] = 0;  // 欠载时填充静音
      }
    }
    return result;
  }

  get available() {
    return this.length;
  }
}
```

---

## 四、音频参数自动化 (AudioParam)

### 4.1 AudioParam 方法

```javascript
const gain = gainNode.gain;  // AudioParam 实例

// 即时设置
gain.value = 0.5;

// 时间事件
gain.setValueAtTime(0.5, ctx.currentTime);           // 即时
gain.linearRampToValueAtTime(1.0, ctx.currentTime + 1);  // 线性渐变
gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 1);  // 指数渐变

// 曲线
gain.setValueCurveAtTime([0, 0.5, 1, 0.5, 0], ctx.currentTime, 2);

// 取消
gain.cancelScheduledValues(ctx.currentTime);
gain.cancelAndHoldAtTime(ctx.currentTime + 0.5);
```

### 4.2 自动化类型

| 方法 | 用途 | 特点 |
|------|------|------|
| `setValueAtTime` | 即时设置 | 阶跃变化 |
| `linearRampToValueAtTime` | 线性渐变 | 均匀变化 |
| `exponentialRampToValueAtTime` | 指数渐变 | 自然听感，避免零值 |
| `setTargetAtTime` | 目标逼近 | 指数逼近，常用包络 |
| `setValueCurveAtTime` | 曲线设置 | 自定义曲线 |

---

## 五、移动端音频优化

### 5.1 iOS Safari 特殊处理

```javascript
// 1. 自动播放策略
let audioContext;
let isUnlocked = false;

function unlock() {
  if (isUnlocked) return;
  
  // 创建空缓冲区播放
  const buffer = audioContext.createBuffer(1, 1, 22050);
  const source = audioContext.createBufferSource();
  source.buffer = buffer;
  source.connect(audioContext.destination);
  source.start(0);
  
  // 恢复上下文
  if (audioContext.state === 'suspended') {
    audioContext.resume();
  }
  
  isUnlocked = true;
}

// 2. 触摸解锁
document.addEventListener('touchstart', unlock, { once: true });
document.addEventListener('touchend', unlock, { once: true });

// 3. 页面可见性处理
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    audioContext.suspend();
  } else {
    audioContext.resume();
  }
});
```

### 5.2 低延迟配置

```javascript
// 创建低延迟上下文
const ctx = new AudioContext({
  latencyHint: 'interactive',  // 最低延迟优先
  sampleRate: 48000            // 原生采样率
});

// 监控延迟
console.log(`Base latency: ${ctx.baseLatency * 1000}ms`);
console.log(`Output latency: ${ctx.outputLatency * 1000}ms`);
```

### 5.3 电源管理

```javascript
// 使用 Page Visibility API
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    // 页面隐藏时挂起
    ctx.suspend();
  } else {
    // 页面可见时恢复
    ctx.resume();
  }
});

// 使用 Wake Lock API (保持屏幕常亮)
let wakeLock = null;
async function requestWakeLock() {
  try {
    wakeLock = await navigator.wakeLock.request('screen');
  } catch (err) {
    console.log('Wake Lock not supported');
  }
}
```

---

## 六、数据格式转换

### 6.1 Float32 ↔ Int16

```javascript
// Float32 [-1, 1] → Int16 [-32768, 32767]
function float32ToInt16(float32Array) {
  const int16Array = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    // 限制范围并转换
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return int16Array;
}

// Int16 → Float32
function int16ToFloat32(int16Array) {
  const float32Array = new Float32Array(int16Array.length);
  for (let i = 0; i < int16Array.length; i++) {
    float32Array[i] = int16Array[i] / (int16Array[i] < 0 ? 0x8000 : 0x7FFF);
  }
  return float32Array;
}
```

### 6.2 采样率转换

```javascript
// 简单线性插值降采样
function downsample(input, inputRate, outputRate) {
  const ratio = inputRate / outputRate;
  const outputLength = Math.floor(input.length / ratio);
  const output = new Float32Array(outputLength);
  
  for (let i = 0; i < outputLength; i++) {
    const srcIndex = i * ratio;
    const srcIndexFloor = Math.floor(srcIndex);
    const srcIndexCeil = Math.min(srcIndexFloor + 1, input.length - 1);
    const t = srcIndex - srcIndexFloor;
    
    // 线性插值
    output[i] = input[srcIndexFloor] * (1 - t) + input[srcIndexCeil] * t;
  }
  
  return output;
}

// 抗混叠滤波 + 降采样
function antiAliasingDownsample(input, inputRate, outputRate) {
  // 先低通滤波 (截止频率 = outputRate / 2)
  const nyquist = outputRate / 2;
  const ctx = new OfflineAudioContext(1, input.length, inputRate);
  const buffer = ctx.createBuffer(1, input.length, inputRate);
  buffer.copyToChannel(input, 0);
  
  const source = ctx.createBufferSource();
  source.buffer = buffer;
  
  const filter = ctx.createBiquadFilter();
  filter.type = 'lowpass';
  filter.frequency.value = nyquist * 0.9;  // 留余量
  
  source.connect(filter);
  filter.connect(ctx.destination);
  source.start();
  
  return ctx.startRendering().then(rendered => {
    return downsample(rendered.getChannelData(0), inputRate, outputRate);
  });
}
```

---

## 七、性能优化最佳实践

### 7.1 避免主线程阻塞

```javascript
// ❌ 避免：主线程重计算
function bad() {
  setInterval(() => {
    // 大量音频计算会阻塞主线程
    heavyProcessing();
  }, 20);
}

// ✅ 推荐：使用 AudioWorklet
function good() {
  const node = new AudioWorkletNode(ctx, 'heavy-processor');
  node.port.onmessage = (e) => {
    // 只在需要时处理结果
    handleResult(e.data);
  };
}
```

### 7.2 内存管理

```javascript
// ✅ 预分配缓冲区
class AudioBufferPool {
  constructor(size, count) {
    this.pool = [];
    for (let i = 0; i < count; i++) {
      this.pool.push(new Float32Array(size));
    }
  }
  
  acquire() {
    return this.pool.pop() || new Float32Array(this.size);
  }
  
  release(buffer) {
    this.pool.push(buffer);
  }
}

// ❌ 避免：频繁创建
function bad() {
  setInterval(() => {
    const buffer = new Float32Array(1024);  // 每次分配新内存
    process(buffer);
  }, 20);
}
```

### 7.3 延迟优化清单

| 优化项 | 措施 | 预期效果 |
|--------|------|----------|
| 采样率 | 使用硬件原生 48kHz | 避免重采样延迟 |
| 缓冲区 | AudioWorklet 128 samples | ~2.67ms 处理延迟 |
| 上下文 | `latencyHint: 'interactive'` | 系统优化调度 |
| 通道 | 单声道语音 | 减少计算量 |
| 编码 | Int16 传输 | 50% 带宽减少 |

---

## 八、MRRC 项目应用模式

### 8.1 RX 接收音频流

```javascript
// 接收 WebSocket 音频流 → AudioWorklet 播放
class RXAudioEngine {
  constructor() {
    this.ctx = new AudioContext({ sampleRate: 48000 });
    this.ringBuffer = new RingBuffer(48000);  // 1秒缓冲
    this.initWorklet();
  }

  async initWorklet() {
    const code = `...AudioWorklet code...`;
    const blob = new Blob([code], { type: 'application/javascript' });
    await this.ctx.audioWorklet.addModule(URL.createObjectURL(blob));
    
    this.node = new AudioWorkletNode(this.ctx, 'rx-processor');
    this.node.connect(this.ctx.destination);
  }

  // 接收 Int16 音频数据
  receiveAudio(int16Data) {
    const float32 = int16ToFloat32(int16Data);
    this.ringBuffer.write(float32);
  }
}
```

### 8.2 TX 发射音频流

```javascript
// 麦克风 → 处理 → WebSocket 发送
class TXAudioEngine {
  constructor() {
    this.ctx = new AudioContext({ sampleRate: 48000 });
    this.ws = null;  // WebSocket 连接
  }

  async start() {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 48000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true
      }
    });

    const source = this.ctx.createMediaStreamSource(stream);
    
    // 抗混叠滤波
    this.antiAliasFilter = this.ctx.createBiquadFilter();
    this.antiAliasFilter.type = 'lowpass';
    this.antiAliasFilter.frequency.value = 6000;
    
    // TX 处理节点
    await this.ctx.audioWorklet.addModule('tx-processor.js');
    this.txNode = new AudioWorkletNode(this.ctx, 'tx-processor');
    this.txNode.port.onmessage = (e) => {
      if (e.data.type === 'audio') {
        this.ws.send(e.data.int16Buffer);
      }
    };

    source.connect(this.antiAliasFilter);
    this.antiAliasFilter.connect(this.txNode);
  }
}
```

### 8.3 完整音频引擎类

```javascript
class MRRCApp {
  constructor() {
    this.config = {
      SAMPLE_RATE: 48000,
      FRAME_SIZE: 960,  // 20ms @ 48kHz
      RING_BUFFER_SIZE: 48000
    };
    
    this.rxAudio = null;
    this.txAudio = null;
    this.ws = null;
  }

  async init() {
    // 创建音频上下文
    this.ctx = new AudioContext({
      sampleRate: this.config.SAMPLE_RATE,
      latencyHint: 'interactive'
    });

    // iOS 解锁
    this.setupIOSUnlock();

    // 初始化 RX/TX
    await this.initRX();
    await this.initTX();
  }

  setupIOSUnlock() {
    const unlock = async () => {
      if (this.ctx.state === 'suspended') {
        await this.ctx.resume();
      }
    };
    document.addEventListener('touchstart', unlock, { once: true });
    document.addEventListener('click', unlock, { once: true });
  }
}
```

---

## 九、故障排查指南

### 9.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 无声音 | AudioContext 挂起 | 调用 `ctx.resume()` |
| 声音断续 | 缓冲区欠载 | 增大环形缓冲区 |
| 延迟过高 | 缓冲区过大 | 减小缓冲区大小 |
| 杂音 | 采样率不匹配 | 统一使用 48kHz |
| iOS 无声 | 自动播放策略 | 用户交互后 resume |

### 9.2 调试工具

```javascript
// 监控音频状态
function monitor(ctx) {
  setInterval(() => {
    console.log({
      state: ctx.state,
      sampleRate: ctx.sampleRate,
      currentTime: ctx.currentTime,
      baseLatency: ctx.baseLatency,
      outputLatency: ctx.outputLatency
    });
  }, 1000);
}

// 检测欠载
class DebugProcessor extends AudioWorkletProcessor {
  process(inputs, outputs) {
    const input = inputs[0][0];
    if (!input || input.every(v => v === 0)) {
      this.port.postMessage({ type: 'underrun' });
    }
    return true;
  }
}
```

---

## 十、参考资源

- [W3C Web Audio API 1.1 Specification](https://webaudio.github.io/web-audio-api/)
- [MDN Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)
- [Web Audio API 最佳实践](https://webaudio.github.io/web-audio-api/#best-practices)
- [MRRC 音频优化文档](./audio_optimization.md)

---

**文档版本**: 1.0  
**最后更新**: 2026-03-22  
**适用于**: MRRC 项目 Web Audio 开发

# MRRC 音频流深度分析与优化建议

## 一、当前实现分析

### 1.1 音频流架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                     MRRC 音频流完整数据流                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ TX 路径 (发射):                                                  │
│ ┌──────────┐    ┌────────────┐    ┌────────────┐    ┌────────┐ │
│ │ 麦克风    │ -> │ Float32    │ -> │ Opus/Int16 │ -> │WebSocket│ │
│ │ 采集     │    │ (16kHz)     │    │  编码      │    │  传输  │ │
│ └──────────┘    └────────────┘    └────────────┘    └────┬───┘ │
│                                                      ↓          │
│ ┌──────────┐    ┌────────────┐    ┌────────────┐             │ │
│ │ PyAudio  │ -> │ Int16播放  │ -> │  电台硬件   │             │ │
│ │ 解码     │    │ (16kHz)     │    │  输出      │             │ │
│ └──────────┘    └────────────┘    └────────────┘             │
│                                                                 │
│ RX 路径 (接收):                                                  │
│ ┌──────────┐    ┌────────────┐    ┌────────────┐    ┌────────┐ │
│ │ 电台     │ -> │ Float32    │ -> │ Int16编码  │ -> │WebSocket│ │
│ │ 音频     │    │ (16kHz)     │    │ (50%优化)  │    │  传输  │ │
│ └──────────┘    └────────────┘    └────────────┘    └────┬───┘ │
│                                                      ↓          │
│ ┌──────────┐    ┌────────────┐    ┌────────────┐             │ │
│ │ Int16    │ -> │ AudioWorklet│ -> │ Web Audio  │ -> │ 扬声器 │ │
│ │ 解码     │    │ 播放器      │    │  播放      │    │ 输出   │ │
│ └──────────┘    └────────────┘    └────────────┘             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 编码解码流程详解

#### TX 路径编码流程：

**位置**: `audio_interface.py:165-172` 和 `www/controls.js:1533-1542`

```python
# 后端 Int16 编码 (audio_interface.py)
float32_data = np.frombuffer(data, dtype=np.float32)
int16_data = (float32_data * 32767).astype(np.int16)
compressed_data = int16_data.tobytes()
```

```javascript
// 前端 Int16 解码 (controls.js:185-192)
const int16Data = new Int16Array(msg.data);
const float32Data = new Float32Array(int16Data.length);
for (let i = 0; i < int16Data.length; i++) {
    float32Data[i] = int16Data[i] / 32767.0;
}
```

#### RX 路径编码流程：

**位置**: `audio_interface.py:165-172` 和 `www/controls.js:185-192`

```python
# 后端 Int16 编码 (audio_interface.py)
float32_data = np.frombuffer(data, dtype=np.float32)
int16_data = (float32_data * 32767).astype(np.int16)
compressed_data = int16_data.tobytes()
```

```javascript
// 前端 Int16 解码 (controls.js:185-192)
const int16Data = new Int16Array(msg.data);
const float32Data = new Float32Array(int16Data.length);
for (let i = 0; i < int16Data.length; i++) {
    float32Data[i] = int16Data[i] / 32767.0;
}
```

### 1.3 关键参数配置

| 参数 | 当前值 | 位置 | 说明 |
|------|--------|------|------|
| 采样率 | 16000 Hz | 全局 | 统一采样率 |
| 缓冲区大小 | 512 帧 | audio_interface.py | PyAudio 缓冲区 |
| RX Worklet 最小缓冲 | 16 帧 | controls.js:233 | 预热深度 |
| RX Worklet 最大缓冲 | 32 帧 | controls.js:233 | 稳定性缓冲 |
| TX 预热帧数 | 10 帧 | tx_button_optimized.js:68 | 确保音频到达 |
| TX 预热间隔 | 10 ms | tx_button_optimized.js:68 | 预热帧发送间隔 |
| RX 批量发送 | 8 帧/批次 | MRRC:911-930 | 减少 WebSocket 开销 |
| PTT 超时计数 | 10 次 | MRRC:688-698 | 200ms 检查间隔 |

### 1.4 带宽分析

**理论带宽计算**：

```
原始 Float32 音频:
  采样率: 16,000 Hz
  位深度: 32 bit (4 bytes)
  声道: 1 (单声道)
  带宽: 16,000 × 4 × 1 = 64,000 bytes/s = 512 kbps

Int16 优化后:
  采样率: 16,000 Hz
  位深度: 16 bit (2 bytes)
  声道: 1 (单声道)
  带宽: 16,000 × 2 × 1 = 32,000 bytes/s = 256 kbps

带宽节省: (512 - 256) / 512 = 50%
```

**实际带宽**（基于代码日志）：
- RX: 约 256 kbps (Int16)
- TX: 约 256 kbps (Int16) 或更低 (Opus 压缩)

### 1.5 延迟分析

**端到端延迟组成**：

```
TX 路径延迟:
  1. 麦克风采集: ~10-20 ms (Web Audio API)
  2. 编码处理: ~1-2 ms (Int16 转换)
  3. 网络传输: ~10-50 ms (取决于网络)
  4. 后端解码: ~1-2 ms (Int16 转换)
  5. PyAudio 播放: ~10-20 ms (缓冲区)
  总计: ~32-94 ms

RX 路径延迟:
  1. 电台采集: ~10-20 ms (PyAudio)
  2. 编码处理: ~1-2 ms (Int16 转换)
  3. 网络传输: ~10-50 ms (取决于网络)
  4. 前端解码: ~1-2 ms (Int16 转换)
  5. Worklet 播放: ~10-20 ms (缓冲区)
  总计: ~32-94 ms

TX→RX 切换延迟:
  1. PTT 命令传输: ~10-50 ms
  2. 缓冲区清除: <1 ms
  3. RX 音频到达: ~32-94 ms
  总计: <100 ms (已优化)
```

---

## 二、已实现的优化措施

### 2.1 带宽优化 ✅

**Int16 编码** (50% 带宽节省)
- **位置**: `audio_interface.py:165-172`
- **实现**: Float32 → Int16 转换
- **效果**: 512 kbps → 256 kbps

### 2.2 延迟优化 ✅

**缓冲区清除机制**
- **位置**: `tx_button_optimized.js:144-150`
- **实现**: TX 释放时立即清除 RX 缓冲区
- **效果**: TX→RX 切换延迟 2-3s → <100ms

**缓冲区深度优化**
- **位置**: `controls.js:233`
- **实现**: 32/64 帧 → 16/32 帧
- **效果**: 降低播放延迟，提高响应速度

**PTT 预热帧机制**
- **位置**: `tx_button_optimized.js:68-89`
- **实现**: 按下即 PTT + 10 个预热帧
- **效果**: 确保后端立即收到音频数据

### 2.3 稳定性优化 ✅

**PTT 防抖机制**
- **位置**: `controls.js:606-680`
- **实现**: 50ms 防抖延迟
- **效果**: 防止重复 PTT 命令

**批量发送优化**
- **位置**: `MRRC:911-930`
- **实现**: 最多 8 帧/批次
- **效果**: 减少 WebSocket 调用开销

**动态缓冲区管理**
- **位置**: `rx_worklet_processor.js`
- **实现**: 预热深度 2-4 帧，最大 4 帧
- **效果**: 平衡延迟和稳定性

---

## 三、进一步优化建议

### 3.1 编码优化

#### 建议 1: 采用更高效的编码格式

**当前**: Int16 (无压缩)
**建议**: Opus 或 AAC (有损压缩)

**优势**:
- 带宽节省: 50-80% (取决于质量设置)
- 更好的网络适应性
- 内置 FEC (前向纠错)

**劣势**:
- 增加编码/解码延迟 (5-10ms)
- 增加 CPU 使用率
- 音频质量损失 (轻微)

**实现难度**: 中等
**优先级**: 低 (当前 Int16 已足够高效)

#### 建议 2: 自适应比特率 (ABR)

**当前**: 固定 Int16 格式
**建议**: 根据网络状况动态调整编码质量

**实现方案**:
```javascript
// 前端网络质量监测
const networkMonitor = {
  rtt: 0,
  bandwidth: 0,
  lastMeasure: 0,

  measure() {
    const start = Date.now();
    fetch('/ping', { mode: 'no-cors' }).then(() => {
      this.rtt = Date.now() - start;
      this.bandwidth = window.__rxBytes * 8 / 1000; // kbps
      this.lastMeasure = Date.now();
    });
  },

  getQuality() {
    if (this.rtt > 100 || this.bandwidth < 100) {
      return 'low'; // 低质量：更激进的压缩
    } else if (this.rtt > 50 || this.bandwidth < 200) {
      return 'medium'; // 中等质量
    } else {
      return 'high'; // 高质量：无压缩
    }
  }
};

// 根据网络质量调整编码
function adjustEncodingQuality(quality) {
  switch(quality) {
    case 'low':
      // 使用 Opus 低比特率模式
      break;
    case 'medium':
      // 使用 Opus 中等比特率模式
      break;
    case 'high':
      // 使用 Int16 无压缩
      break;
  }
}
```

**优势**:
- 自动适应网络条件
- 在恶劣网络下保持连接
- 优化带宽使用

**实现难度**: 高
**优先级**: 中

#### 建议 3: 优化 Int16 转换性能

**当前**: 使用循环逐个转换
**建议**: 使用 TypedArray 的批量操作

**当前实现** (controls.js:185-192):
```javascript
const int16Data = new Int16Array(msg.data);
const float32Data = new Float32Array(int16Data.length);
for (let i = 0; i < int16Data.length; i++) {
    float32Data[i] = int16Data[i] / 32767.0;
}
```

**优化实现**:
```javascript
// 使用 WebAssembly 加速
// 或使用 SIMD 指令（如果浏览器支持）
const int16Data = new Int16Array(msg.data);
const float32Data = new Float32Array(int16Data.length);

// 方法 1: 使用 Float32Array.set() + 缩放
const scale = 1.0 / 32767.0;
for (let i = 0; i < int16Data.length; i++) {
    float32Data[i] = int16Data[i] * scale;
}

// 方法 2: 使用 DataView（跨平台兼容）
const view = new DataView(msg.data);
for (let i = 0; i < int16Data.length; i++) {
    float32Data[i] = view.getInt16(i * 2, true) * scale;
}

// 方法 3: 使用 WebAssembly（最优性能）
// 编译一个简单的 WASM 模块来执行批量转换
```

**性能提升**: 20-30%
**实现难度**: 中
**优先级**: 高

### 3.2 缓冲区优化

#### 建议 4: 自适应缓冲区深度

**当前**: 固定 16/32 帧
**建议**: 根据网络抖动动态调整

**实现方案**:
```javascript
// 在 rx_worklet_processor.js 中添加抖动检测
class RxPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    this.targetMinFrames = 2;
    this.targetMaxFrames = 4;

    // 添加网络抖动检测
    this.jitterHistory = [];
    this.maxJitterHistory = 20;

    this.port.onmessage = (event) => {
      const data = event.data;

      if (data && data.type === 'push') {
        // 记录到达时间
        const now = performance.now();
        this.jitterHistory.push(now);
        if (this.jitterHistory.length > this.maxJitterHistory) {
          this.jitterHistory.shift();
        }

        // 计算抖动
        if (this.jitterHistory.length >= 2) {
          const jitter = this.calculateJitter();
          this.adjustBufferSize(jitter);
        }

        this.queue.push(data.payload);
      }
      // ... 其他消息处理
    };
  }

  calculateJitter() {
    // 计算到达时间的标准差
    const intervals = [];
    for (let i = 1; i < this.jitterHistory.length; i++) {
      intervals.push(this.jitterHistory[i] - this.jitterHistory[i-1]);
    }
    const mean = intervals.reduce((a, b) => a + b) / intervals.length;
    const variance = intervals.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / intervals.length;
    return Math.sqrt(variance);
  }

  adjustBufferSize(jitter) {
    // 根据抖动调整缓冲区
    if (jitter > 50) {
      // 高抖动：增加缓冲区
      this.targetMinFrames = 4;
      this.targetMaxFrames = 8;
    } else if (jitter > 20) {
      // 中等抖动：中等缓冲区
      this.targetMinFrames = 3;
      this.targetMaxFrames = 6;
    } else {
      // 低抖动：最小缓冲区
      this.targetMinFrames = 2;
      this.targetMaxFrames = 4;
    }
  }
}
```

**优势**:
- 自动适应网络条件
- 在稳定网络下降低延迟
- 在不稳定网络下提高稳定性

**实现难度**: 中
**优先级**: 高

#### 建议 5: 优化批量发送策略

**当前**: 固定 8 帧/批次
**建议**: 根据缓冲区状态动态调整

**实现方案** (MRRC:911-930):
```python
@tornado.gen.coroutine
def tailstream(self):
    while flagWavstart and self.ws_connection:
        while len(self.Wavframes) == 0:
            yield tornado.gen.sleep(0.005)

        if self.ws_connection:
            # 动态批量大小：根据缓冲区状态调整
            buffer_size = len(self.Wavframes)

            if buffer_size >= 16:
                # 缓冲区充足：大批量发送
                batch_size = min(12, buffer_size)
            elif buffer_size >= 8:
                # 缓冲区正常：标准批量
                batch_size = 8
            else:
                # 缓冲区较少：小批量快速发送
                batch_size = min(4, buffer_size)

            batch = 0
            while batch < batch_size and len(self.Wavframes) > 0:
                yield self.write_message(self.Wavframes[0], binary=True)
                del self.Wavframes[0]
                batch += 1
```

**优势**:
- 在缓冲区充足时减少 WebSocket 调用
- 在缓冲区不足时快速发送，避免延迟
- 提高整体吞吐量

**实现难度**: 低
**优先级**: 中

### 3.3 网络优化

#### 建议 6: 实现 WebSocket 二进制分片

**当前**: 完整帧发送
**建议**: 大帧分片发送，避免 MTU 限制

**实现方案**:
```javascript
// 前端分片发送
function sendChunked(ws, data, chunkSize = 4096) {
  const totalChunks = Math.ceil(data.byteLength / chunkSize);

  for (let i = 0; i < totalChunks; i++) {
    const start = i * chunkSize;
    const end = Math.min(start + chunkSize, data.byteLength);
    const chunk = data.slice(start, end);

    // 添加分片元数据
    const metadata = new Uint8Array(4);
    const view = new DataView(metadata.buffer);
    view.setUint32(0, totalChunks, true); // 总分片数
    view.setUint32(4, i, true);          // 当前分片索引

    // 合并元数据和分片数据
    const packet = new Uint8Array(metadata.byteLength + chunk.byteLength);
    packet.set(metadata, 0);
    packet.set(new Uint8Array(chunk), metadata.byteLength);

    ws.send(packet);
  }
}

// 后端重组
class ChunkReassembler {
  constructor() {
    this.chunks = new Map(); // chunkId -> {total, received, data}
  }

  addChunk(chunkId, chunkIndex, totalChunks, data) {
    if (!this.chunks.has(chunkId)) {
      this.chunks.set(chunkId, {
        total: totalChunks,
        received: 0,
        data: new Uint8Array(totalChunks * data.byteLength)
      });
    }

    const chunk = this.chunks.get(chunkId);
    chunk.data.set(data, chunkIndex * data.byteLength);
    chunk.received++;

    if (chunk.received === chunk.total) {
      // 所有分片已接收，返回完整数据
      const completeData = chunk.data.slice(0, chunk.data.length);
      this.chunks.delete(chunkId);
      return completeData;
    }

    return null;
  }
}
```

**优势**:
- 避免 MTU 限制导致的分片
- 更好的网络适应性
- 减少丢包影响

**劣势**:
- 增加实现复杂度
- 增加少量开销（元数据）

**实现难度**: 高
**优先级**: 低

#### 建议 7: 实现前向纠错 (FEC)

**当前**: 无纠错机制
**建议**: 使用 Opus FEC 或自定义 FEC

**Opus FEC 实现**:
```python
# 后端编码时启用 FEC
from opus.encoder import Encoder as OpusEncoder

encoder = OpusEncoder(16000, 1, 'voip')
encoder.set_inband_fec(True)
encoder.set_packet_loss_perc(10)  # 10% 丢包率

# 编码时包含 FEC 数据
data = encoder.encode(pcm, frame_size, fec=True)
```

```javascript
// 前端解码时使用 FEC
pcm = decoder.decode(data, frame_size, decode_fec=True);
```

**自定义 FEC 实现** (Reed-Solomon):
```javascript
// 使用 Reed-Solomon 编码
import ReedSolomon from 'reed-solomon';

class FecEncoder {
  constructor(dataShards = 4, parityShards = 2) {
    this.rs = new ReedSolomon(dataShards, parityShards);
  }

  encode(data) {
    // 将数据分成 dataShards 份
    const shards = this.splitData(data, this.rs.dataShards);
    // 生成 parityShards 份冗余数据
    const parity = this.rs.encode(shards);
    return { shards, parity };
  }
}

class FecDecoder {
  constructor(dataShards = 4, parityShards = 2) {
    this.rs = new ReedSolomon(dataShards, parityShards);
  }

  decode(shards, parity) {
    // 最多容忍 parityShards 个分片丢失
    const recovered = this.rs.decode([...shards, ...parity]);
    return this.combineData(recovered.slice(0, this.rs.dataShards));
  }
}
```

**优势**:
- 在丢包环境下提高音质
- 减少音频卡顿
- 提高用户体验

**劣势**:
- 增加带宽消耗 (25-50%)
- 增加编码/解码延迟
- 增加复杂度

**实现难度**: 高
**优先级**: 中

### 3.4 移动端优化

#### 建议 8: 优化移动端音频上下文

**当前**: 固定配置
**建议**: 根据设备类型动态配置

**实现方案** (mobile_audio_direct_copy.js):
```javascript
// 设备检测
const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent);

// 音频上下文配置
const audioContextOptions = {
  sampleRate: 16000,
  // iOS: 使用 playback 延迟提示
  // Android: 使用 interactive 延迟提示
  latencyHint: isIOS ? 'playback' : 'interactive',
  // iOS: 需要明确的通道配置
  channelCount: 1,
  channelInterpretation: 'speakers'
};

// 缓冲区大小
const BUFFER_SIZE = isMobile ? 1024 : 256;

// 播放器选择
let player;
if (isIOS && !window.AudioWorkletNode) {
  // iOS 回退到 ScriptProcessor
  player = createScriptProcessorPlayer();
} else if (window.AudioWorkletNode) {
  // 优先使用 AudioWorklet
  player = createAudioWorkletPlayer();
} else {
  // 旧浏览器回退
  player = createScriptProcessorPlayer();
}
```

**优势**:
- 更好的移动端兼容性
- 优化移动端性能
- 减少移动端延迟

**实现难度**: 低
**优先级**: 高

#### 建议 9: 实现音频预加载

**当前**: 实时流式传输
**建议**: 在 PTT 按下时预加载音频

**实现方案**:
```javascript
// TX 预加载
class TxPreloader {
  constructor(ws) {
    this.ws = ws;
    this.preloaded = false;
    this.preloadBuffer = [];
  }

  preload() {
    if (this.preloaded) return;

    // 在 PTT 按下前预先发送静音帧
    const silence = new Float32Array(160); // 10ms 静音
    for (let i = 0; i < 20; i++) { // 200ms 预加载
      this.ws.send(silence);
    }

    this.preloaded = true;
  }

  reset() {
    this.preloaded = false;
    this.preloadBuffer = [];
  }
}

// 使用
const preloader = new TxPreloader(wsAudioTX);

txButton.addEventListener('touchstart', () => {
  preloader.preload();
  // 发送实际 PTT 命令
  sendTRXptt(true);
});

txButton.addEventListener('touchend', () => {
  preloader.reset();
  sendTRXptt(false);
});
```

**优势**:
- 减少初始延迟
- 确保音频平滑开始
- 提高用户体验

**劣势**:
- 增加少量初始延迟
- 增加带宽消耗

**实现难度**: 低
**优先级**: 中

### 3.5 监控和调试优化

#### 建议 10: 实现实时音频质量监控

**当前**: 基础日志
**建议**: 可视化音频质量指标

**实现方案**:
```javascript
// 音频质量监控器
class AudioQualityMonitor {
  constructor() {
    this.metrics = {
      bitrate: 0,
      latency: 0,
      jitter: 0,
      packetLoss: 0,
      bufferHealth: 0
    };

    this.history = {
      bitrate: [],
      latency: [],
      jitter: []
    };

    this.maxHistory = 60; // 保存 60 秒历史
  }

  updateBitrate(bytes) {
    this.metrics.bitrate = bytes * 8 / 1000; // kbps
    this.history.bitrate.push(this.metrics.bitrate);
    if (this.history.bitrate.length > this.maxHistory) {
      this.history.bitrate.shift();
    }
  }

  updateLatency(latency) {
    this.metrics.latency = latency;
    this.history.latency.push(latency);
    if (this.history.latency.length > this.maxHistory) {
      this.history.latency.shift();
    }
  }

  updateJitter(jitter) {
    this.metrics.jitter = jitter;
    this.history.jitter.push(jitter);
    if (this.history.jitter.length > this.maxHistory) {
      this.history.jitter.shift();
    }
  }

  getScore() {
    // 计算综合质量评分 (0-100)
    let score = 100;

    // 比特率评分
    if (this.metrics.bitrate < 100) score -= 30;
    else if (this.metrics.bitrate < 200) score -= 15;

    // 延迟评分
    if (this.metrics.latency > 200) score -= 30;
    else if (this.metrics.latency > 100) score -= 15;

    // 抖动评分
    if (this.metrics.jitter > 50) score -= 30;
    else if (this.metrics.jitter > 20) score -= 15;

    return Math.max(0, score);
  }

  render() {
    // 渲染质量指标到 UI
    const score = this.getScore();
    const color = score > 80 ? 'green' : score > 50 ? 'yellow' : 'red';

    document.getElementById('quality-score').textContent = score;
    document.getElementById('quality-score').style.color = color;

    // 渲染历史图表
    this.renderChart('bitrate-chart', this.history.bitrate);
    this.renderChart('latency-chart', this.history.latency);
    this.renderChart('jitter-chart', this.history.jitter);
  }

  renderChart(elementId, data) {
    // 使用 Canvas 或 SVG 渲染简单图表
    const canvas = document.getElementById(elementId);
    const ctx = canvas.getContext('2d');

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (data.length < 2) return;

    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;

    ctx.beginPath();
    ctx.strokeStyle = 'blue';
    ctx.lineWidth = 2;

    for (let i = 0; i < data.length; i++) {
      const x = (i / (data.length - 1)) * canvas.width;
      const y = canvas.height - ((data[i] - min) / range) * canvas.height;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.stroke();
  }
}

// 使用
const monitor = new AudioQualityMonitor();

// 每秒更新一次
setInterval(() => {
  monitor.updateBitrate(window.__rxBytes || 0);
  monitor.render();
}, 1000);
```

**优势**:
- 实时了解音频质量
- 快速定位问题
- 优化用户体验

**实现难度**: 中
**优先级**: 中

---

## 四、优化优先级建议

### 高优先级 (立即实施)

1. **优化 Int16 转换性能** - 20-30% 性能提升
2. **实现自适应缓冲区深度** - 自动适应网络条件
3. **优化移动端音频上下文** - 更好的移动端兼容性

### 中优先级 (短期实施)

4. **实现动态批量发送策略** - 提高吞吐量
5. **实现音频预加载** - 减少初始延迟
6. **实现实时音频质量监控** - 快速定位问题
7. **实现自适应比特率 (ABR)** - 自动适应网络条件
8. **实现前向纠错 (FEC)** - 提高丢包环境下的音质

### 低优先级 (长期考虑)

9. **采用更高效的编码格式 (Opus/AAC)** - 进一步节省带宽
10. **实现 WebSocket 二进制分片** - 避免 MTU 限制

---

## 五、性能基准测试建议

### 5.1 测试指标

| 指标 | 当前值 | 目标值 | 测量方法 |
|------|--------|--------|----------|
| 端到端延迟 | <100ms | <80ms | PTT 按下到音频输出时间差 |
| 带宽消耗 | 256 kbps | 200 kbps | WebSocket 数据流量统计 |
| CPU 使用率 | 待测 | <30% | Performance API |
| 内存使用 | 待测 | <100MB | Performance API |
| 音频质量 | 待测 | MOS > 4.0 | 主观评分 |
| 丢包恢复率 | 待测 | >90% | 人为丢包测试 |

### 5.2 测试场景

1. **理想网络** (本地 Wi-Fi, <10ms RTT)
2. **中等网络** (4G, 50-100ms RTT)
3. **恶劣网络** (3G, >200ms RTT, 5-10% 丢包)
4. **移动端** (iOS Safari, Android Chrome)
5. **长时间运行** (24小时稳定性测试)

### 5.3 测试工具

```javascript
// 性能测试脚本
class PerformanceTester {
  constructor() {
    this.results = {
      latency: [],
      bandwidth: [],
      cpu: [],
      memory: []
    };
  }

  async measureLatency() {
    const start = performance.now();

    // 发送测试音频帧
    const testFrame = new Float32Array(160);
    wsAudioTX.send(testFrame);

    // 等待回环确认
    await new Promise(resolve => {
      const handler = (msg) => {
        if (msg.data === 'echo') {
          wsAudioTX.removeEventListener('message', handler);
          resolve();
        }
      };
      wsAudioTX.addEventListener('message', handler);
    });

    const latency = performance.now() - start;
    this.results.latency.push(latency);
    return latency;
  }

  measureBandwidth() {
    // 统计过去 1 秒的带宽
    return window.__rxBytes * 8 / 1000; // kbps
  }

  measureCPU() {
    // 使用 Performance API 估算 CPU 使用率
    if (performance.measureUserAgentSpecificMemory) {
      return performance.measureUserAgentSpecificMemory();
    }
    return null;
  }

  measureMemory() {
    // 使用 Performance API 获取内存使用
    if (performance.memory) {
      return performance.memory.usedJSHeapSize;
    }
    return null;
  }

  async runTest(duration = 60) {
    const startTime = Date.now();

    while (Date.now() - startTime < duration * 1000) {
      await this.measureLatency();
      this.results.bandwidth.push(this.measureBandwidth());
      this.results.cpu.push(await this.measureCPU());
      this.results.memory.push(this.measureMemory());

      await new Promise(resolve => setTimeout(resolve, 1000));
    }

    this.report();
  }

  report() {
    const avgLatency = this.results.latency.reduce((a, b) => a + b) / this.results.latency.length;
    const avgBandwidth = this.results.bandwidth.reduce((a, b) => a + b) / this.results.bandwidth.length;

    console.log('=== 性能测试报告 ===');
    console.log(`平均延迟: ${avgLatency.toFixed(2)} ms`);
    console.log(`平均带宽: ${avgBandwidth.toFixed(2)} kbps`);
    console.log(`延迟范围: ${Math.min(...this.results.latency)} - ${Math.max(...this.results.latency)} ms`);
    console.log(`带宽范围: ${Math.min(...this.results.bandwidth)} - ${Math.max(...this.results.bandwidth)} kbps`);
  }
}

// 运行测试
const tester = new PerformanceTester();
tester.runTest(60);
```

---

## 六、结论

MRRC 项目的音频流实现已经经过了多轮优化，当前的架构设计合理，性能表现良好。以下是主要结论：

### 6.1 当前优势

1. **低延迟**: TX→RX 切换延迟 <100ms
2. **带宽优化**: Int16 编码节省 50% 带宽
3. **稳定性强**: 多重缓冲和防抖机制
4. **跨平台**: 支持桌面和移动端
5. **PTT 可靠**: 预热帧机制确保发射成功

### 6.2 优化潜力

1. **性能提升**: 通过优化 Int16 转换可获得 20-30% 性能提升
2. **自适应能力**: 实现自适应缓冲区和比特率可进一步提高网络适应性
3. **移动端优化**: 专门的移动端配置可提高移动端性能
4. **监控能力**: 实时质量监控可快速定位和解决问题

### 6.3 实施建议

**第一阶段 (1-2周)**:
- 优化 Int16 转换性能
- 实现自适应缓冲区深度
- 优化移动端音频上下文

**第二阶段 (2-4周)**:
- 实现动态批量发送策略
- 实现音频预加载
- 实现实时音频质量监控

**第三阶段 (长期)**:
- 实现自适应比特率 (ABR)
- 实现前向纠错 (FEC)
- 评估更高效的编码格式

### 6.4 最终目标

通过实施上述优化，预期可以达到：

| 指标 | 当前值 | 优化后 | 提升 |
|------|--------|--------|------|
| 端到端延迟 | <100ms | <80ms | 20% |
| 带宽消耗 | 256 kbps | 200 kbps | 22% |
| CPU 使用率 | 待测 | <30% | - |
| 移动端兼容性 | 良好 | 优秀 | - |
| 网络适应性 | 中等 | 强 | - |

---

## 附录：关键代码位置索引

| 功能 | 文件 | 行号 |
|------|------|------|
| Int16 编码 | `audio_interface.py` | 165-172 |
| Int16 解码 | `www/controls.js` | 185-192 |
| RX Worklet | `www/rx_worklet_processor.js` | 全文 |
| TX 按钮控制 | `www/tx_button_optimized.js` | 全文 |
| PTT 预热帧 | `www/tx_button_optimized.js` | 68-89 |
| 缓冲区清除 | `www/tx_button_optimized.js` | 144-150 |
| RX 批量发送 | `MRRC` | 911-930 |
| PTT 超时机制 | `MRRC` | 688-698 |

---

**文档版本**: 1.0
**创建日期**: 2026-02-13
**作者**: MRRC 开发团队
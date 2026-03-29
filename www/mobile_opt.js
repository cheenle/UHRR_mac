/**
 * MRRC Optimized - 核心音频引擎
 * 基于 Web Audio API 1.1 规范的全新实现
 * 
 * 核心设计原则：
 * 1. 统一采样率 48kHz - 与硬件原生匹配
 * 2. 全面使用 AudioWorklet - 无 ScriptProcessor 回退
 * 3. 环形缓冲区 - 统一的缓冲区管理
 * 4. 独立模块 - 不依赖旧代码
 */

'use strict';

// ========== 配置常量 ==========
const CONFIG = {
    // 音频参数
    SAMPLE_RATE: 48000,        // 统一 48kHz
    FRAME_SIZE: 960,           // 20ms @ 48kHz
    CHANNELS: 1,               // 单声道
    BUFFER_TARGET: 3,          // 目标缓冲帧数
    BUFFER_MAX: 20,            // 最大缓冲帧数
    
    // WebSocket
    WS_RECONNECT_DELAY: 1000,
    WS_TIMEOUT: 5000,
    
    // 调谐步进 (Hz)
    TUNE_STEPS: [100, 1000, 5000, 10000],
    DEFAULT_STEP_INDEX: 1,     // 默认 1kHz
    
    // 波段 (Hz)
    BANDS: {
        '160m': [1800000, 2000000],
        '80m': [3500000, 4000000],
        '60m': [5250000, 5450000],
        '40m': [7000000, 7300000],
        '30m': [10100000, 10150000],
        '20m': [14000000, 14350000],
        '17m': [18068000, 18168000],
        '15m': [21000000, 21450000],
        '12m': [24890000, 24990000],
        '10m': [28000000, 29700000],
        '6m': [50000000, 54000000]
    },
    
    // 模式
    MODES: ['USB', 'LSB', 'CW', 'FM', 'AM', 'FT8'],
    
    // 滤波器带宽
    FILTERS: ['1.8k', '2.4k', '3.0k', '4.0k', '6.0k']
};

// ========== 环形缓冲区 ==========
class RingBuffer {
    constructor(capacity) {
        this.buffer = new Float32Array(capacity);
        this.capacity = capacity;
        this.writePos = 0;
        this.readPos = 0;
        this.size = 0;
    }
    
    write(data) {
        const len = data.length;
        if (len > this.capacity) {
            // 数据太大，只保留最新的部分
            const start = len - this.capacity;
            this.buffer.set(data.subarray(start));
            this.writePos = this.capacity;
            this.readPos = 0;
            this.size = this.capacity;
            return;
        }
        
        // 空间不足，先丢弃旧数据
        if (this.size + len > this.capacity) {
            const drop = this.size + len - this.capacity;
            this.readPos = (this.readPos + drop) % this.capacity;
            this.size -= drop;
        }
        
        // 写入数据
        const firstPart = Math.min(len, this.capacity - this.writePos);
        this.buffer.set(data.subarray(0, firstPart), this.writePos);
        
        if (firstPart < len) {
            this.buffer.set(data.subarray(firstPart), 0);
            this.writePos = len - firstPart;
        } else {
            this.writePos = (this.writePos + len) % this.capacity;
        }
        
        this.size += len;
    }
    
    read(output) {
        const len = output.length;
        if (this.size < len) {
            // 数据不足，填充静音
            output.fill(0);
            const available = this.size;
            if (available > 0) {
                this._readInternal(output, available);
                this.size = 0;
            }
            return false;
        }
        
        this._readInternal(output, len);
        this.size -= len;
        return true;
    }
    
    _readInternal(output, len) {
        const firstPart = Math.min(len, this.capacity - this.readPos);
        output.set(this.buffer.subarray(this.readPos, this.readPos + firstPart));
        
        if (firstPart < len) {
            output.set(this.buffer.subarray(0, len - firstPart), firstPart);
            this.readPos = len - firstPart;
        } else {
            this.readPos = (this.readPos + len) % this.capacity;
        }
    }
    
    clear() {
        this.writePos = 0;
        this.readPos = 0;
        this.size = 0;
    }
    
    available() {
        return this.size;
    }
}

// ========== AudioWorklet 处理器代码 ==========
const WORKLET_CODE = `
class OptimizedProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.ringBuffer = new Float32Array(48000); // 1秒缓冲
        this.writePos = 0;
        this.readPos = 0;
        this.available = 0;
        
        this.port.onmessage = (e) => {
            if (e.data.type === 'push') {
                this._push(e.data.samples);
            } else if (e.data.type === 'clear') {
                this.available = 0;
                this.writePos = 0;
                this.readPos = 0;
            }
        };
    }
    
    _push(data) {
        const len = data.length;
        for (let i = 0; i < len; i++) {
            this.ringBuffer[this.writePos] = data[i];
            this.writePos = (this.writePos + 1) % this.ringBuffer.length;
        }
        this.available = Math.min(this.available + len, this.ringBuffer.length);
    }
    
    process(inputs, outputs) {
        const output = outputs[0];
        const channel = output[0];
        
        if (this.available >= channel.length) {
            for (let i = 0; i < channel.length; i++) {
                channel[i] = this.ringBuffer[this.readPos];
                this.readPos = (this.readPos + 1) % this.ringBuffer.length;
            }
            this.available -= channel.length;
        } else {
            // 欠载，输出静音
            channel.fill(0);
        }
        
        return true;
    }
}

registerProcessor('optimized-processor', OptimizedProcessor);
`;

// ========== 音频引擎 ==========
class AudioEngine {
    constructor() {
        // AudioContext
        this.context = null;
        this.sampleRate = CONFIG.SAMPLE_RATE;
        
        // 节点
        this.workletNode = null;
        this.gainNode = null;
        this.analyserNode = null;
        this.micSource = null;
        this.micStream = null;
        
        // 状态
        this.isInitialized = false;
        this.isTxActive = false;
        
        // 缓冲区
        this.ringBuffer = new RingBuffer(CONFIG.SAMPLE_RATE); // 1秒
        
        // 统计
        this.stats = {
            rxPackets: 0,
            rxBytes: 0,
            txPackets: 0,
            txBytes: 0,
            underruns: 0,
            latency: 0
        };
    }
    
    // 初始化
    async init() {
        if (this.isInitialized) return true;
        
        try {
            // 创建 AudioContext（强制 48kHz）
            this.context = new (window.AudioContext || window.webkitAudioContext)({
                latencyHint: 'interactive',
                sampleRate: this.sampleRate
            });
            
            // iOS Safari: 可能需要用户交互后 resume
            if (this.context.state === 'suspended') {
                await this.context.resume();
            }
            
            // 创建增益节点
            this.gainNode = this.context.createGain();
            this.gainNode.gain.value = 0.5;
            
            // 创建分析器
            this.analyserNode = this.context.createAnalyser();
            this.analyserNode.fftSize = 256;
            
            // 创建 AudioWorklet
            const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
            const url = URL.createObjectURL(blob);
            await this.context.audioWorklet.addModule(url);
            URL.revokeObjectURL(url);
            
            this.workletNode = new AudioWorkletNode(this.context, 'optimized-processor');
            
            // 连接节点
            this.workletNode.connect(this.gainNode);
            this.gainNode.connect(this.analyserNode);
            this.analyserNode.connect(this.context.destination);
            
            this.isInitialized = true;
            console.log('✅ 音频引擎初始化完成', {
                sampleRate: this.context.sampleRate,
                state: this.context.state
            });
            
            return true;
        } catch (error) {
            console.error('❌ 音频引擎初始化失败:', error);
            return false;
        }
    }
    
    // 恢复（iOS Safari 需要）
    async resume() {
        if (this.context && this.context.state === 'suspended') {
            await this.context.resume();
        }
    }
    
    // 设置音量
    setVolume(value) {
        if (this.gainNode) {
            this.gainNode.gain.value = Math.max(0, Math.min(1, value));
        }
    }
    
    // 接收音频数据
    receiveAudio(data) {
        if (!this.workletNode) return;
        
        try {
            let float32;
            
            // 检测数据类型：Opus 帧通常较小 (<500 bytes)，Int16 帧较大 (512+ bytes)
            if (data.byteLength < 500 && typeof OpusDecoder !== 'undefined') {
                // Opus 解码
                float32 = this._decodeOpus(data);
            } else {
                // Int16 解码
                float32 = this._decodeInt16(data);
            }
            
            if (!float32) return;
            
            // 发送到 Worklet
            this.workletNode.port.postMessage({
                type: 'push',
                samples: float32
            });
            
            this.stats.rxPackets++;
            this.stats.rxBytes += data.byteLength;
            
            // 更新最后接收时间（用于丢包检测）
            this._lastRxTime = performance.now();
        } catch (e) {
            console.error('音频解码错误:', e);
        }
    }
    
    // Opus 解码 - 支持丢包隐藏 (PLC)
    _decodeOpus(data) {
        const opusRate = 16000;  // Opus 解码采样率
        const contextRate = this.sampleRate;  // AudioContext 采样率 (48kHz)
        
        // 初始化解码器
        if (!this._opusDecoder || this._opusDecoder._rate !== opusRate) {
            if (typeof OpusDecoder === 'undefined') {
                console.error('OpusDecoder 不可用');
                return null;
            }
            this._opusDecoder = new OpusDecoder(opusRate, 1);
            this._opusDecoder._rate = opusRate;
            this._lastRxTime = performance.now();
            console.log('✅ RX Opus 解码器初始化:', opusRate, 'Hz (支持 PLC)');
        }
        
        // 解码得到 Int16
        const int16 = this._opusDecoder.decode(data);
        
        // 重采样 16kHz → 48kHz（使用抗混叠滤波）
        if (contextRate !== opusRate) {
            return this._resampleWithFilter(int16, opusRate, contextRate);
        }
        
        // 直接转换 Int16 → Float32
        const float32 = new Float32Array(int16.length);
        const scale = 1.0 / 32767.0;
        for (let i = 0; i < int16.length; i++) {
            float32[i] = int16[i] * scale;
        }
        return float32;
    }
    
    // PLC 丢包隐藏 - 在检测到丢包时调用
    _decodePLC() {
        const opusRate = 16000;
        const contextRate = this.sampleRate;
        
        if (!this._opusDecoder) return null;
        
        try {
            // 使用 Opus 内置 PLC 生成补偿帧
            const int16 = this._opusDecoder.decode_plc();
            
            // 重采样
            if (contextRate !== opusRate) {
                return this._resampleWithFilter(int16, opusRate, contextRate);
            }
            
            const float32 = new Float32Array(int16.length);
            const scale = 1.0 / 32767.0;
            for (let i = 0; i < int16.length; i++) {
                float32[i] = int16[i] * scale;
            }
            return float32;
        } catch (e) {
            console.warn('PLC 解码失败:', e);
            return null;
        }
    }
    
    // Int16 解码
    _decodeInt16(data) {
        // 检查数据长度是否为 2 的倍数
        if (data.byteLength % 2 !== 0) {
            data = data.slice(0, data.byteLength - 1);
        }
        
        const int16 = new Int16Array(data);
        const float32 = new Float32Array(int16.length);
        const scale = 1.0 / 32767.0;
        
        for (let i = 0; i < int16.length; i++) {
            float32[i] = int16[i] * scale;
        }
        return float32;
    }
    
    // 线性重采样（简单版本）
    _resample(int16Data, fromRate, toRate) {
        const ratio = fromRate / toRate;
        const outputLength = Math.floor(int16Data.length / ratio);
        const float32 = new Float32Array(outputLength);
        const scale = 1.0 / 32767.0;
        
        for (let i = 0; i < outputLength; i++) {
            const srcIndex = i * ratio;
            const srcIndexInt = Math.floor(srcIndex);
            const nextIndex = Math.min(srcIndexInt + 1, int16Data.length - 1);
            const fraction = srcIndex - srcIndexInt;
            
            // 线性插值
            float32[i] = (int16Data[srcIndexInt] * (1 - fraction) + 
                          int16Data[nextIndex] * fraction) * scale;
        }
        return float32;
    }
    
    // ========== 高质量重采样（带抗混叠滤波）==========
    // 使用 Lanczos 插值 + 低通滤波，避免混叠失真
    // 参考: https://ccrma.stanford.edu/~jos/resample/
    _resampleWithFilter(int16Data, fromRate, toRate) {
        const ratio = fromRate / toRate;
        const outputLength = Math.floor(int16Data.length / ratio);
        
        // 先转换为 Float32
        const input = new Float32Array(int16Data.length);
        const scale = 1.0 / 32767.0;
        for (let i = 0; i < int16Data.length; i++) {
            input[i] = int16Data[i] * scale;
        }
        
        // 如果是上采样（如 16k → 48k），直接插值即可，无混叠风险
        // 如果是下采样，需要先低通滤波
        if (ratio < 1) {
            // 上采样：直接使用 Lanczos 插值
            return this._lanczosResample(input, ratio, outputLength);
        } else {
            // 下采样：先低通滤波再降采样
            // Nyquist 频率 = toRate / 2
            // 我们需要滤除高于 toRate/2 的频率成分
            const cutoff = 0.5 / ratio;  // 归一化截止频率
            const filtered = this._lowpassFilter(input, cutoff);
            return this._lanczosResample(filtered, ratio, outputLength);
        }
    }
    
    // Lanczos 插值重采样
    _lanczosResample(input, ratio, outputLength) {
        const output = new Float32Array(outputLength);
        const a = 3;  // Lanczos 窗口大小
        
        for (let i = 0; i < outputLength; i++) {
            const srcIndex = i * ratio;
            const srcIndexInt = Math.floor(srcIndex);
            let sum = 0;
            let weightSum = 0;
            
            for (let j = -a + 1; j <= a; j++) {
                const idx = srcIndexInt + j;
                if (idx >= 0 && idx < input.length) {
                    const x = srcIndex - idx;
                    const weight = this._lanczosKernel(x, a);
                    sum += input[idx] * weight;
                    weightSum += weight;
                }
            }
            
            output[i] = weightSum > 0 ? sum / weightSum : 0;
        }
        
        return output;
    }
    
    // Lanczos 核函数
    _lanczosKernel(x, a) {
        if (x === 0) return 1;
        if (Math.abs(x) >= a) return 0;
        const pix = Math.PI * x;
        return (a * Math.sin(pix) * Math.sin(pix / a)) / (pix * pix);
    }
    
    // 简单低通滤波器（FIR）
    _lowpassFilter(input, cutoff) {
        // 使用 sinc 滤波器
        const filterLen = 33;  // 滤波器长度（奇数）
        const halfLen = Math.floor(filterLen / 2);
        const filter = new Float32Array(filterLen);
        
        // 生成 sinc 滤波器系数
        for (let i = 0; i < filterLen; i++) {
            const n = i - halfLen;
            if (n === 0) {
                filter[i] = 2 * cutoff;
            } else {
                const x = Math.PI * n * 2 * cutoff;
                filter[i] = Math.sin(x) / x * 2 * cutoff;
            }
            // 汉宁窗
            filter[i] *= 0.5 * (1 - Math.cos(2 * Math.PI * i / (filterLen - 1)));
        }
        
        // 归一化
        let sum = 0;
        for (let i = 0; i < filterLen; i++) sum += filter[i];
        for (let i = 0; i < filterLen; i++) filter[i] /= sum;
        
        // 卷积
        const output = new Float32Array(input.length);
        for (let i = 0; i < input.length; i++) {
            let val = 0;
            for (let j = 0; j < filterLen; j++) {
                const idx = i + j - halfLen;
                if (idx >= 0 && idx < input.length) {
                    val += input[idx] * filter[j];
                }
            }
            output[i] = val;
        }
        
        return output;
    }
    
    // 开始 TX
    async startTX() {
        if (this.isTxActive) return;
        
        try {
            // 请求麦克风权限
            this.micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: this.sampleRate,
                    channelCount: 1,
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false
                }
            });
            
            // 创建麦克风源
            this.micSource = this.context.createMediaStreamSource(this.micStream);
            
            // 使用 ScriptProcessor 进行编码（临时方案）
            // TODO: 迁移到 AudioWorklet
            const processor = this.context.createScriptProcessor(960, 1, 1);
            
            processor.onaudioprocess = (e) => {
                if (!this.isTxActive) return;
                
                const input = e.inputBuffer.getChannelData(0);
                // 发送到后端
                this._sendTXAudio(input);
            };
            
            this.micSource.connect(processor);
            processor.connect(this.context.destination);
            this.txProcessor = processor;
            
            // 停止 RX 音频
            this.workletNode.port.postMessage({ type: 'clear' });
            
            this.isTxActive = true;
            console.log('🎙️ TX 开始');
            
        } catch (error) {
            console.error('❌ TX 启动失败:', error);
        }
    }
    
    // 停止 TX
    stopTX() {
        if (!this.isTxActive) return;
        
        // 停止麦克风
        if (this.micStream) {
            this.micStream.getTracks().forEach(track => track.stop());
            this.micStream = null;
        }
        
        // 断开节点
        if (this.micSource) {
            this.micSource.disconnect();
            this.micSource = null;
        }
        
        if (this.txProcessor) {
            this.txProcessor.disconnect();
            this.txProcessor = null;
        }
        
        this.isTxActive = false;
        console.log('🎙️ TX 停止');
    }
    
    // 发送 TX 音频
    _sendTXAudio(float32) {
        if (!window.app || !window.app.wsTX) return;
        
        // Float32 → Int16
        const int16 = new Int16Array(float32.length);
        for (let i = 0; i < float32.length; i++) {
            int16[i] = Math.max(-32768, Math.min(32767, Math.round(float32[i] * 32767)));
        }
        
        // 发送
        window.app.wsTX.send(int16.buffer);
        
        this.stats.txPackets++;
        this.stats.txBytes += int16.buffer.byteLength;
    }
    
    // 获取 S 表值
    getSMeter() {
        if (!this.analyserNode) return 0;
        
        const data = new Uint8Array(this.analyserNode.frequencyBinCount);
        this.analyserNode.getByteFrequencyData(data);
        
        // 计算平均值
        let sum = 0;
        for (let i = 0; i < data.length; i++) {
            sum += data[i];
        }
        const avg = sum / data.length;
        
        // 转换为 S 单位 (0-9+60)
        const s = Math.floor(avg / 25.5); // 255 / 10 = 25.5
        return Math.min(15, Math.max(0, s)); // S0-S9+60 = 0-15
    }
    
    // 关闭
    close() {
        this.stopTX();
        
        if (this.context) {
            this.context.close();
            this.context = null;
        }
        
        this.isInitialized = false;
    }
}

// ========== WebSocket 管理 ==========
class WebSocketManager {
    constructor() {
        this.wsControl = null;
        this.wsRX = null;
        this.wsTX = null;
        
        this.reconnectTimer = null;
        this.isConnected = false;
    }
    
    // 连接
    connect(host, onMessage) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const baseUrl = `${protocol}//${host}`;
        
        // 控制通道
        this.wsControl = new WebSocket(`${baseUrl}/WSControlTRX`);
        this.wsControl.binaryType = 'arraybuffer';
        
        this.wsControl.onopen = () => {
            console.log('✅ 控制通道已连接');
            this._updateStatus('status-ctl', true);
            this._syncState();
        };
        
        this.wsControl.onmessage = (e) => {
            onMessage('control', e.data);
        };
        
        this.wsControl.onclose = () => {
            this._updateStatus('status-ctl', false);
            this._scheduleReconnect(host, onMessage);
        };
        
        this.wsControl.onerror = (e) => {
            console.error('控制通道错误:', e);
        };
        
        // RX 音频通道
        this.wsRX = new WebSocket(`${baseUrl}/WSaudioRX`);
        this.wsRX.binaryType = 'arraybuffer';
        
        this.wsRX.onopen = () => {
            console.log('✅ RX 通道已连接');
            this._updateStatus('status-rx', true);
        };
        
        this.wsRX.onmessage = (e) => {
            onMessage('rx', e.data);
        };
        
        this.wsRX.onclose = () => {
            this._updateStatus('status-rx', false);
        };
        
        // TX 音频通道
        this.wsTX = new WebSocket(`${baseUrl}/WSaudioTX`);
        this.wsTX.binaryType = 'arraybuffer';
        
        this.wsTX.onopen = () => {
            console.log('✅ TX 通道已连接');
            this._updateStatus('status-tx', true);
        };
        
        this.wsTX.onclose = () => {
            this._updateStatus('status-tx', false);
        };
    }
    
    // 同步状态
    _syncState() {
        this.send('getFreq');
        this.send('getMode');
    }
    
    // 发送命令
    send(action, data) {
        if (this.wsControl && this.wsControl.readyState === WebSocket.OPEN) {
            const msg = data ? `${action}:${data}` : action;
            this.wsControl.send(msg);
        }
    }
    
    // 更新状态显示
    _updateStatus(id, connected) {
        const el = document.getElementById(id);
        if (el) {
            el.classList.toggle('connected', connected);
        }
    }
    
    // 重连
    _scheduleReconnect(host, onMessage) {
        if (this.reconnectTimer) return;
        
        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.connect(host, onMessage);
        }, CONFIG.WS_RECONNECT_DELAY);
    }
    
    // 断开
    disconnect() {
        if (this.wsControl) this.wsControl.close();
        if (this.wsRX) this.wsRX.close();
        if (this.wsTX) this.wsTX.close();
        
        this.wsControl = null;
        this.wsRX = null;
        this.wsTX = null;
        this.isConnected = false;
    }
}

// ========== 应用主类 ==========
class MRRCApp {
    constructor() {
        // 状态
        this.state = {
            powerOn: false,
            frequency: 7053000,
            mode: 'USB',
            band: '40m',
            filter: '2.4k',
            tuneStepIndex: CONFIG.DEFAULT_STEP_INDEX,
            volume: 50,
            dspEnabled: false,
            nrEnabled: false,
            nbEnabled: false
        };
        
        // 组件
        this.audio = new AudioEngine();
        this.ws = new WebSocketManager();
        
        // DOM 缓存
        this.dom = {};
        
        // Wake Lock
        this.wakeLock = null;
    }
    
    // 初始化
    async init() {
        console.log('🚀 MRRC Optimized 初始化...');
        
        // 缓存 DOM
        this._cacheDom();
        
        // 绑定事件
        this._bindEvents();
        
        // 初始化菜单
        this._initMenus();
        
        // 加载设置
        this._loadSettings();
        
        // 更新显示
        this._updateDisplay();
        
        console.log('✅ MRRC Optimized 初始化完成');
    }
    
    // 缓存 DOM
    _cacheDom() {
        this.dom = {
            btnPower: document.getElementById('btn-power'),
            btnMenu: document.getElementById('btn-menu'),
            btnPtt: document.getElementById('btn-ptt'),
            btnTune: document.getElementById('btn-tune'),
            btnRecord: document.getElementById('btn-record'),
            btnMode: document.getElementById('btn-mode'),
            btnBand: document.getElementById('btn-band'),
            btnFilter: document.getElementById('btn-filter'),
            btnDsp: document.getElementById('btn-dsp'),
            
            freqDisplay: document.getElementById('freq-display'),
            sBar: document.getElementById('s-bar'),
            sValue: document.getElementById('s-value'),
            pwrValue: document.getElementById('pwr-value'),
            swrValue: document.getElementById('swr-value'),
            volumeSlider: document.getElementById('volume-slider'),
            volumeValue: document.getElementById('volume-value'),
            stepDisplay: document.getElementById('step-display'),
            latencyValue: document.getElementById('latency-value'),
            bufferValue: document.getElementById('buffer-value'),
            
            menuPanel: document.getElementById('menu-panel'),
            overlay: document.getElementById('overlay'),
            bandGrid: document.getElementById('band-grid'),
            modeGrid: document.getElementById('mode-grid'),
            filterGrid: document.getElementById('filter-grid'),
            dspOptions: document.getElementById('dsp-options'),
            
            statusMode: document.getElementById('status-mode')
        };
    }
    
    // 绑定事件
    _bindEvents() {
        // 电源按钮
        this.dom.btnPower?.addEventListener('click', () => this._togglePower());
        
        // 菜单
        this.dom.btnMenu?.addEventListener('click', () => this._openMenu());
        document.getElementById('btn-close-menu')?.addEventListener('click', () => this._closeMenu());
        this.dom.overlay?.addEventListener('click', () => this._closeMenu());
        
        // PTT
        this._bindPTT();
        
        // TUNE
        this.dom.btnTune?.addEventListener('touchstart', (e) => {
            e.preventDefault();
            this._startTune();
        });
        this.dom.btnTune?.addEventListener('touchend', () => this._stopTune());
        this.dom.btnTune?.addEventListener('mousedown', () => this._startTune());
        this.dom.btnTune?.addEventListener('mouseup', () => this._stopTune());
        this.dom.btnTune?.addEventListener('mouseleave', () => this._stopTune());
        
        // 录音
        this.dom.btnRecord?.addEventListener('click', () => this._toggleRecord());
        
        // 快捷按钮
        this.dom.btnMode?.addEventListener('click', () => this._cycleMode());
        this.dom.btnBand?.addEventListener('click', () => this._cycleBand());
        this.dom.btnFilter?.addEventListener('click', () => this._cycleFilter());
        this.dom.btnDsp?.addEventListener('click', () => this._toggleDsp());
        
        // 音量
        this.dom.volumeSlider?.addEventListener('input', (e) => {
            this._setVolume(parseInt(e.target.value));
        });
        
        // 调谐按钮
        document.querySelectorAll('.tune-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const delta = parseInt(btn.dataset.delta);
                this._tune(delta);
            });
        });
        
        // 步进切换
        this.dom.stepDisplay?.addEventListener('click', () => this._cycleStep());
        
        // 频率显示点击
        this.dom.freqDisplay?.addEventListener('click', () => this._showFreqInput());
        
        // 用户交互恢复音频
        document.addEventListener('touchstart', () => this.audio.resume(), { once: true });
        document.addEventListener('mousedown', () => this.audio.resume(), { once: true });
        
        // 页面可见性
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible' && this.state.powerOn) {
                this._requestWakeLock();
            }
        });
    }
    
    // PTT 事件绑定
    _bindPTT() {
        const btn = this.dom.btnPtt;
        if (!btn) return;
        
        let touchId = null;
        
        // 触摸开始
        btn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            if (touchId !== null) return;
            touchId = e.touches[0].identifier;
            this._startPTT();
        });
        
        // 触摸结束
        btn.addEventListener('touchend', (e) => {
            e.preventDefault();
            const touch = e.changedTouches[0];
            if (touch.identifier === touchId) {
                touchId = null;
                this._stopPTT();
            }
        });
        
        btn.addEventListener('touchcancel', (e) => {
            touchId = null;
            this._stopPTT();
        });
        
        // 鼠标
        btn.addEventListener('mousedown', (e) => {
            e.preventDefault();
            this._startPTT();
        });
        
        btn.addEventListener('mouseup', () => this._stopPTT());
        btn.addEventListener('mouseleave', () => this._stopPTT());
        
        // 防止长按菜单
        btn.addEventListener('contextmenu', (e) => e.preventDefault());
    }
    
    // 电源开关
    async _togglePower() {
        if (this.state.powerOn) {
            // 关闭
            this.state.powerOn = false;
            this.ws.disconnect();
            this.audio.close();
            this._releaseWakeLock();
            
            this.dom.btnPower?.classList.remove('active');
            console.log('🔴 电源关闭');
        } else {
            // 开启
            const success = await this.audio.init();
            if (!success) {
                alert('音频初始化失败');
                return;
            }
            
            const host = window.location.host;
            this.ws.connect(host, this._onWSMessage.bind(this));
            
            this.state.powerOn = true;
            this._requestWakeLock();
            
            this.dom.btnPower?.classList.add('active');
            console.log('🟢 电源开启');
        }
    }
    
    // WebSocket 消息处理
    _onWSMessage(type, data) {
        if (type === 'control') {
            this._handleControlMessage(data);
        } else if (type === 'rx') {
            this.audio.receiveAudio(data);
        }
    }
    
    // 控制消息处理
    _handleControlMessage(data) {
        if (typeof data === 'string') {
            if (data.startsWith('getFreq:')) {
                this.state.frequency = parseInt(data.split(':')[1]);
                this._updateFreqDisplay();
            } else if (data.startsWith('getMode:')) {
                this.state.mode = data.split(':')[1];
                this._updateModeDisplay();
            }
        }
    }
    
    // 开始 PTT
    async _startPTT() {
        if (!this.state.powerOn) return;
        
        this.dom.btnPtt?.classList.add('pressed');
        
        // 发送 PTT 命令
        this.ws.send('setPTT', 'True');
        
        // 开始 TX
        await this.audio.startTX();
        
        // 更新状态
        document.getElementById('status-tx')?.classList.add('connected');
    }
    
    // 停止 PTT
    _stopPTT() {
        this.dom.btnPtt?.classList.remove('pressed');
        
        // 停止 TX
        this.audio.stopTX();
        
        // 发送 PTT 停止
        this.ws.send('setPTT', 'False');
        
        // 更新状态
        document.getElementById('status-tx')?.classList.remove('connected');
    }
    
    // 调谐频率
    _tune(delta) {
        const step = CONFIG.TUNE_STEPS[this.state.tuneStepIndex];
        const actualDelta = delta > 0 ? step : -step;
        
        this.state.frequency = Math.max(1000000, Math.min(54000000, this.state.frequency + actualDelta));
        this._updateFreqDisplay();
        
        // 发送命令
        this.ws.send('setFreq', this.state.frequency.toString());
    }
    
    // 切换步进
    _cycleStep() {
        this.state.tuneStepIndex = (this.state.tuneStepIndex + 1) % CONFIG.TUNE_STEPS.length;
        this._updateStepDisplay();
    }
    
    // 更新步进显示
    _updateStepDisplay() {
        const step = CONFIG.TUNE_STEPS[this.state.tuneStepIndex];
        if (this.dom.stepDisplay) {
            if (step >= 1000) {
                this.dom.stepDisplay.textContent = `${step / 1000}kHz`;
            } else {
                this.dom.stepDisplay.textContent = `${step}Hz`;
            }
        }
    }
    
    // 更新频率显示
    _updateFreqDisplay() {
        const freq = this.state.frequency;
        const mhz = Math.floor(freq / 1000000);
        const khz = Math.floor((freq % 1000000) / 1000);
        const hz = freq % 1000;
        
        if (this.dom.freqDisplay) {
            this.dom.freqDisplay.innerHTML = `
                <span class="freq-mhz">${mhz}.${String(khz).padStart(3, '0')}</span>
                <span class="freq-khz">.${String(hz).padStart(3, '0')}</span>
                <span class="freq-unit">MHz</span>
            `;
        }
        
        // 更新波段
        for (const [band, [low, high]] of Object.entries(CONFIG.BANDS)) {
            if (freq >= low && freq <= high) {
                this.state.band = band;
                break;
            }
        }
    }
    
    // 更新模式显示
    _updateModeDisplay() {
        if (this.dom.btnMode) {
            this.dom.btnMode.textContent = this.state.mode;
        }
        if (this.dom.statusMode) {
            this.dom.statusMode.textContent = this.state.mode;
        }
    }
    
    // 设置音量
    _setVolume(value) {
        this.state.volume = value;
        this.audio.setVolume(value / 100);
        
        if (this.dom.volumeValue) {
            this.dom.volumeValue.textContent = `${value}%`;
        }
        
        this._saveSettings();
    }
    
    // 循环模式
    _cycleMode() {
        const idx = CONFIG.MODES.indexOf(this.state.mode);
        this.state.mode = CONFIG.MODES[(idx + 1) % CONFIG.MODES.length];
        this._updateModeDisplay();
        this.ws.send('setMode', this.state.mode);
    }
    
    // 循环波段
    _cycleBand() {
        const bands = Object.keys(CONFIG.BANDS);
        const idx = bands.indexOf(this.state.band);
        this.state.band = bands[(idx + 1) % bands.length];
        
        // 跳转到波段中心
        const [low, high] = CONFIG.BANDS[this.state.band];
        this.state.frequency = Math.floor((low + high) / 2);
        this._updateFreqDisplay();
        this.ws.send('setFreq', this.state.frequency.toString());
        
        if (this.dom.btnBand) {
            this.dom.btnBand.textContent = this.state.band;
        }
    }
    
    // 循环滤波器
    _cycleFilter() {
        const idx = CONFIG.FILTERS.indexOf(this.state.filter);
        this.state.filter = CONFIG.FILTERS[(idx + 1) % CONFIG.FILTERS.length];
        
        if (this.dom.btnFilter) {
            this.dom.btnFilter.textContent = this.state.filter;
        }
    }
    
    // 切换 DSP
    _toggleDsp() {
        this.state.dspEnabled = !this.state.dspEnabled;
        this.dom.btnDsp?.classList.toggle('active', this.state.dspEnabled);
    }
    
    // TUNE
    _startTune() {
        if (!this.state.powerOn) return;
        this.dom.btnTune?.classList.add('active');
        // TODO: 发送 TUNE 命令
    }
    
    _stopTune() {
        this.dom.btnTune?.classList.remove('active');
    }
    
    // 录音
    _toggleRecord() {
        // TODO: 实现录音
        this.dom.btnRecord?.classList.toggle('recording');
    }
    
    // 菜单
    _openMenu() {
        this.dom.menuPanel?.classList.add('open');
        this.dom.overlay?.classList.add('show');
    }
    
    _closeMenu() {
        this.dom.menuPanel?.classList.remove('open');
        this.dom.overlay?.classList.remove('show');
    }
    
    // 初始化菜单
    _initMenus() {
        // 波段
        if (this.dom.bandGrid) {
            this.dom.bandGrid.innerHTML = Object.keys(CONFIG.BANDS).map(band => 
                `<button>${band}</button>`
            ).join('');
            
            this.dom.bandGrid.querySelectorAll('button').forEach(btn => {
                btn.addEventListener('click', () => {
                    this.state.band = btn.textContent;
                    const [low, high] = CONFIG.BANDS[this.state.band];
                    this.state.frequency = Math.floor((low + high) / 2);
                    this._updateFreqDisplay();
                    this.ws.send('setFreq', this.state.frequency.toString());
                    this._closeMenu();
                });
            });
        }
        
        // 模式
        if (this.dom.modeGrid) {
            this.dom.modeGrid.innerHTML = CONFIG.MODES.map(mode => 
                `<button>${mode}</button>`
            ).join('');
            
            this.dom.modeGrid.querySelectorAll('button').forEach(btn => {
                btn.addEventListener('click', () => {
                    this.state.mode = btn.textContent;
                    this._updateModeDisplay();
                    this.ws.send('setMode', this.state.mode);
                    this._closeMenu();
                });
            });
        }
        
        // 滤波器
        if (this.dom.filterGrid) {
            this.dom.filterGrid.innerHTML = CONFIG.FILTERS.map(f => 
                `<button>${f}</button>`
            ).join('');
            
            this.dom.filterGrid.querySelectorAll('button').forEach(btn => {
                btn.addEventListener('click', () => {
                    this.state.filter = btn.textContent;
                    if (this.dom.btnFilter) {
                        this.dom.btnFilter.textContent = this.state.filter;
                    }
                    this._closeMenu();
                });
            });
        }
        
        // DSP 选项
        if (this.dom.dspOptions) {
            this.dom.dspOptions.innerHTML = `
                <div class="dsp-row">
                    <span class="dsp-label">NR 降噪</span>
                    <div class="dsp-toggle" id="dsp-nr"></div>
                </div>
                <div class="dsp-row">
                    <span class="dsp-label">NB 噪声抑制</span>
                    <div class="dsp-toggle" id="dsp-nb"></div>
                </div>
            `;
            
            this.dom.dspOptions.querySelectorAll('.dsp-toggle').forEach(toggle => {
                toggle.addEventListener('click', () => {
                    toggle.classList.toggle('active');
                });
            });
        }
    }
    
    // S 表监控
    _startSMeterMonitor() {
        const update = () => {
            if (!this.state.powerOn) return;
            
            const s = this.audio.getSMeter();
            
            // 更新条形图
            if (this.dom.sBar) {
                const percent = Math.min(100, (s / 15) * 100);
                this.dom.sBar.style.width = `${percent}%`;
            }
            
            // 更新数值
            if (this.dom.sValue) {
                if (s <= 9) {
                    this.dom.sValue.textContent = `S${s}`;
                } else {
                    this.dom.sValue.textContent = `S9+${(s - 9) * 10}`;
                }
            }
            
            requestAnimationFrame(update);
        };
        
        update();
    }
    
    // 更新显示
    _updateDisplay() {
        this._updateFreqDisplay();
        this._updateModeDisplay();
        this._updateStepDisplay();
        
        if (this.dom.btnBand) {
            this.dom.btnBand.textContent = this.state.band;
        }
        if (this.dom.btnFilter) {
            this.dom.btnFilter.textContent = this.state.filter;
        }
        if (this.dom.volumeSlider) {
            this.dom.volumeSlider.value = this.state.volume;
        }
        if (this.dom.volumeValue) {
            this.dom.volumeValue.textContent = `${this.state.volume}%`;
        }
    }
    
    // 设置保存/加载
    _saveSettings() {
        const settings = {
            volume: this.state.volume,
            mode: this.state.mode,
            filter: this.state.filter,
            tuneStepIndex: this.state.tuneStepIndex
        };
        localStorage.setItem('mrrc_opt_settings', JSON.stringify(settings));
    }
    
    _loadSettings() {
        try {
            const saved = localStorage.getItem('mrrc_opt_settings');
            if (saved) {
                const settings = JSON.parse(saved);
                Object.assign(this.state, settings);
            }
        } catch (e) {
            console.warn('加载设置失败:', e);
        }
    }
    
    // Wake Lock
    async _requestWakeLock() {
        if ('wakeLock' in navigator) {
            try {
                this.wakeLock = await navigator.wakeLock.request('screen');
            } catch (e) {
                // 忽略
            }
        }
    }
    
    async _releaseWakeLock() {
        if (this.wakeLock) {
            await this.wakeLock.release();
            this.wakeLock = null;
        }
    }
    
    // 频率输入
    _showFreqInput() {
        const input = prompt('输入频率 (kHz):', Math.floor(this.state.frequency / 1000));
        if (input) {
            const freq = parseInt(input) * 1000;
            if (!isNaN(freq) && freq >= 1000000 && freq <= 54000000) {
                this.state.frequency = freq;
                this._updateFreqDisplay();
                this.ws.send('setFreq', this.state.frequency.toString());
            }
        }
    }
}

// ========== 启动 ==========
document.addEventListener('DOMContentLoaded', async () => {
    window.app = new MRRCApp();
    await window.app.init();
    
    // 开始 S 表监控
    window.app._startSMeterMonitor();
});

// 导出
window.MRRCApp = MRRCApp;

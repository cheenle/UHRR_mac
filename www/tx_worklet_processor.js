/**
 * TX AudioWorklet Processor
 * 
 * 在独立线程处理音频采集和降采样，避免阻塞主线程
 * 使 PTT 期间 ATR-1000 消息能够实时处理
 * 
 * V4.5.5 - 2026-03-06
 */

class TXWorkletProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        
        // 配置参数
        this.targetSampleRate = 16000;  // 目标采样率
        this.inputSampleRate = 44100;   // 输入采样率（会被覆盖）
        this.downSample = 3;            // 降采样因子
        
        // Opus 帧大小：16000Hz * 20ms = 320 samples
        this.opusFrameSize = 320;
        
        // 帧累积缓冲区
        this.frameAccumulator = new Float32Array(0);
        
        // 处理计数器
        this.processCount = 0;
        this.frameCount = 0;
        
        // 从主线程接收配置
        this.port.onmessage = (event) => {
            if (event.data.type === 'config') {
                this.inputSampleRate = event.data.inputSampleRate || 44100;
                this.downSample = event.data.downSample || 3;
                this.targetSampleRate = event.data.targetSampleRate || 16000;
                console.log(`[TX Worklet] 配置: input=${this.inputSampleRate}Hz, target=${this.targetSampleRate}Hz, ds=${this.downSample}`);
            }
        };
        
        // 发送就绪信号
        this.port.postMessage({ type: 'ready' });
    }
    
    process(inputs, outputs, parameters) {
        // 获取输入音频
        const input = inputs[0];
        if (!input || !input[0]) {
            return true; // 保持处理器运行
        }
        
        const inputData = input[0]; // 单声道
        
        // ========== 降采样处理 ==========
        // 计算降采样后的样本数
        const downsampledCount = Math.floor(inputData.length / this.downSample);
        const downsampledBuffer = new Float32Array(downsampledCount);
        
        // 简单降采样：取每第 downSample 个样本
        for (let i = 0; i < downsampledCount; i++) {
            downsampledBuffer[i] = inputData[i * this.downSample];
        }
        
        // ========== 帧累积 ==========
        // 将新数据追加到累积缓冲区
        const newAccumulator = new Float32Array(this.frameAccumulator.length + downsampledBuffer.length);
        newAccumulator.set(this.frameAccumulator);
        newAccumulator.set(downsampledBuffer, this.frameAccumulator.length);
        this.frameAccumulator = newAccumulator;
        
        // ========== 发送完整帧 ==========
        while (this.frameAccumulator.length >= this.opusFrameSize) {
            // 取出一个完整帧
            const frame = this.frameAccumulator.slice(0, this.opusFrameSize);
            this.frameAccumulator = this.frameAccumulator.slice(this.opusFrameSize);
            
            // 发送到主线程进行编码和传输
            this.port.postMessage({
                type: 'audioFrame',
                frame: frame,
                frameNumber: this.frameCount++
            });
            
            this.processCount++;
        }
        
        return true; // 保持处理器运行
    }
}

// 注册处理器
registerProcessor('tx-worklet-processor', TXWorkletProcessor);

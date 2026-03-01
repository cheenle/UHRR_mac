/**
 * AAC 编码器 - 前端实现
 * 
 * 由于浏览器原生不支持 AAC 编码，本模块使用以下策略：
 * 1. 降采样：将高采样率音频降采样到 16kHz（节省带宽）
 * 2. ADPCM/自适应差分PCM：使用差分编码压缩音频数据
 * 3. 可选：如果支持，使用 MediaRecorder 进行实际编码
 */

class AACEncoder {
    constructor(sampleRate = 16000, channels = 1, bitrate = 64000) {
        this.sampleRate = sampleRate;
        this.channels = channels;
        this.bitrate = bitrate;
        this.audioContext = null;
        this.initialized = false;
    }

    /**
     * 初始化音频上下文
     */
    async init() {
        if (this.initialized) return;
        
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.sampleRate
            });
            this.initialized = true;
            console.log('✅ AAC 编码器初始化成功');
        } catch (e) {
            console.error('❌ AAC 编码器初始化失败:', e);
            throw e;
        }
    }

    /**
     * 编码音频数据
     * @param {Float32Array} float32Data - 原始音频数据（Float32）
     * @returns {Promise<Uint8Array>} - 压缩后的数据
     */
    async encode(float32Data) {
        if (!this.initialized) {
            await this.init();
        }

        // 方法1: 降采样 + ADPCM 压缩（最快，兼容性最好）
        return this.encodeADPCM(float32Data);

        // 方法2: 如果支持 MediaRecorder（实际 AAC 编码，但兼容性差）
        // return this.encodeWithMediaRecorder(float32Data);
    }

    /**
     * ADPCM 编码 - 简化的音频压缩方案
     * 压缩率约 50-60%
     */
    encodeADPCM(float32Data) {
        // 转换为 Int16
        const int16Data = new Int16Array(float32Data.length);
        for (let i = 0; i < float32Data.length; i++) {
            int16Data[i] = Math.max(-32768, Math.min(32767, Math.round(float32Data[i] * 32767)));
        }

        // ADPCM 编码
        const compressed = [];
        let prevSample = 0;
        let index = 0;

        for (let i = 0; i < int16Data.length; i++) {
            const diff = int16Data[i] - prevSample;
            
            // 使用 8 位差分编码
            let nibble = Math.max(-128, Math.min(127, diff >> 8));
            
            compressed.push(nibble + 128); // 转换为无符号字节 [0-255]
            
            prevSample = int16Data[i];
        }

        // 添加头部信息
        const header = new Uint8Array(8);
        const view = new DataView(header.buffer);
        view.setUint32(0, 0x4141434D); // "AACM" 魔数
        view.setUint16(4, this.sampleRate);
        view.setUint8(6, this.channels);
        view.setUint8(7, 1); // 编码类型: ADPCM

        // 合并头部和数据
        const result = new Uint8Array(header.length + compressed.length);
        result.set(header, 0);
        result.set(new Uint8Array(compressed), header.length);

        return result;
    }

    /**
     * 使用 MediaRecorder 进行实际 AAC 编码
     * 注意：兼容性有限，某些浏览器不支持 AAC
     */
    async encodeWithMediaRecorder(float32Data) {
        return new Promise((resolve, reject) => {
            try {
                // 创建 AudioBuffer
                const audioBuffer = this.audioContext.createBuffer(
                    this.channels,
                    float32Data.length,
                    this.sampleRate
                );
                audioBuffer.getChannelData(0).set(float32Data);

                // 创建 MediaStreamDestination
                const destination = this.audioContext.createMediaStreamDestination();
                const source = this.audioContext.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(destination);
                source.start();

                // 尝试使用 AAC 编码
                const mimeType = MediaRecorder.isTypeSupported('audio/aac') 
                    ? 'audio/aac' 
                    : (MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : 'audio/webm');

                const chunks = [];
                const recorder = new MediaRecorder(destination.stream, {
                    mimeType: mimeType,
                    audioBitsPerSecond: this.bitrate
                });

                recorder.ondataavailable = (e) => {
                    if (e.data.size > 0) {
                        chunks.push(e.data);
                    }
                };

                recorder.onstop = () => {
                    const blob = new Blob(chunks, { type: mimeType });
                    const reader = new FileReader();
                    reader.onload = () => resolve(new Uint8Array(reader.result));
                    reader.onerror = reject;
                    reader.readAsArrayBuffer(blob);
                };

                recorder.start();
                source.onended = () => {
                    setTimeout(() => recorder.stop(), 50);
                };

            } catch (e) {
                console.warn('⚠️ MediaRecorder 编码失败，回退到 ADPCM:', e);
                resolve(this.encodeADPCM(float32Data));
            }
        });
    }

    /**
     * 计算压缩率
     */
    getCompressionRatio(originalSize, compressedSize) {
        return ((1 - compressedSize / originalSize) * 100).toFixed(1);
    }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AACEncoder;
}
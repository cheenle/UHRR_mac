/**
 * 本地语音识别模块 (ASR)
 * 支持 Web Speech API 和本地 ONNX 模型 (Whisper)
 */

class LocalASR {
    constructor(options = {}) {
        this.options = {
            modelPath: options.modelPath || 'models/whisper-tiny.onnx',
            vocabPath: options.vocabPath || 'models/vocab.json',
            language: options.language || 'zh',
            useWebSpeech: options.useWebSpeech !== false, // 默认启用Web Speech作为fallback
            ...options
        };
        
        this.session = null;
        this.vocab = null;
        this.isInitialized = false;
        this.isRecording = false;
        this.audioContext = null;
        this.mediaStream = null;
        this.processor = null;
        
        // 音频缓冲区
        this.audioBuffer = [];
        this.bufferSize = 0;
        this.sampleRate = 16000;
        this.chunkDuration = 30; // 秒
        
        // Web Speech API fallback
        this.webSpeechRecognition = null;
        
        // 回调函数
        this.onResult = options.onResult || (() => {});
        this.onError = options.onError || (() => {});
        this.onStatusChange = options.onStatusChange || (() => {});
    }
    
    /**
     * 初始化ASR
     */
    async initialize() {
        try {
            this.updateStatus('initializing');
            
            // 首先尝试加载本地ONNX模型
            if (await this.loadONNXModel()) {
                console.log('[LocalASR] ONNX模型加载成功');
                this.isInitialized = true;
                this.updateStatus('ready');
                return true;
            }
        } catch (e) {
            console.warn('[LocalASR] ONNX模型加载失败:', e);
        }
        
        // 如果ONNX失败且允许使用Web Speech，则初始化Web Speech
        if (this.options.useWebSpeech) {
            console.log('[LocalASR] 使用Web Speech API作为fallback');
            return this.initializeWebSpeech();
        }
        
        this.updateStatus('error');
        return false;
    }
    
    /**
     * 加载ONNX模型
     */
    async loadONNXModel() {
        // 检查ONNX Runtime是否可用
        if (typeof ort === 'undefined') {
            console.log('[LocalASR] ONNX Runtime未加载，尝试动态加载...');
            await this.loadScript('https://cdn.jsdelivr.net/npm/onnxruntime-web@1.16.3/dist/ort.min.js');
        }
        
        try {
            // 创建ONNX会话
            this.session = await ort.InferenceSession.create(this.options.modelPath);
            
            // 加载词汇表
            const vocabResponse = await fetch(this.options.vocabPath);
            this.vocab = await vocabResponse.json();
            
            return true;
        } catch (e) {
            console.error('[LocalASR] 加载ONNX模型失败:', e);
            return false;
        }
    }
    
    /**
     * 初始化Web Speech API
     */
    initializeWebSpeech() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        
        if (!SpeechRecognition) {
            this.updateStatus('error');
            throw new Error('浏览器不支持语音识别');
        }
        
        this.webSpeechRecognition = new SpeechRecognition();
        this.webSpeechRecognition.continuous = true;
        this.webSpeechRecognition.interimResults = true;
        this.webSpeechRecognition.lang = this.getLanguageCode();
        
        this.webSpeechRecognition.onstart = () => {
            this.isRecording = true;
            this.updateStatus('recording');
        };
        
        this.webSpeechRecognition.onresult = (event) => {
            let finalTranscript = '';
            let interimTranscript = '';
            
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript;
                } else {
                    interimTranscript += transcript;
                }
            }
            
            this.onResult({
                final: finalTranscript,
                interim: interimTranscript,
                confidence: event.results[0]?.[0]?.confidence || 0,
                isFinal: finalTranscript.length > 0
            });
        };
        
        this.webSpeechRecognition.onerror = (event) => {
            console.error('[LocalASR] Web Speech错误:', event.error);
            this.onError(event.error);
        };
        
        this.webSpeechRecognition.onend = () => {
            this.isRecording = false;
            this.updateStatus('ready');
            
            // 自动重启
            if (this.autoRestart) {
                setTimeout(() => this.start(), 100);
            }
        };
        
        this.isInitialized = true;
        this.updateStatus('ready');
        return true;
    }
    
    /**
     * 使用ONNX模型进行语音识别（高级功能）
     */
    async recognizeWithONNX(audioData) {
        if (!this.session) return null;
        
        try {
            // 预处理音频数据
            const processedAudio = this.preprocessAudio(audioData);
            
            // 创建输入张量
            const inputTensor = new ort.Tensor('float32', processedAudio, [1, processedAudio.length]);
            
            // 运行推理
            const results = await this.session.run({ input: inputTensor });
            
            // 解码结果
            const tokens = results.output.data;
            const text = this.decodeTokens(tokens);
            
            return {
                final: text,
                interim: '',
                confidence: 0.9,
                isFinal: true
            };
        } catch (e) {
            console.error('[LocalASR] ONNX推理失败:', e);
            return null;
        }
    }
    
    /**
     * 预处理音频数据
     */
    preprocessAudio(audioData) {
        // 转换为Float32Array
        const floatData = new Float32Array(audioData.length);
        for (let i = 0; i < audioData.length; i++) {
            floatData[i] = audioData[i] / 32768.0; // 归一化到[-1, 1]
        }
        
        // 重采样到16kHz（如果需要）
        // TODO: 实现重采样
        
        // 应用预加重滤波器
        const preemphasis = 0.97;
        for (let i = floatData.length - 1; i > 0; i--) {
            floatData[i] -= preemphasis * floatData[i - 1];
        }
        
        return floatData;
    }
    
    /**
     * 解码token为文本
     */
    decodeTokens(tokens) {
        if (!this.vocab) return '';
        
        let text = '';
        for (const token of tokens) {
            if (this.vocab[token]) {
                text += this.vocab[token];
            }
        }
        return text;
    }
    
    /**
     * 开始录音和识别
     */
    async start() {
        if (!this.isInitialized) {
            await this.initialize();
        }
        
        this.autoRestart = true;
        
        // 如果使用Web Speech
        if (this.webSpeechRecognition) {
            try {
                this.webSpeechRecognition.start();
            } catch (e) {
                // 可能已经在运行
                console.log('[LocalASR] Web Speech已在运行');
            }
            return;
        }
        
        // 使用ONNX模型录音
        await this.startRecording();
    }
    
    /**
     * 停止录音
     */
    stop() {
        this.autoRestart = false;
        
        if (this.webSpeechRecognition) {
            this.webSpeechRecognition.stop();
        }
        
        this.stopRecording();
    }
    
    /**
     * 开始音频录制（用于ONNX模型）
     */
    async startRecording() {
        try {
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });
            
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 16000
            });
            
            const source = this.audioContext.createMediaStreamSource(this.mediaStream);
            
            // 创建脚本处理器
            this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
            
            this.processor.onaudioprocess = (e) => {
                const inputData = e.inputBuffer.getChannelData(0);
                
                // 转换为Int16Array并存储
                const intData = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    intData[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
                }
                
                this.audioBuffer.push(...intData);
                this.bufferSize += intData.length;
                
                // 当缓冲区足够大时进行识别
                if (this.bufferSize >= this.sampleRate * this.chunkDuration) {
                    this.processAudioChunk();
                }
            };
            
            source.connect(this.processor);
            this.processor.connect(this.audioContext.destination);
            
            this.isRecording = true;
            this.updateStatus('recording');
            
        } catch (e) {
            console.error('[LocalASR] 录音启动失败:', e);
            this.onError(e.message);
        }
    }
    
    /**
     * 停止音频录制
     */
    stopRecording() {
        this.isRecording = false;
        
        if (this.processor) {
            this.processor.disconnect();
            this.processor = null;
        }
        
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }
        
        this.updateStatus('ready');
    }
    
    /**
     * 处理音频块
     */
    async processAudioChunk() {
        const audioData = new Int16Array(this.audioBuffer);
        this.audioBuffer = [];
        this.bufferSize = 0;
        
        const result = await this.recognizeWithONNX(audioData);
        if (result) {
            this.onResult(result);
        }
    }
    
    /**
     * 更新状态
     */
    updateStatus(status) {
        this.onStatusChange(status);
    }
    
    /**
     * 获取语言代码
     */
    getLanguageCode() {
        const langMap = {
            'zh': 'zh-CN',
            'en': 'en-US',
            'ja': 'ja-JP',
            'ko': 'ko-KR',
            'fr': 'fr-FR',
            'de': 'de-DE'
        };
        return langMap[this.options.language] || 'zh-CN';
    }
    
    /**
     * 动态加载脚本
     */
    loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }
}

// ============================================
// 本地语音合成模块 (TTS)
// ============================================

class LocalTTS {
    constructor(options = {}) {
        this.options = {
            useWebSpeech: options.useWebSpeech !== false,
            rate: options.rate || 1.0,
            pitch: options.pitch || 1.0,
            volume: options.volume || 1.0,
            voice: options.voice || null,
            ...options
        };
        
        this.synthesis = window.speechSynthesis;
        this.voices = [];
        this.currentUtterance = null;
        this.isSpeaking = false;
        
        this.onStart = options.onStart || (() => {});
        this.onEnd = options.onEnd || (() => {});
        this.onError = options.onError || (() => {});
        
        this.initialize();
    }
    
    /**
     * 初始化TTS
     */
    initialize() {
        if (!this.synthesis) {
            console.error('[LocalTTS] 浏览器不支持语音合成');
            return;
        }
        
        // 加载可用语音
        const loadVoices = () => {
            this.voices = this.synthesis.getVoices();
            console.log(`[LocalTTS] 加载了 ${this.voices.length} 个语音`);
        };
        
        loadVoices();
        
        if (this.synthesis.onvoiceschanged !== undefined) {
            this.synthesis.onvoiceschanged = loadVoices;
        }
    }
    
    /**
     * 播放文本
     */
    speak(text) {
        if (!this.synthesis) {
            this.onError('语音合成不可用');
            return;
        }
        
        // 取消之前的播放
        this.stop();
        
        this.currentUtterance = new SpeechSynthesisUtterance(text);
        this.currentUtterance.rate = this.options.rate;
        this.currentUtterance.pitch = this.options.pitch;
        this.currentUtterance.volume = this.options.volume;
        this.currentUtterance.lang = 'zh-CN';
        
        // 设置语音
        if (this.options.voice && this.voices[this.options.voice]) {
            this.currentUtterance.voice = this.voices[this.options.voice];
        } else {
            // 自动选择中文语音
            const zhVoice = this.voices.find(v => v.lang.startsWith('zh'));
            if (zhVoice) {
                this.currentUtterance.voice = zhVoice;
            }
        }
        
        this.currentUtterance.onstart = () => {
            this.isSpeaking = true;
            this.onStart();
        };
        
        this.currentUtterance.onend = () => {
            this.isSpeaking = false;
            this.onEnd();
        };
        
        this.currentUtterance.onerror = (e) => {
            this.isSpeaking = false;
            this.onError(e.error);
        };
        
        this.synthesis.speak(this.currentUtterance);
    }
    
    /**
     * 停止播放
     */
    stop() {
        if (this.synthesis) {
            this.synthesis.cancel();
        }
        this.isSpeaking = false;
    }
    
    /**
     * 暂停播放
     */
    pause() {
        if (this.synthesis) {
            this.synthesis.pause();
        }
    }
    
    /**
     * 恢复播放
     */
    resume() {
        if (this.synthesis) {
            this.synthesis.resume();
        }
    }
    
    /**
     * 获取可用语音列表
     */
    getVoices() {
        return this.voices;
    }
    
    /**
     * 设置语音
     */
    setVoice(voiceIndex) {
        if (this.voices[voiceIndex]) {
            this.options.voice = voiceIndex;
        }
    }
    
    /**
     * 设置语速
     */
    setRate(rate) {
        this.options.rate = Math.max(0.5, Math.min(2.0, rate));
    }
}

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { LocalASR, LocalTTS };
}
/**
 * SDR Modern Interface - JavaScript控制逻辑
 * 基于MRRC后端能力的新一代移动端界面
 */

class SDRModern {
    constructor() {
        // WebSocket连接
        this.ws = null;
        this.wsAudioTX = null;
        this.wsAudioRX = null;
        this.wsConnected = false;
        
        // 音频相关
        this.audioContext = null;
        this.audioInitialized = false;
        this.micStream = null;
        this.micSource = null;
        this.gainNode = null;
        
        // 状态
        this.currentVFO = 'A';
        this.currentFreq = 14074000;
        
        // 模式列表
        this.modeList = ['LSB', 'USB', 'CW', 'FM', 'AM'];
        this.currentModeIndex = 1; // 默认USB
        this.currentMode = 'USB';
        this.isTX = false;
        this.pttLastActionTime = 0;
        this.PTT_DEBOUNCE_TIME = 100; // 100ms防抖
        this.pttStartTime = 0; // PTT启动时间
        this.pttPressed = false; // 用户是否按住PTT按钮
        this.lastAudioSendTime = 0; // 上次音频发送时间
        this.isRecording = false;
        
        // ATR-1000 功率/SWR
        this.atr1000 = {
            ws: null,
            isConnected: false,
            lastPower: 0,
            lastSWR: 1.0,
            _txActive: false
        };
        this.sMeterValue = 0;
        this.powerValue = 0;
        this.swrValue = 1.0;
        
        // S表校准参数（默认初始值）
        this.sMeterCalibration = {
            baseNoiseDB: -60,      // 无信号噪音电平 (dBFS) -> S0
            baseNoiseS: 0,         // S0 (无信号)
            strongSignalDB: -30,   // 强信号电平 (dBFS) -> S9+20
            strongSignalS: 11.67   // S9+20 = 9 + 20/6 = 11.67
        };
        
        // 设置
        this.settings = {
            micGain: 150,
            speakerVolume: 80,
            eqLow: 0,
            eqMid: 0,
            eqHigh: 0
        };
        
        // WDSP 状态（与后端配置一致）
        this.wdspState = {
            enabled: true,      // 主开关
            nr2Level: 1,        // NR2级别 (0=关, 1=极, 2=低, 3=中, 4=高)
            nb: true,           // 噪声抑制
            anf: false,         // 自动陷波
            agcMode: 3          // AGC模式 (0=关, 1=长, 2=慢, 3=中, 4=快)
        };
        
        // 常量定义
        this.NR2_LEVEL_NAMES = ['关', '极', '低', '中', '高'];
        this.AGC_MODE_NAMES = ['关', '长', '慢', '中', '快'];
        
        // 调谐步进
        this.tuneSteps = [0.1, 1, 5, 50]; // 100Hz, 1kHz, 5kHz, 50kHz
        this.tuneStepIndex = 1; // 默认1kHz
        
        // 波段数据（数组形式，支持切换）
        this.bandList = [
            { name: '80m', range: [3500000, 4000000], freq: 3750000 },
            { name: '60m', range: [5351000, 5366000], freq: 5357000 },
            { name: '40m', range: [7000000, 7300000], freq: 7050000 },
            { name: '30m', range: [10100000, 10150000], freq: 10120000 },
            { name: '20m', range: [14000000, 14350000], freq: 14200000 },
            { name: '17m', range: [18068000, 18168000], freq: 18100000 },
            { name: '15m', range: [21000000, 21450000], freq: 21200000 },
            { name: '12m', range: [24890000, 24990000], freq: 24900000 },
            { name: '10m', range: [28000000, 29700000], freq: 28500000 }
        ];
        this.currentBandIndex = 4; // 默认20m
        
        // 兼容旧代码的波段数据
        this.bands = {
            '160': [1800000, 2000000],
            '80': [3500000, 4000000],
            '60': [5351000, 5366000],
            '40': [7000000, 7300000],
            '30': [10100000, 10150000],
            '20': [14000000, 14350000],
            '17': [18068000, 18168000],
            '15': [21000000, 21450000],
            '12': [24890000, 24990000],
            '10': [28000000, 29700000],
            '6': [50000000, 54000000],
            '2': [144000000, 148000000],
            '70': [430000000, 440000000]
        };
        
        // PTT宏
        this.macros = {
            'CQ': 'CQ CQ CQ DE [CALL] [CALL] K',
            'QRZ': 'QRZ? DE [CALL]',
            'TEST': 'TEST TEST DE [CALL]',
            'TNX': 'TNX 73',
            '73': '73 DE [CALL] SK',
            'RST599': '599 599'
        };
        
        this.init();
    }
    
    init() {
        // 自动连接 WebSocket 和音频 (模拟点击电源按钮的效果)
        console.log('🔌 自动连接 WebSocket 和音频...');
        
        // 设置 poweron 为 true
        window.poweron = true;
        
        // 调用 controls.js 的连接函数
        if (typeof ControlTRX_start === 'function') {
            ControlTRX_start();
            console.log('✅ ControlTRX_start 调用完成');
        }
        
        if (typeof AudioRX_start === 'function') {
            AudioRX_start();
            console.log('✅ AudioRX_start 调用完成');
        }
        
        if (typeof AudioTX_start === 'function') {
            AudioTX_start();
            console.log('✅ AudioTX_start 调用完成');
        }
        
        if (typeof checklatency === 'function') {
            checklatency();
        }
        
        // 等待 wsControlTRX 连接成功后发送初始命令
        const waitForWSAndInit = () => {
            if (typeof wsControlTRX !== 'undefined' && wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
                // 发送初始命令
                this.sendCommand('getFreq:');
                this.sendCommand('getMode:');
                this.sendCommand('getWDSPStatus:');
            } else {
                // 等待一下再重试
                setTimeout(waitForWSAndInit, 100);
            }
        };
        
        // 延迟一点等待 controls.js 初始化
        setTimeout(waitForWSAndInit, 1000);
        
        // 初始化音频 RX (使用 controls.js 的 toggleaudioRX)
        this.initAudioRX();
        this.initOpusDecoder();
        this.bindEvents();
        this.loadSettings();
        // 加载 WDSP 状态
        this.loadWDSPState();
        // 初始化步进显示
        const step = this.getTuneStep();
        document.getElementById('tune-step').textContent = step < 1 ? `${step * 1000}Hz` : `${step}kHz`;
        // 初始化波段显示
        this.updateBandDisplay();
        // 初始化模式显示
        this.updateModeDisplayElement();
        // 初始化 WDSP 按钮
        this.updateWDSPButtonsState();
        
        // 预连接ATR-1000（功率/SWR显示）
        this.connectATR1000();
        
        // 初始化音量和麦克风滑块
        const volSlider = document.getElementById('vol-slider');
        const volValue = document.getElementById('vol-value');
        if (volSlider && volValue) {
            volSlider.value = this.settings.speakerVolume;
            volValue.textContent = this.settings.speakerVolume;
        }
        
        const micSlider = document.getElementById('mic-slider');
        const micValue = document.getElementById('mic-value');
        if (micSlider && micValue) {
            micSlider.value = 150;
            micValue.textContent = 150;
        }
    }
    
    // 初始化RX音频（接收音频播放）- 使用 controls.js 定义的 wsAudioRX
    initAudioRX() {
        // 等待 wsAudioRX 连接成功后设置消息处理
        const waitForWSAndInit = () => {
            if (typeof wsAudioRX !== 'undefined' && wsAudioRX && wsAudioRX.readyState === WebSocket.OPEN) {
                console.log('🔊 使用 controls.js 的 wsAudioRX');
                
                // 覆盖 onmessage 处理
                wsAudioRX.onmessage = (event) => {
                    this.handleAudioRX(event.data);
                };
            } else {
                // 等待一下再重试
                setTimeout(waitForWSAndInit, 100);
            }
        };
        
        // 延迟一点等待 controls.js 初始化
        setTimeout(waitForWSAndInit, 500);
    }
    
    // 处理接收到的音频数据
    handleAudioRX(data) {
        if (!this.audioContext) {
            this.initAudioContext();
        }
        
        try {
            // 后端默认发送Int16，禁用Opus解码
            // 如需启用Opus，需在后端设置 rx_opus_encode=True
            const int16Data = new Int16Array(data);
            const float32Data = new Float32Array(int16Data.length);
            const scale = 1.0 / 32767.0;
            for (let i = 0; i < int16Data.length; i++) {
                float32Data[i] = int16Data[i] * scale;
            }
            
            // 计算信号强度（用于S表）
            this.calculateSignalStrength(float32Data);
            
            // 播放音频
            this.playBuffer(float32Data);
        } catch (e) {
            console.error('音频解码错误:', e);
        }
    }
    
    // 初始化Opus解码器
    initOpusDecoder() {
        try {
            // 使用controls.js中定义的OpusDecoder
            if (typeof OpusDecoder !== 'undefined') {
                const opusRate = 16000; // 与后端编码采样率一致
                this.opusDecoder = new OpusDecoder(opusRate, 1);
                console.log('✅ Opus解码器已初始化 (' + opusRate + 'Hz)');
            } else {
                console.warn('⚠️ OpusDecoder未定义，请确保controls.js已加载');
            }
        } catch (e) {
            console.error('❌ Opus解码器初始化失败:', e);
        }
    }
    
    // 初始化AudioContext
    initAudioContext() {
        if (this.audioContext) return;
        
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                latencyHint: "playback", // 改为playback以获得更稳定的播放
                sampleRate: 16000 // 与后端编码采样率一致
            });
            
            // 创建增益节点
            this.gainNode = this.audioContext.createGain();
            this.gainNode.gain.value = this.settings.speakerVolume / 100;
            this.gainNode.connect(this.audioContext.destination);
            
            // 启动S表监测
            this.startSMeterMonitoring();
            
            // 设置 AudioWorklet
            this.setupAudioWorklet();
            
            console.log('🔊 AudioContext已创建, 采样率:', this.audioContext.sampleRate);
            
            // 恢复suspended状态
            if (this.audioContext.state === 'suspended') {
                this.audioContext.resume();
            }
        } catch (e) {
            console.error('AudioContext初始化失败:', e);
        }
    }
    
    // 设置AudioWorklet播放器
    async setupAudioWorklet() {
        try {
            await this.audioContext.audioWorklet.addModule('rx_worklet_processor.js');
            this.rxPlayer = new AudioWorkletNode(this.audioContext, 'rx-player');
            this.rxPlayer.connect(this.gainNode);
            
            // 发送缓冲区配置
            this.rxPlayer.port.postMessage({
                type: 'config',
                min: 10,
                max: 60
            });
            
            console.log('✅ AudioWorklet播放器已设置 (min=10, max=60)');
        } catch (e) {
            console.warn('⚠️ AudioWorklet失败，将使用BufferSource:', e);
            this.rxPlayer = null;
        }
    }

    // 启动S表监测
    startSMeterMonitoring() {
        if (this.sMeterInterval) return;
        
        // S表校准参数 - 基于两个参考点
        // 参考点1：无信号状态 = S0 (基础噪音)
        // 参考点2：强信号 = S9+20
        this.sMeterCalibration = {
            baseNoiseDB: -60,      // 无信号噪音电平 (dBFS) -> S0
            baseNoiseS: 0,         // S0 (无信号)
            strongSignalDB: -30,   // 强信号电平 (dBFS) -> S9+20
            strongSignalS: 11.67   // S9+20 = 9 + 20/6 = 11.67
        };
        
        this.sMeterInterval = setInterval(() => {
            this.updateSMeterFromAudio();
        }, 100); // 每100ms更新一次，更灵敏
        
        console.log('📊 S表监测已启动 (无信号S0, 强信号S9+20)');
    }
    
    // 基于音频信号计算S表值
    updateSMeterFromAudio() {
        // 检查是否有新的音频数据
        const now = Date.now();
        const timeSinceLastAudio = now - (this.lastAudioTime || 0);

        let sValue;

        if (timeSinceLastAudio > 500 || this.currentAudioDB === undefined) {
            // 超过500ms没有新音频，衰减到无信号水平（S0）
            sValue = this.sMeterCalibration.baseNoiseS;
        } else {
            // 使用从音频数据计算出的dB值
            const dbFS = this.currentAudioDB;
            const cal = this.sMeterCalibration;

            // 基于两个参考点进行线性插值计算S值
            if (dbFS <= cal.baseNoiseDB) {
                // 低于基础噪音，按每6dB一个S单位计算
                const dbBelowBase = cal.baseNoiseDB - dbFS;
                sValue = cal.baseNoiseS - (dbBelowBase / 6);
            } else if (dbFS >= cal.strongSignalDB) {
                // 高于强信号参考点
                const dbAboveStrong = dbFS - cal.strongSignalDB;
                sValue = cal.strongSignalS + (dbAboveStrong / 6);
            } else {
                // 在两个参考点之间进行线性插值
                const dbRange = cal.strongSignalDB - cal.baseNoiseDB;
                const sRange = cal.strongSignalS - cal.baseNoiseS;
                const ratio = (dbFS - cal.baseNoiseDB) / dbRange;
                sValue = cal.baseNoiseS + (sRange * ratio);
            }

            // 限制范围 S0 - S9+60 (15)
            if (sValue < 0) sValue = 0;
            if (sValue > 15) sValue = 15;
        }

        // 添加平滑处理
        this.currentSMeter = this.currentSMeter || sValue;
        this.currentSMeter = this.currentSMeter * 0.5 + sValue * 0.5;

        // 更新显示
        this.updateSMeterDisplay(this.currentSMeter);
    }
    
    // 更新S表显示
    updateSMeterDisplay(sValue) {
        const sMeterFill = document.getElementById('s-meter-fill');
        const sMeterText = document.getElementById('s-meter-text');
        if (!sMeterFill || !sMeterText) return;

        // 计算百分比 (S0-S9对应0-50%, S9+10到S9+60对应50-100%)
        let percentage;
        let displayText;

        if (sValue < 9) {
            percentage = (sValue / 9) * 50;
            displayText = `S${Math.round(sValue)}`;
        } else {
            const overS9 = (sValue - 9) * 6;
            percentage = 50 + Math.min(overS9 / 60 * 50, 50);
            if (overS9 <= 0) {
                displayText = 'S9';
            } else if (overS9 >= 60) {
                displayText = 'S9+60';
            } else {
                displayText = `S9+${Math.round(overS9)}`;
            }
        }

        // 更新条形显示
        sMeterFill.style.width = `${percentage}%`;

        // 更新数字显示
        sMeterText.textContent = displayText;

        // 根据信号强度改变颜色
        let color;
        if (sValue < 3) {
            color = '#4CAF50'; // 绿色 - 弱信号
        } else if (sValue < 7) {
            color = '#FFC107'; // 黄色 - 中等
        } else if (sValue < 9) {
            color = '#FF9800'; // 橙色 - 强信号
        } else {
            color = '#f44336'; // 红色 - 很强
        }
        sMeterFill.style.background = color;
        sMeterText.style.color = color;
    }
    
    // 停止S表监测
    stopSMeterMonitoring() {
        if (this.sMeterInterval) {
            clearInterval(this.sMeterInterval);
            this.sMeterInterval = null;
        }
    }

    // 校准S表 - 设置无信号参考点（当前应为S0）
    calibrateBaseNoise() {
        if (this.currentAudioDB === undefined) {
            this.showToast('⚠️ 没有音频数据，无法校准', 'warning');
            return;
        }
        this.sMeterCalibration.baseNoiseDB = this.currentAudioDB;
        this.sMeterCalibration.baseNoiseS = 0; // S0
        this.saveSettings();
        const msg = `📊 S表无信号已校准: ${this.currentAudioDB.toFixed(1)} dBFS = S0`;
        console.log(msg);
        this.showToast(msg, 'success');
    }

    // 校准S表 - 设置强信号参考点（当前频率应为S9+20）
    calibrateStrongSignal() {
        if (this.currentAudioDB === undefined) {
            this.showToast('⚠️ 没有音频数据，无法校准', 'warning');
            return;
        }
        this.sMeterCalibration.strongSignalDB = this.currentAudioDB;
        this.saveSettings();
        const msg = `📊 S表强信号已校准: ${this.currentAudioDB.toFixed(1)} dBFS = S9+20`;
        console.log(msg);
        this.showToast(msg, 'success');
    }

    // 显示Toast提示
    showToast(message, type = 'info') {
        // 移除旧的toast
        const oldToast = document.querySelector('.toast-notification');
        if (oldToast) oldToast.remove();

        // 创建新toast
        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${type}`;
        toast.textContent = message;
        
        // 样式
        toast.style.cssText = `
            position: fixed;
            bottom: 100px;
            left: 50%;
            transform: translateX(-50%);
            background: ${type === 'success' ? 'var(--accent-secondary)' : type === 'warning' ? '#f0a030' : 'var(--accent-primary)'};
            color: var(--text-inverse);
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 13px;
            z-index: 9999;
            animation: fadeInOut 3s ease forwards;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        `;

        // 添加动画样式（如果不存在）
        if (!document.getElementById('toast-style')) {
            const style = document.createElement('style');
            style.id = 'toast-style';
            style.textContent = `
                @keyframes fadeInOut {
                    0% { opacity: 0; transform: translateX(-50%) translateY(20px); }
                    10% { opacity: 1; transform: translateX(-50%) translateY(0); }
                    90% { opacity: 1; transform: translateX(-50%) translateY(0); }
                    100% { opacity: 0; transform: translateX(-50%) translateY(-20px); }
                }
            `;
            document.head.appendChild(style);
        }

        document.body.appendChild(toast);
        
        // 3秒后自动移除
        setTimeout(() => toast.remove(), 3000);
    }

    // 获取当前S表读数（用于调试）
    getSMeterDebugInfo() {
        return {
            currentDB: this.currentAudioDB,
            currentS: this.currentSMeter,
            calibration: this.sMeterCalibration,
            timeSinceLastAudio: Date.now() - (this.lastAudioTime || 0)
        };
    }
    
    // 播放音频缓冲区（使用AudioWorklet）
    playBuffer(audioData) {
        if (!this.audioContext || !this.gainNode) return;
        
        try {
            // 计算信号强度用于S表显示
            this.calculateSignalStrength(audioData);
            
            // 如果有AudioWorklet，使用它播放
            if (this.rxPlayer) {
                this.rxPlayer.port.postMessage({
                    type: 'push',
                    payload: audioData
                });
                return;
            }
            
            // 回退到BufferSource
            const buffer = this.audioContext.createBuffer(1, audioData.length, 16000);
            buffer.getChannelData(0).set(audioData);
            
            const source = this.audioContext.createBufferSource();
            source.buffer = buffer;
            source.connect(this.gainNode);
            source.start(0);
        } catch (e) {
            console.error('音频播放错误:', e);
        }
    }
    
    // 计算信号强度（用于S表）
    calculateSignalStrength(audioData) {
        // 计算RMS值
        let sum = 0;
        for (let i = 0; i < audioData.length; i++) {
            sum += audioData[i] * audioData[i];
        }
        const rms = Math.sqrt(sum / audioData.length);

        // 更新RMS历史用于平滑
        if (!this.rmsHistory) this.rmsHistory = [];
        this.rmsHistory.push(rms);
        if (this.rmsHistory.length > 10) this.rmsHistory.shift();

        // 计算平均RMS
        const avgRMS = this.rmsHistory.reduce((a, b) => a + b, 0) / this.rmsHistory.length;

        // 转换为dBFS
        let dbFS = 20 * Math.log10(avgRMS);
        if (dbFS === -Infinity) dbFS = -100;

        // 存储当前dB值和时间戳
        this.currentAudioDB = dbFS;
        this.lastAudioTime = Date.now();
    }
    
    // 初始化TX音频（麦克风采集）
    async initAudioTX() {
        // 如果已有麦克风源，直接使用
        if (this.micSource) return;
        
        // 如果有micStream但没有micSource（之前断开过），重建连接
        if (this.micStream && this.audioContext) {
            this.micSource = this.audioContext.createMediaStreamSource(this.micStream);
            
            this.micGainNode = this.audioContext.createGain();
            this.micGainNode.gain.value = this.settings.micGain / 100;
            this.micSource.connect(this.micGainNode);
            
            const processor = this.audioContext.createScriptProcessor(1024, 1, 1);
            this.micGainNode.connect(processor);
            // 必须连接到destination，否则在iOS Safari上ScriptProcessorNode不会运行
            processor.connect(this.audioContext.destination);
            
            let audioFrameCount = 0;
            let silentFrameCount = 0;
            processor.onaudioprocess = (e) => {
                if (!this.isRecording || !this.wsAudioTX) return;
                
                const inputData = e.inputBuffer.getChannelData(0);
                
                // 检测是否为静音帧
                let isSilent = true;
                for (let i = 0; i < inputData.length; i++) {
                    if (Math.abs(inputData[i]) > 0.001) {
                        isSilent = false;
                        break;
                    }
                }
                if (isSilent) silentFrameCount++;
                else silentFrameCount = 0;
                
                const int16Data = new Int16Array(inputData.length);
                const gain = this.settings.micGain / 100;
                for (let i = 0; i < inputData.length; i++) {
                    let sample = inputData[i] * gain;
                    sample = Math.max(-1, Math.min(1, sample));
                    int16Data[i] = sample * 32767;
                }
                
                if (this.wsAudioTX && this.wsAudioTX.readyState === WebSocket.OPEN) {
                    this.wsAudioTX.send(int16Data.buffer);
                    this.lastAudioSendTime = Date.now();
                    audioFrameCount++;
                }
            };
            
            console.log('🎤 麦克风源已重建');
            return;
        }
        
        // 首次请求麦克风权限
        try {
            this.micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false
                },
                video: false
            });
            
            console.log('🎤 麦克风权限已获取');
            
            // 检查音频轨道状态
            const audioTrack = this.micStream.getAudioTracks()[0];
            if (audioTrack) {
                console.log('🎤 音频轨道状态:', audioTrack.readyState, '静音:', audioTrack.muted, '启用:', audioTrack.enabled);
                // 确保轨道是启用的
                audioTrack.enabled = true;
            }
            
            // 创建AudioContext（如果还没有）
            if (!this.audioContext) {
                this.initAudioContext();
            }
            
            // 创建麦克风源
            this.micSource = this.audioContext.createMediaStreamSource(this.micStream);
            
            // 创建处理节点
            const processor = this.audioContext.createScriptProcessor(1024, 1, 1);
            
            // 设置麦克风增益
            this.micGainNode = this.audioContext.createGain();
            this.micGainNode.gain.value = this.settings.micGain / 100;
            this.micSource.connect(this.micGainNode);
            this.micGainNode.connect(processor);
            
            // 必须连接到destination，否则在iOS Safari上ScriptProcessorNode不会运行
            processor.connect(this.audioContext.destination);
            
            // 处理音频数据
            let audioFrameCount = 0;
            let silentFrameCount = 0;
            processor.onaudioprocess = (e) => {
                // 详细诊断
                if (audioFrameCount % 50 === 0) {
                    console.log('🎤 音频帧诊断: isRecording=', this.isRecording, 
                        'wsAudioTX=', this.wsAudioTX ? `存在(${this.wsAudioTX.readyState})` : 'null',
                        'micStream=', this.micStream ? '有' : '无');
                }
                
                if (!this.isRecording || !this.wsAudioTX || this.wsAudioTX.readyState !== WebSocket.OPEN) {
                    if (audioFrameCount > 0 && audioFrameCount % 100 === 0) {
                        console.log('🎤 音频处理跳过: isRecording=', this.isRecording, 
                            'wsAudioTX=', this.wsAudioTX ? `state=${this.wsAudioTX.readyState}` : 'null');
                    }
                    return;
                }
                
                const inputData = e.inputBuffer.getChannelData(0);
                
                // 检测是否为静音帧（全0或接近0）
                let isSilent = true;
                let maxSample = 0;
                for (let i = 0; i < inputData.length; i++) {
                    const absSample = Math.abs(inputData[i]);
                    if (absSample > 0.001) {
                        isSilent = false;
                    }
                    maxSample = Math.max(maxSample, absSample);
                }
                
                if (isSilent) {
                    silentFrameCount++;
                    if (silentFrameCount % 50 === 0) {
                        console.log('🎤 检测到静音帧:', silentFrameCount, 'maxSample:', maxSample.toFixed(4));
                    }
                } else {
                    silentFrameCount = 0;
                    if (audioFrameCount % 50 === 0) {
                        console.log('🎤 检测到音频帧:', audioFrameCount, 'maxSample:', maxSample.toFixed(4));
                    }
                }
                
                const int16Data = new Int16Array(inputData.length);
                const gain = this.settings.micGain / 100;
                
                // 转换为Int16
                for (let i = 0; i < inputData.length; i++) {
                    // 移除样本限制，允许增益超过100%
                    let sample = inputData[i] * gain;
                    sample = Math.max(-1, Math.min(1, sample));
                    int16Data[i] = sample * 32767;
                }
                
                // 发送到服务器
                if (this.wsAudioTX && this.wsAudioTX.readyState === WebSocket.OPEN) {
                    this.wsAudioTX.send(int16Data.buffer);
                    audioFrameCount++;
                    if (audioFrameCount % 50 === 0) {
                        console.log('🎤 已发送音频帧:', audioFrameCount, '大小:', int16Data.buffer.byteLength, '静音帧:', silentFrameCount);
                    }
                    // 记录最后发送时间
                    this.lastAudioSendTime = Date.now();
                } else {
                    console.log('⚠️ WebSocket未连接，无法发送音频');
                }
            };
            
            // 诊断定时器：检查音频是否持续发送
            this.audioDiagnosisInterval = setInterval(() => {
                if (this.isRecording) {
                    const timeSinceLastSend = Date.now() - (this.lastAudioSendTime || 0);
                    const trackStatus = this.micStream && this.micStream.getAudioTracks()[0] ? 
                        `轨道状态:${this.micStream.getAudioTracks()[0].readyState} 静音:${this.micStream.getAudioTracks()[0].muted}` : 
                        '无轨道';
                    console.log('🎤 音频诊断:', trackStatus, '帧数:', audioFrameCount, '上次发送:', timeSinceLastSend, 'ms前', 'isRecording:', this.isRecording);
                    
                    if (timeSinceLastSend > 500) {
                        console.warn('⚠️ 音频发送可能中断！');
                    }
                }
            }, 200);
            
            console.log('🎤 TX音频已就绪');
            
        } catch (e) {
            console.error('🎤 麦克风初始化失败:', e);
            alert('无法获取麦克风权限，请允许访问');
        }
    }
    
    // 连接TX音频WebSocket（返回Promise等待连接成功）
    connectAudioTX() {
        return new Promise((resolve, reject) => {
            // 如果已经连接，直接resolve
            if (this.wsAudioTX && this.wsAudioTX.readyState === WebSocket.OPEN) {
                console.log('🎤 TX音频连接已存在');
                resolve();
                return;
            }
            
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host || 'localhost:8877';
            
            try {
                // 先关闭旧连接（如果存在）
                if (this.wsAudioTX) {
                    this.wsAudioTX.close();
                    this.wsAudioTX = null;
                }
                
                this.wsAudioTX = new WebSocket(`${protocol}//${host}/WSaudioTX`);
                
                // 设置连接超时
                const connectionTimeout = setTimeout(() => {
                    console.error('🎤 TX音频连接超时');
                    reject(new Error('连接超时'));
                }, 5000);
                
                this.wsAudioTX.onopen = () => {
                    clearTimeout(connectionTimeout);
                    console.log('🎤 TX音频连接已建立');
                    this.updateAudioStatus('tx', true);
                    // 发送采样率配置: 输入采样率,是否编码(0=PCM),Opus采样率,帧时长
                    const sampleRate = this.audioContext.sampleRate;
                    const config = `m:${sampleRate},0,16000,20`;
                    console.log('📡 发送音频配置:', config);
                    this.wsAudioTX.send(config);
                    resolve();
                };
                
                this.wsAudioTX.onclose = () => {
                    console.log('🎤 TX音频连接已关闭');
                    this.updateAudioStatus('tx', false);
                    this.wsAudioTX = null;
                };
                
                this.wsAudioTX.onerror = (error) => {
                    clearTimeout(connectionTimeout);
                    console.error('🎤 TX音频错误:', error);
                    reject(error);
                };
                
            } catch (e) {
                clearTimeout(connectionTimeout || null);
                console.error('🎤 TX音频连接失败:', e);
                reject(e);
            }
        });
    }
    
    // 断开TX音频（只断开连接，不停止麦克风，避免重复授权）
    disconnectAudioTX() {
        if (this.wsAudioTX) {
            this.wsAudioTX.close();
            this.wsAudioTX = null;
        }
        // 只断开音频节点连接，不停止麦克风（保留授权）
        if (this.micSource) {
            this.micSource.disconnect();
            this.micSource = null;
        }
        if (this.micGainNode) {
            this.micGainNode.disconnect();
            this.micGainNode = null;
        }
    }
    
    // 更新音频状态显示
    updateAudioStatus(type, connected) {
        const elId = type === 'tx' ? 'audio-tx-status' : 'audio-rx-status';
        const el = document.getElementById(elId);
        if (el) {
            if (connected) {
                el.classList.add('connected');
            } else {
                el.classList.remove('connected');
            }
        }
        console.log(`音频状态 [${type}]:`, connected ? '已连接' : '已断开');
    }
    
    // 初始化WebSocket连接
    initWebSocket() {
        // 使用 controls.js 定义的 wsControlTRX，不需要自己创建 WebSocket
        // 等待 wsControlTRX 连接成功后设置消息处理
        let retryCount = 0;
        const maxRetries = 30; // 最多等3秒
        
        const waitForWSAndInit = () => {
            retryCount++;
            
            if (typeof wsControlTRX === 'undefined') {
                console.log(`⏳ 等待 wsControlTRX 定义... (${retryCount}/${maxRetries})`);
            } else if (!wsControlTRX) {
                console.log(`⏳ wsControlTRX 未创建... (${retryCount}/${maxRetries})`);
            } else if (wsControlTRX.readyState === WebSocket.CONNECTING) {
                console.log(`⏳ wsControlTRX 正在连接... (${retryCount}/${maxRetries})`);
            } else if (wsControlTRX.readyState === WebSocket.OPEN) {
                console.log('✅ 使用 controls.js 的 wsControlTRX');
                
                // 覆盖 onmessage 处理
                wsControlTRX.onmessage = (event) => {
                    this.handleMessage(event.data);
                };
                
                // 连接成功时更新状态
                this.wsConnected = true;
                this.updateConnectionStatus(true);
                
                // 发送初始命令
                this.sendCommand('getFreq:');
                this.sendCommand('getMode:');
                this.sendCommand('getWDSPStatus:');
                return; // 成功就退出
            } else if (wsControlTRX.readyState === WebSocket.CLOSED) {
                console.log(`❌ wsControlTRX 已关闭，状态码: ${wsControlTRX.readyState} (${retryCount}/${maxRetries})`);
            } else {
                console.log(`⏳ wsControlTRX 状态: ${wsControlTRX.readyState} (${retryCount}/${maxRetries})`);
            }
            
            // 继续等待或超时
            if (retryCount < maxRetries) {
                setTimeout(waitForWSAndInit, 100);
            } else {
                console.error('❌ 等待 wsControlTRX 超时');
            }
        };
        
        // 延迟一点等待 controls.js 初始化
        setTimeout(waitForWSAndInit, 500);
    }
    
    // 发送命令 - 使用 controls.js 定义的 wsControlTRX
    sendCommand(action, data = '') {
        if (typeof wsControlTRX !== 'undefined' && wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
            const message = data ? `${action}${data}` : action;
            console.log(`📤 发送命令: ${message}`);
            wsControlTRX.send(message + '\n');
        } else {
            console.warn(`⚠️ 无法发送命令 ${action}: WebSocket状态=${wsControlTRX?.readyState}`);
        }
    }
    
    // 处理接收到的消息
    handleMessage(message) {
        const lines = message.split('\n');
        
        lines.forEach(line => {
            if (!line.trim()) return;
            
            // 频率更新
            if (line.startsWith('getFreq:')) {
                const freq = parseInt(line.replace('getFreq:', ''));
                if (freq > 0) {
                    this.currentFreq = freq;
                    this.updateFreqDisplay();
                }
            }
            // 模式更新
            else if (line.startsWith('getMode:')) {
                const mode = line.replace('getMode:', '').trim();
                if (mode) {
                    this.currentMode = mode;
                    this.updateModeDisplay();
                }
            }
            // S表数据
            else if (line.startsWith('SMETER:')) {
                const value = parseInt(line.replace('SMETER:', ''));
                this.sMeterValue = value;
                this.updateSMeter(value);
            }
            // PTT状态（后端反馈）
            else if (line.startsWith('PTT:') || line.startsWith('setPTT:')) {
                const ptt = line.replace('PTT:', '').replace('setPTT:', '').trim();
                const backendTX = ptt === 'ON' || ptt === '1' || ptt === 'true';
                
                // 如果用户主动按住PTT，但后端说PTT=OFF，可能是后端的自动保护
                // 此时保持前端状态，等待用户释放按钮
                if (this.isTX && !backendTX && this.pttPressed) {
                    console.log('📡 后端PTT=OFF，但用户仍按住PTT，保持发射状态');
                    // 重新发送PTT ON命令
                    this.sendCommand('setPTT:', 'true');
                } else {
                    this.isTX = backendTX;
                    this.updatePTTStatus(this.isTX);
                    console.log('📡 PTT状态更新:', this.isTX ? 'ON' : 'OFF');
                }
            }
            // 录音列表
            else if (line.startsWith('RECORDINGS:')) {
                const recordings = line.replace('RECORDINGS:', '');
                this.updateRecordingsList(recordings);
            }
            // WDSP 状态
            else if (line.startsWith('WDSPStatus:')) {
                const status = line.replace('WDSPStatus:', '');
                this.handleWDSPStatus(status);
            }
            // WDSP 状态（JSON格式）
            else if (line.startsWith('{"enabled"') || line.startsWith('{\"enabled\"')) {
                // 尝试解析为 WDSP 状态
                try {
                    const data = JSON.parse(line);
                    if (data.enabled !== undefined) {
                        this.handleWDSPStatus(line);
                    }
                } catch (e) {
                    // 不是 WDSP 状态，忽略
                }
            }
        });
    }
    
    // 更新连接状态
    updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connection-status');
        const textEl = statusEl.querySelector('.status-text');
        
        if (connected) {
            statusEl.classList.remove('disconnected');
            statusEl.classList.add('connected');
            textEl.textContent = '已连接';
        } else {
            statusEl.classList.remove('connected');
            statusEl.classList.add('disconnected');
            textEl.textContent = '未连接';
        }
    }
    
    // 更新频率显示
    updateFreqDisplay() {
        const freq = this.currentFreq;
        // 显示格式：14.074.000 (MHz部分 + kHz部分 + Hz部分)
        const mhz = Math.floor(freq / 1000000);
        const khz = Math.floor((freq % 1000000) / 1000);
        const hz = freq % 1000;
        const freqStr = `${mhz}.${String(khz).padStart(3, '0')}.${String(hz).padStart(3, '0')}`;
        
        const freqEl = document.getElementById('vfo-freq');
        if (freqEl) freqEl.textContent = freqStr;
    }
    
    // 更新模式显示
    updateModeDisplay() {
        const modeMap = {
            'LSB': 'LSB',
            'USB': 'USB',
            'CW': 'CW',
            'CWR': 'CW-R',
            'FM': 'FM',
            'AM': 'AM'
        };
        
        const displayMode = modeMap[this.currentMode] || this.currentMode;
        
        // 更新VFO显示
        const modeEl = document.getElementById('vfo-mode');
        if (modeEl) modeEl.textContent = displayMode;
        
        // 更新模式切换显示
        const modeDisplay = document.getElementById('mode-display');
        if (modeDisplay) modeDisplay.textContent = this.currentMode;
        
        // 更新模式按钮状态（如果有的话）
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.remove('active');
            const btnMode = btn.id.replace('mode-', '').toUpperCase();
            if (btnMode === this.currentMode || (this.currentMode === 'CWR' && btnMode === 'CWR')) {
                btn.classList.add('active');
            }
        });
    }
    
    // 更新S表
    updateSMeter(value) {
        // 如果后端提供了有效的S表值（0-15范围），直接使用
        if (value > 0 && value <= 15) {
            this.updateSMeterDisplay(value);
        }
        // 如果value是0-100的原始值，转换为S值
        else if (value > 15) {
            const sValue = (value / 100) * 15; // 转换为0-15范围
            this.updateSMeterDisplay(sValue);
        }
        // value为0时，使用音频计算值（已在updateSMeterFromAudio中处理）
    }
    
    // 更新功率表
    updatePowerMeter(power) {
        const fillPercent = Math.min(100, (power / 200) * 100);
        document.getElementById('power-meter-fill').style.width = fillPercent + '%';
    }
    
        // 更新SWR表
    
        updateSWRMeter(swr) {
    
            // SWR 1.0-10.0 映射到 0-100%
    
            const fillPercent = Math.min(100, ((swr - 1) / 9) * 100);
    
            document.getElementById('swr-meter-fill').style.width = fillPercent + '%';
    
        }
    
    // 更新PTT状态
    updatePTTStatus(tx) {
        const pttBtn = document.getElementById('ptt-btn');
        const pttStatus = document.getElementById('ptt-status');
        const txAudioEl = document.getElementById('audio-tx-status');
        
        if (tx) {
            pttBtn.classList.add('tx-active');
            pttStatus.textContent = 'TX';
            if (txAudioEl) txAudioEl.classList.add('tx-active');
        } else {
            pttBtn.classList.remove('tx-active');
            pttStatus.textContent = 'RX';
            if (txAudioEl) txAudioEl.classList.remove('tx-active');
        }
    }
    
    // 绑定事件
    bindEvents() {
        // 菜单按钮
        document.getElementById('menu-btn').addEventListener('click', () => this.openMenu());
        document.getElementById('menu-close').addEventListener('click', () => this.closeMenu());
        document.getElementById('overlay').addEventListener('click', () => this.closeAllPanels());
        
        // 面板关闭按钮
        document.getElementById('settings-close').addEventListener('click', () => this.closePanel('settings-panel'));
        document.getElementById('logbook-close').addEventListener('click', () => this.closePanel('logbook-panel'));
        document.getElementById('recordings-close').addEventListener('click', () => this.closePanel('recordings-panel'));
        document.getElementById('ptt-macros-close').addEventListener('click', () => this.closePanel('ptt-macros-panel'));
        
        // 菜单项
        document.getElementById('menu-settings').addEventListener('click', () => {
            this.closeMenu();
            this.openPanel('settings-panel');
        });
        document.getElementById('menu-logbook').addEventListener('click', () => {
            this.closeMenu();
            this.openPanel('logbook-panel');
        });
        document.getElementById('menu-recordings').addEventListener('click', () => {
            this.closeMenu();
            this.openPanel('recordings-panel');
            this.sendCommand('getRecordings:');
        });
        document.getElementById('menu-tune').addEventListener('click', () => {
            this.closeMenu();
            window.location.href = 'atu_tuner.html';
        });
        document.getElementById('menu-cw').addEventListener('click', () => {
            this.closeMenu();
            window.location.href = 'cw_simple.html';
        });
        document.getElementById('menu-ptt-macros').addEventListener('click', () => {
            this.closeMenu();
            this.openPanel('ptt-macros-panel');
        });
        
        // PTT按钮 - 使用pointer事件替代touch+mouse，防止重复触发
        const pttBtn = document.getElementById('ptt-btn');
        let pttPressTime = 0;
        const MIN_PRESS_TIME = 200; // 最小按压时间200ms，防止误触
        
        // 检测是否为触摸设备
        const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
        
        if (isTouchDevice) {
            // 触摸设备：只使用touch事件
            pttBtn.addEventListener('touchstart', (e) => {
                e.preventDefault();
                if (!this.pttPressed) {
                    this.pttPressed = true;
                    pttPressTime = Date.now();
                    console.log('🔴 PTT触摸开始');
                    this.pttDown();
                }
            }, {passive: false});
            
            pttBtn.addEventListener('touchend', (e) => {
                e.preventDefault();
                console.log('👆 touchend事件触发, pttPressed:', this.pttPressed);
                if (this.pttPressed) {
                    const pressDuration = Date.now() - pttPressTime;
                    console.log('🟢 PTT触摸结束, 按压时间:', pressDuration, 'ms');
                    if (pressDuration >= MIN_PRESS_TIME) {
                        this.pttUp();
                    } else {
                        console.log('⚠️ 按压时间太短，延迟释放');
                        setTimeout(() => this.pttUp(), MIN_PRESS_TIME - pressDuration);
                    }
                    this.pttPressed = false;
                }
            }, {passive: false});
            
            // 防止触摸后触发mouse事件
            pttBtn.addEventListener('mousedown', (e) => {
                e.preventDefault();
                console.log('🚫 阻止mousedown事件');
            });
            
            // 防止触摸滑动时触发其他事件
            pttBtn.addEventListener('touchmove', (e) => {
                e.preventDefault();
            }, {passive: false});
            
            // 防止触摸取消
            pttBtn.addEventListener('touchcancel', (e) => {
                e.preventDefault();
                console.log('🟡 PTT触摸取消 (touchcancel), pttPressed:', this.pttPressed, 'isTX:', this.isTX);
                if (this.pttPressed) {
                    this.pttPressed = false;
                    this.pttUp();
                }
            }, {passive: false});
        } else {
            // 桌面设备：使用mouse事件
            pttBtn.addEventListener('mousedown', (e) => {
                e.preventDefault();
                if (!this.pttPressed) {
                    this.pttPressed = true;
                    pttPressTime = Date.now();
                    console.log('🔴 PTT鼠标按下');
                    this.pttDown();
                }
            });
            
            pttBtn.addEventListener('mouseup', () => {
                if (this.pttPressed) {
                    console.log('🟢 PTT鼠标释放');
                    this.pttPressed = false;
                    this.pttUp();
                }
            });
            
            pttBtn.addEventListener('mouseleave', () => {
                if (this.pttPressed) {
                    console.log('🟡 PTT鼠标离开');
                    this.pttPressed = false;
                    this.pttUp();
                }
            });
        }
        
        // 调谐按钮 - 慢步进=当前值，快步进=下一档
        const getStep = () => this.getTuneStep();
        const getFastStep = () => {
            // 快步进是当前步进的下一档，50k时跳到100k
            const steps = this.tuneSteps;
            const currentIdx = this.tuneStepIndex;
            if (currentIdx < steps.length - 1) {
                return steps[currentIdx + 1];
            }
            return 100; // 50k的下一档是100k
        };
        document.getElementById('tune-left').addEventListener('click', () => this.tuneFrequency(-getFastStep()));
        document.getElementById('tune-left-s').addEventListener('click', () => this.tuneFrequency(-getStep()));
        document.getElementById('tune-right-s').addEventListener('click', () => this.tuneFrequency(getStep()));
        document.getElementById('tune-right').addEventListener('click', () => this.tuneFrequency(getFastStep()));
        
        // 步进切换
        document.getElementById('tune-step').addEventListener('click', () => {
            this.cycleTuneStep();
            console.log('步进切换到:', this.getTuneStep());
        });
        
        // 波段切换按钮
        document.getElementById('band-left').addEventListener('click', () => this.cycleBand(-1));
        document.getElementById('band-right').addEventListener('click', () => this.cycleBand(1));
        document.getElementById('band-display').addEventListener('click', () => this.cycleBand(1));
        
        // 模式切换按钮
        document.getElementById('mode-left').addEventListener('click', () => this.cycleMode(-1));
        document.getElementById('mode-right').addEventListener('click', () => this.cycleMode(1));
        document.getElementById('mode-display').addEventListener('click', () => this.cycleMode(1));
        
        // 模式按钮
        const modes = ['LSB', 'USB', 'CW', 'CWR', 'FM', 'AM', 'FSK'];
        modes.forEach(mode => {
            const btn = document.getElementById(`mode-${mode.toLowerCase()}`);
            if (btn) {
                btn.addEventListener('click', () => this.setMode(mode));
            }
        });
        
        // WDSP 功能按钮
        const wdspMainBtn = document.getElementById('btn-wdsp-main');
        if (wdspMainBtn) {
            wdspMainBtn.addEventListener('click', () => {
                this.toggleWDSP(!this.wdspState.enabled);
            });
        }
        
        const nr2Btn = document.getElementById('btn-nr2');
        if (nr2Btn) {
            nr2Btn.addEventListener('click', () => this.toggleNR2());
        }
        
        const nbBtn = document.getElementById('btn-nb');
        if (nbBtn) {
            nbBtn.addEventListener('click', () => this.toggleNB());
        }
        
        const anfBtn = document.getElementById('btn-anf');
        if (anfBtn) {
            anfBtn.addEventListener('click', () => this.toggleANF());
        }
        
        const agcBtn = document.getElementById('btn-agc');
        if (agcBtn) {
            agcBtn.addEventListener('click', () => this.cycleAGC());
        }
        
        // 移除VFO切换，已简化
        
        // 仪表切换（长按）
        let meterLongPress;
        document.getElementById('meter-toggle').addEventListener('touchstart', () => {
            meterLongPress = setTimeout(() => this.cycleMeter(), 500);
        });
        document.getElementById('meter-toggle').addEventListener('touchend', () => {
            clearTimeout(meterLongPress);
        });
        
        // 录音控制
        document.getElementById('start-recording').addEventListener('click', () => this.toggleRecording());
        document.getElementById('play-last').addEventListener('click', () => this.playLastRecording());
        
        // PTT宏
        document.querySelectorAll('.macro-btn').forEach(btn => {
            btn.addEventListener('click', () => this.sendMacro(btn.dataset.macro));
        });
        
        // 设置控件
        this.bindSettingsEvents();
    }
    
    // 绑定设置事件
    bindSettingsEvents() {
        // 麦克风增益滑块（底部控制区）
        const micSlider = document.getElementById('mic-slider');
        const micValue = document.getElementById('mic-value');
        if (micSlider && micValue) {
            micSlider.addEventListener('input', (e) => {
                const value = parseInt(e.target.value);
                this.settings.micGain = value;
                micValue.textContent = value;
                this.saveSettings();
                // 设置麦克风增益（如果已初始化）
                if (this.micGainNode) {
                    this.micGainNode.gain.value = value / 100;
                }
            });
        }
        
        // 音量滑块（底部控制区）
        const volSlider = document.getElementById('vol-slider');
        const volValue = document.getElementById('vol-value');
        if (volSlider && volValue) {
            volSlider.addEventListener('input', (e) => {
                const value = parseInt(e.target.value);
                this.settings.speakerVolume = value;
                volValue.textContent = value;
                this.saveSettings();
                // 设置AudioContext音量
                if (this.gainNode) {
                    this.gainNode.gain.value = value / 100;
                }
            });
        }
        
        // 麦克风增益（设置面板）
        const micGainInput = document.getElementById('mic-gain');
        if (micGainInput) {
            micGainInput.addEventListener('input', (e) => {
                this.settings.micGain = parseInt(e.target.value);
                this.saveSettings();
                this.sendCommand('setMicGain:', this.settings.micGain);
            });
        }
        
        // 扬声器音量（设置面板）
        const speakerVolInput = document.getElementById('speaker-volume');
        if (speakerVolInput) {
            speakerVolInput.addEventListener('input', (e) => {
                this.settings.speakerVolume = parseInt(e.target.value);
                this.saveSettings();
                // 设置AudioContext音量
                if (this.gainNode) {
                    this.gainNode.gain.value = this.settings.speakerVolume / 100;
                }
            });
        }
        
        // NR开关
        document.getElementById('toggle-nr').addEventListener('click', (e) => {
            this.settings.nr = !this.settings.nr;
            e.target.textContent = this.settings.nr ? '开' : '关';
            e.target.classList.toggle('active', this.settings.nr);
            this.sendCommand('setNR:', this.settings.nr ? '1' : '0');
        });
        
        // NB开关
        document.getElementById('toggle-nb').addEventListener('click', (e) => {
            this.settings.nb = !this.settings.nb;
            e.target.textContent = this.settings.nb ? '开' : '关';
            e.target.classList.toggle('active', this.settings.nb);
            this.sendCommand('setNB:', this.settings.nb ? '1' : '0');
        });
        
        // ANF开关
        document.getElementById('toggle-anf').addEventListener('click', (e) => {
            this.settings.anf = !this.settings.anf;
            e.target.textContent = this.settings.anf ? '开' : '关';
            e.target.classList.toggle('active', this.settings.anf);
            this.sendCommand('setANF:', this.settings.anf ? '1' : '0');
        });
        
        // AGC模式
        document.getElementById('agc-mode').addEventListener('change', (e) => {
            this.settings.agc = parseInt(e.target.value);
            this.saveSettings();
            this.sendCommand('setAGC:', this.settings.agc);
        });
        
        // EQ低频
        document.getElementById('eq-low').addEventListener('input', (e) => {
            this.settings.eqLow = parseInt(e.target.value);
            this.saveSettings();
            this.sendCommand('setEQ:', `low:${this.settings.eqLow}`);
        });
        
        // EQ中频
        document.getElementById('eq-mid').addEventListener('input', (e) => {
            this.settings.eqMid = parseInt(e.target.value);
            this.saveSettings();
            this.sendCommand('setEQ:', `mid:${this.settings.eqMid}`);
        });
        
        // EQ高频
        document.getElementById('eq-high').addEventListener('input', (e) => {
            this.settings.eqHigh = parseInt(e.target.value);
            this.saveSettings();
            this.sendCommand('setEQ:', `high:${this.settings.eqHigh}`);
        });
        
        // S表校准输入框（设置面板）
        const calS0Input = document.getElementById('cal-s0-input');
        const calS9Input = document.getElementById('cal-s9-input');
        
        if (calS0Input) {
            calS0Input.addEventListener('change', (e) => {
                const value = parseFloat(e.target.value);
                if (!isNaN(value) && value >= -100 && value <= 0) {
                    this.sMeterCalibration.baseNoiseDB = value;
                    this.saveSettings();
                    this.updateCalibrationDisplay();
                    this.showToast(`S0已设为 ${value}dB`, 'success');
                }
            });
        }
        
        if (calS9Input) {
            calS9Input.addEventListener('change', (e) => {
                const value = parseFloat(e.target.value);
                if (!isNaN(value) && value >= -100 && value <= 0) {
                    this.sMeterCalibration.strongSignalDB = value;
                    this.saveSettings();
                    this.updateCalibrationDisplay();
                    this.showToast(`S9+20已设为 ${value}dB`, 'success');
                }
            });
        }
    }
    
    // 更新校准信息显示（设置面板）
    updateCalibrationDisplay() {
        const calS0Input = document.getElementById('cal-s0-input');
        const calS9Input = document.getElementById('cal-s9-input');
        const calInfoSettings = document.getElementById('cal-info-settings');
        
        const baseDB = this.sMeterCalibration.baseNoiseDB;
        const strongDB = this.sMeterCalibration.strongSignalDB;
        
        // 同步输入框值
        if (calS0Input) calS0Input.value = baseDB;
        if (calS9Input) calS9Input.value = strongDB;
        
        // 更新设置面板中的显示
        if (calInfoSettings) {
            calInfoSettings.textContent = `S0@${baseDB}dB | S9+20@${strongDB}dB`;
        }
    }
    
    // 菜单操作
    openMenu() {
        document.getElementById('side-menu').classList.add('open');
        document.getElementById('overlay').classList.add('visible');
    }
    
    closeMenu() {
        document.getElementById('side-menu').classList.remove('open');
        document.getElementById('overlay').classList.remove('visible');
    }
    
    // 面板操作
    openPanel(panelId) {
        document.getElementById(panelId).classList.add('open');
        document.getElementById('overlay').classList.add('visible');
    }
    
    closePanel(panelId) {
        document.getElementById(panelId).classList.remove('open');
        document.getElementById('overlay').classList.remove('visible');
    }
    
    closeAllPanels() {
        this.closeMenu();
        this.closePanel('settings-panel');
        this.closePanel('logbook-panel');
        this.closePanel('recordings-panel');
        this.closePanel('ptt-macros-panel');
    }
    
    // PTT控制 - 使用 mobile_modern 的音频链路
    async pttDown() {
        // 标记用户正在按住PTT
        this.pttPressed = true;
        
        const now = Date.now();
        if (now - this.pttLastActionTime < this.PTT_DEBOUNCE_TIME) {
            console.log('🚫 PTT按下防抖，忽略');
            return;
        }
        this.pttLastActionTime = now;
        this.pttStartTime = now;
        
        console.log('🔴 PTT按下, isTX:', this.isTX, '时间:', new Date().toLocaleTimeString());
        
        if (this.isTX) {
            console.log('⚠️ 已经在TX状态，忽略');
            return;
        }
        
        // 检查WebSocket连接 (wsControlTRX 由 controls.js 定义)
        if (typeof wsControlTRX === 'undefined' || !wsControlTRX || wsControlTRX.readyState !== WebSocket.OPEN) {
            console.error('❌ 控制通道未连接，无法发送PTT');
            return;
        }
        
        try {
            // 使用 mobile_modern 的音频链路
            console.log('📱 使用 mobile_modern 音频链路');
            
            // 1. 初始化 TX 音频 (使用 controls.js 的函数)
            if (typeof AudioTX_start === 'function') {
                AudioTX_start();
                console.log('✅ AudioTX_start 完成');
            }
            
            // 2. 开始录音/发送 (使用 controls.js 的函数)
            if (typeof startRecord === 'function') {
                // 等待 WebSocket 连接
                await new Promise((resolve, reject) => {
                    let retries = 0;
                    const maxRetries = 10;
                    const checkWS = () => {
                        retries++;
                        if (typeof wsAudioTX !== 'undefined' && wsAudioTX && wsAudioTX.readyState === WebSocket.OPEN) {
                            resolve();
                        } else if (retries < maxRetries) {
                            setTimeout(checkWS, 50);
                        } else {
                            reject(new Error('TX WebSocket 连接超时'));
                        }
                    };
                    checkWS();
                });
                startRecord(true);
                console.log('✅ startRecord 完成');
            }
            
            // 3. 发送 PTT 命令 (使用 controls.js 的函数)
            if (typeof sendTRXptt === 'function') {
                sendTRXptt(true);
                console.log('✅ sendTRXptt(true) 完成');
            }
            
            this.isRecording = true;
            this.isTX = true;
            
            // 4. 更新UI
            this.updatePTTStatus(true);
            
            // 5. 启动ATR-1000（发射时显示功率/SWR）
            this.atr1000TXStart();
            
            console.log('🔴 PTT按下完成');
        } catch (e) {
            console.error('❌ PTT启动失败:', e);
            this.isTX = false;
            this.isRecording = false;
            this.updatePTTStatus(false);
        }
    }
    
    pttUp() {
        console.log('🟢 PTT释放开始, isTX:', this.isTX);
        
        // 强制重置所有状态
        this.pttPressed = false;
        this.isRecording = false;
        this.isTX = false;
        this.pttStartTime = null;
        
        // 清除诊断定时器
        if (this.audioDiagnosisInterval) {
            clearInterval(this.audioDiagnosisInterval);
            this.audioDiagnosisInterval = null;
        }
        
        // 立即更新UI
        this.updatePTTStatus(false);
        
        try {
            // 使用 mobile_modern 的音频链路
            console.log('📱 使用 mobile_modern 音频链路 (pttUp)');
            
            // 1. 先发送停止信号保存录音 (使用 controls.js 的函数)
            if (typeof stopRecord === 'function') {
                stopRecord();
                console.log('✅ stopRecord 完成 (发送停止信号保存录音)');
            }
            
            // 2. 发送 PTT OFF 命令 (使用 controls.js 的函数)
            if (typeof sendTRXptt === 'function') {
                sendTRXptt(false);
                console.log('✅ sendTRXptt(false) 完成');
            }
            
            // 3. 停止 TX 音频 (使用 controls.js 的函数)
            if (typeof AudioTX_stop === 'function') {
                AudioTX_stop();
                console.log('✅ AudioTX_stop 完成');
            }
            
            // 3. 恢复 RX 音频 (使用 controls.js 的函数)
            if (typeof toggleaudioRX === 'function') {
                toggleaudioRX(true);
                console.log('✅ toggleaudioRX(true) 完成');
            }
            
        } catch (e) {
            console.error('❌ PTT释放处理出错:', e);
        }
        
        // 4. 停止ATR-1000并恢复S表显示
        this.atr1000TXStop();
        this.restoreSMeterDisplay();
        
        console.log('🟢 PTT释放完成');
    }
    
    // 调谐频率
    tuneFrequency(delta) {
        console.log('tuneFrequency called with delta:', delta, 'step:', this.getTuneStep());
        const newFreq = this.currentFreq + (delta * 1000);
        console.log('Setting frequency:', newFreq);
        this.sendCommand('setFreq:', newFreq);
        this.currentFreq = newFreq;
        this.updateFreqDisplay();
    }
    
    getTuneStep() {
        return this.tuneSteps[this.tuneStepIndex];
    }
    
    cycleTuneStep() {
        this.tuneStepIndex = (this.tuneStepIndex + 1) % this.tuneSteps.length;
        const step = this.getTuneStep();
        // 0.1=100Hz, 1=1kHz, 5=5kHz, 50=50kHz
        const displayStep = step < 1 ? step * 1000 : step * 1000;
        document.getElementById('tune-step').textContent = step < 1 ? `${step * 1000}Hz` : `${step}kHz`;
    }
    
    // 波段选择
    selectBand(band) {
        const range = this.bands[band];
        if (range) {
            const freq = Math.round((range[0] + range[1]) / 2);
            this.sendCommand('setFreq:', freq);
            this.currentFreq = freq;
            this.updateFreqDisplay();
        }
    }
    
    // 波段切换（上一档/下一档）
    cycleBand(direction) {
        this.currentBandIndex = (this.currentBandIndex + direction + this.bandList.length) % this.bandList.length;
        const band = this.bandList[this.currentBandIndex];
        this.sendCommand('setFreq:', band.freq);
        this.currentFreq = band.freq;
        this.updateFreqDisplay();
        this.updateBandDisplay();
    }
    
    // 更新波段显示
    updateBandDisplay() {
        const bandDisplay = document.getElementById('band-display');
        if (bandDisplay) {
            bandDisplay.textContent = this.bandList[this.currentBandIndex].name;
        }
    }
    
    // 模式切换（上一档/下一档）
    cycleMode(direction) {
        this.currentModeIndex = (this.currentModeIndex + direction + this.modeList.length) % this.modeList.length;
        const mode = this.modeList[this.currentModeIndex];
        this.sendCommand('setMode:', mode);
        this.currentMode = mode;
        this.updateModeDisplay();
        this.updateModeDisplayElement();
    }
    
    // 更新模式显示元素
    updateModeDisplayElement() {
        const modeDisplay = document.getElementById('mode-display');
        if (modeDisplay) {
            modeDisplay.textContent = this.currentMode;
        }
    }
    
    // 模式设置
    setMode(mode) {
        this.sendCommand('setMode:', mode);
        this.currentMode = mode;
        this.updateModeDisplay();
    }
    
    // VFO切换
    toggleVFO() {
        this.currentVFO = this.currentVFO === 'A' ? 'B' : 'A';
        const vfoA = document.getElementById('vfo-a');
        const vfoB = document.getElementById('vfo-b');
        
        if (this.currentVFO === 'A') {
            vfoA.classList.add('active');
            vfoB.classList.remove('active');
        } else {
            vfoA.classList.remove('active');
            vfoB.classList.add('active');
        }
        
        this.sendCommand('setVFO:', this.currentVFO);
    }
    
    // 仪表切换
    currentMeter = 's';
    cycleMeter() {
        const meters = ['s', 'power', 'swr'];
        this.currentMeter = meters[(meters.indexOf(this.currentMeter) + 1) % meters.length];
        
        document.getElementById('s-meter').style.display = this.currentMeter === 's' ? 'block' : 'none';
        document.getElementById('power-meter').style.display = this.currentMeter === 'power' ? 'block' : 'none';
        document.getElementById('swr-meter').style.display = this.currentMeter === 'swr' ? 'block' : 'none';
    }
    
    // 功能按钮
    triggerATU() {
        this.sendCommand('startATU:');
    }
    
    toggleNR() {
        this.settings.nr = !this.settings.nr;
        const btn = document.getElementById('btn-nr');
        btn.classList.toggle('active', this.settings.nr);
        this.sendCommand('setNR:', this.settings.nr ? '1' : '0');
    }
    
    // WDSP 主开关
    toggleWDSP(enabled) {
        this.wdspState.enabled = enabled;
        console.log('🔧 WDSP 主开关:', enabled ? '启用' : '禁用');
        
        // 更新按钮状态
        this.updateWDSPButtonsState();
        
        // 发送命令到后端
        this.sendCommand('setWDSPEnabled:', enabled ? 'true' : 'false');
        
        // 如果启用，同步其他参数
        if (enabled) {
            setTimeout(() => {
                this.sendCommand('setWDSPNR2Level:', this.wdspState.nr2Level.toString());
                this.sendCommand('setWDSPNB:', this.wdspState.nb ? 'true' : 'false');
                this.sendCommand('setWDSPANF:', this.wdspState.anf ? 'true' : 'false');
                this.sendCommand('setWDSPAGC:', this.wdspState.agcMode.toString());
            }, 100);
        }
        
        this.saveWDSPState();
    }
    
    // 循环切换 NR2 级别 (关 → 极 → 低 → 中 → 高 → 关)
    toggleNR2() {
        if (!this.wdspState.enabled) return;
        this.wdspState.nr2Level = (this.wdspState.nr2Level + 1) % 5;
        this.updateNR2ButtonUI();
        this.sendCommand('setWDSPNR2Level:', this.wdspState.nr2Level.toString());
        this.saveWDSPState();
        console.log('🔧 NR2 强度:', this.NR2_LEVEL_NAMES[this.wdspState.nr2Level]);
    }
    
    // 切换 NB
    toggleNB() {
        if (!this.wdspState.enabled) return;
        this.wdspState.nb = !this.wdspState.nb;
        this.updateWDSPButtonUI('nb', this.wdspState.nb);
        this.sendCommand('setWDSPNB:', this.wdspState.nb ? 'true' : 'false');
        this.saveWDSPState();
        console.log('🔧 NB:', this.wdspState.nb ? '开启' : '关闭');
    }
    
    // 切换 ANF
    toggleANF() {
        if (!this.wdspState.enabled) return;
        this.wdspState.anf = !this.wdspState.anf;
        this.updateWDSPButtonUI('anf', this.wdspState.anf);
        this.sendCommand('setWDSPANF:', this.wdspState.anf ? 'true' : 'false');
        this.saveWDSPState();
        console.log('🔧 ANF:', this.wdspState.anf ? '开启' : '关闭');
    }
    
    // 循环切换 AGC 模式
    cycleAGC() {
        if (!this.wdspState.enabled) return;
        this.wdspState.agcMode = (this.wdspState.agcMode + 1) % 5;
        this.updateAGCButtonUI();
        this.sendCommand('setWDSPAGC:', this.wdspState.agcMode.toString());
        this.saveWDSPState();
        console.log('🔧 AGC:', this.AGC_MODE_NAMES[this.wdspState.agcMode]);
    }
    
    // 更新 NR2 按钮 UI
    updateNR2ButtonUI() {
        const btn = document.getElementById('btn-nr2');
        if (btn) {
            btn.textContent = `NR2-${this.NR2_LEVEL_NAMES[this.wdspState.nr2Level]}`;
            btn.classList.toggle('active', this.wdspState.nr2Level > 0 && this.wdspState.enabled);
            btn.disabled = !this.wdspState.enabled;
        }
    }

    // 更新 WDSP 按钮 UI
    updateWDSPButtonUI(type, enabled) {
        const btn = document.getElementById(`btn-${type}`);
        if (btn) {
            btn.classList.toggle('active', enabled && this.wdspState.enabled);
            btn.disabled = !this.wdspState.enabled;
        }
    }

    // 更新 AGC 按钮 UI
    updateAGCButtonUI() {
        const btn = document.getElementById('btn-agc');
        if (btn) {
            btn.textContent = `AGC-${this.AGC_MODE_NAMES[this.wdspState.agcMode]}`;
            btn.classList.toggle('active', this.wdspState.agcMode > 0 && this.wdspState.enabled);
            btn.disabled = !this.wdspState.enabled;
        }
    }

    // 更新所有 WDSP 按钮状态
    updateWDSPButtonsState() {
        // 更新主开关
        const mainBtn = document.getElementById('btn-wdsp-main');
        if (mainBtn) {
            mainBtn.classList.toggle('inactive', !this.wdspState.enabled);
            mainBtn.textContent = this.wdspState.enabled ? 'DSP' : 'dsp';
        }

        this.updateNR2ButtonUI();
        this.updateWDSPButtonUI('nb', this.wdspState.nb);
        this.updateWDSPButtonUI('anf', this.wdspState.anf);
        this.updateAGCButtonUI();
    }
    
    // 保存 WDSP 状态
    saveWDSPState() {
        try {
            localStorage.setItem('sdr_modern_wdsp', JSON.stringify(this.wdspState));
        } catch (e) {
            console.error('保存 WDSP 状态失败:', e);
        }
    }
    
    // 加载 WDSP 状态
    loadWDSPState() {
        try {
            const saved = localStorage.getItem('sdr_modern_wdsp');
            if (saved) {
                this.wdspState = { ...this.wdspState, ...JSON.parse(saved) };
                console.log('🔧 WDSP 状态已加载:', this.wdspState);
            }
        } catch (e) {
            console.error('加载 WDSP 状态失败:', e);
        }
    }
    
    // 处理 WDSP 状态响应
    handleWDSPStatus(status) {
        try {
            const data = JSON.parse(status);
            this.wdspState.enabled = data.enabled;
            
            // 支持两种格式：扁平化格式 或 嵌套 config 格式
            const config = data.config || data;
            
            // 更新 NR2 级别
            if (config.nr2Level !== undefined) {
                this.wdspState.nr2Level = config.nr2Level;
            }
            if (config.nr2_enabled !== undefined) {
                this.wdspState.nr2 = config.nr2_enabled;
            }
            
            // 更新其他设置
            if (config.nbEnabled !== undefined) {
                this.wdspState.nb = config.nbEnabled;
            } else if (config.nb_enabled !== undefined) {
                this.wdspState.nb = config.nb_enabled;
            }
            
            if (config.anfEnabled !== undefined) {
                this.wdspState.anf = config.anfEnabled;
            } else if (config.anf_enabled !== undefined) {
                this.wdspState.anf = config.anf_enabled;
            }
            
            if (config.agcMode !== undefined) {
                this.wdspState.agcMode = config.agcMode;
            } else if (config.agc_mode !== undefined) {
                this.wdspState.agcMode = config.agc_mode;
            }
            
            // 更新 UI
            this.updateWDSPButtonsState();
            console.log('🔧 WDSP 状态已更新:', this.wdspState);
        } catch (e) {
            console.error('WDSP 状态解析错误:', e);
        }
    }
    
    // ATR-1000 连接
    connectATR1000() {
        if (this.atr1000.ws && (this.atr1000.ws.readyState === WebSocket.OPEN || this.atr1000.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }
        
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            const url = `${protocol}//${host}/WSATR1000`;
            
            console.log('📻 连接 ATR-1000:', url);
            this.atr1000.ws = new WebSocket(url);
            
            this.atr1000.ws.onopen = () => {
                this.atr1000.isConnected = true;
                console.log('✅ ATR-1000 已连接');
            };
            
            this.atr1000.ws.onmessage = (event) => {
                this.handleATR1000Message(event.data);
            };
            
            this.atr1000.ws.onclose = () => {
                this.atr1000.isConnected = false;
                console.log('🔴 ATR-1000 断开');
            };
            
            this.atr1000.ws.onerror = (err) => {
                console.error('❌ ATR-1000 错误:', err);
            };
        } catch (e) {
            console.error('ATR-1000 连接失败:', e);
        }
    }
    
    // ATR-1000 断开
    disconnectATR1000() {
        if (this.atr1000.ws) {
            this.atr1000.ws.close();
            this.atr1000.ws = null;
        }
        this.atr1000.isConnected = false;
    }
    
    // ATR-1000 消息处理
    handleATR1000Message(data) {
        try {
            const msg = JSON.parse(data.trim());
            if (msg.type === 'atr1000_meter') {
                this.atr1000.lastPower = msg.power || 0;
                this.atr1000.lastSWR = msg.swr || 1.0;
                
                // 如果在TX状态，更新功率/SWR显示
                if (this.isTX) {
                    this.updateTXMeterDisplay();
                }
            }
        } catch (e) {
            // 静默处理
        }
    }
    
    // ATR-1000 TX开始
    atr1000TXStart() {
        this.atr1000._txActive = true;
        this.connectATR1000();
        
        // 启动功率/SWR显示更新定时器（100ms刷新）
        if (this.atr1000.txMeterInterval) {
            clearInterval(this.atr1000.txMeterInterval);
        }
        this.atr1000.txMeterInterval = setInterval(() => {
            if (this.isTX) {
                this.updateTXMeterDisplay();
            }
        }, 100);
        
        setTimeout(() => {
            if (this.atr1000.ws && this.atr1000.ws.readyState === WebSocket.OPEN) {
                this.atr1000.ws.send(JSON.stringify({action: 'start'}));
                console.log('📤 ATR-1000 start');
            }
        }, 100);
    }
    
    // ATR-1000 TX停止
    atr1000TXStop() {
        this.atr1000._txActive = false;
        
        // 停止功率/SWR显示更新定时器
        if (this.atr1000.txMeterInterval) {
            clearInterval(this.atr1000.txMeterInterval);
            this.atr1000.txMeterInterval = null;
        }
        
        if (this.atr1000.ws && this.atr1000.ws.readyState === WebSocket.OPEN) {
            this.atr1000.ws.send(JSON.stringify({action: 'stop'}));
            console.log('🛑 ATR-1000 stop');
        }
        // 清零显示
        this.atr1000.lastPower = 0;
        this.atr1000.lastSWR = 1.0;
        
        // 恢复S表显示
        this.restoreSMeterDisplay();
    }
    
    // 更新TX时的功率/SWR显示（在S表位置）
    updateTXMeterDisplay() {
        const power = this.atr1000.lastPower;
        const swr = this.atr1000.lastSWR;
        
        // 更新S表为功率显示
        const fill = document.getElementById('s-meter-fill');
        const label = document.getElementById('s-meter-label');
        
        if (fill && label) {
            // 功率映射到0-100%（最大200W）
            const powerPercent = Math.min(100, (power / 200) * 100);
            fill.style.width = powerPercent + '%';
            fill.style.background = '#4CAF50'; // 绿色功率条
            
            // 显示功率和SWR
            label.textContent = `${power}W SWR:${swr.toFixed(1)}`;
            label.style.color = power > 100 ? '#ff4444' : '#4CAF50';
        }
    }
    
    // 恢复S表显示
    restoreSMeterDisplay() {
        const fill = document.getElementById('s-meter-fill');
        const label = document.getElementById('s-meter-label');
        
        if (fill && label) {
            // 恢复S表颜色
            fill.style.background = '';
            label.style.color = '';
            // S表值会在下次updateSMeterFromAudio时更新
        }
    }
    
    // 录音功能
    toggleRecording() {
        const btn = document.getElementById('start-recording');
        
        if (this.isRecording) {
            this.sendCommand('stopRecording:');
            btn.classList.remove('recording');
            btn.textContent = '● 录音';
            this.isRecording = false;
        } else {
            this.sendCommand('startRecording:');
            btn.classList.add('recording');
            btn.textContent = '■ 停止';
            this.isRecording = true;
        }
    }
    
    playLastRecording() {
        this.sendCommand('playLastRecording:');
    }
    
    updateRecordingsList(data) {
        // 解析录音列表并显示
        console.log('录音列表:', data);
    }
    
    // PTT宏
    sendMacro(macroName) {
        let text = this.macros[macroName] || macroName;
        // 替换呼号占位符
        text = text.replace('[CALL]', this.settings.callSign || 'N0CALL');
        
        if (this.isTX) {
            // 发送CW文本
            this.sendCommand('sendCW:', text);
        }
    }
    
    // 设置持久化
    loadSettings() {
        try {
            const saved = localStorage.getItem('sdr_modern_settings');
            if (saved) {
                const data = JSON.parse(saved);
                
                // 兼容旧格式（直接是settings）和新格式（包含settings和calibration）
                if (data.settings) {
                    this.settings = { ...this.settings, ...data.settings };
                    if (data.calibration) {
                        this.sMeterCalibration = { ...this.sMeterCalibration, ...data.calibration };
                    }
                } else {
                    // 旧格式直接是settings
                    this.settings = { ...this.settings, ...data };
                }
                
                // 恢复UI状态
                const micGainEl = document.getElementById('mic-gain');
                if (micGainEl) micGainEl.value = this.settings.micGain;
                
                const speakerVolEl = document.getElementById('speaker-volume');
                if (speakerVolEl) speakerVolEl.value = this.settings.speakerVolume;
                
                const agcModeEl = document.getElementById('agc-mode');
                if (agcModeEl) agcModeEl.value = this.settings.agc;
                
                const eqLowEl = document.getElementById('eq-low');
                if (eqLowEl) eqLowEl.value = this.settings.eqLow;
                
                const eqMidEl = document.getElementById('eq-mid');
                if (eqMidEl) eqMidEl.value = this.settings.eqMid;
                
                const eqHighEl = document.getElementById('eq-high');
                if (eqHighEl) eqHighEl.value = this.settings.eqHigh;
                
                // 同步新的滑块值
                const volSlider = document.getElementById('vol-slider');
                const volValue = document.getElementById('vol-value');
                if (volSlider && volValue) {
                    volSlider.value = this.settings.speakerVolume;
                    volValue.textContent = this.settings.speakerVolume;
                }
                
                const micSlider = document.getElementById('mic-slider');
                const micValue = document.getElementById('mic-value');
                if (micSlider && micValue) {
                    micSlider.value = this.settings.micGain;
                    micValue.textContent = this.settings.micGain;
                }
                
                console.log('📊 S表校准参数已加载:', this.sMeterCalibration);
                
                // 更新校准输入框显示
                this.updateCalibrationDisplay();
            }
        } catch (e) {
            console.error('加载设置失败:', e);
        }
    }
    
    saveSettings() {
        try {
            const data = {
                settings: this.settings,
                calibration: this.sMeterCalibration
            };
            localStorage.setItem('sdr_modern_settings', JSON.stringify(data));
        } catch (e) {
            console.error('保存设置失败:', e);
        }
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    window.sdr = new SDRModern();
});
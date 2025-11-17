// iPhone Ham Radio Remote - 可工作的音频实现
// 基于已验证的工作实现进行优化

// 全局变量
let isConnected = false;
let isTransmitting = false;
let currentFrequency = 7053000;
let currentMode = 'USB';

// WebSocket连接
let wsControlTRX = null;
let wsAudioRX = null;
let wsAudioTX = null;

// 音频上下文和相关变量（直接复制自mobile_audio_direct_copy.js）
var AudioRX_context = "";
var AudioRX_source_node = "";
var AudioRX_gain_node = "";
var AudioRX_biquadFilter_node = "";
var AudioRX_analyser = "";
var audiobufferready = false;
var AudioRX_audiobuffer = [];
var AudioRX_sampleRate = 16000;
var audioContextInitialized = false; // Track if audio context has been initialized with user gesture

// Mobile-specific variables
var isMobileDevice = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

// DOM元素引用
const domElements = {
    powerBtn: null,
    pttBtn: null,
    freqDisplay: null,
    statusCtrl: null,
    statusRX: null,
    statusTX: null,
    signalText: null
};

// 初始化应用
document.addEventListener('DOMContentLoaded', function() {
    console.log('iPhone Ham Radio Remote initializing...');
    initializeElements();
    setupEventListeners();
    updateFrequencyDisplay();
    
    // 添加一次性的全局触摸事件监听器来初始化音频上下文
    document.addEventListener('touchstart', initAudioOnFirstTouch, { once: true });
    document.addEventListener('mousedown', initAudioOnFirstTouch, { once: true });
});

// 初始化DOM元素
function initializeElements() {
    domElements.powerBtn = document.getElementById('power-btn');
    domElements.pttBtn = document.getElementById('ptt-btn');
    domElements.freqDisplay = document.getElementById('freq-main');
    domElements.statusCtrl = document.getElementById('status-ctrl');
    domElements.statusRX = document.getElementById('status-rx');
    domElements.statusTX = document.getElementById('status-tx');
    domElements.signalText = document.getElementById('signal-text');
    
    console.log('DOM elements initialized');
}

// 在用户首次交互时初始化音频上下文
function initAudioOnFirstTouch() {
    if (audioContextInitialized) return;
    
    try {
        // 直接调用已验证的工作音频启动函数
        console.log('Initializing audio with proven implementation');
        AudioRX_start();
        audioContextInitialized = true;
        console.log('Audio context initialized on user gesture');
    } catch (e) {
        console.error('Failed to initialize audio context:', e);
    }
}

// 设置事件监听器
function setupEventListeners() {
    // 电源按钮
    if (domElements.powerBtn) {
        domElements.powerBtn.addEventListener('click', togglePower);
    }
    
    // PTT按钮
    if (domElements.pttBtn) {
        domElements.pttBtn.addEventListener('touchstart', handlePTTStart, { passive: false });
        domElements.pttBtn.addEventListener('touchend', handlePTTEnd, { passive: false });
        domElements.pttBtn.addEventListener('mousedown', handlePTTStart);
        domElements.pttBtn.addEventListener('mouseup', handlePTTEnd);
        domElements.pttBtn.addEventListener('mouseleave', handlePTTEnd);
    }
    
    // 频率调节按钮
    document.querySelectorAll('.digit-up, .digit-down').forEach(button => {
        button.addEventListener('click', handleFrequencyChange);
    });
    
    // 模式选择按钮
    document.querySelectorAll('.mode-btn').forEach(button => {
        button.addEventListener('click', handleModeChange);
    });
    
    // VFO选择按钮
    document.querySelectorAll('.vfo-btn').forEach(button => {
        button.addEventListener('click', handleVFOChange);
    });
    
    // 频段选择按钮
    document.querySelectorAll('.band-btn').forEach(button => {
        button.addEventListener('click', handleBandChange);
    });
    
    console.log('Event listeners setup completed');
}

// 音频启动函数（直接复制自mobile_audio_direct_copy.js并优化）
function AudioRX_start() {
    console.log('Starting AudioRX with proven implementation');
    
    // 更新状态指示器
    const indwsAudioRX = document.getElementById("indwsAudioRX");
    if (indwsAudioRX) {
        indwsAudioRX.innerHTML = '<img src="img/critsgrey.png">wsRX';
    }
    
    AudioRX_audiobuffer = [];

    // 建立WebSocket连接
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const baseUrl = `${protocol}//${window.location.host}`;
    wsAudioRX = new WebSocket(`${baseUrl}/WSaudioRX`);
    wsAudioRX.binaryType = 'arraybuffer';
    wsAudioRX.onmessage = appendwsAudioRX;
    wsAudioRX.onopen = wsAudioRXopen;
    wsAudioRX.onclose = wsAudioRXclose;
    wsAudioRX.onerror = wsAudioRXerror;

    // 每秒打印一次码率（RX/TX）
    if (!window.__brTimer) {
        window.__rxBytes = 0;
        window.__txBytes = 0;
        window.__brTimer = setInterval(function() {
            var rxkbps = (window.__rxBytes || 0) * 8 / 1000; // Kbps
            var txkbps = (window.__txBytes || 0) * 8 / 1000;
            console.log(`[码率] RX: ${rxkbps.toFixed(1)} kbps, TX: ${txkbps.toFixed(1)} kbps`);
            window.__rxBytes = 0;
            window.__txBytes = 0;
        }, 1000);
    }

    function appendwsAudioRX(msg) {
        // 码率统计：RX
        if (!window.__rxBytes) {
            window.__rxBytes = 0;
        }
        if (msg && msg.data && msg.data.byteLength) {
            window.__rxBytes += msg.data.byteLength;
        }
        // 限制缓冲区大小，防止累积过多音频数据
        if (AudioRX_audiobuffer.length > 10) {
            AudioRX_audiobuffer = AudioRX_audiobuffer.slice(-5); // 只保留最新的5个缓冲区
        }
        // Convert Int16 to Float32 for Web Audio API
        const int16Data = new Int16Array(msg.data);
        const float32Data = new Float32Array(int16Data.length);
        for (let i = 0; i < int16Data.length; i++) {
            float32Data[i] = int16Data[i] / 32767.0;
        }
        AudioRX_audiobuffer.push(float32Data);
        
        // Initialize audio context on first audio data if not already initialized
        if (!audioContextInitialized) {
            initializeAudioContextOnUserGesture();
        }
    }

    // Initialize audio context with user gesture handling for iOS Safari
    function initializeAudioContextOnUserGesture() {
        if (audioContextInitialized) return;
        
        try {
            // Create AudioContext with proper settings optimized for mobile
            const audioContextOptions = {
                latencyHint: isMobileDevice ? "playback" : "interactive",
                sampleRate: AudioRX_sampleRate
            };
            
            // For iOS, we might need to use a different sample rate
            if (isMobileDevice && typeof webkitAudioContext !== 'undefined') {
                // iOS Safari sometimes works better with default sample rate
                audioContextOptions.sampleRate = undefined;
            }
            
            AudioRX_context = new (window.AudioContext || window.webkitAudioContext)(audioContextOptions);
            AudioRX_gain_node = AudioRX_context.createGain();
            AudioRX_biquadFilter_node = AudioRX_context.createBiquadFilter();
            AudioRX_analyser = AudioRX_context.createAnalyser();

            // 优先使用 AudioWorkletNode 播放，失败则回退到 ScriptProcessor
            // For mobile devices, we'll optimize the buffer settings
            const targetMinFrames = isMobileDevice ? 2 : 16;
            const targetMaxFrames = isMobileDevice ? 4 : 32;
            
            (async () => {
                try {
                    // 尝试加载AudioWorklet模块
                    await AudioRX_context.audioWorklet.addModule('rx_worklet_processor.js');
                    const rxNode = new AudioWorkletNode(AudioRX_context, 'rx-player');
                    AudioRX_source_node = rxNode;
                    
                    // 配置缓冲区参数
                    try {
                        rxNode.port.postMessage({
                            type: 'config',
                            min: targetMinFrames,
                            max: targetMaxFrames
                        });
                    } catch (_) {}
                    
                    // 设置数据推送函数
                    window.__pushRxFrame = function(f32) {
                        rxNode.port.postMessage({
                            type: 'push',
                            payload: f32
                        });
                    };
                    
                    // 更新消息处理函数
                    wsAudioRX.onmessage = function(msg) {
                        if (!window.__rxBytes) window.__rxBytes = 0;
                        if (msg && msg.data && msg.data.byteLength) window.__rxBytes += msg.data.byteLength;
                        try {
                            const int16Data = new Int16Array(msg.data);
                            const float32Data = new Float32Array(int16Data.length);
                            for (let i = 0; i < int16Data.length; i++) {
                                float32Data[i] = int16Data[i] / 32767.0;
                            }
                            window.__pushRxFrame(float32Data);
                        } catch (e) {
                            try {
                                const int16Data = new Int16Array(msg.data);
                                const float32Data = new Float32Array(int16Data.length);
                                for (let i = 0; i < int16Data.length; i++) {
                                    float32Data[i] = int16Data[i] / 32767.0;
                                }
                                AudioRX_audiobuffer.push(float32Data);
                            } catch (_) {}
                        }
                    };
                    rxNode.connect(AudioRX_biquadFilter_node);
                    console.log('AudioWorklet initialized successfully');
                } catch (e) {
                    // 回退到 ScriptProcessor
                    console.log('Using ScriptProcessor fallback for audio playback:', e);
                    const BUFF_SIZE = isMobileDevice ? 1024 : 256;
                    AudioRX_source_node = AudioRX_context.createScriptProcessor(BUFF_SIZE, 1, 1);
                    AudioRX_source_node.onaudioprocess = (function() {
                        return function(event) {
                            var out = event.outputBuffer.getChannelData(0);
                            if (AudioRX_audiobuffer.length === 0) { out.fill(0); return; }
                            var cur = AudioRX_audiobuffer[0];
                            var n = Math.min(cur.length, out.length);
                            for (var j = 0; j < n; j++) out[j] = cur[j];
                            for (var k = n; k < out.length; k++) out[k] = 0;
                            if (n >= cur.length) AudioRX_audiobuffer.shift(); else AudioRX_audiobuffer[0] = cur.slice(n);
                        };
                    }());
                    AudioRX_source_node.connect(AudioRX_biquadFilter_node);
                }
                
                // 连接音频节点
                AudioRX_biquadFilter_node.connect(AudioRX_gain_node);
                AudioRX_gain_node.connect(AudioRX_analyser);
                AudioRX_gain_node.connect(AudioRX_context.destination);
                
                // 设置初始音频参数
                AudioRX_biquadFilter_node.type = "lowshelf";
                AudioRX_biquadFilter_node.frequency.setValueAtTime(AudioRX_sampleRate/2, AudioRX_context.currentTime);
                AudioRX_biquadFilter_node.gain.setValueAtTime(0, AudioRX_context.currentTime);
                
                AudioRX_SetGAIN();
                
                audioContextInitialized = true;
                console.log('Audio context initialized successfully');
                
                // 更新状态指示器
                if (indwsAudioRX) {
                    indwsAudioRX.innerHTML = '<img src="img/critsgreen.png">wsRX';
                }
            })();
        } catch (e) {
            console.error('Failed to initialize audio context:', e);
            // 更新状态指示器
            if (indwsAudioRX) {
                indwsAudioRX.innerHTML = '<img src="img/critsred.png">wsRX';
            }
        }
    }

    // 设置初始消息处理函数
    wsAudioRX.onmessage = function(msg) {
        // Just buffer the audio data until audio context is ready
        appendwsAudioRX(msg);
    };
}

// 设置音频增益
function AudioRX_SetGAIN(vol = "None") {
    if (vol == "None") {
        volumeRX = isMobileDevice ? 1.0 : 0.8; // Higher default volume for mobile
        vol = volumeRX;
    }
    if (AudioRX_context && AudioRX_gain_node) {
        AudioRX_gain_node.gain.setValueAtTime(vol, AudioRX_context.currentTime);
    }
}

// WebSocket事件处理函数
function wsAudioRXopen() {
    console.log('WebSocket audio RX connection opened');
    const indwsAudioRX = document.getElementById("indwsAudioRX");
    if (indwsAudioRX) {
        indwsAudioRX.innerHTML = '<img src="img/critsgreen.png">wsRX';
    }
}

function wsAudioRXclose() {
    console.log('WebSocket audio RX connection closed');
    const indwsAudioRX = document.getElementById("indwsAudioRX");
    if (indwsAudioRX) {
        indwsAudioRX.innerHTML = '<img src="img/critsred.png">wsRX';
    }
    AudioRX_stop();
}

function wsAudioRXerror(err) {
    console.log('WebSocket audio RX error:', err);
    const indwsAudioRX = document.getElementById("indwsAudioRX");
    if (indwsAudioRX) {
        indwsAudioRX.innerHTML = '<img src="img/critsred.png">wsRX';
    }
    AudioRX_stop();
}

// 音频停止函数
function AudioRX_stop() {
    console.log('Stopping AudioRX');
    if (wsAudioRX) {
        wsAudioRX.close();
    }
    if (AudioRX_source_node) {
        AudioRX_source_node.onaudioprocess = null;
    }
    // 不要关闭音频上下文以避免重新初始化问题
    // audioContextInitialized = false;
}

// 电源开关
function togglePower() {
    if (isConnected) {
        // 断开连接
        disconnect();
        if (domElements.powerBtn) {
            domElements.powerBtn.classList.remove('power-on');
            domElements.powerBtn.classList.add('power-off');
            domElements.powerBtn.textContent = '⏻';
        }
    } else {
        // 建立连接
        connect();
        // 立即更新按钮状态
        if (domElements.powerBtn) {
            domElements.powerBtn.classList.remove('power-off');
            domElements.powerBtn.classList.add('power-on');
            domElements.powerBtn.textContent = '⏼';
        }
    }
}

// 建立WebSocket连接
function connect() {
    console.log('Connecting to UHRR server...');
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const baseUrl = `${protocol}//${window.location.host}`;
    
    try {
        // 控制WebSocket
        wsControlTRX = new WebSocket(`${baseUrl}/WSCTRX`);
        wsControlTRX.onopen = handleControlOpen;
        wsControlTRX.onmessage = handleControlMessage;
        wsControlTRX.onclose = handleControlClose;
        wsControlTRX.onerror = handleControlError;
        
        // 音频TX WebSocket
        wsAudioTX = new WebSocket(`${baseUrl}/WSaudioTX`);
        wsAudioTX.onopen = handleAudioTXOpen;
        wsAudioTX.onclose = handleAudioTXClose;
        wsAudioTX.onerror = handleAudioTXError;
        
        console.log('WebSocket connections initiated');
    } catch (error) {
        console.error('Failed to establish WebSocket connections:', error);
    }
}

// 断开连接
function disconnect() {
    console.log('Disconnecting from UHRR server...');
    
    if (wsControlTRX) {
        wsControlTRX.close();
        wsControlTRX = null;
    }
    
    if (wsAudioRX) {
        wsAudioRX.close();
        wsAudioRX = null;
    }
    
    if (wsAudioTX) {
        wsAudioTX.close();
        wsAudioTX = null;
    }
    
    isConnected = false;
    updateConnectionStatus();
    
    console.log('Disconnected from UHRR server');
}

// WebSocket事件处理函数
function handleControlOpen() {
    console.log('Control WebSocket connected');
    isConnected = true;
    updateConnectionStatus();
    
    // 请求初始状态
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send('getFreq:');
        wsControlTRX.send('getMode:');
    }
    
    // 连接成功后立即启动音频
    setTimeout(() => {
        if (isConnected) {
            AudioRX_start();
        }
    }, 100);
}

function handleControlMessage(event) {
    const data = event.data;
    
    const parts = data.split(':');
    const command = parts[0];
    const value = parts[1];
    
    switch (command) {
        case 'getFreq':
            const freq = parseInt(value);
            if (freq && freq > 0) {
                currentFrequency = freq;
                updateFrequencyDisplay();
            }
            break;
        case 'getMode':
            if (value) {
                currentMode = value;
                updateModeDisplay();
            }
            break;
        case 'getSignalLevel':
            updateSignalDisplay(value);
            break;
        case 'getPTT':
            const pttStatus = value === 'true';
            updatePTTStatus(pttStatus);
            break;
    }
}

function handleControlClose() {
    console.log('Control WebSocket disconnected');
    isConnected = false;
    updateConnectionStatus();
}

function handleControlError(error) {
    console.error('Control WebSocket error:', error);
    isConnected = false;
    updateConnectionStatus();
}

function handleAudioTXOpen() {
    console.log('Audio TX WebSocket connected');
    updateConnectionStatus();
    
    // 更新隐藏的状态指示器
    const indwsAudioTX = document.getElementById('indwsAudioTX');
    if (indwsAudioTX) {
        indwsAudioTX.innerHTML = '<img src="img/critsgreen.png">wsTX';
    }
}

function handleAudioTXClose() {
    console.log('Audio TX WebSocket disconnected');
    updateConnectionStatus();
    
    // 更新隐藏的状态指示器
    const indwsAudioTX = document.getElementById('indwsAudioTX');
    if (indwsAudioTX) {
        indwsAudioTX.innerHTML = '<img src="img/critsred.png">wsTX';
    }
}

function handleAudioTXError(error) {
    console.error('Audio TX WebSocket error:', error);
    updateConnectionStatus();
    
    // 更新隐藏的状态指示器
    const indwsAudioTX = document.getElementById('indwsAudioTX');
    if (indwsAudioTX) {
        indwsAudioTX.innerHTML = '<img src="img/critsred.png">wsTX';
    }
}

// 更新连接状态显示
function updateConnectionStatus() {
    if (domElements.statusCtrl) {
        if (isConnected) {
            domElements.statusCtrl.classList.add('connected');
        } else {
            domElements.statusCtrl.classList.remove('connected');
        }
    }
    
    if (domElements.statusRX) {
        if (wsAudioRX && wsAudioRX.readyState === WebSocket.OPEN) {
            domElements.statusRX.classList.add('connected');
        } else {
            domElements.statusRX.classList.remove('connected');
        }
    }
    
    if (domElements.statusTX) {
        if (wsAudioTX && wsAudioTX.readyState === WebSocket.OPEN) {
            domElements.statusTX.classList.add('connected');
        } else {
            domElements.statusTX.classList.remove('connected');
        }
    }
}

// 更新频率显示
function updateFrequencyDisplay() {
    if (!domElements.freqDisplay) return;
    
    // 格式化频率显示
    const freqStr = currentFrequency.toString().padStart(9, '0');
    const formattedFreq = `${freqStr.substring(0, 1)}.${freqStr.substring(1, 4)}.${freqStr.substring(4, 7)}`;
    domElements.freqDisplay.textContent = formattedFreq;
    
    // 更新各个数字段显示
    document.getElementById('cmhz').textContent = freqStr[0];
    document.getElementById('dmhz').textContent = freqStr[1];
    document.getElementById('umhz').textContent = freqStr[2];
    document.getElementById('ckhz').textContent = freqStr[3];
    document.getElementById('dkhz').textContent = freqStr[4];
    document.getElementById('ukhz').textContent = freqStr[5];
    document.getElementById('chz').textContent = freqStr[6];
    document.getElementById('dhz').textContent = freqStr[7];
    document.getElementById('uhz').textContent = freqStr[8];
}

// 更新模式显示
function updateModeDisplay() {
    document.querySelectorAll('.mode-btn').forEach(button => {
        if (button.dataset.mode === currentMode) {
            button.classList.add('active');
        } else {
            button.classList.remove('active');
        }
    });
}

// 更新信号显示
function updateSignalDisplay(level) {
    if (domElements.signalText) {
        domElements.signalText.textContent = `S${level}`;
    }
    
    // 更新信号条显示
    const signalBars = document.querySelectorAll('.signal-bar');
    const levelInt = parseInt(level) || 0;
    
    signalBars.forEach((bar, index) => {
        if (index < levelInt) {
            bar.style.backgroundColor = '#4CAF50';
        } else {
            bar.style.backgroundColor = '#666';
        }
    });
}

// 更新PTT状态显示
function updatePTTStatus(isTransmitting) {
    if (domElements.statusTX) {
        if (isTransmitting) {
            domElements.statusTX.classList.add('active');
        } else {
            domElements.statusTX.classList.remove('active');
        }
    }
    
    // 更新RX状态显示
    if (domElements.statusRX) {
        if (isTransmitting) {
            domElements.statusRX.classList.remove('active');
        } else {
            domElements.statusRX.classList.add('active');
        }
    }
}

// PTT按钮处理
function handlePTTStart(event) {
    event.preventDefault();
    if (!isConnected) {
        console.warn('Not connected to server');
        return;
    }
    
    // 确保音频上下文已resume（iOS Safari要求）
    if (AudioRX_context && AudioRX_context.state === 'suspended') {
        AudioRX_context.resume().then(() => {
            console.log('AudioContext resumed on PTT start');
        }).catch(err => {
            console.error('Failed to resume AudioContext on PTT start:', err);
        });
    }
    
    if (isTransmitting) {
        console.log('Already transmitting');
        return;
    }
    
    console.log('PTT Start');
    isTransmitting = true;
    updatePTTStatus(true);
    
    // 发送PTT命令
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send('setPTT:true');
    }
    
    // 发送预热帧
    sendPTTWarmupFrames();
    
    // 触觉反馈
    if (navigator.vibrate) {
        navigator.vibrate(50);
    }
}

function handlePTTEnd(event) {
    event.preventDefault();
    if (!isTransmitting) {
        return;
    }
    
    console.log('PTT End');
    isTransmitting = false;
    updatePTTStatus(false);
    
    // 发送PTT停止命令
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send('setPTT:false');
    }
    
    // 清除音频缓冲区以减少延迟
    if (AudioRX_audiobuffer) {
        AudioRX_audiobuffer = [];
        console.log('Audio buffer cleared');
    }
    
    // 如果使用AudioWorklet，发送flush命令
    if (AudioRX_source_node && AudioRX_source_node.port) {
        try {
            AudioRX_source_node.port.postMessage({type: 'flush'});
            console.log('AudioWorklet buffer flushed');
        } catch (e) {
            console.warn('Failed to flush AudioWorklet buffer:', e);
        }
    }
    
    // 触觉反馈
    if (navigator.vibrate) {
        navigator.vibrate(25);
    }
}

// 发送PTT预热帧
function sendPTTWarmupFrames() {
    if (!wsAudioTX || wsAudioTX.readyState !== WebSocket.OPEN) {
        console.warn('Audio TX WebSocket not connected');
        return;
    }
    
    console.log('Sending PTT warmup frames...');
    
    // 发送10个预热帧
    for (let i = 0; i < 10; i++) {
        setTimeout(() => {
            try {
                // 创建静音帧
                const warmup = new Int16Array(160); // 160个样本
                
                if (wsAudioTX && wsAudioTX.readyState === WebSocket.OPEN) {
                    wsAudioTX.send(warmup);
                    console.log(`Sent warmup frame ${i + 1}/10`);
                }
            } catch (error) {
                console.warn(`Failed to send warmup frame ${i}:`, error);
            }
        }, i * 10); // 每10ms发送一帧
    }
}

// 频率调节处理
function handleFrequencyChange(event) {
    if (!isConnected) return;
    
    const button = event.target;
    const digit = button.dataset.digit;
    const isUp = button.classList.contains('digit-up');
    
    // 计算频率变化步长
    let step = 0;
    switch (digit) {
        case 'cmhz': step = 100000000; break;
        case 'dmhz': step = 10000000; break;
        case 'umhz': step = 1000000; break;
        case 'ckhz': step = 100000; break;
        case 'dkhz': step = 10000; break;
        case 'ukhz': step = 1000; break;
        case 'chz': step = 100; break;
        case 'dhz': step = 10; break;
        case 'uhz': step = 1; break;
    }
    
    // 应用步长
    if (!isUp) step = -step;
    currentFrequency += step;
    
    // 确保频率不为负
    if (currentFrequency < 0) currentFrequency = 0;
    
    // 更新显示
    updateFrequencyDisplay();
    
    // 发送频率变更到服务器
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setFreq:${currentFrequency}`);
    }
}

// 模式变更处理
function handleModeChange(event) {
    if (!isConnected) return;
    
    const button = event.target;
    const mode = button.dataset.mode;
    
    // 更新当前模式
    currentMode = mode;
    
    // 更新UI
    updateModeDisplay();
    
    // 发送模式变更到服务器
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setMode:${mode}`);
    }
}

// VFO变更处理
function handleVFOChange(event) {
    console.log('VFO change requested:', event.target.dataset.vfo);
}

// 频段变更处理
function handleBandChange(event) {
    if (!isConnected) return;
    
    const button = event.target;
    const bandFreq = parseInt(button.dataset.band);
    
    // 更新当前频率
    currentFrequency = bandFreq;
    
    // 更新显示
    updateFrequencyDisplay();
    
    // 发送频率变更到服务器
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setFreq:${currentFrequency}`);
    }
}

// 防止页面缩放
let lastTouchEnd = 0;
document.addEventListener('touchend', function(event) {
    const now = (new Date()).getTime();
    if (now - lastTouchEnd <= 300) {
        event.preventDefault();
    }
    lastTouchEnd = now;
}, false);

console.log('iPhone Ham Radio Remote script loaded');
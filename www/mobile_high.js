// High Quality Mobile Interface - 48kHz TX
// V1.0.0 - 2026-03-08
// 高品质语音版本：TX 48kHz PCM 直发，RX 保持 Opus 16kHz
// 
// 重要：此文件依赖 controls.js 先加载
// 核心改动：覆盖 TX 音频处理，不降采样，直接发送 48kHz PCM

////////////////////////////////////////////////////////////
// 高品质模式配置 - TX 48kHz PCM / RX 16kHz PCM
////////////////////////////////////////////////////////////
const HQ_MODE = {
    enabled: true,
    txSampleRate: 48000,    // TX 使用 48kHz PCM（高品质发射）
    rxSampleRate: 16000,    // RX 使用 16kHz PCM（兼容性好）
    useOpus: false,         // 不使用 Opus 编码
    
    // 16kHz RX 缓冲区参数
    minBufferFrames: 2,
    maxBufferFrames: 20,
    targetBufferFrames: 5,
    
    // TX 参数
    txFrameSize: 960,       // 48kHz * 20ms = 960 samples
    txBufferSize: 2048      // ScriptProcessor 缓冲区
};

console.log('🎵 高品质模式已启用: TX=' + HQ_MODE.txSampleRate + 'Hz PCM, RX=' + HQ_MODE.rxSampleRate + 'Hz PCM');

// 设置 RX 采样率为 16kHz
if (typeof AudioRX_sampleRate !== 'undefined') {
    AudioRX_sampleRate = 16000;
    console.log('📡 RX 采样率已设置为 16000Hz');
}

////////////////////////////////////////////////////////////
// Wake Lock - 防止屏幕休眠
////////////////////////////////////////////////////////////
let wakeLock = null;
let wakeLockSupported = null;

async function requestWakeLock() {
    if (wakeLock) return;
    if (wakeLockSupported === null) {
        wakeLockSupported = 'wakeLock' in navigator;
    }
    if (!wakeLockSupported) return;
    
    try {
        wakeLock = await navigator.wakeLock.request('screen');
        console.log('🔒 Wake Lock 已启用 (HQ Mode)');
        wakeLock.addEventListener('release', () => { wakeLock = null; });
    } catch (err) {
        if (err.name !== 'NotAllowedError') {
            console.log('⚠️ Wake Lock 请求失败:', err.name);
        }
    }
}

async function releaseWakeLock() {
    if (wakeLock) {
        try {
            await wakeLock.release();
            wakeLock = null;
        } catch (err) {
            wakeLock = null;
        }
    }
}

////////////////////////////////////////////////////////////
// 移动端状态
////////////////////////////////////////////////////////////
const IS_MOBILE_LOCAL = typeof IS_MOBILE !== 'undefined' ? IS_MOBILE : /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

var mobileState = {
    isConnected: false,
    currentFrequency: 7053000,
    currentMode: 'USB',
    currentVFO: 'VFO-A',
    isTransmitting: false,
    tuneStep: 100
};

////////////////////////////////////////////////////////////
// DOM 元素引用
////////////////////////////////////////////////////////////
const domElements = {
    menuToggle: null,
    menuClose: null,
    menuOverlay: null,
    mainMenu: null,
    pttButton: null,
    tuneButton: null,
    powerButton: null,
    freqDisplay: null,
    freqInput: null,
    modeIndicator: null,
    vfoIndicator: null,
    statusCtrl: null,
    statusRX: null,
    statusTX: null,
    sMeterCanvas: null,
    quickButtons: null,
    tuneButtons: null
};

////////////////////////////////////////////////////////////
// 高品质 TX 处理器 - 覆盖 controls.js 的 OpusEncoderProcessor
////////////////////////////////////////////////////////////

// 保存原始的 AudioTX_start 函数
var original_AudioTX_start = null;

// 高品质 TX 处理器（48kHz PCM 直发）
var HQ_TxProcessor = null;
var HQ_MediaHandler = null;

function HQ_AudioTX_start() {
    console.log('🎵 HQ_AudioTX_start: 初始化高品质 TX (48kHz PCM)');
    
    // 设置全局变量（controls.js 中定义）
    if (typeof isRecording !== 'undefined') isRecording = false;
    if (typeof encode !== 'undefined') encode = false;  // 高品质模式不使用 Opus 编码
    
    // 使用安全的方式更新 DOM
    var el = document.getElementById("indwsAudioTX");
    if (el) el.innerHTML = '<img src="img/critsgrey.png">wsTX';
    
    // 创建 WebSocket（使用全局变量 wsAudioTX）
    var ws = new WebSocket('wss://' + window.location.href.split('/')[2] + '/WSaudioTX');
    
    ws.onopen = function() {
        var el = document.getElementById("indwsAudioTX");
        if (el) el.innerHTML = '<img src="img/critsgreen.png">wsTX';
        console.log('✅ HQ TX WebSocket 已连接');
    };
    
    ws.onerror = function(err) {
        var el = document.getElementById("indwsAudioTX");
        if (el) el.innerHTML = '<img src="img/critsred.png">wsTX';
        console.error('❌ HQ TX WebSocket 错误:', err);
        ws.close();
        setTimeout(HQ_AudioTX_start, 1000);
    };
    
    ws.onclose = function() {
        var el = document.getElementById("indwsAudioTX");
        if (el) el.innerHTML = '<img src="img/critsred.png">wsTX';
    };
    
    // 设置全局 wsAudioTX 变量（controls.js 中定义）
    if (typeof wsAudioTX !== 'undefined') {
        wsAudioTX = ws;
    }
    
    // 创建高品质 TX 处理器（不降采样）
    HQ_TxProcessor = new HQ_TxProcessorClass(ws);
    HQ_MediaHandler = new HQ_MediaHandlerClass(HQ_TxProcessor);
    
    // 替换全局变量（controls.js 中定义）- 直接设置确保生效
    try { ap = HQ_TxProcessor; } catch(e) {}
    try { mh = HQ_MediaHandler; } catch(e) {}
    window.mh = HQ_MediaHandler;  // 确保全局可访问
    window.ap = HQ_TxProcessor;
    
    console.log('✅ HQ_MediaHandler 已设置: window.mh =', window.mh);
    
    // 加载 MIC 增益设置
    setTimeout(function() {
        try {
            var micGain = '150';  // 高品质模式默认 150%
            if (typeof loadUserAudioSetting === 'function') {
                micGain = loadUserAudioSetting('mobile_mic_gain', '150');
            } else if (typeof getCookie === 'function') {
                var c = getCookie('mobile_mic_gain');
                if (c) micGain = c;
            }
            // 升级旧的低增益值
            if (parseInt(micGain) <= 100) micGain = '150';
            setMicGain(micGain);
            console.log('🎤 MIC 增益已加载:', micGain + '%');
        } catch (e) {
            console.warn('加载 MIC 增益失败:', e);
        }
    }, 500);
}

// 高品质 TX 处理器类（48kHz PCM 直发，不降采样）
function HQ_TxProcessorClass(wsh) {
    this.wsh = wsh;
    this.bufferSize = 2048;
    this.downSample = 1;  // 关键：不降采样！
    this.txSampleRate = 48000;  // 使用原始 48kHz
    
    // 累积缓冲区
    this.accumulator = new Int16Array(0);
    
    // 发送帧大小：48kHz * 20ms = 960 samples
    this.frameSize = 960;
    
    console.log('🎵 HQ TX 处理器初始化: sampleRate=' + this.txSampleRate + ', frameSize=' + this.frameSize);
}

HQ_TxProcessorClass.prototype.onAudioProcess = function(e) {
    // 检查全局 isRecording 变量（controls.js 中定义）
    if (typeof isRecording !== 'undefined' && !isRecording) return;
    
    var data = e.inputBuffer.getChannelData(0);
    
    // 转换为 Int16（不降采样）
    var int16Data = new Int16Array(data.length);
    for (var i = 0; i < data.length; i++) {
        int16Data[i] = Math.max(-32768, Math.min(32767, Math.floor(data[i] * 32767)));
    }
    
    // 累积数据
    var newAccumulator = new Int16Array(this.accumulator.length + int16Data.length);
    newAccumulator.set(this.accumulator);
    newAccumulator.set(int16Data, this.accumulator.length);
    this.accumulator = newAccumulator;
    
    // 发送完整帧
    while (this.accumulator.length >= this.frameSize) {
        var frame = this.accumulator.slice(0, this.frameSize);
        this.accumulator = this.accumulator.slice(this.frameSize);
        
        // 检查 WebSocket 状态
        if (this.wsh.readyState !== WebSocket.OPEN) {
            return;
        }
        
        // 直接发送 PCM Int16 数据
        this.wsh.send(frame.buffer);
        
        // 码率统计
        if (!window.__txBytes) { window.__txBytes = 0; }
        window.__txBytes += frame.byteLength;
    }
    
    // 更新电平表（安全检查）
    try {
        if (typeof TXinstantMeter !== 'undefined' && TXinstantMeter) {
            var sum = 0;
            for (var j = 0; j < data.length; j++) {
                sum += data[j] * data[j];
            }
            TXinstantMeter.value = Math.sqrt(sum / data.length) * 100;
        }
    } catch (e) {
        // 忽略电平表更新错误
    }
};

// 高品质 MediaHandler（使用 48kHz）
function HQ_MediaHandlerClass(audioProcessor) {
    console.log('🎤 HQ_MediaHandler: 创建高品质 TX 音频上下文 (48kHz)...');
    
    var context = new (window.AudioContext || window.webkitAudioContext)();
    if (!context.createScriptProcessor) {
        context.createScriptProcessor = context.createJavaScriptNode;
    }
    
    console.log('🎤 HQ_MediaHandler: AudioContext 采样率:', context.sampleRate);
    
    // iOS Safari 兼容性
    if (context.state === 'suspended') {
        console.log('🎤 HQ_MediaHandler: AudioContext suspended，尝试恢复...');
        context.resume().then(() => {
            console.log('✅ HQ_MediaHandler: AudioContext 已恢复');
        }).catch(e => {
            console.error('❌ HQ_MediaHandler: AudioContext 恢复失败:', e);
        });
    }
    
    this.context = context;
    this.audioProcessor = audioProcessor;
    
    // 获取麦克风
    var self = this;
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: 48000,  // 请求 48kHz
                channelCount: 1,
                echoCancellation: false,
                noiseSuppression: false,
                autoGainControl: false
            },
            video: false
        }).then(function(stream) {
            console.log('✅ HQ_MediaHandler: 麦克风权限获取成功');
            self.callback.bind(self)(stream);
        }).catch(function(err) {
            console.error('❌ HQ_MediaHandler: 麦克风权限获取失败:', err);
        });
    } else {
        console.warn('⚠️ mediaDevices.getUserMedia 不可用');
    }
}

// 复制 MediaHandler 的 callback 方法
HQ_MediaHandlerClass.prototype.callback = function(stream) {
    var self = this;
    this.stream = stream;
    
    // 创建音频源
    this.micSource = this.context.createMediaStreamSource(stream);
    
    // TX EQ 均衡器链（如果存在）
    var lastNode = this.micSource;
    
    // 检查是否有 TX EQ 设置
    if (typeof createTX_EQ_Chain === 'function') {
        var eqChain = createTX_EQ_Chain(this.context);
        if (eqChain) {
            lastNode.connect(eqChain.input);
            lastNode = eqChain.output;
        }
    }
    
    // 增益节点 - 高品质模式默认使用更高的增益
    this.gain_node = this.context.createGain();
    
    // 读取保存的 MIC 增益，默认 150%（高品质模式需要更高增益）
    var savedMicGain = '150';
    try {
        if (typeof loadUserAudioSetting === 'function') {
            savedMicGain = loadUserAudioSetting('mobile_mic_gain', '150');
        } else if (typeof getCookie === 'function') {
            var c = getCookie('mobile_mic_gain');
            if (c) savedMicGain = c;
        }
    } catch(e) {}
    
    var initialGain = parseInt(savedMicGain) / 100;
    this.gain_node.gain.value = initialGain;
    console.log('🎤 HQ TX 初始增益: ' + initialGain + ' (' + savedMicGain + '%)');
    
    lastNode.connect(this.gain_node);
    lastNode = this.gain_node;
    
    // 创建 ScriptProcessor
    var bufferSize = this.audioProcessor.bufferSize || 2048;
    this.scriptProcessor = this.context.createScriptProcessor(bufferSize, 1, 1);
    this.scriptProcessor.onaudioprocess = function(e) {
        self.audioProcessor.onAudioProcess(e);
    };
    
    lastNode.connect(this.scriptProcessor);
    this.scriptProcessor.connect(this.context.destination);
    
    console.log('✅ HQ_MediaHandler: 音频链已建立 (48kHz)');
};

HQ_MediaHandlerClass.prototype.error = function(err) {
    console.error('❌ HQ_MediaHandler error:', err);
};

////////////////////////////////////////////////////////////
// 高品质模式的 sendSettings 覆盖
////////////////////////////////////////////////////////////
function HQ_sendSettings() {
    // 设置全局 encode 变量（controls.js 中定义）
    if (typeof encode !== 'undefined') encode = 0;  // 高品质模式不使用 Opus
    
    // 发送 48kHz 采样率
    var rate = String(HQ_MODE.txSampleRate);  // 48000
    var opusRate = '0';  // 不使用 Opus
    var opusFrameDur = '0';
    
    var msg = "m:" + [rate, 0, opusRate, opusFrameDur].join(",");
    console.log('🎵 HQ sendSettings: ' + msg);
    
    // 使用全局 wsAudioTX 变量
    if (typeof wsAudioTX !== 'undefined' && wsAudioTX && wsAudioTX.readyState === WebSocket.OPEN) {
        wsAudioTX.send(msg);
    }
}

////////////////////////////////////////////////////////////
// 立即覆盖 controls.js 的函数（脚本加载时立即执行）
////////////////////////////////////////////////////////////

// 立即执行覆盖，不等待 DOMContentLoaded（因为脚本在 body 末尾）
console.log('🚀 Mobile High Quality - 立即执行覆盖...');

// 保存原始函数引用
if (typeof AudioTX_start !== 'undefined') {
    original_AudioTX_start = AudioTX_start;
}
// 立即覆盖
window.AudioTX_start = HQ_AudioTX_start;
window.sendSettings = HQ_sendSettings;
console.log('✅ 已覆盖 AudioTX_start 和 sendSettings');

// 覆盖 AudioRX_start 函数，使用 16kHz RX
var original_AudioRX_start = null;
function HQ_AudioRX_start() {
    console.log('🎵 HQ_AudioRX_start: 初始化 16kHz RX PCM');
    
    // 设置 RX 采样率为 16000
    if (typeof AudioRX_sampleRate !== 'undefined') {
        AudioRX_sampleRate = 16000;
        console.log('  📡 RX 采样率已设置为 16000Hz');
    }
    
    // 禁用 Opus 解码
    if (typeof AudioRX_opusDecode !== 'undefined') {
        AudioRX_opusDecode = false;
        console.log('  📡 RX Opus 解码已禁用');
    }
    
    // 强制取消 encode 复选框（controls.js 会检查这个）
    var encodeElement = document.getElementById("encode");
    if (encodeElement) {
        encodeElement.checked = false;
        console.log('  📡 encode 复选框已取消');
    }
    
    // 调用原始的 AudioRX_start（此时 AudioRX_sampleRate 已是 16000）
    if (original_AudioRX_start) {
        original_AudioRX_start();
    }
    
    // 缓冲区优化
    setTimeout(function() {
        if (typeof AudioRX_source_node !== 'undefined' && AudioRX_source_node && AudioRX_source_node.port) {
            AudioRX_source_node.port.postMessage({
                type: 'config',
                min: HQ_MODE.minBufferFrames,
                max: HQ_MODE.maxBufferFrames
            });
            console.log('📡 AudioWorklet 缓冲区已配置: min=' + HQ_MODE.minBufferFrames + ', max=' + HQ_MODE.maxBufferFrames);
        }
    }, 500);
}

// 覆盖 wsAudioRXopen 函数，请求后端发送 16kHz Int16 数据
var original_wsAudioRXopen = null;
function HQ_wsAudioRXopen() {
    console.log('🎵 HQ_wsAudioRXopen: 请求后端发送 16kHz Int16 数据');
    
    // 设置 UI 状态
    if (typeof safeSetInnerHTML === 'function') {
        safeSetInnerHTML("indwsAudioRX", '<img src="img/critsgreen.png">wsRX');
    }
    
    // 发送请求到后端：禁用 Opus，降采样到 16kHz
    setTimeout(function() {
        if (typeof wsAudioRX !== 'undefined' && wsAudioRX) {
            var request = JSON.stringify({
                action: "set_opus_encode",
                enabled: false,      // 禁用 Opus
                rate: 16000,         // 降采样到 16kHz
                frame_dur: 20
            });
            try {
                wsAudioRX.send(request);
                console.log('📡 已请求后端: Int16 PCM @ 16kHz');
            } catch(e) {
                console.error('📡 发送请求失败:', e);
            }
        }
    }, 100);
}

// 延迟覆盖（等 controls.js 加载完成）
setTimeout(function() {
    if (typeof AudioRX_start !== 'undefined' && !original_AudioRX_start) {
        original_AudioRX_start = AudioRX_start;
        window.AudioRX_start = HQ_AudioRX_start;
        console.log('✅ 已覆盖 AudioRX_start → HQ_AudioRX_start');
    }
    if (typeof wsAudioRXopen !== 'undefined' && !original_wsAudioRXopen) {
        original_wsAudioRXopen = wsAudioRXopen;
        window.wsAudioRXopen = HQ_wsAudioRXopen;
        console.log('✅ 已覆盖 wsAudioRXopen → HQ_wsAudioRXopen');
    }
}, 50);

////////////////////////////////////////////////////////////
// DOMContentLoaded 后初始化 UI
////////////////////////////////////////////////////////////

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Mobile High Quality UI 初始化...');
    
    // 初始化 UI 元素
    try {
        initializeElements();
        console.log('✅ DOM元素初始化完成');
    } catch (e) {
        console.error('❌ initializeElements 失败:', e);
    }
    
    try {
        setupEventListeners();
        console.log('✅ 事件监听器设置完成');
    } catch (e) {
        console.error('❌ setupEventListeners 失败:', e);
    }
    
    try {
        initializeSMeter();
    } catch (e) {
        console.error('❌ initializeSMeter 失败:', e);
    }
    
    try {
        updateFrequencyDisplay();
    } catch (e) {
        console.error('❌ updateFrequencyDisplay 失败:', e);
    }
    
    try {
        setupMenuItems();
    } catch (e) {
        console.error('❌ setupMenuItems 失败:', e);
    }
    
    try {
        loadAudioSettingsFromCookies();
    } catch (e) {
        console.error('❌ loadAudioSettingsFromCookies 失败:', e);
    }
    
    // iOS Safari 音频初始化
    document.addEventListener('touchstart', initAudioOnFirstTouch, { once: true });
    document.addEventListener('mousedown', initAudioOnFirstTouch, { once: true });
    
    // 页面可见性变化
    document.addEventListener('visibilitychange', async () => {
        if (document.visibilityState === 'visible' && mobileState.isConnected) {
            await requestWakeLock();
        }
    });
    
    console.log('✅ Mobile High Quality UI 初始化完成');
});

////////////////////////////////////////////////////////////
// 复制 mobile_modern.js 的核心功能
////////////////////////////////////////////////////////////

function initializeElements() {
    domElements.menuToggle = document.getElementById('menu-toggle');
    domElements.menuClose = document.getElementById('menu-close');
    domElements.menuOverlay = document.getElementById('menu-overlay');
    domElements.mainMenu = document.getElementById('main-menu');
    domElements.pttButton = document.getElementById('ptt-btn');
    domElements.tuneButton = document.getElementById('tune-btn');
    domElements.powerButton = document.getElementById('power-btn');
    domElements.freqDisplay = document.getElementById('freq-main-display');
    domElements.freqInput = document.getElementById('freq-input');
    domElements.modeIndicator = document.getElementById('mode-indicator');
    domElements.vfoIndicator = document.getElementById('vfo-indicator');
    domElements.statusCtrl = document.getElementById('status-ctrl');
    domElements.statusRX = document.getElementById('status-rx');
    domElements.statusTX = document.getElementById('status-tx');
    domElements.sMeterCanvas = document.getElementById('s-meter-canvas');
    domElements.quickButtons = document.querySelectorAll('.quick-btn');
    domElements.tuneButtons = document.querySelectorAll('.tune-btn-grid');
}

////////////////////////////////////////////////////////////
// 电源开关 - 不依赖全局 event 对象
////////////////////////////////////////////////////////////
function togglePower() {
    console.log('🔋 togglePower 被调用, 当前 poweron:', (typeof poweron !== 'undefined') ? poweron : 'undefined');
    
    // 直接调用底层函数，不使用 powertogle()（它依赖全局 event 对象）
    
    if (typeof poweron !== 'undefined' && poweron) {
        // 断开连接
        console.log('🔴 正在关闭电源...');
        try {
            if (typeof AudioRX_stop === 'function') AudioRX_stop();
            if (typeof AudioTX_stop === 'function') AudioTX_stop();
            if (typeof ControlTRX_stop === 'function') ControlTRX_stop();
        } catch (e) {
            console.error('关闭电源时出错:', e);
        }
        poweron = false;
        
        // 更新按钮状态
        if (domElements.powerButton) {
            domElements.powerButton.classList.remove('active');
            var icon = domElements.powerButton.querySelector('.power-icon');
            if (icon) icon.textContent = '⏻';
        }
        console.log('🔴 电源已关闭');
        
        releaseWakeLock();
        mobileState.isConnected = false;
    } else {
        // 连接
        console.log('🟢 正在开启电源 (HQ 48kHz TX)...');
        
        // HQ 模式：禁用 RX Opus 解码
        if (typeof AudioRX_opusDecode !== 'undefined') {
            AudioRX_opusDecode = false;
            console.log('  📡 HQ模式：禁用 RX Opus 解码');
        }
        
        try {
            if (typeof check_connected === 'function') check_connected();
            if (typeof AudioRX_start === 'function') {
                console.log('  调用 AudioRX_start...');
                AudioRX_start();
            }
            if (typeof AudioTX_start === 'function') {
                console.log('  调用 AudioTX_start (HQ 48kHz)...');
                AudioTX_start();  // 这会调用我们的 HQ_AudioTX_start
            }
            if (typeof ControlTRX_start === 'function') {
                console.log('  调用 ControlTRX_start...');
                ControlTRX_start();
            }
            if (typeof checklatency === 'function') checklatency();
        } catch (e) {
            console.error('开启电源时出错:', e);
        }
        poweron = true;
        
        // 更新按钮状态
        if (domElements.powerButton) {
            domElements.powerButton.classList.add('active');
            var icon = domElements.powerButton.querySelector('.power-icon');
            if (icon) icon.textContent = '⏼';
        }
        console.log('🟢 电源已开启 (HQ 48kHz TX)');
        
        requestWakeLock();
        mobileState.isConnected = true;
        
        // 更新状态指示器
        updateConnectionStatus(true);
    }
}

function setupEventListeners() {
    // Power button - 使用自定义 togglePower，不依赖全局 event 对象
    if (domElements.powerButton) {
        domElements.powerButton.addEventListener('click', function() {
            togglePower();
        });
    }
    
    // Menu toggle
    if (domElements.menuToggle) {
        domElements.menuToggle.addEventListener('click', function() {
            domElements.mainMenu.classList.add('open');
            domElements.menuOverlay.classList.add('active');
        });
    }
    
    // Menu close
    if (domElements.menuClose) {
        domElements.menuClose.addEventListener('click', closeMenu);
    }
    if (domElements.menuOverlay) {
        domElements.menuOverlay.addEventListener('click', closeMenu);
    }
    
    // Mode button
    var modeBtn = document.getElementById('mode-btn');
    if (modeBtn) {
        modeBtn.addEventListener('click', function() {
            cycleMode();
        });
    }
    
    // Band button
    var bandBtn = document.getElementById('band-btn');
    if (bandBtn) {
        bandBtn.addEventListener('click', function() {
            cycleBand();
        });
    }
    
    // Filter button
    var filterBtn = document.getElementById('filter-btn');
    if (filterBtn) {
        filterBtn.addEventListener('click', function() {
            cycleFilter();
        });
    }
    
    // Frequency tuning buttons
    domElements.tuneButtons.forEach(function(btn) {
        btn.addEventListener('click', function() {
            var step = parseInt(this.getAttribute('data-step'));
            adjustFrequency(step);
        });
    });
    
    // Frequency display click to input
    if (domElements.freqDisplay) {
        domElements.freqDisplay.addEventListener('click', function() {
            showFrequencyInput();
        });
    }
    
    // Frequency input
    if (domElements.freqInput) {
        domElements.freqInput.addEventListener('blur', function() {
            hideFrequencyInput();
        });
        domElements.freqInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                hideFrequencyInput();
            }
        });
    }
    
    // TUNE 天调按钮 - 长按发射1kHz单音
    if (domElements.tuneButton) {
        // 触摸开始
        domElements.tuneButton.addEventListener('touchstart', function(e) {
            e.preventDefault();
            this.classList.add('active');
            if (typeof startTune === 'function') {
                startTune();
            }
        });
        
        // 触摸结束
        domElements.tuneButton.addEventListener('touchend', function(e) {
            e.preventDefault();
            this.classList.remove('active');
            if (typeof stopTune === 'function') {
                stopTune();
            }
        });
        
        // 鼠标按下
        domElements.tuneButton.addEventListener('mousedown', function(e) {
            e.preventDefault();
            this.classList.add('active');
            if (typeof startTune === 'function') {
                startTune();
            }
        });
        
        // 鼠标释放
        domElements.tuneButton.addEventListener('mouseup', function(e) {
            e.preventDefault();
            this.classList.remove('active');
            if (typeof stopTune === 'function') {
                stopTune();
            }
        });
        
        // 鼠标离开按钮
        domElements.tuneButton.addEventListener('mouseleave', function(e) {
            if (this.classList.contains('active')) {
                this.classList.remove('active');
                if (typeof stopTune === 'function') {
                    stopTune();
                }
            }
        });
        
        console.log('🎵 TUNE 天调按钮已初始化');
    }
}

function closeMenu() {
    if (domElements.mainMenu) domElements.mainMenu.classList.remove('open');
    if (domElements.menuOverlay) domElements.menuOverlay.classList.remove('active');
}

var modes = ['USB', 'LSB', 'CW', 'AM', 'FM'];
var currentModeIndex = 0;

function cycleMode() {
    currentModeIndex = (currentModeIndex + 1) % modes.length;
    var mode = modes[currentModeIndex];
    var modeBtn = document.getElementById('mode-btn');
    if (modeBtn) modeBtn.textContent = mode;
    if (domElements.modeIndicator) domElements.modeIndicator.textContent = mode;
    
    // 发送模式切换命令
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send('setMode:' + mode);
    }
}

var bands = ['160m', '80m', '40m', '30m', '20m', '17m', '15m', '12m', '10m'];
var bandFreqs = {
    '160m': 1900000, '80m': 3750000, '40m': 7150000,
    '30m': 10125000, '20m': 14200000, '17m': 18118000,
    '15m': 21225000, '12m': 24940000, '10m': 28500000
};
var currentBandIndex = 4; // 默认 20m

function cycleBand() {
    currentBandIndex = (currentBandIndex + 1) % bands.length;
    var band = bands[currentBandIndex];
    var freq = bandFreqs[band];
    var bandBtn = document.getElementById('band-btn');
    if (bandBtn) bandBtn.textContent = band;
    
    mobileState.currentFrequency = freq;
    updateFrequencyDisplay();
    
    // 发送频率命令
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send('setFreq:' + freq);
    }
}

var filters = ['OFF', 'MID', 'WIDE', 'NAR'];
var currentFilterIndex = 0;  // 默认 OFF

// 滤波器设置：使用 lowshelf + highshelf 组合实现带通效果
// lowshelf: 衰减低于截止频率的低频（设为负增益）
// highshelf: 衰减高于截止频率的高频（设为负增益）
var filterSettings = {
    'OFF': {
        name: 'OFF',
        lowCut: 0,
        highCut: 0,
        attenuation: 0
    },
    'MID': {
        name: 'MID',
        lowCut: 200,    // 低截止频率
        highCut: 2700,  // 高截止频率
        attenuation: -20 // 衰减量 (dB) - 降低到 -20dB 避免过度衰减
    },
    'WIDE': {
        name: 'WIDE',
        lowCut: 200,
        highCut: 3000,
        attenuation: -20
    },
    'NAR': {
        name: 'NAR',
        lowCut: 300,
        highCut: 2100,
        attenuation: -20
    }
};

// 高品质模式滤波器节点
var HQ_RX_lowFilter = null;   // 低频切除
var HQ_RX_highFilter = null;  // 高频切除
var filterChainConnected = false;

function cycleFilter() {
    currentFilterIndex = (currentFilterIndex + 1) % filters.length;
    var filter = filters[currentFilterIndex];
    var filterBtn = document.getElementById('filter-btn');
    if (filterBtn) filterBtn.textContent = filter;
    
    // 应用滤波器设置
    applyRXFilter(filter);
}

function applyRXFilter(filterName) {
    var settings = filterSettings[filterName];
    if (!settings) return;
    
    console.log('📻 设置 RX 滤波器:', filterName, settings);
    
    // 检查 AudioRX_context 是否存在
    if (typeof AudioRX_context === 'undefined' || !AudioRX_context) {
        console.warn('AudioRX_context 不存在，无法设置滤波器');
        return;
    }
    
    // OFF 模式：断开滤波器，直通
    if (filterName === 'OFF') {
        // 断开滤波器链
        if (HQ_RX_lowFilter) {
            try { HQ_RX_lowFilter.disconnect(); } catch(e) {}
        }
        if (HQ_RX_highFilter) {
            try { HQ_RX_highFilter.disconnect(); } catch(e) {}
        }
        // 恢复直连：biquadFilter → gain_node
        if (typeof AudioRX_biquadFilter_node !== 'undefined' && AudioRX_biquadFilter_node &&
            typeof AudioRX_gain_node !== 'undefined' && AudioRX_gain_node) {
            try {
                AudioRX_biquadFilter_node.disconnect();
                AudioRX_biquadFilter_node.connect(AudioRX_gain_node);
            } catch(e) {}
        }
        filterChainConnected = false;
        console.log('📻 RX 滤波器已关闭');
        return;
    }
    
    // 创建滤波器节点（如果还没有）
    if (!HQ_RX_lowFilter) {
        try {
            HQ_RX_lowFilter = AudioRX_context.createBiquadFilter();
            HQ_RX_lowFilter.type = 'lowshelf';  // 低架滤波器衰减低频
            console.log('✅ HQ_RX_lowFilter 已创建 (lowshelf)');
        } catch (e) {
            console.error('创建 HQ_RX_lowFilter 失败:', e);
        }
    }
    
    if (!HQ_RX_highFilter) {
        try {
            HQ_RX_highFilter = AudioRX_context.createBiquadFilter();
            HQ_RX_highFilter.type = 'highshelf';  // 高架滤波器衰减高频
            console.log('✅ HQ_RX_highFilter 已创建 (highshelf)');
        } catch (e) {
            console.error('创建 HQ_RX_highFilter 失败:', e);
        }
    }
    
    // 设置滤波器参数
    // lowshelf: 衰减低于 lowCut 的低频
    if (HQ_RX_lowFilter) {
        HQ_RX_lowFilter.frequency.setValueAtTime(settings.lowCut, AudioRX_context.currentTime);
        HQ_RX_lowFilter.gain.setValueAtTime(settings.attenuation, AudioRX_context.currentTime);
        console.log('  lowshelf: freq=' + settings.lowCut + 'Hz, gain=' + settings.attenuation + 'dB');
    }
    
    // highshelf: 衰减高于 highCut 的高频
    if (HQ_RX_highFilter) {
        HQ_RX_highFilter.frequency.setValueAtTime(settings.highCut, AudioRX_context.currentTime);
        HQ_RX_highFilter.gain.setValueAtTime(settings.attenuation, AudioRX_context.currentTime);
        console.log('  highshelf: freq=' + settings.highCut + 'Hz, gain=' + settings.attenuation + 'dB');
    }
    
    // 将滤波器插入音频链
    try {
        if (typeof AudioRX_biquadFilter_node !== 'undefined' && AudioRX_biquadFilter_node && 
            typeof AudioRX_gain_node !== 'undefined' && AudioRX_gain_node &&
            HQ_RX_lowFilter && HQ_RX_highFilter) {
            
            // 如果已经连接过，先断开
            if (filterChainConnected) {
                try {
                    AudioRX_biquadFilter_node.disconnect();
                    HQ_RX_lowFilter.disconnect();
                    HQ_RX_highFilter.disconnect();
                } catch (e) {}
            } else {
                // 首次连接，断开原有连接
                try {
                    AudioRX_biquadFilter_node.disconnect(AudioRX_gain_node);
                } catch (e) {}
            }
            
            // 重新连接：biquadFilter → lowFilter → highFilter → gain_node
            AudioRX_biquadFilter_node.connect(HQ_RX_lowFilter);
            HQ_RX_lowFilter.connect(HQ_RX_highFilter);
            HQ_RX_highFilter.connect(AudioRX_gain_node);
            
            filterChainConnected = true;
            console.log('✅ RX 滤波器链已插入:', filterName);
        }
    } catch (e) {
        console.error('插入滤波器链失败:', e);
    }
}

function adjustFrequency(step) {
    mobileState.currentFrequency += step;
    if (mobileState.currentFrequency < 1000000) mobileState.currentFrequency = 1000000;
    if (mobileState.currentFrequency > 60000000) mobileState.currentFrequency = 60000000;
    updateFrequencyDisplay();
    
    // 发送频率命令
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send('setFreq:' + mobileState.currentFrequency);
    }
}

function updateFrequencyDisplay() {
    var freq = mobileState.currentFrequency;
    var freqKHz = Math.floor(freq / 1000);
    var freqStr = freqKHz.toString().padStart(5, '0');
    
    var digits = ['freq-10mhz', 'freq-1mhz', 'freq-100khz', 'freq-10khz', 'freq-1khz'];
    for (var i = 0; i < 5; i++) {
        var el = document.getElementById(digits[i]);
        if (el) el.textContent = freqStr[i];
    }
}

function showFrequencyInput() {
    if (domElements.freqDisplay) domElements.freqDisplay.style.display = 'none';
    if (domElements.freqInput) {
        domElements.freqInput.style.display = 'block';
        domElements.freqInput.value = Math.floor(mobileState.currentFrequency / 1000);
        domElements.freqInput.focus();
    }
}

function hideFrequencyInput() {
    if (domElements.freqInput) {
        var val = parseInt(domElements.freqInput.value);
        if (!isNaN(val) && val >= 1000 && val <= 60000) {
            mobileState.currentFrequency = val * 1000;
            updateFrequencyDisplay();
            if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
                wsControlTRX.send('setFreq:' + mobileState.currentFrequency);
            }
        }
        domElements.freqInput.style.display = 'none';
    }
    if (domElements.freqDisplay) domElements.freqDisplay.style.display = 'flex';
}

////////////////////////////////////////////////////////////
// S-Meter 初始化
////////////////////////////////////////////////////////////
function initializeSMeter() {
    var canvas = domElements.sMeterCanvas;
    if (!canvas) return;
    
    var ctx = canvas.getContext('2d');
    drawSMeter(ctx, 0);
}

// S 表更新函数 - controls.js 的 drawRXSmeter() 会调用这个函数
function updateSMeter(level) {
    var canvas = domElements.sMeterCanvas;
    if (!canvas) return;
    
    var ctx = canvas.getContext('2d');
    var value = parseInt(level) || 0;
    drawSMeter(ctx, value);
    
    // 更新信号强度文字显示
    var signalText = document.querySelector('.signal-text');
    if (signalText) {
        var res = "S0";
        if (value > 9) {
            res = "S9+" + value;
        } else {
            res = "S" + value;
        }
        // 添加dB显示（使用 controls.js 中的 RIG_LEVEL_STRENGTH）
        if (typeof RIG_LEVEL_STRENGTH !== 'undefined' && RIG_LEVEL_STRENGTH[value] !== undefined) {
            res += " (" + RIG_LEVEL_STRENGTH[value] + "dB)";
        }
        signalText.textContent = res;
    }
    
    // 更新信号条显示
    updateSignalBars(value);
}

// 更新信号条显示
function updateSignalBars(level) {
    var bars = document.querySelectorAll('.signal-bar');
    if (!bars || bars.length === 0) return;
    
    var activeCount = Math.min(5, Math.ceil(level / 2));  // S0-S2=1条, S3-S4=2条, ... S9+=5条
    if (level > 9) activeCount = 5;
    
    bars.forEach(function(bar, index) {
        if (index < activeCount) {
            bar.classList.add('active');
        } else {
            bar.classList.remove('active');
        }
    });
}

function drawSMeter(ctx, level) {
    var width = ctx.canvas.width;
    var height = ctx.canvas.height;
    
    // 背景
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, width, height);
    
    // 刻度
    ctx.strokeStyle = '#666';
    ctx.lineWidth = 1;
    for (var i = 0; i <= 12; i++) {
        var x = 20 + (i / 12) * (width - 40);
        ctx.beginPath();
        ctx.moveTo(x, height - 20);
        ctx.lineTo(x, height - 10);
        ctx.stroke();
    }
    
    // 指针
    var pointerX = 20 + (level / 100) * (width - 40);
    ctx.strokeStyle = '#00ff00';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(pointerX, height - 5);
    ctx.lineTo(pointerX, height - 25);
    ctx.stroke();
}

////////////////////////////////////////////////////////////
// 菜单项设置
////////////////////////////////////////////////////////////
function setupMenuItems() {
    var menuItems = document.querySelectorAll('.menu-item');
    menuItems.forEach(function(item) {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            var action = this.getAttribute('data-action');
            handleMenuAction(action);
            closeMenu();
        });
    });
}

function handleMenuAction(action) {
    console.log('Menu action:', action);
    // 各菜单项的处理逻辑
    switch(action) {
        case 'bands':
            // 打开波段选择
            break;
        case 'modes':
            // 打开模式选择
            break;
        case 'settings':
            // 打开设置
            break;
        case 'audio':
            // 打开音频设置面板
            showAudioSettingsPanel();
            break;
        case 'txeq':
            // 打开 TX EQ 设置
            if (typeof showTX_EQ_Dialog === 'function') {
                showTX_EQ_Dialog();
            }
            break;
        default:
            break;
    }
}

////////////////////////////////////////////////////////////
// 音频设置面板 - 高品质模式
////////////////////////////////////////////////////////////
function showAudioSettingsPanel() {
    // 获取当前 AF 增益
    var afValue = 50;
    var cAfEl = document.getElementById('C_af');
    if (cAfEl && cAfEl.value) {
        afValue = Math.round(parseInt(cAfEl.value) / 10);
    }
    
    // 获取当前 MIC 增益
    var micValue = 150;  // 高品质模式默认 150%
    try {
        if (typeof loadUserAudioSetting === 'function') {
            var saved = loadUserAudioSetting('mobile_mic_gain', '150');
            if (saved) micValue = parseInt(saved);
        } else if (typeof getCookie === 'function') {
            var c = getCookie('mobile_mic_gain');
            if (c) micValue = parseInt(c);
        }
    } catch (e) {}
    
    // 升级旧的低增益值
    if (micValue <= 100) micValue = 150;
    
    // 静噪值
    var squelchEl = document.getElementById('SQUELCH');
    var sqlValue = squelchEl ? parseInt(squelchEl.value) : 0;
    
    let html = '<div class="modal-panel"><h3>🎵 高品质音频设置</h3>';
    html += '<p style="font-size:12px;color:#888;margin-bottom:15px;">TX: 48kHz PCM | RX: 16kHz PCM</p>';
    
    // AF 增益
    html += '<div class="setting-item">';
    html += '<label>AF 增益: <span id="af-value-display">' + afValue + '%</span></label>';
    html += '<input type="range" id="mobile-af-gain" min="0" max="100" value="' + afValue + '" oninput="setAFGain(this.value)">';
    html += '</div>';
    
    // MIC 增益（高品质模式默认 150%，最大 300%）
    html += '<div class="setting-item">';
    html += '<label>MIC 增益: <span id="mic-value-display">' + micValue + '%</span></label>';
    html += '<input type="range" id="mobile-mic-gain" min="0" max="300" value="' + micValue + '" oninput="setMicGain(this.value)">';
    html += '</div>';
    
    // 静噪
    html += '<div class="setting-item">';
    html += '<label>静噪: <span id="sql-value-display">' + sqlValue + '</span></label>';
    html += '<input type="range" id="mobile-squelch" min="0" max="100" value="' + sqlValue + '" oninput="setSquelch(this.value)">';
    html += '</div>';
    
    html += '<button class="close-panel-btn" onclick="closeModalPanel()">关闭</button></div>';
    showModalPanel(html);
}

function setAFGain(value) {
    var display = document.getElementById('af-value-display');
    if (display) display.textContent = value + '%';
    
    var cAfEl = document.getElementById('C_af');
    if (cAfEl) cAfEl.value = parseInt(value) * 10;
    
    if (typeof AudioRX_SetGAIN === 'function') {
        AudioRX_SetGAIN();
    }
    
    if (typeof saveUserAudioSetting === 'function') {
        saveUserAudioSetting('C_af', parseInt(value) * 10, 180);
    } else if (typeof setCookie === 'function') {
        setCookie('C_af', parseInt(value) * 10, 180);
    }
}

function setSquelch(value) {
    var display = document.getElementById('sql-value-display');
    if (display) display.textContent = value;
    
    var squelchEl = document.getElementById('SQUELCH');
    if (squelchEl) squelchEl.value = value;
}

// 简单模态面板显示
function showModalPanel(html) {
    var existing = document.getElementById('modal-panel-overlay');
    if (existing) existing.remove();
    
    var overlay = document.createElement('div');
    overlay.id = 'modal-panel-overlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:10000;display:flex;align-items:center;justify-content:center;';
    overlay.innerHTML = html;
    document.body.appendChild(overlay);
    
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) closeModalPanel();
    });
}

function closeModalPanel() {
    var overlay = document.getElementById('modal-panel-overlay');
    if (overlay) overlay.remove();
}

////////////////////////////////////////////////////////////
// 音频设置加载
////////////////////////////////////////////////////////////
function loadAudioSettingsFromCookies() {
    // 加载 AF 增益 - 高品质模式默认 100%
    var cAfEl = document.getElementById('C_af');
    var mainAfSlider = document.getElementById('main-af-gain');
    var mainAfValue = document.getElementById('main-af-value');
    
    if (cAfEl && mainAfSlider) {
        var vol = '';
        try {
            if (typeof loadUserAudioSetting === 'function') {
                vol = loadUserAudioSetting('C_af', '');
            } else if (typeof getCookie === 'function') {
                vol = getCookie('C_af');
            }
        } catch (e) {}
        
        // 高品质模式：默认使用 100% 增益
        // 只有用户明确设置过（Cookie 存在且值有效）才加载
        var defaultVol = 1000;  // 默认 100%
        if (vol && parseInt(vol) > 0) {
            var volNum = parseInt(vol);
            // 如果保存的值是旧的默认值 500（50%），升级到 1000（100%）
            if (volNum === 500) {
                volNum = 1000;
            }
            cAfEl.value = volNum;
            var afPercent = Math.round(volNum / 10);
            mainAfSlider.value = afPercent;
            if (mainAfValue) mainAfValue.textContent = afPercent + '%';
            console.log('🎵 AF 增益已加载: ' + afPercent + '%');
        } else {
            // 无 Cookie，使用默认值 100%
            cAfEl.value = defaultVol;
            mainAfSlider.value = 100;
            if (mainAfValue) mainAfValue.textContent = '100%';
            console.log('🎵 AF 增益使用默认值: 100%');
        }
    }
    
    // 加载 MIC 增益
    var micSlider = document.getElementById('mobile-mic-gain');
    var micValueDisplay = document.getElementById('mic-value-display');
    if (micSlider) {
        var micGain = '150';  // 高品质模式默认 150%
        try {
            if (typeof loadUserAudioSetting === 'function') {
                micGain = loadUserAudioSetting('mobile_mic_gain', '150');
            } else if (typeof getCookie === 'function') {
                var c = getCookie('mobile_mic_gain');
                if (c) micGain = c;
            }
        } catch (e) {}
        
        // 升级旧的低增益值（100 或更低）到 150%
        var micNum = parseInt(micGain);
        if (micNum <= 100) {
            micNum = 150;
            micGain = '150';
            console.log('🎤 MIC 增益已升级到 150%');
        }
        
        micSlider.value = micGain;
        if (micValueDisplay) micValueDisplay.textContent = micGain + '%';
        
        // 应用 MIC 增益
        setMicGain(micGain);
    }
}

function setMainAFGain(value) {
    var mainAfValue = document.getElementById('main-af-value');
    if (mainAfValue) mainAfValue.textContent = value + '%';
    
    var cAfEl = document.getElementById('C_af');
    if (cAfEl) cAfEl.value = parseInt(value) * 10;
    
    if (typeof AudioRX_SetGAIN === 'function') {
        AudioRX_SetGAIN();
    }
    
    if (typeof saveUserAudioSetting === 'function') {
        saveUserAudioSetting('C_af', parseInt(value) * 10, 180);
    } else if (typeof setCookie === 'function') {
        setCookie('C_af', parseInt(value) * 10, 180);
    }
}

////////////////////////////////////////////////////////////
// MIC 增益控制 - 高品质模式专用
////////////////////////////////////////////////////////////
function setMicGain(value) {
    // 更新显示
    var display = document.getElementById('mic-value-display');
    if (display) display.textContent = value + '%';
    
    // 直接设置 HQ_MediaHandler 的增益节点
    if (HQ_MediaHandler && HQ_MediaHandler.gain_node) {
        var gainValue = parseInt(value) / 100;
        HQ_MediaHandler.gain_node.gain.setValueAtTime(gainValue, HQ_MediaHandler.context.currentTime);
        console.log('🎤 HQ MIC 增益设置为:', gainValue);
    }
    
    // 也尝试调用标准方法（备用）
    if (typeof AudioTX_SetGAIN === 'function') {
        AudioTX_SetGAIN(parseInt(value) / 100);
    }
    
    // 保存设置
    if (typeof saveUserAudioSetting === 'function') {
        saveUserAudioSetting('mobile_mic_gain', value, 180);
    } else if (typeof setCookie === 'function') {
        setCookie('mobile_mic_gain', value, 180);
    }
}

////////////////////////////////////////////////////////////
// iOS Safari 音频初始化
////////////////////////////////////////////////////////////
function initAudioOnFirstTouch() {
    console.log('📱 iOS Safari 音频初始化（用户触摸后）');
    
    // 恢复所有 AudioContext
    if (typeof AudioRX_context !== 'undefined' && AudioRX_context && AudioRX_context.state === 'suspended') {
        AudioRX_context.resume();
    }
    if (HQ_MediaHandler && HQ_MediaHandler.context && HQ_MediaHandler.context.state === 'suspended') {
        HQ_MediaHandler.context.resume();
    }
}

////////////////////////////////////////////////////////////
// 状态更新函数（供 controls.js 回调）
////////////////////////////////////////////////////////////
function updateConnectionStatus(connected) {
    mobileState.isConnected = connected;
    
    if (domElements.statusCtrl) {
        domElements.statusCtrl.classList.toggle('connected', connected);
    }
    
    if (connected) {
        requestWakeLock();
    } else {
        releaseWakeLock();
    }
}

// showTRXfreq 函数（兼容 5 位 kHz 格式）
function showTRXfreq(freq) {
    var freqNum = parseInt(freq);
    if (isNaN(freqNum)) return;
    
    // 支持 5 位 kHz 格式
    if (freqNum >= 1000 && freqNum <= 60000) {
        mobileState.currentFrequency = freqNum * 1000;
    } else {
        mobileState.currentFrequency = freqNum;
    }
    
    updateFrequencyDisplay();
}

console.log('✅ mobile_high.js 加载完成 - 高品质 48kHz TX 模式');

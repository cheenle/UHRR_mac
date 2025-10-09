// PAD专用触摸屏优化JavaScript

// 全局变量
let poweron = false;
let currentFreq = 14000000; // 默认20米波段
let currentMode = 'USB';
let txActive = false;
let wsControlTRX = null;
let wsAudioRX = null;
let wsAudioTX = null;
let AudioRX_context = null;
let AudioRX_analyser = null;
let AudioRX_gain_node = null;
let AudioRX_source_node = null;
let spectrumCanvas = null;
let spectrumCtx = null;
let muteRX = false;
let volumeRX = 0.5;
let isRecording = false;
let AudioRX_audiobuffer = [];
let AudioRX_sampleRate = 16000; // 参考原始代码
let AudioTX_analyser = null; // TX音频分析器
let Audio_analyser = null; // 当前音频分析器

// 音量表引用 - 参考原始代码
let RXinstantMeter = null;
let TXinstantMeter = null;

// 触摸状态跟踪
let touchStates = {
    txButton: false,
    freqButtons: {},
    modeButtons: {},
    bandButtons: {},
    filterButtons: {}
};

// 页面加载完成后初始化
function padload() {
    console.log('PAD界面初始化开始');
    
    // 初始化DOM元素
    initDOMElements();
    
    // 初始化触摸事件
    initTouchEvents();
    
    // 初始化音频控制
    initAudioControls();
    
    // 初始化频谱显示
    initSpectrumDisplay();
    
    // 检查呼号
    checkCallsign();
    
    // 注意：移除自动连接，改为用户点击电源按钮时连接
    console.log('PAD界面初始化完成，等待用户点击电源按钮');
}

// 初始化DOM元素
function initDOMElements() {
    spectrumCanvas = document.getElementById('pad-spectrum-canvas');
    spectrumCtx = spectrumCanvas.getContext('2d');

    // 音量表引用 - 参考原始代码
    RXinstantMeter = document.querySelector('#pad-rx-meter');
    TXinstantMeter = document.querySelector('#pad-tx-meter');

    // 更新频率显示
    updateFrequencyDisplay();

    // 更新模式显示
    updateModeDisplay();
}

// 初始化触摸事件
function initTouchEvents() {
    // TX按钮触摸事件
    initTXButtonTouch();
    
    // 频率按钮触摸事件
    initFreqButtonsTouch();
    
    // 模式按钮触摸事件
    initModeButtonsTouch();
    
    // 波段按钮触摸事件
    initBandButtonsTouch();
    
    // 滤波器按钮触摸事件
    initFilterButtonsTouch();
    
    // 频谱控制按钮
    initSpectrumControls();
    
    // 频率输入功能
    initFrequencyInput();
}

// TX按钮触摸事件
function initTXButtonTouch() {
    const txButton = document.getElementById('pad-tx-button');
    const txLockCheckbox = document.getElementById('pad-tx-lock');
    let touchStartTime = 0;
    let touchActive = false;
    let txLocked = false;
    
    // 触摸开始
    txButton.addEventListener('touchstart', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        touchActive = true;
        touchStartTime = Date.now();
        
        // 检查TX Lock状态
        txLocked = txLockCheckbox.checked;
        
        // 立即视觉反馈
        this.classList.add('active');
        
        // 立即执行TX开启
        if (poweron) {
            startTX();
        }
        
        console.log('TX触摸开始', txLocked ? '(锁定模式)' : '(按住模式)');
        
    }, {passive: false, capture: true});
    
    // 触摸结束
    txButton.addEventListener('touchend', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        touchActive = false;
        
        // 如果不是锁定模式，则停止TX
        if (!txLocked) {
            // 立即视觉反馈
            this.classList.remove('active');
            
            // 立即执行TX关闭
            if (poweron) {
                stopTX();
            }
        }
        
        console.log('TX触摸结束', txLocked ? '(保持锁定)' : '(释放)');
        
    }, {passive: false, capture: true});
    
    // 触摸取消
    txButton.addEventListener('touchcancel', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        touchActive = false;
        this.classList.remove('active');
        
        if (poweron) {
            stopTX();
        }
        
        console.log('TX触摸取消');
        
    }, {passive: false, capture: true});
    
    // 触摸移动检测
    txButton.addEventListener('touchmove', function(e) {
        if (!touchActive) return;
        
        const touch = e.touches[0];
        const rect = this.getBoundingClientRect();
        const x = touch.clientX - rect.left;
        const y = touch.clientY - rect.top;
        
        // 如果触摸点移出按钮区域，取消操作
        if (x < 0 || x > rect.width || y < 0 || y > rect.height) {
            touchActive = false;
            this.classList.remove('active');
            if (poweron) {
                stopTX();
            }
            console.log('TX触摸移出区域');
        }
    }, {passive: false});
    
    // TX Lock复选框事件
    txLockCheckbox.addEventListener('change', function() {
        txLocked = this.checked;
        console.log('TX Lock状态:', txLocked ? '开启' : '关闭');
        
        // 如果取消锁定且当前在TX状态，则停止TX
        if (!txLocked && txActive) {
            stopTX();
            txButton.classList.remove('active');
        }
    });
}

// 频率按钮触摸事件
function initFreqButtonsTouch() {
    const freqButtons = document.querySelectorAll('.freq-button');
    
    freqButtons.forEach(button => {
        button.addEventListener('touchstart', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const value = parseInt(this.dataset.value);
            adjustFrequency(value);
            
            // 视觉反馈
            this.classList.add('selected');
            setTimeout(() => {
                this.classList.remove('selected');
            }, 200);
            
            console.log('频率调整:', value);
            
        }, {passive: false, capture: true});
    });
}

// 模式按钮触摸事件
function initModeButtonsTouch() {
    const modeButtons = document.querySelectorAll('.mode-button');
    
    modeButtons.forEach(button => {
        button.addEventListener('touchstart', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const mode = this.dataset.mode;
            setMode(mode);
            
            // 更新选中状态
            modeButtons.forEach(btn => btn.classList.remove('selected'));
            this.classList.add('selected');
            
            console.log('模式切换:', mode);
            
        }, {passive: false, capture: true});
    });
}

// 波段按钮触摸事件
function initBandButtonsTouch() {
    const bandButtons = document.querySelectorAll('.band-button');
    
    bandButtons.forEach(button => {
        button.addEventListener('touchstart', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const freq = parseInt(this.dataset.freq);
            setFrequency(freq);
            
            // 更新选中状态
            bandButtons.forEach(btn => btn.classList.remove('selected'));
            this.classList.add('selected');
            
            console.log('波段切换:', freq);
            
        }, {passive: false, capture: true});
    });
}

// 滤波器按钮触摸事件
function initFilterButtonsTouch() {
    const filterButtons = document.querySelectorAll('.filter-button');
    
    filterButtons.forEach(button => {
        button.addEventListener('touchstart', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const filter = this.dataset.filter;
            setAudioFilter(filter);
            
            // 更新选中状态
            filterButtons.forEach(btn => btn.classList.remove('selected'));
            this.classList.add('selected');
            
            console.log('滤波器切换:', filter);
            
        }, {passive: false, capture: true});
    });
}

// 频谱控制按钮
function initSpectrumControls() {
    document.getElementById('pad-spectrum-scale-up').addEventListener('touchstart', function(e) {
        e.preventDefault();
        adjustSpectrumScale(1.2);
    }, {passive: false});
    
    document.getElementById('pad-spectrum-scale-down').addEventListener('touchstart', function(e) {
        e.preventDefault();
        adjustSpectrumScale(0.8);
    }, {passive: false});
    
    document.getElementById('pad-spectrum-reset').addEventListener('touchstart', function(e) {
        e.preventDefault();
        resetSpectrumScale();
    }, {passive: false});
}

// 频率输入功能
function initFrequencyInput() {
    const freqInput = document.getElementById('pad-freq-input');
    const freqSetButton = document.getElementById('pad-freq-set');
    
    // 设置按钮点击事件
    freqSetButton.addEventListener('touchstart', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const inputValue = freqInput.value.trim();
        if (inputValue) {
            const freq = parseInt(inputValue);
            if (!isNaN(freq) && freq >= 0 && freq <= 300000000) {
                setFrequency(freq);
                freqInput.value = ''; // 清空输入框
                console.log('手动设置频率:', freq, 'Hz');
            } else {
                alert('请输入有效的频率值 (0-300000000 Hz)');
            }
        }
        
    }, {passive: false, capture: true});
    
    // 输入框回车事件
    freqInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            const inputValue = this.value.trim();
            if (inputValue) {
                const freq = parseInt(inputValue);
                if (!isNaN(freq) && freq >= 0 && freq <= 300000000) {
                    setFrequency(freq);
                    this.value = ''; // 清空输入框
                    console.log('手动设置频率:', freq, 'Hz');
                } else {
                    alert('请输入有效的频率值 (0-300000000 Hz)');
                }
            }
        }
    });
    
    // 输入框聚焦时选中所有文本
    freqInput.addEventListener('focus', function() {
        this.select();
    });
}

// 初始化音频控制
function initAudioControls() {
    // AF GAIN
    const afGain = document.getElementById('pad-af-gain');
    afGain.addEventListener('input', function() {
        const value = this.value;
        document.querySelector('#pad-audio-section .audio-control:nth-child(1) .audio-value').textContent = value;
        setAudioGain('af', value);
    });
    
    // RX VOL
    const rxVol = document.getElementById('pad-rx-vol');
    rxVol.addEventListener('input', function() {
        const value = this.value;
        document.querySelector('#pad-audio-section .audio-control:nth-child(2) .audio-value').textContent = value;
        setAudioGain('rx', value);
    });
    
    // MIC GAIN
    const micGain = document.getElementById('pad-mic-gain');
    micGain.addEventListener('input', function() {
        const value = this.value;
        document.querySelector('#pad-audio-section .audio-control:nth-child(3) .audio-value').textContent = value;
        setAudioGain('mic', value);
    });
    
    // SQUELCH
    const squelch = document.getElementById('pad-squelch');
    squelch.addEventListener('input', function() {
        const value = this.value;
        document.querySelector('#pad-audio-section .audio-control:nth-child(4) .audio-value').textContent = value;
        setSquelch(value);
    });
}

// 初始化频谱显示
function initSpectrumDisplay() {
    if (!spectrumCanvas || !spectrumCtx) return;
    
    // 开始绘制频谱
    drawSpectrum();
}

// 开始连接
function startConnection() {
    showLoading(true);
    
    // 连接控制WebSocket
    connectControlWebSocket();
    
    // 连接音频WebSocket
    connectAudioWebSockets();
}

// 连接控制WebSocket
function connectControlWebSocket() {
    try {
        // 使用ws://协议（避免SSL证书问题）
        const protocol = 'ws:';
        const wsUrl = protocol + '//' + window.location.host + '/WSCTRX';

        console.log('正在连接到控制WebSocket:', wsUrl);
        wsControlTRX = new WebSocket(wsUrl);

        wsControlTRX.onopen = function() {
            console.log('控制WebSocket连接成功');
            updateConnectionStatus('pad-ws-ctrl', 'connected');

            // 请求当前状态 - 参考原始代码格式，添加延迟避免服务器过载
            setTimeout(() => {
                try {
                    wsControlTRX.send('getFreq:');  // 添加冒号
                    wsControlTRX.send('getMode:');  // 添加冒号
                } catch (error) {
                    console.error('发送初始消息失败:', error);
                }
            }, 100);
        };
        
        wsControlTRX.onmessage = function(msg) {
            handleControlMessage(msg.data);
        };
        
        wsControlTRX.onclose = function(event) {
            console.log('控制WebSocket连接关闭 (code:', event.code, ', reason:', event.reason + ')');
            updateConnectionStatus('pad-ws-ctrl', 'disconnected');

            // 如果不是正常关闭，5秒后重试
            if (event.code !== 1000) {
                console.log('连接非正常关闭，5秒后重试...');
                setTimeout(() => {
                    connectControlWebSocket();
                }, 5000);
            }
        };

        wsControlTRX.onerror = function(error) {
            console.error('控制WebSocket错误:', error);
            updateConnectionStatus('pad-ws-ctrl', 'disconnected');
        };
        
    } catch (error) {
        console.error('创建控制WebSocket失败:', error);
        updateConnectionStatus('pad-ws-ctrl', 'disconnected');
    }
}

// 连接音频WebSocket
function connectAudioWebSockets() {
    // 使用ws://协议（避免SSL证书问题）
    const protocol = 'ws:';

    // RX音频
    try {
        const wsUrl = protocol + '//' + window.location.host + '/WSaudioRX';
        console.log('正在连接到音频RX WebSocket:', wsUrl);
        wsAudioRX = new WebSocket(wsUrl);
        wsAudioRX.binaryType = 'arraybuffer';
        
        wsAudioRX.onopen = function() {
            console.log('音频RX WebSocket连接成功');
            updateConnectionStatus('pad-ws-rx', 'connected');
            initAudioContext();
        };
        
        wsAudioRX.onmessage = function(msg) {
            handleAudioRXData(msg.data);
        };
        
        wsAudioRX.onclose = function() {
            console.log('音频RX WebSocket连接关闭');
            updateConnectionStatus('pad-ws-rx', 'disconnected');
        };
        
        wsAudioRX.onerror = function(error) {
            console.error('音频RX WebSocket错误:', error);
            updateConnectionStatus('pad-ws-rx', 'disconnected');
        };
        
    } catch (error) {
        console.error('创建音频RX WebSocket失败:', error);
        updateConnectionStatus('pad-ws-rx', 'disconnected');
    }
    
    // TX音频
    try {
        const wsUrl = protocol + '//' + window.location.host + '/WSaudioTX';  // 修正TX音频WebSocket URL
        console.log('正在连接到音频TX WebSocket:', wsUrl);
        wsAudioTX = new WebSocket(wsUrl);
        wsAudioTX.binaryType = 'arraybuffer';
        
        wsAudioTX.onopen = function() {
            console.log('音频TX WebSocket连接成功');
            updateConnectionStatus('pad-ws-tx', 'connected');
        };
        
        wsAudioTX.onclose = function() {
            console.log('音频TX WebSocket连接关闭');
            updateConnectionStatus('pad-ws-tx', 'disconnected');
        };
        
        wsAudioTX.onerror = function(error) {
            console.error('音频TX WebSocket错误:', error);
            updateConnectionStatus('pad-ws-tx', 'disconnected');
        };
        
    } catch (error) {
        console.error('创建音频TX WebSocket失败:', error);
        updateConnectionStatus('pad-ws-tx', 'disconnected');
    }
}

// 初始化音频上下文
function initAudioContext() {
    try {
        AudioRX_context = new (window.AudioContext || window.webkitAudioContext)({
            latencyHint: 'interactive',
            sampleRate: 8000
        });
        
        // 创建音频节点 - 参考原始代码的完整链路
        AudioRX_gain_node = AudioRX_context.createGain();
        AudioRX_biquadFilter_node = AudioRX_context.createBiquadFilter();
        AudioRX_analyser = AudioRX_context.createAnalyser();
        AudioRX_source_node = AudioRX_context.createScriptProcessor(256, 1, 1);
        
        // 设置分析器
        AudioRX_analyser.fftSize = 1024;
        AudioRX_analyser.smoothingTimeConstant = 0.8;
        
        // 设置音频处理 - 参考原始代码
        AudioRX_source_node.onaudioprocess = function(event) {
            var synth_buff = event.outputBuffer.getChannelData(0); // 使用outputBuffer
            let le = Boolean(AudioRX_audiobuffer.length);
            if(le){
                for (var i = 0, buff_size = synth_buff.length; i < buff_size; i++) {
                    synth_buff[i] = AudioRX_audiobuffer[0][i];
                }
                if(le){AudioRX_audiobuffer.shift();}
            }
        };
        
        // 连接音频节点 - 参考原始代码的完整链路
        AudioRX_source_node.connect(AudioRX_biquadFilter_node);
        AudioRX_biquadFilter_node.connect(AudioRX_gain_node);
        AudioRX_gain_node.connect(AudioRX_analyser);
        AudioRX_gain_node.connect(AudioRX_context.destination);
        
        // 启动音频源节点
        AudioRX_source_node.start(0);
        
        // 设置滤波器参数 - 参考原始代码
        AudioRX_biquadFilter_node.type = "lowshelf";
        AudioRX_biquadFilter_node.frequency.setValueAtTime(22000, AudioRX_context.currentTime);
        AudioRX_biquadFilter_node.gain.setValueAtTime(0, AudioRX_context.currentTime);

        // 设置增益
        AudioRX_gain_node.gain.setValueAtTime(volumeRX, AudioRX_context.currentTime);

        console.log('音频上下文初始化成功');
        updateConnectionStatus('pad-audio-status', 'connected');

        // 启动频谱和音量显示 - 参考原始代码
        drawBF();
        drawRXvol();

    } catch (error) {
        console.error('音频上下文初始化失败:', error);
        updateConnectionStatus('pad-audio-status', 'disconnected');
    }
}

// 频谱显示函数 - 参考原始代码
function drawBF(){
    if(muteRX){
        // TX模式下，如果有TX分析器则使用，否则保持RX
        if(AudioTX_analyser){
            Audio_analyser = AudioTX_analyser;
        } else {
            Audio_analyser = AudioRX_analyser;
        }
    } else {
        Audio_analyser = AudioRX_analyser;
    }
    drawRXSPC(Audio_analyser);
    drawRXFFT(Audio_analyser);
    setTimeout(function(){ drawBF(); }, 200);
}

// 音量显示函数 - 参考原始代码
function drawRXvol(){
    if (!AudioRX_analyser) return;

    var arraySPC = new Float32Array(AudioRX_analyser.fftSize);
    AudioRX_analyser.getFloatTimeDomainData(arraySPC);

    // 更新音量指示器 - 参考原始代码
    if (RXinstantMeter) {
        const volumeLevel = Math.max.apply(null, arraySPC) * 100;
        RXinstantMeter.value = volumeLevel;

        // 更新数值显示
        const rxValue = document.getElementById('pad-rx-value');
        if (rxValue) {
            rxValue.textContent = Math.round(volumeLevel) + '%';
        }

        // 如果音量过高，闪烁警告
        if (volumeLevel > RXinstantMeter.high) {
            blikcritik("pad-rx-meters");
        }
    }

    setTimeout(function(){ drawRXvol(); }, 300);
}

// 频谱绘制函数
function drawRXFFT(analyser){
    if (!analyser || !spectrumCanvas || !spectrumCtx) return;

    analyser.fftSize = spectrumCanvas.width;
    var arrayFFT = new Float32Array(analyser.frequencyBinCount);
    analyser.getFloatFrequencyData(arrayFFT);

    // 绘制频谱
    spectrumCtx.clearRect(0, 0, spectrumCanvas.width, spectrumCanvas.height);
    spectrumCtx.fillStyle = '#000';
    spectrumCtx.fillRect(0, 0, spectrumCanvas.width, spectrumCanvas.height);

    spectrumCtx.strokeStyle = '#00ff00';
    spectrumCtx.lineWidth = 2;
    spectrumCtx.beginPath();

    for (let i = 0; i < arrayFFT.length; i++) {
        const x = i;
        const y = spectrumCanvas.height - ((arrayFFT[i] + 140) / 140) * spectrumCanvas.height;

        if (i === 0) {
            spectrumCtx.moveTo(x, y);
        } else {
            spectrumCtx.lineTo(x, y);
        }
    }
    spectrumCtx.stroke();
}

// 频谱范围绘制函数
function drawRXSPC(analyser){
    var arraySPC = new Float32Array(analyser.fftSize);
    analyser.getFloatTimeDomainData(arraySPC);

    // 更新音量指示器（如果有的话）
    const maxValue = Math.max.apply(null, arraySPC);
    console.log('音频信号峰值:', maxValue);
}


// AudioTX启动函数 - 参考原始代码
function AudioTX_start() {
    document.getElementById("pad-ws-tx").innerHTML = '<img src="img/critsgrey.png">wsTX';

    try {
        // 使用ws://协议（避免SSL证书问题）
        const protocol = 'ws:';
        const wsUrl = protocol + '//' + window.location.host + '/WSaudioTX';
        console.log('AudioTX重新连接到:', wsUrl);
        wsAudioTX = new WebSocket(wsUrl);
        wsAudioTX.onopen = function() {
            document.getElementById("pad-ws-tx").innerHTML = '<img src="img/critsgreen.png">wsTX';
            updateConnectionStatus('pad-ws-tx', 'connected');
        };
        wsAudioTX.onerror = function(error) {
            document.getElementById("pad-ws-tx").innerHTML = '<img src="img/critsred.png">wsTX';
            updateConnectionStatus('pad-ws-tx', 'disconnected');
        };
        wsAudioTX.onclose = function() {
            document.getElementById("pad-ws-tx").innerHTML = '<img src="img/critsred.png">wsTX';
            updateConnectionStatus('pad-ws-tx', 'disconnected');
        };

        isRecording = false;
        console.log('AudioTX启动');

    } catch (error) {
        console.error('AudioTX启动失败:', error);
        updateConnectionStatus('pad-ws-tx', 'disconnected');
    }
}

// 开始录音
function startRecord() {
    if (isRecording) return;

    isRecording = true;

    // 更新TX音量表显示
    if (TXinstantMeter) {
        TXinstantMeter.value = 50; // 模拟中等音量
    }
    const txValue = document.getElementById('pad-tx-value');
    if (txValue) {
        txValue.textContent = '50%';
    }

    console.log('开始录音');
}

// 停止录音
function stopRecord() {
    if (!isRecording) return;

    isRecording = false;

    // 重置TX音量表
    if (TXinstantMeter) {
        TXinstantMeter.value = 0;
    }
    const txValue = document.getElementById('pad-tx-value');
    if (txValue) {
        txValue.textContent = '0%';
    }

    console.log('停止录音');
}

// 闪烁警告函数 - 参考原始代码
function blikcritik(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.style.backgroundColor = '#ff4444';
        setTimeout(() => {
            element.style.backgroundColor = '';
        }, 200);
    }
}

// 处理控制消息
function handleControlMessage(data) {
    const parts = data.split(':');
    const command = parts[0];
    const value = parts[1];
    
    switch (command) {
        case 'getFreq':
            currentFreq = parseInt(value);
            updateFrequencyDisplay();
            break;
        case 'getMode':
            currentMode = value;
            updateModeDisplay();
            break;
        case 'getSignalLevel':
            updateSMeter(parseInt(value));
            break;
        case 'PONG':
            updateLatency();
            break;
    }
}

// 处理RX音频数据
function handleAudioRXData(data) {
    if (!AudioRX_context) return;
    
    // 将音频数据添加到缓冲区 - 参考原始代码
    AudioRX_audiobuffer.push(new Float32Array(data));
    
    // 限制缓冲区大小，防止内存溢出
    if (AudioRX_audiobuffer.length > 20) {
        AudioRX_audiobuffer.shift();
    }
    
    // 更新频谱显示
    updateSpectrum();
}

// 更新频率显示
function updateFrequencyDisplay() {
    const freqDisplay = document.getElementById('pad-freq-display');
    const freqStr = currentFreq.toString().padStart(9, '0');
    freqDisplay.textContent = freqStr.substring(0, 3) + '.' + 
                            freqStr.substring(3, 6) + '.' + 
                            freqStr.substring(6, 9);
}

// 更新模式显示
function updateModeDisplay() {
    const modeButtons = document.querySelectorAll('.mode-button');
    modeButtons.forEach(button => {
        button.classList.remove('selected');
        if (button.dataset.mode === currentMode) {
            button.classList.add('selected');
        }
    });
}

// 更新S表
function updateSMeter(level) {
    const smeterFill = document.getElementById('pad-smeter-fill');
    const smeterValue = document.getElementById('pad-smeter-value');
    
    const percentage = Math.min((level / 60) * 100, 100);
    smeterFill.style.width = percentage + '%';
    
    if (level < 9) {
        smeterValue.textContent = 'S' + level;
    } else {
        smeterValue.textContent = 'S9+' + (level - 9) + 'dB';
    }
}

// 更新连接状态
function updateConnectionStatus(elementId, status) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    element.classList.remove('connected', 'disconnected', 'connecting');
    element.classList.add(status);
    
    // 检查所有连接状态
    checkAllConnections();
}

// 检查所有连接
function checkAllConnections() {
    const ctrlStatus = document.getElementById('pad-ws-ctrl').classList.contains('connected');
    const rxStatus = document.getElementById('pad-ws-rx').classList.contains('connected');
    const txStatus = document.getElementById('pad-ws-tx').classList.contains('connected');

    if (ctrlStatus && rxStatus && txStatus) {
        poweron = true;
        showLoading(false);
        updateConnectionStatus('pad-power-status', 'connected');

        // 更新电源按钮为开启状态
        const powerButton = document.getElementById('pad-button-power');
        if (powerButton && powerButton.src.includes('poweroff.png')) {
            powerButton.src = 'img/poweron.png';
        }
    } else {
        poweron = false;
        updateConnectionStatus('pad-power-status', 'disconnected');
    }
}

// 电源开关函数 - 参考原始代码
function powertogle() {
    const powerButton = document.getElementById('pad-button-power');

    if (powerButton.src.includes('poweroff.png')) {
        // 启动系统
        powerButton.src = 'img/poweron.png';
        showLoading(true);

        // 启动各个子系统
        AudioRX_start();
        AudioTX_start();
        ControlTRX_start();
        checklatency();

        poweron = true;
        console.log('系统启动');

    } else {
        // 关闭系统
        powerButton.src = 'img/poweroff.png';

        // 停止各个子系统
        if (wsAudioRX) wsAudioRX.close();
        if (wsAudioTX) wsAudioTX.close();
        if (wsControlTRX) wsControlTRX.close();

        // 停止音频上下文
        if (AudioRX_context) {
            AudioRX_context.close();
            AudioRX_context = null;
        }

        poweron = false;
        showLoading(false);
        console.log('系统关闭');
    }
}

// 显示/隐藏加载遮罩
function showLoading(show) {
    const overlay = document.getElementById('pad-loading-overlay');
    overlay.style.display = show ? 'flex' : 'none';
}

// 检查呼号
function checkCallsign() {
    const callsign = getCookie('callsign');
    const callsignDisplay = document.getElementById('pad-callsign');
    
    if (callsign) {
        callsignDisplay.textContent = callsign;
    } else {
        const inputCallsign = prompt('请输入您的呼号:');
        if (inputCallsign) {
            setCookie('callsign', inputCallsign, 180);
            callsignDisplay.textContent = inputCallsign;
        }
    }
}

// 调整频率
function adjustFrequency(value) {
    currentFreq += value;
    if (currentFreq < 0) currentFreq = 0;
    if (currentFreq > 300000000) currentFreq = 300000000;
    
    updateFrequencyDisplay();
    sendFrequency();
    
    console.log('频率调整:', currentFreq, 'Hz');
}

// 设置频率
function setFrequency(freq) {
    currentFreq = freq;
    updateFrequencyDisplay();
    sendFrequency();
}

// 发送频率
function sendFrequency() {
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send('setFreq:' + currentFreq);
    }
}

// 设置模式
function setMode(mode) {
    currentMode = mode;
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send('setMode:' + mode);
    }
}

// 开始TX
function startTX() {
    if (!poweron || txActive) return;
    
    txActive = true;
    document.getElementById('pad-tx-button').classList.add('active');
    
    // 静音RX音频 - 参考原始代码
    muteRX = true;
    if (AudioRX_gain_node) {
        AudioRX_gain_node.gain.setValueAtTime(0, AudioRX_context.currentTime);
    }
    
    // 发送PTT命令
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send('setPTT:true');
    }
    
    // 开始录音
    if (wsAudioTX && wsAudioTX.readyState === WebSocket.OPEN) {
        startRecord();
    }
    
    console.log('TX开始');
}

// 停止TX
function stopTX() {
    if (!poweron || !txActive) return;
    
    txActive = false;
    document.getElementById('pad-tx-button').classList.remove('active');
    
    // 恢复RX音频 - 参考原始代码
    muteRX = false;
    if (AudioRX_gain_node) {
        AudioRX_gain_node.gain.setValueAtTime(volumeRX, AudioRX_context.currentTime);
    }
    
    // 发送PTT命令
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send('setPTT:false');
    }
    
    // 停止录音
    stopRecord();
    
    console.log('TX停止');
}

// 设置音频增益
function setAudioGain(type, value) {
    const gainValue = value / 100; // 转换为0-1范围
    
    switch (type) {
        case 'af':
            volumeRX = gainValue;
            if (AudioRX_gain_node && !muteRX) {
                AudioRX_gain_node.gain.setValueAtTime(gainValue, AudioRX_context.currentTime);
            }
            break;
        case 'rx':
            // RX音量控制
            if (AudioRX_gain_node && !muteRX) {
                AudioRX_gain_node.gain.setValueAtTime(gainValue, AudioRX_context.currentTime);
            }
            break;
        case 'mic':
            // MIC增益控制
            console.log('设置MIC增益:', value);
            break;
    }
    
    console.log('设置音频增益:', type, value, '->', gainValue);
}

// 设置静噪
function setSquelch(value) {
    // 这里应该发送静噪设置到服务器
    console.log('设置静噪:', value);
}

// 设置音频滤波器
function setAudioFilter(filter) {
    // 这里应该发送滤波器设置到服务器
    console.log('设置滤波器:', filter);
}

// 调整频谱缩放
function adjustSpectrumScale(factor) {
    // 这里应该调整频谱显示缩放
    console.log('调整频谱缩放:', factor);
}

// 重置频谱缩放
function resetSpectrumScale() {
    // 这里应该重置频谱显示缩放
    console.log('重置频谱缩放');
}

// 更新频谱
function updateSpectrum() {
    if (!AudioRX_analyser) return;
    
    const arrayFFT = new Float32Array(AudioRX_analyser.frequencyBinCount);
    AudioRX_analyser.getFloatFrequencyData(arrayFFT);
    
    // 绘制频谱
    drawSpectrum(arrayFFT);
}

// 绘制频谱
function drawSpectrum(fftData) {
    if (!spectrumCanvas || !spectrumCtx) return;
    
    // 清空画布
    spectrumCtx.clearRect(0, 0, spectrumCanvas.width, spectrumCanvas.height);
    
    // 绘制背景
    spectrumCtx.fillStyle = '#000';
    spectrumCtx.fillRect(0, 0, spectrumCanvas.width, spectrumCanvas.height);
    
    // 绘制网格
    spectrumCtx.strokeStyle = '#333';
    spectrumCtx.lineWidth = 1;
    for (let i = 0; i <= 10; i++) {
        const x = (spectrumCanvas.width / 10) * i;
        spectrumCtx.beginPath();
        spectrumCtx.moveTo(x, 0);
        spectrumCtx.lineTo(x, spectrumCanvas.height);
        spectrumCtx.stroke();
    }
    
    // 绘制频谱数据
    if (fftData && fftData.length > 0) {
        spectrumCtx.strokeStyle = '#00ff00';
        spectrumCtx.lineWidth = 2;
        spectrumCtx.beginPath();
        
        const barWidth = spectrumCanvas.width / fftData.length;
        
        for (let i = 0; i < fftData.length; i++) {
            const x = i * barWidth;
            const y = spectrumCanvas.height - ((fftData[i] + 140) / 140) * spectrumCanvas.height;
            
            if (i === 0) {
                spectrumCtx.moveTo(x, y);
            } else {
                spectrumCtx.lineTo(x, y);
            }
        }
        spectrumCtx.stroke();
    }
    
    // 继续绘制
    requestAnimationFrame(() => updateSpectrum());
}

// 延迟检查函数 - 参考原始代码
let startTime = 0;
let latency = 0;

function checklatency() {
    setTimeout(function () {
        startTime = Date.now();
        if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
            wsControlTRX.send("PING:");
        }
        if(poweron === true){
            checklatency();
        }
    }, 5000);
}

function showlatency(){
    latency = Date.now() - startTime;
    document.getElementById("pad-latency").textContent = 'latency: ' + latency + 'ms';
    console.log('延迟:', latency + 'ms');
}

// 更新延迟显示
function updateLatency() {
    document.getElementById('pad-latency').textContent = 'latency: ' + latency + 'ms';
}

// Cookie操作函数
function setCookie(name, value, days) {
    const expires = new Date();
    expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
    document.cookie = name + '=' + value + ';expires=' + expires.toUTCString() + ';path=/';
}

function getCookie(name) {
    const nameEQ = name + '=';
    const ca = document.cookie.split(';');
    for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) === ' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
}

// 页面可见性变化处理
document.addEventListener('visibilitychange', function() {
    if (document.hidden && txActive) {
        stopTX();
    }
});

// 页面卸载处理
window.addEventListener('beforeunload', function() {
    if (txActive) {
        stopTX();
    }
});

// 启动控制WebSocket - 参考原始代码
function ControlTRX_start() {
    connectControlWebSocket();
}

// 启动音频RX - 参考原始代码
function AudioRX_start() {
    connectAudioWebSockets();
}

// 启动音频TX - 参考原始代码  
function AudioTX_start() {
    // AudioTX_start已在connectAudioWebSockets中处理
    console.log('AudioTX_start调用');
}

// 检查延迟函数 - 参考原始代码
function checklatency() {
    console.log('延迟检查已启动');
    // 这里可以添加实际的延迟检查逻辑
}

// Modern Mobile Interface JavaScript for iPhone 15 and modern browsers
// 完全兼容 controls.js 的实现，确保与桌面版一致的行为
// 
// 重要：此文件依赖 controls.js 先加载
// 所有核心功能由 controls.js 提供，此文件仅处理移动端特定的 UI 逻辑

////////////////////////////////////////////////////////////
// 移动端检测 - 使用 controls.js 的 IS_MOBILE 变量
////////////////////////////////////////////////////////////

// controls.js 使用 const IS_MOBILE 声明，我们不能再声明
// 直接使用 controls.js 中已定义的 IS_MOBILE
// 如果需要本地判断，使用不同的变量名
const IS_MOBILE_LOCAL = typeof IS_MOBILE !== 'undefined' ? IS_MOBILE : /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

var audioContextInitialized = false;

////////////////////////////////////////////////////////////
// 移动端特定状态（不影响 controls.js 的全局变量）
////////////////////////////////////////////////////////////

// 移动端 UI 状态
var mobileState = {
    isConnected: false,
    currentFrequency: 7053000,
    currentMode: 'USB',
    currentVFO: 'VFO-A',
    isTransmitting: false,
    tuneStep: 100  // 默认步进 100Hz
};

// PTT 触摸状态由 tx_button_optimized.js 管理

////////////////////////////////////////////////////////////
// DOM 元素引用
////////////////////////////////////////////////////////////
const domElements = {
    menuToggle: null,
    menuClose: null,
    menuOverlay: null,
    mainMenu: null,
    pttButton: null,
    powerButton: null,
    freqDisplay: null,
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
// 初始化
////////////////////////////////////////////////////////////

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Mobile Modern 界面初始化...');
    
    initializeElements();
    setupEventListeners();
    initializeSMeter();
    updateFrequencyDisplay();
    setupMenuItems();
    loadAudioSettingsFromCookies();
    
    // iOS Safari 需要用户交互才能初始化音频
    document.addEventListener('touchstart', initAudioOnFirstTouch, { once: true });
    document.addEventListener('mousedown', initAudioOnFirstTouch, { once: true });
    
    console.log('✅ Mobile Modern 界面初始化完成');
});

// 从Cookie加载音频设置
function loadAudioSettingsFromCookies() {
    // 加载AF增益
    var cAfEl = document.getElementById('C_af');
    var mainAfSlider = document.getElementById('main-af-gain');
    var mainAfValue = document.getElementById('main-af-value');
    
    if (cAfEl) {
        var vol = typeof getCookie === 'function' ? getCookie('C_af') : '';
        if (vol) {
            cAfEl.value = vol;
        }
        
        // 同步主界面音量滑块
        var afPercent = Math.round(parseInt(cAfEl.value) / 10);
        if (mainAfSlider) {
            mainAfSlider.value = afPercent;
        }
        if (mainAfValue) {
            mainAfValue.textContent = afPercent + '%';
        }
    }
    
    // 加载静噪
    var squelchEl = document.getElementById('SQUELCH');
    if (squelchEl) {
        var sql = typeof getCookie === 'function' ? getCookie('SQUELCH') : '';
        if (sql) {
            squelchEl.value = sql;
        }
    }
    
    console.log('🔊 音频设置已从Cookie加载');
}

// 主界面音量控制
function setMainAFGain(value) {
    // 更新显示
    var mainAfValue = document.getElementById('main-af-value');
    if (mainAfValue) {
        mainAfValue.textContent = value + '%';
    }
    
    // 更新隐藏的C_af元素（范围0-1000）
    var cAfEl = document.getElementById('C_af');
    if (cAfEl) {
        cAfEl.value = parseInt(value) * 10; // 0-100映射到0-1000
    }
    
    // 调用AudioRX_SetGAIN
    if (typeof AudioRX_SetGAIN === 'function') {
        AudioRX_SetGAIN();
    }
    
    // 保存Cookie
    if (typeof setCookie === 'function') {
        setCookie('C_af', parseInt(value) * 10, 180);
    }
    
    // 更新设置面板中的显示（如果打开的话）
    var afDisplay = document.getElementById('af-value-display');
    if (afDisplay) {
        afDisplay.textContent = value + '%';
    }
    var afSlider = document.getElementById('mobile-af-gain');
    if (afSlider) {
        afSlider.value = value;
    }
    
    console.log('🔊 AF 增益:', value + '%');
}

// 设置菜单项点击事件
function setupMenuItems() {
    document.querySelectorAll('.menu-item').forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            const action = this.dataset.action;
            if (action) {
                handleMenuItem(action);
            }
        });
    });
}

// 初始化 DOM 元素引用
function initializeElements() {
    domElements.menuToggle = document.getElementById('menu-toggle');
    domElements.menuClose = document.getElementById('menu-close');
    domElements.menuOverlay = document.getElementById('menu-overlay');
    domElements.mainMenu = document.getElementById('main-menu');
    domElements.pttButton = document.getElementById('ptt-btn');
    domElements.powerButton = document.getElementById('power-btn');
    domElements.freqDisplay = document.getElementById('freq-main-display');
    domElements.modeIndicator = document.getElementById('mode-indicator');
    domElements.vfoIndicator = document.getElementById('vfo-indicator');
    domElements.statusCtrl = document.getElementById('status-ctrl');
    domElements.statusRX = document.getElementById('status-rx');
    domElements.statusTX = document.getElementById('status-tx');
    domElements.sMeterCanvas = document.getElementById('s-meter-canvas');
    domElements.quickButtons = document.querySelectorAll('.quick-btn');
    domElements.tuneButtons = document.querySelectorAll('.tune-btn');
}

// 在用户首次交互时初始化音频上下文
function initAudioOnFirstTouch() {
    if (audioContextInitialized) return;
    
    console.log('🔊 用户首次交互，尝试恢复 AudioContext...');
    
    // iOS Safari 关键：调用 controls.js 导出的恢复函数
    if (typeof window.resumeAudioContext === 'function') {
        window.resumeAudioContext().then(success => {
            if (success) {
                console.log('✅ AudioContext 恢复成功');
            } else {
                console.error('❌ AudioContext 恢复失败');
            }
        });
    }
    
    // 检查 TX AudioContext
    if (typeof mh !== 'undefined' && mh && mh.context) {
        if (mh.context.state === 'suspended') {
            mh.context.resume().then(() => {
                console.log('✅ TX AudioContext 已恢复');
            });
        }
    }
    
    audioContextInitialized = true;
    console.log('✅ 音频上下文初始化完成');
}

////////////////////////////////////////////////////////////
// 事件监听器设置
////////////////////////////////////////////////////////////

function setupEventListeners() {
    // 菜单切换
    if (domElements.menuToggle) {
        domElements.menuToggle.addEventListener('click', toggleMenu);
        // iOS Safari: 同时添加 touchend 事件
        domElements.menuToggle.addEventListener('touchend', function(e) {
            e.preventDefault();
            toggleMenu();
        }, { passive: false });
    }
    if (domElements.menuClose) {
        domElements.menuClose.addEventListener('click', closeMenu);
        domElements.menuClose.addEventListener('touchend', function(e) {
            e.preventDefault();
            closeMenu();
        }, { passive: false });
    }
    if (domElements.menuOverlay) {
        domElements.menuOverlay.addEventListener('click', closeMenu);
    }
    
    // PTT 按钮 - 由 tx_button_optimized.js 自动初始化
    // 不在这里设置，避免事件冲突
    
    // 电源按钮 - iOS Safari 关键修复
    if (domElements.powerButton) {
        // iOS Safari: 使用单一的触摸事件处理，避免 click 和 touchend 双重触发
        let powerButtonClicked = false;
        let powerButtonTimeout = null;
        
        const handlePowerClick = function(e) {
            // 防抖：300ms 内只响应一次点击
            if (powerButtonClicked) {
                console.log('🔋 电源按钮防抖，忽略重复点击');
                return;
            }
            
            powerButtonClicked = true;
            clearTimeout(powerButtonTimeout);
            powerButtonTimeout = setTimeout(() => {
                powerButtonClicked = false;
            }, 300);
            
            console.log('🔋 电源按钮触发');
            
            // iOS Safari 关键：在用户交互事件内部立即恢复 AudioContext
            // 这必须在事件处理函数内部同步执行，异步调用无效
            if (typeof AudioRX_context !== 'undefined' && AudioRX_context && AudioRX_context.state === 'suspended') {
                console.log('🔊 电源按钮点击：AudioContext suspended，尝试恢复...');
                AudioRX_context.resume().then(() => {
                    console.log('✅ AudioContext 已在电源按钮点击后恢复');
                }).catch(err => {
                    console.error('❌ AudioContext 恢复失败:', err);
                });
            }
            
            togglePower();
        };
        
        // 只使用 click 事件（iOS Safari 会正确触发）
        domElements.powerButton.addEventListener('click', handlePowerClick);
        
        // 添加视觉反馈
        domElements.powerButton.addEventListener('touchstart', function(e) {
            // 不阻止默认行为，让 click 事件正常触发
            this.style.transform = 'scale(0.9)';
        }, { passive: true });
        
        domElements.powerButton.addEventListener('touchend', function(e) {
            this.style.transform = '';
        }, { passive: true });
        
        domElements.powerButton.addEventListener('touchcancel', function(e) {
            this.style.transform = '';
        }, { passive: true });
    }
    
    // 快捷按钮
    domElements.quickButtons.forEach(button => {
        button.addEventListener('click', function() {
            handleQuickButton(this);
        });
    });
    
    // 频率调节按钮
    domElements.tuneButtons.forEach(button => {
        button.addEventListener('click', function() {
            tuneFrequency(parseInt(this.dataset.step));
        });
    });
    
    // TUNE天调按钮 - 长按发射1kHz单音
    const tuneHeaderBtn = document.getElementById('tune-header-btn');
    if (tuneHeaderBtn) {
        // 触摸开始
        tuneHeaderBtn.addEventListener('touchstart', function(e) {
            e.preventDefault();
            this.classList.add('active');
            if (typeof startTune === 'function') {
                startTune();
            }
        });
        
        // 触摸结束
        tuneHeaderBtn.addEventListener('touchend', function(e) {
            e.preventDefault();
            this.classList.remove('active');
            if (typeof stopTune === 'function') {
                stopTune();
            }
        });
        
        // 鼠标按下
        tuneHeaderBtn.addEventListener('mousedown', function(e) {
            e.preventDefault();
            this.classList.add('active');
            if (typeof startTune === 'function') {
                startTune();
            }
        });
        
        // 鼠标释放
        tuneHeaderBtn.addEventListener('mouseup', function(e) {
            e.preventDefault();
            this.classList.remove('active');
            if (typeof stopTune === 'function') {
                stopTune();
            }
        });
        
        // 鼠标离开按钮
        tuneHeaderBtn.addEventListener('mouseleave', function(e) {
            if (this.classList.contains('active')) {
                this.classList.remove('active');
                if (typeof stopTune === 'function') {
                    stopTune();
                }
            }
        });
        
        console.log('🎵 TUNE天调按钮已初始化');
    }
    
    // 防止长按菜单
    document.addEventListener('contextmenu', function(e) {
        e.preventDefault();
    });
    
    // 防止双击缩放
    let lastTouchEnd = 0;
    document.addEventListener('touchend', function(event) {
        const now = (new Date()).getTime();
        if (now - lastTouchEnd <= 300) {
            event.preventDefault();
        }
        lastTouchEnd = now;
    }, false);
    
    // PTT 按钮由 tx_button_optimized.js 完全接管
    // 不再在这里设置事件监听器，避免冲突
    console.log('🎯 PTT 按钮由 tx_button_optimized.js 接管');
}

////////////////////////////////////////////////////////////
// WebSocket 连接 - 使用 controls.js 的函数
////////////////////////////////////////////////////////////

function connectWebSocket() {
    console.log('🔌 连接 WebSocket...');
    
    // 使用 controls.js 的连接函数
    if (typeof AudioRX_start === 'function') {
        AudioRX_start();
    }
    if (typeof AudioTX_start === 'function') {
        AudioTX_start();
    }
    if (typeof ControlTRX_start === 'function') {
        ControlTRX_start();
    }
    
    mobileState.isConnected = true;
    
    // 启动延迟检查
    if (typeof checklatency === 'function' && typeof poweron !== 'undefined') {
        // poweron 是 controls.js 的全局变量
    }
}

function disconnectWebSocket() {
    console.log('🔌 断开 WebSocket...');
    
    // 使用 controls.js 的断开函数
    if (typeof AudioRX_stop === 'function') {
        AudioRX_stop();
    }
    if (typeof AudioTX_stop === 'function') {
        AudioTX_stop();
    }
    if (typeof ControlTRX_stop === 'function') {
        ControlTRX_stop();
    }
    
    mobileState.isConnected = false;
}

////////////////////////////////////////////////////////////
// 音频系统 - 使用 controls.js 的函数
////////////////////////////////////////////////////////////

// 音频初始化（iOS Safari 需要用户交互）
function initAudioOnFirstTouch() {
    if (audioContextInitialized) return;
    
    try {
        // controls.js 会在连接时初始化音频
        // 这里只是确保 AudioContext 可以在用户交互后使用
        if (typeof AudioRX_context !== 'undefined' && AudioRX_context) {
            if (AudioRX_context.state === 'suspended') {
                AudioRX_context.resume().then(() => {
                    console.log('✅ AudioContext 已恢复');
                });
            }
        }
        
        audioContextInitialized = true;
        console.log('✅ 音频上下文初始化完成');
    } catch (e) {
        console.error('❌ 音频上下文初始化失败:', e);
    }
}

////////////////////////////////////////////////////////////
// 电源控制
////////////////////////////////////////////////////////////

function togglePower() {
    console.log('🔋 togglePower 被调用, 当前 poweron:', (typeof poweron !== 'undefined') ? poweron : 'undefined');
    
    // 直接使用 controls.js 的全局变量和函数
    // 不能直接调用 powertogle() 因为它依赖全局 event 对象和特定的 DOM 结构
    
    if (typeof poweron !== 'undefined' && poweron) {
        // 断开连接 - 直接调用底层函数
        console.log('🔴 正在关闭电源...');
        if (typeof AudioRX_stop === 'function') AudioRX_stop();
        if (typeof AudioTX_stop === 'function') AudioTX_stop();
        if (typeof ControlTRX_stop === 'function') ControlTRX_stop();
        poweron = false;
        
        // 更新按钮状态
        if (domElements.powerButton) {
            domElements.powerButton.classList.remove('active');
            const icon = domElements.powerButton.querySelector('.power-icon');
            if (icon) icon.textContent = '⏻';
        }
        console.log('🔴 电源已关闭');
    } else {
        // 连接 - 直接调用底层函数
        console.log('🟢 正在开启电源...');
        if (typeof check_connected === 'function') check_connected();
        if (typeof AudioRX_start === 'function') AudioRX_start();
        if (typeof AudioTX_start === 'function') AudioTX_start();
        if (typeof ControlTRX_start === 'function') ControlTRX_start();
        if (typeof checklatency === 'function') checklatency();
        poweron = true;
        
        // 更新按钮状态
        if (domElements.powerButton) {
            domElements.powerButton.classList.add('active');
            const icon = domElements.powerButton.querySelector('.power-icon');
            if (icon) icon.textContent = '⏼';
        }
        console.log('🟢 电源已开启');
        
        // iOS Safari：AudioContext 恢复已在点击事件处理函数内部完成
        // 这里只是打印状态
        if (typeof AudioRX_context !== 'undefined' && AudioRX_context) {
            console.log('🔊 AudioContext 状态:', AudioRX_context.state);
        }
    }
}

////////////////////////////////////////////////////////////
// PTT 预热帧发送
////////////////////////////////////////////////////////////

function sendPTTWarmupFrames() {
    // 使用 controls.js 的全局变量
    if (typeof wsAudioTX !== 'undefined' && wsAudioTX && wsAudioTX.readyState === WebSocket.OPEN) {
        console.log('🔥 发送 PTT 预热帧...');
        for (let i = 0; i < 10; i++) {
            setTimeout(() => {
                try {
                    // 发送静音帧
                    const warmup = new Int16Array(160);
                    wsAudioTX.send(warmup);
                } catch (e) {
                    console.warn('预热帧发送失败:', e);
                }
            }, i * 10);
        }
    }
}

////////////////////////////////////////////////////////////
// RX 音频缓冲区清除
////////////////////////////////////////////////////////////

function flushRXAudioBuffer() {
    // 使用 controls.js 的全局变量
    if (typeof AudioRX_source_node !== 'undefined' && AudioRX_source_node && AudioRX_source_node.port) {
        try {
            AudioRX_source_node.port.postMessage({ type: 'flush' });
            console.log('🧹 RX 音频缓冲区已清除');
        } catch (e) {
            console.warn('清除 RX 缓冲区失败:', e);
        }
    }
    // 同时清除数组缓冲
    if (typeof AudioRX_audiobuffer !== 'undefined') {
        AudioRX_audiobuffer = [];
    }
}

////////////////////////////////////////////////////////////
// 消息发送函数 - 使用 controls.js 的全局 WebSocket
////////////////////////////////////////////////////////////

function sendWebSocketMessage(message) {
    if (typeof wsControlTRX !== 'undefined' && wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        console.log(`📤 发送消息: ${message}`);
        wsControlTRX.send(message);
    } else {
        console.warn('⚠️ WebSocket 未连接，无法发送消息:', message);
    }
}

////////////////////////////////////////////////////////////
// UI 更新函数
////////////////////////////////////////////////////////////

// 更新 TX 状态显示
function updateTXStatus(isTX) {
    if (isTX) {
        domElements.statusTX.classList.add('active');
        domElements.statusRX.classList.remove('active');
    } else {
        domElements.statusTX.classList.remove('active');
        domElements.statusRX.classList.add('active');
    }
}

// 更新频率显示
function updateFrequencyDisplay() {
    // 从 controls.js 的全局变量获取频率
    if (typeof TRXfrequency !== 'undefined') {
        mobileState.currentFrequency = TRXfrequency;
    }
    
    const freqStr = mobileState.currentFrequency.toString().padStart(8, '0');
    
    // HF频段：两位MHz + 三位kHz + 三位Hz
    const elements = ['freq-10mhz', 'freq-1mhz', 
                      'freq-100khz', 'freq-10khz', 'freq-1khz',
                      'freq-100hz', 'freq-10hz', 'freq-1hz'];
    
    elements.forEach((id, index) => {
        const el = document.getElementById(id);
        if (el) el.textContent = freqStr[index];
    });
}

// 调节频率
function tuneFrequency(step) {
    // 检查 poweron 状态（来自 controls.js）
    if (typeof poweron !== 'undefined' && !poweron) return;
    
    // 使用 controls.js 的全局频率变量
    if (typeof TRXfrequency !== 'undefined') {
        mobileState.currentFrequency = TRXfrequency;
    }
    
    mobileState.currentFrequency += step;
    if (mobileState.currentFrequency < 0) mobileState.currentFrequency = 0;
    
    // 更新全局频率变量
    if (typeof TRXfrequency !== 'undefined') {
        TRXfrequency = mobileState.currentFrequency;
    }
    
    updateFrequencyDisplay();
    
    // 使用 controls.js 的发送函数
    if (typeof sendTRXfreq === 'function') {
        sendTRXfreq(mobileState.currentFrequency);
    } else {
        sendWebSocketMessage("setFreq:" + mobileState.currentFrequency);
    }
}

// S表映射表使用controls.js中定义的全局变量 SP 和 RIG_LEVEL_STRENGTH
// SP: S表位置映射，键为信号级别(0-9为S单位，10-60为S9+dB)，值为画布X坐标
// RIG_LEVEL_STRENGTH: 对应的dB值，S9=0dB

// 更新 S 表
function updateSMeter(level) {
    const canvas = domElements.sMeterCanvas;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    const value = parseInt(level) || 0;
    drawSMeter(ctx, value);
    
    // 更新信号强度文字显示
    updateSignalText(value);
}

// 更新信号强度文字显示
function updateSignalText(level) {
    const signalText = document.querySelector('.signal-text');
    if (!signalText) return;
    
    let res = "S0";
    if (level > 9) {
        res = "S9+" + level;
    } else {
        res = "S" + level;
    }
    
    // 添加dB显示
    if (typeof RIG_LEVEL_STRENGTH[level] !== 'undefined') {
        res += " (" + RIG_LEVEL_STRENGTH[level] + "dB)";
    }
    
    signalText.textContent = res;
}

////////////////////////////////////////////////////////////
// S 表绘制
////////////////////////////////////////////////////////////

function initializeSMeter() {
    const canvas = domElements.sMeterCanvas;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    drawSMeter(ctx, 0);
}

function drawSMeter(ctx, level) {
    const canvas = ctx.canvas;
    const width = canvas.width;
    const height = canvas.height;
    
    // 清除画布
    ctx.clearRect(0, 0, width, height);
    
    // 绘制背景
    ctx.fillStyle = '#111';
    ctx.fillRect(0, 0, width, height);
    
    // S表刻度区域（0-240像素对应S0-S9+60dB）
    const meterWidth = 240;
    const meterStartX = 20;
    
    // 绘制S单位刻度线（S1-S9）
    ctx.strokeStyle = '#444';
    ctx.lineWidth = 1;
    for (let i = 1; i <= 9; i++) {
        if (SP[i] !== undefined) {
            const x = meterStartX + SP[i];
            ctx.beginPath();
            ctx.moveTo(x, height * 0.7);
            ctx.lineTo(x, height);
            ctx.stroke();
        }
    }
    
    // 绘制S9+刻度线（+10, +20, +30, +40, +50, +60）
    ctx.strokeStyle = '#666';
    for (let i = 10; i <= 60; i += 10) {
        if (SP[i] !== undefined) {
            const x = meterStartX + SP[i];
            ctx.beginPath();
            ctx.moveTo(x, height * 0.7);
            ctx.lineTo(x, height);
            ctx.stroke();
        }
    }
    
    // 绘制当前信号级别条形
    if (typeof SP[level] !== 'undefined') {
        const barX = meterStartX;
        const barWidth = SP[level];
        const barHeight = height * 0.5;
        const barY = height * 0.25;
        
        // 创建渐变色
        const gradient = ctx.createLinearGradient(barX, 0, barX + meterWidth, 0);
        gradient.addColorStop(0, '#4CAF50');      // S1-S3 绿色
        gradient.addColorStop(0.35, '#8BC34A');   // S4-S5 浅绿
        gradient.addColorStop(0.5, '#FFC107');    // S6-S7 黄色
        gradient.addColorStop(0.65, '#FF9800');   // S8-S9 橙色
        gradient.addColorStop(0.75, '#F44336');   // S9+10 红色
        gradient.addColorStop(1, '#D32F2F');      // S9+60 深红
        
        ctx.fillStyle = gradient;
        ctx.fillRect(barX, barY, barWidth, barHeight);
        
        // 绘制指示线
        ctx.strokeStyle = '#fffb16';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(meterStartX + SP[level], 0);
        ctx.lineTo(meterStartX + SP[level], height);
        ctx.stroke();
    }
    
    // 绘制静噪线（如果有设置）
    const squelchEl = document.getElementById('SQUELCH');
    if (squelchEl) {
        const sqValue = squelchEl.value * 2.5; // 转换为像素位置
        ctx.strokeStyle = '#deded5';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(meterStartX + sqValue, 0);
        ctx.lineTo(meterStartX + sqValue, height);
        ctx.stroke();
    }
}

////////////////////////////////////////////////////////////
// 菜单和其他 UI 功能
////////////////////////////////////////////////////////////

function toggleMenu() {
    domElements.mainMenu.classList.toggle('open');
    domElements.menuOverlay.classList.toggle('open');
}

function closeMenu() {
    domElements.mainMenu.classList.remove('open');
    domElements.menuOverlay.classList.remove('open');
}

function handleQuickButton(button) {
    // 移除兄弟元素的 active 状态
    const siblings = button.parentElement.children;
    for (let i = 0; i < siblings.length; i++) {
        siblings[i].classList.remove('active');
    }
    
    button.classList.add('active');
    
    // 处理特定按钮
    if (button.id === 'vfo-a-btn' || button.id === 'vfo-b-btn') {
        // VFO 切换 - 目前后端不支持，只更新 UI
        const vfo = button.id === 'vfo-a-btn' ? 'VFO-A' : 'VFO-B';
        mobileState.currentVFO = vfo;
        if (domElements.vfoIndicator) {
            domElements.vfoIndicator.textContent = vfo;
        }
        console.log('VFO 切换:', vfo, '(后端暂不支持)');
        // TODO: 当后端支持时发送命令
        // sendWebSocketMessage("setVFO:" + vfo.replace('-', ''));
    } else if (button.id === 'mode-btn') {
        cycleMode();
    } else if (button.id === 'band-btn') {
        // 波段切换 - 简单实现
        cycleBand();
    } else if (button.id === 'filter-btn') {
        // 滤波器切换
        cycleFilter();
    } else if (button.id === 'step-btn') {
        // 步进切换
        cycleStep();
    }
}

// 波段切换 - 频率参照 index.html 中的设置
function cycleBand() {
    const bands = ['160m', '80m', '40m', '30m', '20m', '17m', '15m', '12m', '10m'];
    const bandFreqs = {
        '160m': 1845500,   // 1.845500 MHz
        '80m': 3850000,    // 3.850000 MHz
        '40m': 7050000,    // 7.050000 MHz
        '30m': 10140000,   // 10.140000 MHz
        '20m': 14270000,   // 14.270000 MHz
        '17m': 18132500,   // 18.132500 MHz
        '15m': 21400000,   // 21.400000 MHz
        '12m': 24952500,   // 24.952500 MHz
        '10m': 28450000,   // 28.450000 MHz
    };
    
    const bandBtn = document.getElementById('band-btn');
    if (!bandBtn) return;
    
    const currentBand = bandBtn.innerHTML;
    const currentIndex = bands.indexOf(currentBand);
    const nextIndex = (currentIndex + 1) % bands.length;
    const nextBand = bands[nextIndex];
    
    bandBtn.innerHTML = nextBand;
    
    // 设置频率
    const freq = bandFreqs[nextBand];
    if (freq && typeof TRXfrequency !== 'undefined') {
        TRXfrequency = freq;
        mobileState.currentFrequency = freq;
        updateFrequencyDisplay();
        if (typeof sendTRXfreq === 'function') {
            sendTRXfreq(freq);
        }
        console.log('波段切换:', nextBand, '频率:', freq);
    }
}

// 滤波器切换 - 使用 controls.js 的 setaudiofilter
function cycleFilter() {
    const filters = [
        { name: 'OFF', ft: 'highshelf', frq: 22000, fg: 0, fq: 0 },
        { name: 'LP2.7k', ft: 'highshelf', frq: 2700, fg: -20, fq: 0 },
        { name: 'LP2.1k', ft: 'highshelf', frq: 2100, fg: -20, fq: 0 },
        { name: 'LP1.0k', ft: 'highshelf', frq: 1000, fg: -20, fq: 0 },
        { name: 'BP500', ft: 'bandpass', frq: 500, fg: -100, fq: 50 },
        { name: 'BP300', ft: 'bandpass', frq: 300, fg: -100, fq: 50 }
    ];
    
    const filterBtn = document.getElementById('filter-btn');
    if (!filterBtn) return;
    
    const currentName = filterBtn.innerHTML;
    const currentIndex = filters.findIndex(f => f.name === currentName);
    const nextIndex = (currentIndex + 1) % filters.length;
    const nextFilter = filters[nextIndex];
    
    filterBtn.innerHTML = nextFilter.name;
    
    // 应用滤波器
    if (typeof poweron !== 'undefined' && poweron && typeof AudioRX_biquadFilter_node !== 'undefined' && AudioRX_biquadFilter_node) {
        try {
            AudioRX_biquadFilter_node.type = nextFilter.ft;
            AudioRX_biquadFilter_node.frequency.setValueAtTime(nextFilter.frq, AudioRX_context.currentTime);
            AudioRX_biquadFilter_node.gain.setValueAtTime(nextFilter.fg, AudioRX_context.currentTime);
            AudioRX_biquadFilter_node.Q.setValueAtTime(nextFilter.fq, AudioRX_context.currentTime);
            console.log('滤波器切换:', nextFilter.name, nextFilter);
        } catch (e) {
            console.error('滤波器设置失败:', e);
        }
    }
}

// 步进切换
function cycleStep() {
    const steps = ['10Hz', '100Hz', '1kHz', '10kHz'];
    const stepValues = [10, 100, 1000, 10000];
    const stepBtn = document.getElementById('step-btn');
    if (!stepBtn) return;
    
    const current = stepBtn.innerHTML;
    const currentIndex = steps.indexOf(current);
    const nextIndex = (currentIndex + 1) % steps.length;
    stepBtn.innerHTML = steps[nextIndex];
    
    // 存储当前步进值
    mobileState.tuneStep = stepValues[nextIndex];
    console.log('步进切换:', steps[nextIndex]);
}

////////////////////////////////////////////////////////////
// 菜单项处理
////////////////////////////////////////////////////////////

// 菜单项点击处理
function handleMenuItem(action) {
    console.log('菜单项点击:', action);
    closeMenu();
    
    switch (action) {
        case 'bands':
            showBandSelector();
            break;
        case 'modes':
            showModeSelector();
            break;
        case 'memory':
            showMemoryPanel();
            break;
        case 'settings':
            showSettingsPanel();
            break;
        case 'audio':
            showAudioPanel();
            break;
        case 'txeq':
            showTXEQPanel();
            break;
        case 'digital':
            showDigitalPanel();
            break;
        case 'logbook':
            showLogbookPanel();
            break;
        case 'about':
            showAboutPanel();
            break;
    }
}

// 波段选择器
function showBandSelector() {
    const bands = [
        { name: '160m', freq: 1845500 },
        { name: '80m', freq: 3850000 },
        { name: '40m', freq: 7050000 },
        { name: '30m', freq: 10140000 },
        { name: '20m', freq: 14270000 },
        { name: '17m', freq: 18132500 },
        { name: '15m', freq: 21400000 },
        { name: '12m', freq: 24952500 },
        { name: '10m', freq: 28450000 }
    ];
    
    let html = '<div class="modal-panel"><h3>波段选择</h3><div class="band-grid">';
    bands.forEach(band => {
        html += `<button class="band-select-btn" onclick="selectBand(${band.freq}, '${band.name}')">${band.name}</button>`;
    });
    html += '</div><button class="close-panel-btn" onclick="closeModalPanel()">关闭</button></div>';
    
    showModalPanel(html);
}

function selectBand(freq, name) {
    if (typeof TRXfrequency !== 'undefined') {
        TRXfrequency = freq;
        mobileState.currentFrequency = freq;
        updateFrequencyDisplay();
        
        // 更新波段按钮
        const bandBtn = document.getElementById('band-btn');
        if (bandBtn) bandBtn.innerHTML = name;
        
        if (typeof sendTRXfreq === 'function') {
            sendTRXfreq(freq);
        }
        console.log('选择波段:', name, '频率:', freq);
    }
    closeModalPanel();
}

// 模式选择器
function showModeSelector() {
    const modes = ['USB', 'LSB', 'AM', 'FM'];
    
    let html = '<div class="modal-panel"><h3>模式选择</h3><div class="mode-grid">';
    modes.forEach(mode => {
        const active = mobileState.currentMode === mode ? 'active' : '';
        html += `<button class="mode-select-btn ${active}" onclick="selectMode('${mode}')">${mode}</button>`;
    });
    html += '</div><button class="close-panel-btn" onclick="closeModalPanel()">关闭</button></div>';
    
    showModalPanel(html);
}

function selectMode(mode) {
    mobileState.currentMode = mode;
    
    // 更新 UI
    if (domElements.modeIndicator) {
        domElements.modeIndicator.textContent = mode;
    }
    const modeBtn = document.getElementById('mode-btn');
    if (modeBtn) modeBtn.innerHTML = mode;
    
    // 发送命令
    sendWebSocketMessage("setMode:" + mode);
    console.log('选择模式:', mode);
    
    closeModalPanel();
}

// 内存面板（占位）
function showMemoryPanel() {
    let html = '<div class="modal-panel"><h3>内存管理</h3>';
    html += '<p>内存功能开发中...</p>';
    html += '<button class="close-panel-btn" onclick="closeModalPanel()">关闭</button></div>';
    showModalPanel(html);
}

// 设置面板
function showSettingsPanel() {
    // 获取当前增益值
    var cAfEl = document.getElementById('C_af');
    var squelchEl = document.getElementById('SQUELCH');
    
    // AF增益值（0-1000映射到0-100%显示）
    var afValue = cAfEl ? parseInt(cAfEl.value) : 500;
    var afPercent = Math.round(afValue / 10); // 0-100%
    
    // 静噪值（0-100）
    var sqlValue = squelchEl ? parseInt(squelchEl.value) : 0;
    
    // MIC增益（从Cookie获取，默认50%）
    var micValue = 50;
    var micCookie = getCookie('mobile_mic_gain');
    if (micCookie) {
        micValue = parseInt(micCookie);
    }
    
    let html = '<div class="modal-panel"><h3>音频设置</h3>';
    
    // AF 增益
    html += '<div class="setting-item">';
    html += '<label>AF 增益: <span id="af-value-display">' + afPercent + '%</span></label>';
    html += '<input type="range" id="mobile-af-gain" min="0" max="100" value="' + afPercent + '" oninput="setAFGain(this.value)">';
    html += '</div>';
    
    // MIC 增益
    html += '<div class="setting-item">';
    html += '<label>MIC 增益: <span id="mic-value-display">' + micValue + '%</span></label>';
    html += '<input type="range" id="mobile-mic-gain" min="0" max="200" value="' + micValue + '" oninput="setMicGain(this.value)">';
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
    // 更新显示
    var display = document.getElementById('af-value-display');
    if (display) display.textContent = value + '%';
    
    // 更新隐藏的C_af元素（范围0-1000）
    var cAfEl = document.getElementById('C_af');
    if (cAfEl) {
        cAfEl.value = parseInt(value) * 10; // 0-100映射到0-1000
    }
    
    // 同步主界面音量滑块
    var mainAfSlider = document.getElementById('main-af-gain');
    var mainAfValue = document.getElementById('main-af-value');
    if (mainAfSlider) mainAfSlider.value = value;
    if (mainAfValue) mainAfValue.textContent = value + '%';
    
    // 调用AudioRX_SetGAIN
    if (typeof AudioRX_SetGAIN === 'function') {
        AudioRX_SetGAIN();
    }
    
    // 保存Cookie
    if (typeof setCookie === 'function') {
        setCookie('C_af', parseInt(value) * 10, 180);
    }
    
    console.log('AF 增益:', value + '%');
}

function setMicGain(value) {
    // 更新显示
    var display = document.getElementById('mic-value-display');
    if (display) display.textContent = value + '%';
    
    // 调用AudioTX_SetGAIN（值范围0-1）
    if (typeof AudioTX_SetGAIN === 'function') {
        AudioTX_SetGAIN(parseInt(value) / 100);
    }
    
    // 保存Cookie
    if (typeof setCookie === 'function') {
        setCookie('mobile_mic_gain', value, 180);
    }
    
    console.log('MIC 增益:', value + '%');
}

function setSquelch(value) {
    // 更新显示
    var display = document.getElementById('sql-value-display');
    if (display) display.textContent = value;
    
    // 更新隐藏的SQUELCH元素
    var squelchEl = document.getElementById('SQUELCH');
    if (squelchEl) {
        squelchEl.value = value;
    }
    
    // 更新S表显示（重绘静噪线）
    if (typeof drawRXSmeter === 'function') {
        drawRXSmeter();
    }
    // 同时更新移动端S表
    if (typeof updateSMeter === 'function' && typeof SignalLevel !== 'undefined') {
        updateSMeter(SignalLevel);
    }
    
    // 保存Cookie
    if (typeof setCookie === 'function') {
        setCookie('SQUELCH', value, 180);
    }
    
    console.log('静噪:', value);
}

// 音频面板
function showAudioPanel() {
    const filters = ['OFF', 'LP2.7k', 'LP2.1k', 'LP1.0k', 'BP500', 'BP300'];
    
    let html = '<div class="modal-panel"><h3>音频滤波器</h3><div class="filter-grid">';
    filters.forEach(f => {
        html += `<button class="filter-select-btn" onclick="selectFilter('${f}')">${f}</button>`;
    });
    html += '</div><button class="close-panel-btn" onclick="closeModalPanel()">关闭</button></div>';
    showModalPanel(html);
}

function selectFilter(name) {
    const filterBtn = document.getElementById('filter-btn');
    if (filterBtn) filterBtn.innerHTML = name;
    cycleFilter(); // 应用滤波器
    closeModalPanel();
}

////////////////////////////////////////////////////////////
// TX EQ 均衡器面板 - 短波通信优化
////////////////////////////////////////////////////////////

function showTXEQPanel() {
    // 获取当前预设
    const currentPreset = typeof getTX_EQ_Preset === 'function' ? getTX_EQ_Preset() : 'DEFAULT';
    const presets = typeof getTX_EQ_Presets === 'function' ? getTX_EQ_Presets() : {
        'DEFAULT': { name: '默认', low: 0, mid: 0, high: 0, desc: '无EQ处理' },
        'HF_VOICE': { name: '短波语音', low: 4, mid: 6, high: -3, desc: '增强中低频' },
        'DX_WEAK': { name: '弱信号', low: 6, mid: 8, high: -6, desc: '强调中低频' },
        'CONTEST': { name: '比赛模式', low: 2, mid: 4, high: -2, desc: '均衡处理' }
    };
    
    let html = '<div class="modal-panel"><h3>🎙️ 发射均衡器</h3>';
    html += '<p style="font-size:12px;color:#888;margin-bottom:15px;">短波通信语音优化</p>';
    html += '<div class="txeq-grid">';
    
    Object.keys(presets).forEach(key => {
        const preset = presets[key];
        const isActive = currentPreset === key;
        const activeClass = isActive ? 'txeq-btn-active' : '';
        html += `<button class="txeq-select-btn ${activeClass}" onclick="selectTX_EQ('${key}')">`;
        html += `<strong>${preset.name}</strong>`;
        html += `<br><span style="font-size:11px;color:#aaa;">${preset.desc}</span>`;
        if (key !== 'DEFAULT') {
            html += `<br><span style="font-size:10px;color:#666;">低+${preset.low} 中+${preset.mid} 高${preset.high}</span>`;
        }
        html += '</button>';
    });
    
    html += '</div>';
    html += '<div style="margin-top:15px;padding:10px;background:#222;border-radius:8px;">';
    html += '<p style="font-size:12px;color:#aaa;margin:0;">';
    html += '<strong>说明：</strong>短波通信中，高频信号容易过强导致声音刺耳。';
    html += '选择合适的预设可以增强中低频，提高语音清晰度和舒适度。';
    html += '</p></div>';
    html += '<button class="close-panel-btn" onclick="closeModalPanel()">关闭</button></div>';
    showModalPanel(html);
}

function selectTX_EQ(presetName) {
    if (typeof setTX_EQ_Preset === 'function') {
        setTX_EQ_Preset(presetName);
        // 刷新面板显示
        showTXEQPanel();
    } else {
        console.error('setTX_EQ_Preset function not found');
    }
}

// 数字模式面板（占位）
function showDigitalPanel() {
    let html = '<div class="modal-panel"><h3>数字模式</h3>';
    html += '<p>数字模式功能开发中...</p>';
    html += '<button class="close-panel-btn" onclick="closeModalPanel()">关闭</button></div>';
    showModalPanel(html);
}

// 日志面板（占位）
function showLogbookPanel() {
    let html = '<div class="modal-panel"><h3>日志</h3>';
    html += '<p>日志功能开发中...</p>';
    html += '<button class="close-panel-btn" onclick="closeModalPanel()">关闭</button></div>';
    showModalPanel(html);
}

// 关于面板
function showAboutPanel() {
    let html = '<div class="modal-panel"><h3>关于</h3>';
    html += '<p><strong>Universal Ham Radio Remote</strong></p>';
    html += '<p>版本: 3.2</p>';
    html += '<p>移动端界面优化版</p>';
    html += '<hr>';
    html += '<p>基于 F4HTB 开源项目</p>';
    html += '<p>GPL-3.0 许可证</p>';
    html += '<button class="close-panel-btn" onclick="closeModalPanel()">关闭</button></div>';
    showModalPanel(html);
}

// 模态面板显示/隐藏
function showModalPanel(html) {
    let panel = document.getElementById('modal-panel-container');
    if (!panel) {
        panel = document.createElement('div');
        panel.id = 'modal-panel-container';
        document.body.appendChild(panel);
    }
    panel.innerHTML = html;
    panel.style.display = 'flex';
}

function closeModalPanel() {
    const panel = document.getElementById('modal-panel-container');
    if (panel) {
        panel.style.display = 'none';
    }
}

function cycleMode() {
    const modes = ['LSB', 'USB', 'AM', 'FM'];
    const currentIndex = modes.indexOf(mobileState.currentMode);
    const nextIndex = (currentIndex + 1) % modes.length;
    mobileState.currentMode = modes[nextIndex];
    
    // 更新显示
    domElements.modeIndicator.textContent = mobileState.currentMode;
    var modeBtn = document.getElementById("mode-btn");
    if (modeBtn) {
        modeBtn.innerHTML = mobileState.currentMode;
    }
    
    // 发送模式命令
    sendWebSocketMessage("setMode:" + mobileState.currentMode);
}

////////////////////////////////////////////////////////////
// 页面可见性和方向变化处理
////////////////////////////////////////////////////////////

document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        console.log('页面隐藏');
    } else {
        console.log('页面可见');
    }
});

window.addEventListener('resize', function() {
    initializeSMeter();
});

window.addEventListener('orientationchange', function() {
    setTimeout(() => {
        initializeSMeter();
    }, 100);
});

////////////////////////////////////////////////////////////
// 导出全局函数供外部调用
////////////////////////////////////////////////////////////

// 供 controls.js 调用的接口
window.mobileModemUpdateFrequency = function(freq) {
    mobileState.currentFrequency = freq;
    updateFrequencyDisplay();
};

window.mobileModemUpdateMode = function(mode) {
    mobileState.currentMode = mode;
    domElements.modeIndicator.textContent = mode;
};

window.mobileModemUpdatePTT = function(state) {
    mobileState.isTransmitting = state;
    updateTXStatus(state);
};

// 监听 controls.js 的状态变化
if (typeof MutationObserver !== 'undefined') {
    // 监听频率显示变化
    const freqObserver = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.target.id && mutation.target.id.startsWith('freq-')) {
                // 频率显示已更新
            }
        });
    });
}

console.log('🎯 Mobile Modern JS 加载完成');

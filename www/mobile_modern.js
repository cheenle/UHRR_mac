// Modern Mobile Interface JavaScript for iPhone 15 and modern browsers
// V4.4.21 - 2026-03-06
// 完全兼容 controls.js 的实现，确保与桌面版一致的行为
// 
// 重要：此文件依赖 controls.js 先加载
// 所有核心功能由 controls.js 提供，此文件仅处理移动端特定的 UI 逻辑

////////////////////////////////////////////////////////////
// Wake Lock - 防止屏幕休眠
////////////////////////////////////////////////////////////
let wakeLock = null;
let wakeLockSupported = null; // null = 未检测, true = 支持, false = 不支持

// 请求 Wake Lock（带缓存，避免重复请求）
async function requestWakeLock() {
    // 已经有 Wake Lock，不需要重复请求
    if (wakeLock) {
        return;
    }
    
    // 检测支持性（只检测一次）
    if (wakeLockSupported === null) {
        wakeLockSupported = 'wakeLock' in navigator;
    }
    
    if (!wakeLockSupported) {
        return; // 不支持，静默跳过
    }
    
    try {
        wakeLock = await navigator.wakeLock.request('screen');
        console.log('🔒 Wake Lock 已启用');
        
        // 监听 Wake Lock 释放事件（只记录一次）
        wakeLock.addEventListener('release', () => {
            wakeLock = null;
        });
    } catch (err) {
        // 常见错误不记录日志
        if (err.name !== 'NotAllowedError') {
            console.log('⚠️ Wake Lock 请求失败:', err.name);
        }
    }
}

// 释放 Wake Lock
async function releaseWakeLock() {
    if (wakeLock) {
        try {
            await wakeLock.release();
            wakeLock = null;
            console.log('🔓 Wake Lock 已释放');
        } catch (err) {
            wakeLock = null;
        }
    }
}

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
// 初始化
////////////////////////////////////////////////////////////

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Mobile Modern 界面初始化...');
    
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
    
    // iOS Safari 需要用户交互才能初始化音频
    document.addEventListener('touchstart', initAudioOnFirstTouch, { once: true });
    document.addEventListener('mousedown', initAudioOnFirstTouch, { once: true });
    
    // 页面可见性变化时重新请求 Wake Lock
    document.addEventListener('visibilitychange', async () => {
        if (document.visibilityState === 'visible' && mobileState.isConnected) {
            await requestWakeLock();
        }
    });
    
    console.log('✅ Mobile Modern 界面初始化完成');
});

// 从Cookie加载音频设置（用户专属）
function loadAudioSettingsFromCookies() {
    // 获取当前用户
    var currentUser = '';
    try {
        if (typeof getCurrentUserCallsign === 'function') {
            currentUser = getCurrentUserCallsign();
        }
    } catch (e) {
        console.warn('获取用户呼号失败:', e);
    }
    console.log('🔊 加载用户设置, 当前用户:', currentUser || '默认');
    
    // 加载AF增益
    var cAfEl = document.getElementById('C_af');
    var mainAfSlider = document.getElementById('main-af-gain');
    var mainAfValue = document.getElementById('main-af-value');
    
    if (cAfEl) {
        // 优先加载用户设置，回退到默认设置
        var vol = '';
        try {
            if (typeof loadUserAudioSetting === 'function') {
                vol = loadUserAudioSetting('C_af', '');
            } else if (typeof getCookie === 'function') {
                vol = getCookie('C_af');
            }
        } catch (e) {
            console.warn('加载C_af设置失败:', e);
        }
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
        var sql = '';
        try {
            if (typeof loadUserAudioSetting === 'function') {
                sql = loadUserAudioSetting('SQUELCH', '');
            } else if (typeof getCookie === 'function') {
                sql = getCookie('SQUELCH');
            }
        } catch (e) {
            console.warn('加载SQUELCH设置失败:', e);
        }
        if (sql) {
            squelchEl.value = sql;
        }
    }
    
    // 加载MIC增益
    var micSlider = document.getElementById('mobile-mic-gain');
    var micValue = document.getElementById('mobile-mic-value');
    if (micSlider) {
        var micCookie = '50'; // 默认值
        try {
            if (typeof loadUserAudioSetting === 'function') {
                micCookie = loadUserAudioSetting('mobile_mic_gain', '50');
            } else if (typeof getCookie === 'function') {
                var c = getCookie('mobile_mic_gain');
                if (c) micCookie = c;
            }
        } catch (e) {
            console.warn('加载MIC增益设置失败:', e);
        }
        micSlider.value = parseInt(micCookie);
        if (micValue) micValue.textContent = micCookie + '%';
    }
    
    console.log('🔊 用户音频设置已加载');
}

// 主界面音量控制（用户专属设置）
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
    
    // 保存用户专属Cookie
    if (typeof saveUserAudioSetting === 'function') {
        saveUserAudioSetting('C_af', parseInt(value) * 10, 180);
    } else if (typeof setCookie === 'function') {
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
    domElements.tuneButtons = document.querySelectorAll('.tune-btn, .tune-btn-compact, .tune-btn-grid');
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
    
    // 底部 TUNE 按钮 - 长按发射1kHz单音
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
        
        console.log('🎵 底部 TUNE 按钮已初始化');
    }
    
    // 频率显示点击切换到输入模式
    if (domElements.freqDisplay && domElements.freqInput) {
        // 点击频率显示区域显示输入框
        domElements.freqDisplay.addEventListener('click', function() {
            showFrequencyInput();
        });
        
        // 输入框失去焦点时隐藏并应用频率
        domElements.freqInput.addEventListener('blur', function() {
            hideFrequencyInput(true);
        });
        
        // 回车确认输入
        domElements.freqInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                hideFrequencyInput(true);
                this.blur();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                hideFrequencyInput(false);
                this.blur();
            }
        });
        
        console.log('🔢 频率输入功能已初始化');
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

// 更新 Opus 编码状态指示器
function updateOpusStatus() {
    const opusIndicator = document.getElementById('status-opus');
    const encodeCheckbox = document.getElementById('encode');
    
    if (opusIndicator) {
        const isOpusEnabled = encodeCheckbox ? encodeCheckbox.checked : false;
        if (isOpusEnabled) {
            opusIndicator.classList.add('active');
            opusIndicator.title = 'Opus 编码已启用 (高质量/低带宽)';
        } else {
            opusIndicator.classList.remove('active');
            opusIndicator.title = 'Opus 编码未启用 (PCM 模式)';
        }
    }
}

function togglePower() {
    console.log('🔋 togglePower 被调用, 当前 poweron:', (typeof poweron !== 'undefined') ? poweron : 'undefined');
    
    // 直接使用 controls.js 的全局变量和函数
    // 不能直接调用 powertogle() 因为它依赖全局 event 对象和特定的 DOM 结构
    
    if (typeof poweron !== 'undefined' && poweron) {
        // 断开连接 - 直接调用底层函数
        console.log('🔴 正在关闭电源...');
        try {
            if (typeof AudioRX_stop === 'function') {
                console.log('  调用 AudioRX_stop...');
                AudioRX_stop();
            }
            if (typeof AudioTX_stop === 'function') {
                console.log('  调用 AudioTX_stop...');
                AudioTX_stop();
            }
            if (typeof ControlTRX_stop === 'function') {
                console.log('  调用 ControlTRX_stop...');
                ControlTRX_stop();
            }
        } catch (e) {
            console.error('关闭电源时出错:', e);
        }
        poweron = false;
        
        // 更新按钮状态
        if (domElements.powerButton) {
            domElements.powerButton.classList.remove('active');
            const icon = domElements.powerButton.querySelector('.power-icon');
            if (icon) icon.textContent = '⏻';
        }
        console.log('🔴 电源已关闭');
        
        // 断开 ATR-1000 代理
        if (typeof ATR1000 !== 'undefined' && ATR1000.onPowerOff) {
            ATR1000.onPowerOff();
        }
        
        // 释放 Wake Lock
        releaseWakeLock();
        
        // 更新连接状态
        mobileState.isConnected = false;
    } else {
        // 连接 - 直接调用底层函数
        console.log('🟢 正在开启电源...');
        
        try {
            if (typeof check_connected === 'function') {
                console.log('  调用 check_connected...');
                check_connected();
            }
            if (typeof AudioRX_start === 'function') {
                console.log('  调用 AudioRX_start...');
                AudioRX_start();
                console.log('  AudioRX_start 完成, wsAudioRX:', typeof wsAudioRX !== 'undefined' ? '已创建' : '未创建');
            }
            if (typeof AudioTX_start === 'function') {
                console.log('  调用 AudioTX_start...');
                AudioTX_start();
                console.log('  AudioTX_start 完成, wsAudioTX:', typeof wsAudioTX !== 'undefined' ? '已创建' : '未创建');
            }
            if (typeof ControlTRX_start === 'function') {
                console.log('  调用 ControlTRX_start...');
                ControlTRX_start();
                console.log('  ControlTRX_start 完成, wsControlTRX:', typeof wsControlTRX !== 'undefined' ? '已创建' : '未创建');
            }
            if (typeof checklatency === 'function') {
                console.log('  调用 checklatency...');
                checklatency();
            }
        } catch (e) {
            console.error('开启电源时出错:', e);
        }
        poweron = true;
        
        // 更新按钮状态
        if (domElements.powerButton) {
            domElements.powerButton.classList.add('active');
            const icon = domElements.powerButton.querySelector('.power-icon');
            if (icon) icon.textContent = '⏼';
        }
        console.log('🟢 电源已开启');
        
        // 连接 ATR-1000 代理
        if (typeof ATR1000 !== 'undefined' && ATR1000.onPowerOn) {
            ATR1000.onPowerOn();
        }
        
        // 更新 Opus 编码状态指示器
        updateOpusStatus();
        
        // 启用 Wake Lock 防止屏幕休眠
        requestWakeLock();
        
        // 更新连接状态
        mobileState.isConnected = true;
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
    
    // 频率格式：kHz 单位，显示 5 位数字（如 07053 = 7053 kHz）
    const freqKhz = Math.floor(mobileState.currentFrequency / 1000);
    const freqStr = freqKhz.toString().padStart(5, '0');
    
    // 更新显示元素（只更新 5 位数字）
    const elements = ['freq-10mhz', 'freq-1mhz', 
                      'freq-100khz', 'freq-10khz', 'freq-1khz'];
    
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
    
    // 自动加载天调参数（如果存在）
    if (typeof ATR1000 !== 'undefined' && ATR1000.isConnected) {
        const tunerRecord = ATR1000.loadTunerForFreq(mobileState.currentFrequency);
        if (tunerRecord) {
            console.log(`🎵 自动加载天调: ${(mobileState.currentFrequency/1000).toFixed(1)}kHz`);
        }
    }
}

// 显示频率输入框
function showFrequencyInput() {
    if (!domElements.freqDisplay || !domElements.freqInput) return;
    
    // 隐藏频率显示
    domElements.freqDisplay.classList.add('hidden-for-input');
    
    // 显示输入框并设置当前频率（kHz）
    domElements.freqInput.classList.add('freq-input-visible');
    const freqKhz = Math.round(mobileState.currentFrequency / 1000);
    domElements.freqInput.value = freqKhz;
    
    // 聚焦并选中文本
    setTimeout(() => {
        domElements.freqInput.focus();
        domElements.freqInput.select();
    }, 50);
    
    console.log('🔢 显示频率输入框');
}

// 隐藏频率输入框
function hideFrequencyInput(apply) {
    if (!domElements.freqDisplay || !domElements.freqInput) return;
    
    // 隐藏输入框
    domElements.freqInput.classList.remove('freq-input-visible');
    domElements.freqDisplay.classList.remove('hidden-for-input');
    
    if (apply) {
        // 解析输入的频率
        let inputVal = domElements.freqInput.value.trim();
        
        // 支持多种格式：7053, 7.053, 7053000, 705300
        let freqHz = 0;
        
        if (inputVal.includes('.')) {
            // MHz 格式：7.053
            freqHz = Math.round(parseFloat(inputVal) * 1000000);
        } else {
            // 纯数字，根据长度判断单位
            const num = parseInt(inputVal, 10);
            if (inputVal.length <= 5) {
                // kHz 格式：7053
                freqHz = num * 1000;
            } else if (inputVal.length <= 7) {
                // Hz 格式：7053000
                freqHz = num;
            } else {
                // 已经是 Hz
                freqHz = num;
            }
        }
        
        // 验证频率范围 (100kHz - 1000MHz)
        if (freqHz >= 100000 && freqHz <= 1000000000) {
            mobileState.currentFrequency = freqHz;
            
            // 更新全局频率变量
            if (typeof TRXfrequency !== 'undefined') {
                TRXfrequency = freqHz;
            }
            
            updateFrequencyDisplay();
            
            // 发送频率到服务器
            if (typeof sendTRXfreq === 'function') {
                sendTRXfreq(freqHz);
            } else {
                sendWebSocketMessage("setFreq:" + freqHz);
            }
            
            console.log(`✅ 设置频率: ${(freqHz/1000).toFixed(1)}kHz`);
        } else {
            console.warn('⚠️ 频率超出范围:', freqHz);
        }
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
    if (!canvas) {
        console.warn('S-Meter canvas 未找到');
        return;
    }
    
    // 确保 SP 变量存在（来自 controls.js）
    if (typeof SP === 'undefined') {
        console.warn('SP 变量未定义，使用默认值');
        // 定义默认 SP 映射表
        window.SP = {0:0,1:25,2:37,3:50,4:62,5:73,6:84,7:98,8:110,9:123,10:144,20:164,30:180,40:202,50:221,60:240};
    }
    
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
    try {
        var micCookie = '';
        if (typeof loadUserAudioSetting === 'function') {
            micCookie = loadUserAudioSetting('mobile_mic_gain', '');
        } else if (typeof getCookie === 'function') {
            micCookie = getCookie('mobile_mic_gain');
        }
        if (micCookie) {
            micValue = parseInt(micCookie);
        }
    } catch (e) {
        console.warn('加载MIC增益失败:', e);
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
    
    // 保存用户专属Cookie
    if (typeof saveUserAudioSetting === 'function') {
        saveUserAudioSetting('mobile_mic_gain', value, 180);
    } else if (typeof setCookie === 'function') {
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
    
    // 保存用户专属Cookie
    if (typeof saveUserAudioSetting === 'function') {
        saveUserAudioSetting('SQUELCH', value, 180);
    } else if (typeof setCookie === 'function') {
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

////////////////////////////////////////////////////////////
// ATR-1000 性能监控工具
////////////////////////////////////////////////////////////
const ATR1000Monitor = {
    messageCount: 0,
    updateCount: 0,
    droppedCount: 0,  // 被节流丢弃的消息数
    lastReportTime: Date.now(),
    latencySum: 0,
    latencyCount: 0,
    
    recordMessage: function() {
        this.messageCount++;
    },
    
    recordUpdate: function() {
        this.updateCount++;
    },
    
    recordDropped: function() {
        this.droppedCount++;
    },
    
    recordLatency: function(ms) {
        this.latencySum += ms;
        this.latencyCount++;
    },
    
    report: function() {
        const now = Date.now();
        const elapsed = now - this.lastReportTime;
        if (elapsed >= 5000) {  // 每5秒报告
            const msgRate = (this.messageCount / elapsed * 1000).toFixed(1);
            const updateRate = (this.updateCount / elapsed * 1000).toFixed(1);
            const ratio = this.messageCount > 0 ? (this.updateCount / this.messageCount * 100).toFixed(1) : 0;
            const avgLatency = this.latencyCount > 0 ? (this.latencySum / this.latencyCount).toFixed(1) : 0;
            
            console.log(
                `%c[ATR-1000监控] 消息:${this.messageCount}(${msgRate}/s) 更新:${this.updateCount}(${updateRate}/s) ` +
                `比例:${ratio}% 丢弃:${this.droppedCount} 延迟:${avgLatency}ms`,
                'color: #2196F3; font-weight: bold'
            );
            
            // 重置计数器
            this.messageCount = 0;
            this.updateCount = 0;
            this.droppedCount = 0;
            this.latencySum = 0;
            this.latencyCount = 0;
            this.lastReportTime = now;
        }
    },
    
    // 显示实时统计（在页面上）
    showStats: function() {
        let statsEl = document.getElementById('atr1000-stats');
        if (!statsEl) {
            statsEl = document.createElement('div');
            statsEl.id = 'atr1000-stats';
            statsEl.style.cssText = 'position:fixed;bottom:10px;right:10px;background:rgba(0,0,0,0.8);color:#0f0;padding:8px 12px;border-radius:4px;font-size:11px;font-family:monospace;z-index:9999;pointer-events:none;';
            document.body.appendChild(statsEl);
        }
        
        const updateStats = () => {
            const avgLatency = this.latencyCount > 0 ? (this.latencySum / this.latencyCount).toFixed(0) : 0;
            statsEl.innerHTML = `ATR-1000: msg=${this.messageCount} upd=${this.updateCount} drop=${this.droppedCount} ${avgLatency}ms`;
            requestAnimationFrame(updateStats);
        };
        updateStats();
    }
};

// 启动监控（开发调试时取消注释）
// ATR1000Monitor.showStats();

////////////////////////////////////////////////////////////
// ATR-1000 天调功率/驻波显示模块
// 仅在 TX 发射期间获取并显示数据，3秒更新一次
// 通过后端 MRRC 代理获取数据，解决 HTTPS 混合内容问题
////////////////////////////////////////////////////////////

const ATR1000 = {
    ws: null,
    worker: null,           // V4.6.0: Web Worker 实例
    useWorker: true,        // V4.6.0: 是否使用 Worker 模式
    isConnected: false,
    lastPower: 0,
    lastSWR: 0,
    maxPower: 100,  // 默认最大功率100W
    _txActive: false,  // TX状态标志（防抖）
    _pollInterval: null,  // 数据轮询定时器引用
    _pendingStart: false,  // 待发送的 start 命令标志
    _msgCount: 0,  // 收到的消息计数
    // 继电器状态
    relayStatus: {
        sw: 0,        // 网络类型: 0=LC, 1=CL
        ind: 0,       // 电感索引
        cap: 0,       // 电容索引
        ind_uh: 0.0,  // 电感值 (uH)
        cap_pf: 0     // 电容值 (pF)
    },
    
    // 初始化 - V4.6.0: 优先使用 Worker 模式
    init: function() {
        console.log('📻 ATR-1000 代理模式初始化...');
        this._reconnectTimer = null;
        this._reconnectAttempts = 0;
        this._maxReconnectAttempts = 10;
        
        // 精简版面板始终显示
        const section = document.getElementById('atr-meter-section');
        if (section) {
            section.classList.remove('hidden');
            section.classList.add('visible');
        }
        
        // V4.6.0: 检查 Worker 支持
        if (this.useWorker && typeof Worker !== 'undefined') {
            this._initWorker();
        } else {
            // 回退到传统 WebSocket 模式
            this.useWorker = false;
            this.connect();
        }
    },
    
    // V4.6.0: 初始化 Worker
    _initWorker: function() {
        try {
            // 创建 Worker
            this.worker = new Worker('atr1000_worker.js');
            
            // Worker 消息处理
            this.worker.onmessage = (e) => {
                const { type, data, msgCount } = e.data;
                
                switch (type) {
                    case 'connected':
                        this.isConnected = true;
                        this._reconnectAttempts = 0;
                        console.log('✅ ATR-1000 Worker 已连接');
                        this.updateStatus('已连接');
                        break;
                        
                    case 'disconnected':
                        this.isConnected = false;
                        console.log('🔴 ATR-1000 Worker 断开');
                        this.updateStatus('断开');
                        this._handleDisconnect();
                        break;
                        
                    case 'meter':
                        // 接收 Worker 解析后的数据，直接更新 DOM
                        this._msgCount = msgCount;
                        this.lastPower = data.power || 0;
                        this.lastSWR = data.swr || 0;
                        
                        // 更新继电器状态
                        if (data.sw !== undefined) {
                            this.relayStatus.sw = data.sw;
                            this.relayStatus.ind = data.ind || 0;
                            this.relayStatus.cap = data.cap || 0;
                            this.relayStatus.ind_uh = data.ind_uh || 0;
                            this.relayStatus.cap_pf = data.cap_pf || 0;
                        }
                        
                        // 直接更新 DOM
                        this._doUpdateDisplay();
                        
                        // 每10条打印日志
                        if (msgCount % 10 === 0) {
                            console.log(`📊 ATR-1000 #${msgCount}: power=${data.power}W, swr=${data.swr.toFixed(2)}`);
                        }
                        break;
                        
                    case 'error':
                        console.error('ATR-1000 Worker 错误:', data);
                        break;
                }
            };
            
            this.worker.onerror = (e) => {
                console.error('ATR-1000 Worker 加载失败:', e);
                // 回退到传统模式
                this.useWorker = false;
                this.connect();
            };
            
            console.log('🚀 ATR-1000 Worker 模式已启用');
            
            // 连接 WebSocket
            this.connect();
            
        } catch (e) {
            console.error('Worker 初始化失败:', e);
            this.useWorker = false;
            this.connect();
        }
    },
    
    // 连接后端 ATR-1000 代理 - V4.6.0: Worker 模式
    connect: function() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const url = `${protocol}//${host}/WSATR1000`;
        
        if (this.useWorker && this.worker) {
            // Worker 模式：发送连接命令给 Worker
            console.log('📻 [Worker模式] 连接 ATR-1000:', url);
            this.worker.postMessage({ type: 'connect', data: { url: url } });
        } else {
            // 传统模式：保持原有逻辑
            this._connectTraditional(url);
        }
    },
    
    // 传统 WebSocket 连接（回退模式）
    _connectTraditional: function(url) {
        // 检查是否已有连接（OPEN 或 CONNECTING 状态）
        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            console.log('📻 ATR-1000 代理已连接或正在连接，跳过');
            return;
        }
        
        // 清理旧连接
        if (this.ws) {
            this.ws.onopen = null;
            this.ws.onclose = null;
            this.ws.onerror = null;
            this.ws.onmessage = null;
            this.ws = null;
        }
        
        try {
            console.log('📻 [传统模式] 连接 ATR-1000 后端代理:', url);
            this.ws = new WebSocket(url);
            
            this.ws.onopen = () => {
                this.isConnected = true;
                this._reconnectAttempts = 0;  // 重置重连计数
                console.log('✅ ATR-1000 后端代理已连接');
                this.updateStatus('已连接');
                
                // 启动心跳保活（连接成功就启动，不只是在 TX 期间）
                this._startHeartbeat();
                
                // 如果在TX期间（_txActive=true 或 _pendingStart=true），发送start命令
                if (this._txActive || this._pendingStart) {
                    this._pendingStart = false;
                    try {
                        this.ws.send(JSON.stringify({action: 'start'}));
                        console.log('📤 发送 ATR-1000 start 命令（重连后恢复）');
                    } catch (e) {
                        console.error('发送 start 命令失败:', e);
                    }
                    
                    // 显示面板（使用CSS类）
                    const section = document.getElementById('atr-meter-section');
                    if (section) {
                        section.classList.remove('hidden');
                        section.classList.add('visible');
                    }
                }
            };
            
            this.ws.onclose = () => {
                this.isConnected = false;
                console.log('🔴 ATR-1000 后端代理断开');
                this.updateStatus('断开');
                
                // 停止心跳
                this._stopHeartbeat();
                
                // 自动重连（最多尝试 10 次，每次间隔 3 秒）
                if (this._reconnectAttempts < this._maxReconnectAttempts) {
                    this._reconnectAttempts++;
                    console.log(`🔄 ATR-1000 尝试重连 (${this._reconnectAttempts}/${this._maxReconnectAttempts})...`);
                    this._reconnectTimer = setTimeout(() => {
                        this.connect();
                    }, 3000);
                } else {
                    console.log('❌ ATR-1000 重连失败次数过多，停止重连');
                }
            };
            
            this.ws.onerror = (err) => {
                console.error('❌ ATR-1000 后端代理错误:', err);
                this.updateStatus('连接失败');
            };
            
            this.ws.onmessage = (event) => {
                // V4.4.20: 减少日志输出，避免阻塞控制台
                // PTT 期间音频编码占用主线程，减少日志有助于性能
                this.handleMessage(event.data);
            };
        } catch (e) {
            console.error('❌ ATR-1000 后端代理连接异常:', e);
        }
    },
    
    // 断开连接 - V4.6.0: Worker 模式
    disconnect: function() {
        if (this.useWorker && this.worker) {
            // Worker 模式：发送断开命令
            this.worker.postMessage({ type: 'disconnect' });
        } else if (this.ws) {
            // 传统模式：只有在本 OPEN 状态时才发送 stop 消息
            if (this.ws.readyState === WebSocket.OPEN) {
                try {
                    this.ws.send(JSON.stringify({action: 'stop'}));
                } catch (e) {
                    console.log('📻 ATR-1000 发送停止消息失败:', e);
                }
            }
            // 无论什么状态都关闭连接
            try {
                this.ws.close();
            } catch (e) {
                // 忽略关闭错误
            }
            this.ws = null;
        }
        this.isConnected = false;
    },
    
    // 处理接收的消息 (JSON 格式)
    handleMessage: function(data) {
        try {
            const msg = JSON.parse(data.trim());
            
            if (msg.type === 'atr1000_meter') {
                this._msgCount++;
                this._lastUpdateTime = Date.now();
                this._processMessage(msg);
                
                // 每10条消息打印一次日志确认数据正常
                if (this._msgCount % 10 === 0) {
                    console.log(`📊 ATR-1000 #${this._msgCount}: power=${msg.power}W, swr=${msg.swr.toFixed(2)}`);
                }
            }
        } catch (e) {
            // 静默处理错误
        }
    },
    
    // 实际处理消息数据 - 简化版，专注于快速 DOM 更新
    _processMessage: function(msg) {
        // 更新值
        this.lastPower = msg.power || 0;
        this.lastSWR = msg.swr || 0;
        
        // 更新继电器状态
        if (msg.sw !== undefined) {
            this.relayStatus.sw = msg.sw;
            this.relayStatus.ind = msg.ind || 0;
            this.relayStatus.cap = msg.cap || 0;
            this.relayStatus.ind_uh = msg.ind_uh || 0;
            this.relayStatus.cap_pf = msg.cap_pf || 0;
        }
        
        // 直接更新 DOM（不经过其他逻辑）
        this._doUpdateDisplay();
    },
    
    // 设置继电器参数
    setRelay: function(sw, ind, cap) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                action: 'set_relay',
                sw: sw,
                ind: ind,
                cap: cap
            }));
            console.log(`🎛️ 设置继电器: SW=${sw}, IND=${ind}, CAP=${cap}`);
        }
    },
    
    // 启动自动调谐
    startTune: function(mode = 2) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                action: 'tune',
                mode: mode
            }));
            console.log(`🔧 启动调谐: mode=${mode}`);
        }
    },
    
    // 保存当前天调参数
    saveCurrentTuner: function() {
        // 获取当前频率
        const freqInput = document.getElementById('freq_disp');
        const freq = freqInput ? parseInt(freqInput.textContent.replace(/\D/g, '')) : 0;
        
        if (freq === 0) {
            alert('无法获取当前频率');
            return;
        }
        
        // 保存到本地存储
        const tunerData = {
            freq: freq,
            sw: this.relayStatus.sw,
            ind: this.relayStatus.ind,
            cap: this.relayStatus.cap,
            ind_uh: this.relayStatus.ind_uh,
            cap_pf: this.relayStatus.cap_pf,
            swr: this.lastSWR,
            power: this.lastPower,
            timestamp: new Date().toISOString()
        };
        
        // 获取现有记录
        let records = JSON.parse(localStorage.getItem('atr1000_tuner_records') || '[]');
        
        // 检查是否有相同频率的记录
        const existingIndex = records.findIndex(r => Math.abs(r.freq - freq) < 10000);
        if (existingIndex >= 0) {
            // 更新现有记录
            records[existingIndex] = tunerData;
        } else {
            // 添加新记录
            records.push(tunerData);
        }
        
        localStorage.setItem('atr1000_tuner_records', JSON.stringify(records));
        console.log('💾 保存天调参数:', tunerData);
        alert(`已保存天调参数: ${(freq/1000).toFixed(1)}kHz, SWR=${this.lastSWR}`);
    },
    
    // 加载天调参数
    loadTunerForFreq: function(freq) {
        const records = JSON.parse(localStorage.getItem('atr1000_tuner_records') || '[]');
        
        // 查找最接近的频率记录
        let bestMatch = null;
        let minDiff = Infinity;
        
        for (const record of records) {
            const diff = Math.abs(record.freq - freq);
            if (diff < minDiff && diff < 50000) {  // 50kHz 范围内
                minDiff = diff;
                bestMatch = record;
            }
        }
        
        if (bestMatch) {
            // 设置继电器参数
            this.setRelay(bestMatch.sw, bestMatch.ind, bestMatch.cap);
            console.log(`📥 加载天调参数: ${(freq/1000).toFixed(1)}kHz -> ${(bestMatch.freq/1000).toFixed(1)}kHz`);
            return bestMatch;
        }
        
        return null;
    },
    
    // 更新显示 - 使用 RAF 优化
    updateDisplay: function() {
        // 使用 requestAnimationFrame 批量处理 DOM 更新
        // 直接执行 DOM 更新（不使用 RAF 批处理，避免消息丢失）
        this._doUpdateDisplay();
    },
    
    // 实际执行 DOM 更新 - V4.4.20 优化：减少日志输出
    _doUpdateDisplay: function() {
        try {
            const powerEl = document.getElementById('atr-power');
            const swrEl = document.getElementById('atr-swr');
            const powerBar = document.getElementById('atr-power-bar');
            const swrBar = document.getElementById('atr-swr-bar');
            
            const power = this.lastPower;
            const swr = this.lastSWR;
            const maxPower = this.maxPower;
            
            if (powerEl) {
                // 直接更新文本
                powerEl.textContent = power;
                
                // 根据功率设置颜色
                const colorClass = power > maxPower * 0.8 ? 'high' : power > maxPower * 0.5 ? 'medium' : 'low';
                powerEl.dataset.powerLevel = colorClass;
                powerEl.style.color = colorClass === 'high' ? '#f44336' : colorClass === 'medium' ? '#ff9800' : '#4CAF50';
            }
            
            if (swrEl) {
                // 直接更新文本
                swrEl.textContent = swr.toFixed(2);
                
                // 根据 SWR 设置颜色
                const swrClass = swr >= 3 ? 'danger' : swr >= 2 ? 'warning' : 'normal';
                swrEl.dataset.swrLevel = swrClass;
                swrEl.style.color = swrClass === 'danger' ? '#f44336' : swrClass === 'warning' ? '#ff9800' : '#4CAF50';
            }
            
            // 更新功率条
            if (powerBar) {
                const powerPercent = Math.min(100, (power / maxPower) * 100);
                powerBar.style.width = powerPercent + '%';
                
                // 功率条颜色
                const barClass = powerPercent > 80 ? 'high' : powerPercent > 50 ? 'medium' : 'low';
                powerBar.dataset.barLevel = barClass;
                if (barClass === 'high') {
                    powerBar.style.background = 'linear-gradient(90deg, #4CAF50, #ff9800, #f44336)';
                } else if (barClass === 'medium') {
                    powerBar.style.background = 'linear-gradient(90deg, #4CAF50, #ff9800)';
                } else {
                    powerBar.style.background = '#4CAF50';
                }
            }
            
            // 更新 SWR 条
            if (swrBar) {
                // SWR 1.0-3.0 映射到 0-100%
                let swrPercent = 0;
                if (swr >= 3) {
                    swrPercent = 100;
                } else if (swr >= 1) {
                    swrPercent = ((swr - 1) / 2) * 100;
                }
                swrBar.style.width = swrPercent + '%';
                
                // SWR 条颜色
                const swrBarClass = swr >= 3 ? 'danger' : swr >= 2 ? 'warning' : 'normal';
                swrBar.dataset.swrLevel = swrBarClass;
                swrBar.style.background = swrBarClass === 'danger' ? '#f44336' : swrBarClass === 'warning' ? '#ff9800' : '#4CAF50';
            }
            
            // 更新继电器状态显示
        const relayInfo = document.getElementById('atr-relay-info');
        if (relayInfo) {
            const swText = this.relayStatus.sw === 0 ? 'LC' : 'CL';
            const newText = `${swText} | L: ${this.relayStatus.ind_uh.toFixed(2)}µH (${this.relayStatus.ind}) | C: ${this.relayStatus.cap_pf}pF (${this.relayStatus.cap})`;
            if (relayInfo.textContent !== newText) {
                relayInfo.textContent = newText;
            }
        }
        } catch (e) {
            console.error('❌ _doUpdateDisplay 错误:', e);
        }
    },
    
    // 显示天调记录列表
    showTunerRecords: function() {
        const records = JSON.parse(localStorage.getItem('atr1000_tuner_records') || '[]');
        
        if (records.length === 0) {
            alert('暂无天调记录\n\n在发射时点击"保存"按钮可保存当前天调参数');
            return;
        }
        
        // 按频率排序
        records.sort((a, b) => a.freq - b.freq);
        
        // 创建列表 HTML
        let html = '<div style="max-height: 300px; overflow-y: auto;">';
        html += '<table style="width: 100%; font-size: 12px; border-collapse: collapse;">';
        html += '<tr style="background: #f0f0f0;"><th style="padding: 8px; text-align: left;">频率</th><th style="padding: 8px;">SWR</th><th style="padding: 8px;">类型</th><th style="padding: 8px;">操作</th></tr>';
        
        for (const record of records) {
            const swText = record.sw === 0 ? 'LC' : 'CL';
            const freqStr = (record.freq / 1000).toFixed(1) + 'kHz';
            html += `<tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 8px;">${freqStr}</td>
                <td style="padding: 8px; text-align: center; color: ${record.swr < 1.5 ? '#4CAF50' : record.swr < 2 ? '#ff9800' : '#f44336'}">${record.swr.toFixed(2)}</td>
                <td style="padding: 8px; text-align: center;">${swText}</td>
                <td style="padding: 8px; text-align: center;">
                    <button onclick="ATR1000.applyTunerRecord(${record.freq})" style="padding: 4px 8px; font-size: 11px; background: #2196F3; color: white; border: none; border-radius: 4px; cursor: pointer;">应用</button>
                </td>
            </tr>`;
        }
        
        html += '</table></div>';
        html += '<div style="margin-top: 10px; text-align: center;">';
        html += '<button onclick="ATR1000.clearTunerRecords()" style="padding: 8px 16px; background: #f44336; color: white; border: none; border-radius: 4px; cursor: pointer;">清空所有</button>';
        html += '</div>';
        
        // 使用简单的模态框显示
        const modal = document.createElement('div');
        modal.id = 'tuner-records-modal';
        modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 10000;';
        modal.innerHTML = `
            <div style="background: white; border-radius: 12px; padding: 20px; max-width: 90%; width: 360px; max-height: 80%; overflow-y: auto;">
                <h3 style="margin: 0 0 15px 0; color: #333;">📋 天调记录 (${records.length}条)</h3>
                ${html}
                <button onclick="document.getElementById('tuner-records-modal').remove()" style="width: 100%; margin-top: 15px; padding: 10px; background: #666; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px;">关闭</button>
            </div>
        `;
        document.body.appendChild(modal);
        
        // 点击背景关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    },
    
    // 应用天调记录
    applyTunerRecord: function(freq) {
        const records = JSON.parse(localStorage.getItem('atr1000_tuner_records') || '[]');
        const record = records.find(r => r.freq === freq);
        
        if (record) {
            this.setRelay(record.sw, record.ind, record.cap);
            
            // 关闭模态框
            const modal = document.getElementById('tuner-records-modal');
            if (modal) modal.remove();
            
            console.log(`✅ 应用天调参数: ${(freq/1000).toFixed(1)}kHz`);
        }
    },
    
    // 清空所有记录
    clearTunerRecords: function() {
        if (confirm('确定要清空所有天调记录吗？')) {
            localStorage.removeItem('atr1000_tuner_records');
            
            // 关闭模态框
            const modal = document.getElementById('tuner-records-modal');
            if (modal) modal.remove();
            
            console.log('🗑️ 已清空所有天调记录');
        }
    },
    
    // 更新连接状态
    updateStatus: function(status) {
        const statusEl = document.getElementById('atr-status');
        if (statusEl) {
            statusEl.textContent = status;
            statusEl.className = 'atr-meter-status';
            if (status === '已连接') {
                statusEl.classList.add('connected');
            } else if (status === '断开' || status === '连接失败' || status === '设备离线') {
                statusEl.classList.add('disconnected');
            }
        }
    },
    
    // Power 开启时预连接 WebSocket（精简版面板始终显示）
    onPowerOn: function() {
        console.log('📻 Power 开启，预连接 ATR-1000 代理 WebSocket');
        
        // 精简版面板始终显示（显示 "--" 直到有数据）
        const section = document.getElementById('atr-meter-section');
        if (section) {
            section.classList.remove('hidden');
            section.classList.add('visible');
        }
        
        // 建立连接但不发送start命令
        if (!this.isConnected) {
            this.connect();
        }
    },
    
    // Power 关闭时断开
    onPowerOff: function() {
        console.log('📻 Power 关闭，断开 ATR-1000 代理');
        this.disconnect();
        // 精简版面板保持显示，不断开时显示 "--"
    },
    
    // 启动心跳保活 - V4.6.0: Worker 模式由 Worker 内部管理
    _startHeartbeat: function() {
        if (this.useWorker && this.worker) {
            // Worker 模式：发送启动心跳命令
            this.worker.postMessage({ type: 'startHeartbeat' });
            console.log('💓 ATR-1000 Worker 心跳已启动');
        } else {
            // 传统模式
            this._stopHeartbeat();  // 先停止旧的心跳
            this._lastSyncTime = 0;  // 初始化上次同步时间
            this._heartbeatInterval = setInterval(() => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    const now = Date.now();
                    // V4.5.5: 最小间隔 250ms（从500ms优化）
                    if (now - this._lastSyncTime >= 250) {
                        try {
                            this.ws.send(JSON.stringify({action: 'sync'}));
                            this._lastSyncTime = now;
                        } catch (e) {
                            console.log('💓 ATR-1000 sync 发送失败:', e);
                        }
                    }
                }
            }, 250);  // 每0.25秒检查一次（V4.5.5优化）
            console.log('💓 ATR-1000 心跳已启动 (0.25s sync interval, 高频更新)');
        }
    },
    
    // 停止心跳 - V4.6.0: Worker 模式
    _stopHeartbeat: function() {
        if (this.useWorker && this.worker) {
            // Worker 模式：发送停止心跳命令
            this.worker.postMessage({ type: 'stopHeartbeat' });
            console.log('💓 ATR-1000 Worker 心跳已停止');
        } else if (this._heartbeatInterval) {
            clearInterval(this._heartbeatInterval);
            this._heartbeatInterval = null;
            console.log('💓 ATR-1000 心跳已停止');
        }
    },
    
    // 定期请求数据（已禁用 - 使用推送模式）
    startDataPolling: function() {
        // 推送模式：后端主动推送数据，无需轮询
        console.log('📊 ATR-1000 使用推送模式（无需轮询）');
    },
    
    // 停止数据轮询
    stopDataPolling: function() {
        if (this._pollInterval) {
            clearInterval(this._pollInterval);
            this._pollInterval = null;
            console.log('🛑 ATR-1000 数据轮询已停止');
        }
    },
    
    // TX 开始时调用 - V4.4.16: 不发送 start/stop 命令，使用与 TUNE 相同的方式
    onTXStart: function() {
        // 防抖：如果已经启动则跳过
        if (this._txActive) {
            console.log('📻 ATR-1000 已在 TX 模式，跳过重复启动');
            return;
        }
        this._txActive = true;
        
        console.log('📻 TX 开始（不发送 start 命令，依赖心跳同步）');
        
        // V4.4.16: 不再发送 start 命令，让数据通过心跳机制自然流动
        // 这与 TUNE 模式一致
        // 重置消息计数
        this._msgCount = 0;
    },
    
    // TX 结束时调用 - V4.4.16: 不发送 start/stop 命令，与 TUNE 方式一致
    onTXStop: function() {
        console.log('🛑 ATR-1000 onTXStop 被调用, _txActive=', this._txActive);
        
        // 防抖：如果已经停止则跳过
        if (!this._txActive) {
            console.log('📻 ATR-1000 已在 RX 模式，跳过重复停止');
            return;
        }
        this._txActive = false;
        
        console.log('📻 TX 结束（不发送 stop 命令，依赖心跳同步）');
        
        // 清理重试定时器
        if (this._startRetryTimer) {
            clearTimeout(this._startRetryTimer);
            this._startRetryTimer = null;
        }
        
        // 清理待更新数据
        if (this._updateTimer) {
            clearTimeout(this._updateTimer);
            this._updateTimer = null;
        }
        this._pendingUpdate = null;
        
        // V4.4.16: 不再发送 stop 命令，保持数据流持续
        // 心跳机制会持续同步数据
        
        // 面板保持显示（精简版始终可见）
        console.log('✅ ATR-1000 面板保持显示（精简版）');
    },
    
    // V4.6.0: 处理断开连接（Worker 和传统模式共用）
    _handleDisconnect: function() {
        this._stopHeartbeat();
        
        // 自动重连
        if (this._reconnectAttempts < this._maxReconnectAttempts) {
            this._reconnectAttempts++;
            const delay = Math.min(1000 * this._reconnectAttempts, 10000);
            console.log(`📻 ATR-1000 尝试重连 (${this._reconnectAttempts}/${this._maxReconnectAttempts})...`);
            
            if (this._reconnectTimer) {
                clearTimeout(this._reconnectTimer);
            }
            this._reconnectTimer = setTimeout(() => {
                this.connect();
            }, delay);
        } else {
            console.log('📻 ATR-1000 重连次数超限，停止重连');
        }
    }
};

// 初始化 ATR-1000 模块
document.addEventListener('DOMContentLoaded', function() {
    ATR1000.init();
    console.log('📻 ATR-1000 后端代理模块已加载（通过 Unix Socket 连接独立代理）');
});

// 导出 ATR-1000 控制函数
window.ATR1000 = ATR1000;

// TX按钮完全重构 - 优化 TX→RX 切换
// 专门针对PAD触摸屏优化

// 全局TX状态管理 - 简化版本
let TXState = {
    isPressed: false,
    isInitialized: false,
    element: null,
    touchId: null,  // 跟踪当前触摸ID
    startTime: 0
};

// 核心TX控制函数 - 优化 TX→RX 切换
async function TXControl(action) {
    const timestamp = new Date().toISOString().substr(11, 12);
    console.log(`[${timestamp}] 🎯 TX控制: ${action}, 当前状态: ${TXState.isPressed}, 系统状态: ${poweron}`);
    
    // 检查系统状态
    if (!poweron && action === 'start') {
        console.log(`[${timestamp}] ❌ 系统未启动，无法开始TX`);
        return false;
    }
    
    // 检查按钮元素
    if (!TXState.element) {
        console.log(`[${timestamp}] ❌ TX按钮元素未找到`);
        return false;
    }
    
    if (action === 'start' && !TXState.isPressed) {
        console.log(`[${timestamp}] 🚀 开始TX流程`);
        
        // 开始TX
        TXState.isPressed = true;
        TXState.startTime = Date.now();
        
        // 视觉反馈
        console.log(`[${timestamp}] 🎨 应用视觉反馈`);
        TXState.element.style.transform = 'scale(0.95)';
        TXState.element.style.backgroundColor = '#ff4444';
        TXState.element.classList.add('button_pressed');
        TXState.element.classList.remove('button_unpressed');
        
        // 触觉反馈
        if (navigator.vibrate) {
            console.log(`[${timestamp}] 📳 触觉反馈`);
            navigator.vibrate(50);
        }
        
        // 执行TX功能 - 优先发送PTT命令
        try {
            // 0. 立即PTT优先
            console.log(`[${timestamp}] 🔧 按下即PTT:true`);
            if (typeof sendTRXptt === 'function') {
                sendTRXptt(true);
                console.log(`[${timestamp}] 📡 已发送PTT:true`);
            }

            // 1. 同步开始录音
            console.log(`[${timestamp}] 🔧 同步初始化TX`);
            // 先检查 TX WebSocket 状态
            if (typeof isTXWebSocketReady === "function" && !isTXWebSocketReady()) {
                console.warn("⚠️ TX WebSocket 未就绪，等待连接...");
                // 等待最多 500ms
                let waited = 0;
                while (waited < 500) {
                    if (isTXWebSocketReady()) break;
                    waited += 50;
                }
                if (!isTXWebSocketReady()) {
                    console.error("❌ TX WebSocket 连接超时，无法开始TX");
                    TXState.isPressed = false;
                    return false;
                }
            }
            toggleRecord(true);

            // 2. 发送预热帧（减少到3帧，更快完成）
            for(let i = 0; i < 3; i++) {
                setTimeout(() => {
                    try {
                        if (wsAudioTX && wsAudioTX.readyState === WebSocket.OPEN && typeof ap === 'object') {
                            const warmup = new Float32Array(160);
                            for(let j = 0; j < warmup.length; j++) {
                                warmup[j] = Math.sin(j * 0.2) * 0.05;
                            }
                            if (encode && ap && ap.opusEncoder) {
                                const packets = ap.opusEncoder.encode_float(warmup);
                                for (let k = 0; k < packets.length; k++) { 
                                    wsAudioTX.send(packets[k]); 
                                }
                            } else if (ap && ap.i16arr) {
                                wsAudioTX.send(new Int16Array(warmup.length));
                            }
                        }
                    } catch(e) { 
                        console.warn(`TX warmup skip frame ${i}:`, e); 
                    }
                }, i * 3); // 更快的预热
            }

            // 3. 执行其他功能
            console.log(`[${timestamp}] 🔧 调用button_pressed()`);
            button_pressed();
            
            console.log(`[${timestamp}] 🔧 调用toggleaudioRX()`);
            toggleaudioRX();
            
            // PTT状态已激活
            if (typeof window.updatePTTStatus === 'function') {
                window.updatePTTStatus(true);
            }
            
            // 触发 ATR-1000 天调显示（仅TX期间）
            if (typeof window.ATR1000 !== 'undefined') {
                window.ATR1000.onTXStart();
            }
            
            console.log(`[${timestamp}] ✅ TX开始成功`);
            return true;
        } catch (error) {
            console.error(`[${timestamp}] ❌ TX开始失败:`, error);
            TXState.isPressed = false;
            return false;
        }
    }
    else if (action === 'stop' && TXState.isPressed) {
        console.log(`[${timestamp}] 🛑 停止TX流程`);
        
        // 停止TX
        TXState.isPressed = false;
        
        // 恢复视觉状态
        console.log(`[${timestamp}] 🎨 恢复视觉状态`);
        TXState.element.style.transform = 'scale(1)';
        TXState.element.style.backgroundColor = '';
        TXState.element.classList.remove('button_pressed');
        TXState.element.classList.add('button_unpressed');
        
        // 执行TX停止功能 - 优化顺序
        try {
            // 1. 首先发送PTT停止命令（最高优先级）
            console.log(`[${timestamp}] 🔧 调用sendTRXptt(false)`);
            if (typeof sendTRXptt === 'function') {
                sendTRXptt(false);
                console.log(`[${timestamp}] 📡 PTT停止命令已发送`);
            }
            
            // 2. 立即清除RX音频缓冲区（关键优化）
            console.log(`[${timestamp}] 🧹 清除RX音频缓冲区`);
            
            // 清除累积缓冲区
            if (typeof AudioRX_audiobuffer !== 'undefined') {
                AudioRX_audiobuffer = [];
                console.log(`[${timestamp}] ✅ AudioRX_audiobuffer 已清空`);
            }
            
            // 清除 AudioWorklet 缓冲区
            if (typeof AudioRX_source_node !== 'undefined' && AudioRX_source_node) {
                if (AudioRX_source_node.port) {
                    try {
                        AudioRX_source_node.port.postMessage({type: 'flush'});
                        console.log(`[${timestamp}] ✅ AudioWorklet 缓冲区已清除`);
                    } catch(e) {
                        console.log(`[${timestamp}] ⚠️ 清除AudioWorklet缓冲区时出错:`, e);
                    }
                }
                // 重置累积缓冲区（如果有）
                if (typeof window.__rxAccumulatedBuffer !== 'undefined') {
                    window.__rxAccumulatedBuffer = [];
                    window.__rxTotalSamples = 0;
                }
            }
            
            // 3. 停止录音
            console.log(`[${timestamp}] 🔧 调用toggleRecord()`);
            toggleRecord();
            
            // 4. 恢复RX音频
            console.log(`[${timestamp}] 🔧 调用toggleaudioRX()`);
            toggleaudioRX();
            
            // 5. 其他清理
            console.log(`[${timestamp}] 🔧 调用button_unpressed()`);
            button_unpressed();
            
            // PTT状态已释放
            if (typeof window.updatePTTStatus === 'function') {
                window.updatePTTStatus(false);
            }
            
            // 停止 ATR-1000 天调显示
            if (typeof window.ATR1000 !== 'undefined') {
                window.ATR1000.onTXStop();
            }
            
            console.log(`[${timestamp}] ✅ TX停止成功 - RX缓冲区已清除`);
            return true;
        } catch (error) {
            console.error(`[${timestamp}] ❌ TX停止失败:`, error);
            return false;
        }
    }
    else {
        console.log(`[${timestamp}] ⚠️ 忽略操作 - action: ${action}, isPressed: ${TXState.isPressed}`);
    }
    
    return false;
}

// 检查触摸是否在按钮区域内
function isTouchInButton(touch, button) {
    const rect = button.getBoundingClientRect();
    const x = touch.clientX;
    const y = touch.clientY;
    return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
}

// 初始化TX按钮
function initTXButton(button) {
    if (!button) {
        button = document.getElementById('TX-record') || document.getElementById('ptt-btn');
    }
    
    if (!button) {
        console.error('❌ TX按钮元素未找到');
        return false;
    }
    
    console.log('🚀 开始初始化TX按钮:', button.id);
    
    if (TXState.isInitialized) {
        console.log('⚠️ TX按钮已经初始化，跳过');
        return true;
    }
    
    TXState.element = button;
    
    const newButton = button.cloneNode(true);
    button.parentNode.replaceChild(newButton, button);
    TXState.element = newButton;
    
    console.log('🧹 清除现有事件监听器');
    
    // 触摸开始事件
    newButton.addEventListener('touchstart', function(e) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        
        if (TXState.touchId !== null) return;
        
        const touch = e.touches[0];
        TXState.touchId = touch.identifier;
        
        if (!isTouchInButton(touch, this)) {
            TXState.touchId = null;
            return;
        }
        
        TXControl('start');
    }, { passive: false, capture: true });
    
    // 触摸结束事件
    newButton.addEventListener('touchend', function(e) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        
        const touch = e.changedTouches[0];
        if (touch.identifier !== TXState.touchId) return;
        
        TXControl('stop');
        TXState.touchId = null;
    }, { passive: false, capture: true });
    
    // 触摸取消事件
    newButton.addEventListener('touchcancel', function(e) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        
        TXControl('stop');
        TXState.touchId = null;
    }, { passive: false, capture: true });
    
    // 触摸移动事件
    newButton.addEventListener('touchmove', function(e) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        
        if (!TXState.isPressed || TXState.touchId === null) return;
        
        const touch = e.touches[0];
        if (touch.identifier === TXState.touchId) {
            if (!isTouchInButton(touch, this)) {
                TXControl('stop');
                TXState.touchId = null;
            }
        }
    }, { passive: false, capture: true });
    
    // 鼠标事件
    newButton.addEventListener('mousedown', function(e) {
        e.preventDefault();
        e.stopPropagation();
        TXControl('start');
    });
    
    newButton.addEventListener('mouseup', function(e) {
        e.preventDefault();
        e.stopPropagation();
        TXControl('stop');
    });
    
    newButton.addEventListener('mouseleave', function(e) {
        TXControl('stop');
    });
    
    newButton.addEventListener('contextmenu', function(e) {
        e.preventDefault();
    });
    
    newButton.style.touchAction = 'manipulation';
    newButton.style.userSelect = 'none';
    newButton.style.webkitTouchCallout = 'none';
    newButton.style.webkitUserSelect = 'none';
    
    TXState.isInitialized = true;
    
    console.log('✅ TX按钮初始化完成');
    return true;
}

// 确保TX按钮初始化
function ensureTXButtonReady() {
    if (TXState.isInitialized) return true;
    
    let txButton = document.getElementById('TX-record') || document.getElementById('ptt-btn');
    
    if (!txButton) {
        if (document.getElementById('ptt-btn')) {
            return true;
        }
        setTimeout(ensureTXButtonReady, 100);
        return false;
    }
    
    return initTXButton(txButton);
}

document.addEventListener('DOMContentLoaded', function() {
    ensureTXButtonReady();
});

if (document.readyState !== 'loading') {
    ensureTXButtonReady();
}

window.addEventListener('load', function() {
    ensureTXButtonReady();
});

function TXtogle(state) {
    if (state === "True" || state === true) {
        return TXControl('start');
    } else if (state === "False" || state === false) {
        return TXControl('stop');
    } else {
        return TXControl(TXState.isPressed ? 'stop' : 'start');
    }
}

console.log('🎯 TX按钮系统加载完成 (优化版)');

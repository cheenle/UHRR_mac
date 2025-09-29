// TX按钮完全重构 - 简单、稳定、可靠的按住功能
// 专门针对PAD触摸屏优化

// 全局TX状态管理 - 简化版本
let TXState = {
    isPressed: false,
    isInitialized: false,
    element: null,
    touchId: null,  // 跟踪当前触摸ID
    startTime: 0
};

// 核心TX控制函数 - 详细日志版本
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
            // 0. 立即PTT优先，避免按下阶段无发射
            console.log(`[${timestamp}] 🔧 按下即PTT:true`);
            if (typeof sendTRXptt === 'function') {
                sendTRXptt(true);
                console.log(`[${timestamp}] 📡 已发送PTT:true`);
            }

            // 1. 同步开始录音（发送 m:... 的 TX_init），并行让后端就绪
            console.log(`[${timestamp}] 🔧 同步初始化TX（toggleRecord(true)）`);
            toggleRecord(true);

            // 2. 异步预热静音帧，避免阻塞UI
            setTimeout(() => {
                try {
                    if (wsAudioTX && wsAudioTX.readyState === WebSocket.OPEN && typeof ap === 'object') {
                        const warmup = new Float32Array(160);
                        if (encode && ap && ap.opusEncoder) {
                            const packets = ap.opusEncoder.encode_float(warmup);
                            for (let i = 0; i < packets.length; i++) { wsAudioTX.send(packets[i]); }
                        } else if (ap && ap.i16arr) {
                            wsAudioTX.send(new Int16Array(warmup.length));
                        }
                    }
                } catch(e) { console.warn('TX warmup skip:', e); }
            }, 0);

            // 3. PTT后再补3帧静音（异步分批），确保后端超时窗口中有数据
            [20, 50, 80].forEach((delay)=>{
                setTimeout(() => {
                    try {
                        if (wsAudioTX && wsAudioTX.readyState === WebSocket.OPEN && typeof ap === 'object') {
                            const warm2 = new Float32Array(160);
                            if (encode && ap && ap.opusEncoder) {
                                const packets = ap.opusEncoder.encode_float(warm2);
                                for (let i = 0; i < packets.length; i++) { wsAudioTX.send(packets[i]); }
                            } else if (ap && ap.i16arr) {
                                wsAudioTX.send(new Int16Array(warm2.length));
                            }
                        }
                    } catch(e) { /* ignore */ }
                }, delay);
            });
            
            // 2. 然后执行其他功能
            console.log(`[${timestamp}] 🔧 调用button_pressed()`);
            button_pressed();
            
            // toggleRecord(true) 已提前调用
            
            console.log(`[${timestamp}] 🔧 调用toggleaudioRX()`);
            toggleaudioRX();
            
            console.log(`[${timestamp}] ✅ TX开始成功 - 所有函数调用完成`);
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
        
        // 执行TX停止功能 - 分步执行并记录
        try {
            console.log(`[${timestamp}] 🔧 调用button_unpressed()`);
            button_unpressed();
            
            console.log(`[${timestamp}] 🔧 调用toggleRecord()`);
            toggleRecord();
            
            console.log(`[${timestamp}] 🔧 调用toggleaudioRX()`);
            toggleaudioRX();
            
            console.log(`[${timestamp}] 🔧 调用sendTRXptt(false)`);
            if (typeof sendTRXptt === 'function') {
                sendTRXptt(false);
                console.log(`[${timestamp}] 📡 PTT停止命令已发送，WebSocket状态:`, wsControlTRX ? wsControlTRX.readyState : 'undefined');
            } else {
                console.error(`[${timestamp}] ❌ sendTRXptt函数未定义！`);
            }
            
            console.log(`[${timestamp}] ✅ TX停止成功 - 所有函数调用完成`);
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

// 初始化TX按钮 - 完全重构版本
function initTXButton() {
    console.log('🚀 开始初始化TX按钮');
    
    // 获取TX按钮元素
    const txButton = document.getElementById('TX-record');
    if (!txButton) {
        console.error('❌ TX按钮元素未找到');
        return false;
    }
    
    // 检查是否已经初始化
    if (TXState.isInitialized) {
        console.log('⚠️ TX按钮已经初始化，跳过');
        return true;
    }
    
    // 保存按钮引用
    TXState.element = txButton;
    
    // 完全清除现有事件监听器
    const newButton = txButton.cloneNode(true);
    txButton.parentNode.replaceChild(newButton, txButton);
    TXState.element = newButton;
    
    console.log('🧹 清除现有事件监听器');
    
    // 触摸开始事件
    newButton.addEventListener('touchstart', function(e) {
        const timestamp = new Date().toISOString().substr(11, 12);
        console.log(`[${timestamp}] 👆 触摸开始事件触发`);
        
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        
        // 只处理第一个触摸点
        if (TXState.touchId !== null) {
            console.log(`[${timestamp}] ⚠️ 已有触摸在进行中，忽略 (touchId: ${TXState.touchId})`);
            return;
        }
        
        const touch = e.touches[0];
        TXState.touchId = touch.identifier;
        console.log(`[${timestamp}] 📍 触摸点ID: ${touch.identifier}, 坐标: (${touch.clientX}, ${touch.clientY})`);
        
        // 检查是否在按钮区域内
        if (!isTouchInButton(touch, this)) {
            console.log(`[${timestamp}] ⚠️ 触摸不在按钮区域内，清除touchId`);
            TXState.touchId = null;
            return;
        }
        
        console.log(`[${timestamp}] ✅ 触摸在按钮区域内，开始TX`);
        // 开始TX
        TXControl('start');
        
    }, { passive: false, capture: true });
    
    // 触摸结束事件
    newButton.addEventListener('touchend', function(e) {
        const timestamp = new Date().toISOString().substr(11, 12);
        console.log(`[${timestamp}] 👆 触摸结束事件触发`);
        
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        
        // 检查是否是当前触摸点
        const touch = e.changedTouches[0];
        console.log(`[${timestamp}] 📍 结束触摸点ID: ${touch.identifier}, 当前跟踪ID: ${TXState.touchId}`);
        
        if (touch.identifier !== TXState.touchId) {
            console.log(`[${timestamp}] ⚠️ 不是当前触摸点，忽略`);
            return;
        }
        
        console.log(`[${timestamp}] ✅ 确认是当前触摸点，停止TX`);
        // 停止TX
        TXControl('stop');
        
        // 清除触摸ID
        TXState.touchId = null;
        console.log(`[${timestamp}] 🧹 清除触摸ID`);
        
    }, { passive: false, capture: true });
    
    // 触摸取消事件
    newButton.addEventListener('touchcancel', function(e) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        
        console.log('👆 触摸取消');
        
        // 强制停止TX
        TXControl('stop');
        
        // 清除触摸ID
        TXState.touchId = null;
        
    }, { passive: false, capture: true });
    
    // 触摸移动事件 - 检查是否移出按钮
    newButton.addEventListener('touchmove', function(e) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        
        // 如果没有活跃的TX，忽略
        if (!TXState.isPressed || TXState.touchId === null) {
            return;
        }
        
        // 检查当前触摸点是否还在按钮内
        const touch = e.touches[0];
        if (touch.identifier === TXState.touchId) {
            if (!isTouchInButton(touch, this)) {
                console.log('👆 手指移出按钮区域，停止TX');
                TXControl('stop');
                TXState.touchId = null;
            }
        }
        
    }, { passive: false, capture: true });
    
    // 鼠标事件（桌面兼容）
    newButton.addEventListener('mousedown', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        console.log('🖱️ 鼠标按下');
        TXControl('start');
    });
    
    newButton.addEventListener('mouseup', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        console.log('🖱️ 鼠标释放');
        TXControl('stop');
    });
    
    newButton.addEventListener('mouseleave', function(e) {
        console.log('🖱️ 鼠标离开');
        TXControl('stop');
    });
    
    // 防止长按菜单
    newButton.addEventListener('contextmenu', function(e) {
        e.preventDefault();
    });
    
    // 优化触摸响应
    newButton.style.touchAction = 'manipulation';
    newButton.style.userSelect = 'none';
    newButton.style.webkitTouchCallout = 'none';
    newButton.style.webkitUserSelect = 'none';
    
    // 标记为已初始化
    TXState.isInitialized = true;
    
    console.log('✅ TX按钮初始化完成');
    return true;
}

// 确保TX按钮初始化的函数
function ensureTXButtonReady() {
    if (TXState.isInitialized) {
        return true;
    }
    
    const txButton = document.getElementById('TX-record');
    if (!txButton) {
        console.log('⏳ TX按钮尚未创建，等待100ms后重试');
        setTimeout(ensureTXButtonReady, 100);
        return false;
    }
    
    return initTXButton();
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log('📱 DOMContentLoaded - 初始化TX按钮');
    ensureTXButtonReady();
});

// 如果页面已经加载完成，立即初始化
if (document.readyState === 'loading') {
    console.log('📱 页面加载中，等待DOMContentLoaded');
} else {
    console.log('📱 页面已加载完成，立即初始化TX按钮');
    ensureTXButtonReady();
}

// 额外的保险措施
window.addEventListener('load', function() {
    console.log('📱 window.onload - 确保TX按钮初始化');
    ensureTXButtonReady();
});

// 兼容性：提供TXtogle函数（向后兼容）
function TXtogle(state) {
    if (state === "True" || state === true) {
        return TXControl('start');
    } else if (state === "False" || state === false) {
        return TXControl('stop');
    } else {
        // 切换模式
        return TXControl(TXState.isPressed ? 'stop' : 'start');
    }
}

console.log('🎯 TX按钮系统加载完成');
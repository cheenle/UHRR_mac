/**
 * tune_cq.js — Tune and CQ functionality extracted from controls.js
 *
 * Globals referenced (remain in controls.js):
 *   poweron, wsControlTRX, PTT_USER_INTENT, PTT_DEVICE_STATE, ATR1000
 */

// Tune单音生成功能
var isTuning = false;

function startTune() {
    if (isTuning) {
        console.log('Tune已经在运行中');
        return;
    }

    if (!poweron) {
        alert('请先开启电源');
        return;
    }

    if (!wsControlTRX || wsControlTRX.readyState !== WebSocket.OPEN) {
        alert('控制通道未连接');
        return;
    }

    try {
        // 发送tune命令到服务器
        wsControlTRX.send("tune:true");
        console.log('🎵 发送Tune启动命令到服务器');

        // 同步设置PTT用户意图状态，避免"PTT状态不一致"警告
        PTT_USER_INTENT = true;
        PTT_DEVICE_STATE = true;

        isTuning = true;

        // V4.5.8: 启动 ATR-1000 数据流
        if (typeof ATR1000 !== 'undefined' && ATR1000.onTXStart) {
            ATR1000.onTXStart();
        }

        // Tune 发射建立后，若 SWR 偏高则联动 ATR-1000 执行完整调谐。
        if (typeof ATR1000 !== 'undefined' && ATR1000.autoFullTuneIfHighSWR) {
            ATR1000.autoFullTuneIfHighSWR();
        }

        // 更新状态显示
        var tuneStatus = document.getElementById('tune-status');
        if (tuneStatus) {
            tuneStatus.textContent = '发射中...';
            tuneStatus.style.color = '#4CAF50';
        }

        // 更新按钮状态
        var tuneBtn = document.getElementById('Tune-button');
        if (tuneBtn) {
            tuneBtn.className = 'button_pressed';
            tuneBtn.style.background = '#FF5722';
        }

    } catch (error) {
        console.error('Tune启动失败:', error);
        alert('Tune启动失败: ' + error.message);
    }
}

function stopTune() {
    if (!isTuning) return;

    try {
        // 发送tune停止命令到服务器
        if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
            wsControlTRX.send("tune:false");
            console.log('🛑 发送Tune停止命令到服务器');
        }

        // 同步设置PTT用户意图状态
        PTT_USER_INTENT = false;
        PTT_DEVICE_STATE = false;

        isTuning = false;

        // 更新状态显示
        var tuneStatus = document.getElementById('tune-status');
        if (tuneStatus) {
            tuneStatus.textContent = '停止';
            tuneStatus.style.color = '#ff4444';
        }

        // 更新按钮状态
        var tuneBtn = document.getElementById('Tune-button');
        if (tuneBtn) {
            tuneBtn.className = 'button_unpressed';
            tuneBtn.style.background = '#FF9800';
        }

        // V4.5.8: 停止 ATR-1000 数据流并清零功率显示
        if (typeof ATR1000 !== 'undefined' && ATR1000.cancelTuneAssist) {
            ATR1000.cancelTuneAssist();
        }
        if (typeof ATR1000 !== 'undefined' && ATR1000.onTXStop) {
            ATR1000.onTXStop();
        }
        // 清零功率/SWR 显示
        if (typeof ATR1000 !== 'undefined' && ATR1000.clearDisplay) {
            ATR1000.clearDisplay();
        }

        console.log('🛑 Tune停止');

    } catch (error) {
        console.error('Tune停止失败:', error);
    }
}

// CQ呼叫功能
var isCQing = false;

function startCQ() {
    if (isCQing) {
        console.log('CQ已经在运行中');
        return;
    }

    if (!poweron) {
        alert('请先开启电源');
        return;
    }

    if (!wsControlTRX || wsControlTRX.readyState !== WebSocket.OPEN) {
        alert('控制通道未连接');
        return;
    }

    try {
        // 发送cq命令到服务器
        wsControlTRX.send("cq:true");
        console.log('📻 发送CQ启动命令到服务器');

        // 同步设置PTT用户意图状态，避免"PTT状态不一致"警告
        PTT_USER_INTENT = true;
        PTT_DEVICE_STATE = true;

        isCQing = true;

        // 更新状态显示
        var cqStatus = document.getElementById('cq-status');
        if (cqStatus) {
            cqStatus.textContent = '呼叫中...';
            cqStatus.style.color = '#4CAF50';
        }

        // 更新按钮状态
        var cqBtn = document.getElementById('CQ-button');
        if (cqBtn) {
            cqBtn.className = 'button_pressed';
            cqBtn.style.background = '#FF5722';
            cqBtn.disabled = true; // 禁用按钮防止重复点击
        }

    } catch (error) {
        console.error('CQ启动失败:', error);
        alert('CQ启动失败: ' + error.message);
    }
}

function stopCQ() {
    console.log('🛑 stopCQ被调用，isCQing=', isCQing);
    if (!isCQing) {
        console.log('🛑 isCQing为false，直接返回');
        return;
    }

    try {
        // 发送cq停止命令到服务器
        if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
            wsControlTRX.send("cq:false");
            console.log('🛑 发送CQ停止命令到服务器');
        }

        // 同步设置PTT用户意图状态
        PTT_USER_INTENT = false;
        PTT_DEVICE_STATE = false;

        isCQing = false;

        // 更新状态显示
        var cqStatus = document.getElementById('cq-status');
        if (cqStatus) {
            cqStatus.textContent = '停止';
            cqStatus.style.color = '#ff4444';
        }

        // 更新桌面端按钮状态
        var cqBtn = document.getElementById('CQ-button');
        if (cqBtn) {
            cqBtn.className = 'button_unpressed';
            cqBtn.style.background = '#9C27B0';
            cqBtn.disabled = false; // 启用按钮
        }

        // 恢复移动端按钮样式
        var mobileCqBtn = document.getElementById('cq-btn');
        if (mobileCqBtn) {
            mobileCqBtn.style.background = '';
            mobileCqBtn.disabled = false;
        }

        console.log('🛑 CQ停止');

    } catch (error) {
        console.error('CQ停止失败:', error);
    }
}

// 添加CQ自动停止的监听器
function onCQComplete() {
    console.log('📻 onCQComplete被调用，isCQing=', isCQing);
    if (!isCQing) {
        console.log('📻 isCQing为false，跳过停止');
        return;
    }

    console.log('📻 CQ播放完成，自动停止');
    stopCQ();

    // 调用移动端处理函数（如果存在）
    if (typeof handleCQCompleteMobile === 'function') {
        console.log('📻 调用handleCQCompleteMobile');
        handleCQCompleteMobile();
    }
}

// 在WebSocket消息处理中添加CQ完成通知
// 这个函数会在控制WebSocket接收到cq:complete消息时被调用
function handleCQComplete() {
    onCQComplete();
}

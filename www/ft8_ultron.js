/**
 * ULTRON FT8 Web Interface
 * 与 ft8_integration.py 后端深度集成
 */

// 全局状态
const state = {
    isConnected: false,
    isListening: false,
    isCQActive: false,
    currentTarget: null,
    decodes: [],
    workedDxcc: new Set(),
    settings: {
        callsign: localStorage.getItem('ultron_callsign') || '',
        grid: localStorage.getItem('ultron_grid') || '',
        threshold: parseInt(localStorage.getItem('ultron_threshold')) || -20,
        autoReply: localStorage.getItem('ultron_auto_reply') !== 'false'
    },
    stats: {
        today: 0,
        worked: 0,
        new: 0,
        decodes: 0
    }
};

// WebSocket 连接
let ws = null;
let reconnectTimer = null;

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    updateStats();
    connectWebSocket();
    logMessage('系统初始化完成');
});

// WebSocket 连接
function connectWebSocket() {
    if (ws && ws.readyState === WebSocket.OPEN) return;
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/WSFT8`;
    
    try {
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            state.isConnected = true;
            updateConnectionStatus(true);
            logMessage('WebSocket 连接成功', 'success');
            
            // 发送设置
            sendCommand('get_status');
        };
        
        ws.onmessage = (event) => {
            handleMessage(event.data);
        };
        
        ws.onclose = () => {
            state.isConnected = false;
            updateConnectionStatus(false);
            logMessage('WebSocket 连接断开，5秒后重试...', 'error');
            
            // 重连
            reconnectTimer = setTimeout(connectWebSocket, 5000);
        };
        
        ws.onerror = (error) => {
            logMessage('WebSocket 错误: ' + error.message, 'error');
        };
        
    } catch (err) {
        logMessage('连接失败: ' + err.message, 'error');
        reconnectTimer = setTimeout(connectWebSocket, 5000);
    }
}

// 处理消息
function handleMessage(data) {
    try {
        const msg = JSON.parse(data);
        
        switch (msg.type) {
            case 'decode':
                handleDecode(msg.data);
                break;
            case 'status':
                handleStatus(msg.data);
                break;
            case 'status_change':
                handleStatusChange(msg.data);
                break;
            case 'qso_logged':
                handleQSOLogged(msg.data);
                break;
            case 'command_ack':
                handleCommandAck(msg.data);
                break;
        }
    } catch (e) {
        console.error('解析消息错误:', e);
    }
}

// 处理解码消息
function handleDecode(data) {
    state.stats.decodes++;
    updateStats();
    
    // 添加到列表
    const decode = {
        timestamp: data.timestamp,
        snr: data.snr,
        delta_f: data.delta_f,
        mode: data.mode,
        message: data.message,
        status: data.status,
        dxcc_id: data.dxcc_id,
        dxcc_name: data.dxcc_name,
        dxcc_flag: data.dxcc_flag,
        priority: data.priority
    };
    
    state.decodes.unshift(decode);
    if (state.decodes.length > 100) {
        state.decodes.pop();
    }
    
    // 渲染
    renderDecodes();
    
    // 高优先级提示
    if (data.priority >= 10) {
        showNotification(`🎯 新目标: ${data.message.split(' ')[1] || 'Unknown'}`, data.dxcc_name);
    }
}

// 处理状态消息
function handleStatus(data) {
    document.getElementById('software-name').textContent = data.software || '-';
    document.getElementById('frequency').textContent = data.frequency ? 
        (data.frequency / 1000000).toFixed(3) + ' MHz' : '-';
    document.getElementById('mode').textContent = data.mode || '-';
    document.getElementById('band').textContent = data.band || '-';
}

// 处理状态变化
function handleStatusChange(data) {
    if (data.sendcq) {
        state.isCQActive = true;
        document.getElementById('cq-status').textContent = '活跃';
        document.getElementById('cq-status').classList.add('active');
    }
    
    if (data.current_call) {
        state.currentTarget = data.current_call;
        document.getElementById('target-call').textContent = data.current_call;
        document.getElementById('current-target').textContent = data.current_call;
        document.getElementById('target-panel').style.display = 'block';
    }
    
    logMessage(data.message || '状态已更新');
}

// 处理 QSO 记录
function handleQSOLogged(data) {
    state.stats.today++;
    state.stats.worked++;
    updateStats();
    
    logMessage(`✓ QSO 记录: ${data.dx_call}`, 'success');
    
    // 检查是否新 DXCC
    if (!state.workedDxcc.has(data.dxcc_id)) {
        state.workedDxcc.add(data.dxcc_id);
        state.stats.new++;
        updateStats();
        showNotification('🎉 新 DXCC!', data.dxcc_name);
    }
}

// 处理命令确认
function handleCommandAck(data) {
    logMessage(`命令执行: ${data.command}`);
}

// 渲染解码列表
function renderDecodes() {
    const container = document.getElementById('decodes-list');
    
    if (state.decodes.length === 0) {
        container.innerHTML = `
            <div class="decode-empty" style="text-align: center; padding: 40px; color: var(--text-muted);">
                等待解码数据...<br>
                <small>请启动 JTDX/WSJT-X 并确保 UDP 端口 2237 开启</small>
            </div>
        `;
        return;
    }
    
    container.innerHTML = state.decodes.map(decode => {
        let cssClass = 'decode-item';
        if (decode.priority >= 10) cssClass += ' priority-high';
        else if (decode.priority >= 5) cssClass += ' priority-medium';
        if (decode.status === '--') cssClass += ' worked';
        
        let statusClass = '';
        if (decode.status === '>>' || decode.status === '->') statusClass = 'target';
        else if (decode.status === '--') statusClass = 'worked';
        else if (decode.status === 'Lo') statusClass = 'low';
        
        return `
            <div class="${cssClass}" onclick="selectDecode('${decode.message}')">
                <span class="decode-time">${decode.timestamp}</span>
                <span class="decode-snr ${decode.snr < -20 ? 'low' : ''}">${decode.snr}</span>
                <span class="decode-delta">${decode.delta_f}</span>
                <span class="decode-status ${statusClass}">${decode.status || '  '}</span>
                <span class="decode-message">${decode.message}</span>
            </div>
        `;
    }).join('');
}

// 发送命令
function sendCommand(command, params = {}) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        logMessage('未连接，无法发送命令', 'error');
        return;
    }
    
    ws.send(JSON.stringify({
        type: 'command',
        command: command,
        params: params
    }));
}

// 控制函数
function toggleListen() {
    state.isListening = !state.isListening;
    
    const btn = document.getElementById('btn-listen');
    if (state.isListening) {
        btn.textContent = '停止监听';
        btn.classList.remove('primary');
        btn.classList.add('danger');
        document.getElementById('btn-cq').disabled = false;
        logMessage('开始监听 JTDX/WSJT-X 数据');
    } else {
        btn.textContent = '开始监听';
        btn.classList.remove('danger');
        btn.classList.add('primary');
        document.getElementById('btn-cq').disabled = true;
        document.getElementById('btn-stop-cq').disabled = true;
        logMessage('停止监听');
    }
}

function sendCQ() {
    sendCommand('send_cq');
    document.getElementById('btn-stop-cq').disabled = false;
    document.getElementById('btn-cq').disabled = true;
}

function stopCQ() {
    sendCommand('stop_cq');
    document.getElementById('btn-stop-cq').disabled = true;
    document.getElementById('btn-cq').disabled = false;
    document.getElementById('target-panel').style.display = 'none';
}

function replyToTarget() {
    if (state.currentTarget) {
        sendCommand('reply', {
            callsign: state.currentTarget,
            message: `${state.currentTarget} ${state.settings.callsign} ${state.settings.grid || 'AA00'}`
        });
    }
}

function skipTarget() {
    if (state.currentTarget) {
        sendCommand('exclude', { callsign: state.currentTarget });
        document.getElementById('target-panel').style.display = 'none';
        logMessage(`跳过: ${state.currentTarget}`);
    }
}

function selectDecode(message) {
    // 解析消息获取呼号
    const parts = message.split(' ');
    if (parts.length > 1) {
        const call = parts[1];
        document.getElementById('current-target').textContent = call;
        document.getElementById('target-panel').style.display = 'block';
    }
}

// 设置面板
function toggleSettings() {
    const panel = document.getElementById('settings-panel');
    panel.classList.toggle('active');
}

function loadSettings() {
    document.getElementById('setting-callsign').value = state.settings.callsign;
    document.getElementById('setting-grid').value = state.settings.grid;
    document.getElementById('setting-threshold').value = state.settings.threshold;
    document.getElementById('setting-auto-reply').checked = state.settings.autoReply;
}

function saveSettings() {
    state.settings.callsign = document.getElementById('setting-callsign').value.toUpperCase();
    state.settings.grid = document.getElementById('setting-grid').value.toUpperCase();
    state.settings.threshold = parseInt(document.getElementById('setting-threshold').value);
    state.settings.autoReply = document.getElementById('setting-auto-reply').checked;
    
    localStorage.setItem('ultron_callsign', state.settings.callsign);
    localStorage.setItem('ultron_grid', state.settings.grid);
    localStorage.setItem('ultron_threshold', state.settings.threshold);
    localStorage.setItem('ultron_auto_reply', state.settings.autoReply);
    
    // 发送到后端
    sendCommand('settings', state.settings);
    
    toggleSettings();
    logMessage('设置已保存');
}

// 更新状态
function updateConnectionStatus(connected) {
    const indicator = document.getElementById('connection-status');
    const text = indicator.querySelector('.status-text');
    
    if (connected) {
        indicator.classList.remove('disconnected');
        indicator.classList.add('connected');
        text.textContent = '在线';
    } else {
        indicator.classList.remove('connected');
        indicator.classList.add('disconnected');
        text.textContent = '离线';
    }
}

function updateStats() {
    document.getElementById('stat-today').textContent = state.stats.today;
    document.getElementById('stat-worked').textContent = state.stats.worked;
    document.getElementById('stat-new').textContent = state.stats.new;
    document.getElementById('stat-decodes').textContent = state.stats.decodes;
}

// 日志
function logMessage(message, type = 'info') {
    const panel = document.getElementById('log-panel');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    panel.appendChild(entry);
    panel.scrollTop = panel.scrollHeight;
    
    // 限制日志数量
    while (panel.children.length > 50) {
        panel.removeChild(panel.firstChild);
    }
}

// 通知
function showNotification(title, body) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, { body });
    } else {
        logMessage(`${title}: ${body}`, 'success');
    }
}

// 请求通知权限
if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
}

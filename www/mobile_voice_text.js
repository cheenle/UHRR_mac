/**
 * 语音文字助手 - 前端
 * 通过WebSocket与后端语音服务通信
 * 只传输文本，不处理音频
 */

// ============================================
// 配置
// ============================================
const CONFIG = {
    // 统一使用MRRC主服务的WebSocket端点(8877)，共享TLS配置
    get WS_URL() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const hostname = window.location.hostname || 'localhost';
        const port = window.location.port;
        return protocol + '//' + hostname + (port ? ':' + port : '') + '/WSVoiceAssistant';
    },
    RECONNECT_INTERVAL: 3000,
    MAX_RECONNECT_ATTEMPTS: 5
};

// ============================================
// 全局状态
// ============================================
const State = {
    ws: null,
    connected: false,
    reconnectAttempts: 0,
    reconnectTimer: null,
    
    // 服务状态
    asr: {
        running: false,
        available: false
    },
    tts: {
        available: false,
        speaking: false
    },
    
    // ATR-1000状态
    atr: {
        ws: null,
        connected: false,
        power: 0,
        swr: 1.0,
        sw: 0,
        ind: 0,
        cap: 0
    },
    
    // 语音识别状态(通过主服务WSVoice)
    asr: {
        recording: false
    },
    
    // 对话历史
    messages: [],
    sendHistory: JSON.parse(localStorage.getItem('vt_send_history') || '[]'),
    
    // PTT状态
    pttActive: false,
    
    // 文件选择状态
    files: {
        list: [],
        selected: null,
        recognized: new Set(),  // 已识别的文件名集合
        recognizing: null  // 正在识别的文件名
    }
};

// ============================================
// 初始化
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    console.log('[VoiceText] 初始化...');

    initWebSocket();
    initATRWebSocket();
    initEventListeners();
    loadSendHistory();
    updateFrequencyDisplay();

    console.log('[VoiceText] 初始化完成');
});

// ============================================
// WebSocket连接
// ============================================
function initWebSocket() {
    console.log('[VoiceText] 连接WebSocket:', CONFIG.WS_URL);
    
    updateConnectionStatus('connecting');
    
    try {
        State.ws = new WebSocket(CONFIG.WS_URL);
        
        State.ws.onopen = () => {
            console.log('[VoiceText] WebSocket已连接');
            State.connected = true;
            State.reconnectAttempts = 0;
            updateConnectionStatus('connected');
            showToast('语音服务已连接', 'success');
            
            // 启动心跳
            startHeartbeat();
        };
        
        State.ws.onmessage = (event) => {
            handleMessage(JSON.parse(event.data));
        };
        
        State.ws.onerror = (error) => {
            console.error('[VoiceText] WebSocket错误:', error);
            updateConnectionStatus('error');
        };
        
        State.ws.onclose = () => {
            console.log('[VoiceText] WebSocket已断开');
            State.connected = false;
            stopHeartbeat();
            updateConnectionStatus('disconnected');
            
            // 自动重连
            if (State.reconnectAttempts < CONFIG.MAX_RECONNECT_ATTEMPTS) {
                State.reconnectAttempts++;
                console.log(`[VoiceText] ${CONFIG.RECONNECT_INTERVAL/1000}秒后尝试重连 (${State.reconnectAttempts}/${CONFIG.MAX_RECONNECT_ATTEMPTS})`);
                
                State.reconnectTimer = setTimeout(() => {
                    initWebSocket();
                }, CONFIG.RECONNECT_INTERVAL);
            } else {
                showToast('无法连接到语音服务，请检查后端服务是否已启动', 'error');
            }
        };
        
    } catch (e) {
        console.error('[VoiceText] 创建WebSocket失败:', e);
        updateConnectionStatus('error');
        showToast('连接失败: ' + e.message, 'error');
    }
}

// 心跳检测
let heartbeatInterval = null;
let lastPongTime = Date.now();

function startHeartbeat() {
    // 每30秒发送一次ping
    heartbeatInterval = setInterval(() => {
        if (State.connected && State.ws.readyState === WebSocket.OPEN) {
            sendMessage({ action: 'ping' });
            
            // 检查是否收到pong（超过60秒未收到则认为断开）
            if (Date.now() - lastPongTime > 60000) {
                console.warn('[VoiceText] 心跳超时，重新连接');
                State.ws.close();
            }
        }
    }, 30000);
}

function stopHeartbeat() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
    }
}

function handleMessage(data) {
    console.log('[VoiceText] 收到消息:', data.type);
    
    switch (data.type) {
        case 'connected':
            // 服务已连接，更新状态
            State.asr.available = data.asr_ready;
            State.tts.available = data.tts_ready;
            updateServiceStatus();
            break;
            
        case 'asr_result':
            // 语音识别结果
            handleASRResult(data);
            break;
            
        case 'listening_started':
            State.asr.running = true;
            updateServiceStatus();
            showToast('语音识别已启动');
            break;
            
        case 'listening_stopped':
            State.asr.running = false;
            updateServiceStatus();
            break;
            
        case 'tts_started':
            State.tts.speaking = true;
            updateTransmitUI(true);
            break;
            
        case 'tts_completed':
            State.tts.speaking = false;
            updateTransmitUI(false);
            
            // 添加到对话记录
            addMessage('sent', data.text);
            
            // 保存到历史
            saveToHistory(data.text);
            
            // 清空输入
            document.getElementById('reply-input').value = '';
            updateTransmitButtons();
            
            showToast('语音已发射');
            break;
            
        case 'error':
            showToast(data.message, 'error');
            State.tts.speaking = false;
            updateTransmitUI(false);
            break;
            
        case 'pong':
            // 心跳响应
            lastPongTime = Date.now();
            break;
            
        case 'recordings_list':
            handleRecordingsList(data);
            break;
            
        case 'file_recognized':
            handleFileRecognized(data);
            break;
            
        case 'recognition_progress':
            handleRecognitionProgress(data);
            break;
    }
}

function sendMessage(data) {
    if (State.ws && State.ws.readyState === WebSocket.OPEN) {
        State.ws.send(JSON.stringify(data));
    } else {
        showToast('语音服务未连接', 'error');
    }
}

// ============================================
// 事件处理
// ============================================
function initEventListeners() {
    // 返回按钮
    document.getElementById('back-btn').addEventListener('click', () => {
        window.location.href = 'mobile_modern.html';
    });
    
    // 启动/停止语音识别
    document.getElementById('toggle-asr-btn').addEventListener('click', toggleASR);
    
    // 刷新文件列表
    document.getElementById('refresh-files-btn').addEventListener('click', () => {
        loadRecordingsList();
        showToast('正在刷新文件列表...', 'info');
    });
    
    // 识别选中文件
    document.getElementById('select-file-btn').addEventListener('click', recognizeSelectedFile);
    
    // 清空识别
    document.getElementById('clear-asr-btn').addEventListener('click', () => {
        document.getElementById('asr-display').innerHTML = `
            <div class="vt-placeholder">
                <div class="placeholder-icon">🎙️</div>
                <div>识别内容已清空</div>
            </div>
        `;
        document.getElementById('confidence-bar').style.display = 'none';
    });
    
    // 清空对话
    document.getElementById('clear-chat-btn').addEventListener('click', () => {
        document.getElementById('chat-list').innerHTML = '';
        State.messages = [];
    });
    
    // 快捷回复
    document.getElementById('quick-reply-btn').addEventListener('click', () => {
        document.getElementById('quick-reply-modal').classList.add('active');
    });
    
    document.getElementById('close-quick-reply').addEventListener('click', () => {
        document.getElementById('quick-reply-modal').classList.remove('active');
    });
    
    // 快捷回复项
    document.querySelectorAll('.vt-quick-reply-item').forEach(item => {
        item.addEventListener('click', () => {
            const text = item.dataset.text;
            document.getElementById('reply-input').value = text;
            document.getElementById('quick-reply-modal').classList.remove('active');
            updateTransmitButtons();
        });
    });
    
    // 历史记录
    document.getElementById('history-btn').addEventListener('click', showHistoryModal);
    document.getElementById('close-history').addEventListener('click', () => {
        document.getElementById('history-modal').classList.remove('active');
    });
    
    // 输入框变化
    document.getElementById('reply-input').addEventListener('input', updateTransmitButtons);
    
    // 试听按钮
    document.getElementById('preview-btn').addEventListener('click', previewTTS);
    
    // 发射按钮（按住说话）
    const transmitBtn = document.getElementById('transmit-btn');
    
    transmitBtn.addEventListener('mousedown', startTransmit);
    transmitBtn.addEventListener('mouseup', stopTransmit);
    transmitBtn.addEventListener('mouseleave', stopTransmit);
    
    transmitBtn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        startTransmit();
    });
    transmitBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        stopTransmit();
    });
    
    // 停止按钮
    document.getElementById('stop-btn').addEventListener('click', stopTTS);
    
    // 点击弹窗背景关闭
    document.querySelectorAll('.vt-modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });
}

// ============================================
// 语音识别控制
// ============================================
function toggleASR() {
    const btn = document.getElementById('toggle-asr-btn');
    const fileSelector = document.getElementById('file-selector');
    
    if (State.asr.running) {
        // 停止识别，隐藏文件选择器
        sendMessage({ action: 'stop_listening' });
        btn.textContent = '启动';
        btn.classList.remove('active');
        fileSelector.style.display = 'none';
    } else {
        // 显示文件选择器
        if (!State.asr.available) {
            showToast('语音识别服务不可用', 'error');
            return;
        }
        
        // 切换到文件选择模式
        btn.textContent = '关闭';
        btn.classList.add('active');
        State.asr.running = true;
        
        // 显示文件选择器并加载文件列表
        fileSelector.style.display = 'block';
        loadRecordingsList();
        
        // 清空之前的显示
        document.getElementById('asr-display').innerHTML = `
            <div class="vt-placeholder">
                <div class="placeholder-icon">📁</div>
                <div>请选择要识别的录音文件</div>
                <div class="placeholder-hint">从上方列表选择一个WAV文件进行识别</div>
            </div>
        `;
    }
}

// ============================================
// 文件选择功能
// ============================================

function loadRecordingsList() {
    // 请求文件列表
    sendMessage({ action: 'get_recordings' });
    document.getElementById('file-list').innerHTML = '<div class="file-list-placeholder">正在加载文件列表...</div>';
}

function renderFileList(files) {
    State.files.list = files;
    const container = document.getElementById('file-list');
    
    if (files.length === 0) {
        container.innerHTML = '<div class="file-list-placeholder">暂无录音文件</div>';
        return;
    }
    
    let html = '<ul class="file-list">';
    files.forEach((file, index) => {
        const isRecognized = State.files.recognized.has(file.filename);
        const isRecognizing = State.files.recognizing === file.filename;
        const isSelected = State.files.selected === file.filename;
        
        const sizeMB = (file.size / 1024 / 1024).toFixed(2);
        const date = new Date(file.mtime * 1000).toLocaleString('zh-CN', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        let statusClass = 'pending';
        let statusText = '待识别';
        if (isRecognized) {
            statusClass = 'recognized';
            statusText = '已识别';
        } else if (isRecognizing) {
            statusText = '识别中...';
        }
        
        html += `
            <li class="file-item ${isSelected ? 'selected' : ''} ${isRecognized ? 'recognized' : ''} ${isRecognizing ? 'recognizing' : ''}" 
                data-filename="${escapeHtml(file.filename)}"
                onclick="selectFile('${escapeHtml(file.filename)}')">
                <div class="file-checkbox"></div>
                <div class="file-info">
                    <div class="file-name">${escapeHtml(file.filename)}</div>
                    <div class="file-meta">${sizeMB}MB · ${date}</div>
                </div>
                ${file.freq ? `<span class="file-freq">${escapeHtml(file.freq)}</span>` : ''}
                <span class="file-status ${statusClass}">${statusText}</span>
            </li>
        `;
    });
    html += '</ul>';
    
    container.innerHTML = html;
}

function selectFile(filename) {
    State.files.selected = filename;
    
    // 更新UI
    document.querySelectorAll('.file-item').forEach(item => {
        item.classList.remove('selected');
        if (item.dataset.filename === filename) {
            item.classList.add('selected');
        }
    });
    
    // 启用识别按钮
    document.getElementById('select-file-btn').disabled = false;
    
    console.log('[VoiceText] 选中文件:', filename);
}

function recognizeSelectedFile() {
    if (!State.files.selected) {
        showToast('请先选择一个文件', 'warning');
        return;
    }
    
    const filename = State.files.selected;
    
    // 标记为正在识别
    State.files.recognizing = filename;
    renderFileList(State.files.list);
    
    // 发送识别请求
    sendMessage({ 
        action: 'recognize_file',
        filename: filename
    });
    
    // 更新显示区域
    document.getElementById('asr-display').innerHTML = `
        <div class="vt-placeholder">
            <div class="placeholder-icon">🔄</div>
            <div>正在识别...</div>
            <div class="placeholder-hint">${escapeHtml(filename)}</div>
        </div>
    `;
    
    // 禁用按钮
    document.getElementById('select-file-btn').disabled = true;
    document.getElementById('select-file-btn').textContent = '识别中...';
    
    console.log('[VoiceText] 开始识别文件:', filename);
}

function handleFileRecognized(data) {
    const { filename, result } = data;
    
    // 标记为已识别
    State.files.recognized.add(filename);
    State.files.recognizing = null;
    
    // 更新文件列表显示
    renderFileList(State.files.list);
    
    // 恢复按钮
    const btn = document.getElementById('select-file-btn');
    btn.disabled = State.files.selected === null;
    btn.textContent = '识别选中文件';
    
    // 显示识别结果
    const display = document.getElementById('asr-display');
    let html = `
        <div class="final-text">${escapeHtml(result.text)}</div>
    `;
    
    // 显示呼号
    if (result.callsigns && result.callsigns.length > 0) {
        html += `<div class="extracted-callsigns">
            <span class="label">📡 呼号:</span>
            ${result.callsigns.map(c => `<span class="callsign-tag">${escapeHtml(c)}</span>`).join('')}
        </div>`;
    }
    
    // 显示QSO术语
    if (result.qso_terms && result.qso_terms.length > 0) {
        html += `<div class="extracted-terms">
            <span class="label">📋 QSO:</span>
            ${result.qso_terms.map(t => `<span class="term-tag">${escapeHtml(t)}</span>`).join('')}
        </div>`;
    }
    
    display.innerHTML = html;
    
    // 添加到对话记录
    let displayText = result.text;
    if (result.callsigns && result.callsigns.length > 0) {
        displayText += ` [呼号: ${result.callsigns.join(', ')}]`;
    }
    addMessage('received', displayText);
    
    showToast(`识别完成: ${filename}`, 'success');
}

function handleRecognitionProgress(data) {
    if (data.stage === 'processing') {
        document.getElementById('asr-display').innerHTML = `
            <div class="vt-placeholder">
                <div class="placeholder-icon">🔄</div>
                <div>正在处理音频...</div>
                <div class="placeholder-hint">${escapeHtml(data.filename)}</div>
            </div>
        `;
    }
}

function handleRecordingsList(data) {
    renderFileList(data.files);
}

// ============================================
// WebSocket消息处理 - 添加到现有的onMessage中
// ============================================

function handleVoiceAssistantMessage(data) {
    switch(data.type) {
        case 'recordings_list':
            handleRecordingsList(data);
            break;
        case 'file_recognized':
            handleFileRecognized(data);
            break;
        case 'recognition_progress':
            handleRecognitionProgress(data);
            break;
    }
}

function handleASRResult(result) {
    // 更新识别显示
    const display = document.getElementById('asr-display');
    let html = `<div class="final-text">${escapeHtml(result.text)}</div>`;
    
    // 显示呼号
    if (result.callsigns && result.callsigns.length > 0) {
        html += `<div class="extracted-callsigns">
            <span class="label">📡 呼号:</span>
            ${result.callsigns.map(c => `<span class="callsign-tag">${escapeHtml(c)}</span>`).join('')}
        </div>`;
    }
    
    // 显示QSO术语
    if (result.qso_terms && result.qso_terms.length > 0) {
        const uniqueTerms = [...new Set(result.qso_terms.map(t => t.term))];
        html += `<div class="extracted-terms">
            <span class="label">📋 QSO:</span>
            ${uniqueTerms.slice(0, 8).map(t => `<span class="term-tag">${escapeHtml(t)}</span>`).join('')}
        </div>`;
    }
    
    display.innerHTML = html;
    
    // 更新置信度
    const confidencePercent = Math.round((result.confidence || 0.8) * 100);
    document.getElementById('confidence-fill').style.width = confidencePercent + '%';
    document.getElementById('confidence-value').textContent = confidencePercent + '%';
    document.getElementById('confidence-bar').style.display = 'flex';
    
    // 添加到对话记录（包含提取信息）
    let displayText = result.text;
    if (result.callsigns && result.callsigns.length > 0) {
        displayText += ` [呼号: ${result.callsigns.join(', ')}]`;
    }
    addMessage('received', displayText);
}

// ============================================
// 语音合成与发射
// ============================================
function startTransmit() {
    const btn = document.getElementById('transmit-btn');
    if (btn.disabled || btn.classList.contains('active')) return;
    
    const text = document.getElementById('reply-input').value.trim();
    if (!text) {
        showToast('请输入要发送的内容');
        return;
    }
    
    if (!State.tts.available) {
        showToast('语音合成服务不可用', 'error');
        return;
    }
    
    btn.classList.add('active');
    State.pttActive = true;
    
    // 发送到后端进行合成
    const speed = parseFloat(document.getElementById('tts-speed').value);
    sendMessage({
        action: 'tts',
        text: text,
        speed: speed
    });
    
    // 同时通知父窗口启动PTT
    if (window.parent !== window) {
        window.parent.postMessage({ type: 'PTT_START' }, '*');
    }
}

function stopTransmit() {
    const btn = document.getElementById('transmit-btn');
    if (!btn.classList.contains('active')) return;
    
    btn.classList.remove('active');
    State.pttActive = false;
    
    // 停止TTS
    stopTTS();
    
    // 通知父窗口停止PTT
    if (window.parent !== window) {
        window.parent.postMessage({ type: 'PTT_STOP' }, '*');
    }
}

function stopTTS() {
    // 发送停止命令到后端
    // 注意：实际停止需要通过其他方式，如发送abort命令
    State.tts.speaking = false;
    updateTransmitUI(false);
    
    if (window.parent !== window) {
        window.parent.postMessage({ type: 'PTT_STOP' }, '*');
    }
}

function previewTTS() {
    const text = document.getElementById('reply-input').value.trim();
    if (!text) return;
    
    // 试听功能 - 使用浏览器TTS（不发射）
    if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'zh-CN';
        utterance.rate = parseFloat(document.getElementById('tts-speed').value);
        
        document.getElementById('preview-btn').disabled = true;
        
        utterance.onend = () => {
            document.getElementById('preview-btn').disabled = false;
        };
        
        speechSynthesis.speak(utterance);
    }
}

// ============================================
// UI更新
// ============================================
function updateConnectionStatus(status) {
    const indicator = document.getElementById('connection-status');
    indicator.className = 'vt-status-indicator';
    
    switch (status) {
        case 'connected':
            indicator.classList.add('connected');
            indicator.title = '已连接';
            break;
        case 'connecting':
            indicator.classList.add('connecting');
            indicator.title = '连接中...';
            break;
        case 'error':
        case 'disconnected':
            indicator.classList.add('error');
            indicator.title = '连接失败';
            break;
    }
}

function updateServiceStatus() {
    // ASR状态
    const asrEl = document.getElementById('status-asr');
    if (State.asr.running) {
        asrEl.className = 'vt-service-item processing';
        asrEl.querySelector('.service-status').textContent = '运行中';
    } else if (State.asr.available) {
        asrEl.className = 'vt-service-item online';
        asrEl.querySelector('.service-status').textContent = '就绪';
    } else {
        asrEl.className = 'vt-service-item offline';
        asrEl.querySelector('.service-status').textContent = '离线';
    }
    
    // TTS状态
    const ttsEl = document.getElementById('status-tts');
    if (State.tts.speaking) {
        ttsEl.className = 'vt-service-item processing';
        ttsEl.querySelector('.service-status').textContent = '合成中';
    } else if (State.tts.available) {
        ttsEl.className = 'vt-service-item online';
        ttsEl.querySelector('.service-status').textContent = '就绪';
    } else {
        ttsEl.className = 'vt-service-item offline';
        ttsEl.querySelector('.service-status').textContent = '离线';
    }
}

function updateTransmitUI(speaking) {
    document.getElementById('transmit-btn').disabled = speaking;
    document.getElementById('stop-btn').disabled = !speaking;
    document.getElementById('preview-btn').disabled = speaking;
}

function updateTransmitButtons() {
    const hasText = document.getElementById('reply-input').value.trim().length > 0;
    const speaking = State.tts.speaking;
    
    document.getElementById('transmit-btn').disabled = !hasText || speaking;
    document.getElementById('preview-btn').disabled = !hasText || speaking;
}

function addMessage(type, text) {
    const chatList = document.getElementById('chat-list');
    
    const message = document.createElement('div');
    message.className = `vt-message ${type}`;
    
    const time = new Date().toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit'
    });
    
    const avatarText = type === 'received' ? '收' : '发';
    
    message.innerHTML = `
        <div class="vt-message-header">
            <div class="vt-message-avatar">${avatarText}</div>
            <span>${type === 'received' ? '电台接收' : '本台发送'}</span>
        </div>
        <div class="vt-message-content">${escapeHtml(text)}</div>
        <div class="vt-message-time">${time}</div>
    `;
    
    chatList.appendChild(message);
    chatList.scrollTop = chatList.scrollHeight;
    
    // 保存到状态
    State.messages.push({
        type,
        text,
        time
    });
}

// ============================================
// 历史记录
// ============================================
function saveToHistory(text) {
    const item = {
        text,
        time: new Date().toISOString()
    };
    
    State.sendHistory.unshift(item);
    
    // 最多保存50条
    if (State.sendHistory.length > 50) {
        State.sendHistory = State.sendHistory.slice(0, 50);
    }
    
    localStorage.setItem('vt_send_history', JSON.stringify(State.sendHistory));
}

function loadSendHistory() {
    // 历史记录已加载到State中
}

function showHistoryModal() {
    const list = document.getElementById('history-list');
    list.innerHTML = '';
    
    if (State.sendHistory.length === 0) {
        list.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted);">暂无发送历史</div>';
    } else {
        State.sendHistory.forEach(item => {
            const div = document.createElement('div');
            div.className = 'vt-history-item';
            
            const date = new Date(item.time);
            const timeStr = date.toLocaleString('zh-CN');
            
            div.innerHTML = `
                <div>${escapeHtml(item.text)}</div>
                <div class="vt-history-time">${timeStr}</div>
            `;
            
            div.addEventListener('click', () => {
                document.getElementById('reply-input').value = item.text;
                document.getElementById('history-modal').classList.remove('active');
                updateTransmitButtons();
            });
            
            list.appendChild(div);
        });
    }
    
    document.getElementById('history-modal').classList.add('active');
}

// ============================================
// 工具函数
// ============================================
function updateFrequencyDisplay() {
    const freq = localStorage.getItem('currentFreq') || '7053.0';
    document.getElementById('current-freq').textContent = freq + ' kHz';
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('vt-toast');
    toast.textContent = message;
    toast.className = 'vt-toast ' + type + ' show';
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 监听来自父窗口的消息
window.addEventListener('message', (event) => {
    if (event.data.type === 'FREQ_UPDATE') {
        document.getElementById('current-freq').textContent = event.data.freq + ' kHz';
    }
});

// 页面卸载时清理
window.addEventListener('beforeunload', () => {
    if (State.ws) {
        State.ws.close();
    }
    if (State.reconnectTimer) {
        clearTimeout(State.reconnectTimer);
    }
    if (State.atr.ws) {
        State.atr.ws.close();
    }
});

// ============================================
// ATR-1000 WebSocket连接
// ============================================
function initATRWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/WSATR1000`;

    console.log('[VoiceText] 连接ATR-1000:', wsUrl);

    try {
        State.atr.ws = new WebSocket(wsUrl);

        State.atr.ws.onopen = () => {
            console.log('[VoiceText] ATR-1000已连接');
            State.atr.connected = true;
            updateATRStatus();

            // 发送sync请求获取初始数据
            State.atr.ws.send(JSON.stringify({ action: 'sync' }));
        };

        State.atr.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleATRMessage(data);
            } catch (e) {
                console.log('[VoiceText] ATR消息解析失败:', e);
            }
        };

        State.atr.ws.onclose = () => {
            console.log('[VoiceText] ATR-1000连接断开');
            State.atr.connected = false;
            updateATRStatus();

            // 5秒后重连
            setTimeout(initATRWebSocket, 5000);
        };

        State.atr.ws.onerror = (error) => {
            console.error('[VoiceText] ATR-1000错误:', error);
        };
    } catch (e) {
        console.error('[VoiceText] 创建ATR WebSocket失败:', e);
    }
}

function handleATRMessage(data) {
    // 处理功率/驻波数据
    if (data.power !== undefined) {
        State.atr.power = parseFloat(data.power) || 0;
    }
    if (data.swr !== undefined) {
        State.atr.swr = parseFloat(data.swr) || 1.0;
    }
    if (data.sw !== undefined) {
        State.atr.sw = data.sw;
    }
    if (data.ind !== undefined) {
        State.atr.ind = data.ind;
    }
    if (data.cap !== undefined) {
        State.atr.cap = data.cap;
    }

    updateATRDisplay();
}

function updateATRDisplay() {
    const powerEl = document.getElementById('atr-power');
    const swrEl = document.getElementById('atr-swr');
    const lcEl = document.getElementById('atr-lc');

    if (powerEl) {
        powerEl.textContent = State.atr.power.toFixed(0);
    }
    if (swrEl) {
        swrEl.textContent = State.atr.swr.toFixed(1);
    }
    if (lcEl) {
        const swType = State.atr.sw === 0 ? 'LC' : 'CL';
        lcEl.textContent = `${swType} L${State.atr.ind}C${State.atr.cap}`;
    }

    updateATRStatus();
}

function updateATRStatus() {
    const statusEl = document.getElementById('atr-status');
    if (statusEl) {
        const dot = statusEl.querySelector('.status-dot');
        if (State.atr.connected) {
            dot.style.background = '#4caf50';
            statusEl.title = 'ATR-1000已连接';
        } else {
            dot.style.background = '#666';
            statusEl.title = 'ATR-1000未连接';
        }
    }
}

console.log('[VoiceText] 脚本加载完成');

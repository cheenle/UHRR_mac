/**
 * FT8 Mode - MRRC 移动端 FT8 模式
 * 
 * 功能：
 * - 实时解码消息显示
 * - 发送预设和宏
 * - QSO 状态机
 * - 自动回复
 * - 瀑布图显示
 * 
 * 参考：https://documents.roskosch.de/sdr-control-mobile/
 */

////////////////////////////////////////////////////////////
// 全局配置和状态
////////////////////////////////////////////////////////////

const FT8_CONFIG = {
    // FT8 标准参数
    CYCLE_DURATION: 15000,      // 15秒周期
    BANDWIDTH: 50,               // 带宽 Hz
    AUDIO_SAMPLE_RATE: 12000,    // 音频采样率
    
    // 默认频率（各波段FT8频率）
    BAND_FREQUENCIES: {
        '160m': 1840000,
        '80m': 3573000,
        '60m': 5357000,
        '40m': 7074000,
        '30m': 10136000,
        '20m': 14074000,
        '17m': 18100000,
        '15m': 21074000,
        '12m': 24915000,
        '10m': 28074000,
        '6m': 50313000
    },
    
    // 瀑布图配置
    WATERFALL_HEIGHT: 80,
    WATERFALL_HISTORY: 200,      // 保留的历史行数
    
    // 消息解码
    MAX_DECODES: 50,             // 最大显示解码消息数
    DECODE_EXPIRE: 300000        // 5分钟后过期
};

// FT8 状态
const ft8State = {
    // 连接状态
    wsAudioRX: null,
    wsAudioTX: null,
    wsControl: null,
    isConnected: false,
    
    // 发射状态
    isTransmitting: false,
    txEnabled: false,
    txStartTime: null,
    
    // 当前周期
    cycleStart: 0,
    cyclePhase: 0,              // 0-1，表示当前周期进度
    
    // 解码消息
    decodedMessages: [],
    
    // QSO 状态
    qsoState: 'IDLE',           // IDLE, CALLING, ANSWERING, IN_QSO, FINALIZING
    currentQSO: null,
    
    // 设置
    settings: {
        myCallsign: '',
        myGrid: '',
        txPower: 50,
        audioOffset: 1500,
        autoLog: true,
        filterWorked: false,
        autoCQ: false,
        autoCQInterval: 3       // 分钟
    },
    
    // 日志
    qsoLog: [],
    
    // 瀑布图
    waterfallCanvas: null,
    waterfallCtx: null,
    waterfallData: [],
    
    // 已通联呼号（从日志加载）
    workedCallsigns: new Set()
};

////////////////////////////////////////////////////////////
// 初始化
////////////////////////////////////////////////////////////

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 FT8 模式初始化...');
    
    // 初始化瀑布图
    initWaterfall();
    
    // 初始化设置
    loadSettings();
    
    // 绑定事件
    bindEvents();
    
    // 启动时钟
    startClock();
    
    // 启动周期计时器
    startCycleTimer();
    
    // 加载日志
    loadLog();
    
    console.log('✅ FT8 模式初始化完成');
});

////////////////////////////////////////////////////////////
// 事件绑定
////////////////////////////////////////////////////////////

function bindEvents() {
    // TX 标签切换
    document.querySelectorAll('.tx-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            const tabId = this.dataset.tab;
            switchTab(tabId);
        });
    });
    
    // 设置滑块实时更新
    const txPowerSlider = document.getElementById('tx-power');
    if (txPowerSlider) {
        txPowerSlider.addEventListener('input', function() {
            document.getElementById('tx-power-value').textContent = this.value + 'W';
        });
    }
    
    const audioOffsetSlider = document.getElementById('audio-offset');
    if (audioOffsetSlider) {
        audioOffsetSlider.addEventListener('input', function() {
            document.getElementById('audio-offset-value').textContent = this.value + ' Hz';
        });
    }
    
    // 解码消息点击
    document.getElementById('decode-list').addEventListener('click', function(e) {
        const decodeItem = e.target.closest('.decode-item');
        if (decodeItem) {
            handleDecodeClick(decodeItem.dataset.callsign, decodeItem.dataset.grid);
        }
    });
}

// 切换标签
function switchTab(tabId) {
    document.querySelectorAll('.tx-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tx-panel').forEach(p => p.classList.remove('active'));
    
    document.querySelector(`.tx-tab[data-tab="${tabId}"]`).classList.add('active');
    document.getElementById(`panel-${tabId}`).classList.add('active');
}

////////////////////////////////////////////////////////////
// WebSocket 连接
////////////////////////////////////////////////////////////

function connect() {
    if (ft8State.isConnected) return;
    
    console.log('🔌 连接电台...');
    updateStatus('connecting');
    
    const baseUrl = 'wss://' + window.location.host;
    
    // 连接 FT8 专用 WebSocket
    try {
        ft8State.wsFT8 = new WebSocket(baseUrl + '/WSFT8');
        
        ft8State.wsFT8.onopen = () => {
            console.log('✅ FT8 连接成功');
            ft8State.isConnected = true;
            updateStatus('connected');
            
            // 发送设置
            if (ft8State.settings.myCallsign) {
                ft8State.wsFT8.send('setCallsign:' + ft8State.settings.myCallsign);
            }
            if (ft8State.settings.myGrid) {
                ft8State.wsFT8.send('setGrid:' + ft8State.settings.myGrid);
            }
        };
        
        ft8State.wsFT8.onmessage = (msg) => {
            handleFT8Message(msg.data);
        };
        
        ft8State.wsFT8.onerror = (err) => {
            console.error('❌ FT8 连接错误:', err);
            updateStatus('error');
        };
        
        ft8State.wsFT8.onclose = () => {
            console.log('🔌 FT8 连接关闭');
            ft8State.isConnected = false;
            updateStatus('disconnected');
        };
        
        // 同时连接控制 WebSocket（用于频率控制）
        ft8State.wsControl = new WebSocket(baseUrl + '/WSCTRX');
        
        ft8State.wsControl.onopen = () => {
            console.log('✅ 控制连接成功');
            
            // 设置 FT8 模式
            ft8State.wsControl.send('setMode:USB');
            ft8State.wsControl.send('setFilterWidth:3000');
            
            // 获取频率
            ft8State.wsControl.send('getFreq:');
        };
        
        ft8State.wsControl.onmessage = (msg) => {
            handleControlMessage(msg.data);
        };
        
        ft8State.wsControl.onerror = (err) => {
            console.error('❌ 控制连接错误:', err);
        };
        
        ft8State.wsControl.onclose = () => {
            console.log('🔌 控制连接关闭');
        };
        
    } catch (err) {
        console.error('❌ 连接失败:', err);
        updateStatus('error');
    }
}

////////////////////////////////////////////////////////////
// FT8 消息处理
////////////////////////////////////////////////////////////

function handleFT8Message(data) {
    try {
        const msg = JSON.parse(data);
        
        switch (msg.type) {
            case 'status':
                // 初始状态
                console.log('📊 FT8 状态:', msg.data);
                if (msg.data.cycle) {
                    ft8State.cycleInfo = msg.data.cycle;
                }
                if (msg.data.messages) {
                    msg.data.messages.forEach(m => addDecodedMessage(m));
                }
                break;
                
            case 'decode':
                // 解码结果
                console.log('📡 解码到', msg.messages.length, '条消息');
                msg.messages.forEach(m => addDecodedMessage(m));
                break;
                
            case 'cycle':
                // 周期更新
                ft8State.cycleInfo = msg.cycle;
                updateCycleDisplay(msg.cycle);
                break;
                
            case 'settings':
                // 设置确认
                console.log('⚙️ 设置已更新:', msg.data);
                break;
                
            case 'audio':
                // 编码音频（用于发送）
                console.log('🔊 收到编码音频');
                playFT8Audio(msg.data);
                break;
                
            case 'error':
                console.error('❌ 服务器错误:', msg.message);
                break;
        }
    } catch (e) {
        console.error('解析 FT8 消息错误:', e);
    }
}

function playFT8Audio(audioBase64) {
    // TODO: 播放 FT8 编码音频
    // 这需要将 base64 解码为音频数据并通过 Web Audio API 播放
}

function disconnect() {
    if (ft8State.wsFT8) {
        ft8State.wsFT8.close();
        ft8State.wsFT8 = null;
    }
    if (ft8State.wsControl) {
        ft8State.wsControl.close();
        ft8State.wsControl = null;
    }
    ft8State.isConnected = false;
    updateStatus('disconnected');
}

////////////////////////////////////////////////////////////
// 解码消息显示
////////////////////////////////////////////////////////////

function addDecodedMessage(msg) {
    const list = document.getElementById('decode-list');
    if (!list) return;
    
    // 创建消息元素
    const item = document.createElement('div');
    item.className = 'decode-item';
    item.dataset.callsign = extractCallsign(msg.message);
    item.dataset.grid = extractGrid(msg.message);
    
    // 格式化时间
    const time = new Date(msg.time).toLocaleTimeString('zh-CN', { hour12: false });
    
    // 判断是否已通联
    const callsign = extractCallsign(msg.message);
    const isWorked = ft8State.workedCallsigns.has(callsign);
    if (isWorked) {
        item.classList.add('worked');
    }
    
    // 判断是否是 CQ
    const isCQ = msg.message.startsWith('CQ');
    if (isCQ) {
        item.classList.add('cq');
    }
    
    item.innerHTML = `
        <span class="decode-time">${time}</span>
        <span class="decode-freq">${msg.freq} Hz</span>
        <span class="decode-snr">${msg.snr > 0 ? '+' : ''}${msg.snr} dB</span>
        <span class="decode-msg">${msg.message}</span>
        ${isWorked ? '<span class="worked-badge">✓</span>' : ''}
    `;
    
    // 插入到列表顶部
    list.insertBefore(item, list.firstChild);
    
    // 限制显示数量
    while (list.children.length > FT8_CONFIG.MAX_DECODES) {
        list.removeChild(list.lastChild);
    }
    
    // 保存到状态
    ft8State.decodedMessages.push(msg);
}

function extractCallsign(message) {
    // 从消息中提取呼号
    // 格式: CQ AA1AA FN31 或 AA1AA BB1BB -10
    const parts = message.split(' ');
    if (parts[0] === 'CQ' && parts.length >= 2) {
        return parts[1];
    } else if (parts.length >= 2) {
        // 可能是 AA1AA BB1BB 格式
        return parts[0];
    }
    return '';
}

function extractGrid(message) {
    // 从消息中提取网格坐标
    const parts = message.split(' ');
    if (parts.length >= 3) {
        const last = parts[parts.length - 1];
        // 网格格式: RR00 (4字符)
        if (/^[A-R]{2}[0-9]{2}$/.test(last)) {
            return last;
        }
    }
    return '';
}

////////////////////////////////////////////////////////////
// 周期显示
////////////////////////////////////////////////////////////

function updateCycleDisplay(cycle) {
    // 更新周期进度条
    const progress = document.getElementById('cycle-progress');
    if (progress) {
        progress.style.width = (cycle.cycle_phase * 100) + '%';
    }
    
    // 更新周期标签
    const label = document.getElementById('cycle-label');
    if (label) {
        label.textContent = cycle.is_even ? '偶数周期' : '奇数周期';
    }
}

////////////////////////////////////////////////////////////
// 发送功能
////////////////////////////////////////////////////////////

function sendCQ(type = 'standard') {
    if (!ft8State.wsFT8 || !ft8State.isConnected) {
        console.warn('⚠️ 未连接，无法发送');
        return;
    }
    
    let message = '';
    switch (type) {
        case 'dx':
            message = `CQ DX ${ft8State.settings.myCallsign} ${ft8State.settings.myGrid}`;
            break;
        case 'as':
            message = `CQ AS ${ft8State.settings.myCallsign} ${ft8State.settings.myGrid}`;
            break;
        default:
            message = `CQ ${ft8State.settings.myCallsign} ${ft8State.settings.myGrid}`;
    }
    
    console.log('📤 发送 CQ:', message);
    ft8State.wsFT8.send('encode:' + message);
    
    // 更新状态
    ft8State.qsoState = 'CALLING';
}

function sendReply(callsign, grid, report = null) {
    if (!ft8State.wsFT8 || !ft8State.isConnected) return;
    
    let message;
    if (report) {
        // 第二次回复：发送信号报告
        message = `${callsign} ${ft8State.settings.myCallsign} ${report}`;
    } else {
        // 第一次回复：发送网格
        message = `${callsign} ${ft8State.settings.myCallsign} ${ft8State.settings.myGrid}`;
    }
    
    console.log('📤 发送回复:', message);
    ft8State.wsFT8.send('encode:' + message);
    
    // 更新状态
    ft8State.qsoState = 'ANSWERING';
}

function sendFinal(callsign) {
    if (!ft8State.wsFT8 || !ft8State.isConnected) return;
    
    const message = `${callsign} ${ft8State.settings.myCallsign} RR73`;
    console.log('📤 发送结束:', message);
    ft8State.wsFT8.send('encode:' + message);
    
    // 更新状态
    ft8State.qsoState = 'FINALIZING';
}

function sendCustom(message) {
    if (!ft8State.wsFT8 || !ft8State.isConnected) return;
    if (message.length > 13) {
        console.warn('⚠️ 自由文本消息最多13字符');
        return;
    }
    
    console.log('📤 发送自定义:', message);
    ft8State.wsFT8.send('encode:"' + message + '"');
}

////////////////////////////////////////////////////////////
// 解码消息点击处理
////////////////////////////////////////////////////////////

function handleDecodeClick(callsign, grid) {
    console.log('点击消息:', callsign, grid);
    
    // 填充回复表单
    const replyCallsign = document.getElementById('reply-callsign');
    const replyGrid = document.getElementById('reply-grid');
    
    if (replyCallsign) replyCallsign.value = callsign;
    if (replyGrid) replyGrid.value = grid;
    
    // 切换到回复标签
    switchTab('reply');
    
    // 高亮选中的消息
    document.querySelectorAll('.decode-item').forEach(item => {
        item.classList.remove('selected');
    });
    event.currentTarget.classList.add('selected');
}

////////////////////////////////////////////////////////////
// 状态显示
////////////////////////////////////////////////////////////

function updateStatus(status) {
    const indicator = document.getElementById('status-indicator');
    const text = document.getElementById('status-text');
    
    if (indicator) {
        indicator.className = 'status-dot ' + status;
    }
    
    if (text) {
        switch (status) {
            case 'connected':
                text.textContent = '已连接';
                break;
            case 'connecting':
                text.textContent = '连接中...';
                break;
            case 'disconnected':
                text.textContent = '未连接';
                break;
            case 'error':
                text.textContent = '连接错误';
                break;
        }
    }
}

////////////////////////////////////////////////////////////
// 时钟和周期
////////////////////////////////////////////////////////////

function startClock() {
    updateClock();
    setInterval(updateClock, 1000);
}

function updateClock() {
    const clockEl = document.getElementById('utc-clock');
    if (clockEl) {
        const now = new Date();
        clockEl.textContent = now.toISOString().substr(11, 8);
    }
}

function startCycleTimer() {
    updateCycleInfo();
    setInterval(updateCycleInfo, 100);
}

function updateCycleInfo() {
    const now = Date.now();
    const cycleDuration = FT8_CONFIG.CYCLE_DURATION;
    const cycleStart = now - (now % cycleDuration);
    const cycleElapsed = now - cycleStart;
    const cyclePhase = cycleElapsed / cycleDuration;
    const timeToNext = cycleDuration - cycleElapsed;
    
    // 判断偶数/奇数周期
    const minute = Math.floor(cycleStart / 60000);
    const isEven = (Math.floor(minute / 15) % 2) === 0;
    
    ft8State.cycleInfo = {
        cycle_start: cycleStart,
        cycle_phase: cyclePhase,
        time_to_next: timeToNext,
        is_even: isEven
    };
    
    updateCycleDisplay(ft8State.cycleInfo);
}

////////////////////////////////////////////////////////////
// 设置
////////////////////////////////////////////////////////////

function loadSettings() {
    const saved = localStorage.getItem('ft8_settings');
    if (saved) {
        try {
            const settings = JSON.parse(saved);
            Object.assign(ft8State.settings, settings);
        } catch (e) {
            console.error('加载设置失败:', e);
        }
    }
    
    // 应用设置到UI
    const callsignInput = document.getElementById('my-callsign');
    const gridInput = document.getElementById('my-grid');
    
    if (callsignInput && ft8State.settings.myCallsign) {
        callsignInput.value = ft8State.settings.myCallsign;
    }
    if (gridInput && ft8State.settings.myGrid) {
        gridInput.value = ft8State.settings.myGrid;
    }
}

function saveSettings() {
    localStorage.setItem('ft8_settings', JSON.stringify(ft8State.settings));
}

////////////////////////////////////////////////////////////
// 日志
////////////////////////////////////////////////////////////

function loadLog() {
    const saved = localStorage.getItem('ft8_log');
    if (saved) {
        try {
            ft8State.qsoLog = JSON.parse(saved);
            ft8State.qsoLog.forEach(qso => {
                ft8State.workedCallsigns.add(qso.callsign);
            });
        } catch (e) {
            console.error('加载日志失败:', e);
        }
    }
}

function logQSO(qso) {
    ft8State.qsoLog.push(qso);
    ft8State.workedCallsigns.add(qso.callsign);
    localStorage.setItem('ft8_log', JSON.stringify(ft8State.qsoLog));
}

function exportADIF() {
    // 导出 ADIF 格式日志
    let adif = '';
    ft8State.qsoLog.forEach(qso => {
        adif += `<CALL:${qso.callsign.length}>${qso.callsign}\n`;
        adif += `<GRIDSQUARE:${qso.grid.length}>${qso.grid}\n`;
        adif += `<MODE:3>FT8\n`;
        adif += `<QSO_DATE:8>${qso.date}\n`;
        adif += `<TIME_ON:4>${qso.time}\n`;
        adif += `<RST_SENT:3>${qso.rst_sent || '-10'}\n`;
        adif += `<RST_RCVD:3>${qso.rst_rcvd || '-10'}\n`;
        adif += `<EOR>\n\n`;
    });
    
    // 下载文件
    const blob = new Blob([adif], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ft8_log_${new Date().toISOString().substr(0, 10)}.adi`;
    a.click();
    URL.revokeObjectURL(url);
}

////////////////////////////////////////////////////////////
// 消息处理
////////////////////////////////////////////////////////////

function handleControlMessage(data) {
    if (data.startsWith('getFreq:')) {
        const freq = parseInt(data.split(':')[1]);
        updateFrequency(freq);
    }
}

function handleAudioData(msg) {
    // 接收音频数据用于瀑布图
    const int16Data = new Int16Array(msg.data);
    const float32Data = new Float32Array(int16Data.length);
    
    for (let i = 0; i < int16Data.length; i++) {
        float32Data[i] = int16Data[i] / 32768.0;
    }
    
    // 更新瀑布图
    updateWaterfall(float32Data);
}

////////////////////////////////////////////////////////////
// 瀑布图
////////////////////////////////////////////////////////////

function initWaterfall() {
    const canvas = document.getElementById('waterfall-canvas');
    if (!canvas) return;
    
    ft8State.waterfallCanvas = canvas;
    ft8State.waterfallCtx = canvas.getContext('2d');
    
    // 设置画布尺寸
    canvas.width = canvas.offsetWidth;
    canvas.height = FT8_CONFIG.WATERFALL_HEIGHT;
    
    // 初始化数据
    ft8State.waterfallData = [];
    
    // 绘制频率刻度
    drawFreqScale();
}

function updateWaterfall(audioData) {
    if (!ft8State.waterfallCtx) return;
    
    // 简化FFT处理（实际应用中应使用完整的FFT）
    const bins = 256;
    const spectrum = computeSpectrum(audioData, bins);
    
    // 添加到历史数据
    ft8State.waterfallData.push(spectrum);
    
    // 限制历史长度
    if (ft8State.waterfallData.length > FT8_CONFIG.WATERFALL_HISTORY) {
        ft8State.waterfallData.shift();
    }
    
    // 绘制瀑布图
    drawWaterfall();
}

function computeSpectrum(data, bins) {
    // 简化的频谱计算（实际应使用FFT）
    const spectrum = new Float32Array(bins);
    const step = Math.floor(data.length / bins);
    
    for (let i = 0; i < bins; i++) {
        let sum = 0;
        for (let j = 0; j < step; j++) {
            const idx = i * step + j;
            if (idx < data.length) {
                sum += Math.abs(data[idx]);
            }
        }
        spectrum[i] = sum / step;
    }
    
    // 归一化
    const max = Math.max(...spectrum);
    if (max > 0) {
        for (let i = 0; i < bins; i++) {
            spectrum[i] /= max;
        }
    }
    
    return spectrum;
}

function drawWaterfall() {
    const ctx = ft8State.waterfallCtx;
    const canvas = ft8State.waterfallCanvas;
    if (!ctx) return;
    
    const width = canvas.width;
    const height = canvas.height;
    
    // 清除画布
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, width, height);
    
    // 绘制历史数据
    const data = ft8State.waterfallData;
    const startIndex = Math.max(0, data.length - height);
    
    for (let y = 0; y < height && (startIndex + y) < data.length; y++) {
        const spectrum = data[startIndex + y];
        for (let x = 0; x < spectrum.length; x++) {
            const intensity = spectrum[x];
            const color = getWaterfallColor(intensity);
            ctx.fillStyle = color;
            ctx.fillRect(
                x * width / spectrum.length,
                height - y - 1,
                width / spectrum.length + 1,
                1
            );
        }
    }
}

function getWaterfallColor(value) {
    // 瀑布图颜色映射（黑-蓝-青-绿-黄-红）
    const v = Math.max(0, Math.min(1, value));
    
    if (v < 0.2) {
        // 黑 -> 蓝
        const t = v / 0.2;
        return `rgb(0, 0, ${Math.floor(255 * t)})`;
    } else if (v < 0.4) {
        // 蓝 -> 青
        const t = (v - 0.2) / 0.2;
        return `rgb(0, ${Math.floor(255 * t)}, 255)`;
    } else if (v < 0.6) {
        // 青 -> 绿
        const t = (v - 0.4) / 0.2;
        return `rgb(0, 255, ${Math.floor(255 * (1 - t))})`;
    } else if (v < 0.8) {
        // 绿 -> 黄
        const t = (v - 0.6) / 0.2;
        return `rgb(${Math.floor(255 * t)}, 255, 0)`;
    } else {
        // 黄 -> 红
        const t = (v - 0.8) / 0.2;
        return `rgb(255, ${Math.floor(255 * (1 - t))}, 0)`;
    }
}

function drawFreqScale() {
    const scale = document.getElementById('freq-scale');
    if (!scale) return;
    
    // 清空并添加频率标记
    scale.innerHTML = '';
    
    const freqs = ['0', '500', '1000', '1500', '2000', '2500', '3000'];
    freqs.forEach(f => {
        const span = document.createElement('span');
        span.textContent = f;
        scale.appendChild(span);
    });
}

////////////////////////////////////////////////////////////
// 解码消息
////////////////////////////////////////////////////////////

function addDecodedMessage(msg) {
    /**
     * msg 结构：
     * {
     *   time: '12:34:56',
     *   snr: -15,
     *   dt: 0.5,
     *   freq: 1200,
     *   message: 'CQ BG7XXX PM95',
     *   callsign: 'BG7XXX',
     *   grid: 'PM95'
     * }
     */
    
    // 检查是否需要过滤
    if (ft8State.settings.filterWorked && ft8State.workedCallsigns.has(msg.callsign)) {
        return; // 跳过已通联的呼号
    }
    
    // 添加到列表
    ft8State.decodedMessages.unshift(msg);
    
    // 限制数量
    if (ft8State.decodedMessages.length > FT8_CONFIG.MAX_DECODES) {
        ft8State.decodedMessages.pop();
    }
    
    // 更新显示
    renderDecodedMessages();
    
    // 检查是否是给自己的消息
    checkMessageForMe(msg);
    
    // 在瀑布图上标记
    addWaterfallMarker(msg);
}

function renderDecodedMessages() {
    const container = document.getElementById('decode-list');
    if (!container) return;
    
    if (ft8State.decodedMessages.length === 0) {
        container.innerHTML = '<div class="decode-empty">等待解码...</div>';
        return;
    }
    
    container.innerHTML = ft8State.decodedMessages.map(msg => {
        const isCQ = msg.message.startsWith('CQ');
        const isToMe = msg.message.includes(ft8State.settings.myCallsign);
        
        let cssClass = 'decode-item';
        if (isCQ) cssClass += ' cq';
        if (isToMe) cssClass += ' to-me';
        
        // 高亮呼号和网格
        let formattedMsg = msg.message;
        if (msg.callsign) {
            formattedMsg = formattedMsg.replace(msg.callsign, `<span class="callsign">${msg.callsign}</span>`);
        }
        if (msg.grid) {
            formattedMsg = formattedMsg.replace(msg.grid, `<span class="grid">${msg.grid}</span>`);
        }
        
        return `
            <div class="${cssClass}" 
                 data-callsign="${msg.callsign || ''}" 
                 data-grid="${msg.grid || ''}">
                <span class="decode-time">${msg.time}</span>
                <span class="decode-snr ${msg.snr < 0 ? 'negative' : ''}">${msg.snr > 0 ? '+' : ''}${msg.snr} dB</span>
                <span class="decode-message">${formattedMsg}</span>
            </div>
        `;
    }).join('');
}

function clearDecodes() {
    ft8State.decodedMessages = [];
    renderDecodedMessages();
}

function toggleFilter() {
    ft8State.settings.filterWorked = !ft8State.settings.filterWorked;
    const icon = document.getElementById('filter-icon');
    icon.textContent = ft8State.settings.filterWorked ? '🔍✓' : '🔍';
    renderDecodedMessages();
}

function handleDecodeClick(callsign, grid) {
    // 填充回复面板
    document.getElementById('reply-callsign').value = callsign || '';
    document.getElementById('reply-grid').value = grid || '';
    
    // 切换到回复标签
    switchTab('reply');
}

////////////////////////////////////////////////////////////
// 瀑布图标记
////////////////////////////////////////////////////////////

function addWaterfallMarker(msg) {
    const overlay = document.getElementById('waterfall-overlay');
    if (!overlay) return;
    
    const marker = document.createElement('div');
    marker.className = 'decode-marker';
    
    if (msg.message.startsWith('CQ')) {
        marker.classList.add('cq');
    } else if (msg.message.includes(ft8State.settings.myCallsign)) {
        marker.classList.add('to-me');
    }
    
    // 计算位置（基于频率）
    const leftPercent = (msg.freq / 3000) * 100;
    marker.style.left = leftPercent + '%';
    marker.style.top = '0';
    marker.textContent = msg.callsign || '';
    
    overlay.appendChild(marker);
    
    // 15秒后移除
    setTimeout(() => {
        marker.remove();
    }, FT8_CONFIG.CYCLE_DURATION);
}

////////////////////////////////////////////////////////////
// 发送功能
////////////////////////////////////////////////////////////

function sendCQ(type) {
    const callsign = ft8State.settings.myCallsign;
    if (!callsign) {
        alert('请先设置你的呼号');
        toggleSettings();
        return;
    }
    
    const grid = ft8State.settings.myGrid || '';
    
    let message;
    if (type === 'CQ DX') {
        message = `CQ DX ${callsign} ${grid}`.trim();
    } else if (type === 'CQ AS') {
        message = `CQ AS ${callsign} ${grid}`.trim();
    } else {
        message = `CQ ${callsign} ${grid}`.trim();
    }
    
    queueMessage(message);
    setQSOState('CALLING');
}

function sendReply(step) {
    const callsign = ft8State.settings.myCallsign;
    const targetCallsign = document.getElementById('reply-callsign').value.toUpperCase();
    const targetGrid = document.getElementById('reply-grid').value.toUpperCase();
    const myGrid = ft8State.settings.myGrid || '';
    
    if (!callsign) {
        alert('请先设置你的呼号');
        toggleSettings();
        return;
    }
    
    if (!targetCallsign) {
        alert('请输入对方呼号');
        return;
    }
    
    let message;
    
    switch (step) {
        case 1:
            // 第一条回复：对方呼号 我的呼号 网格
            message = `${targetCallsign} ${callsign} ${myGrid}`.trim();
            setQSOState('ANSWERING');
            break;
        case 2:
            // 第二条回复：对方呼号 我的呼号 信号报告
            const signalReport = generateSignalReport();
            message = `${targetCallsign} ${callsign} ${signalReport}`;
            setQSOState('IN_QSO');
            break;
        case 3:
            // 结束：RR73
            message = `${targetCallsign} ${callsign} RR73`;
            setQSOState('FINALIZING');
            break;
    }
    
    // 更新当前QSO信息
    ft8State.currentQSO = {
        callsign: targetCallsign,
        grid: targetGrid,
        startTime: new Date()
    };
    updateQSODisplay();
    
    queueMessage(message);
}

function sendCustom() {
    const message = document.getElementById('custom-message').value.toUpperCase();
    if (!message) {
        alert('请输入消息');
        return;
    }
    
    queueMessage(message);
}

function insertPreset(text) {
    const input = document.getElementById('custom-message');
    input.value = text;
    input.focus();
}

function queueMessage(message) {
    console.log('📝 准备发送:', message);
    
    // TODO: 实际发送需要等待下一个TX周期
    // 这里简化为立即设置待发送状态
    ft8State.pendingMessage = message;
    
    // 显示确认
    showToast(`准备发送: ${message}`);
    
    // 如果TX按钮已激活，等待周期开始自动发送
    // 否则提示用户点击TX按钮
    if (!ft8State.txEnabled) {
        showToast('点击"发射"按钮开始发送');
    }
}

////////////////////////////////////////////////////////////
// TX 控制
////////////////////////////////////////////////////////////

function toggleTX() {
    ft8State.txEnabled = !ft8State.txEnabled;
    
    const txBtn = document.getElementById('tx-btn');
    const txLabel = document.getElementById('tx-label');
    const container = document.querySelector('.ft8-container');
    
    if (ft8State.txEnabled) {
        txBtn.classList.add('tx-active');
        txLabel.textContent = '停止';
        container.classList.add('tx-active');
        
        // 立即开始发射（如果当前是TX周期的开始）
        scheduleTX();
    } else {
        txBtn.classList.remove('tx-active');
        txLabel.textContent = '发射';
        container.classList.remove('tx-active');
        
        // 停止发射
        stopTX();
    }
}

function scheduleTX() {
    if (!ft8State.txEnabled || !ft8State.pendingMessage) return;
    
    // 计算下一个TX周期（偶数秒开始）
    const now = Date.now();
    const cycleStart = Math.floor(now / FT8_CONFIG.CYCLE_DURATION) * FT8_CONFIG.CYCLE_DURATION;
    const nextTX = cycleStart + (now % (FT8_CONFIG.CYCLE_DURATION * 2) < FT8_CONFIG.CYCLE_DURATION ? FT8_CONFIG.CYCLE_DURATION : FT8_CONFIG.CYCLE_DURATION * 2);
    
    const delay = nextTX - now;
    
    console.log(`⏱️ ${delay}ms 后开始发射`);
    
    setTimeout(() => {
        if (ft8State.txEnabled && ft8State.pendingMessage) {
            startTX(ft8State.pendingMessage);
        }
    }, delay);
}

function startTX(message) {
    ft8State.isTransmitting = true;
    ft8State.txStartTime = Date.now();
    
    updateTXStatus('TX');
    console.log('📡 开始发射:', message);
    
    // TODO: 实际音频生成和发送
    // 这里需要FT8编码器生成音频，然后通过WebSocket发送
    
    // 模拟发射完成
    setTimeout(() => {
        stopTX();
    }, FT8_CONFIG.CYCLE_DURATION - 500); // 留500ms余量
}

function stopTX() {
    ft8State.isTransmitting = false;
    updateTXStatus('RX');
    
    // 如果TX启用且有pending消息，安排下一次发射
    if (ft8State.txEnabled) {
        scheduleTX();
    }
}

function updateTXStatus(status) {
    const statusEl = document.getElementById('tx-status');
    statusEl.textContent = status;
    statusEl.className = 'status-item-ft8 ' + status.toLowerCase();
    
    const wsStatus = document.getElementById('ws-status');
    if (status === 'TX') {
        wsStatus.classList.add('tx');
    } else {
        wsStatus.classList.remove('tx');
    }
}

////////////////////////////////////////////////////////////
// QSO 状态机
////////////////////////////////////////////////////////////

function setQSOState(state) {
    ft8State.qsoState = state;
    
    const statusEl = document.getElementById('qso-status');
    
    switch (state) {
        case 'IDLE':
            statusEl.textContent = '空闲';
            statusEl.className = 'qso-status';
            break;
        case 'CALLING':
            statusEl.textContent = '呼叫中';
            statusEl.className = 'qso-status active';
            break;
        case 'ANSWERING':
            statusEl.textContent = '回复中';
            statusEl.className = 'qso-status active';
            break;
        case 'IN_QSO':
            statusEl.textContent = '通联中';
            statusEl.className = 'qso-status active';
            break;
        case 'FINALIZING':
            statusEl.textContent = '结束中';
            statusEl.className = 'qso-status active';
            break;
    }
}

function checkMessageForMe(msg) {
    const myCallsign = ft8State.settings.myCallsign;
    if (!myCallsign) return;
    
    if (msg.message.includes(myCallsign)) {
        // 收到给我的消息
        handleIncomingMessage(msg);
    }
}

function handleIncomingMessage(msg) {
    // 更新QSO信息
    if (!ft8State.currentQSO || ft8State.currentQSO.callsign !== msg.callsign) {
        ft8State.currentQSO = {
            callsign: msg.callsign,
            grid: msg.grid,
            snr: msg.snr,
            startTime: new Date()
        };
    } else {
        ft8State.currentQSO.snr = msg.snr;
    }
    
    updateQSODisplay();
    
    // 生成建议回复
    suggestReply(msg);
}

function suggestReply(msg) {
    const suggested = document.getElementById('suggested-reply');
    const myCallsign = ft8State.settings.myCallsign;
    const myGrid = ft8State.settings.myGrid || '';
    
    let reply;
    
    switch (ft8State.qsoState) {
        case 'IDLE':
        case 'CALLING':
            // 收到别人回复我的CQ
            reply = `${msg.callsign} ${myCallsign} ${myGrid}`;
            setQSOState('ANSWERING');
            break;
        case 'ANSWERING':
            // 收到信号报告，回复RR73
            reply = `${msg.callsign} ${myCallsign} RR73`;
            setQSOState('FINALIZING');
            break;
        case 'IN_QSO':
        case 'FINALIZING':
            // 收到RR73，QSO完成
            reply = '73';
            completeQSO();
            break;
        default:
            reply = '-';
    }
    
    suggested.textContent = reply;
    
    // 自动填充回复面板
    document.getElementById('reply-callsign').value = msg.callsign || '';
    document.getElementById('reply-grid').value = msg.grid || '';
}

function updateQSODisplay() {
    if (ft8State.currentQSO) {
        document.getElementById('qso-callsign').textContent = ft8State.currentQSO.callsign || '-';
        document.getElementById('qso-grid').textContent = ft8State.currentQSO.grid || '-';
        document.getElementById('qso-snr').textContent = ft8State.currentQSO.snr + ' dB';
    }
}

function completeQSO() {
    if (!ft8State.currentQSO) return;
    
    // 保存到日志
    if (ft8State.settings.autoLog) {
        logQSO(ft8State.currentQSO);
    }
    
    // 添加到已通联列表
    ft8State.workedCallsigns.add(ft8State.currentQSO.callsign);
    
    // 重置状态
    ft8State.currentQSO = null;
    setQSOState('IDLE');
    
    // 清除显示
    document.getElementById('qso-callsign').textContent = '-';
    document.getElementById('qso-grid').textContent = '-';
    document.getElementById('qso-snr').textContent = '-';
    document.getElementById('suggested-reply').textContent = '-';
}

////////////////////////////////////////////////////////////
// 自动 CQ
////////////////////////////////////////////////////////////

function checkAutoCQ() {
    if (!ft8State.settings.autoCQ || ft8State.qsoState !== 'IDLE') return;
    
    // 检查是否到了自动CQ时间
    const now = Date.now();
    const interval = ft8State.settings.autoCQInterval * 60000;
    
    if (!ft8State.lastAutoCQ || (now - ft8State.lastAutoCQ) >= interval) {
        sendCQ('CQ');
        ft8State.lastAutoCQ = now;
    }
}

////////////////////////////////////////////////////////////
// 日志功能
////////////////////////////////////////////////////////////

function logQSO(qso) {
    const entry = {
        callsign: qso.callsign,
        grid: qso.grid,
        frequency: ft8State.currentFrequency,
        mode: 'FT8',
        time: new Date().toISOString(),
        snr: qso.snr
    };
    
    ft8State.qsoLog.push(entry);
    saveLog();
    
    console.log('📝 QSO已记录:', entry.callsign);
    showToast(`QSO已记录: ${entry.callsign}`);
}

function saveLog() {
    try {
        localStorage.setItem('ft8_qso_log', JSON.stringify(ft8State.qsoLog));
    } catch (e) {
        console.error('保存日志失败:', e);
    }
}

function loadLog() {
    try {
        const log = localStorage.getItem('ft8_qso_log');
        if (log) {
            ft8State.qsoLog = JSON.parse(log);
            
            // 提取已通联呼号
            ft8State.qsoLog.forEach(entry => {
                ft8State.workedCallsigns.add(entry.callsign);
            });
        }
    } catch (e) {
        console.error('加载日志失败:', e);
    }
}

function showLog() {
    const overlay = document.getElementById('log-overlay');
    overlay.classList.toggle('active');
    
    if (overlay.classList.contains('active')) {
        renderLog();
    }
}

function renderLog() {
    const container = document.getElementById('log-list');
    
    if (ft8State.qsoLog.length === 0) {
        container.innerHTML = '<div class="log-empty">暂无日志</div>';
        return;
    }
    
    // 按时间倒序显示
    const sorted = [...ft8State.qsoLog].reverse();
    
    container.innerHTML = sorted.map(entry => `
        <div class="log-item">
            <span class="log-item-callsign">${entry.callsign}</span>
            <span class="log-item-grid">${entry.grid || ''}</span>
            <span class="log-item-time">${new Date(entry.time).toLocaleString()}</span>
        </div>
    `).join('');
}

function clearLog() {
    if (confirm('确定要清除所有日志吗？')) {
        ft8State.qsoLog = [];
        ft8State.workedCallsigns.clear();
        saveLog();
        renderLog();
    }
}

function exportLogADIF() {
    // 生成ADIF格式
    let adif = '';
    
    ft8State.qsoLog.forEach(entry => {
        adif += `<call:${entry.callsign.length}>${entry.callsign}\n`;
        if (entry.grid) {
            adif += `<gridsquare:${entry.grid.length}>${entry.grid}\n`;
        }
        adif += `<mode:3>FT8\n`;
        adif += `<freq:${entry.frequency.toString().length}>${entry.frequency}\n`;
        adif += `<qso_date:10>${new Date(entry.time).toISOString().slice(0, 10).replace(/-/g, '')}\n`;
        adif += `<time_on:8>${new Date(entry.time).toTimeString().slice(0, 8).replace(/:/g, '')}\n`;
        adif += `<eor>\n\n`;
    });
    
    // 下载文件
    const blob = new Blob([adif], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ft8_log_${new Date().toISOString().slice(0, 10)}.adi`;
    a.click();
    URL.revokeObjectURL(url);
}

////////////////////////////////////////////////////////////
// 设置
////////////////////////////////////////////////////////////

function toggleSettings() {
    const overlay = document.getElementById('settings-overlay');
    overlay.classList.toggle('active');
}

function saveSettings() {
    ft8State.settings.myCallsign = document.getElementById('my-callsign').value.toUpperCase();
    ft8State.settings.myGrid = document.getElementById('my-grid').value.toUpperCase();
    ft8State.settings.txPower = parseInt(document.getElementById('tx-power').value);
    ft8State.settings.audioOffset = parseInt(document.getElementById('audio-offset').value);
    ft8State.settings.autoLog = document.getElementById('auto-log').checked;
    ft8State.settings.filterWorked = document.getElementById('filter-worked').checked;
    
    // 保存到本地存储
    try {
        localStorage.setItem('ft8_settings', JSON.stringify(ft8State.settings));
    } catch (e) {
        console.error('保存设置失败:', e);
    }
    
    toggleSettings();
    showToast('设置已保存');
}

function loadSettings() {
    try {
        const saved = localStorage.getItem('ft8_settings');
        if (saved) {
            ft8State.settings = { ...ft8State.settings, ...JSON.parse(saved) };
        }
    } catch (e) {
        console.error('加载设置失败:', e);
    }
    
    // 应用设置到UI
    document.getElementById('my-callsign').value = ft8State.settings.myCallsign;
    document.getElementById('my-grid').value = ft8State.settings.myGrid;
    document.getElementById('tx-power').value = ft8State.settings.txPower;
    document.getElementById('tx-power-value').textContent = ft8State.settings.txPower + 'W';
    document.getElementById('audio-offset').value = ft8State.settings.audioOffset;
    document.getElementById('audio-offset-value').textContent = ft8State.settings.audioOffset + ' Hz';
    document.getElementById('auto-log').checked = ft8State.settings.autoLog;
    document.getElementById('filter-worked').checked = ft8State.settings.filterWorked;
}

////////////////////////////////////////////////////////////
// 工具函数
////////////////////////////////////////////////////////////

function updateStatus(status) {
    const dot = document.getElementById('ws-status');
    const text = document.getElementById('status-text');
    
    switch (status) {
        case 'connected':
            dot.className = 'status-dot connected';
            text.textContent = '已连接';
            ft8State.isConnected = true;
            break;
        case 'disconnected':
            dot.className = 'status-dot';
            text.textContent = '离线';
            ft8State.isConnected = false;
            break;
        case 'connecting':
            dot.className = 'status-dot';
            dot.style.background = 'var(--accent-warning)';
            text.textContent = '连接中...';
            break;
        case 'error':
            dot.className = 'status-dot';
            dot.style.background = 'var(--accent-danger)';
            text.textContent = '连接错误';
            break;
    }
}

function updateFrequency(freqHz) {
    ft8State.currentFrequency = freqHz;
    
    const freqMHz = freqHz / 1000000;
    document.getElementById('freq-display').textContent = freqMHz.toFixed(3);
}

function generateSignalReport() {
    // FT8使用两位信号报告，如 -15 -> R-15
    // 简化：根据SNR生成
    const snr = ft8State.currentQSO?.snr || -10;
    
    if (snr >= 0) {
        return 'R+' + snr;
    } else {
        return 'R' + snr;
    }
}

function startClock() {
    setInterval(() => {
        const now = new Date();
        document.getElementById('time-display').textContent = 
            now.toTimeString().slice(0, 8);
    }, 1000);
}

function startCycleTimer() {
    // FT8 15秒周期
    setInterval(() => {
        const now = Date.now();
        const phase = (now % FT8_CONFIG.CYCLE_DURATION) / FT8_CONFIG.CYCLE_DURATION;
        
        const bar = document.querySelector('.cycle-bar');
        if (bar) {
            bar.style.width = (phase * 100) + '%';
        }
        
        // 检查自动CQ
        checkAutoCQ();
        
    }, 100);
}

function showToast(message) {
    // 简单的提示消息
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 100px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(0, 212, 255, 0.9);
        color: #000;
        padding: 10px 20px;
        border-radius: 20px;
        font-size: 13px;
        z-index: 2000;
        animation: fade-in 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 2000);
}

////////////////////////////////////////////////////////////
// 页面加载后自动连接
////////////////////////////////////////////////////////////

// 延迟连接，等待用户确认
// connect();

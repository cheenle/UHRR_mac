/**
 * ATR-1000 Web Worker
 * V4.6.0 - 在独立线程处理 ATR-1000 WebSocket 连接
 * 
 * 解决问题：主线程在 PTT/TUNE 期间被阻塞，导致 ATR-1000 消息积压
 * 
 * 架构：
 * Worker 线程: WebSocket 连接 → 解析 JSON → postMessage
 * 主线程: 接收数据 → DOM 更新
 */

let ws = null;
let heartbeatInterval = null;
let isConnected = false;
let msgCount = 0;
let lastSyncTime = 0;

// 心跳间隔（毫秒）
const HEARTBEAT_INTERVAL = 250;

// 从主线程接收命令
self.onmessage = function(e) {
    const { type, data } = e.data;
    
    switch (type) {
        case 'connect':
            connect(data.url);
            break;
        case 'disconnect':
            disconnect();
            break;
        case 'sync':
            sendSync();
            break;
        case 'start':
            sendStart();
            break;
        case 'stop':
            sendStop();
            break;
        case 'startHeartbeat':
            startHeartbeat();
            break;
        case 'stopHeartbeat':
            stopHeartbeat();
            break;
    }
};

// 建立 WebSocket 连接
function connect(url) {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        console.log('[ATR Worker] 已连接或正在连接，跳过');
        return;
    }
    
    try {
        console.log('[ATR Worker] 连接:', url);
        ws = new WebSocket(url);
        
        ws.onopen = function() {
            isConnected = true;
            console.log('[ATR Worker] ✅ 已连接');
            
            // 通知主线程
            self.postMessage({ type: 'connected' });
            
            // V4.6.0: 不自动启动心跳，由主线程控制
        };
        
        ws.onclose = function() {
            isConnected = false;
            console.log('[ATR Worker] 🔴 连接关闭');
            stopHeartbeat();
            self.postMessage({ type: 'disconnected' });
        };
        
        ws.onerror = function(err) {
            console.error('[ATR Worker] ❌ 连接错误:', err);
            self.postMessage({ type: 'error', data: err.toString() });
        };
        
        ws.onmessage = function(event) {
            // 在 Worker 线程解析 JSON
            try {
                const msg = JSON.parse(event.data.trim());
                
                if (msg.type === 'atr1000_meter') {
                    msgCount++;
                    
                    // 发送解析后的数据给主线程
                    self.postMessage({
                        type: 'meter',
                        data: {
                            power: msg.power || 0,
                            swr: msg.swr || 0,
                            vforward: msg.vforward || 0,
                            vreflected: msg.vreflected || 0,
                            sw: msg.sw,
                            ind: msg.ind,
                            cap: msg.cap,
                            ind_uh: msg.ind_uh,
                            cap_pf: msg.cap_pf
                        },
                        msgCount: msgCount
                    });
                }
            } catch (e) {
                // 忽略解析错误
            }
        };
        
    } catch (err) {
        console.error('[ATR Worker] 连接失败:', err);
        self.postMessage({ type: 'error', data: err.toString() });
    }
}

// 断开连接
function disconnect() {
    stopHeartbeat();
    if (ws) {
        ws.close();
        ws = null;
    }
    isConnected = false;
}

// 启动心跳
function startHeartbeat() {
    stopHeartbeat();
    lastSyncTime = Date.now();
    
    heartbeatInterval = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            const now = Date.now();
            if (now - lastSyncTime >= HEARTBEAT_INTERVAL) {
                sendSync();
                lastSyncTime = now;
            }
        }
    }, HEARTBEAT_INTERVAL);
    
    console.log('[ATR Worker] 💓 心跳已启动 (' + HEARTBEAT_INTERVAL + 'ms)');
}

// 停止心跳
function stopHeartbeat() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
    }
}

// 发送 sync 命令
function sendSync() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        try {
            ws.send(JSON.stringify({ action: 'sync' }));
        } catch (e) {
            console.error('[ATR Worker] sync 发送失败:', e);
        }
    }
}

// 发送 start 命令
function sendStart() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        try {
            ws.send(JSON.stringify({ action: 'start' }));
            console.log('[ATR Worker] 📤 发送 start');
        } catch (e) {
            console.error('[ATR Worker] start 发送失败:', e);
        }
    }
}

// 发送 stop 命令
function sendStop() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        try {
            ws.send(JSON.stringify({ action: 'stop' }));
            console.log('[ATR Worker] 📤 发送 stop');
        } catch (e) {
            console.error('[ATR Worker] stop 发送失败:', e);
        }
    }
}

console.log('[ATR Worker] 🚀 ATR-1000 Worker 已加载');

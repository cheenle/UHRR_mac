// ATU功率和SWR显示管理
// 独立处理ATU WebSocket连接和数据显示

// ATU WebSocket连接管理
let atuSocket = null;
let atuIsConnected = false;
let atuConnectionAttempts = 0;
const MAX_CONNECTION_ATTEMPTS = 5;

// 初始化ATU显示系统
function initAtuDisplay() {
    console.log('[ATU] 开始初始化ATU显示系统');
    
    // 检查显示元素是否存在
    const powerElement = document.getElementById('power-value');
    const swrElement = document.getElementById('swr-value');
    
    if (!powerElement || !swrElement) {
        console.error('[ATU] ATU显示元素未找到，请检查HTML结构');
        return;
    }
    
    console.log('[ATU] ATU显示元素已找到，开始连接服务器');
    connectToAtuServer();
    
    // 启动每秒更新ATU数据
    console.log('[ATU] 启动ATU数据同步');
    startAtuSync();
}

// 连接到ATU WebSocket服务器
function connectToAtuServer() {
    console.log('[ATU] 尝试连接到ATU WebSocket服务器，当前连接状态:', atuIsConnected);
    
    if (atuIsConnected) {
        console.log('[ATU] 已连接，无需重新连接');
        return;
    }
    
    if (atuConnectionAttempts >= MAX_CONNECTION_ATTEMPTS) {
        console.error('[ATU] ATU连接尝试次数过多，停止重连');
        updateAtuDisplay({ power: '--', swr: '--' });
        return;
    }
    
    const hostname = window.location.hostname;
    const serverUrl = `wss://${hostname}:8889/atu/ws`;  // 修改端口为8889，与ATU服务器一致
    
    console.log('[ATU] 连接URL:', serverUrl);
    
    try {
        atuSocket = new WebSocket(serverUrl);
        atuConnectionAttempts++;
        console.log('[ATU] 创建WebSocket连接，尝试次数:', atuConnectionAttempts);
        
        const connectionTimeout = setTimeout(() => {
            if (atuSocket && atuSocket.readyState === WebSocket.CONNECTING) {
                console.warn('[ATU] 连接超时，关闭连接');
                atuSocket.close();
            }
        }, 5000);
        
        atuSocket.onopen = () => {
            console.log('[ATU] WebSocket连接已建立');
            clearTimeout(connectionTimeout);
            atuIsConnected = true;
            // 确保全局变量也更新
            if (typeof window !== 'undefined') {
                window.atuIsConnected = true;
            }
            atuConnectionAttempts = 0; // 重置重连计数
            
            console.log('[ATU] ATU WebSocket连接已建立');
            
            // 连接成功后立即发送状态查询
            setTimeout(() => {
                try {
                    const statusCommand = {
                        type: 'command',
                        command: 'status'
                    };
                    console.log('[ATU] 发送状态查询命令');
                    atuSocket.send(JSON.stringify(statusCommand));
                    console.log('[ATU] 已发送ATU状态查询命令');
                } catch (error) {
                    console.error('[ATU] 发送ATU状态查询命令失败:', error);
                }
            }, 1000);
        };
        
        atuSocket.onclose = (event) => {
            console.log('[ATU] WebSocket连接已关闭，代码: ' + event.code + ', 原因: ' + event.reason);
            clearTimeout(connectionTimeout);
            atuIsConnected = false;
            // 确保全局变量也更新
            if (typeof window !== 'undefined') {
                window.atuIsConnected = false;
            }
            console.log('[ATU] ATU WebSocket连接已关闭，代码: ' + event.code + ', 原因: ' + event.reason);
            
            // 自动重连
            setTimeout(() => {
                console.log('[ATU] 尝试重新连接ATU服务器...');
                connectToAtuServer();
            }, 5000);
        };
        
        atuSocket.onerror = (event) => {
            console.error('[ATU] WebSocket连接错误:', event);
            clearTimeout(connectionTimeout);
            atuIsConnected = false;
            // 确保全局变量也更新
            if (typeof window !== 'undefined') {
                window.atuIsConnected = false;
            }
            console.log('[ATU] ATU WebSocket连接错误:', event);
        };
        
        atuSocket.onmessage = (event) => {
            console.log('[ATU] 接收到ATU WebSocket消息:', event.data);
            handleAtuMessage(event.data);
        };
        
    } catch (error) {
        console.error('[ATU] ATU WebSocket连接失败:', error);
        atuIsConnected = false;
    }
}

// 处理ATU消息
function handleAtuMessage(message) {
    console.log('[ATU] 开始处理ATU消息:', message);
    
    try {
        const data = JSON.parse(message);
        console.log('[ATU] 接收到ATU消息:', data);
        
        if (data.type === 'data') {
            console.log('[ATU] 处理数据类型消息:', data.data);
            updateAtuDisplay(data.data);
        } else if (data.type === 'status') {
            console.log('[ATU] 处理状态类型消息:', data);
            // 处理状态信息
        } else {
            console.warn('[ATU] 未知消息类型:', data.type);
        }
    } catch (error) {
        console.error('[ATU] ATU消息处理错误:', error, '原始消息:', message);
    }
}

// 更新ATU显示
function updateAtuDisplay(data) {
    console.log('[ATU] 更新ATU显示:', data);
    
    // 更新功率显示
    const powerElement = document.getElementById('power-value');
    if (powerElement && data.power !== undefined) {
        powerElement.textContent = data.power + ' W';
        // 根据功率值设置颜色
        if (data.power > 0) {
            powerElement.style.color = '#ff9900'; // 橙色表示有功率输出
        } else {
            powerElement.style.color = '#4CAF50'; // 绿色表示无功率
        }
        console.log('[ATU] 功率更新:', data.power + ' W');
    }
    
    // 更新SWR显示
    const swrElement = document.getElementById('swr-value');
    if (swrElement && data.swr !== undefined) {
        swrElement.textContent = data.swr;
        // 根据SWR值设置颜色
        if (data.swr > 2.0) {
            swrElement.style.color = '#ff4444'; // 红色表示高SWR
        } else if (data.swr > 1.5) {
            swrElement.style.color = '#ff9900'; // 橙色表示中等SWR
        } else {
            swrElement.style.color = '#44ff44'; // 绿色表示良好SWR
        }
        console.log('[ATU] SWR更新:', data.swr);
    }
    
    // 更新效率显示
    const efficiencyElement = document.getElementById('efficiency-value');
    if (efficiencyElement && data.efficiency !== undefined) {
        efficiencyElement.textContent = data.efficiency + ' %';
        // 根据效率值设置颜色
        if (data.efficiency > 80) {
            efficiencyElement.style.color = '#44ff44'; // 绿色表示高效率
        } else if (data.efficiency > 60) {
            efficiencyElement.style.color = '#ff9900'; // 橙色表示中等效率
        } else {
            efficiencyElement.style.color = '#ff4444'; // 红色表示低效率
        }
        console.log('[ATU] 效率更新:', data.efficiency + ' %');
    }
}

// 断开ATU连接
function disconnectFromAtuServer() {
    console.log('[ATU] 断开ATU连接');
    if (atuSocket) {
        console.log('[ATU] 关闭WebSocket连接');
        atuSocket.close();
        atuSocket = null;
    }
    atuIsConnected = false;
    console.log('[ATU] ATU连接已断开');
}

// 发送ATU同步命令
function sendAtuSyncCommand() {
    console.log('[ATU] 尝试发送ATU同步命令');
    
    if (!atuIsConnected || !atuSocket) {
        console.log('[ATU] ATU未连接或Socket不存在');
        return;
    }
    
    // 检查WebSocket连接状态
    if (atuSocket.readyState !== WebSocket.OPEN) {
        console.log('[ATU] ATU WebSocket连接未打开，当前状态：' + atuSocket.readyState);
        return;
    }
    
    try {
        const syncCommand = {
            type: 'command',
            command: 'sync'
        };
        
        console.log('[ATU] 发送同步命令');
        atuSocket.send(JSON.stringify(syncCommand));
        console.log('[ATU] 已发送ATU同步命令');
    } catch (error) {
        console.error('[ATU] 发送ATU同步命令失败:', error);
    }
}

// 页面加载完成后初始化ATU显示
if (typeof window !== 'undefined') {
    window.addEventListener('load', function() {
        console.log('[ATU] 页面加载完成，准备初始化ATU显示系统...');
        // 增加延迟确保其他组件已加载
        setTimeout(initAtuDisplay, 2000); // 延迟2秒确保页面完全加载
    });
    
    // 页面卸载时清理资源
    window.addEventListener('beforeunload', function() {
        console.log('[ATU] 页面卸载，清理ATU资源...');
        disconnectFromAtuServer();
    });
}

// 每秒发送一次同步命令以获取实时数据
let atuSyncInterval = null;
function startAtuSync() {
    console.log('[ATU] 启动ATU数据同步');
    
    // 先停止现有的同步（如果有的话）
    if (atuSyncInterval) {
        console.log('[ATU] 清除现有的同步定时器');
        clearInterval(atuSyncInterval);
        atuSyncInterval = null;
    }
    
    // 每秒发送一次同步命令
    console.log('[ATU] 设置新的同步定时器，每秒发送一次同步命令');
    atuSyncInterval = setInterval(() => {
        console.log('[ATU] 定时器触发，检查连接状态');
        if (atuIsConnected && atuSocket && atuSocket.readyState === WebSocket.OPEN) {
            console.log('[ATU] 连接正常，发送同步命令');
            sendAtuSyncCommand();
        } else {
            console.log('[ATU] 连接异常，跳过同步命令发送');
        }
    }, 1000); // 每秒更新一次
    
    console.log('[ATU] ATU数据同步已启动');
}

function stopAtuSync() {
    console.log('[ATU] 停止ATU数据同步');
    if (atuSyncInterval) {
        console.log('[ATU] 清除同步定时器');
        clearInterval(atuSyncInterval);
        atuSyncInterval = null;
    }
    console.log('[ATU] ATU数据同步已停止');
}

// 导出函数和变量供其他脚本使用
if (typeof window !== 'undefined') {
    window.initAtuDisplay = initAtuDisplay;
    window.connectToAtuServer = connectToAtuServer;
    window.disconnectFromAtuServer = disconnectFromAtuServer;
    window.updateAtuDisplay = updateAtuDisplay;
    window.sendAtuSyncCommand = sendAtuSyncCommand;
    window.startAtuSync = startAtuSync;
    window.stopAtuSync = stopAtuSync;
    // 导出atuSocket变量
    Object.defineProperty(window, 'atuSocket', {
        get: function() {
            return atuSocket;
        },
        set: function(value) {
            atuSocket = value;
        }
    });
    Object.defineProperty(window, 'atuIsConnected', {
        get: function() {
            return atuIsConnected;
        },
        set: function(value) {
            atuIsConnected = value;
        }
    });
}
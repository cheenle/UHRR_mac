// ATU测试脚本 - 用于测试与ATR-1000天调设备的通信
// 通过后端代理与ATU设备通信，解决混合内容问题

class AtuTester {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.reconnectInterval = 2000;
        
        // ATU设备命令常量
        this.tuningModes = {
            RESET: 0,
            MEMORY: 1,
            FULL: 2,
            FINE: 3
        };
        
        this.tuningStatus = {
            BYPASS: 0,
            TUNE: 1
        };
    }
    
    connect() {
        try {
            // 连接到后端ATU代理服务器
            const hostname = window.location.hostname;
            const url = `wss://${hostname}:8889/atu/ws`;
            
            // 如果已有连接，先关闭
            if (this.ws) {
                this.ws.close();
            }
            
            this.ws = new WebSocket(url);
            
            this.ws.onopen = () => {
                this.isConnected = true;
                // 更新页面连接状态
                this.updateConnectionStatus(true);
            };
            
            this.ws.onclose = () => {
                this.isConnected = false;
                // 更新页面连接状态
                this.updateConnectionStatus(false);
            };
            
            this.ws.onerror = (error) => {
                this.isConnected = false;
                // 更新页面连接状态
                this.updateConnectionStatus(false);
            };
            
            this.ws.onmessage = (event) => {
                this.handleMessage(event.data);
            };
        } catch (error) {
            this.isConnected = false;
            // 更新页面连接状态
            this.updateConnectionStatus(false);
        }
    }
    
    updateConnectionStatus(connected) {
        // 更新页面上的连接状态显示
        const statusDiv = document.getElementById('status');
        if (statusDiv) {
            if (connected) {
                statusDiv.className = 'status status-connected';
                statusDiv.textContent = 'ATU代理服务器已连接';
            } else {
                statusDiv.className = 'status status-disconnected';
                statusDiv.textContent = 'ATU代理服务器未连接';
            }
        }
    }
    
    handleMessage(message) {
        try {
            const data = JSON.parse(message);
            
            if (data.type === 'data') {
                // 处理ATU数据
                if (data.data.power !== undefined || data.data.swr !== undefined) {
                    // 更新页面显示
                    this.updateDisplay(data.data);
                }
            } else if (data.type === 'status') {
                // 更新连接状态
                if (data.connected !== undefined) {
                    this.updateConnectionStatus(data.connected);
                }
            }
        } catch (error) {
            console.error('消息处理错误:', error);
        }
    }
    
    updateDisplay(data) {
        // 更新功率显示
        const powerElement = document.getElementById('power-value');
        if (powerElement && data.power !== undefined) {
            powerElement.textContent = data.power;
        }
        
        // 更新SWR显示
        const swrElement = document.getElementById('swr-value');
        if (swrElement && data.swr !== undefined) {
            swrElement.textContent = data.swr;
        }
        
        // 更新效率显示
        const efficiencyElement = document.getElementById('efficiency-value');
        if (efficiencyElement && data.efficiency !== undefined) {
            efficiencyElement.textContent = data.efficiency;
        }
    }
    
    sendCommand(command, value = null, additionalData = {}) {
        if (!this.isConnected || !this.ws) {
            return;
        }
        
        if (this.ws.readyState !== WebSocket.OPEN) {
            return;
        }
        
        try {
            const cmdData = {
                type: 'command',
                command: command,
                ...additionalData
            };
            
            if (value !== null) {
                cmdData.value = value;
            }
            
            this.ws.send(JSON.stringify(cmdData));
        } catch (error) {
            console.error('发送命令失败:', error);
        }
    }
    
    // 调谐控制命令
    setTuneStatus(status) {
        this.sendCommand('tune_status', status);
    }
    
    setTuneMode(mode) {
        this.sendCommand('tune_mode', mode);
    }
    
    // 继电器控制命令
    setRelayStatus(sw, ind, cap) {
        this.sendCommand('relay_status', null, {
            sw: sw,
            ind: ind,
            cap: cap
        });
    }
    
    // 同步命令
    sync() {
        this.sendCommand('sync');
    }
    
    // 快捷命令
    startFullTune() {
        this.setTuneMode(this.tuningModes.FULL);
        this.setTuneStatus(this.tuningStatus.TUNE);
    }
    
    startMemoryTune() {
        this.setTuneMode(this.tuningModes.MEMORY);
        this.setTuneStatus(this.tuningStatus.TUNE);
    }
    
    setBypass() {
        this.setTuneStatus(this.tuningStatus.BYPASS);
    }
}

// 创建ATU测试器实例
const atuTester = new AtuTester();

// 提供全局函数供控制台调用
window.atuTester = atuTester;
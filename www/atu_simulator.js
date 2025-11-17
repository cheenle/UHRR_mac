// ATU模拟测试脚本
// 用于测试页面在有数据时的显示效果

class AtuSimulator {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.isSimulating = false;
        this.simulationInterval = null;
    }
    
    connect() {
        try {
            // 连接到ATU服务器
            const hostname = window.location.hostname;
            const url = `wss://${hostname}:8889/atu/ws`;
            
            if (this.ws) {
                this.ws.close();
            }
            
            this.ws = new WebSocket(url);
            
            this.ws.onopen = () => {
                this.isConnected = true;
                console.log('ATU服务器连接成功');
                this.updateStatus('已连接到ATU服务器');
            };
            
            this.ws.onclose = () => {
                this.isConnected = false;
                console.log('ATU服务器连接关闭');
                this.updateStatus('ATU服务器连接已关闭');
                this.stopSimulation();
            };
            
            this.ws.onerror = (error) => {
                this.isConnected = false;
                console.error('ATU服务器连接错误:', error);
                this.updateStatus('ATU服务器连接错误');
                this.stopSimulation();
            };
            
            this.ws.onmessage = (event) => {
                // 处理来自服务器的消息
                console.log('收到服务器消息:', event.data);
            };
        } catch (error) {
            this.isConnected = false;
            console.error('连接创建失败:', error);
            this.updateStatus('连接创建失败: ' + error);
        }
    }
    
    updateStatus(message) {
        const statusElement = document.getElementById('status');
        if (statusElement) {
            statusElement.textContent = message;
        }
    }
    
    startSimulation() {
        if (!this.isConnected) {
            console.log('未连接到服务器，无法开始模拟');
            return;
        }
        
        if (this.isSimulating) {
            console.log('模拟已在运行');
            return;
        }
        
        this.isSimulating = true;
        console.log('开始模拟ATU数据...');
        this.updateStatus('正在模拟ATU数据...');
        
        // 每500ms发送一次模拟数据
        this.simulationInterval = setInterval(() => {
            this.sendSimulatedData();
        }, 500);
    }
    
    stopSimulation() {
        if (this.simulationInterval) {
            clearInterval(this.simulationInterval);
            this.simulationInterval = null;
        }
        this.isSimulating = false;
        console.log('停止模拟ATU数据');
        this.updateStatus('模拟已停止');
    }
    
    sendSimulatedData() {
        if (!this.isConnected || !this.ws) {
            return;
        }
        
        if (this.ws.readyState !== WebSocket.OPEN) {
            return;
        }
        
        // 生成模拟数据
        const data = {
            type: 'data',
            data: {
                power: Math.floor(Math.random() * 100), // 0-100W随机功率
                swr: (1.0 + Math.random() * 2.0).toFixed(2), // 1.0-3.0随机SWR
                max_power: 100,
                efficiency: Math.floor(Math.random() * 100) // 0-100%随机效率
            },
            timestamp: new Date().toISOString()
        };
        
        try {
            this.ws.send(JSON.stringify(data));
            console.log('发送模拟数据:', data);
        } catch (error) {
            console.error('发送模拟数据失败:', error);
        }
    }
    
    sendCommand(command, value = null) {
        if (!this.isConnected || !this.ws) {
            return;
        }
        
        if (this.ws.readyState !== WebSocket.OPEN) {
            return;
        }
        
        try {
            const cmdData = {
                type: 'command',
                command: command
            };
            
            if (value !== null) {
                cmdData.value = value;
            }
            
            this.ws.send(JSON.stringify(cmdData));
            console.log('发送命令:', cmdData);
        } catch (error) {
            console.error('发送命令失败:', error);
        }
    }
}

// 创建模拟器实例
const atuSimulator = new AtuSimulator();

// 页面加载完成后初始化
window.addEventListener('load', function() {
    console.log('页面加载完成');
});

// 提供全局函数供控制台调用
window.atuSimulator = atuSimulator;
window.connect = () => atuSimulator.connect();
window.startSim = () => atuSimulator.startSimulation();
window.stopSim = () => atuSimulator.stopSimulation();
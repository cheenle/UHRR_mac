/**
 * ATU功率和驻波比监控系统
 * 实时监控天线调谐器的功率输出和驻波比状态
 */

class AtuMonitor {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.isMonitoring = false;
        this.dataHistory = [];
        this.alerts = [];
        this.config = {
            serverUrl: `wss://${window.location.hostname}:8889/atu/ws`,
            updateInterval: 200, // 降低到200ms，提高更新频率
            swrAlertThreshold: 2.0,
            maxHistoryLength: 200, // 增加历史数据长度
            pttStatus: false, // 当前PTT状态
            lastPttUpdate: 0,   // 最后PTT更新时间
            dataBuffer: [],     // 数据缓冲区
            lastDataTimestamp: 0 // 最后数据时间戳
        };

        // DOM元素引用
        this.initializeDomElements();
        
        // 加载配置
        this.loadConfig();
        
        // 绑定事件
        this.bindEvents();
        
        // 初始化图表
        this.initializeCharts();
        
        // 启动PTT状态监控
        this.startPttMonitoring();
        
        // 自动连接（可选）
        this.log('ATU监控系统初始化完成', 'info');
    }

    initializeDomElements() {
        // 状态指示器
        this.connectionStatus = document.getElementById('connectionStatus');
        this.connectionStatusText = document.getElementById('connectionStatusText');
        this.deviceInfo = document.getElementById('deviceInfo');
        
        
        // 控制按钮
        this.connectBtn = document.getElementById('connectBtn');
        this.disconnectBtn = document.getElementById('disconnectBtn');
        this.autoConnectBtn = document.getElementById('autoConnectBtn');
        
        // 数据卡片
        this.powerCard = document.getElementById('powerCard');
        this.swrCard = document.getElementById('swrCard');
        this.maxPowerCard = document.getElementById('maxPowerCard');
        this.efficiencyCard = document.getElementById('efficiencyCard');
        
        // 数据值
        this.powerValue = document.getElementById('powerValue');
        this.swrValue = document.getElementById('swrValue');
        this.maxPowerValue = document.getElementById('maxPowerValue');
        this.efficiencyValue = document.getElementById('efficiencyValue');
        
        // 趋势
        this.powerTrend = document.getElementById('powerTrend');
        this.swrTrend = document.getElementById('swrTrend');
        this.maxPowerTrend = document.getElementById('maxPowerTrend');
        this.efficiencyTrend = document.getElementById('efficiencyTrend');
        
        // 配置
        this.serverUrlInput = document.getElementById('serverUrl');
        this.updateIntervalInput = document.getElementById('updateInterval');
        this.swrAlertThresholdInput = document.getElementById('swrAlertThreshold');
        this.saveConfigBtn = document.getElementById('saveConfigBtn');
        this.resetConfigBtn = document.getElementById('resetConfigBtn');
        
        // 其他
        this.lastUpdateTime = document.getElementById('lastUpdateTime');
        this.alertsContainer = document.getElementById('alertsContainer');
        this.powerChart = document.getElementById('powerChart');
        this.swrChart = document.getElementById('swrChart');
    }

    bindEvents() {
        this.connectBtn.addEventListener('click', () => this.connect());
        this.disconnectBtn.addEventListener('click', () => this.disconnect());
        this.autoConnectBtn.addEventListener('click', () => this.autoConnect());
        this.saveConfigBtn.addEventListener('click', () => this.saveConfig());
        this.resetConfigBtn.addEventListener('click', () => this.resetConfig());
        
        // 配置变更监听
        this.serverUrlInput.addEventListener('change', () => this.updateConfig());
        this.updateIntervalInput.addEventListener('change', () => this.updateConfig());
        this.swrAlertThresholdInput.addEventListener('change', () => this.updateConfig());
    }

    initializeCharts() {
        // 初始化SVG图表
        this.powerChart.innerHTML = '';
        this.swrChart.innerHTML = '';
    }

    loadConfig() {
        try {
            const savedConfig = localStorage.getItem('atuMonitorConfig');
            if (savedConfig) {
                this.config = { ...this.config, ...JSON.parse(savedConfig) };
            }
            this.updateConfigDisplay();
        } catch (error) {
            this.log('加载配置失败: ' + error.message, 'error');
        }
    }

    saveConfig() {
        try {
            localStorage.setItem('atuMonitorConfig', JSON.stringify(this.config));
            this.log('配置已保存', 'success');
            this.showAlert('配置已保存', 'info');
        } catch (error) {
            this.log('保存配置失败: ' + error.message, 'error');
            this.showAlert('保存配置失败: ' + error.message, 'error');
        }
    }

    resetConfig() {
        this.config = {
            serverUrl: `wss://${window.location.hostname}:8889/atu/ws`,
            updateInterval: 1000,
            swrAlertThreshold: 2.0,
            maxHistoryLength: 100
        };
        this.updateConfigDisplay();
        this.log('配置已重置', 'info');
        this.showAlert('配置已重置', 'info');
    }

    updateConfig() {
        this.config.serverUrl = this.serverUrlInput.value;
        this.config.updateInterval = parseInt(this.updateIntervalInput.value);
        this.config.swrAlertThreshold = parseFloat(this.swrAlertThresholdInput.value);
    }

    updateConfigDisplay() {
        this.serverUrlInput.value = this.config.serverUrl;
        this.updateIntervalInput.value = this.config.updateInterval;
        this.swrAlertThresholdInput.value = this.config.swrAlertThreshold;
    }

    async connect() {
        if (this.isConnected) {
            this.log('已经连接到ATU服务器', 'warning');
            return;
        }

        this.updateConfig();
        this.updateConnectionStatus('connecting', '连接中...');

        try {
            const url = this.config.serverUrl;
            this.log(`尝试连接到ATU服务器: ${url}`, 'info');

            this.socket = new WebSocket(url);

            // 设置连接超时
            const connectionTimeout = setTimeout(() => {
                if (this.socket && this.socket.readyState === WebSocket.CONNECTING) {
                    this.socket.close();
                    this.updateConnectionStatus('disconnected', '连接超时');
                    this.log('ATU服务器连接超时', 'error');
                    this.showAlert('ATU服务器连接超时，请检查服务器是否运行', 'error');
                }
            }, 5000);

            this.socket.onopen = () => {
                clearTimeout(connectionTimeout);
                this.isConnected = true;
                this.updateConnectionStatus('connected', '已连接');
                this.log('ATU服务器连接成功', 'success');
                this.showAlert('ATU服务器连接成功', 'info');
                
                // 连接成功后发送状态查询
                setTimeout(() => {
                    this.sendStatusCommand();
                }, 500);
            };

            this.socket.onclose = (event) => {
                clearTimeout(connectionTimeout);
                this.isConnected = false;
                this.updateConnectionStatus('disconnected', '连接关闭');
                this.log(`ATU服务器连接关闭 (代码: ${event.code}, 原因: ${event.reason || '未知'})`, 'warning');
                this.showAlert('ATU服务器连接已断开', 'warning');
            };

            this.socket.onerror = (error) => {
                clearTimeout(connectionTimeout);
                this.isConnected = false;
                this.updateConnectionStatus('disconnected', '连接错误');
                this.log(`ATU服务器连接错误: 无法连接到 ${this.config.serverUrl}`, 'error');
                this.showAlert(`无法连接到ATU服务器 ${this.config.serverUrl}，请检查：<br>1. ATU服务器是否运行<br>2. 端口配置是否正确`, 'error');
            };

            this.socket.onmessage = (event) => {
                this.handleServerMessage(event.data);
            };

        } catch (error) {
            this.updateConnectionStatus('disconnected', '连接失败');
            this.log(`连接失败: ${error.message}`, 'error');
            this.showAlert('连接失败: ' + error.message, 'error');
        }
    }


    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.isConnected = false;
        this.updateConnectionStatus('disconnected', '已断开');
        this.log('手动断开连接', 'info');
        this.showAlert('已断开ATU设备连接', 'info');
    }

    async autoConnect() {
        this.log('开始自动连接流程...', 'info');
        
        // 尝试常见服务器URL
        const commonUrls = [
            `wss://${window.location.hostname}:8889/atu/ws`,
            'wss://127.0.0.1:8889/atu/ws',
            `wss://${window.location.hostname}:8890/atu/ws`,
            'wss://127.0.0.1:8890/atu/ws'
        ];
        
        for (const url of commonUrls) {
            this.config.serverUrl = url;
            this.updateConfigDisplay();
            
            this.log(`尝试服务器 ${url}...`, 'info');
            
            try {
                await this.connect();
                
                // 等待连接状态
                await new Promise(resolve => setTimeout(resolve, 2000));
                
                if (this.isConnected) {
                    this.log(`自动连接成功，使用服务器 ${url}`, 'success');
                    this.showAlert(`自动连接成功，使用服务器 ${url}`, 'info');
                    return;
                }
            } catch (error) {
                this.log(`服务器 ${url} 连接失败: ${error.message}`, 'warning');
            }
        }
        
        this.log('自动连接失败，请手动配置', 'error');
        this.showAlert('自动连接失败，请检查ATU服务器是否运行', 'error');
    }


    handleServerMessage(message) {
        try {
            const data = JSON.parse(message);
            
            if (data.type === 'data') {
                // 处理ATU数据
                this.handleAtuData(data.data);
            } else if (data.type === 'status') {
                // 处理状态信息
                this.log(`ATU设备状态: ${data.message}, 连接状态: ${data.connected}`, 'info');
            }
        } catch (error) {
            this.log(`服务器消息处理错误: ${error.message}`, 'error');
        }
    }

    handleAtuData(data) {
        try {
            const currentTime = Date.now();
            
            // 数据缓冲和去抖动
            this.config.dataBuffer.push({
                timestamp: currentTime,
                power: data.power,
                swr: data.swr,
                maxPower: data.max_power,
                efficiency: data.efficiency
            });
            
            // 限制缓冲区大小
            if (this.config.dataBuffer.length > 5) {
                this.config.dataBuffer.shift();
            }
            
            // 计算平均值，减少抖动
            const avgData = this.calculateAverageData();
            
            // 更新显示
            this.updateDisplay(avgData.power, avgData.swr, avgData.maxPower, avgData.efficiency);
            
            // 添加到历史数据
            this.addToHistory({
                timestamp: currentTime,
                power: avgData.power,
                swr: avgData.swr,
                maxPower: avgData.maxPower,
                efficiency: avgData.efficiency
            });

            // 检查告警
            this.checkAlerts(avgData.power, avgData.swr, avgData.efficiency);

        } catch (error) {
            this.log(`ATU数据处理错误: ${error.message}`, 'error');
        }
    }

    calculateAverageData() {
        if (this.config.dataBuffer.length === 0) {
            return { power: 0, swr: 0, maxPower: 0, efficiency: 0 };
        }
        
        const sum = this.config.dataBuffer.reduce((acc, data) => {
            acc.power += data.power;
            acc.swr += data.swr;
            acc.maxPower += data.maxPower;
            acc.efficiency += data.efficiency;
            return acc;
        }, { power: 0, swr: 0, maxPower: 0, efficiency: 0 });
        
        const count = this.config.dataBuffer.length;
        return {
            power: Math.round(sum.power / count * 10) / 10, // 保留1位小数
            swr: Math.round(sum.swr / count * 100) / 100,   // 保留2位小数
            maxPower: Math.round(sum.maxPower / count),
            efficiency: Math.round(sum.efficiency / count * 10) / 10
        };
    }

    sendStatusCommand() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            try {
                const command = {
                    type: 'command',
                    command: 'status'
                };
                this.socket.send(JSON.stringify(command));
                this.log('发送状态查询命令', 'info');
            } catch (error) {
                this.log(`发送状态命令失败: ${error.message}`, 'error');
            }
        }
    }

    updateDisplay(power, swr, maxPower, efficiency) {
        const currentTime = Date.now();
        
        // 避免过于频繁的更新（至少100ms间隔）
        if (currentTime - this.config.lastDataTimestamp < 100) {
            return;
        }
        this.config.lastDataTimestamp = currentTime;
        
        // 更新数值（只更新有变化的）
        if (this.powerValue.textContent !== power.toString()) {
            this.powerValue.textContent = power;
        }
        if (this.swrValue.textContent !== swr.toString()) {
            this.swrValue.textContent = swr;
        }
        if (this.maxPowerValue.textContent !== maxPower.toString()) {
            this.maxPowerValue.textContent = maxPower;
        }
        if (this.efficiencyValue.textContent !== efficiency.toString()) {
            this.efficiencyValue.textContent = efficiency;
        }

        // 更新趋势
        this.updateTrends(power, swr, maxPower, efficiency);

        // 更新卡片状态
        this.updateCardStatus(power, swr, efficiency);

        // 更新最后更新时间
        this.lastUpdateTime.textContent = new Date().toLocaleTimeString();

        // 图表更新频率降低（每5次数据更新一次图表）
        if (this.dataHistory.length % 5 === 0) {
            this.updateCharts();
        }
    }

    updateTrends(power, swr, maxPower, efficiency) {
        if (this.dataHistory.length < 2) {
            this.powerTrend.textContent = '--';
            this.swrTrend.textContent = '--';
            this.maxPowerTrend.textContent = '--';
            this.efficiencyTrend.textContent = '--';
            return;
        }

        const prevData = this.dataHistory[this.dataHistory.length - 2];
        
        this.updateSingleTrend(this.powerTrend, power, prevData.power, 'W');
        this.updateSingleTrend(this.swrTrend, swr, prevData.swr, '');
        this.updateSingleTrend(this.maxPowerTrend, maxPower, prevData.maxPower, 'W');
        this.updateSingleTrend(this.efficiencyTrend, efficiency, prevData.efficiency, '%');
    }

    updateSingleTrend(element, current, previous, unit) {
        const diff = current - previous;
        const absDiff = Math.abs(diff);
        
        if (absDiff < 0.1) {
            element.textContent = '稳定';
            element.className = 'data-trend trend-stable';
        } else if (diff > 0) {
            element.textContent = `↑ ${absDiff.toFixed(1)}${unit}`;
            element.className = 'data-trend trend-up';
        } else {
            element.textContent = `↓ ${absDiff.toFixed(1)}${unit}`;
            element.className = 'data-trend trend-down';
        }
    }

    updateCardStatus(power, swr, efficiency) {
        // 功率卡片状态
        if (power === 0) {
            this.powerCard.className = 'data-card';
        } else if (power > 50) {
            this.powerCard.className = 'data-card critical';
        } else if (power > 25) {
            this.powerCard.className = 'data-card warning';
        } else {
            this.powerCard.className = 'data-card normal';
        }

        // SWR卡片状态
        const swrNum = parseFloat(swr);
        if (swrNum > this.config.swrAlertThreshold) {
            this.swrCard.className = 'data-card critical';
        } else if (swrNum > 1.5) {
            this.swrCard.className = 'data-card warning';
        } else {
            this.swrCard.className = 'data-card normal';
        }

        // 效率卡片状态
        const effNum = parseFloat(efficiency);
        if (effNum < 50) {
            this.efficiencyCard.className = 'data-card critical';
        } else if (effNum < 80) {
            this.efficiencyCard.className = 'data-card warning';
        } else {
            this.efficiencyCard.className = 'data-card normal';
        }

        // PTT卡片状态
        this.updatePttCardStatus();
    }

    addToHistory(data) {
        this.dataHistory.push(data);
        
        // 限制历史数据长度
        if (this.dataHistory.length > this.config.maxHistoryLength) {
            this.dataHistory.shift();
        }
    }

    updateCharts() {
        if (this.dataHistory.length < 2) return;

        // 简化的图表更新 - 实际项目中可以使用Chart.js等库
        this.updateSimpleChart(this.powerChart, this.dataHistory.map(d => d.power), '#4CAF50');
        this.updateSimpleChart(this.swrChart, this.dataHistory.map(d => d.swr), '#2196F3');
    }

    updateSimpleChart(chartElement, data, color) {
        const width = chartElement.clientWidth;
        const height = chartElement.clientHeight;
        
        chartElement.setAttribute('width', width);
        chartElement.setAttribute('height', height);
        
        // 清空现有内容
        chartElement.innerHTML = '';
        
        if (data.length < 2) return;
        
        const maxValue = Math.max(...data);
        const minValue = Math.min(...data);
        const range = maxValue - minValue || 1;
        
        const points = data.map((value, index) => {
            const x = (index / (data.length - 1)) * width;
            const y = height - ((value - minValue) / range) * height;
            return `${x},${y}`;
        }).join(' ');
        
        const polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
        polyline.setAttribute('points', points);
        polyline.setAttribute('stroke', color);
        polyline.setAttribute('stroke-width', '2');
        polyline.setAttribute('fill', 'none');
        
        chartElement.appendChild(polyline);
    }

    checkAlerts(power, swr, efficiency) {
        const swrNum = parseFloat(swr);
        const powerNum = parseFloat(power);
        const efficiencyNum = parseFloat(efficiency);

        // SWR告警
        if (swrNum > this.config.swrAlertThreshold) {
            this.showAlert(`SWR过高: ${swr}`, 'error');
        }

        // 功率告警
        if (powerNum > 50) {
            this.showAlert(`功率过高: ${power}W`, 'warning');
        }

        // 效率告警
        if (efficiencyNum < 50 && powerNum > 0) {
            this.showAlert(`传输效率过低: ${efficiency}%`, 'warning');
        }
    }

    showAlert(message, type = 'info') {
        const alert = {
            id: Date.now(),
            message,
            type,
            timestamp: new Date().toLocaleTimeString()
        };

        this.alerts.unshift(alert);
        
        // 限制告警数量
        if (this.alerts.length > 10) {
            this.alerts.pop();
        }

        this.updateAlertsDisplay();
    }

    updateAlertsDisplay() {
        this.alertsContainer.innerHTML = '';

        this.alerts.forEach(alert => {
            const alertElement = document.createElement('div');
            alertElement.className = `alert-item ${alert.type}`;
            
            let icon = 'ℹ️';
            if (alert.type === 'error') icon = '❌';
            if (alert.type === 'warning') icon = '⚠️';

            alertElement.innerHTML = `
                <div class="alert-icon">${icon}</div>
                <div class="alert-content">
                    <strong>${alert.type.toUpperCase()}</strong>
                    <div>${alert.message}</div>
                </div>
                <div class="alert-time">${alert.timestamp}</div>
            `;

            this.alertsContainer.appendChild(alertElement);
        });
    }

    updateConnectionStatus(status, text) {
        this.connectionStatus.className = `status-indicator status-${status}`;
        this.connectionStatusText.textContent = text;
        
        // 更新按钮状态
        this.connectBtn.disabled = status === 'connected' || status === 'connecting';
        this.disconnectBtn.disabled = status !== 'connected';
        
        // 更新设备信息
        if (status === 'connected') {
            this.deviceInfo.textContent = ` - ${this.config.deviceIp}:${this.config.devicePort}`;
        } else {
            this.deviceInfo.textContent = ' - ATU设备';
        }
    }

    // PTT状态监控相关方法
    startPttMonitoring() {
        // 每500ms检查一次PTT状态
        this.pttMonitorInterval = setInterval(() => {
            this.checkPttStatus();
        }, 500);
        
        this.log('PTT状态监控已启动', 'info');
    }

    async checkPttStatus() {
        // 直接使用模拟数据，避免不必要的API调用
        this.simulatePttStatus();
    }

    parsePttStatusFromLog(logData) {
        const lines = logData.split('\n').reverse();
        
        // 查找最近的PTT状态记录
        for (const line of lines) {
            if (line.includes('rigctl_set_ptt:')) {
                const match = line.match(/ptt=(\d+)/);
                if (match) {
                    const pttValue = parseInt(match[1]);
                    const isPttOn = pttValue === 1;
                    
                    // 只有当状态改变时才更新
                    if (this.config.pttStatus !== isPttOn) {
                        this.updatePttStatus(isPttOn);
                    }
                    break;
                }
            }
        }
    }

    simulatePttStatus() {
        // 模拟PTT状态变化，用于演示
        const currentTime = Date.now();
        if (currentTime - this.config.lastPttUpdate > 3000) {
            const randomPtt = Math.random() > 0.7; // 30%概率为发射状态
            this.updatePttStatus(randomPtt);
            this.config.lastPttUpdate = currentTime;
        }
    }

    updatePttStatus(isPttOn) {
        this.config.pttStatus = isPttOn;
        this.config.lastPttUpdate = Date.now();
        
        // 更新PTT显示
        this.updatePttCardStatus();
        
        // 记录状态变化
        if (isPttOn) {
            this.log('PTT状态：发射中', 'info');
        } else {
            this.log('PTT状态：未发射', 'info');
        }
    }

    updatePttCardStatus() {
        if (!this.pttCard || !this.pttValue || !this.pttTrend) return;
        
        if (this.config.pttStatus) {
            // PTT ON - 发射中
            this.pttCard.className = 'data-card ptt-on';
            this.pttValue.textContent = '发射中';
            this.pttValue.style.color = '#00ff00';
            this.pttTrend.textContent = 'TX';
            this.pttTrend.className = 'data-trend trend-up';
        } else {
            // PTT OFF - 未发射
            this.pttCard.className = 'data-card ptt-off';
            this.pttValue.textContent = '未发射';
            this.pttValue.style.color = '#ff4444';
            this.pttTrend.textContent = 'RX';
            this.pttTrend.className = 'data-trend trend-down';
        }
    }

    log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        console.log(`[${timestamp}] [ATU Monitor] ${message}`);
    }
}

// 页面加载完成后初始化
window.addEventListener('load', () => {
    const atuMonitor = new AtuMonitor();
    
    // 暴露全局方法
    window.atuMonitor = atuMonitor;
});
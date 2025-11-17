// ATU自动调谐功能模块
// 在PTT激活时自动调整天调并使SWR最小化

class AtuAutoTune {
    constructor() {
        this.isEnabled = false;
        this.isTuning = false;
        this.lastSwr = 0;
        this.tuneAttempts = 0;
        this.maxTuneAttempts = 3;
        this.swrThreshold = 1.5; // SWR阈值，低于此值认为已调谐好
        this.tuneDelay = 1000;   // 调谐延迟（毫秒）
        this.frequency = 0;      // 当前频率
        this.tuningNetwork = 'LC'; // 当前调谐网络
        this.tuningCapacitance = 0; // 当前电容值
        this.tuningInductance = 0;  // 当前电感值
        
        // 存储优化配置参数的对象
        this.optimizedConfigs = {};
        
        // 绑定事件监听器
        this.setupEventListeners();
        
        console.log('🔧 ATU自动调谐模块已初始化');
        console.log('🔧 当前配置: SWR阈值=' + this.swrThreshold + ', 最大尝试次数=' + this.maxTuneAttempts);
    }
    
    // 设置事件监听器
    setupEventListeners() {
        // 监听PTT状态变化
        if (typeof window.updatePTTStatus !== 'undefined') {
            // 保存原始函数
            const originalUpdatePTTStatus = window.updatePTTStatus;
            
            // 重写函数
            window.updatePTTStatus = (isPTTOn) => {
                // 调用原始函数
                originalUpdatePTTStatus(isPTTOn);
                
                // 处理PTT状态变化
                this.handlePTTStatusChange(isPTTOn);
            };
        }
        
        // 监听频率变化
        window.updateFrequency = (freq) => {
            this.frequency = freq;
        };
    }
    
    // 处理PTT状态变化
    handlePTTStatusChange(isPTTOn) {
        if (!this.isEnabled) {
            return;
        }
        
        if (isPTTOn) {
            this.checkAndTune();
        } else {
            this.resetTuningState();
        }
    }
    
    // 检查并执行调谐
    async checkAndTune() {
        if (this.isTuning) {
            return;
        }
        
        // 获取当前SWR
        const currentSwr = this.getCurrentSwr();
        
        // 检查是否需要调谐
        if (currentSwr <= this.swrThreshold) {
            return;
        }
        
        // 检查是否已存在该频率的优化配置
        const freqKey = this.frequency.toFixed(3); // 保留3位小数作为频率键
        const storedConfig = this.getStoredConfig(freqKey);
        
        if (storedConfig) {
            await this.applyStoredConfig(storedConfig);
            
            // 短暂等待后检查SWR
            await new Promise(resolve => setTimeout(resolve, 500));
            const updatedSwr = this.getCurrentSwr();
            
            if (updatedSwr <= this.swrThreshold) {
                return;
            }
        }
        
        // 开始调谐过程
        await this.startTuningProcess();
    }
    
    // 获取当前SWR值
    getCurrentSwr() {
        // 从ATU显示元素获取SWR值
        const swrElement = document.getElementById('swr-value');
        if (swrElement) {
            const swrText = swrElement.textContent.trim();
            const swrValue = parseFloat(swrText);
            if (!isNaN(swrValue)) {
                return swrValue;
            }
        }
        
        // 如果无法获取，返回上次记录的值
        return this.lastSwr;
    }
    
    // 获取当前频率
    getCurrentFrequency() {
        // 从频率显示元素获取频率值
        try {
            const freq = parseInt(
                document.getElementById("cmhz").innerHTML +
                document.getElementById("dmhz").innerHTML +
                document.getElementById("umhz").innerHTML +
                document.getElementById("ckhz").innerHTML +
                document.getElementById("dkhz").innerHTML +
                document.getElementById("ukhz").innerHTML +
                document.getElementById("chz").innerHTML +
                document.getElementById("dhz").innerHTML +
                document.getElementById("uhz").innerHTML
            );
            
            if (!isNaN(freq) && freq > 0) {
                this.frequency = freq;
                return freq;
            }
        } catch (error) {
            console.error('获取频率失败:', error);
        }
        
        return this.frequency;
    }
    
    // 获取已存储的配置
    getStoredConfig(freqKey) {
        if (this.optimizedConfigs[freqKey]) {
            return this.optimizedConfigs[freqKey];
        }
        
        // 尝试从localStorage获取
        const storedData = localStorage.getItem('atu_optimized_configs');
        if (storedData) {
            try {
                const configs = JSON.parse(storedData);
                if (configs[freqKey]) {
                    this.optimizedConfigs[freqKey] = configs[freqKey];
                    return configs[freqKey];
                }
            } catch (error) {
                console.error('❌ 解析存储的配置失败:', error);
            }
        }
        
        return null;
    }
    
    // 存储优化配置
    storeConfig(freqKey, config) {
        this.optimizedConfigs[freqKey] = config;
        
        // 保存到localStorage
        try {
            localStorage.setItem('atu_optimized_configs', JSON.stringify(this.optimizedConfigs));
        } catch (error) {
            console.error('存储配置失败:', error);
        }
    }
    
    // 应用已存储的配置
    async applyStoredConfig(config) {
        // 通过WebSocket发送命令到ATU设备
        if (typeof window.atuSocket !== 'undefined' && atuSocket && atuSocket.readyState === WebSocket.OPEN) {
            try {
                // 设置调谐网络
                if (config.network) {
                    const networkValue = config.network === 'CL' ? 1 : 0;
                    const networkCommand = {
                        type: 'command',
                        command: 'relay_status',
                        sw: networkValue,
                        ind: config.inductance || 0,
                        cap: config.capacitance || 0
                    };
                    atuSocket.send(JSON.stringify(networkCommand));
                }
                
                // 设置电容和电感值
                if (config.capacitance !== undefined && config.inductance !== undefined) {
                    const relayCommand = {
                        type: 'command',
                        command: 'relay_status',
                        sw: config.network === 'CL' ? 1 : 0,
                        ind: Math.round(config.inductance), // 电感继电器值
                        cap: config.capacitance // 电容继电器值
                    };
                    atuSocket.send(JSON.stringify(relayCommand));
                }
            } catch (error) {
                console.error('应用存储配置失败:', error);
            }
        }
        
        // 短暂等待让设置生效
        await new Promise(resolve => setTimeout(resolve, 300));
    }
    
    // 开始调谐过程
    async startTuningProcess() {
        this.isTuning = true;
        this.tuneAttempts = 0;
        
        // 发送完整调谐命令
        await this.sendTuneCommand(2); // 2 = 完整调谐模式
        
        // 等待调谐完成
        await this.waitForTuningCompletion();
    }
    
    // 发送调谐命令
    sendTuneCommand(mode) {
        return new Promise((resolve) => {
            // 通过WebSocket发送调谐命令到ATU设备
            if (typeof window.atuSocket !== 'undefined' && atuSocket && atuSocket.readyState === WebSocket.OPEN) {
                try {
                    const tuneCommand = {
                        type: 'command',
                        command: 'tune_mode',
                        value: mode // 0=重置, 1=内存调谐, 2=完整调谐, 3=微调
                    };
                    
                    atuSocket.send(JSON.stringify(tuneCommand));
                    
                    // 立即发送调谐状态命令
                    const statusCommand = {
                        type: 'command',
                        command: 'tune_status',
                        value: 1 // 1 = 调谐状态
                    };
                    
                    atuSocket.send(JSON.stringify(statusCommand));
                } catch (error) {
                    console.error('发送调谐命令失败:', error);
                }
            }
            
            // 延迟一段时间以确保命令发送
            setTimeout(resolve, 100);
        });
    }
    
    // 等待调谐完成
    async waitForTuningCompletion() {
        // 等待一段时间让调谐完成
        await new Promise(resolve => setTimeout(resolve, this.tuneDelay));
        
        // 检查调谐结果
        await this.checkTuningResult();
    }
    
    // 检查调谐结果
    async checkTuningResult() {
        this.tuneAttempts++;
        const currentSwr = this.getCurrentSwr();
        const freqKey = this.frequency.toFixed(3);
        
        // 检查调谐是否成功
        if (currentSwr <= this.swrThreshold) {
            // 获取当前调谐参数并存储
            // 注意：这里需要从ATU设备获取实际的继电器状态
            // 由于我们无法直接获取，暂时使用默认值
            const successConfig = {
                network: this.tuningNetwork,
                capacitance: this.tuningCapacitance,
                inductance: this.tuningInductance,
                swr: currentSwr,
                timestamp: Date.now()
            };
            
            this.storeConfig(freqKey, successConfig);
            
            this.isTuning = false;
            return;
        }
        
        // 如果还未达到最大尝试次数，继续调谐
        if (this.tuneAttempts < this.maxTuneAttempts) {
            await this.startTuningProcess();
        } else {
            this.isTuning = false;
        }
    }
    
    // 重置调谐状态
    resetTuningState() {
        this.isTuning = false;
        this.tuneAttempts = 0;
        this.lastSwr = this.getCurrentSwr();
        
        // 发送直通状态命令
        if (typeof window.atuSocket !== 'undefined' && atuSocket && atuSocket.readyState === WebSocket.OPEN) {
            try {
                const statusCommand = {
                    type: 'command',
                    command: 'tune_status',
                    value: 0 // 0 = 直通状态
                };
                
                atuSocket.send(JSON.stringify(statusCommand));
            } catch (error) {
                console.error('发送直通状态命令失败:', error);
            }
        }
    }
    
    // 启用自动调谐
    enable() {
        this.isEnabled = true;
    }
    
    // 禁用自动调谐
    disable() {
        this.isEnabled = false;
    }
    
    // 设置SWR阈值
    setSwrThreshold(threshold) {
        this.swrThreshold = threshold;
    }
    
    // 设置最大调谐尝试次数
    setMaxTuneAttempts(attempts) {
        this.maxTuneAttempts = attempts;
    }
    
    // 获取所有存储的配置
    getAllStoredConfigs() {
        return this.optimizedConfigs;
    }
    
    // 清除存储的配置
    clearStoredConfigs() {
        this.optimizedConfigs = {};
        localStorage.removeItem('atu_optimized_configs');
        console.log('🗑️ 已清除所有存储的配置');
    }
}

// 初始化ATU自动调谐模块
const atuAutoTune = new AtuAutoTune();

// 页面加载完成后启用自动调谐
window.addEventListener('load', function() {
    // 启用ATU自动调谐
    atuAutoTune.enable();
    
    // 设置SWR阈值
    atuAutoTune.setSwrThreshold(1.5);
    
    // 设置最大调谐尝试次数
    atuAutoTune.setMaxTuneAttempts(3);
});

// 导出模块供其他脚本使用
if (typeof window !== 'undefined') {
    window.atuAutoTune = atuAutoTune;
}
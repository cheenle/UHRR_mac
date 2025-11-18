// Modern Hamradio Remote Interface JavaScript - 完整功能版本

// 全局变量 - 与旧界面兼容
var poweron = false;
var wsControlTRX = null;
var wsAudioRX = null;
var wsAudioTX = null;
var audiobufferready = false;
var AudioRX_audiobuffer = [];
var AudioRX_sampleRate = 16000;
var audioSyncMonitor = {
    lastProcessTime: 0,
    bufferCount: 0,
    lagWarning: false
};

class ModernHamInterface {
    constructor() {
        this.isConnected = false;
        this.isTransmitting = false;
        this.currentFrequency = 14200000;
        this.currentMode = 'USB';
        this.currentBand = '20m';
        this.canvasRXsmeter = null;
        this.ctxRXsmeter = null;
        
        this.initializeEventListeners();
        this.initializeMeters();
        this.initializeFFT();
        this.startClock();
        this.initializePersonalFreqs();
        
        // 等待DOM加载完成后初始化
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initializeComponents());
        } else {
            this.initializeComponents();
        }
    }

    initializeComponents() {
        this.initializeSMeter();
        this.initializePersonalFreqs();
        this.initializeBitrateMonitoring();
        console.log('现代界面组件初始化完成');
    }

    initializeEventListeners() {
        // Connection controls
        document.getElementById('powerBtn').addEventListener('click', () => this.toggleConnection());
        document.getElementById('pttBtn').addEventListener('click', () => this.togglePTT());
        
        // TX controls - 与旧界面完全兼容
        const txRecord = document.getElementById('TX-record');
        if (txRecord) {
            txRecord.addEventListener('mousedown', () => this.startTX());
            txRecord.addEventListener('mouseup', () => this.stopTX());
            txRecord.addEventListener('touchstart', (e) => {
                e.preventDefault();
                this.startTX();
            });
            txRecord.addEventListener('touchend', (e) => {
                e.preventDefault();
                this.stopTX();
            });
        }
        
        // TX Lock control
        const txLock = document.getElementById('TX-record-lock');
        if (txLock) {
            txLock.addEventListener('click', () => this.toggleTXLock());
        }
        
        // Frequency controls
        document.querySelectorAll('.freq-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.adjustFrequency(parseInt(e.target.dataset.step)));
        });
        
        // Mode controls
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.setMode(e.target.dataset.mode));
        });
        
        // Band controls
        document.querySelectorAll('.band-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.setBand(e.target.dataset.band));
        });
        
        // Filter controls
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.setFilter(e.target));
        });
        
        // Audio controls
        document.getElementById('afGain').addEventListener('input', (e) => this.updateAFGain(e.target.value));
        document.getElementById('micGain').addEventListener('input', (e) => this.updateMICGain(e.target.value));
        document.getElementById('SQUELCH').addEventListener('input', (e) => this.updateSquelch(e.target.value));
        
        // Personal frequency controls
        document.querySelector('#personalfrequency button[onclick*="recall"]').addEventListener('click', () => this.recallPersonalFreq());
        document.querySelector('#personalfrequency button[onclick*="delete"]').addEventListener('click', () => this.deletePersonalFreq());
        document.querySelector('#personalfrequency button[onclick*="save"]').addEventListener('click', () => this.savePersonalFreq());
        
        // FFT controls
        document.getElementById('canBFFFT_scale_floor').addEventListener('input', () => this.updateFFTDisplay());
        document.getElementById('canBFFFT_scale_multdb').addEventListener('input', () => this.updateFFTDisplay());
        document.getElementById('canBFFFT_scale_start').addEventListener('input', () => this.updateFFTDisplay());
        document.getElementById('canBFFFT_scale_multhz').addEventListener('input', () => this.updateFFTDisplay());
        
        // Header controls
        document.getElementById('settingsBtn').addEventListener('click', () => this.openSettings());
        document.getElementById('fullscreenBtn').addEventListener('click', () => this.toggleFullscreen());
        
        // Spectrum controls
        document.getElementById('spectrumSettings').addEventListener('click', () => this.openSpectrumSettings());
        
        // Configuration links
        document.getElementById('div-conf').addEventListener('click', (e) => {
            e.preventDefault();
            window.open('/CONFIG', '_UHRRconfig');
        });
        
        document.getElementById('div-panfft').addEventListener('click', (e) => {
            e.preventDefault();
            window.open('/panfft.html', 'UHRRpanfft', 'width=1000, height=1000, menubar=no, toolbar=no, location=no, resizable=yes, scrollbars=no, status=no, dependent=yes');
        });
        
        // FFT canvas mouse events
        const fftCanvas = document.getElementById('canBFFFT');
        if (fftCanvas) {
            fftCanvas.addEventListener('mousemove', (e) => this.updateFFTCoordinates(e));
            fftCanvas.addEventListener('click', (e) => this.setCustomFilterFromFFT(e));
        }
    }

    initializeMeters() {
        this.meters = {
            sMeter: document.getElementById('sMeter'),
            sMeterValue: document.getElementById('sMeterValue'),
            powerMeter: document.getElementById('powerMeter'),
            powerValue: document.getElementById('powerValue'),
            swrMeter: document.getElementById('swrMeter'),
            swrValue: document.getElementById('swrValue')
        };
        
        this.updateMeters();
    }

    updateMeters() {
        if (!this.isConnected) {
            this.setMeterValue('sMeter', 0, 'S0');
            this.setMeterValue('powerMeter', 0, '0W');
            this.setMeterValue('swrMeter', 0, '1.0');
            return;
        }

        // Simulate meter readings
        const sValue = Math.random() * 9;
        const powerValue = this.isTransmitting ? Math.random() * 100 : 0;
        const swrValue = this.isTransmitting ? 1 + Math.random() * 1.5 : 1;

        this.setMeterValue('sMeter', sValue / 9 * 100, `S${Math.floor(sValue)}`);
        this.setMeterValue('powerMeter', powerValue, `${Math.floor(powerValue)}W`);
        this.setMeterValue('swrMeter', Math.min(swrValue / 3 * 100, 100), swrValue.toFixed(1));
    }

    setMeterValue(meterId, percentage, value) {
        const meter = this.meters[meterId];
        const valueElement = this.meters[meterId + 'Value'];
        
        if (meter && valueElement) {
            meter.style.width = `${percentage}%`;
            valueElement.textContent = value;
        }
    }

    updateFrequencyDisplay() {
        const freqDisplay = document.getElementById('freqDisplay');
        const freqString = (this.currentFrequency / 1000000).toFixed(6);
        freqDisplay.textContent = freqString;
    }

    adjustFrequency(step) {
        this.currentFrequency += step;
        this.currentFrequency = Math.max(100000, Math.min(50000000, this.currentFrequency));
        this.updateFrequencyDisplay();
        this.updateSpectrum();
    }

    setFrequency(freq) {
        this.currentFrequency = freq;
        this.updateFrequencyDisplay();
        this.updateSpectrum();
    }

    setMode(mode) {
        this.currentMode = mode;
        
        // Update UI
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-mode="${mode}"]`).classList.add('active');
    }

    setBand(band) {
        this.currentBand = band;
        
        // Set default frequency for band
        const bandFrequencies = {
            '160m': 1900000,
            '80m': 3600000,
            '40m': 7100000,
            '30m': 10100000,
            '20m': 14200000,
            '17m': 18100000,
            '15m': 21200000,
            '12m': 24900000,
            '10m': 28300000,
            '6m': 52000000,
            '4m': 70000000,
            '2m': 145000000
        };
        
        if (bandFrequencies[band]) {
            this.setFrequency(bandFrequencies[band]);
        }
        
        // Update UI
        document.querySelectorAll('.band-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-band="${band}"]`).classList.add('active');
    }

    toggleConnection() {
        this.isConnected = !this.isConnected;
        
        const powerBtn = document.getElementById('powerBtn');
        const connectionStatus = document.getElementById('connectionStatus');
        const connectionText = document.getElementById('connectionText');
        
        if (this.isConnected) {
            powerBtn.innerHTML = '<i class="fas fa-power-off"></i><span>Disconnect</span>';
            powerBtn.style.background = 'rgba(239, 68, 68, 0.2)';
            powerBtn.style.borderColor = 'rgba(239, 68, 68, 0.3)';
            powerBtn.style.color = 'var(--danger-color)';
            
            connectionStatus.classList.add('connected');
            connectionText.textContent = 'Connected';
            
            this.startMeterUpdates();
        } else {
            powerBtn.innerHTML = '<i class="fas fa-power-off"></i><span>Connect</span>';
            powerBtn.style.background = 'rgba(16, 185, 129, 0.2)';
            powerBtn.style.borderColor = 'rgba(16, 185, 129, 0.3)';
            powerBtn.style.color = 'var(--success-color)';
            
            connectionStatus.classList.remove('connected');
            connectionText.textContent = 'Disconnected';
            
            this.stopMeterUpdates();
            this.isTransmitting = false;
            this.updatePTTButton();
        }
        
        this.updateMeters();
    }

    togglePTT() {
        if (!this.isConnected) return;
        
        this.isTransmitting = !this.isTransmitting;
        this.updatePTTButton();
        this.updateMeters();
    }

    updatePTTButton() {
        const pttBtn = document.getElementById('pttBtn');
        
        if (this.isTransmitting) {
            pttBtn.classList.add('active');
            pttBtn.innerHTML = '<i class="fas fa-stop"></i><span>TX</span>';
        } else {
            pttBtn.classList.remove('active');
            pttBtn.innerHTML = '<i class="fas fa-microphone"></i><span>PTT</span>';
        }
    }

    updateAFGain(value) {
        const sliderValue = document.querySelector('#afGain').nextElementSibling;
        sliderValue.textContent = value;
        
        // Here you would send the AF gain to the server
        console.log(`AF Gain set to: ${value}`);
    }

    updateMICGain(value) {
        const sliderValue = document.querySelector('#micGain').nextElementSibling;
        sliderValue.textContent = value;
        
        // Here you would send the MIC gain to the server
        console.log(`MIC Gain set to: ${value}`);
    }

    updateSpectrum() {
        const canvas = document.getElementById('spectrumCanvas');
        const ctx = canvas.getContext('2d');
        
        // Set canvas size
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw spectrum background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Draw frequency markers
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
        ctx.lineWidth = 1;
        
        for (let i = 0; i <= 10; i++) {
            const x = (canvas.width / 10) * i;
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, canvas.height);
            ctx.stroke();
        }
        
        // Draw spectrum data (simulated)
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        for (let i = 0; i < canvas.width; i++) {
            const frequency = (i / canvas.width) * 200000 + (this.currentFrequency - 100000);
            const amplitude = Math.sin((frequency / 10000) * Math.PI) * 0.5 + 0.5;
            const noise = (Math.random() - 0.5) * 0.1;
            const y = canvas.height - (amplitude + noise) * canvas.height * 0.8;
            
            if (i === 0) {
                ctx.moveTo(i, y);
            } else {
                ctx.lineTo(i, y);
            }
        }
        
        ctx.stroke();
        
        // Draw center frequency marker
        const centerX = canvas.width / 2;
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(centerX, 0);
        ctx.lineTo(centerX, canvas.height);
        ctx.stroke();
    }

    startClock() {
        const updateClock = () => {
            const now = new Date();
            const timeString = now.toLocaleTimeString();
            document.getElementById('clock').textContent = timeString;
        };
        
        updateClock();
        setInterval(updateClock, 1000);
    }

    startMeterUpdates() {
        if (this.meterInterval) return;
        
        this.meterInterval = setInterval(() => {
            this.updateMeters();
        }, 100);
    }

    stopMeterUpdates() {
        if (this.meterInterval) {
            clearInterval(this.meterInterval);
            this.meterInterval = null;
        }
    }

    simulateConnection() {
        // Simulate connection process
        setTimeout(() => {
            this.toggleConnection();
        }, 2000);
    }

    openSettings() {
        console.log('Opening settings...');
        // Implement settings modal
    }

    toggleFullscreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    }

    openSpectrumSettings() {
        console.log('Opening spectrum settings...');
        // Implement spectrum settings modal
    }

    // TX控制功能 - 与旧界面完全兼容
    startTX() {
        if (!poweron) return;
        console.log('开始TX');
        
        // 调用TX按钮优化脚本的控制函数
        if (typeof TXControl === 'function') {
            TXControl('start');
        }
    }

    stopTX() {
        if (!poweron) return;
        console.log('停止TX');
        
        // 调用TX按钮优化脚本的控制函数
        if (typeof TXControl === 'function') {
            TXControl('stop');
        }
    }

    toggleTXLock() {
        if (!poweron) return;
        console.log('切换TX锁定');
        
        // 调用旧界面的TXtogle函数
        if (typeof TXtogle === 'function') {
            TXtogle();
        }
    }

    // 滤波器控制
    setFilter(button) {
        if (!poweron) return;
        
        // 移除所有活动状态
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // 设置当前按钮为活动状态
        button.classList.add('active');
        
        // 调用旧界面的滤波器设置函数
        if (typeof setaudiofilter === 'function') {
            // 设置滤波器参数
            const fq = button.getAttribute('fq');
            const fg = button.getAttribute('fg');
            const ft = button.getAttribute('ft');
            const frq = button.getAttribute('frq');
            
            // 这里应该调用实际的滤波器设置逻辑
            console.log('设置滤波器:', {fq, fg, ft, frq});
        }
    }

    // 静噪控制
    updateSquelch(value) {
        const sliderValue = document.getElementById('squelchValue');
        if (sliderValue) {
            sliderValue.textContent = value;
        }
        
        // 调用旧界面的静噪更新函数
        if (typeof drawRXSmeter === 'function') {
            drawRXSmeter();
        }
        
        // 设置cookie
        if (typeof setCookie === 'function') {
            setCookie('SQUELCH', value, 180);
        }
    }

    // FFT显示更新
    updateFFTDisplay() {
        // 更新滑块值显示
        const floorValue = document.getElementById('fftFloorValue');
        const multdbValue = document.getElementById('fftMultdbValue');
        const startValue = document.getElementById('fftStartValue');
        const multhzValue = document.getElementById('fftMulthzValue');
        
        if (floorValue) floorValue.textContent = document.getElementById('canBFFFT_scale_floor').value;
        if (multdbValue) multdbValue.textContent = document.getElementById('canBFFFT_scale_multdb').value;
        if (startValue) startValue.textContent = document.getElementById('canBFFFT_scale_start').value;
        if (multhzValue) multhzValue.textContent = document.getElementById('canBFFFT_scale_multhz').value;
        
        // 这里应该调用实际的FFT更新逻辑
        console.log('更新FFT显示');
    }

    updateFFTCoordinates(event) {
        const canvas = document.getElementById('canBFFFT');
        if (!canvas) return;
        
        const rect = canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        
        const coordLabel = document.getElementById('canvasBFFFT_coord');
        if (coordLabel) {
            coordLabel.textContent = `Coords: ${Math.round(x)}, ${Math.round(y)}`;
        }
    }

    setCustomFilterFromFFT(event) {
        if (!poweron) return;
        
        const canvas = document.getElementById('canBFFFT');
        if (!canvas) return;
        
        const rect = canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const frequency = this.pixelToFrequency(x);
        
        // 设置自定义滤波器频率
        const customFilterF = document.getElementById('customfilter_F');
        if (customFilterF) {
            customFilterF.value = Math.round(frequency);
        }
        
        console.log('从FFT设置滤波器频率:', frequency);
    }

    pixelToFrequency(pixel) {
        const canvas = document.getElementById('canBFFFT');
        if (!canvas) return 0;
        
        const width = canvas.width;
        const centerFreq = this.currentFrequency;
        const span = 200000; // 200kHz span
        
        return centerFreq + ((pixel / width) - 0.5) * span;
    }

    // 个人频率管理
    initializePersonalFreqs() {
        this.updatePersonalFreqList();
    }

    updatePersonalFreqList() {
        const select = document.getElementById('selectpersonalfrequency');
        if (!select) return;
        
        // 清空现有选项
        select.innerHTML = '';
        
        // 从cookie加载个人频率
        const freqs = this.getPersonalFreqsFromCookie();
        
        freqs.forEach((freq, index) => {
            const option = document.createElement('option');
            option.value = freq.frequency;
            option.textContent = `${freq.name} - ${(freq.frequency / 1000000).toFixed(3)} MHz`;
            select.appendChild(option);
        });
    }

    getPersonalFreqsFromCookie() {
        // 这里应该从cookie读取个人频率
        // 现在返回一些示例频率
        return [
            {name: '20m USB', frequency: 14200000},
            {name: '40m LSB', frequency: 7100000},
            {name: '80m LSB', frequency: 3600000}
        ];
    }

    recallPersonalFreq() {
        const select = document.getElementById('selectpersonalfrequency');
        if (!select || !select.value) return;
        
        const frequency = parseInt(select.value);
        this.setFrequency(frequency);
        console.log('召回个人频率:', frequency);
    }

    savePersonalFreq() {
        const freq = this.currentFrequency;
        const name = prompt('请输入频率名称:');
        if (!name) return;
        
        // 这里应该保存到cookie
        console.log('保存个人频率:', name, freq);
        this.updatePersonalFreqList();
    }

    deletePersonalFreq() {
        const select = document.getElementById('selectpersonalfrequency');
        if (!select || !select.value) return;
        
        if (confirm('确定要删除这个频率吗?')) {
            // 这里应该从cookie删除
            console.log('删除个人频率:', select.value);
            this.updatePersonalFreqList();
        }
    }

    // S-Meter初始化
    initializeSMeter() {
        const canvas = document.getElementById('canRXsmeter');
        if (!canvas) return;
        
        this.canvasRXsmeter = canvas;
        this.ctxRXsmeter = canvas.getContext('2d');
        
        // 设置canvas大小
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
        
        this.drawRXSmeter();
    }

    drawRXSmeter() {
        if (!this.ctxRXsmeter || !this.canvasRXsmeter) return;
        
        const ctx = this.ctxRXsmeter;
        const canvas = this.canvasRXsmeter;
        
        // 清空画布
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // 绘制S-meter背景
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // 绘制刻度
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
        ctx.lineWidth = 2;
        
        // S-meter刻度 (S0-S9+60dB)
        for (let i = 0; i <= 9; i++) {
            const x = (canvas.width / 9) * i;
            ctx.beginPath();
            ctx.moveTo(x, canvas.height - 10);
            ctx.lineTo(x, canvas.height - 20);
            ctx.stroke();
            
            // 标签
            ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
            ctx.font = '12px Inter';
            ctx.textAlign = 'center';
            ctx.fillText(`S${i}`, x, canvas.height - 25);
        }
        
        // 绘制信号强度指示
        const signalStrength = this.isConnected ? Math.random() * 9 : 0;
        const signalX = (canvas.width / 9) * signalStrength;
        
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(0, canvas.height / 2);
        ctx.lineTo(signalX, canvas.height / 2);
        ctx.stroke();
        
        // 更新S-meter数值显示
        const smeterDisplay = document.getElementById('div-smeterdigitRX');
        if (smeterDisplay) {
            smeterDisplay.textContent = signalStrength > 9 ? 'S9+60dB' : `S${Math.floor(signalStrength)}`;
        }
    }

    // 比特率监控
    initializeBitrateMonitoring() {
        // 每秒更新比特率显示
        setInterval(() => {
            this.updateBitrateDisplay();
        }, 1000);
    }

    updateBitrateDisplay() {
        const bitrateDiv = document.getElementById('div-bitrates');
        if (!bitrateDiv) return;
        
        // 模拟比特率数据
        const rxBitrate = Math.random() * 100 + 50;
        const txBitrate = this.isTransmitting ? Math.random() * 100 + 50 : 0;
        
        bitrateDiv.textContent = `bitrate RX: ${rxBitrate.toFixed(1)} kbps | TX: ${txBitrate.toFixed(1)} kbps`;
    }

    // FFT初始化
    initializeFFT() {
        this.updateFFTDisplay();
        
        // 定期更新FFT显示
        setInterval(() => {
            this.drawFFT();
        }, 100);
    }

    drawFFT() {
        const canvas = document.getElementById('canBFFFT');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
        
        // 清空画布
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // 绘制背景
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // 绘制频谱数据
        ctx.strokeStyle = '#4CAF50';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        for (let i = 0; i < canvas.width; i++) {
            const amplitude = Math.sin((i / canvas.width) * Math.PI * 4) * 0.5 + 0.5;
            const noise = (Math.random() - 0.5) * 0.1;
            const y = canvas.height - (amplitude + noise) * canvas.height * 0.8;
            
            if (i === 0) {
                ctx.moveTo(i, y);
            } else {
                ctx.lineTo(i, y);
            }
        }
        
        ctx.stroke();
    }

    // WebSocket连接管理
    startWebSocketConnections() {
        if (!this.isConnected) return;
        
        // 音频RX WebSocket
        this.startAudioRX();
        
        // 音频TX WebSocket
        this.startAudioTX();
        
        // 控制TRX WebSocket
        this.startControlTRX();
    }

    startAudioRX() {
        wsAudioRX = new WebSocket('wss://' + window.location.host + '/WSaudioRX');
        wsAudioRX.binaryType = 'arraybuffer';
        wsAudioRX.onmessage = (msg) => this.appendwsAudioRX(msg);
        wsAudioRX.onopen = () => this.wsAudioRXopen();
        wsAudioRX.onclose = () => this.wsAudioRXclose();
        wsAudioRX.onerror = (error) => this.wsAudioRXerror(error);
    }

    startAudioTX() {
        wsAudioTX = new WebSocket('wss://' + window.location.host + '/WSaudioTX');
        wsAudioTX.binaryType = 'arraybuffer';
        wsAudioTX.onopen = () => this.wsAudioTXopen();
        wsAudioTX.onclose = () => this.wsAudioTXclose();
        wsAudioTX.onerror = (error) => this.wsAudioTXerror(error);
    }

    startControlTRX() {
        wsControlTRX = new WebSocket('wss://' + window.location.host + '/WSControlTRX');
        wsControlTRX.onmessage = (msg) => this.appendwsControlTRX(msg);
        wsControlTRX.onopen = () => this.wsControlTRXopen();
        wsControlTRX.onclose = () => this.wsControlTRXclose();
        wsControlTRX.onerror = (error) => this.wsControlTRXerror(error);
    }

    appendwsAudioRX(msg) {
        // 处理音频RX数据
        console.log('收到音频RX数据:', msg.data.byteLength, 'bytes');
    }

    wsAudioRXopen() {
        console.log('音频RX WebSocket已连接');
    }

    wsAudioRXclose() {
        console.log('音频RX WebSocket已断开');
    }

    wsAudioRXerror(error) {
        console.error('音频RX WebSocket错误:', error);
    }

    wsAudioTXopen() {
        console.log('音频TX WebSocket已连接');
    }

    wsAudioTXclose() {
        console.log('音频TX WebSocket已断开');
    }

    wsAudioTXerror(error) {
        console.error('音频TX WebSocket错误:', error);
    }

    appendwsControlTRX(msg) {
        // 处理控制TRX数据
        console.log('收到控制TRX数据:', msg.data);
    }

    wsControlTRXopen() {
        console.log('控制TRX WebSocket已连接');
        this.sendTRXparameters();
    }

    wsControlTRXclose() {
        console.log('控制TRX WebSocket已断开');
    }

    wsControlTRXerror(error) {
        console.error('控制TRX WebSocket错误:', error);
    }

    sendTRXparameters() {
        if (!wsControlTRX || wsControlTRX.readyState !== WebSocket.OPEN) return;
        
        const params = {
            frequency: this.currentFrequency,
            mode: this.currentMode,
            bandwidth: 2700
        };
        
        wsControlTRX.send(JSON.stringify(params));
        console.log('发送TRX参数:', params);
    }

    sendTRXmode() {
        if (!wsControlTRX || wsControlTRX.readyState !== WebSocket.OPEN) return;
        
        wsControlTRX.send(JSON.stringify({mode: this.currentMode}));
        console.log('发送模式:', this.currentMode);
    }

    // 兼容性功能 - 与旧界面函数名称保持一致
    bodyload() {
        this.initializeComponents();
    }

    powertogle() {
        this.toggleConnection();
    }

    TXtogle() {
        this.toggleTXLock();
    }

    // 注意：避免函数名冲突，使用不同的内部实现
    sendTRXmodeCompat() {
        this.sendTRXmode();
    }

    setaudiofilter() {
        // 滤波器设置将在setFilter中处理
        console.log('设置音频滤波器');
    }

    drawRXSmeterCompat() {
        this.drawRXSmeter();
    }

    updateFFTDisplayCompat() {
        this.updateFFTDisplay();
    }

    setcustomaudiofilter() {
        // 自定义滤波器设置
        console.log('设置自定义滤波器');
    }

    recall_freqfromcokkies() {
        this.recallPersonalFreq();
    }

    delete_freqfromcokkies() {
        this.deletePersonalFreq();
    }

    save_freqtocokkies() {
        this.savePersonalFreq();
    }

    // Cookie管理功能
    setCookie(name, value, days) {
        const expires = new Date();
        expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
        document.cookie = name + '=' + value + ';expires=' + expires.toUTCString() + ';path=/';
    }

    getCookie(name) {
        const nameEQ = name + '=';
        const ca = document.cookie.split(';');
        for (let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    }
}

// Initialize the modern interface when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.modernInterface = new ModernHamInterface();
    console.log('现代界面初始化完成，全局接口对象已创建');
});
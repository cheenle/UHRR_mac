// Modern Hamradio Remote Interface JavaScript

class ModernHamInterface {
    constructor() {
        this.isConnected = false;
        this.isTransmitting = false;
        this.currentFrequency = 14200000;
        this.currentMode = 'USB';
        this.currentBand = '20m';
        
        this.initializeEventListeners();
        this.initializeMeters();
        this.startClock();
        this.simulateConnection();
    }

    initializeEventListeners() {
        // Connection controls
        document.getElementById('powerBtn').addEventListener('click', () => this.toggleConnection());
        document.getElementById('pttBtn').addEventListener('click', () => this.togglePTT());
        
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
        
        // Audio controls
        document.getElementById('afGain').addEventListener('input', (e) => this.updateAFGain(e.target.value));
        document.getElementById('micGain').addEventListener('input', (e) => this.updateMICGain(e.target.value));
        
        // Header controls
        document.getElementById('settingsBtn').addEventListener('click', () => this.openSettings());
        document.getElementById('fullscreenBtn').addEventListener('click', () => this.toggleFullscreen());
        
        // Spectrum controls
        document.getElementById('spectrumSettings').addEventListener('click', () => this.openSpectrumSettings());
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
}

// Initialize the modern interface when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new ModernHamInterface();
});
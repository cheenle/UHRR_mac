// Modern Mobile Interface JavaScript for iPhone 15 and modern browsers
// Handles all interactive elements, WebSocket connections, and radio controls

// Global variables
let websocket = null;
let isConnected = false;
let currentFrequency = 7053000; // Default frequency in Hz
let currentMode = 'USB';
let currentVFO = 'VFO-A';
let isTransmitting = false;

// UHRR WebSocket connections
let wsControlTRX = null;
let wsAudioRX = null;
let wsAudioTX = null;

// Audio context for mobile
let audioContext = null;
let audioRXSourceNode = null;
let audioRXGainNode = null;
let audioRXBiquadFilterNode = null; // Add filter node like desktop version
let audioBufferReady = false;
let audioRXAudioBuffer = []; // Audio buffer queue
let audioRXSampleRate = 12000; // Match server-side sample rate
let audioRXProcessing = false; // Flag to prevent concurrent processing

// DOM Elements
const domElements = {
    menuToggle: null,
    menuClose: null,
    menuOverlay: null,
    mainMenu: null,
    pttButton: null,
    powerButton: null,
    freqDisplay: null,
    modeIndicator: null,
    vfoIndicator: null,
    statusCtrl: null,
    statusRX: null,
    statusTX: null,
    sMeterCanvas: null,
    navButtons: null,
    quickButtons: null,
    tuneButtons: null
};

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeElements();
    setupEventListeners();
    initializeSMeter();
    connectWebSocket();
    updateFrequencyDisplay();
});

// Initialize DOM elements
function initializeElements() {
    domElements.menuToggle = document.getElementById('menu-toggle');
    domElements.menuClose = document.getElementById('menu-close');
    domElements.menuOverlay = document.getElementById('menu-overlay');
    domElements.mainMenu = document.getElementById('main-menu');
    domElements.pttButton = document.getElementById('ptt-btn');
    domElements.powerButton = document.getElementById('power-btn');
    domElements.freqDisplay = document.getElementById('freq-main-display');
    domElements.modeIndicator = document.getElementById('mode-indicator');
    domElements.vfoIndicator = document.getElementById('vfo-indicator');
    domElements.statusCtrl = document.getElementById('status-ctrl');
    domElements.statusRX = document.getElementById('status-rx');
    domElements.statusTX = document.getElementById('status-tx');
    domElements.sMeterCanvas = document.getElementById('s-meter-canvas');
    domElements.navButtons = document.querySelectorAll('.nav-btn');
    domElements.quickButtons = document.querySelectorAll('.quick-btn');
    domElements.tuneButtons = document.querySelectorAll('.tune-btn');
}

// Setup event listeners
function setupEventListeners() {
    // Menu toggle
    if (domElements.menuToggle) {
        domElements.menuToggle.addEventListener('click', toggleMenu);
    }
    
    // Menu close
    if (domElements.menuClose) {
        domElements.menuClose.addEventListener('click', closeMenu);
    }
    
    // Menu overlay
    if (domElements.menuOverlay) {
        domElements.menuOverlay.addEventListener('click', closeMenu);
    }
    
    // PTT button (touch optimized for mobile)
    if (domElements.pttButton) {
        domElements.pttButton.addEventListener('touchstart', handlePTTStart, { passive: false });
        domElements.pttButton.addEventListener('touchend', handlePTTEnd, { passive: false });
        domElements.pttButton.addEventListener('mousedown', handlePTTStart);
        domElements.pttButton.addEventListener('mouseup', handlePTTEnd);
        domElements.pttButton.addEventListener('mouseleave', handlePTTEnd);
    }
    
    // Power button
    if (domElements.powerButton) {
        domElements.powerButton.addEventListener('click', togglePower);
    }
    
    // Navigation buttons
    domElements.navButtons.forEach(button => {
        button.addEventListener('click', function() {
            switchTab(this.dataset.tab);
        });
    });
    
    // Quick buttons
    domElements.quickButtons.forEach(button => {
        button.addEventListener('click', function() {
            handleQuickButton(this);
        });
    });
    
    // Tune buttons
    domElements.tuneButtons.forEach(button => {
        button.addEventListener('click', function() {
            tuneFrequency(parseInt(this.dataset.step));
        });
    });
    
    // Prevent context menu on long press
    document.addEventListener('contextmenu', function(e) {
        e.preventDefault();
    });
}

// Toggle menu visibility
function toggleMenu() {
    domElements.mainMenu.classList.toggle('open');
    domElements.menuOverlay.classList.toggle('open');
}

// Close menu
function closeMenu() {
    domElements.mainMenu.classList.remove('open');
    domElements.menuOverlay.classList.remove('open');
}

// Handle PTT start (transmit)
function handlePTTStart(e) {
    e.preventDefault();
    if (!isConnected) return;
    
    isTransmitting = true;
    updateTXStatus(true);
    sendWebSocketMessage('setPTT:true');
    
    // Add visual feedback
    domElements.pttButton.classList.add('active');
    
    // Haptic feedback
    if (navigator.vibrate) {
        navigator.vibrate(50);
    }
}

// Handle PTT end (receive)
function handlePTTEnd(e) {
    e.preventDefault();
    if (!isTransmitting) return;
    
    isTransmitting = false;
    updateTXStatus(false);
    sendWebSocketMessage('setPTT:false');
    
    // Remove visual feedback
    domElements.pttButton.classList.remove('active');
    
    // Haptic feedback
    if (navigator.vibrate) {
        navigator.vibrate(25);
    }
}

// Toggle power state
function togglePower() {
    if (isConnected) {
        disconnectWebSocket();
        domElements.powerButton.querySelector('.power-icon').textContent = '⏻';
    } else {
        connectWebSocket();
        domElements.powerButton.querySelector('.power-icon').textContent = '⏼';
        // Test audio immediately after connection
        setTimeout(() => {
            if (typeof AudioRX_start === 'function') {
                console.log('Starting desktop-compatible audio...');
                AudioRX_start();
            }
        }, 2000);
    }
}

// Switch between tabs
function switchTab(tabName) {
    // Update active state for nav buttons
    domElements.navButtons.forEach(button => {
        if (button.dataset.tab === tabName) {
            button.classList.add('active');
        } else {
            button.classList.remove('active');
        }
    });
    
    // In a full implementation, this would show/hide different content sections
    console.log(`Switching to tab: ${tabName}`);
}

// Handle quick button actions
function handleQuickButton(button) {
    // Remove active state from siblings
    const siblings = button.parentElement.children;
    for (let i = 0; i < siblings.length; i++) {
        siblings[i].classList.remove('active');
    }
    
    // Add active state to clicked button
    button.classList.add('active');
    
    // Handle specific button actions
    if (button.id === 'vfo-a-btn' || button.id === 'vfo-b-btn') {
        currentVFO = button.textContent;
        domElements.vfoIndicator.textContent = currentVFO;
        sendWebSocketMessage(`VFO_${currentVFO.replace('-', '')}`);
    } else if (button.id === 'mode-btn') {
        // Cycle through modes in a full implementation
        cycleMode();
    } else if (button.id === 'band-btn') {
        // Show band selection in a full implementation
        console.log('Band selection requested');
    }
}

// Cycle through radio modes
function cycleMode() {
    const modes = ['LSB', 'USB', 'CW', 'FM', 'AM'];
    const currentIndex = modes.indexOf(currentMode);
    const nextIndex = (currentIndex + 1) % modes.length;
    currentMode = modes[nextIndex];
    domElements.modeIndicator.textContent = currentMode;
    sendWebSocketMessage(`setMode:${currentMode}`);
}

// Tune frequency by specified step
function tuneFrequency(step) {
    currentFrequency += step;
    if (currentFrequency < 0) currentFrequency = 0;
    updateFrequencyDisplay();
    sendWebSocketMessage(`setFreq:${currentFrequency}`);
}

// Update frequency display
function updateFrequencyDisplay() {
    const freqStr = currentFrequency.toString().padStart(9, '0');
    
    // Update each digit element
    document.getElementById('freq-100mhz').textContent = freqStr[0];
    document.getElementById('freq-10mhz').textContent = freqStr[1];
    document.getElementById('freq-1mhz').textContent = freqStr[2];
    document.getElementById('freq-100khz').textContent = freqStr[3];
    document.getElementById('freq-10khz').textContent = freqStr[4];
    document.getElementById('freq-1khz').textContent = freqStr[5];
    document.getElementById('freq-100hz').textContent = freqStr[6];
    document.getElementById('freq-10hz').textContent = freqStr[7];
    document.getElementById('freq-1hz').textContent = freqStr[8];
}

// Update TX status indicator
function updateTXStatus(isTransmitting) {
    if (isTransmitting) {
        domElements.statusTX.classList.add('active');
        domElements.statusRX.classList.remove('active');
    } else {
        domElements.statusTX.classList.remove('active');
        domElements.statusRX.classList.add('active');
    }
}

// Initialize S-Meter visualization
function initializeSMeter() {
    const canvas = domElements.sMeterCanvas;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    // Draw initial S-Meter
    drawSMeter(ctx, 0);
    
    // In a full implementation, this would be updated with real S-Meter data
    // For now, we'll simulate periodic updates
    setInterval(() => {
        if (isConnected && !isTransmitting) {
            const randomValue = Math.random() * 100;
            drawSMeter(ctx, randomValue);
        }
    }, 500);
}

// Draw S-Meter on canvas
function drawSMeter(ctx, value) {
    const canvas = ctx.canvas;
    const width = canvas.width;
    const height = canvas.height;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Draw background
    ctx.fillStyle = '#111';
    ctx.fillRect(0, 0, width, height);
    
    // Draw grid lines
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    
    // Vertical grid lines
    for (let i = 0; i <= 10; i++) {
        const x = (width / 10) * i;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
    }
    
    // Horizontal grid lines
    for (let i = 0; i <= 5; i++) {
        const y = (height / 5) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
    }
    
    // Draw S-Meter bars
    const barWidth = width / 50;
    const maxBars = 50;
    const barsToDraw = Math.min(maxBars, Math.floor((value / 100) * maxBars));
    
    for (let i = 0; i < barsToDraw; i++) {
        const x = i * barWidth;
        const barHeight = height * (0.2 + (i / maxBars) * 0.8);
        const y = height - barHeight;
        
        // Color gradient from green to red
        if (i < 20) {
            ctx.fillStyle = '#4CAF50'; // Green
        } else if (i < 35) {
            ctx.fillStyle = '#FFC107'; // Yellow
        } else {
            ctx.fillStyle = '#F44336'; // Red
        }
        
        ctx.fillRect(x, y, barWidth - 1, barHeight);
    }
    
    // Draw value text
    ctx.fillStyle = '#fff';
    ctx.font = '14px Arial';
    ctx.textAlign = 'right';
    ctx.fillText(`${Math.round(value)}%`, width - 10, 20);
}

// WebSocket connection handling
function connectWebSocket() {
    console.log('Connecting to UHRR WebSocket server...');
    
    // Use the same protocol as the current page
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const baseUrl = `${protocol}//${window.location.host}`;
    
    try {
        // Control WebSocket
        console.log('Establishing control WebSocket connection...');
        wsControlTRX = new WebSocket(`${baseUrl}/WSCTRX`);
        
        wsControlTRX.onopen = function() {
            console.log('Control WebSocket connected successfully');
            isConnected = true;
            domElements.statusCtrl.classList.add('connected');
            domElements.powerButton.querySelector('.power-icon').textContent = '⏻';
            
            // Request initial status from radio
            console.log('Requesting initial frequency and mode...');
            wsControlTRX.send('getFreq:');
            wsControlTRX.send('getMode:');
        };
        
        wsControlTRX.onmessage = function(msg) {
            console.log('WebSocket message received:', msg.data);
            handleControlMessage(msg.data);
        };
        
        wsControlTRX.onclose = function() {
            console.log('Control WebSocket disconnected');
            isConnected = false;
            domElements.statusCtrl.classList.remove('connected');
            domElements.powerButton.querySelector('.power-icon').textContent = '⏻';
        };
        
        wsControlTRX.onerror = function(error) {
            console.error('Control WebSocket error:', error);
            isConnected = false;
            domElements.statusCtrl.classList.remove('connected');
        };
        
        // Audio RX WebSocket
        wsAudioRX = new WebSocket(`${baseUrl}/WSaudioRX`);
        wsAudioRX.binaryType = 'arraybuffer';
        wsAudioRX.onopen = function() {
            console.log('Audio RX WebSocket connected');
            // Initialize Web Audio API for audio playback
            if (!audioContext) {
                try {
                    // Use 12000Hz sample rate to match server-side configuration
                    audioContext = new (window.AudioContext || window.webkitAudioContext)({sampleRate: 12000});
                    console.log('Web Audio API initialized with sample rate: 12000');
                    
                    // Create audio processing nodes like desktop version
                    audioRXGainNode = audioContext.createGain();
                    audioRXGainNode.gain.value = 0.8; // Set initial volume to 80%
                    
                    // Add biquad filter node like desktop version
                    audioRXBiquadFilterNode = audioContext.createBiquadFilter();
                    audioRXBiquadFilterNode.type = "lowshelf";
                    // Clamp frequency to valid range (max 8000Hz for 16000Hz sample rate)
                    audioRXBiquadFilterNode.frequency.setValueAtTime(6000, audioContext.currentTime);
                    audioRXBiquadFilterNode.gain.setValueAtTime(0, audioContext.currentTime);
                    
                    // Try to use ScriptProcessor for better audio buffering like desktop version
                    const BUFF_SIZE = 256;
                    audioRXSourceNode = audioContext.createScriptProcessor(BUFF_SIZE, 1, 1);
                    audioRXSourceNode.onaudioprocess = function(event) {
                        var out = event.outputBuffer.getChannelData(0);
                        if (audioRXAudioBuffer.length === 0) { 
                            out.fill(0); 
                            return; 
                        }
                        var cur = audioRXAudioBuffer[0];
                        var n = Math.min(cur.length, out.length);
                        for (var j = 0; j < n; j++) out[j] = cur[j];
                        for (var k = n; k < out.length; k++) out[k] = 0;
                        if (n >= cur.length) audioRXAudioBuffer.shift(); else audioRXAudioBuffer[0] = cur.slice(n);
                    };
                    
                    // Connect nodes: source -> filter -> gain -> destination
                    audioRXSourceNode.connect(audioRXBiquadFilterNode);
                    audioRXBiquadFilterNode.connect(audioRXGainNode);
                    audioRXGainNode.connect(audioContext.destination);
                    
                    console.log('Audio processing nodes initialized');
                } catch (e) {
                    console.error('Web Audio API initialization failed:', e);
                }
            }
        };
        
        wsAudioRX.onmessage = function(event) {
            // Handle incoming audio data using buffer queue like desktop version
            if (event.data instanceof ArrayBuffer) {
                try {
                    // 码率统计：RX (borrowed from desktop version)
                    if (!window.__rxBytes) { window.__rxBytes = 0; }
                    if (event.data && event.data.byteLength) {
                        window.__rxBytes += event.data.byteLength;
                    }
                    
                    // Convert Int16 to Float32 for Web Audio API
                    const int16Data = new Int16Array(event.data);
                    const audioData = new Float32Array(int16Data.length);
                    for (let i = 0; i < int16Data.length; i++) {
                        audioData[i] = int16Data[i] / 32767.0;
                    }
                    
                    // 限制缓冲区大小，防止累积过多音频数据 (borrowed from desktop version)
                    if (audioRXAudioBuffer.length > 10) {
                        console.log('⚠️ 音频缓冲区过大，清除旧数据');
                        audioRXAudioBuffer = audioRXAudioBuffer.slice(-5); // 只保留最新的5个缓冲区
                    }
                    
                    audioRXAudioBuffer.push(audioData);
                    console.log('DEBUG: Audio buffer length after push:', audioRXAudioBuffer.length);
                    
                } catch (error) {
                    console.error('Error processing audio data:', error);
                }
            }
        };
        
        wsAudioRX.onclose = function() {
            console.log('Audio RX WebSocket disconnected');
        };
        
        wsAudioRX.onerror = function(error) {
            console.error('Audio RX WebSocket error:', error);
        };
        
        // Audio TX WebSocket
        wsAudioTX = new WebSocket(`${baseUrl}/WSaudioTX`);
        wsAudioTX.onopen = function() {
            console.log('Audio TX WebSocket connected');
        };
        
        wsAudioTX.onclose = function() {
            console.log('Audio TX WebSocket disconnected');
        };
        
        wsAudioTX.onerror = function(error) {
            console.error('Audio TX WebSocket error:', error);
        };
        
    } catch (error) {
        console.error('Failed to establish WebSocket connections:', error);
        isConnected = false;
    }
}

function disconnectWebSocket() {
    console.log('Disconnecting from UHRR WebSocket server...');
    
    if (wsControlTRX) {
        wsControlTRX.close();
        wsControlTRX = null;
    }
    if (wsAudioRX) {
        wsAudioRX.close();
        wsAudioRX = null;
    }
    if (wsAudioTX) {
        wsAudioTX.close();
        wsAudioTX = null;
    }
    
    isConnected = false;
    domElements.statusCtrl.classList.remove('connected');
    domElements.powerButton.querySelector('.power-icon').textContent = '⏻';
}

function sendWebSocketMessage(message) {
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        console.log(`Sending message: ${message}`);
        wsControlTRX.send(message);
    } else {
        console.warn('WebSocket not connected, cannot send message:', message);
    }
}

function handleControlMessage(data) {
    const parts = data.split(':');
    const command = parts[0];
    const value = parts[1];
    
    console.log('Received command:', command, 'value:', value);
    
    switch (command) {
        case 'getFreq':
            // Update frequency display
            const freq = parseInt(value);
            if (freq && freq > 0) {
                currentFrequency = freq;
                updateFrequencyDisplay();
            }
            break;
        case 'getMode':
            if (value) {
                currentMode = value;
                domElements.modeIndicator.textContent = currentMode;
            }
            break;
        case 'getSignalLevel':
            // Update S-meter
            updateSMeter(value);
            break;
        case 'getPTT':
            // Update PTT status
            const pttStatus = value === 'true';
            isTransmitting = pttStatus;
            updateTXStatus(pttStatus);
            break;
        default:
            console.log('Unknown command:', command, value);
            break;
    }
}

function updateSMeter(level) {
    // Update S-meter display with signal level
    console.log('Updating S-meter with level:', level);
    // In a full implementation, this would update the canvas
}

// Handle page visibility changes
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        // Page is hidden, optionally reduce activity
        console.log('Page hidden');
    } else {
        // Page is visible, resume normal activity
        console.log('Page visible');
    }
});

// Handle window resize
window.addEventListener('resize', function() {
    // Reinitialize S-Meter on resize
    initializeSMeter();
});

// Prevent zoom on double tap
let lastTouchEnd = 0;
document.addEventListener('touchend', function(event) {
    const now = (new Date()).getTime();
    if (now - lastTouchEnd <= 300) {
        event.preventDefault();
    }
    lastTouchEnd = now;
}, false);

// Handle orientation change
window.addEventListener('orientationchange', function() {
    setTimeout(() => {
        // Reinitialize elements that might need adjustment
        initializeSMeter();
    }, 100);
});
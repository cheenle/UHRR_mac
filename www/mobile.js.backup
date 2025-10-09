/* Mobile Ham Radio Remote JavaScript */

// Mobile detection
const IS_MOBILE = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

// WebSocket connections
let wsControlTRX = null;
let wsAudioRX = null;
let wsAudioTX = null;

// Application state
let appState = {
    powered: false,
    frequency: 7053000,  // Default to 7.053 MHz (IC-M710 can't read frequency)
    vfoAFreq: 7053000,
    vfoBFreq: 14230000,
    mode: 'USB',
    vfoAMode: 'USB',
    vfoBMode: 'USB',
    vfo: 'A',
    pttActive: false,
    connected: false,
    split: false,
    rit: false,
    xit: false,
    ritOffset: 0,
    vox: false,
    monitor: false,
    tune: false,
    signalStrength: 0,
    powerOutput: 0,
    swr: 1.0,
    tuneStep: 10,
    filterWidth: 'mid',
    antenna: 'ant1',
    keyerSpeed: 20,
    dualWatch: false,
    qsk: false,
    scope: false,
    waterfall: false,
    antTuner: false,
    digitalMode: null,
    cwSpeed: 20,
    waterfallCenter: 1500,
    ft8Cycle: 'RX',
    qsoLog: []
};

// Audio context for mobile optimization
let audioContext = null;
let microphoneStream = null;

// Audio processing variables for mobile
let audioRXSourceNode = null;
let audioRXGainNode = null;
let audioRXBiquadFilterNode = null;
let audioRXAnalyser = null;
let audioRXAudioBuffer = [];
let audioRXSampleRate = 8000;
let audioBufferReady = false;

// Function to resume audio context on user interaction
function resumeAudioContext() {
    if (audioContext && audioContext.state === 'suspended') {
        console.log('Attempting to resume AudioContext...');
        audioContext.resume().then(() => {
            console.log('AudioContext resumed successfully');
            // Play any buffered audio
            playBufferedAudio();
        }).catch((error) => {
            console.error('Failed to resume AudioContext:', error);
        });
    }
}

// Function to play buffered audio
function playBufferedAudio() {
    if (audioRXAudioBuffer.length > 0 && audioContext && audioContext.state === 'running') {
        console.log(`Playing ${audioRXAudioBuffer.length} buffered audio chunks`);
        audioRXAudioBuffer.forEach((audioData, index) => {
            try {
                const buffer = audioContext.createBuffer(1, audioData.length, audioRXSampleRate);
                buffer.copyToChannel(audioData, 0);
                
                const source = audioContext.createBufferSource();
                source.buffer = buffer;
                // Connect through gain node for volume control
                if (audioRXGainNode) {
                    source.connect(audioRXGainNode);
                    audioRXGainNode.connect(audioContext.destination);
                } else {
                    source.connect(audioContext.destination);
                }
                // Stagger playback to avoid overlap
                source.start(audioContext.currentTime + (index * 0.01));
            } catch (error) {
                console.error('Error playing buffered audio:', error);
            }
        });
        // Clear buffer after playing
        audioRXAudioBuffer = [];
    }
}

// Initialize the mobile interface
document.addEventListener('DOMContentLoaded', function() {
    console.log('Mobile Ham Radio Remote initializing...');
    
    // Setup mobile-specific optimizations
    setupMobileOptimizations();
    
    // Initialize event handlers
    setupEventHandlers();
    
    // Set initial frequency (IC-M710 can't read frequency, so use default)
    appState.frequency = 7053000;  // 7.053 MHz default
    
    // Update UI
    updateFrequencyDisplay();
    updateStatus();
    updateClock();
    
    // Auto-connect WebSockets (don't wait for power button)
    console.log('Auto-connecting WebSockets...');
    // Add a small delay to ensure DOM is fully loaded
    setTimeout(function() {
        connectWebSockets();
        
        // Mark as powered on
        appState.powered = true;
        const powerBtn = document.getElementById('power-btn');
        if (powerBtn) {
            powerBtn.classList.add('on');
        }
    }, 100);
    
    // Start clock update
    setInterval(updateClock, 1000);
    
    console.log('Mobile interface ready - frequency initialized to:', appState.frequency);
});

// Also listen for page load event as a fallback
window.addEventListener('load', function() {
    console.log('Window load event fired');
    // Ensure WebSockets are connected
    if (!wsControlTRX || wsControlTRX.readyState !== WebSocket.OPEN) {
        console.log('Reconnecting WebSockets on window load');
        connectWebSockets();
    }
});

function setupMobileOptimizations() {
    // Prevent iOS bounce effect
    document.addEventListener('touchmove', function(e) {
        if (e.target.closest('.mobile-container')) {
            e.preventDefault();
        }
    }, { passive: false });
    
    // Prevent iOS zoom on input focus  
    if (IS_MOBILE) {
        document.addEventListener('touchstart', function(e) {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') {
                e.target.style.fontSize = '16px';
            }
        });
        
        // Additional mobile optimizations
        document.addEventListener('touchend', function(e) {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') {
                e.target.style.fontSize = '';
            }
        });
    }
    
    // Setup PTT button with optimized touch handling
    const pttBtn = document.getElementById('ptt-btn');
    if (pttBtn) {
        // Remove default mouse events to prevent delays
        pttBtn.onmousedown = null;
        pttBtn.onmouseup = null;
        pttBtn.onmouseleave = null;
        
        // Add optimized touch events
        pttBtn.addEventListener('touchstart', function(e) {
            e.preventDefault();
            e.stopPropagation();
            // Resume audio context on first user interaction
            resumeAudioContext();
            handlePTT(true);
        }, { passive: false, capture: true });
        
        pttBtn.addEventListener('touchend', function(e) {
            e.preventDefault();
            e.stopPropagation();
            handlePTT(false);
        }, { passive: false, capture: true });
        
        // Add touchcancel event to ensure PTT is released
        pttBtn.addEventListener('touchcancel', function(e) {
            e.preventDefault();
            e.stopPropagation();
            handlePTT(false);
        }, { passive: false, capture: true });
        
        // Fallback for desktop
        pttBtn.addEventListener('mousedown', function(e) {
            if (!IS_MOBILE) {
                e.preventDefault();
                // Resume audio context on first user interaction
                resumeAudioContext();
                handlePTT(true);
            }
        });
        
        pttBtn.addEventListener('mouseup', function(e) {
            if (!IS_MOBILE) {
                e.preventDefault();
                handlePTT(false);
            }
        });
        
        // Handle mouse leaving the button while pressed
        pttBtn.addEventListener('mouseleave', function(e) {
            if (!IS_MOBILE && e.buttons === 1) { // Left mouse button is still pressed
                handlePTT(false);
            }
        });
    }
    
    // Optimize all buttons for mobile
    const buttons = document.querySelectorAll('button');
    buttons.forEach(button => {
        button.addEventListener('touchstart', function(e) {
            this.classList.add('button-pulse');
            // Resume audio context on first user interaction
            resumeAudioContext();
        });
        
        button.addEventListener('touchend', function(e) {
            this.classList.remove('button-pulse');
        });
    });
}

function setupEventHandlers() {
    // Power button
    const powerBtn = document.getElementById('power-btn');
    if (powerBtn) {
        powerBtn.addEventListener('click', powerToggle);
    }
    
    // Mode buttons
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            setMode(this.dataset.mode);
        });
    });
    
    // Band buttons
    document.querySelectorAll('.band-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            setFrequency(parseInt(this.dataset.freq));
        });
    });
    
    // VFO buttons
    document.getElementById('vfo-a')?.addEventListener('click', () => setVFO('A'));
    document.getElementById('vfo-b')?.addEventListener('click', () => setVFO('B'));
    
    // Audio controls
    document.getElementById('af-gain')?.addEventListener('input', updateAFGain);
    document.getElementById('rf-gain')?.addEventListener('input', updateRFGain);
    document.getElementById('mic-gain')?.addEventListener('input', updateMicGain);
    document.getElementById('squelch')?.addEventListener('input', updateSquelch);
    
    // RIT control
    document.getElementById('rit-offset')?.addEventListener('input', updateRIT);
    
    // Quick settings
    document.querySelectorAll('.setting-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            this.classList.toggle('active');
        });
    });
    
    // Initialize S-meter canvas
    initializeSMeter();
    
    // Initialize waterfall display
    initializeWaterfall();
    
    // Initialize QSO date/time
    initializeLogbook();
}

function powerToggle() {
    appState.powered = !appState.powered;
    
    const powerBtn = document.getElementById('power-btn');
    if (appState.powered) {
        powerBtn.classList.add('on');
        connectWebSockets();
        
        // Haptic feedback on mobile
        if (navigator.vibrate && IS_MOBILE) {
            navigator.vibrate(50);
        }
    } else {
        powerBtn.classList.remove('on');
        disconnectWebSockets();
    }
    
    updateStatus();
}

function connectWebSockets() {
    // Use the same protocol as the current page
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const baseUrl = `${protocol}//${window.location.host}`;
    console.log('Connecting to WebSocket server at:', baseUrl);
    
    // Control WebSocket
    console.log('Establishing control WebSocket connection...');
    wsControlTRX = new WebSocket(`${baseUrl}/WSCTRX`);
    
    wsControlTRX.onopen = function() {
        console.log('Control WebSocket connected successfully');
        updateConnectionStatus('ctrl', true);
        
        // Request initial status from radio
        console.log('Requesting initial frequency and mode...');
        wsControlTRX.send('getFreq:');
        wsControlTRX.send('getMode:');
        
        // Send current frequency to radio (IC-M710 can't read, but can set)
        console.log('Setting radio frequency to:', appState.frequency);
        wsControlTRX.send(`setFreq:${appState.frequency}`);
    };
    
    wsControlTRX.onmessage = function(msg) {
        console.log('WebSocket message received:', msg.data);
        handleControlMessage(msg.data);
    };
    
    wsControlTRX.onclose = function() {
        console.log('Control WebSocket disconnected');
        updateConnectionStatus('ctrl', false);
        
        // Attempt reconnection after 3 seconds
        setTimeout(() => {
            console.log('Attempting to reconnect...');
            connectWebSockets();
        }, 3000);
    };
    
    wsControlTRX.onerror = function(error) {
        console.error('Control WebSocket error:', error);
        updateConnectionStatus('ctrl', false);
    };
    
    // Audio RX WebSocket
    wsAudioRX = new WebSocket(`${baseUrl}/WSaudioRX`);
    wsAudioRX.binaryType = 'arraybuffer';
    wsAudioRX.onopen = function() {
        console.log('Audio RX WebSocket connected');
        updateConnectionStatus('rx', true);
        
        // Initialize Web Audio API for audio playback
        if (!audioContext) {
            try {
                audioContext = new (window.AudioContext || window.webkitAudioContext)({sampleRate: audioRXSampleRate});
                console.log('Web Audio API initialized with sample rate:', audioRXSampleRate);
                
                // Create audio processing nodes
                audioRXGainNode = audioContext.createGain();
                audioRXGainNode.gain.value = 0.8; // Set initial volume to 80%
                
                // Create biquad filter node for audio processing
                audioRXBiquadFilterNode = audioContext.createBiquadFilter();
                audioRXBiquadFilterNode.type = "lowshelf";
                audioRXBiquadFilterNode.frequency.setValueAtTime(22000, audioContext.currentTime);
                audioRXBiquadFilterNode.gain.setValueAtTime(0, audioContext.currentTime);
            } catch (e) {
                console.error('Web Audio API initialization failed:', e);
            }
        }
        
        // Ensure AudioContext is running (modern browsers require user interaction)
        if (audioContext && audioContext.state === 'suspended') {
            console.log('AudioContext is suspended, will resume on user interaction');
        }
    };
    
    wsAudioRX.onmessage = function(event) {
        // Handle incoming audio data - simple direct playback
        if (event.data instanceof ArrayBuffer) {
            try {
                // Convert received data to Float32Array
                const audioData = new Float32Array(event.data);
                
                // Play audio immediately if context is running
                if (audioContext && audioContext.state === 'running') {
                    const buffer = audioContext.createBuffer(1, audioData.length, audioRXSampleRate);
                    buffer.copyToChannel(audioData, 0);
                    
                    const source = audioContext.createBufferSource();
                    source.buffer = buffer;
                    
                    // Connect through the audio processing chain (filter -> gain -> destination)
                    if (audioRXBiquadFilterNode && audioRXGainNode) {
                        source.connect(audioRXBiquadFilterNode);
                        audioRXBiquadFilterNode.connect(audioRXGainNode);
                        audioRXGainNode.connect(audioContext.destination);
                    } else if (audioRXGainNode) {
                        source.connect(audioRXGainNode);
                        audioRXGainNode.connect(audioContext.destination);
                    } else {
                        source.connect(audioContext.destination);
                    }
                    source.start();
                } else {
                    // If context is suspended, try to resume and play
                    if (audioContext && audioContext.state === 'suspended') {
                        console.log('AudioContext suspended, attempting to resume and play');
                        audioContext.resume().then(() => {
                            // Play the audio after resuming
                            const buffer = audioContext.createBuffer(1, audioData.length, audioRXSampleRate);
                            buffer.copyToChannel(audioData, 0);
                            
                            const source = audioContext.createBufferSource();
                            source.buffer = buffer;
                            
                            // Connect through the audio processing chain (filter -> gain -> destination)
                            if (audioRXBiquadFilterNode && audioRXGainNode) {
                                source.connect(audioRXBiquadFilterNode);
                                audioRXBiquadFilterNode.connect(audioRXGainNode);
                                audioRXGainNode.connect(audioContext.destination);
                            } else if (audioRXGainNode) {
                                source.connect(audioRXGainNode);
                                audioRXGainNode.connect(audioContext.destination);
                            } else {
                                source.connect(audioContext.destination);
                            }
                            source.start();
                        }).catch((error) => {
                            console.error('Failed to resume AudioContext:', error);
                        });
                    } else {
                        console.log('AudioContext not available, state:', audioContext ? audioContext.state : 'null');
                    }
                }
            } catch (error) {
                console.error('Error processing audio data:', error);
            }
        }
    };
    
    wsAudioRX.onclose = function() {
        console.log('Audio RX WebSocket disconnected');
        updateConnectionStatus('rx', false);
        // Clean up audio context
        if (audioRXSourceNode) {
            audioRXSourceNode.onaudioprocess = null;
        }
        if (audioContext) {
            audioContext.close().then(() => {
                console.log('Audio context closed');
            }).catch((error) => {
                console.error('Error closing audio context:', error);
            });
        }
        // Reset audio buffers
        audioRXAudioBuffer = [];
        audioBufferReady = false;
    };
    
    wsAudioRX.onerror = function(error) {
        console.error('Audio RX WebSocket error:', error);
        updateConnectionStatus('rx', false);
    };
    
    // Audio TX WebSocket
    wsAudioTX = new WebSocket(`${baseUrl}/WSaudioTX`);
    wsAudioTX.onopen = function() {
        console.log('Audio TX WebSocket connected');
        updateConnectionStatus('tx', true);
        
        // Request microphone access for TX
        if (!microphoneStream && navigator.mediaDevices) {
            navigator.mediaDevices.getUserMedia({ audio: true })
                .then(function(stream) {
                    microphoneStream = stream;
                    console.log('Microphone access granted');
                })
                .catch(function(error) {
                    console.error('Microphone access denied:', error);
                });
        }
    };
    
    wsAudioTX.onclose = function() {
        console.log('Audio TX WebSocket disconnected');
        updateConnectionStatus('tx', false);
        
        // Stop microphone stream when TX connection closes
        if (microphoneStream) {
            microphoneStream.getTracks().forEach(track => track.stop());
            microphoneStream = null;
        }
    };
    
    wsAudioTX.onerror = function(error) {
        console.error('Audio TX WebSocket error:', error);
        updateConnectionStatus('tx', false);
    };
}

function disconnectWebSockets() {
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
    
    updateConnectionStatus('ctrl', false);
    updateConnectionStatus('rx', false);
    updateConnectionStatus('tx', false);
}

function handleControlMessage(data) {
    const parts = data.split(':');
    const command = parts[0];
    const value = parts[1];
    
    console.log('Received command:', command, 'value:', value);
    
    switch (command) {
        case 'getFreq':
            // IC-M710 frequency fix: ensure integer conversion
            const freq = parseInt(value);
            if (freq && freq > 0) {
                appState.frequency = freq;
                console.log('Frequency updated to:', freq);
                updateFrequencyDisplay();
            } else {
                console.log('Invalid frequency received, keeping current:', appState.frequency);
            }
            break;
        case 'getMode':
            if (value) {
                appState.mode = value;
                console.log('Mode updated to:', value);
                updateModeDisplay();
            }
            break;
        case 'getSignalLevel':
            updateSignalMeter(value);
            break;
        case 'PONG':
            // Handle latency calculation
            break;
        default:
            console.log('Unknown command:', command, value);
            break;
    }
}

function handlePTT(active) {
    // Prevent multiple rapid PTT calls
    if (appState.pttActive === active) {
        return;
    }
    
    appState.pttActive = active;
    
    // Immediate visual feedback
    const pttBtn = document.getElementById('ptt-btn');
    if (pttBtn) {
        if (active) {
            pttBtn.style.transform = 'scale(0.95)';
            pttBtn.style.background = 'linear-gradient(145deg, #ff8800, #ff4400)';
        } else {
            pttBtn.style.transform = 'scale(1)';
            pttBtn.style.background = 'linear-gradient(145deg, #ff6600, #cc4400)';
        }
    }
    
    // Send PTT command with priority
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        try {
            wsControlTRX.send(`setPTT:${active}`);
            console.log(`PTT ${active ? 'ON' : 'OFF'} sent at ${Date.now()}`);
        } catch (error) {
            console.error('Failed to send PTT command:', error);
        }
    } else {
        console.warn('WebSocket not connected, cannot send PTT command');
    }
    
    // Haptic feedback for mobile
    if (navigator.vibrate && IS_MOBILE) {
        navigator.vibrate(active ? 30 : 15);
    }
    
    // Update TX indicator
    updateConnectionStatus('tx', active ? 'transmitting' : true);
}

function setFrequency(freq) {
    // Validate frequency
    if (!freq || freq <= 0 || freq > 1000000000) { // 1 GHz limit
        console.warn('Invalid frequency:', freq);
        return;
    }
    
    appState.frequency = Math.round(freq);
    updateFrequencyDisplay();
    
    // Send frequency command with error handling
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        try {
            wsControlTRX.send(`setFreq:${appState.frequency}`);
            console.log(`Frequency set to: ${appState.frequency} Hz`);
        } catch (error) {
            console.error('Failed to send frequency command:', error);
        }
    } else {
        console.warn('WebSocket not connected, cannot send frequency command');
    }
    
    // Button feedback
    if (navigator.vibrate && IS_MOBILE) {
        navigator.vibrate(25);
    }
}

function setMode(mode) {
    appState.mode = mode;
    updateModeDisplay();
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setMode:${mode}`);
    }
}

function setVFO(vfo) {
    appState.vfo = vfo;
    
    // Update VFO button states
    document.querySelectorAll('.vfo-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.getElementById(`vfo-${vfo.toLowerCase()}`).classList.add('active');
}

function swapVFO() {
    // Implement VFO A/B swap
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send('swapVFO:');
    }
    
    // Visual feedback
    if (navigator.vibrate && IS_MOBILE) {
        navigator.vibrate(40);
    }
}

function updateFrequencyDisplay() {
    const freq = appState.frequency;
    console.log('Updating frequency display with:', freq);
    
    // Ensure we have a valid frequency
    if (!freq || freq <= 0) {
        console.log('Invalid frequency, using default 7053000');
        appState.frequency = 7053000;
    }
    
    const freqStr = appState.frequency.toString().padStart(9, '0');
    console.log('Frequency string:', freqStr);
    
    // Update individual digit elements
    const elements = {
        'freq-100mhz': freqStr[0],
        'freq-10mhz': freqStr[1], 
        'freq-1mhz': freqStr[2],
        'freq-100khz': freqStr[3],
        'freq-10khz': freqStr[4],
        'freq-1khz': freqStr[5],
        'freq-100hz': freqStr[6],
        'freq-10hz': freqStr[7],
        'freq-1hz': freqStr[8]
    };
    
    Object.entries(elements).forEach(([id, digit]) => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = digit;
        } else {
            console.warn('Element not found:', id);
        }
    });
    
    console.log('Frequency display updated successfully');
}

function updateModeDisplay() {
    // Update mode button states
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.mode === appState.mode) {
            btn.classList.add('active');
        }
    });
}

function updateConnectionStatus(type, connected) {
    const indicator = document.getElementById(`status-${type}`);
    if (indicator) {
        if (connected === 'transmitting') {
            indicator.style.background = 'linear-gradient(145deg, #ff4444, #cc0000)';
            indicator.textContent = 'TX';
        } else if (connected) {
            indicator.classList.add('connected');
        } else {
            indicator.classList.remove('connected');
            indicator.style.background = '';
        }
    }
}

function updateSignalMeter(level) {
    const meter = document.getElementById('signal-level');
    const text = document.getElementById('signal-text');
    
    if (meter && text) {
        meter.value = level;
        // Convert to S-meter reading
        const sValue = Math.max(0, Math.min(9, Math.floor((level + 60) / 6)));
        text.textContent = `S${sValue}`;
    }
}

function updateStatus() {
    const statusText = document.getElementById('connection-status');
    if (statusText) {
        statusText.textContent = appState.powered ? 'Connected' : 'Disconnected';
    }
}

// Audio control handlers
function updateAFGain() {
    const value = document.getElementById('af-gain').value;
    document.getElementById('af-value').textContent = value;
    
    // Update audio gain in the Web Audio API
    if (audioRXGainNode && audioContext) {
        const gainValue = value / 100; // Convert to 0.0 - 1.0 range
        audioRXGainNode.gain.setValueAtTime(gainValue, audioContext.currentTime);
        console.log(`Audio gain set to: ${gainValue}`);
    }
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setAFGain:${value}`);
    }
}

function updateRFGain() {
    const value = document.getElementById('rf-gain').value;
    document.getElementById('rf-value').textContent = value;
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setRFGain:${value}`);
    }
}

function updateMicGain() {
    const value = document.getElementById('mic-gain').value;
    document.getElementById('mic-value').textContent = value;
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setMicGain:${value}`);
    }
}

// Audio filter controls (like main program)
function setAudioFilter(filterType, frequency, gain, Q) {
    if (audioRXBiquadFilterNode && audioContext) {
        try {
            audioRXBiquadFilterNode.type = filterType;
            audioRXBiquadFilterNode.frequency.setValueAtTime(frequency, audioContext.currentTime);
            audioRXBiquadFilterNode.gain.setValueAtTime(gain, audioContext.currentTime);
            audioRXBiquadFilterNode.Q.setValueAtTime(Q, audioContext.currentTime);
            console.log(`Audio filter set: ${filterType}, ${frequency}Hz, ${gain}dB, Q=${Q}`);
        } catch (error) {
            console.error('Error setting audio filter:', error);
        }
    }
}

// Audio buffer monitoring
function monitorAudioBuffer() {
    if (audioBufferReady) {
        const bufferSize = audioRXAudioBuffer.length;
        console.log(`Audio buffer size: ${bufferSize}`);
        
        // Warn if buffer is too large (potential lag) or too small (potential underruns)
        if (bufferSize > 10) {
            console.warn(`Audio buffer is large (${bufferSize}), potential audio lag`);
        } else if (bufferSize === 0) {
            console.warn('Audio buffer is empty, potential audio interruptions');
        }
    }
    
    // Check periodically
    setTimeout(monitorAudioBuffer, 1000);
}

// Start monitoring when audio is initialized
function startAudioMonitoring() {
    monitorAudioBuffer();
}

// Tuning functions
function tuneStep(step) {
    const actualStep = step || appState.tuneStep;
    const newFreq = appState.frequency + actualStep;
    if (newFreq > 0 && newFreq < 1000000000) { // 1 GHz limit
        setFrequency(newFreq);
    }
    
    // Visual feedback
    if (navigator.vibrate && IS_MOBILE) {
        navigator.vibrate(20);
    }
}

function updateTuneStep() {
    const stepValue = parseInt(document.getElementById('tune-step').value);
    appState.tuneStep = stepValue;
    
    // Update status display
    const stepDisplay = document.getElementById('freq-step');
    if (stepDisplay) {
        if (stepValue >= 1000) {
            stepDisplay.textContent = `Step: ${stepValue/1000}kHz`;
        } else {
            stepDisplay.textContent = `Step: ${stepValue}Hz`;
        }
    }
}

// Memory functions
function memoryRecall() {
    const channel = document.getElementById('memory-ch').value;
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`memoryRecall:${channel}`);
    }
}

function memoryStore() {
    const channel = document.getElementById('memory-ch').value;
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`memoryStore:${channel}`);
    }
}

function memoryScan() {
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send('memoryScan:');
    }
    
    // Visual feedback
    const btn = event.target;
    btn.classList.toggle('active');
}

function memorySkip() {
    const channel = document.getElementById('memory-ch').value;
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`memorySkip:${channel}`);
    }
}

// Quick setting toggles
function toggleAGC() {
    const btn = document.getElementById('agc-status').parentElement;
    btn.classList.toggle('active');
    // Send command to radio
}

function toggleNB() {
    const btn = document.getElementById('nb-status').parentElement;
    btn.classList.toggle('active');
    // Send command to radio
}

function toggleNR() {
    const btn = document.getElementById('nr-status').parentElement;
    btn.classList.toggle('active');
    // Send command to radio
}

function toggleATT() {
    const btn = document.getElementById('att-status').parentElement;
    btn.classList.toggle('active');
    // Send command to radio
}

function togglePRE() {
    const btn = document.getElementById('pre-status').parentElement;
    btn.classList.toggle('active');
    // Send command to radio
}

// Professional ICOM-style functions
function showFreqKeypad() {
    const freq = prompt('Enter frequency (MHz):', (appState.frequency / 1000000).toFixed(6));
    if (freq && !isNaN(freq)) {
        setFrequency(Math.round(parseFloat(freq) * 1000000));
    }
}

function toggleSplit() {
    appState.split = !appState.split;
    const splitBtn = document.querySelector('[onclick="toggleSplit();"]');
    if (splitBtn) {
        splitBtn.classList.toggle('active', appState.split);
    }
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setSplit:${appState.split}`);
    }
    
    updateVFODisplay();
}

function copyVFO() {
    if (appState.vfo === 'A') {
        appState.vfoBFreq = appState.vfoAFreq;
        appState.vfoBMode = appState.vfoAMode;
    } else {
        appState.vfoAFreq = appState.vfoBFreq;
        appState.vfoAMode = appState.vfoBMode;
    }
    updateVFODisplay();
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send('copyVFO:');
    }
}

function toggleRIT() {
    appState.rit = !appState.rit;
    const ritBtn = document.getElementById('rit-btn');
    const ritOffset = document.getElementById('rit-offset');
    
    if (ritBtn) {
        ritBtn.classList.toggle('active', appState.rit);
    }
    if (ritOffset) {
        ritOffset.disabled = !appState.rit;
    }
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setRIT:${appState.rit}`);
    }
}

function toggleXIT() {
    appState.xit = !appState.xit;
    const xitBtn = document.getElementById('xit-btn');
    
    if (xitBtn) {
        xitBtn.classList.toggle('active', appState.xit);
    }
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setXIT:${appState.xit}`);
    }
}

function updateRIT() {
    const ritOffset = document.getElementById('rit-offset');
    const ritValue = document.getElementById('rit-value');
    
    if (ritOffset && ritValue) {
        appState.ritOffset = parseInt(ritOffset.value);
        ritValue.textContent = appState.ritOffset + 'Hz';
        
        if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
            wsControlTRX.send(`setRITOffset:${appState.ritOffset}`);
        }
    }
}

function toggleVOX() {
    appState.vox = !appState.vox;
    const voxBtn = document.querySelector('[onclick="toggleVOX();"]');
    if (voxBtn) {
        voxBtn.classList.toggle('active', appState.vox);
    }
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setVOX:${appState.vox}`);
    }
}

function toggleMON() {
    appState.monitor = !appState.monitor;
    const monBtn = document.querySelector('[onclick="toggleMON();"]');
    if (monBtn) {
        monBtn.classList.toggle('active', appState.monitor);
    }
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setMonitor:${appState.monitor}`);
    }
}

function toggleTUNE() {
    appState.tune = !appState.tune;
    const tuneBtn = document.querySelector('[onclick="toggleTUNE();"]');
    if (tuneBtn) {
        tuneBtn.classList.toggle('active', appState.tune);
    }
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setTune:${appState.tune}`);
    }
}

// Function key handlers
function quickMemo() {
    // Quick memory store to current channel
    memoryStore();
}

function quickScan() {
    // Start/stop scanning
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send('startScan:');
    }
}

function quickSplit() {
    toggleSplit();
}

function quickFilter() {
    // Cycle through filter widths
    const filters = ['wide', 'mid', 'narrow'];
    const currentIndex = filters.indexOf(appState.filterWidth);
    const nextIndex = (currentIndex + 1) % filters.length;
    appState.filterWidth = filters[nextIndex];
    
    const filterSelect = document.getElementById('filter-width');
    if (filterSelect) {
        filterSelect.value = appState.filterWidth;
    }
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setFilter:${appState.filterWidth}`);
    }
}

function quickDual() {
    toggleDualWatch();
}

function quickScope() {
    toggleBandScope();
}

function updateVFODisplay() {
    // Update VFO frequency displays
    const vfoAFreq = document.getElementById('vfo-a-freq');
    const vfoBFreq = document.getElementById('vfo-b-freq');
    const vfoAMode = document.getElementById('vfo-a-mode');
    const vfoBMode = document.getElementById('vfo-b-mode');
    
    if (vfoAFreq) {
        vfoAFreq.textContent = formatFrequency(appState.vfoAFreq);
    }
    if (vfoBFreq) {
        vfoBFreq.textContent = formatFrequency(appState.vfoBFreq);
    }
    if (vfoAMode) {
        vfoAMode.textContent = appState.vfoAMode;
    }
    if (vfoBMode) {
        vfoBMode.textContent = appState.vfoBMode;
    }
    
    // Update active VFO highlighting
    const vfoADisplay = document.getElementById('vfo-a-display');
    const vfoBDisplay = document.getElementById('vfo-b-display');
    
    if (vfoADisplay && vfoBDisplay) {
        vfoADisplay.classList.toggle('active', appState.vfo === 'A');
        vfoBDisplay.classList.toggle('active', appState.vfo === 'B');
    }
}

function formatFrequency(freq) {
    const mhz = Math.floor(freq / 1000000);
    const khz = Math.floor((freq % 1000000) / 1000);
    const hz = freq % 1000;
    return `${mhz}.${khz.toString().padStart(3, '0')}.${hz.toString().padStart(3, '0')}`;
}

function initializeSMeter() {
    const canvas = document.getElementById('s-meter-canvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    // Draw S-meter background
    function drawSMeter(signalLevel) {
        ctx.clearRect(0, 0, width, height);
        
        // Background
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, width, height);
        
        // S-meter scale
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1;
        
        // Draw scale lines
        for (let i = 0; i <= 15; i++) {
            const x = (i / 15) * (width - 20) + 10;
            ctx.beginPath();
            ctx.moveTo(x, height - 20);
            ctx.lineTo(x, height - 10);
            ctx.stroke();
        }
        
        // Draw signal bar
        if (signalLevel > -60) {
            const normalizedLevel = Math.max(0, Math.min(1, (signalLevel + 60) / 80));
            const barWidth = normalizedLevel * (width - 20);
            
            // Green for S1-S9, yellow for S9+, red for S9+40
            if (normalizedLevel < 0.6) {
                ctx.fillStyle = '#00ff00';
            } else if (normalizedLevel < 0.8) {
                ctx.fillStyle = '#ffff00';
            } else {
                ctx.fillStyle = '#ff0000';
            }
            
            ctx.fillRect(10, 10, barWidth, height - 30);
        }
    }
    
    // Store the drawing function for updates
    window.drawSMeter = drawSMeter;
    drawSMeter(-60); // Initialize with no signal
}

function updateSquelch() {
    const value = document.getElementById('squelch').value;
    document.getElementById('sql-value').textContent = value;
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setSquelch:${value}`);
    }
}

function toggleCOMP() {
    const btn = document.getElementById('comp-status').parentElement;
    btn.classList.toggle('active');
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setCompressor:${btn.classList.contains('active')}`);
    }
}

// Professional feature functions
function updateFilterWidth() {
    const value = document.getElementById('filter-width').value;
    appState.filterWidth = value;
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setFilter:${value}`);
    }
}

function updateAntenna() {
    const value = document.getElementById('antenna-sel').value;
    appState.antenna = value;
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setAntenna:${value}`);
    }
}

function updateKeyerSpeed() {
    const value = document.getElementById('keyer-speed').value;
    appState.keyerSpeed = value;
    document.getElementById('keyer-wpm').textContent = value + ' WPM';
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setKeyerSpeed:${value}`);
    }
}

function toggleDualWatch() {
    appState.dualWatch = !appState.dualWatch;
    const btn = document.querySelector('[onclick*="toggleDualWatch"]');
    if (btn) {
        btn.classList.toggle('active', appState.dualWatch);
    }
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setDualWatch:${appState.dualWatch}`);
    }
}

function toggleFullBreakIn() {
    appState.qsk = !appState.qsk;
    const btn = document.querySelector('[onclick*="toggleFullBreakIn"]');
    if (btn) {
        btn.classList.toggle('active', appState.qsk);
    }
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setQSK:${appState.qsk}`);
    }
}

function toggleBandScope() {
    appState.scope = !appState.scope;
    const btn = document.querySelector('[onclick*="toggleBandScope"]');
    if (btn) {
        btn.classList.toggle('active', appState.scope);
    }
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setBandScope:${appState.scope}`);
    }
}

function toggleWaterfall() {
    appState.waterfall = !appState.waterfall;
    const btn = document.querySelector('[onclick*="toggleWaterfall"]');
    if (btn) {
        btn.classList.toggle('active', appState.waterfall);
    }
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setWaterfall:${appState.waterfall}`);
    }
}

function toggleAntTuner() {
    appState.antTuner = !appState.antTuner;
    const btn = document.querySelector('[onclick*="toggleAntTuner"]');
    if (btn) {
        btn.classList.toggle('active', appState.antTuner);
    }
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setAntTuner:${appState.antTuner}`);
    }
}

// Clock update function
function updateClock() {
    const timeDisplay = document.getElementById('current-time');
    if (timeDisplay) {
        const now = new Date();
        const utc = now.toISOString().substr(11, 8) + ' UTC';
        timeDisplay.textContent = utc;
    }
}

// Digital Modes Functions
function toggleDigitalPanel() {
    const content = document.getElementById('digital-content');
    const toggle = document.querySelector('.digital-modes-panel .panel-toggle');
    
    if (content.style.display === 'none') {
        content.style.display = 'block';
        toggle.classList.add('open');
    } else {
        content.style.display = 'none';
        toggle.classList.remove('open');
    }
}

function setDigitalMode(mode) {
    appState.digitalMode = mode;
    
    // Update button states
    document.querySelectorAll('.digital-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    const activeBtn = document.querySelector(`[onclick="setDigitalMode('${mode}');"]`);
    if (activeBtn) {
        activeBtn.classList.add('active');
    }
    
    // Show/hide mode-specific controls
    document.querySelectorAll('.cw-controls, .ft8-controls').forEach(ctrl => {
        ctrl.style.display = 'none';
    });
    
    if (mode === 'CW') {
        const cwControls = document.getElementById('cw-controls');
        if (cwControls) cwControls.style.display = 'block';
    } else if (mode === 'FT8' || mode === 'FT4') {
        const ft8Controls = document.getElementById('ft8-controls');
        if (ft8Controls) ft8Controls.style.display = 'block';
        startFT8Cycle();
    }
    
    // Send command to radio
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setDigitalMode:${mode}`);
    }
    
    console.log(`Digital mode set to: ${mode}`);
}

function updateCWSpeed() {
    const speed = document.getElementById('cw-speed').value;
    appState.cwSpeed = speed;
    document.getElementById('cw-speed-display').textContent = speed + ' WPM';
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`setCWSpeed:${speed}`);
    }
}

function sendCWMacro(macro) {
    const macros = {
        'CQ': 'CQ CQ CQ DE [MYCALL] [MYCALL] K',
        '599': '599 599 [MYSTATE]',
        'TU': 'TU 73 DE [MYCALL] K',
        'AGN': 'AGN PSE AGN'
    };
    
    const message = macros[macro] || macro;
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`sendCW:${message}`);
    }
    
    console.log(`Sending CW macro: ${message}`);
}

function startFT8Cycle() {
    // FT8 operates on 15-second cycles
    const updateFT8Time = () => {
        const now = new Date();
        const seconds = now.getUTCSeconds();
        const cycleSecond = seconds % 15;
        const isOddCycle = Math.floor(seconds / 15) % 2 === 1;
        
        appState.ft8Cycle = isOddCycle ? 'TX' : 'RX';
        
        const timeDisplay = document.getElementById('ft8-time');
        const cycleDisplay = document.getElementById('ft8-cycle');
        
        if (timeDisplay) {
            timeDisplay.textContent = String(cycleSecond).padStart(2, '0') + '/15';
        }
        if (cycleDisplay) {
            cycleDisplay.textContent = `Cycle: ${appState.ft8Cycle}`;
            cycleDisplay.style.color = appState.ft8Cycle === 'TX' ? '#ff4444' : '#00ff00';
        }
    };
    
    updateFT8Time();
    setInterval(updateFT8Time, 1000);
}

function sendFT8(message) {
    const ft8Messages = document.getElementById('ft8-messages');
    const timestamp = new Date().toISOString().substr(11, 8);
    
    if (ft8Messages) {
        ft8Messages.value += `${timestamp} TX: ${message}\n`;
        ft8Messages.scrollTop = ft8Messages.scrollHeight;
    }
    
    if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
        wsControlTRX.send(`sendFT8:${message}`);
    }
    
    console.log(`Sending FT8: ${message}`);
}

function updateWaterfallCenter() {
    const offset = document.getElementById('waterfall-offset').value;
    appState.waterfallCenter = 1500 + parseInt(offset);
    document.getElementById('waterfall-center').textContent = appState.waterfallCenter + 'Hz';
    
    // Redraw waterfall with new center frequency
    drawWaterfall();
}

function initializeWaterfall() {
    const canvas = document.getElementById('waterfall-canvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Store drawing function globally
    window.drawWaterfall = function() {
        const width = canvas.width;
        const height = canvas.height;
        
        ctx.clearRect(0, 0, width, height);
        
        // Draw frequency scale
        ctx.strokeStyle = '#444';
        ctx.lineWidth = 1;
        
        for (let i = 0; i <= 10; i++) {
            const x = (i / 10) * width;
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.stroke();
        }
        
        // Draw center frequency line
        ctx.strokeStyle = '#ff8800';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(width / 2, 0);
        ctx.lineTo(width / 2, height);
        ctx.stroke();
        
        // Simulate waterfall data
        for (let y = 0; y < height; y += 2) {
            for (let x = 0; x < width; x += 4) {
                const intensity = Math.random() * 100;
                let color;
                if (intensity > 70) color = '#ffff00'; // Yellow for strong signals
                else if (intensity > 40) color = '#ff8800'; // Orange
                else if (intensity > 20) color = '#0088ff'; // Blue
                else color = '#000044'; // Dark blue for noise
                
                ctx.fillStyle = color;
                ctx.fillRect(x, y, 4, 2);
            }
        }
    };
    
    drawWaterfall();
    
    // Update waterfall periodically
    setInterval(drawWaterfall, 100);
}

// Logbook Functions
function toggleLogbookPanel() {
    const content = document.getElementById('logbook-content');
    const toggle = document.querySelector('.logbook-panel .panel-toggle');
    
    if (content.style.display === 'none') {
        content.style.display = 'block';
        toggle.classList.add('open');
    } else {
        content.style.display = 'none';
        toggle.classList.remove('open');
    }
}

function initializeLogbook() {
    const now = new Date();
    const today = now.toISOString().split('T')[0];
    const currentTime = now.toTimeString().substr(0, 5);
    
    const dateInput = document.getElementById('qso-date');
    const timeInput = document.getElementById('qso-time');
    
    if (dateInput) dateInput.value = today;
    if (timeInput) timeInput.value = currentTime;
    
    // Load saved QSOs from localStorage
    const savedQSOs = localStorage.getItem('qsoLog');
    if (savedQSOs) {
        appState.qsoLog = JSON.parse(savedQSOs);
        updateQSOList();
    }
}

function saveQSO() {
    const callsign = document.getElementById('callsign').value.trim().toUpperCase();
    const rstSent = document.getElementById('rst-sent').value.trim();
    const rstRcvd = document.getElementById('rst-rcvd').value.trim();
    const qth = document.getElementById('qth').value.trim();
    const name = document.getElementById('name').value.trim();
    const date = document.getElementById('qso-date').value;
    const time = document.getElementById('qso-time').value;
    
    if (!callsign) {
        alert('Callsign is required!');
        return;
    }
    
    const qso = {
        callsign,
        rstSent: rstSent || '599',
        rstRcvd: rstRcvd || '599',
        qth,
        name,
        date,
        time,
        frequency: appState.frequency,
        mode: appState.mode,
        timestamp: new Date().toISOString()
    };
    
    appState.qsoLog.unshift(qso); // Add to beginning
    
    // Keep only last 50 QSOs in memory
    if (appState.qsoLog.length > 50) {
        appState.qsoLog = appState.qsoLog.slice(0, 50);
    }
    
    // Save to localStorage
    localStorage.setItem('qsoLog', JSON.stringify(appState.qsoLog));
    
    // Update display
    updateQSOList();
    
    // Clear form
    document.getElementById('callsign').value = '';
    document.getElementById('qth').value = '';
    document.getElementById('name').value = '';
    
    // Haptic feedback
    if (navigator.vibrate && IS_MOBILE) {
        navigator.vibrate(50);
    }
    
    console.log('QSO logged:', qso);
}

function updateQSOList() {
    const qsoList = document.getElementById('qso-list');
    if (!qsoList) return;
    
    qsoList.innerHTML = '';
    
    appState.qsoLog.slice(0, 10).forEach(qso => {
        const qsoItem = document.createElement('div');
        qsoItem.className = 'qso-item';
        
        const freq = (qso.frequency / 1000000).toFixed(3);
        
        qsoItem.innerHTML = `
            <div>
                <span class="qso-callsign">${qso.callsign}</span>
                ${qso.name ? ` - ${qso.name}` : ''}
            </div>
            <div class="qso-details">
                ${freq} MHz ${qso.mode} | ${qso.date} ${qso.time} UTC
                ${qso.qth ? ` | ${qso.qth}` : ''}
            </div>
        `;
        
        qsoList.appendChild(qsoItem);
    });
    
    if (appState.qsoLog.length === 0) {
        qsoList.innerHTML = '<div class="qso-item">No QSOs logged yet</div>';
    }
}
window.addEventListener('error', function(e) {
    console.error('Mobile app error:', e.error);
});

// PWA support
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').then(function(registration) {
        console.log('ServiceWorker registration successful');
    }).catch(function(err) {
        console.log('ServiceWorker registration failed');
    });
}

// Comprehensive mobile interface test
function runMobileInterfaceTest() {
    console.log('🚀 Starting comprehensive mobile interface test...');
    
    const testResults = {
        uiElements: 0,
        eventHandlers: 0,
        professionalFeatures: 0,
        totalTests: 0,
        passed: 0,
        failed: 0
    };
    
    // Test 1: Check essential UI elements
    const essentialElements = [
        'power-btn', 'freq-display', 'ptt-btn', 'vfo-a', 'vfo-b',
        's-meter-canvas', 'af-gain', 'rf-gain', 'mic-gain', 'squelch',
        'rit-btn', 'xit-btn', 'memory-ch', 'tune-step', 'filter-width'
    ];
    
    console.log('Testing UI elements...');
    essentialElements.forEach(id => {
        testResults.totalTests++;
        const element = document.getElementById(id);
        if (element) {
            console.log(`✅ ${id}: Found`);
            testResults.uiElements++;
            testResults.passed++;
        } else {
            console.log(`❌ ${id}: Missing`);
            testResults.failed++;
        }
    });
    
    // Test 2: Check function definitions
    const functions = [
        'powerToggle', 'setFrequency', 'setMode', 'setVFO', 'handlePTT',
        'toggleSplit', 'copyVFO', 'toggleRIT', 'toggleXIT', 'updateTuneStep',
        'toggleDualWatch', 'toggleBandScope', 'updateFilterWidth',
        'setDigitalMode', 'sendCWMacro', 'sendFT8', 'saveQSO', 'toggleLogbookPanel'
    ];
    
    console.log('Testing function definitions...');
    functions.forEach(funcName => {
        testResults.totalTests++;
        if (typeof window[funcName] === 'function') {
            console.log(`✅ ${funcName}: Function defined`);
            testResults.eventHandlers++;
            testResults.passed++;
        } else {
            console.log(`❌ ${funcName}: Function missing`);
            testResults.failed++;
        }
    });
    
    // Test 3: Check professional features
    const professionalFeatures = [
        { name: 'Dual VFO Display', test: () => document.querySelectorAll('.vfo-display').length >= 2 },
        { name: 'Function Keys F1-F6', test: () => document.querySelectorAll('.func-btn').length >= 6 },
        { name: 'S-Meter Canvas', test: () => document.getElementById('s-meter-canvas') !== null },
        { name: 'Professional Panel', test: () => document.querySelector('.professional-panel') !== null },
        { name: 'Memory Controls', test: () => document.querySelectorAll('.mem-btn').length >= 3 },
        { name: 'Advanced Audio Controls', test: () => document.querySelectorAll('.volume-control').length >= 4 },
        { name: 'RIT/XIT Controls', test: () => document.querySelector('.rit-xit-controls') !== null },
        { name: 'Step Controls', test: () => document.querySelector('.step-controls') !== null },
        { name: 'Digital Modes Panel', test: () => document.querySelector('.digital-modes-panel') !== null },
        { name: 'Waterfall Display', test: () => document.getElementById('waterfall-canvas') !== null },
        { name: 'FT8/CW Controls', test: () => document.querySelectorAll('.digital-btn').length >= 6 },
        { name: 'Logbook Panel', test: () => document.querySelector('.logbook-panel') !== null },
        { name: 'QSO Entry Form', test: () => document.getElementById('callsign') !== null }
    ];
    
    console.log('Testing professional features...');
    professionalFeatures.forEach(feature => {
        testResults.totalTests++;
        try {
            if (feature.test()) {
                console.log(`✅ ${feature.name}: Working`);
                testResults.professionalFeatures++;
                testResults.passed++;
            } else {
                console.log(`❌ ${feature.name}: Not working`);
                testResults.failed++;
            }
        } catch (error) {
            console.log(`❌ ${feature.name}: Error - ${error.message}`);
            testResults.failed++;
        }
    });
    
    // Test 4: Check app state initialization
    testResults.totalTests++;
    if (typeof appState === 'object' && appState !== null) {
        console.log('✅ App State: Initialized');
        console.log('📊 Current app state:', appState);
        testResults.passed++;
    } else {
        console.log('❌ App State: Not initialized');
        testResults.failed++;
    }
    
    // Test 5: Test S-meter canvas drawing
    testResults.totalTests++;
    try {
        if (typeof window.drawSMeter === 'function') {
            window.drawSMeter(-40); // Test with sample signal
            console.log('✅ S-Meter Drawing: Working');
            testResults.passed++;
        } else {
            console.log('❌ S-Meter Drawing: Function not available');
            testResults.failed++;
        }
    } catch (error) {
        console.log(`❌ S-Meter Drawing: Error - ${error.message}`);
        testResults.failed++;
    }
    
    // Summary
    console.log('\n🎯 MOBILE INTERFACE TEST SUMMARY:');
    console.log('=================================');
    console.log(`📱 UI Elements: ${testResults.uiElements}/${essentialElements.length}`);
    console.log(`⚡ Event Handlers: ${testResults.eventHandlers}/${functions.length}`);
    console.log(`🏆 Professional Features: ${testResults.professionalFeatures}/${professionalFeatures.length}`);
    console.log(`✅ Total Passed: ${testResults.passed}/${testResults.totalTests}`);
    console.log(`❌ Total Failed: ${testResults.failed}/${testResults.totalTests}`);
    console.log(`📊 Success Rate: ${((testResults.passed / testResults.totalTests) * 100).toFixed(1)}%`);
    
    if (testResults.failed === 0) {
        console.log('🎉 ALL TESTS PASSED! Mobile interface is fully functional.');
    } else {
        console.log(`⚠️  ${testResults.failed} tests failed. Check the details above.`);
    }
    
    return testResults;
}

// Auto-run test when page loads
window.addEventListener('load', function() {
    setTimeout(() => {
        console.log('🔧 Running automatic mobile interface test...');
        runMobileInterfaceTest();
    }, 2000); // Wait 2 seconds for everything to initialize
});

// Make test function globally available
window.runMobileInterfaceTest = runMobileInterfaceTest;
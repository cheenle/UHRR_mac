// Direct copy of audio functions from controls.js to mobile interface
// This ensures 100% compatibility with the working desktop version

// Global variables (matching desktop version)
var wsAudioRX = "";
var AudioRX_context = "";
var AudioRX_source_node = "";
var AudioRX_gain_node = "";
var AudioRX_biquadFilter_node = "";
var AudioRX_analyser = "";
var audiobufferready = false;
var AudioRX_audiobuffer = [];
var AudioRX_sampleRate = 16000;
var audioContextInitialized = false; // Track if audio context has been initialized with user gesture

// Mobile-specific variables
var isMobileDevice = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
var mobileAudioBufferingOptimized = false;

// Audio functions copied directly from controls.js
function AudioRX_start() {
    console.log('Starting AudioRX with desktop-compatible implementation');
    document.getElementById("indwsAudioRX").innerHTML = '<img src="img/critsgrey.png">wsRX';
    AudioRX_audiobuffer = [];
    var lenglitchbuf = 2;

    // Use the same protocol and URL construction as desktop version
    wsAudioRX = new WebSocket('wss://' + window.location.href.split('/')[2] + '/WSaudioRX');
    wsAudioRX.binaryType = 'arraybuffer';
    wsAudioRX.onmessage = appendwsAudioRX;
    wsAudioRX.onopen = wsAudioRXopen;
    wsAudioRX.onclose = wsAudioRXclose;
    wsAudioRX.onerror = wsAudioRXerror;

    // 每秒打印一次码率（RX/TX）
    if (!window.__brTimer) {
        window.__rxBytes = 0;
        window.__txBytes = 0;
        window.__brTimer = setInterval(function() {
            var rxkbps = (window.__rxBytes || 0) * 8 / 1000; // Kbps
            var txkbps = (window.__txBytes || 0) * 8 / 1000;
            console.log(`[码率] RX: ${rxkbps.toFixed(1)} kbps, TX: ${txkbps.toFixed(1)} kbps`);
            var brEl = document.getElementById('div-bitrates');
            if (brEl) {
                brEl.textContent = `bitrate RX: ${rxkbps.toFixed(1)} kbps | TX: ${txkbps.toFixed(1)} kbps`;
            }
            window.__rxBytes = 0;
            window.__txBytes = 0;
        }, 1000);
    }

    function appendwsAudioRX(msg) {
        console.log('DEBUG: Received audio data message');
        // 码率统计：RX
        if (!window.__rxBytes) {
            window.__rxBytes = 0;
        }
        if (msg && msg.data && msg.data.byteLength) {
            window.__rxBytes += msg.data.byteLength;
        }
        // 限制缓冲区大小，防止累积过多音频数据
        if (AudioRX_audiobuffer.length > 10) {
            console.log('⚠️ 音频缓冲区过大，清除旧数据');
            AudioRX_audiobuffer = AudioRX_audiobuffer.slice(-5); // 只保留最新的5个缓冲区
        }
        // Convert Int16 to Float32 for Web Audio API
        const int16Data = new Int16Array(msg.data);
        const float32Data = new Float32Array(int16Data.length);
        for (let i = 0; i < int16Data.length; i++) {
            float32Data[i] = int16Data[i] / 32767.0;
        }
        AudioRX_audiobuffer.push(float32Data);
        console.log('DEBUG: Audio buffer length after push:', AudioRX_audiobuffer.length);
        
        // Initialize audio context on first audio data if not already initialized
        // This handles iOS Safari requirement for user gesture
        if (!audioContextInitialized) {
            initializeAudioContextOnUserGesture();
        }
    }

    // Initialize audio context with user gesture handling for iOS Safari
    function initializeAudioContextOnUserGesture() {
        if (audioContextInitialized) return;
        
        try {
            // Create AudioContext with proper settings optimized for mobile
            const audioContextOptions = {
                latencyHint: isMobileDevice ? "playback" : "interactive", // Use playback for better mobile performance
                sampleRate: AudioRX_sampleRate
            };
            
            // For iOS, we might need to use a different sample rate
            if (isMobileDevice && typeof webkitAudioContext !== 'undefined') {
                // iOS Safari sometimes works better with default sample rate
                audioContextOptions.sampleRate = undefined;
            }
            
            AudioRX_context = new (window.AudioContext || window.webkitAudioContext)(audioContextOptions);
            AudioRX_gain_node = AudioRX_context.createGain();
            AudioRX_biquadFilter_node = AudioRX_context.createBiquadFilter();
            AudioRX_analyser = AudioRX_context.createAnalyser();

            // 优先使用 AudioWorkletNode 播放，失败则回退到 ScriptProcessor
            // For mobile devices, we'll optimize the buffer settings
            const targetMinFrames = isMobileDevice ? 2 : 16;  // Reduce for mobile
            const targetMaxFrames = isMobileDevice ? 4 : 32;  // Reduce for mobile
            
            (async () => {
                try {
                    // Note: Worklet may not be available on mobile, so we'll rely on ScriptProcessor fallback
                    await AudioRX_context.audioWorklet.addModule('rx_worklet_processor.js');
                    const rxNode = new AudioWorkletNode(AudioRX_context, 'rx-player');
                    // Store rxNode in AudioRX_source_node so we can access it later for flushing
                    AudioRX_source_node = rxNode;
                    // 调整为稳态与延迟更均衡：根据设备类型优化参数
                    try {
                        rxNode.port.postMessage({
                            type: 'config',
                            min: targetMinFrames,
                            max: targetMaxFrames
                        });
                    } catch (_) {}
                    // 将网络收到的帧直接投递到 worklet
                    window.__pushRxFrame = function(f32) {
                        rxNode.port.postMessage({
                            type: 'push',
                            payload: f32
                        });
                    };
                    // Update onmessage to use worklet
                    wsAudioRX.onmessage = function(msg) {
                        if (!window.__rxBytes) window.__rxBytes = 0;
                        if (msg && msg.data && msg.data.byteLength) window.__rxBytes += msg.data.byteLength;
                        try {
                            // Convert Int16 to Float32 for Web Audio API
                            const int16Data = new Int16Array(msg.data);
                            const float32Data = new Float32Array(int16Data.length);
                            for (let i = 0; i < int16Data.length; i++) {
                                float32Data[i] = int16Data[i] / 32767.0;
                            }
                            window.__pushRxFrame(float32Data);
                        } catch (e) {
                            // 出错回退到原有缓冲播放
                            try {
                                // Convert Int16 to Float32 for Web Audio API
                                const int16Data = new Int16Array(msg.data);
                                const float32Data = new Float32Array(int16Data.length);
                                for (let i = 0; i < int16Data.length; i++) {
                                    float32Data[i] = int16Data[i] / 32767.0;
                                }
                                AudioRX_audiobuffer.push(float32Data);
                            } catch (_) {}
                        }
                    };
                    rxNode.connect(AudioRX_biquadFilter_node);
                } catch (e) {
                    // 回退到 ScriptProcessor
                    console.log('Using ScriptProcessor fallback for audio playback');
                    // Use larger buffer size for mobile to reduce audio glitches
                    const BUFF_SIZE = isMobileDevice ? 1024 : 256;
                    AudioRX_source_node = AudioRX_context.createScriptProcessor(BUFF_SIZE, 1, 1);
                    AudioRX_source_node.onaudioprocess = (function() {
                        return function(event) {
                            var out = event.outputBuffer.getChannelData(0);
                            if (AudioRX_audiobuffer.length === 0) {
                                out.fill(0);
                                return;
                            }
                            var cur = AudioRX_audiobuffer[0];
                            var n = Math.min(cur.length, out.length);
                            for (var j = 0; j < n; j++) out[j] = cur[j];
                            for (var k = n; k < out.length; k++) out[k] = 0;
                            if (n >= cur.length) AudioRX_audiobuffer.shift();
                            else AudioRX_audiobuffer[0] = cur.slice(n);
                        };
                    }());
                    AudioRX_source_node.connect(AudioRX_biquadFilter_node);
                }
                
                // Connect audio nodes
                AudioRX_biquadFilter_node.connect(AudioRX_gain_node);
                AudioRX_gain_node.connect(AudioRX_analyser);
                AudioRX_gain_node.connect(AudioRX_context.destination);
                
                // Set initial audio parameters
                AudioRX_biquadFilter_node.type = "lowshelf";
                // Clamp frequency to valid range for sample rate
                AudioRX_biquadFilter_node.frequency.setValueAtTime(AudioRX_sampleRate/2, AudioRX_context.currentTime);
                AudioRX_biquadFilter_node.gain.setValueAtTime(0, AudioRX_context.currentTime);
                
                AudioRX_SetGAIN();
                
                audioContextInitialized = true;
                console.log('Audio context initialized successfully');
            })();
        } catch (e) {
            console.error('Failed to initialize audio context:', e);
        }
    }

    // Set up a temporary message handler until audio context is initialized
    wsAudioRX.onmessage = function(msg) {
        // Just buffer the audio data until audio context is ready
        appendwsAudioRX(msg);
    };
}

function AudioRX_SetGAIN(vol = "None") {
    if (vol == "None") {
        volumeRX = isMobileDevice ? 1.0 : 0.8; // Higher default volume for mobile
        vol = volumeRX;
    }
    if (AudioRX_context && AudioRX_gain_node) {
        AudioRX_gain_node.gain.setValueAtTime(vol, AudioRX_context.currentTime);
    }
}

function wsAudioRXopen() {
    console.log('DEBUG: WebSocket audio RX connection opened');
    if (document.getElementById("indwsAudioRX")) {
        document.getElementById("indwsAudioRX").innerHTML = '<img src="img/critsgreen.png">wsRX';
    }
}

function wsAudioRXclose() {
    console.log('DEBUG: WebSocket audio RX connection closed');
    if (document.getElementById("indwsAudioRX")) {
        document.getElementById("indwsAudioRX").innerHTML = '<img src="img/critsred.png">wsRX';
    }
}

function wsAudioRXerror(err) {
    console.log('DEBUG: WebSocket audio RX error:', err);
    if (document.getElementById("indwsAudioRX")) {
        document.getElementById("indwsAudioRX").innerHTML = '<img src="img/critsred.png">wsRX';
    }
}

function AudioRX_stop() {
    console.log('Stopping AudioRX');
    audiobufferready = false;
    if (wsAudioRX) {
        wsAudioRX.close();
    }
    if (AudioRX_source_node) {
        AudioRX_source_node.onaudioprocess = null;
    }
    if (AudioRX_context) {
        AudioRX_context.close();
    }
}

// Test function to verify audio is working
function testMobileAudio() {
    console.log('=== Testing Mobile Audio with Desktop Implementation ===');
    AudioRX_start();
}
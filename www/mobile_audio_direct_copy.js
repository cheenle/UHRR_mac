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
var AudioRX_sampleRate = 12000;

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
        AudioRX_audiobuffer.push(new Float32Array(msg.data));
        console.log('DEBUG: Audio buffer length after push:', AudioRX_audiobuffer.length);
    }

    // 显式使用 24k 以与后端匹配
    AudioRX_context = new AudioContext({
        latencyHint: "interactive",
        sampleRate: AudioRX_sampleRate
    });
    AudioRX_gain_node = AudioRX_context.createGain();
    AudioRX_biquadFilter_node = AudioRX_context.createBiquadFilter();
    AudioRX_analyser = AudioRX_context.createAnalyser();

    // 优先使用 AudioWorkletNode 播放，失败则回退到 ScriptProcessor
    (async () => {
        try {
            // Note: Worklet may not be available on mobile, so we'll rely on ScriptProcessor fallback
            await AudioRX_context.audioWorklet.addModule('rx_worklet_processor.js');
            const rxNode = new AudioWorkletNode(AudioRX_context, 'rx-player');
            // Store rxNode in AudioRX_source_node so we can access it later for flushing
            AudioRX_source_node = rxNode;
            // 调整为稳态与延迟更均衡：最小16帧，最大32帧
            try {
                rxNode.port.postMessage({
                    type: 'config',
                    min: 16,
                    max: 32
                });
            } catch (_) {}
            // 将网络收到的帧直接投递到 worklet
            window.__pushRxFrame = function(f32) {
                rxNode.port.postMessage({
                    type: 'push',
                    payload: f32
                });
            };
            // 直接重设 onmessage，避免旧处理函数仍被引用
            wsAudioRX.onmessage = function(msg) {
                if (!window.__rxBytes) window.__rxBytes = 0;
                if (msg && msg.data && msg.data.byteLength) window.__rxBytes += msg.data.byteLength;
                try {
                    window.__pushRxFrame(new Float32Array(msg.data));
                } catch (e) {
                    // 出错回退到原有缓冲播放
                    try {
                        AudioRX_audiobuffer.push(new Float32Array(msg.data));
                    } catch (_) {}
                }
            };
            rxNode.connect(AudioRX_biquadFilter_node);
        } catch (e) {
            // 回退到 ScriptProcessor
            console.log('Using ScriptProcessor fallback for audio playback');
            const BUFF_SIZE = 256;
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
    })();

    AudioRX_biquadFilter_node.connect(AudioRX_gain_node);
    AudioRX_gain_node.connect(AudioRX_analyser);
    AudioRX_gain_node.connect(AudioRX_context.destination);

    // Initialize visualization functions if needed
    // drawBF();
    // drawRXvol();

    AudioRX_biquadFilter_node.type = "lowshelf";
    // Clamp frequency to valid range for 24kHz sample rate
    AudioRX_biquadFilter_node.frequency.setValueAtTime(12000, AudioRX_context.currentTime);
    AudioRX_biquadFilter_node.gain.setValueAtTime(0, AudioRX_context.currentTime);

    AudioRX_SetGAIN();
}

function AudioRX_SetGAIN(vol = "None") {
    if (vol == "None") {
        volumeRX = 0.8; // Default volume for mobile
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
/**
 * 语音助手 - 本地语音识别与合成
 * 支持Web Speech API和本地模型
 */

// ============================================
// 全局状态管理
// ============================================
const VAState = {
    // 语音识别
    asr: {
        active: false,
        recognizing: false,
        transcript: '',
        confidence: 0,
        recognition: null,
        useLocal: true
    },
    // 语音合成
    tts: {
        active: false,
        speaking: false,
        useLocal: true,
        voices: [],
        selectedVoice: null,
        rate: 1.0
    },
    // PTT控制
    ptt: {
        active: false,
        autoPTT: false,
        delay: 1000
    },
    // 设置
    settings: {
        asrLang: 'zh-CN',
        autoPTT: false,
        pttDelay: 1000
    },
    // 音频可视化
    audioContext: null,
    analyser: null,
    visualizerDataArray: null
};

// ============================================
// 初始化
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    console.log('[VoiceAssistant] 初始化开始...');
    
    initSpeechRecognition();
    initSpeechSynthesis();
    initEventListeners();
    initAudioVisualizer();
    loadSettings();
    
    // 更新频率显示
    updateFrequencyDisplay();
    
    console.log('[VoiceAssistant] 初始化完成');
});

// ============================================
// 语音识别初始化 (Web Speech API)
// ============================================
function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
        console.warn('[VoiceAssistant] 浏览器不支持 Speech Recognition API');
        showToast('您的浏览器不支持语音识别，已切换至手动模式', 'error');
        updateStatus('asr', 'error');
        enableManualInputMode();
        return;
    }
    
    // 检查是否HTTPS（Web Speech API需要HTTPS）
    if (window.location.protocol !== 'https:' && window.location.hostname !== 'localhost') {
        console.warn('[VoiceAssistant] Web Speech API 需要HTTPS连接');
        showToast('语音识别需要HTTPS连接，已切换至手动模式', 'error');
        updateStatus('asr', 'error');
        enableManualInputMode();
        return;
    }
    
    VAState.asr.recognition = new SpeechRecognition();
    VAState.asr.recognition.continuous = true;
    VAState.asr.recognition.interimResults = true;
    VAState.asr.recognition.lang = VAState.settings.asrLang;
    VAState.asr.errorCount = 0;  // 错误计数器
    VAState.asr.lastRestartTime = 0;  // 上次重启时间
    
    VAState.asr.recognition.onstart = function() {
        console.log('[VoiceAssistant] 语音识别已启动');
        VAState.asr.recognizing = true;
        VAState.asr.errorCount = 0;  // 重置错误计数
        updateStatus('asr', 'active');
        document.getElementById('asr-display').innerHTML = '<span class="recognizing">正在聆听电台语音...</span>';
    };
    
    VAState.asr.recognition.onresult = function(event) {
        let finalTranscript = '';
        let interimTranscript = '';
        let maxConfidence = 0;
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            const confidence = event.results[i][0].confidence;
            
            if (event.results[i].isFinal) {
                finalTranscript += transcript;
                maxConfidence = Math.max(maxConfidence, confidence);
            } else {
                interimTranscript += transcript;
            }
        }
        
        // 更新显示
        const display = document.getElementById('asr-display');
        if (finalTranscript) {
            display.innerHTML = `<span class="final-text">${escapeHtml(finalTranscript)}</span>`;
            VAState.asr.transcript = finalTranscript;
            VAState.asr.confidence = maxConfidence;
            
            // 更新置信度
            updateConfidence(maxConfidence);
            
            // 添加到对话历史
            addMessage('received', finalTranscript);
        } else if (interimTranscript) {
            display.innerHTML = `<span class="recognizing">${escapeHtml(interimTranscript)}</span>`;
        }
    };
    
    VAState.asr.recognition.onerror = function(event) {
        console.error('[VoiceAssistant] 语音识别错误:', event.error);
        
        // 增加错误计数
        VAState.asr.errorCount = (VAState.asr.errorCount || 0) + 1;
        
        if (event.error === 'network') {
            // 网络错误 - 这是最常见的问题
            console.warn(`[VoiceAssistant] 网络错误 (${VAState.asr.errorCount}/5)`);
            
            if (VAState.asr.errorCount >= 5) {
                // 连续5次网络错误，切换到手动模式
                showToast('语音识别网络错误，已切换至手动输入模式', 'error');
                updateStatus('asr', 'error');
                VAState.asr.active = false;
                enableManualInputMode();
                return;
            }
            
            // 稍后重试，使用递增延迟
            const delay = Math.min(1000 * VAState.asr.errorCount, 5000);
            setTimeout(() => {
                if (VAState.asr.active) {
                    console.log(`[VoiceAssistant] 尝试重启识别 (延迟 ${delay}ms)`);
                    startRecognition();
                }
            }, delay);
            
        } else if (event.error === 'no-speech') {
            // 无语音输入，这是正常的，立即重启
            if (VAState.asr.active) {
                setTimeout(() => startRecognition(), 200);
            }
        } else if (event.error === 'audio-capture') {
            showToast('无法访问麦克风', 'error');
            updateStatus('asr', 'error');
            enableManualInputMode();
        } else if (event.error === 'not-allowed') {
            showToast('请允许麦克风权限', 'error');
            updateStatus('asr', 'error');
            enableManualInputMode();
        } else if (event.error === 'aborted') {
            // 用户或脚本中止，不处理
            console.log('[VoiceAssistant] 识别已中止');
        } else {
            console.error('[VoiceAssistant] 未知错误:', event.error);
            // 其他错误，短暂延迟后重试
            if (VAState.asr.active && VAState.asr.errorCount < 3) {
                setTimeout(() => startRecognition(), 1000);
            }
        }
    };
    
    VAState.asr.recognition.onend = function() {
        console.log('[VoiceAssistant] 语音识别已停止');
        VAState.asr.recognizing = false;
        
        if (VAState.asr.active && VAState.asr.errorCount < 5) {
            // 短暂延迟后自动重启
            const now = Date.now();
            const timeSinceLastRestart = now - (VAState.asr.lastRestartTime || 0);
            
            // 避免过于频繁的重启（至少间隔500ms）
            const delay = Math.max(100, 500 - timeSinceLastRestart);
            
            setTimeout(() => {
                if (VAState.asr.active) {
                    VAState.asr.lastRestartTime = Date.now();
                    startRecognition();
                }
            }, delay);
        } else if (VAState.asr.errorCount >= 5) {
            updateStatus('asr', 'error');
            enableManualInputMode();
        } else {
            updateStatus('asr', 'inactive');
            document.getElementById('asr-display').innerHTML = '<div class="va-placeholder">语音识别已停止</div>';
        }
    };
    
    // 自动开始识别
    startRecognition();
}

function startRecognition() {
    if (!VAState.asr.recognition || VAState.asr.recognizing) return;
    
    try {
        VAState.asr.active = true;
        VAState.asr.recognition.lang = VAState.settings.asrLang;
        VAState.asr.recognition.start();
    } catch (e) {
        console.error('[VoiceAssistant] 启动语音识别失败:', e);
        
        if (e.name === 'InvalidStateError') {
            // 可能已经在运行，忽略
            console.log('[VoiceAssistant] 识别已在运行');
        } else {
            VAState.asr.errorCount = (VAState.asr.errorCount || 0) + 1;
            if (VAState.asr.errorCount >= 3) {
                enableManualInputMode();
            }
        }
    }
}

function stopRecognition() {
    VAState.asr.active = false;
    if (VAState.asr.recognition && VAState.asr.recognizing) {
        try {
            VAState.asr.recognition.stop();
        } catch (e) {
            console.log('[VoiceAssistant] 停止识别失败:', e);
        }
    }
}

// ============================================
// 手动输入模式（语音识别不可用时的降级方案）
// ============================================
function enableManualInputMode() {
    console.log('[VoiceAssistant] 启用手动输入模式');
    VAState.asr.manualMode = true;
    
    const display = document.getElementById('asr-display');
    display.innerHTML = `
        <div class="va-placeholder" style="text-align: center; padding: 20px;">
            <div style="font-size: 24px; margin-bottom: 10px;">✏️</div>
            <div>语音识别不可用</div>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 8px;">
                请使用下方输入框手动输入接收到的内容
            </div>
        </div>
    `;
    
    // 添加手动输入按钮到识别区
    const section = document.querySelector('.va-recognition-section');
    let manualBtn = document.getElementById('manual-asr-btn');
    
    if (!manualBtn) {
        manualBtn = document.createElement('button');
        manualBtn.id = 'manual-asr-btn';
        manualBtn.className = 'va-action-btn';
        manualBtn.style.marginTop = '10px';
        manualBtn.style.width = '100%';
        manualBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
            手动输入接收内容
        `;
        manualBtn.addEventListener('click', showManualInputDialog);
        section.appendChild(manualBtn);
    }
}

function showManualInputDialog() {
    const dialog = document.createElement('div');
    dialog.className = 'va-modal active';
    dialog.innerHTML = `
        <div class="va-modal-content" style="max-height: 50vh;">
            <div class="va-modal-header">
                <h3>输入接收到的内容</h3>
                <button class="va-modal-close" onclick="this.closest('.va-modal').remove()">&times;</button>
            </div>
            <div style="padding: 16px;">
                <textarea id="manual-input-text" class="va-textarea" 
                    placeholder="请输入从电台接收到的语音内容..." 
                    rows="4" style="margin-bottom: 12px;"></textarea>
                <button id="confirm-manual-input" class="va-action-btn" style="width: 100%;">
                    添加到对话记录
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(dialog);
    
    // 聚焦输入框
    setTimeout(() => {
        document.getElementById('manual-input-text').focus();
    }, 100);
    
    // 确认按钮事件
    dialog.querySelector('#confirm-manual-input').addEventListener('click', () => {
        const text = document.getElementById('manual-input-text').value.trim();
        if (text) {
            document.getElementById('asr-display').innerHTML = `<span class="final-text">${escapeHtml(text)}</span>`;
            addMessage('received', text);
            updateConfidence(1.0);  // 手动输入置信度为100%
            dialog.remove();
        }
    });
    
    // 点击背景关闭
    dialog.addEventListener('click', (e) => {
        if (e.target === dialog) {
            dialog.remove();
        }
    });
}

// ============================================
// 语音合成初始化 (Web Speech API)
// ============================================
function initSpeechSynthesis() {
    if (!window.speechSynthesis) {
        console.warn('[VoiceAssistant] 浏览器不支持 Speech Synthesis API');
        showToast('您的浏览器不支持语音合成', 'error');
        updateStatus('tts', 'error');
        return;
    }
    
    // 加载可用语音
    const loadVoices = () => {
        VAState.tts.voices = window.speechSynthesis.getVoices();
        console.log(`[VoiceAssistant] 加载了 ${VAState.tts.voices.length} 个语音`);
        
        // 填充语音选择下拉框
        const voiceSelect = document.getElementById('tts-voice-select');
        voiceSelect.innerHTML = '<option value="">默认语音</option>';
        
        VAState.tts.voices.forEach((voice, index) => {
            if (voice.lang.startsWith('zh') || voice.lang.startsWith('en')) {
                const option = document.createElement('option');
                option.value = index;
                option.textContent = `${voice.name} (${voice.lang})`;
                voiceSelect.appendChild(option);
            }
        });
    };
    
    // Chrome需要等待voiceschanged事件
    if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = loadVoices;
    }
    
    loadVoices();
    updateStatus('tts', 'active');
}

function speak(text, callback) {
    if (!window.speechSynthesis) {
        showToast('语音合成不可用', 'error');
        return;
    }
    
    // 取消之前的语音
    window.speechSynthesis.cancel();
    
    // 先启动PTT，给系统一点准备时间
    console.log('[VoiceAssistant] 准备语音合成，先启动PTT...');
    
    // 通过parent或postMessage启动PTT
    let pttStarted = false;
    if (window.parent !== window && window.parent.startPTT) {
        window.parent.startPTT();
        pttStarted = true;
    } else {
        // 尝试通过postMessage
        window.parent.postMessage({ type: 'PTT_START' }, '*');
        pttStarted = true;
    }
    
    // 延迟后开始播放语音，确保PTT已经稳定
    const startDelay = VAState.settings.pttDelay || 500;
    
    setTimeout(() => {
        const utterance = new SpeechSynthesisUtterance(text);
        
        // 设置语音
        const voiceSelect = document.getElementById('tts-voice-select');
        if (voiceSelect.value && VAState.tts.voices[voiceSelect.value]) {
            utterance.voice = VAState.tts.voices[voiceSelect.value];
        }
        
        // 设置语速 - 业余无线电通常较慢更清晰
        const speedSelect = document.getElementById('tts-speed');
        utterance.rate = parseFloat(speedSelect.value) * 0.9;  // 稍微慢一点
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        
        utterance.onstart = function() {
            console.log('[VoiceAssistant] 语音合成开始');
            VAState.tts.speaking = true;
            updateStatus('tts', 'processing');
            document.getElementById('stop-tts-btn').disabled = false;
            document.getElementById('play-tts-btn').disabled = true;
        };
        
        utterance.onend = function() {
            console.log('[VoiceAssistant] 语音合成结束');
            VAState.tts.speaking = false;
            updateStatus('tts', 'active');
            document.getElementById('stop-tts-btn').disabled = true;
            document.getElementById('play-tts-btn').disabled = false;
            
            // 播放结束后延迟停止PTT，确保音频完全发送
            setTimeout(() => {
                if (window.parent !== window && window.parent.stopPTT) {
                    window.parent.stopPTT();
                } else {
                    window.parent.postMessage({ type: 'PTT_STOP' }, '*');
                }
                
                // 将发送的消息添加到对话历史
                addMessage('sent', text);
                
                // 清空输入框
                document.getElementById('reply-text').value = '';
                
                if (callback) callback();
            }, 300);
        };
        
        utterance.onerror = function(event) {
            console.error('[VoiceAssistant] 语音合成错误:', event.error);
            VAState.tts.speaking = false;
            updateStatus('tts', 'error');
            document.getElementById('stop-tts-btn').disabled = true;
            document.getElementById('play-tts-btn').disabled = false;
            
            // 出错时也要停止PTT
            setTimeout(() => {
                if (window.parent !== window && window.parent.stopPTT) {
                    window.parent.stopPTT();
                } else {
                    window.parent.postMessage({ type: 'PTT_STOP' }, '*');
                }
            }, 100);
            
            if (event.error !== 'canceled') {
                showToast('语音合成出错: ' + event.error, 'error');
            }
        };
        
        window.speechSynthesis.speak(utterance);
        
    }, startDelay);
}

/**
 * 试听语音（不启动PTT）
 */
function playPreview(text) {
    if (!window.speechSynthesis) {
        showToast('语音合成不可用', 'error');
        return;
    }
    
    // 取消之前的语音
    window.speechSynthesis.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    
    // 设置语音
    const voiceSelect = document.getElementById('tts-voice-select');
    if (voiceSelect.value && VAState.tts.voices[voiceSelect.value]) {
        utterance.voice = VAState.tts.voices[voiceSelect.value];
    }
    
    // 设置语速
    const speedSelect = document.getElementById('tts-speed');
    utterance.rate = parseFloat(speedSelect.value) * 0.9;
    utterance.pitch = 1.0;
    utterance.volume = 0.8;  // 试听音量稍小
    
    utterance.onstart = function() {
        console.log('[VoiceAssistant] 试听开始');
        VAState.tts.speaking = true;
        updateStatus('tts', 'processing');
        document.getElementById('stop-tts-btn').disabled = false;
        document.getElementById('play-tts-btn').disabled = true;
    };
    
    utterance.onend = function() {
        console.log('[VoiceAssistant] 试听结束');
        VAState.tts.speaking = false;
        updateStatus('tts', 'active');
        document.getElementById('stop-tts-btn').disabled = true;
        document.getElementById('play-tts-btn').disabled = false;
    };
    
    utterance.onerror = function(event) {
        console.error('[VoiceAssistant] 试听错误:', event.error);
        VAState.tts.speaking = false;
        updateStatus('tts', 'error');
        document.getElementById('stop-tts-btn').disabled = true;
        document.getElementById('play-tts-btn').disabled = false;
    };
    
    window.speechSynthesis.speak(utterance);
}

function stopSpeaking() {
    if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
    }
    VAState.tts.speaking = false;
    
    if (typeof window.parent !== 'undefined' && window.parent.stopPTT) {
        window.parent.stopPTT();
    }
}

// ============================================
// 音频可视化
// ============================================
function initAudioVisualizer() {
    const canvas = document.getElementById('audio-visualizer');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // 尝试获取音频输入进行可视化
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                VAState.audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const source = VAState.audioContext.createMediaStreamSource(stream);
                VAState.analyser = VAState.audioContext.createAnalyser();
                VAState.analyser.fftSize = 256;
                source.connect(VAState.analyser);
                
                const bufferLength = VAState.analyser.frequencyBinCount;
                VAState.visualizerDataArray = new Uint8Array(bufferLength);
                
                drawVisualizer();
            })
            .catch(err => {
                console.log('[VoiceAssistant] 无法获取麦克风:', err);
                // 绘制静态波形
                drawStaticVisualizer();
            });
    } else {
        drawStaticVisualizer();
    }
    
    function drawVisualizer() {
        if (!VAState.analyser) return;
        
        requestAnimationFrame(drawVisualizer);
        
        VAState.analyser.getByteFrequencyData(VAState.visualizerDataArray);
        
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        const barWidth = (canvas.width / VAState.visualizerDataArray.length) * 2.5;
        let barHeight;
        let x = 0;
        
        for (let i = 0; i < VAState.visualizerDataArray.length; i++) {
            barHeight = (VAState.visualizerDataArray[i] / 255) * canvas.height;
            
            const gradient = ctx.createLinearGradient(0, canvas.height - barHeight, 0, canvas.height);
            gradient.addColorStop(0, '#00d4ff');
            gradient.addColorStop(1, '#0099cc');
            
            ctx.fillStyle = gradient;
            ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
            
            x += barWidth + 1;
        }
    }
    
    function drawStaticVisualizer() {
        let offset = 0;
        
        function draw() {
            requestAnimationFrame(draw);
            
            ctx.fillStyle = '#1a1a1a';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            ctx.beginPath();
            ctx.strokeStyle = '#00d4ff';
            ctx.lineWidth = 2;
            
            for (let x = 0; x < canvas.width; x++) {
                const y = canvas.height / 2 + 
                    Math.sin((x + offset) * 0.05) * 10 +
                    Math.sin((x + offset) * 0.1) * 5;
                
                if (x === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            }
            
            ctx.stroke();
            offset += 2;
        }
        
        draw();
    }
}

// ============================================
// 事件监听
// ============================================
function initEventListeners() {
    // 返回按钮
    document.getElementById('back-btn').addEventListener('click', () => {
        window.location.href = 'mobile_modern.html';
    });
    
    // 设置按钮
    document.getElementById('settings-btn').addEventListener('click', () => {
        document.getElementById('settings-modal').classList.add('active');
    });
    
    // 关闭设置
    document.getElementById('close-settings').addEventListener('click', () => {
        document.getElementById('settings-modal').classList.remove('active');
    });
    
    // 清空识别
    document.getElementById('clear-asr-btn').addEventListener('click', () => {
        document.getElementById('asr-display').innerHTML = '<div class="va-placeholder">等待接收语音...</div>';
        VAState.asr.transcript = '';
        updateConfidence(0);
    });
    
    // 清空对话
    document.getElementById('clear-chat-btn').addEventListener('click', () => {
        document.getElementById('chat-history').innerHTML = '';
    });
    
    // 快捷回复
    document.getElementById('quick-reply-btn').addEventListener('click', () => {
        document.getElementById('quick-reply-modal').classList.add('active');
    });
    
    // 关闭快捷回复
    document.getElementById('close-quick-reply').addEventListener('click', () => {
        document.getElementById('quick-reply-modal').classList.remove('active');
    });
    
    // 快捷回复项点击
    document.querySelectorAll('.va-quick-reply-item').forEach(item => {
        item.addEventListener('click', () => {
            const text = item.dataset.text;
            document.getElementById('reply-text').value = text;
            document.getElementById('quick-reply-modal').classList.remove('active');
            document.getElementById('play-tts-btn').disabled = false;
        });
    });
    
    // 语音输入按钮
    document.getElementById('voice-input-btn').addEventListener('click', () => {
        // 临时停止接收识别，使用输入框的语音识别
        if ('webkitSpeechRecognition' in window) {
            const recognition = new webkitSpeechRecognition();
            recognition.lang = VAState.settings.asrLang;
            recognition.interimResults = true;
            
            recognition.onresult = (event) => {
                let transcript = '';
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    transcript += event.results[i][0].transcript;
                }
                document.getElementById('reply-text').value = transcript;
                document.getElementById('play-tts-btn').disabled = false;
            };
            
            recognition.start();
            showToast('请说出回复内容...');
        } else {
            showToast('您的浏览器不支持语音输入', 'error');
        }
    });
    
    // 输入框变化
    document.getElementById('reply-text').addEventListener('input', (e) => {
        document.getElementById('play-tts-btn').disabled = !e.target.value.trim();
    });
    
    // 试听按钮 - 只播放声音，不发射
    document.getElementById('play-tts-btn').addEventListener('click', () => {
        const text = document.getElementById('reply-text').value.trim();
        if (text) {
            playPreview(text);
        }
    });
    
    // 停止按钮
    document.getElementById('stop-tts-btn').addEventListener('click', stopSpeaking);
    
    // PTT按钮
    const pttBtn = document.getElementById('ptt-btn');
    
    pttBtn.addEventListener('mousedown', startPTT);
    pttBtn.addEventListener('mouseup', stopPTT);
    pttBtn.addEventListener('mouseleave', stopPTT);
    
    pttBtn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        startPTT();
    });
    pttBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        stopPTT();
    });
    
    // 设置变更
    document.getElementById('setting-local-asr').addEventListener('change', (e) => {
        VAState.asr.useLocal = e.target.checked;
        saveSettings();
    });
    
    document.getElementById('setting-local-tts').addEventListener('change', (e) => {
        VAState.tts.useLocal = e.target.checked;
        saveSettings();
    });
    
    document.getElementById('setting-auto-ptt').addEventListener('change', (e) => {
        VAState.settings.autoPTT = e.target.checked;
        saveSettings();
    });
    
    document.getElementById('setting-asr-lang').addEventListener('change', (e) => {
        VAState.settings.asrLang = e.target.value;
        saveSettings();
        // 重启识别以应用新语言
        stopRecognition();
        setTimeout(startRecognition, 200);
    });
    
    document.getElementById('setting-ptt-delay').addEventListener('change', (e) => {
        VAState.settings.pttDelay = parseInt(e.target.value);
        saveSettings();
    });
    
    // 点击模态框背景关闭
    document.querySelectorAll('.va-modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });
}

// ============================================
// PTT控制
// ============================================
function startPTT() {
    const pttBtn = document.getElementById('ptt-btn');
    if (pttBtn.classList.contains('active')) return;  // 已经在发射中
    
    pttBtn.classList.add('active');
    VAState.ptt.active = true;
    updateStatus('ptt', 'active');
    
    // 获取回复文本
    const text = document.getElementById('reply-text').value.trim();
    
    if (text) {
        // 有文本内容，播放语音并发射
        console.log('[VoiceAssistant] PTT按下，播放语音:', text.substring(0, 20) + '...');
        speak(text);
    } else {
        // 没有文本，只启动PTT（可能是手动讲话）
        console.log('[VoiceAssistant] PTT按下，无文本内容');
        if (window.parent !== window && window.parent.startPTT) {
            window.parent.startPTT();
        } else {
            window.parent.postMessage({ type: 'PTT_START' }, '*');
        }
        showToast('PTT已启动，请讲话...');
    }
}

function stopPTT() {
    const pttBtn = document.getElementById('ptt-btn');
    if (!pttBtn.classList.contains('active')) return;  // 已经停止
    
    pttBtn.classList.remove('active');
    VAState.ptt.active = false;
    updateStatus('ptt', 'inactive');
    
    console.log('[VoiceAssistant] PTT松开，停止发射');
    
    // 停止语音合成
    if (VAState.tts.speaking) {
        stopSpeaking();
    }
    
    // 停止PTT发射
    if (window.parent !== window && window.parent.stopPTT) {
        window.parent.stopPTT();
    } else {
        window.parent.postMessage({ type: 'PTT_STOP' }, '*');
    }
}

// ============================================
// UI更新函数
// ============================================
function updateStatus(type, state) {
    const statusEl = document.getElementById(`status-${type}`);
    if (!statusEl) return;
    
    statusEl.classList.remove('active', 'error', 'processing', 'inactive');
    
    switch (state) {
        case 'active':
            statusEl.classList.add('active');
            break;
        case 'error':
            statusEl.classList.add('error');
            break;
        case 'processing':
            statusEl.classList.add('processing');
            break;
        default:
            statusEl.classList.add('inactive');
    }
}

function updateConfidence(value) {
    const percentage = Math.round(value * 100);
    document.getElementById('confidence-fill').style.width = `${percentage}%`;
    document.getElementById('confidence-value').textContent = `${percentage}%`;
}

function addMessage(type, content) {
    const chatHistory = document.getElementById('chat-history');
    
    const message = document.createElement('div');
    message.className = `va-message ${type}`;
    
    const time = new Date().toLocaleTimeString('zh-CN', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    const avatarText = type === 'received' ? '收' : '发';
    
    message.innerHTML = `
        <div class="va-message-header">
            <div class="va-message-avatar">${avatarText}</div>
            <span>${type === 'received' ? '接收' : '发送'}</span>
        </div>
        <div class="va-message-content">${escapeHtml(content)}</div>
        <div class="va-message-time">${time}</div>
    `;
    
    chatHistory.appendChild(message);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function updateFrequencyDisplay() {
    // 尝试从URL参数或localStorage获取频率
    const urlParams = new URLSearchParams(window.location.search);
    const freq = urlParams.get('freq') || localStorage.getItem('currentFreq') || '7053.0';
    document.getElementById('current-freq').textContent = `${freq} kHz`;
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('va-toast');
    toast.textContent = message;
    toast.className = `va-toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// ============================================
// 设置管理
// ============================================
function loadSettings() {
    try {
        const saved = localStorage.getItem('voiceAssistantSettings');
        if (saved) {
            const settings = JSON.parse(saved);
            VAState.settings = { ...VAState.settings, ...settings };
            
            // 应用设置到UI
            document.getElementById('setting-asr-lang').value = VAState.settings.asrLang;
            document.getElementById('setting-auto-ptt').checked = VAState.settings.autoPTT;
            document.getElementById('setting-ptt-delay').value = VAState.settings.pttDelay;
        }
    } catch (e) {
        console.error('[VoiceAssistant] 加载设置失败:', e);
    }
}

function saveSettings() {
    try {
        localStorage.setItem('voiceAssistantSettings', JSON.stringify(VAState.settings));
    } catch (e) {
        console.error('[VoiceAssistant] 保存设置失败:', e);
    }
}

// ============================================
// 工具函数
// ============================================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 监听来自父窗口的消息
window.addEventListener('message', (event) => {
    if (event.data.type === 'FREQ_UPDATE') {
        document.getElementById('current-freq').textContent = `${event.data.freq} kHz`;
    }
});

// 页面可见性变化处理
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // 页面隐藏时暂停识别
        stopRecognition();
    } else {
        // 页面显示时恢复识别
        startRecognition();
    }
});

// 页面卸载时清理
window.addEventListener('beforeunload', () => {
    stopRecognition();
    stopSpeaking();
});

// 防止页面滚动弹跳
document.addEventListener('touchmove', (e) => {
    if (e.target.closest('.va-chat-history') || e.target.closest('.va-recognition-display')) {
        return;
    }
    e.preventDefault();
}, { passive: false });

console.log('[VoiceAssistant] 脚本加载完成');
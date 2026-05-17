////////////////////////////////////////////////////////////
// TX Audio EQ Module - tx_audio_eq.js
// Extracted from controls.js
//
// TX EQ (Equalizer) system optimized for shortwave voice
// communication. Provides bandpass filtering, anti-alias
// lowpass, preamp gain, and preset management (DEFAULT,
// MEDIUM, STRONG, RAGCHEW).
//
// Global variables (AudioTX_eqLow, etc.) are intentionally
// kept global as they are referenced by MediaHandler.callback
// in controls.js.
//
// Dependencies: setCookie() and getCookie() from controls.js
// must be loaded before this module is used.
////////////////////////////////////////////////////////////

// TX EQ 节点 - 针对短波通信优化 (100Hz - 2700Hz 语音频段)
var AudioTX_eqLow = null;      // 低频衰减 @ 100Hz (切除超低频噪声)
var AudioTX_eqMid = null;      // 中频增强 @ 1500Hz (语音中心频率)
var AudioTX_eqHigh = null;     // 高频衰减 @ 2700Hz (切除高频噪声)
var AudioTX_antiAlias = null;  // 抗混叠低通滤波器第一级
var AudioTX_antiAlias2 = null; // 抗混叠低通滤波器第二级 (更陡峭滚降)
var AudioTX_preamp = null;     // TX 前置放大器（实质性提升发射功率）

// RagChew 专用节点
var AudioTX_highCut = null;    // 高切低通 @ 3kHz
var AudioTX_midCut = null;     // 中低频衰减 @ 500Hz
var AudioTX_presence = null;   // 高频存在感 @ 2.4kHz
var AudioTX_compressor = null; // 动态压缩器
var AudioTX_noiseGate = null;  // 噪声门（gain 节点）
var isRagchewMode = false;     // 当前是否为 RagChew 模式

// TX EQ 预设 - 针对短波通信 + 手机麦克风补偿优化
// 参数说明：
//   low:  低频增强 @ 350Hz (dB)，正值增强语音厚度，补偿手机麦克风低频不足
//   mid:  中频增强 @ 1500Hz (dB)，正值增强语音清晰度
//   high: 高频衰减 @ 2700Hz (dB)，负值衰减，消除尖锐音
// 短波通信核心频段：200Hz - 2700Hz
var TX_EQ_PRESETS = {
    'DEFAULT': {
        name: '默认',
        low: 6, mid: 8, high: -6,
        desc: '基础增强：适度提升发射功率'
    },
    'MEDIUM': {
        name: '中',
        low: 9,      // 适度增强低频厚度
        mid: 10,     // 中频增强，提高清晰度
        high: -12,   // 适度高频衰减
        desc: '适中调节：增强厚度与清晰度'
    },
    'STRONG': {
        name: '强',
        low: 12,     // 强力增强低频，补偿手机麦克风
        mid: 12,     // 强调中频
        high: -18,   // 强力高频衰减，消除尖锐音
        desc: '最大发射功率：iPhone/手机专用'
    },
    'RAGCHEW': {
        name: 'RagChew',
        low: 0, mid: 0, high: 0,
        lowCut: 150,    // 低切频率 Hz
        midCutFreq: 500, midCutGain: -2,  // 400-600Hz 浊音区衰减
        presenceFreq: 2400, presenceGain: 3,  // 2.4kHz 清晰度提升
        highCut: 3000,  // 高切频率 Hz
        desc: '本地强信号：温暖自然，平稳舒适，纯净背景'
    }
};

var currentTX_EQ_Preset = 'DEFAULT';

// 初始化 TX EQ
function initTX_EQ(context) {
    if (!context) return;

    // ========== TX 前置放大器 ==========
    // 实质性提升发射功率，补偿手机麦克风输出电平低的问题
    AudioTX_preamp = context.createGain();
    AudioTX_preamp.gain.setValueAtTime(3.0, context.currentTime);  // +9.5dB 前置增益

    // ========== 轻度高切，保留语音完整性 ==========
    AudioTX_antiAlias = context.createBiquadFilter();
    AudioTX_antiAlias.type = 'lowpass';
    AudioTX_antiAlias.frequency.setValueAtTime(4500, context.currentTime);
    AudioTX_antiAlias.Q.setValueAtTime(0.707, context.currentTime);

    // 第二级：进一步限制超高频
    AudioTX_antiAlias2 = context.createBiquadFilter();
    AudioTX_antiAlias2.type = 'lowpass';
    AudioTX_antiAlias2.frequency.setValueAtTime(4500, context.currentTime);
    AudioTX_antiAlias2.Q.setValueAtTime(0.707, context.currentTime);

    // 创建三个BiquadFilter节点 - 针对短波通信优化
    AudioTX_eqLow = context.createBiquadFilter();
    AudioTX_eqMid = context.createBiquadFilter();
    AudioTX_eqHigh = context.createBiquadFilter();

    // ========== 短波通信语音滤波策略 ==========
    // 核心频段：200Hz - 2700Hz (SSB 语音优化)
    // 200-500Hz: 语音厚度/温暖感 (手机麦克风弱区，需增强)
    // 800-2200Hz: 语音清晰度 (保持/适度增强)
    // >2700Hz: 高频噪声/尖锐音 (衰减)

    // 低频增强 - peaking @ 350Hz (补偿手机麦克风低频不足)
    // low 参数: 增益量 (dB)，正值增强语音厚度
    AudioTX_eqLow.type = 'peaking';
    AudioTX_eqLow.frequency.setValueAtTime(350, context.currentTime);
    AudioTX_eqLow.Q.setValueAtTime(1.0, context.currentTime); // 宽Q值覆盖200-500Hz
    AudioTX_eqLow.gain.setValueAtTime(0, context.currentTime);

    // 中频增强 - 语音中心频率 (1500Hz)
    // mid 参数: 增益量 (dB)，正值增强语音清晰度
    AudioTX_eqMid.type = 'peaking';
    AudioTX_eqMid.frequency.setValueAtTime(1500, context.currentTime);
    AudioTX_eqMid.Q.setValueAtTime(1.4, context.currentTime); // 较宽的 Q 值，覆盖 800-2200Hz
    AudioTX_eqMid.gain.setValueAtTime(0, context.currentTime);

    // 高频衰减 - highshelf @ 2700Hz
    // high 参数: 衰减量 (dB)，0 = 不衰减，-20 = 切除高频噪声
    AudioTX_eqHigh.type = 'highshelf';
    AudioTX_eqHigh.frequency.setValueAtTime(2700, context.currentTime);
    AudioTX_eqHigh.gain.setValueAtTime(0, context.currentTime);

    // ========== RagChew 专用节点 ==========
    AudioTX_highCut = context.createBiquadFilter();
    AudioTX_highCut.type = 'lowpass';
    AudioTX_highCut.frequency.setValueAtTime(3000, context.currentTime);
    AudioTX_highCut.Q.setValueAtTime(0.707, context.currentTime);

    AudioTX_midCut = context.createBiquadFilter();
    AudioTX_midCut.type = 'peaking';
    AudioTX_midCut.frequency.setValueAtTime(500, context.currentTime);
    AudioTX_midCut.Q.setValueAtTime(1.0, context.currentTime);
    AudioTX_midCut.gain.setValueAtTime(0, context.currentTime);

    AudioTX_presence = context.createBiquadFilter();
    AudioTX_presence.type = 'peaking';
    AudioTX_presence.frequency.setValueAtTime(2400, context.currentTime);
    AudioTX_presence.Q.setValueAtTime(1.4, context.currentTime);
    AudioTX_presence.gain.setValueAtTime(0, context.currentTime);

    AudioTX_compressor = context.createDynamicsCompressor();
    AudioTX_compressor.threshold.setValueAtTime(-24, context.currentTime);
    AudioTX_compressor.knee.setValueAtTime(30, context.currentTime);
    AudioTX_compressor.ratio.setValueAtTime(3, context.currentTime);
    AudioTX_compressor.attack.setValueAtTime(0.003, context.currentTime);
    AudioTX_compressor.release.setValueAtTime(0.25, context.currentTime);

    AudioTX_noiseGate = context.createGain();
    AudioTX_noiseGate.gain.setValueAtTime(1, context.currentTime);

    console.log('✅ TX EQ 初始化完成 (短波语音 100-2700Hz 带通 + 抗混叠 6kHz + RagChew 节点)');
}

// 应用 TX EQ 预设
function setTX_EQ_Preset(presetName) {
    var preset = TX_EQ_PRESETS[presetName];
    if (!preset) {
        console.warn('TX EQ 预设不存在:', presetName);
        return;
    }

    currentTX_EQ_Preset = presetName;

    // 检查核心EQ节点是否存在
    if (!AudioTX_eqLow || !AudioTX_eqMid || !AudioTX_eqHigh || !AudioTX_antiAlias || !AudioTX_antiAlias2) {
        console.warn('TX EQ 节点未初始化，跳过预设:', presetName);
        return;
    }

    // 获取AudioContext
    var ctx = AudioTX_eqLow.context;
    if (!ctx) {
        console.warn('AudioContext 不存在，跳过预设:', presetName);
        return;
    }

    if (presetName === 'RAGCHEW') {
        // ====== RagChew 模式 ======
        isRagchewMode = true;

        // 标准3段EQ设为直通
        AudioTX_eqLow.gain.setValueAtTime(0, ctx.currentTime);
        AudioTX_eqMid.gain.setValueAtTime(0, ctx.currentTime);
        AudioTX_eqHigh.gain.setValueAtTime(0, ctx.currentTime);

        // antiAlias / antiAlias2 设为直通（极高截止频率的低通 = 直通）
        AudioTX_antiAlias.type = 'lowpass';
        AudioTX_antiAlias.frequency.setValueAtTime(22000, ctx.currentTime);
        AudioTX_antiAlias.Q.setValueAtTime(0.707, ctx.currentTime);
        AudioTX_antiAlias2.type = 'lowpass';
        AudioTX_antiAlias2.frequency.setValueAtTime(22000, ctx.currentTime);
        AudioTX_antiAlias2.Q.setValueAtTime(0.707, ctx.currentTime);

        // 低切 150Hz — 使用 AudioTX_highCut 节点（不动态改变 filter type）
        if (AudioTX_highCut) {
            AudioTX_highCut.type = 'highpass';
            AudioTX_highCut.frequency.setValueAtTime(preset.lowCut, ctx.currentTime);
            AudioTX_highCut.Q.setValueAtTime(0.707, ctx.currentTime);
            AudioTX_highCut.gain.setValueAtTime(0, ctx.currentTime);
        }

        // 中低频衰减 500Hz -2dB
        if (AudioTX_midCut) {
            AudioTX_midCut.gain.setValueAtTime(preset.midCutGain, ctx.currentTime);
            AudioTX_midCut.frequency.setValueAtTime(preset.midCutFreq, ctx.currentTime);
        }

        // 高频增强 2.4kHz +3dB (Presence)
        if (AudioTX_presence) {
            AudioTX_presence.gain.setValueAtTime(preset.presenceGain, ctx.currentTime);
            AudioTX_presence.frequency.setValueAtTime(preset.presenceFreq, ctx.currentTime);
        }

        // 高切 3kHz — 在 presence 之后再加一级低通
        // 使用 AudioTX_highCut 串联 antiAlias2 实现: highCut(highpass @ 150) → midCut → presence → antiAlias2(lowpass @ 3k)

        // 压缩器: Ratio 3:1, 温和压缩
        if (AudioTX_compressor) {
            AudioTX_compressor.threshold.setValueAtTime(-24, ctx.currentTime);
            AudioTX_compressor.knee.setValueAtTime(30, ctx.currentTime);
            AudioTX_compressor.ratio.setValueAtTime(3, ctx.currentTime);
            AudioTX_compressor.attack.setValueAtTime(0.003, ctx.currentTime);
            AudioTX_compressor.release.setValueAtTime(0.250, ctx.currentTime);
        }

        // 噪声门
        if (AudioTX_noiseGate) {
            AudioTX_noiseGate.gain.setValueAtTime(1, ctx.currentTime);
        }

        console.log('🎛️ TX EQ RagChew: 低切=' + preset.lowCut + 'Hz, 500Hz=' + preset.midCutGain + 'dB, 2.4kHz=' + preset.presenceGain + 'dB, 高切=' + preset.highCut + 'Hz, 压缩比=3:1');
    } else {
        // ====== 标准模式 ======
        isRagchewMode = false;

        // 恢复 antiAlias / antiAlias2 为原始低通
        AudioTX_antiAlias.type = 'lowpass';
        AudioTX_antiAlias.frequency.setValueAtTime(4500, ctx.currentTime);
        AudioTX_antiAlias.Q.setValueAtTime(0.707, ctx.currentTime);
        AudioTX_antiAlias2.type = 'lowpass';
        AudioTX_antiAlias2.frequency.setValueAtTime(4500, ctx.currentTime);
        AudioTX_antiAlias2.Q.setValueAtTime(0.707, ctx.currentTime);

        // RagChew 专用滤波器直通
        if (AudioTX_highCut) {
            AudioTX_highCut.type = 'peaking';
            AudioTX_highCut.frequency.setValueAtTime(1000, ctx.currentTime);
            AudioTX_highCut.Q.setValueAtTime(0.5, ctx.currentTime);
            AudioTX_highCut.gain.setValueAtTime(0, ctx.currentTime);
        }
        if (AudioTX_midCut) AudioTX_midCut.gain.setValueAtTime(0, ctx.currentTime);
        if (AudioTX_presence) AudioTX_presence.gain.setValueAtTime(0, ctx.currentTime);

        // 应用标准3段EQ
        AudioTX_eqLow.gain.setValueAtTime(preset.low, ctx.currentTime);
        AudioTX_eqMid.gain.setValueAtTime(preset.mid, ctx.currentTime);
        AudioTX_eqHigh.gain.setValueAtTime(preset.high, ctx.currentTime);

        console.log('🎛️ TX EQ 预设:', preset.name, '- 低频:', preset.low, 'dB, 中频:', preset.mid, 'dB, 高频:', preset.high, 'dB');
    }

    // 保存到Cookie
    if (typeof setCookie === 'function') {
        setCookie('TX_EQ_Preset', presetName, 180);
    }
}

// 获取当前TX EQ预设
function getTX_EQ_Preset() {
    return currentTX_EQ_Preset;
}

// 获取所有TX EQ预设
function getTX_EQ_Presets() {
    return TX_EQ_PRESETS;
}

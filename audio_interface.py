#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cross-platform audio interface using PyAudio
Replaces the ALSA-specific implementation in the original code

支持 Opus 端到端编解码:
- TX: 前端 Opus 编码 → 后端 Opus 解码 → 电台
- RX: 电台 → 后端 Opus 编码 → 前端 Opus 解码

支持 RNNoise 神经网络降噪:
- RX: 电台 → RNNoise 降噪 → Opus/Int16 编码 → 前端

支持 WDSP 数字信号处理:
- RX: 电台 → WDSP(NR2/NB/ANF/AGC) → Opus/Int16 编码 → 前端
- WDSP 提供专业的业余无线电音频处理
"""

import pyaudio
import threading
import queue
import time
import gc
import numpy as np
import os
import subprocess
import logging
from datetime import datetime
from opus.decoder import Decoder as OpusDecoder
from opus.encoder import Encoder as OpusEncoder

# Module logger (F4 fix: `logger` was referenced but never defined,
# causing a NameError inside the recording lock that silently defeated
# the RECORDING_MAX_CHUNKS growth guard).
logger = logging.getLogger(__name__)

# RNNoise 可选导入（需要 pip install pyrnnoise）
RNNOISE_AVAILABLE = False
RNNoise = None
try:
    from pyrnnoise import RNNoise
    RNNOISE_AVAILABLE = True
    print("✅ RNNoise 神经网络降噪可用")
except ImportError:
    print("⚠️ RNNoise 不可用，如需降噪功能请运行: pip install pyrnnoise")

# WDSP 可选导入
WDSP_AVAILABLE = False
WDSPProcessor = None
try:
    from wdsp_wrapper import WDSPProcessor, WDSPMode, WDSPAGCMode, WDSPMeterType, WDSP_AVAILABLE as WDSP_LIB_AVAILABLE
    WDSP_AVAILABLE = WDSP_LIB_AVAILABLE
    if WDSP_AVAILABLE:
        print("✅ WDSP 数字信号处理库可用")
except ImportError as e:
    print(f"⚠️ WDSP 不可用: {e}")
    print("   如需 WDSP 功能，请先编译安装: cd /tmp && git clone https://github.com/g0orx/wdsp.git && cd wdsp && make")


def soft_peak_limiter(x, knee=0.9, ceiling=0.98, ratio=2.0):
    """软膝峰值限幅器。

    低于 knee 时直通（不引入任何失真）；knee~ceiling 之间按 ratio 压缩；
    超过则硬切到 ceiling。替代旧的全范围 tanh 软削波——tanh 会对正常语音电平
    施加持续非线性压缩，本函数只在峰值接近满幅时才介入。
    """
    x = np.asarray(x, dtype=np.float32)
    if ratio <= 1.0:
        return np.clip(x, -ceiling, ceiling)
    ax = np.abs(x)
    over = ax - knee
    # 仅在超过 knee 的部分减去压缩量 (1 - 1/ratio)；低于 knee 完全直通
    reduction = np.where(over > 0, over * (1.0 - 1.0 / ratio), 0.0)
    out_ax = np.minimum(ax - reduction, ceiling)
    return np.sign(x) * out_ax


class _StatefulDecimator:
    """有状态 48k→16k 降采样（窗口化sinc低通 + 精确抽取）。

    用 FIR 滤波 + 跨块状态实现连续滤波，避免按块独立 resample 在块边界产生
    瞬态/咔哒声。抽取相位跨调用连续，输出帧边界不漂移。纯 numpy，无第三方依赖。
    """

    def __init__(self, factor=3, cutoff_hz=5500.0, fs=48000.0, ntaps=96):
        self.factor = factor
        self._ntaps = ntaps
        n = np.arange(ntaps) - (ntaps - 1) / 2.0
        # 窗口化 sinc 低通，截止 5.5kHz（目标奈奎斯特 8kHz 以下留足过渡带），
        # 通带 0~2.7kHz（SSB 语音）完全平坦
        h = 2.0 * cutoff_hz / fs * np.sinc(2.0 * cutoff_hz / fs * n)
        h *= np.hamming(ntaps)
        h /= np.sum(h)
        self._h = h.astype(np.float64)
        self._state = np.zeros(ntaps - 1, dtype=np.float64)  # 最近 ntaps-1 个输入样本
        self._phase = 0  # 抽取相位 0..factor-1

    def process(self, x):
        x = np.asarray(x, dtype=np.float64)
        if x.size == 0:
            return np.zeros(0, dtype=np.float64)
        combined = np.concatenate([self._state, x])
        y = np.convolve(combined, self._h)[self._ntaps - 1: self._ntaps - 1 + x.size]
        # 状态 = 最近 ntaps-1 个输入样本（含本次新增）
        self._state = combined[-(self._ntaps - 1):] if combined.size >= self._ntaps - 1 else combined
        out = y[self._phase::self.factor]
        self._phase = (self._phase - x.size) % self.factor
        return out

    def reset(self):
        self._state = np.zeros(self._ntaps - 1, dtype=np.float64)
        self._phase = 0


def enumerate_audio_devices():
    """Enumerate audio devices available on the system"""
    try:
        p = pyaudio.PyAudio()
        devices = []
        
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            devices.append({
                'index': i,
                'name': info['name'],
                'max_input_channels': info['maxInputChannels'],
                'max_output_channels': info['maxOutputChannels'],
                'default_sample_rate': info['defaultSampleRate']
            })
        
        p.terminate()
        return devices
    except Exception as e:
        print(f"Error enumerating audio devices: {e}")
        return []

def get_default_input_device():
    """Get the default input device"""
    try:
        p = pyaudio.PyAudio()
        info = p.get_default_input_device_info()
        p.terminate()
        return info['name']
    except Exception as e:
        print(f"Error getting default input device: {e}")
        return None

def get_default_output_device():
    """Get the default output device"""
    try:
        p = pyaudio.PyAudio()
        info = p.get_default_output_device_info()
        p.terminate()
        return info['name']
    except Exception as e:
        print(f"Error getting default output device: {e}")
        return None

class PyAudioCapture(threading.Thread):
    """PyAudio-based replacement for ALSA capture
    
    支持 Opus 编码传输：
    - rx_opus_encode=False: 发送 Int16 PCM（默认，兼容旧客户端）
    - rx_opus_encode=True: 发送 Opus 编码音频（节省带宽约 70%）
    
    帧序号机制：
    - 每个Opus帧前添加4字节序号(小端uint32)
    - 前端可检测丢包并使用FEC恢复
    """
    
    # 类级别的 Opus 编码设置（由客户端协商后设置）
    rx_opus_encode = False
    rx_opus_rate = 16000  # Opus 采样率
    rx_opus_frame_dur = 20  # Opus 帧时长 (ms)
    _flush_opus_accumulator = False  # 跨线程标志：PTT释放时清空opus_accumulator
    rx_opus_encoder = None  # Opus 编码器实例

    # 固定 RX 码率（bps）：16kHz AUDIO 模式下 32kbps 为短波语音的平衡点。
    # 码率经 opus.encoder 的 max_data_bytes 按帧限幅生效（arm64 兼容，见 opus/encoder.py）。
    RX_OPUS_BITRATE = 32000

    # 线格式 1 字节编解码标签（与 mrrc_ft710/opus_rx.py 一致）
    AUDIO_TAG_PCM = 0x00   # 裸 Int16 PCM
    AUDIO_TAG_OPUS = 0x01  # Opus 帧
    
    # RNNoise 降噪设置
    rnnoise_enabled = False
    rnnoise_suppress_level = 50
    
    # WDSP 设置
    wdsp_enabled = False
    wdsp_config = {}
    _wdsp_config_hash = None  # V5.2: 配置快照缓存，避免每帧重检
    
    # V5.2: 标记配置已变更，由外部 setter 触发
    _wdsp_dirty = threading.Event()
    _wdsp_dirty.set()  # 初始需要应用
    
    # 帧序号（用于FEC丢包检测）
    _frame_sequence = 0
    _sequence_lock = threading.Lock()
    
    # 录音功能设置
    recording_enabled = False  # 是否启用录音
    recording_buffer = []  # RX 录音数据缓冲区（左声道）
    tx_recording_buffer = []  # TX 录音数据缓冲区（右声道）
    # WARNING: recording_buffer and tx_recording_buffer are unbounded lists.
    # At 8 kHz mono, ~1 hour of audio ≈ 220 MB RAM.  A very long recording
    # session without stop_recording() will grow memory indefinitely.
    # If this becomes a problem, enforce a maximum duration or switch to
    # writing chunks directly to disk (e.g. via a WAV file writer).
    RECORDING_MAX_CHUNKS = 36000  # ~1 h at 8 kHz / 800-sample frames
    recording_lock = threading.Lock()  # 录音缓冲区锁
    recording_start_time = None  # 录音开始时间
    recording_freq = 0  # 录音时的频率
    recording_dir = "recordings"  # 录音文件保存目录
    
    def __init__(self, config):
        threading.Thread.__init__(self)
        # daemon=True：进程退出时不因本线程阻塞而挂起；_stop_event 控制 run() 循环退出
        self.daemon = True
        self._stop_event = threading.Event()
        self.config = config
        
        # Opus 编码器实例（延迟初始化）
        self.rx_opus_encoder = None
        self.rx_opus_encoder_rate = 0  # 用于检测参数变化
        
        # RNNoise 降噪器实例（延迟初始化）
        self.rnnoise_denoiser = None
        
        # WDSP 处理器实例（延迟初始化）
        self.wdsp_processor = None
        self.wdsp_resample_buffer = np.array([], dtype=np.int16)
        # 有状态 48k→16k 降采样器（WDSP 配置在低采样率时使用）
        self._decimator = None
        
        # 读取 RNNoise 配置（已弃用，推荐使用 WDSP）
        if 'RNNOISE' in config:
            PyAudioCapture.rnnoise_enabled = config['RNNOISE'].getboolean('enabled', False)
            PyAudioCapture.rnnoise_suppress_level = config['RNNOISE'].getint('suppress_level', 50)
            if PyAudioCapture.rnnoise_enabled and RNNOISE_AVAILABLE:
                print(f"🔇 RNNoise 降噪已启用（已弃用，建议改用 WDSP），强度: {PyAudioCapture.rnnoise_suppress_level}")
        
        # 读取 WDSP 配置（推荐使用 WDSP 替代 RNNoise）
        if 'WDSP' in config:
            PyAudioCapture.wdsp_enabled = config['WDSP'].getboolean('enabled', True)  # 默认启用
            if PyAudioCapture.wdsp_enabled and WDSP_AVAILABLE:
                PyAudioCapture.wdsp_config = {
                    'sample_rate': config['WDSP'].getint('sample_rate', 48000),
                    'buffer_size': config['WDSP'].getint('buffer_size', 256),
                    'nr2_enabled': config['WDSP'].getboolean('nr2_enabled', True),
                    'nr2_level': config['WDSP'].getint('nr2_level', 2),
                    'nb_enabled': config['WDSP'].getboolean('nb_enabled', True),
                    'anf_enabled': config['WDSP'].getboolean('anf_enabled', False),
                    'nf_enabled': config['WDSP'].getboolean('nf_enabled', False),
                    'agc_mode': config['WDSP'].getint('agc_mode', 3),
                    'bandpass_low': config['WDSP'].getfloat('bandpass_low', 300.0),
                    'bandpass_high': config['WDSP'].getfloat('bandpass_high', 2700.0),
                    # AE 掩码平滑（抑制 NR2"水音"音乐噪声）：psi 越大越平滑，阈值越小越常触发
                    'nr2_ae_psi': config['WDSP'].getfloat('nr2_ae_psi', 12.0),
                    'nr2_ae_zeta_thresh': config['WDSP'].getfloat('nr2_ae_zeta_thresh', 0.65),
                }
                cfg = PyAudioCapture.wdsp_config
                print(f"🔧 WDSP DSP 已启用（替代 RNNoise）")
                print(f"   配置: {cfg['sample_rate']}Hz, NR2={cfg['nr2_enabled']}(level={cfg['nr2_level']}), NB={cfg['nb_enabled']}, AGC={cfg['agc_mode']}")
            elif PyAudioCapture.wdsp_enabled and not WDSP_AVAILABLE:
                print(f"⚠️ WDSP 已启用但库不可用，请先编译安装 libwdsp")
                print(f"   安装命令: cd /tmp && git clone https://github.com/g0orx/wdsp.git && cd wdsp && make")
        
        # Initialize PyAudio
        self.p = pyaudio.PyAudio()
        
        # List available audio devices for debugging
        print("Available audio input devices:")
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"  {i}: {info['name']} (channels: {info['maxInputChannels']})")
        
        # Get device index
        device_index = self._get_device_index(config['AUDIO']['inputdevice'])
        
        # Check device capabilities first
        device_channels = 1
        if device_index is not None:
            try:
                device_info = self.p.get_device_info_by_index(device_index)
                device_channels = device_info['maxInputChannels']
                print(f"Device '{device_info['name']}' supports {device_channels} input channels")
            except Exception as e:
                print(f"Error getting device info: {e}")
        
        # Try to open with the device's native channel count first
        try:
            try:
                self.stream = self.p.open(
                    format=pyaudio.paFloat32,
                    channels=device_channels,
                    rate=48000,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=960  # V5.2: 20ms@48kHz → 对齐Opus帧(320samples@16kHz)
                )
                print(f'PyAudio input stream opened successfully with {device_channels} channel(s) at 48000 Hz')
                self.stereo_mode = (device_channels == 2)
            except Exception as e:
                print(f"Failed to open PyAudio input stream with {device_channels} channels: {e}")
                # Fall back to mono
                try:
                    self.stream = self.p.open(
                        format=pyaudio.paFloat32,
                        channels=1,
                        rate=48000,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=960  # V5.2: 20ms@48kHz → 对齐Opus帧(320samples@16kHz)
                    )
                    print('PyAudio input stream opened successfully with MONO (1 channel) at 48000 Hz - fallback')
                    self.stereo_mode = False
                except Exception as e2:
                    print(f"Failed to open mono PyAudio input stream: {e2}")
                    # Try with default device
                    try:
                        self.stream = self.p.open(
                            format=pyaudio.paFloat32,
                            channels=1,
                            rate=48000,
                            input=True,
                            frames_per_buffer=960  # V5.2: 20ms@48kHz → 对齐Opus帧(320samples@16kHz)
                        )
                        print('Opened with default input device (mono) at 48000 Hz')
                        self.stereo_mode = False
                    except Exception as e3:
                        print(f"Failed to open default input device: {e3}")
                        raise
        except Exception:
            # 构造失败：必须释放已创建的 PyAudio 上下文，否则句柄泄漏
            # （调用方拿到异常时对象尚未构造完成，无法调用 close()）
            try:
                self.p.terminate()
            except Exception:
                pass
            raise
    
    def _get_device_index(self, device_name):
        """Convert device name to device index for PyAudio"""
        if device_name == "" or device_name is None:
            return None  # Use default device
        
        # Try to find device by name (partial match)
        try:
            for i in range(self.p.get_device_count()):
                info = self.p.get_device_info_by_index(i)
                if device_name.lower() in info['name'].lower():
                    # Check if device supports the required channels
                    if info['maxInputChannels'] > 0:
                        print(f"Found input device: {info['name']} (index {i})")
                        return i
        except Exception as e:
            print(f"Error finding device '{device_name}': {e}")
        
        print(f"Device '{device_name}' not found, using default input device")
        return None  # Use default if not found
    
    def run(self):
        # Import globals at runtime to avoid circular imports
        import __main__
        
        print("🎵 PyAudioCapture线程已启动，开始音频捕获...")
        frame_count = 0
        last_log_time = time.time()
        
        # Opus 编码累积缓冲区
        opus_accumulator = np.array([], dtype=np.int16)
        
        # 降采样滤波器状态（用于 48kHz → 16kHz）
        # 使用简单的平均滤波：每 3 个样本取 1 个
        downsample_factor = 3  # 48000 / 16000 = 3
        
        while not self._stop_event.is_set():
            try:
                # 使用非阻塞读取，避免线程被阻塞
                data = self.stream.read(320, exception_on_overflow=False)
                
                if len(data) > 0:
                    frame_count += 1
                    
                    # 每 5 秒打印一次状态
                    current_time = time.time()
                    if current_time - last_log_time >= 30.0:
                        # 动态读取类变量
                        current_opus_mode = PyAudioCapture.rx_opus_encode
                        encode_mode = "Opus" if current_opus_mode else "Int16"
                        print(f"🎵 音频捕获正常 | 帧数: {frame_count} | 模式: {encode_mode}")
                        last_log_time = current_time
                    
                    # Convert stereo to mono if needed
                    # 只取右声道（电台录音通常右声道是RX输出）
                    if self.stereo_mode:
                        stereo_data = np.frombuffer(data, dtype=np.float32)
                        stereo_data = stereo_data.reshape(-1, 2)
                        mono_data = stereo_data[:, 1]  # 只取右声道
                        data = mono_data.tobytes()
                    
                    # Convert Float32 to Int16 for 50% bandwidth reduction
                    float32_data = np.frombuffer(data, dtype=np.float32)
                    
                    # 音频优化：提升语音质量
                    # 1. 去除直流偏移
                    dc_offset = np.mean(float32_data)
                    if abs(dc_offset) > 0.001:
                        float32_data = float32_data - dc_offset
                    
                    # 2. 自动增益控制 (AGC) - 当 WDSP AGC 已开启时跳过
                    wdsp_agc_active = (
                        PyAudioCapture.wdsp_enabled and WDSP_AVAILABLE
                        and PyAudioCapture.wdsp_config.get('agc_mode', 0) != 0
                    )
                    if not wdsp_agc_active:
                        max_val = np.max(np.abs(float32_data))
                        if max_val > 0.001:
                            target_level = 0.6  # 目标电平 -4dB
                            if max_val < target_level * 0.3:
                                # 弱信号：提升增益（最大4倍）
                                gain = min(target_level / max_val, 4.0)
                                float32_data = float32_data * gain
                            elif max_val > 0.9:
                                # 强信号：略微衰减，防止削波
                                float32_data = float32_data * 0.85
                    
                    # 3. 软膝峰值限幅（仅>0.95 介入，强信号不再硬切方波产生谐波）
                    float32_data = soft_peak_limiter(float32_data, knee=0.95, ceiling=0.99)
                    
                    int16_data = (float32_data * 32767).astype(np.int16)
                    
                    # ========== 录音功能：保存原始音频数据（48kHz，未经WDSP处理）==========
                    if PyAudioCapture.recording_enabled:
                        with PyAudioCapture.recording_lock:
                            # 将48kHz数据降采样到16kHz（与输出一致）
                            # 先 3 样本平均低通防混叠，再抽取
                            samples_len = len(int16_data)
                            trimmed_len = (samples_len // 3) * 3
                            if trimmed_len >= 3:
                                reshaped = int16_data[:trimmed_len].reshape(-1, 3)
                                downsampled = reshaped.mean(axis=1).astype(np.int16)
                            else:
                                downsampled = int16_data
                            PyAudioCapture.recording_buffer.append(downsampled)
                            # Guard against unbounded growth
                            if len(PyAudioCapture.recording_buffer) >= PyAudioCapture.RECORDING_MAX_CHUNKS:
                                logger.warning("录音缓冲区已满 (RECORDING_MAX_CHUNKS), 自动停止录音")
                                PyAudioCapture.recording_enabled = False
                    
                    # ========== WDSP 数字信号处理 ==========
                    # 在 Int16 转换后、Opus编码前进行 WDSP 处理

                    # V5.2: WDSP 配置缓存 — 仅变更时进入
                    # 计算配置哈希，避免每帧 100+ 行的属性比较
                    if not PyAudioCapture.wdsp_enabled and self.wdsp_processor is not None:
                        try:
                            self.wdsp_processor.close()
                            self.wdsp_processor = None
                            self.wdsp_resample_buffer = np.array([], dtype=np.int16)
                            if self._decimator is not None:
                                self._decimator.reset()
                            PyAudioCapture._wdsp_config_hash = None
                        except Exception as e:
                            pass
                    
                    # 当前 int16_data 的采样率（决定后续是否需降采样到 Opus 率）
                    stream_rate = 48000

                    if PyAudioCapture.wdsp_enabled and WDSP_AVAILABLE:
                        try:
                            cfg = PyAudioCapture.wdsp_config
                            # 快速哈希：只取最可能变更的键
                            new_hash = hash((
                                cfg.get('nr2_enabled', True),
                                cfg.get('nr2_level', 1),
                                cfg.get('nb_enabled', True),
                                cfg.get('anf_enabled', False),
                                cfg.get('agc_mode', 3),
                                cfg.get('bandpass_low', 300.0),
                                cfg.get('bandpass_high', 2700.0),
                                cfg.get('nr2_ae_psi', 12.0),
                                cfg.get('nr2_ae_zeta_thresh', 0.65),
                            ))
                            
                            if new_hash != PyAudioCapture._wdsp_config_hash or self.wdsp_processor is None:
                                PyAudioCapture._wdsp_config_hash = new_hash
                                
                                if self.wdsp_processor is None:
                                    wdsp_sr = cfg.get('sample_rate', 48000)
                                    wdsp_bs = cfg.get('buffer_size', 256)
                                    self.wdsp_processor = WDSPProcessor(
                                        sample_rate=wdsp_sr, buffer_size=wdsp_bs,
                                        mode=WDSPMode.USB,
                                        enable_nr2=cfg['nr2_enabled'],
                                        enable_nb=cfg['nb_enabled'],
                                        enable_anf=cfg['anf_enabled'],
                                        agc_mode=cfg['agc_mode'],
                                        nr2_ae_psi=cfg.get('nr2_ae_psi', 12.0),
                                        nr2_ae_zeta_thresh=cfg.get('nr2_ae_zeta_thresh', 0.65),
                                    )
                                    self.wdsp_processor.set_bandpass(cfg['bandpass_low'], cfg['bandpass_high'])
                                    if cfg['nr2_enabled']:
                                        self.wdsp_processor.set_nr2_level(cfg.get('nr2_level', 2))
                                    # WDSP 配置在低采样率（如 16k）时，输入需先做有状态 48k→16k 降采样
                                    if wdsp_sr < 48000:
                                        self._decimator = _StatefulDecimator(factor=48000 // wdsp_sr)
                                    else:
                                        self._decimator = None
                                else:
                                    self.wdsp_processor.set_nr2_level(cfg.get('nr2_level', 2) if cfg['nr2_enabled'] else 0)
                                    self.wdsp_processor.set_nb_enabled(cfg['nb_enabled'])
                                    self.wdsp_processor.set_anf_enabled(cfg['anf_enabled'])
                                    self.wdsp_processor.set_agc_mode(cfg['agc_mode'])
                                    self.wdsp_processor.set_bandpass(cfg['bandpass_low'], cfg['bandpass_high'])
                                    # nr2_ae_run 已由 set_nr2_level() 内置管理，无需额外设置
                        except Exception as e:
                            # H10: WDSP 配置异常不可静默吞掉，否则 DSP 静默不工作且无法排查
                            print(f"⚠️ WDSP config/初始化错误（降级直通）: {e}")
                        
                        # V5.2: WDSP 处理 — 在 try/except 之外，每帧必执行
                        cfg = PyAudioCapture.wdsp_config
                        wdsp_buffer_size = cfg['buffer_size']

                        # DSP 实际采样率由降采样器决定（其存在 ⟺ DSP 跑在 16k）。
                        # 以 decimator 而非重读 cfg 为准，避免运行中配置漂移导致率不匹配。
                        if self._decimator is not None:
                            wdsp_sr = 48000 // self._decimator.factor
                            # 有状态 48k→16k 降采样：输出与 Opus 编码率对齐，后续无需二次降采样
                            decimated = self._decimator.process(int16_data.astype(np.float64) / 32767.0)
                            dsp_input = np.clip(decimated, -1.0, 1.0)
                            dsp_input = (dsp_input * 32767.0).astype(np.int16)
                        else:
                            wdsp_sr = 48000
                            dsp_input = int16_data

                        self.wdsp_resample_buffer = np.concatenate([self.wdsp_resample_buffer, dsp_input])

                        processed_frames = []
                        while len(self.wdsp_resample_buffer) >= wdsp_buffer_size:
                            frame = self.wdsp_resample_buffer[:wdsp_buffer_size]
                            self.wdsp_resample_buffer = self.wdsp_resample_buffer[wdsp_buffer_size:]
                            processed = self.wdsp_processor.process(frame)
                            if processed is not None and len(processed) > 0:
                                if len(processed) != len(frame):
                                    processed = frame
                                processed_frames.append(processed)

                        if processed_frames:
                            int16_data = np.concatenate(processed_frames)
                            try:
                                # 软膝峰值限幅：knee=0.97 只在真正接近削顶时才介入，
                                # 避免 AGC 归一化后的正常语音峰值被持续压缩失真
                                float_output = int16_data.astype(np.float32) / 32767.0
                                float_output = soft_peak_limiter(float_output, knee=0.97, ceiling=0.99)
                                int16_data = (float_output * 32767.0).astype(np.int16)
                            except Exception:
                                pass
                            # WDSP 输出采样率即 DSP 配置率（16k）
                            stream_rate = wdsp_sr

                    # 发送到客户端队列
                    try:
                        import sys
                        main_module = sys.modules['__main__']
                        if hasattr(main_module, 'AudioRXHandlerClients'):
                            global AudioRXHandlerClients
                            AudioRXHandlerClients = getattr(main_module, 'AudioRXHandlerClients')
                            client_count = len(AudioRXHandlerClients)

                            if client_count > 0:
                                # H7: 快照客户端列表，避免 Tornado 线程并发 append/remove
                                # 导致迭代中 'list changed size during iteration'，丢帧并报错
                                clients_snapshot = list(AudioRXHandlerClients)
                                # 半双工优化：TX 时停止发送 RX 音频数据
                                # 避免 Echo 和节省带宽
                                is_ptt_on = False
                                try:
                                    if hasattr(main_module, 'CTRX') and main_module.CTRX:
                                        is_ptt_on = main_module.CTRX.infos.get("PTT", False)
                                except Exception:
                                    pass
                                
                                if is_ptt_on:
                                    # TX 时跳过 RX 数据发送，但保持连接
                                    continue
                                
                                # 动态读取类变量，支持运行时切换编码模式
                                # 跨线程：PTT释放时清空accumulator
                                if PyAudioCapture._flush_opus_accumulator:
                                    opus_accumulator = np.array([], dtype=np.int16)
                                    PyAudioCapture._flush_opus_accumulator = False

                                current_opus_mode = PyAudioCapture.rx_opus_encode
                                current_opus_rate = PyAudioCapture.rx_opus_rate
                                current_opus_frame_dur = PyAudioCapture.rx_opus_frame_dur
                                
                                # Opus 编码模式
                                if current_opus_mode:
                                    # 降采样：48kHz → 目标采样率
                                    # 使用简单的平均滤波降采样
                                    source_rate = stream_rate  # 捕获率；WDSP@16k 时为 16k，否则 48k
                                    if current_opus_rate < source_rate:
                                        downsample_ratio = source_rate // current_opus_rate
                                        # 平均降采样：每 downsample_ratio 个样本取平均
                                        if len(int16_data) >= downsample_ratio:
                                            # 重塑数组并进行平均
                                            trimmed_len = (len(int16_data) // downsample_ratio) * downsample_ratio
                                            reshaped = int16_data[:trimmed_len].reshape(-1, downsample_ratio)
                                            int16_data = reshaped.mean(axis=1).astype(np.int16)
                                    
                                    # 动态计算帧大小
                                    opus_frame_size = int(current_opus_rate * current_opus_frame_dur / 1000)
                                    
                                    # 累积数据直到达到一个完整的 Opus 帧
                                    opus_accumulator = np.concatenate([opus_accumulator, int16_data])
                                    
                                    # 当累积足够的数据时，编码并发送
                                    encode_count = 0
                                    while len(opus_accumulator) >= opus_frame_size:
                                        encode_count += 1
                                        # 取出一帧数据
                                        frame_data = opus_accumulator[:opus_frame_size]
                                        opus_accumulator = opus_accumulator[opus_frame_size:]
                                        
                                        # V5.2: 编码器仅在首次或参数变化时初始化
                                        if self.rx_opus_encoder is None or self.rx_opus_encoder_rate != current_opus_rate:
                                            try:
                                                # application 传 'audio'(2049)：短波语音/数字模式比 VOIP(2048) 更自然
                                                self.rx_opus_encoder = OpusEncoder(
                                                    current_opus_rate, 1, 'audio'
                                                )
                                                self.rx_opus_encoder_rate = current_opus_rate
                                                # 固定码率（不再全局自适应）：单客户端拥塞不再拖累全体，
                                                # 拥塞由下方每客户端的 Wavframes 队列丢帧机制吸收。
                                                self.rx_opus_encoder.configure_for_voip(
                                                    bitrate=PyAudioCapture.RX_OPUS_BITRATE, complexity=8,
                                                    fec=True, packet_loss_perc=15, dtx=True
                                                )
                                            except Exception as e:
                                                # H10: 不可静默回退；记录原因并通知路径（前端协商了 Opus）
                                                print(f"⚠️ Opus 编码器初始化失败，回退 PCM: {e}")
                                                PyAudioCapture.rx_opus_encode = False
                                                break
                                        
                                        # 编码
                                        try:
                                            frame_bytes = frame_data.tobytes()
                                            encoded_data = self.rx_opus_encoder.encode(frame_bytes, opus_frame_size)
                                            # 线格式：1 字节编解码标签 + Opus 帧（客户端按标签确定性解码）
                                            encoded_data = bytes([PyAudioCapture.AUDIO_TAG_OPUS]) + encoded_data

                                            # 发送到客户端
                                            # 弱网优化：智能队列管理
                                            # 根据队列深度动态调整策略
                                            for c in clients_snapshot:
                                                queue_len = len(c.Wavframes)
                                                if queue_len < 10:
                                                    # 队列空闲，正常添加
                                                    c.Wavframes.append(encoded_data)
                                                elif queue_len < 20:
                                                    # 队列适中，丢弃旧帧保持新鲜度
                                                    c.Wavframes.pop(0)
                                                    c.Wavframes.append(encoded_data)
                                                else:
                                                    # 队列过满（网络拥塞），丢弃一半旧帧
                                                    # 避免客户端收到过时数据
                                                    c.Wavframes = c.Wavframes[10:]
                                                    c.Wavframes.append(encoded_data)
                                            # V5.2: 仅每 1000 帧打印（减少热路径IO）
                                            if frame_count % 1000 == 0:
                                                print(f"🎵 Opus 编码正常... 帧数: {frame_count}, 压缩率: {len(encoded_data)}/{len(frame_bytes)}")
                                        except Exception as e:
                                            if frame_count % 1000 == 0:
                                                print(f"Opus 编码错误: {e}")
                                else:
                                    # Int16 PCM 模式（默认）
                                    # 支持 48kHz → 目标采样率 降采样
                                    source_rate = stream_rate  # 捕获率；WDSP@16k 时为 16k，否则 48k
                                    target_rate = PyAudioCapture.rx_opus_rate  # 目标采样率
                                    if target_rate < source_rate and target_rate > 0:
                                        downsample_ratio = source_rate // target_rate
                                        if downsample_ratio > 1 and len(int16_data) >= downsample_ratio:
                                            # 平均降采样
                                            trimmed_len = (len(int16_data) // downsample_ratio) * downsample_ratio
                                            reshaped = int16_data[:trimmed_len].reshape(-1, downsample_ratio)
                                            int16_data = reshaped.mean(axis=1).astype(np.int16)
                                    
                                    # 确保数据长度是 2 的倍数（Int16 要求）
                                    if len(int16_data) % 2 != 0:
                                        int16_data = int16_data[:-1]
                                    
                                    compressed_data = int16_data.tobytes()
                                    # 线格式：1 字节编解码标签 + Int16 PCM（客户端按标签确定性解码）
                                    compressed_data = bytes([PyAudioCapture.AUDIO_TAG_PCM]) + compressed_data
                                    # 弱网优化：智能队列管理
                                    for c in clients_snapshot:
                                        queue_len = len(c.Wavframes)
                                        if queue_len < 10:
                                            # 队列空闲，正常添加
                                            c.Wavframes.append(compressed_data)
                                        elif queue_len < 20:
                                            # 队列适中，丢弃旧帧保持新鲜度
                                            c.Wavframes.pop(0)
                                            c.Wavframes.append(compressed_data)
                                        else:
                                            # 队列过满（网络拥塞），丢弃一半旧帧
                                            c.Wavframes = c.Wavframes[10:]
                                            c.Wavframes.append(compressed_data)
                    except Exception as e:
                        if frame_count % 100 == 0:
                            print(f"Error accessing AudioRXHandlerClients: {e}")
                else:
                    # 没有数据时短暂等待
                    time.sleep(0.005)
                    
            except IOError as e:
                # PyAudio 缓冲区溢出，继续
                if frame_count % 100 == 0:
                    print(f"Audio buffer overflow: {e}")
                continue
            except Exception as e:
                print(f"Audio read error: {e}")
                time.sleep(0.01)
    
    def close(self):
        """Close the audio stream and stop the capture thread."""
        # 通知 run() 循环退出
        self._stop_event.set()
        try:
            if hasattr(self, 'stream') and self.stream is not None and self.stream.is_active():
                self.stream.stop_stream()
        except Exception as e:
            print(f"⚠️ stop_stream error: {e}")
        try:
            if hasattr(self, 'stream') and self.stream is not None:
                self.stream.close()
        except Exception as e:
            print(f"⚠️ stream.close error: {e}")
        try:
            if hasattr(self, 'p') and self.p is not None:
                self.p.terminate()
        except Exception as e:
            print(f"⚠️ PyAudio terminate error: {e}")
        # 等待线程退出，避免非守护线程残留（daemon=True 兜底，仍尽量 join）
        try:
            self.join(timeout=2.0)
        except Exception:
            pass
    
    # ========== 录音功能静态方法 ==========
    
    @staticmethod
    def start_recording(freq=0):
        """
        开始录音
        
        Args:
            freq: 当前频率（Hz），用于文件名
        
        Returns:
            bool: 是否成功开始录音
        """
        try:
            # 确保录音目录存在
            if not os.path.exists(PyAudioCapture.recording_dir):
                os.makedirs(PyAudioCapture.recording_dir)
            
            with PyAudioCapture.recording_lock:
                PyAudioCapture.recording_buffer = []
                PyAudioCapture.tx_recording_buffer = []
                PyAudioCapture.recording_start_time = datetime.now()
                PyAudioCapture.recording_freq = freq
                PyAudioCapture.recording_enabled = True
            
            freq_khz = freq / 1000 if freq > 0 else 0
            print(f"🔴 开始录音: 频率 {freq_khz:.1f}kHz")
            return True
            
        except Exception as e:
            print(f"❌ 开始录音失败: {e}")
            return False
    
    @staticmethod
    def stop_recording():
        """
        停止录音并保存文件
        
        Returns:
            str: 保存的文件路径，如果失败返回None
        """
        try:
            with PyAudioCapture.recording_lock:
                PyAudioCapture.recording_enabled = False

                rx_data = np.concatenate(PyAudioCapture.recording_buffer) if PyAudioCapture.recording_buffer else None
                tx_data = np.concatenate(PyAudioCapture.tx_recording_buffer) if PyAudioCapture.tx_recording_buffer else None
                PyAudioCapture.recording_buffer = []
                PyAudioCapture.tx_recording_buffer = []

                if rx_data is None and tx_data is None:
                    print("⚠️ 录音缓冲区为空")
                    return None

                # 对齐 RX 和 TX 数据长度，填充较短的声道
                max_len = max(len(rx_data) if rx_data is not None else 0,
                              len(tx_data) if tx_data is not None else 0)
                if rx_data is not None and len(rx_data) < max_len:
                    rx_data = np.pad(rx_data, (0, max_len - len(rx_data)), mode='constant')
                if tx_data is not None and len(tx_data) < max_len:
                    tx_data = np.pad(tx_data, (0, max_len - len(tx_data)), mode='constant')
                if rx_data is None:
                    rx_data = np.zeros(max_len, dtype=np.int16)
                if tx_data is None:
                    tx_data = np.zeros(max_len, dtype=np.int16)

                # 交错合并为立体声: [L0, R0, L1, R1, ...]
                stereo_data = np.column_stack((rx_data, tx_data)).reshape(-1).astype(np.int16)

                # 生成文件名: 频率(kHz)_日期_时间.mp3
                freq_khz = int(PyAudioCapture.recording_freq / 1000) if PyAudioCapture.recording_freq > 0 else 0
                now = datetime.now()
                date_str = now.strftime('%Y%m%d')
                time_str = now.strftime('%H%M%S')
                filename = f"{freq_khz:05d}kHz_{date_str}_{time_str}.mp3"
                filepath = os.path.join(PyAudioCapture.recording_dir, filename)

                # 使用 ffmpeg 编码为高质量 MP3 (LAME VBR q:0, 16kHz stereo PCM -> MP3)
                ffmpeg_cmd = [
                    'ffmpeg', '-y',                    # 覆盖已存在的输出文件
                    '-f', 's16le',                      # 输入格式: 16-bit signed little-endian
                    '-ar', '16000',                     # 输入采样率: 16kHz
                    '-ac', '2',                         # 输入声道: stereo
                    '-i', 'pipe:0',                    # 从 stdin 读取
                    '-c:a', 'libmp3lame',              # LAME MP3 编码器
                    '-q:a', '0',                       # 最高质量 VBR (0=best, 9=worst)
                    filepath
                ]
                proc = subprocess.run(
                    ffmpeg_cmd,
                    input=stereo_data.tobytes(),
                    capture_output=True,
                    timeout=30
                )
                if proc.returncode != 0:
                    raise RuntimeError(f"ffmpeg 编码失败: {proc.stderr.decode()}")

                duration = max_len / 16000
                print(f"✅ 录音已保存 (MP3高质量): {filename} ({duration:.1f}秒, L={len(rx_data)} R={len(tx_data)}, {os.path.getsize(filepath)} bytes)")
                return filepath
                
        except Exception as e:
            print(f"❌ 停止录音失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def get_recording_status():
        """
        获取录音状态
        
        Returns:
            dict: 包含录音状态、频率、开始时间等信息
        """
        with PyAudioCapture.recording_lock:
            duration = 0
            if PyAudioCapture.recording_enabled and PyAudioCapture.recording_start_time:
                duration = (datetime.now() - PyAudioCapture.recording_start_time).total_seconds()
            
            return {
                'recording': PyAudioCapture.recording_enabled,
                'freq': PyAudioCapture.recording_freq,
                'start_time': PyAudioCapture.recording_start_time.isoformat() if PyAudioCapture.recording_start_time else None,
                'duration': duration,
                'buffer_size': sum(len(buf) for buf in PyAudioCapture.recording_buffer) if PyAudioCapture.recording_buffer else 0
            }

class PyAudioPlayback:
    """PyAudio-based replacement for ALSA playback"""
    
    def __init__(self, config, itrate, is_encoded, op_rate, op_frm_dur):
        self.config = config
        self.itrate = itrate
        self.is_encoded = is_encoded
        self.op_rate = op_rate
        self.op_frm_dur = op_frm_dur
        self._tx_gain_smooth = 1.0  # TX 电平平滑状态

        # F2 fix: bounded queue + dedicated writer thread so the blocking
        # PyAudio stream.write() never runs on the Tornado IOLoop.
        # ~50 frames @ 20ms = 1s of buffered TX audio before we drop oldest.
        self._tx_queue = queue.Queue(maxsize=50)
        self._writer_stop = threading.Event()
        self._writer_thread = None

        if is_encoded:
            self.decoder = OpusDecoder(op_rate, 1)
            self.frame_size = op_frm_dur * op_rate
        
        # ========== 关键修复：采样率匹配 ==========
        # 当 Opus 编码启用时，解码后的 PCM 数据采样率是 op_rate (16kHz)
        # 必须 PyAudio 流也使用 op_rate，否则播放速度不正确导致噪音
        playback_rate = op_rate if is_encoded else itrate
        
        # Initialize PyAudio
        self.p = pyaudio.PyAudio()
        
        # List available audio devices for debugging
        print("Available audio output devices:")
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                print(f"  {i}: {info['name']} (channels: {info['maxOutputChannels']})")
        
        # Get device index
        device_index = self._get_device_index(config['AUDIO']['outputdevice'])
        
        try:
            try:
                # Open output stream with optimized settings for low latency
                self.stream = self.p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=playback_rate,
                    output=True,
                    output_device_index=device_index,
                    frames_per_buffer=960  # V5.2: 20ms@48kHz → 对齐Opus帧(320samples@16kHz)
                )
                print(f'PyAudio output stream opened successfully at {playback_rate}Hz (Opus: {is_encoded})')
            except Exception as e:
                print(f"Failed to open PyAudio output stream: {e}")
                # Try with default device
                try:
                    self.stream = self.p.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=playback_rate,  # 使用正确的采样率
                        output=True,
                        frames_per_buffer=960  # V5.2: 20ms@48kHz → 对齐Opus帧(320samples@16kHz)
                    )
                    print(f'Opened with default output device at {playback_rate}Hz')
                except Exception as e2:
                    print(f"Failed to open default output device: {e2}")
                    raise
        except Exception:
            # 构造失败：释放 PyAudio 上下文，避免句柄泄漏
            try:
                self.p.terminate()
            except Exception:
                pass
            raise

        # F2 fix: start dedicated playback writer thread now that the stream is open.
        # All blocking stream.write() calls happen here, off the Tornado IOLoop.
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()

    def _get_device_index(self, device_name):
        """Convert device name to device index for PyAudio"""
        if device_name == "" or device_name is None:
            return None  # Use default device
        
        # Try to find device by name (partial match)
        try:
            for i in range(self.p.get_device_count()):
                info = self.p.get_device_info_by_index(i)
                if device_name.lower() in info['name'].lower():
                    # Check if device supports the required channels
                    if info['maxOutputChannels'] > 0:
                        print(f"Found output device: {info['name']} (index {i})")
                        return i
        except Exception as e:
            print(f"Error finding device '{device_name}': {e}")
        
        print(f"Device '{device_name}' not found, using default output device")
        return None  # Use default if not found
    
    def _normalize(self, data):
        """Decode (if needed) + TX level normalization. Runs on caller thread (cheap)."""
        if self.is_encoded:
            pcm = self.decoder.decode(data, self.frame_size, False)
        else:
            pcm = data

        # TX 音频电平归一化：带 smoothing 的增益控制，防 pumping
        tx_int16 = np.frombuffer(pcm, dtype=np.int16)
        if len(tx_int16) > 0:
            max_val = np.max(np.abs(tx_int16))
            if max_val > 0:
                target_peak = int(32767 * 0.85)
                if max_val < target_peak:
                    target_gain = min(target_peak / max_val, 2.5)
                else:
                    target_gain = 1.0  # 已够大，不提升
                # 一阶平滑：attack(需减增益)快 release(需增增益)慢，防 pumping
                alpha = 0.5 if target_gain < self._tx_gain_smooth else 0.05
                self._tx_gain_smooth = self._tx_gain_smooth * (1 - alpha) + target_gain * alpha
                # 低失真：软膝峰值限幅（仅>0.9 介入），替代硬削波，避免大声喊话削峰失真
                f = (tx_int16 * self._tx_gain_smooth).astype(np.float32) / 32767.0
                f = soft_peak_limiter(f, knee=0.9, ceiling=0.98)
                tx_int16 = (f * 32767.0).astype(np.int16)
            pcm = tx_int16.tobytes()
        return pcm

    def write(self, data):
        """Enqueue audio for the playback thread (non-blocking).

        F2 fix: the blocking PyAudio stream.write() previously ran on the
        Tornado IOLoop thread (WS_AudioTXHandler.on_message). Device backpressure
        would stall the entire server. We now normalize on the caller (cheap,
        numpy-only) and hand the PCM to a dedicated writer thread via a bounded
        queue. If the queue is full (device underrun/backpressure), we drop the
        oldest frame instead of blocking the IOLoop.
        """
        try:
            pcm = self._normalize(data)
        except Exception as e:
            print(f"TX normalize error: {e}")
            return

        try:
            self._tx_queue.put_nowait(pcm)
        except queue.Full:
            # Drop oldest frame to make room — never block the IOLoop
            try:
                self._tx_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._tx_queue.put_nowait(pcm)
            except queue.Full:
                pass

    def _writer_loop(self):
        """Dedicated thread: drains the TX queue into the blocking PyAudio stream."""
        while not self._writer_stop.is_set():
            try:
                pcm = self._tx_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if pcm is None:  # sentinel to stop
                break
            try:
                self.stream.write(pcm)
            except Exception as e:
                print(f"TX stream write error: {e}")

    def close(self):
        """Close the audio stream"""
        # Stop the writer thread first so it doesn't touch a closed stream
        self._writer_stop.set()
        try:
            self._tx_queue.put_nowait(None)  # wake the writer
        except queue.Full:
            pass
        if self._writer_thread is not None:
            self._writer_thread.join(timeout=1.0)
        try:
            if self.stream.is_active():
                self.stream.stop_stream()
            self.stream.close()
        except Exception as e:
            print(f"TX stream close error: {e}")
        self.p.terminate()


# ========== 录音控制函数 ==========

def start_recording(freq=0):
    """
    开始录音
    
    Args:
        freq: 当前频率（Hz），用于文件名
    
    Returns:
        bool: 是否成功开始录音
    """
    return PyAudioCapture.start_recording(freq)

def stop_recording():
    """
    停止录音并保存文件
    
    Returns:
        str: 保存的文件路径，如果失败返回None
    """
    return PyAudioCapture.stop_recording()

def get_recording_status():
    """
    获取录音状态
    
    Returns:
        dict: 包含录音状态、频率、开始时间等信息
    """
    return PyAudioCapture.get_recording_status()

def get_recordings_list():
    """
    获取录音文件列表
    
    Returns:
        list: 录音文件信息列表，按日期排序
    """
    recording_dir = PyAudioCapture.recording_dir
    
    if not os.path.exists(recording_dir):
        return []
    
    recordings = []
    try:
        for filename in os.listdir(recording_dir):
            if filename.endswith('.mp3'):
                filepath = os.path.join(recording_dir, filename)
                stat = os.stat(filepath)

                # 解析文件名获取频率和时间
                # 格式: 频率(kHz)_日期_时间.mp3
                parts = filename.replace('.mp3', '').split('_')
                freq_str = parts[0] if len(parts) > 0 else "Unknown"
                date_str = parts[1] if len(parts) > 1 else ""
                time_str = parts[2] if len(parts) > 2 else ""
                
                recordings.append({
                    'filename': filename,
                    'filepath': filepath,
                    'freq': freq_str,
                    'date': date_str,
                    'time': time_str,
                    'size': stat.st_size,
                    'created': stat.st_mtime
                })
        
        # 按创建时间倒序排列
        recordings.sort(key=lambda x: x['created'], reverse=True)
        return recordings
        
    except Exception as e:
        print(f"❌ 获取录音列表失败: {e}")
        return []
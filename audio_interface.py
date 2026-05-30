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
import time
import gc
import numpy as np
import wave
import os
from datetime import datetime
from opus.decoder import Decoder as OpusDecoder
from opus.encoder import Encoder as OpusEncoder

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
        self.config = config
        
        # Opus 编码器实例（延迟初始化）
        self.rx_opus_encoder = None
        self.rx_opus_encoder_rate = 0  # 用于检测参数变化
        
        # RNNoise 降噪器实例（延迟初始化）
        self.rnnoise_denoiser = None
        
        # WDSP 处理器实例（延迟初始化）
        self.wdsp_processor = None
        self.wdsp_resample_buffer = np.array([], dtype=np.int16)
        
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
                    'nr2_level': config['WDSP'].getint('nr2_level', 1),  # 默认低强度
                    'nr2_gain_method': config['WDSP'].getint('nr2_gain_method', 0),  # NR2 Gain Method
                    'nr2_npe_method': config['WDSP'].getint('nr2_npe_method', 1),  # NR2 NPE Method
                    'nr2_ae_run': config['WDSP'].getboolean('nr2_ae_run', True),  # NR2 AE Run (默认开启)
                    'nr_enabled': config['WDSP'].getboolean('nr_enabled', False),
                    'nb_enabled': config['WDSP'].getboolean('nb_enabled', True),
                    'nb2_enabled': config['WDSP'].getboolean('nb2_enabled', False),
                    'anf_enabled': config['WDSP'].getboolean('anf_enabled', False),
                    'nf_enabled': config['WDSP'].getboolean('nf_enabled', False),  # 手动陷波滤波器 (NF)
                    'agc_mode': config['WDSP'].getint('agc_mode', 3),
                    'bandpass_low': config['WDSP'].getfloat('bandpass_low', 300.0),
                    'bandpass_high': config['WDSP'].getfloat('bandpass_high', 2700.0),
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
        
        while True:
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
                    
                    # 3. 软削波保护
                    float32_data = np.clip(float32_data, -0.95, 0.95)
                    
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
                            PyAudioCapture._wdsp_config_hash = None
                        except Exception as e:
                            pass
                    
                    if PyAudioCapture.wdsp_enabled and WDSP_AVAILABLE:
                        try:
                            cfg = PyAudioCapture.wdsp_config
                            # 快速哈希：只取 6 个最可能变更的键
                            new_hash = hash((
                                cfg.get('nr2_enabled', True),
                                cfg.get('nr2_level', 1),
                                cfg.get('nb_enabled', True),
                                cfg.get('anf_enabled', False),
                                cfg.get('agc_mode', 3),
                                cfg.get('bandpass_low', 300.0),
                                cfg.get('bandpass_high', 2700.0),
                            ))
                            
                            if new_hash != PyAudioCapture._wdsp_config_hash or self.wdsp_processor is None:
                                PyAudioCapture._wdsp_config_hash = new_hash
                                
                                if self.wdsp_processor is None:
                                    wdsp_sr = 48000
                                    wdsp_bs = cfg.get('buffer_size', 256)
                                    self.wdsp_processor = WDSPProcessor(
                                        sample_rate=wdsp_sr, buffer_size=wdsp_bs,
                                        mode=WDSPMode.USB,
                                        enable_nr2=cfg['nr2_enabled'],
                                        enable_nb=cfg['nb_enabled'],
                                        enable_anf=cfg['anf_enabled'],
                                        agc_mode=cfg['agc_mode']
                                    )
                                    self.wdsp_processor.set_bandpass(cfg['bandpass_low'], cfg['bandpass_high'])
                                    if cfg['nr2_enabled']:
                                        self.wdsp_processor.set_nr2_level(cfg.get('nr2_level', 2))
                                else:
                                    self.wdsp_processor.set_nr2_level(cfg.get('nr2_level', 2) if cfg['nr2_enabled'] else 0)
                                    self.wdsp_processor.set_nb_enabled(cfg['nb_enabled'])
                                    self.wdsp_processor.set_anf_enabled(cfg['anf_enabled'])
                                    self.wdsp_processor.set_agc_mode(cfg['agc_mode'])
                                    self.wdsp_processor.set_bandpass(cfg['bandpass_low'], cfg['bandpass_high'])
                                    # nr2_ae_run 已由 set_nr2_level() 内置管理，无需额外设置
                        except Exception as e:
                            pass
                        
                        # V5.2: WDSP 处理 — 在 try/except 之外，每帧必执行
                        cfg = PyAudioCapture.wdsp_config
                        wdsp_buffer_size = cfg['buffer_size']
                        wdsp_sample_rate = 48000
                        
                        self.wdsp_resample_buffer = np.concatenate([self.wdsp_resample_buffer, int16_data])
                        
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
                                float_output = int16_data.astype(np.float32) / 32767.0
                                soft_clip_threshold = 0.95
                                float_output = np.tanh(float_output / soft_clip_threshold) * soft_clip_threshold
                                int16_data = (float_output * 32767.0).astype(np.int16)
                            except Exception:
                                pass
                    
                    # 发送到客户端队列
                    try:
                        import sys
                        main_module = sys.modules['__main__']
                        if hasattr(main_module, 'AudioRXHandlerClients'):
                            global AudioRXHandlerClients
                            AudioRXHandlerClients = getattr(main_module, 'AudioRXHandlerClients')
                            client_count = len(AudioRXHandlerClients)

                            if client_count > 0:
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
                                    source_rate = 48000  # PyAudio 捕获采样率
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
                                                self.rx_opus_encoder = OpusEncoder(
                                                    current_opus_rate, 1, 2048
                                                )
                                                self.rx_opus_encoder_rate = current_opus_rate
                                                self.rx_opus_encoder.configure_for_voip(
                                                    bitrate=28000, complexity=8,
                                                    fec=True, packet_loss_perc=15, dtx=True
                                                )
                                            except Exception as e:
                                                PyAudioCapture.rx_opus_encode = False
                                                break
                                        
                                        # 自适应 Opus 比特率：队列深度反映网络状况
                                        qlen = max(len(c.Wavframes) for c in AudioRXHandlerClients) if AudioRXHandlerClients else 0
                                        target_bps = 32000 if qlen < 5 else (24000 if qlen < 15 else 16000)
                                        if target_bps != getattr(self, '_rx_opus_bitrate', -1):
                                            try:
                                                self.rx_opus_encoder.bitrate = target_bps
                                                self._rx_opus_bitrate = target_bps
                                            except Exception:
                                                pass
                                        
                                        # 编码
                                        try:
                                            frame_bytes = frame_data.tobytes()
                                            encoded_data = self.rx_opus_encoder.encode(frame_bytes, opus_frame_size)
                                            
                                            # 发送到客户端
                                            # 弱网优化：智能队列管理
                                            # 根据队列深度动态调整策略
                                            for c in AudioRXHandlerClients:
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
                                    source_rate = 48000  # PyAudio 捕获采样率
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
                                    # 弱网优化：智能队列管理
                                    for c in AudioRXHandlerClients:
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
        """Close the audio stream"""
        if self.stream.is_active():
            self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
    
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

                # 生成文件名: 频率(kHz)_日期_时间.wav
                freq_khz = int(PyAudioCapture.recording_freq / 1000) if PyAudioCapture.recording_freq > 0 else 0
                now = datetime.now()
                date_str = now.strftime('%Y%m%d')
                time_str = now.strftime('%H%M%S')
                filename = f"{freq_khz:05d}kHz_{date_str}_{time_str}.wav"
                filepath = os.path.join(PyAudioCapture.recording_dir, filename)

                # 保存为 WAV 文件 (16kHz, 16bit, stereo)
                with wave.open(filepath, 'wb') as wf:
                    wf.setnchannels(2)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(16000)  # 16kHz
                    wf.writeframes(stereo_data.tobytes())

                duration = max_len / 16000
                print(f"✅ 录音已保存 (立体声): {filename} ({duration:.1f}秒, L={len(rx_data)} R={len(tx_data)}, {os.path.getsize(filepath)} bytes)")
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
    
    def write(self, data):
        """Write audio data to output stream with TX level normalization"""
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
                tx_int16 = np.clip(tx_int16 * self._tx_gain_smooth, -32767, 32767).astype(np.int16)
            pcm = tx_int16.tobytes()

        self.stream.write(pcm)
    
    def close(self):
        """Close the audio stream"""
        if self.stream.is_active():
            self.stream.stop_stream()
        self.stream.close()
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
            if filename.endswith('.wav'):
                filepath = os.path.join(recording_dir, filename)
                stat = os.stat(filepath)
                
                # 解析文件名获取频率和时间
                # 格式: 频率(kHz)_日期_时间.wav
                parts = filename.replace('.wav', '').split('_')
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
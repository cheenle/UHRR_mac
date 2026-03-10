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
    rx_opus_encoder = None  # Opus 编码器实例
    
    # RNNoise 降噪设置
    rnnoise_enabled = False
    rnnoise_suppress_level = 50
    
    # WDSP 设置
    wdsp_enabled = False
    wdsp_config = {}
    
    # 帧序号（用于FEC丢包检测）
    _frame_sequence = 0
    _sequence_lock = threading.Lock()
    
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
                frames_per_buffer=256  # 优化：从512减至256，降低延迟约16ms
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
                    frames_per_buffer=256  # 优化：从512减至256，降低延迟约16ms
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
                        frames_per_buffer=256  # 优化：从512减至256，降低延迟约16ms
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
                data = self.stream.read(256, exception_on_overflow=False)
                
                if len(data) > 0:
                    frame_count += 1
                    
                    # 每 5 秒打印一次状态
                    current_time = time.time()
                    if current_time - last_log_time >= 5.0:
                        # 动态读取类变量
                        current_opus_mode = PyAudioCapture.rx_opus_encode
                        encode_mode = "Opus" if current_opus_mode else "Int16"
                        print(f"🎵 音频捕获正常... 帧数: {frame_count}, 模式: {encode_mode}, 数据长度: {len(data)}")
                        last_log_time = current_time
                    
                    # Convert stereo to mono if needed
                    if self.stereo_mode:
                        stereo_data = np.frombuffer(data, dtype=np.float32)
                        stereo_data = stereo_data.reshape(-1, 2)
                        mono_data = np.mean(stereo_data, axis=1)
                        data = mono_data.tobytes()
                    
                    # Convert Float32 to Int16 for 50% bandwidth reduction
                    float32_data = np.frombuffer(data, dtype=np.float32)
                    
                    # 音频优化：提升语音质量
                    # 1. 去除直流偏移
                    dc_offset = np.mean(float32_data)
                    if abs(dc_offset) > 0.001:
                        float32_data = float32_data - dc_offset
                    
                    # 2. 自动增益控制 (AGC) - 提升弱信号
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
                    
                    # ========== WDSP 数字信号处理 ==========
                    # 在 Int16 转换后、Opus编码前进行 WDSP 处理

                    # 调试：定期打印 WDSP 状态
                    if frame_count % 100 == 0:
                        cfg = PyAudioCapture.wdsp_config
                        print(f"🔍 WDSP: enabled={PyAudioCapture.wdsp_enabled}, processor={'存在' if self.wdsp_processor else 'None'}, NR2={cfg.get('nr2_enabled', False)}(L{cfg.get('nr2_level', 0)}), AGC={cfg.get('agc_mode', 0)}")

                    # 如果 WDSP 被禁用但处理器还存在，清理它
                    if not PyAudioCapture.wdsp_enabled and self.wdsp_processor is not None:
                        try:
                            print("🔧 WDSP 已禁用，关闭处理器")
                            self.wdsp_processor.close()
                            self.wdsp_processor = None
                            self.wdsp_resample_buffer = np.array([], dtype=np.int16)
                            # 强制垃圾回收，确保资源释放
                            import gc
                            gc.collect()
                            print("🔧 WDSP 处理器已完全关闭")
                        except Exception as e:
                            print(f"⚠️ 关闭 WDSP 处理器错误: {e}")
                    
                    if PyAudioCapture.wdsp_enabled and WDSP_AVAILABLE:
                        try:
                            # 延迟初始化 WDSP 处理器
                            if self.wdsp_processor is None:
                                cfg = PyAudioCapture.wdsp_config
                                # 强制使用 48000Hz，与 PyAudio 捕获采样率一致
                                # 避免采样率转换导致的音质劣化
                                wdsp_sr = 48000
                                wdsp_bs = cfg.get('buffer_size', 256)
                                self.wdsp_processor = WDSPProcessor(
                                    sample_rate=wdsp_sr,
                                    buffer_size=wdsp_bs,
                                    mode=WDSPMode.USB,
                                    enable_nr2=cfg['nr2_enabled'],
                                    enable_nb=cfg['nb_enabled'],
                                    enable_anf=cfg['anf_enabled'],
                                    agc_mode=cfg['agc_mode']
                                )
                                # 设置带通滤波器
                                self.wdsp_processor.set_bandpass(
                                    cfg['bandpass_low'],
                                    cfg['bandpass_high']
                                )
                                # 设置 NR2 强度级别
                                if cfg['nr2_enabled'] and 'nr2_level' in cfg:
                                    self.wdsp_processor.set_nr2_level(cfg['nr2_level'])
                                # 设置 NR2 自动均衡（必须开启以消除音乐噪音）
                                if cfg['nr2_enabled'] and 'nr2_ae_run' in cfg:
                                    self.wdsp_processor.set_nr2_ae_run(cfg['nr2_ae_run'])
                                print(f"🔧 WDSP 处理器已初始化: {wdsp_sr}Hz, NR2={cfg['nr2_enabled']}(level={cfg.get('nr2_level', 1)}, ae={cfg.get('nr2_ae_run', True)}), NB={cfg['nb_enabled']}")
                            else:
                                # 动态同步配置参数
                                cfg = PyAudioCapture.wdsp_config
                                
                                # 检查并更新 NR2 级别
                                if hasattr(self.wdsp_processor, '_nr2_level') and \
                                   hasattr(self.wdsp_processor, '_nr2_enabled'):
                                    # 获取目标状态
                                    target_level = cfg.get('nr2_level', 1)
                                    # 关键：level > 0 时 enabled 必须为 True
                                    target_enabled = target_level > 0
                                    
                                    # 获取当前状态
                                    current_enabled = self.wdsp_processor._nr2_enabled
                                    current_level = getattr(self.wdsp_processor, '_nr2_level', -1)
                                    
                                    # 只有状态真正变化时才更新
                                    if current_enabled != target_enabled or current_level != target_level:
                                        print(f"🔄 NR2 更新: 当前={current_level}({'开' if current_enabled else '关'}), 目标={target_level}({'开' if target_enabled else '关'})")
                                        if target_enabled and target_level > 0:
                                            self.wdsp_processor.set_nr2_level(target_level)
                                        else:
                                            self.wdsp_processor.set_nr2_level(0)
                                
                                # 检查并更新 NR2 高级设置
                                if hasattr(self.wdsp_processor, 'set_nr2_gain_method'):
                                    target_gain_method = cfg.get('nr2_gain_method', 0)
                                    current_gain_method = getattr(self.wdsp_processor, '_nr2_gain_method', -1)
                                    if current_gain_method != target_gain_method:
                                        self.wdsp_processor.set_nr2_gain_method(target_gain_method)
                                
                                if hasattr(self.wdsp_processor, 'set_nr2_npe_method'):
                                    target_npe_method = cfg.get('nr2_npe_method', 1)
                                    current_npe_method = getattr(self.wdsp_processor, '_nr2_npe_method', -1)
                                    if current_npe_method != target_npe_method:
                                        self.wdsp_processor.set_nr2_npe_method(target_npe_method)
                                
                                if hasattr(self.wdsp_processor, 'set_nr2_ae_run'):
                                    target_ae_run = cfg.get('nr2_ae_run', False)
                                    current_ae_run = getattr(self.wdsp_processor, '_nr2_ae_run', None)
                                    if current_ae_run != target_ae_run:
                                        self.wdsp_processor.set_nr2_ae_run(target_ae_run)
                                
                                # 检查并更新 NB
                                if hasattr(self.wdsp_processor, '_nb_enabled') and \
                                   self.wdsp_processor._nb_enabled != cfg['nb_enabled']:
                                    self.wdsp_processor.set_nb_enabled(cfg['nb_enabled'])
                                
                                # 检查并更新 ANF
                                if hasattr(self.wdsp_processor, '_anf_enabled') and \
                                   self.wdsp_processor._anf_enabled != cfg['anf_enabled']:
                                    self.wdsp_processor.set_anf_enabled(cfg['anf_enabled'])
                                
                                # 检查并更新 AGC
                                if hasattr(self.wdsp_processor, '_agc_mode') and \
                                   self.wdsp_processor._agc_mode != cfg['agc_mode']:
                                    self.wdsp_processor.set_agc_mode(cfg['agc_mode'])
                                
                                # 检查并更新带通滤波器
                                if hasattr(self.wdsp_processor, 'set_bandpass'):
                                    target_low = cfg.get('bandpass_low', 300)
                                    target_high = cfg.get('bandpass_high', 2700)
                                    current_low = getattr(self.wdsp_processor, '_bandpass_low', -1)
                                    current_high = getattr(self.wdsp_processor, '_bandpass_high', -1)
                                    if current_low != target_low or current_high != target_high:
                                        self.wdsp_processor.set_bandpass(target_low, target_high)
                            
                            # WDSP 直接处理 48kHz 数据，无需降采样/升采样
                            # 避免重复采样导致的音质劣化
                            cfg = PyAudioCapture.wdsp_config
                            wdsp_buffer_size = cfg['buffer_size']
                            # 强制使用 48kHz，与 PyAudio 捕获采样率一致
                            wdsp_sample_rate = 48000
                            
                            # 累积到 WDSP 缓冲区
                            self.wdsp_resample_buffer = np.concatenate([self.wdsp_resample_buffer, int16_data])
                            
                            # 处理完整缓冲区
                            processed_frames = []
                            while len(self.wdsp_resample_buffer) >= wdsp_buffer_size:
                                # 取出一帧
                                frame = self.wdsp_resample_buffer[:wdsp_buffer_size]
                                self.wdsp_resample_buffer = self.wdsp_resample_buffer[wdsp_buffer_size:]
                                
                                # 通过 WDSP 处理
                                processed = self.wdsp_processor.process(frame)
                                # 只使用有效输出（WDSP 启动时可能有 -2 错误，返回原始数据）
                                if processed is not None and len(processed) > 0:
                                    # 验证输出长度与输入一致
                                    if len(processed) != len(frame):
                                        if frame_count % 100 == 0:
                                            print(f"⚠️ WDSP 输出长度不一致: in={len(frame)}, out={len(processed)}")
                                        processed = frame  # 使用原始数据
                                    processed_frames.append(processed)
                            
                            # 合并处理后的帧
                            if processed_frames:
                                int16_data = np.concatenate(processed_frames)
                                # 调试：显示WDSP处理效果（输入vs输出能量对比）
                                if frame_count % 100 == 0:
                                    in_energy = np.sum(np.abs(frame.astype(np.float64)))
                                    out_energy = np.sum(np.abs(int16_data.astype(np.float64)))
                                    ratio = out_energy / in_energy if in_energy > 0 else 0
                                    print(f"🔍 WDSP 能量: 输入={in_energy:.0f}, 输出={out_energy:.0f}, 比例={ratio:.2f}")
                            else:
                                # 没有处理帧（缓冲区未满），使用原始数据
                                # 这样可以避免 WDSP 启动时的音频丢失
                                pass
                            # 保持 48kHz，后续 Opus 编码前统一降采样
                            
                            # 每 100 帧获取一次 S-meter 读数
                            if frame_count % 100 == 0:
                                smeter = self.wdsp_processor.get_meter(WDSPMeterType.S_PK)
                                # 可以在这里将 S-meter 值存储到全局变量供前端读取
                                
                        except Exception as e:
                            if frame_count % 100 == 0:
                                print(f"⚠️ WDSP 处理错误: {e}")
                                import traceback
                                traceback.print_exc()
                    
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
                                        
                                        # 初始化 Opus 编码器（如果需要或参数变化）
                                        if self.rx_opus_encoder is None or self.rx_opus_encoder_rate != current_opus_rate:
                                            try:
                                                # OpusEncoder 只需要 3 个参数：采样率、声道数、应用类型
                                                # 2048 = OPUS_APPLICATION_VOIP（语音优化）
                                                self.rx_opus_encoder = OpusEncoder(
                                                    current_opus_rate, 1, 2048
                                                )
                                                self.rx_opus_encoder_rate = current_opus_rate
                                                
                                                # ========== Opus 深度优化 ==========
                                                # 启用FEC抗丢包、DTX静音检测、优化比特率
                                                # 这些参数针对弱网环境和短波语音通信优化
                                                self.rx_opus_encoder.configure_for_voip(
                                                    bitrate=20000,       # 20kbps 短波语音足够
                                                    complexity=6,        # 中等复杂度，移动端友好
                                                    fec=True,            # 启用前向纠错（关键！）
                                                    packet_loss_perc=15, # 预期15%丢包率
                                                    dtx=True             # 启用静音检测
                                                )
                                                print(f"🎵 Opus RX 编码器已优化: {current_opus_rate}Hz, FEC=ON, DTX=ON, 20kbps")
                                            except Exception as e:
                                                print(f"❌ Opus RX 编码器初始化失败: {e}")
                                                PyAudioCapture.rx_opus_encode = False
                                                break
                                        
                                        # 编码
                                        try:
                                            # 使用OpusEncoder的encode方法
                                            # 将numpy数组转换为bytes
                                            frame_bytes = frame_data.tobytes()
                                            
                                            # 调试：打印编码参数
                                            if frame_count % 100 == 0:
                                                print(f"🔍 Opus编码参数: frame_size={opus_frame_size}, input_len={len(frame_bytes)}")
                                            
                                            # 调用编码方法
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
                                            # 每 100 帧打印一次编码结果
                                            if frame_count % 100 == 0:
                                                print(f"🎵 Opus 编码正常... 帧数: {frame_count}, 压缩率: {len(encoded_data)}/{len(frame_bytes)}")
                                        except Exception as e:
                                            if frame_count % 100 == 0:
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

class PyAudioPlayback:
    """PyAudio-based replacement for ALSA playback"""
    
    def __init__(self, config, itrate, is_encoded, op_rate, op_frm_dur):
        self.config = config
        self.itrate = itrate
        self.is_encoded = is_encoded
        self.op_rate = op_rate
        self.op_frm_dur = op_frm_dur
        
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
                frames_per_buffer=256  # 优化：从512减至256，降低延迟约16ms
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
                    frames_per_buffer=256  # 优化：从512减至256，降低延迟约16ms
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
        """Write audio data to output stream"""
        if self.is_encoded:
            # Decode Opus data first
            pcm = self.decoder.decode(data, self.frame_size, False)
            self.stream.write(pcm)
        else:
            self.stream.write(data)
    
    def close(self):
        """Close the audio stream"""
        if self.stream.is_active():
            self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
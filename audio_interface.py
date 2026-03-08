#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cross-platform audio interface using PyAudio
Replaces the ALSA-specific implementation in the original code

支持 Opus 端到端编解码:
- TX: 前端 Opus 编码 → 后端 Opus 解码 → 电台
- RX: 电台 → 后端 Opus 编码 → 前端 Opus 解码
"""

import pyaudio
import threading
import time
import gc
import numpy as np
from opus.decoder import Decoder as OpusDecoder
from opus.encoder import Encoder as OpusEncoder


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
    
    # 帧序号（用于FEC丢包检测）
    _frame_sequence = 0
    _sequence_lock = threading.Lock()
    
    def __init__(self, config):
        threading.Thread.__init__(self)
        self.config = config
        
        # Opus 编码器实例（延迟初始化）
        self.rx_opus_encoder = None
        self.rx_opus_encoder_rate = 0  # 用于检测参数变化
        
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
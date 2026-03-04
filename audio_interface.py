#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cross-platform audio interface using PyAudio
Replaces the ALSA-specific implementation in the original code
"""

import pyaudio
import threading
import time
import gc
import numpy as np
from opus.decoder import Decoder as OpusDecoder


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
    """PyAudio-based replacement for ALSA capture"""
    
    def __init__(self, config):
        threading.Thread.__init__(self)
        self.config = config
        
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
                rate=16000,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=256  # 优化：从512减至256，降低延迟约16ms
            )
            print(f'PyAudio input stream opened successfully with {device_channels} channel(s) at 16000 Hz')
            self.stereo_mode = (device_channels == 2)
        except Exception as e:
            print(f"Failed to open PyAudio input stream with {device_channels} channels: {e}")
            # Fall back to mono
            try:
                self.stream = self.p.open(
                    format=pyaudio.paFloat32,
                    channels=1,
                    rate=16000,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=256  # 优化：从512减至256，降低延迟约16ms
                )
                print('PyAudio input stream opened successfully with MONO (1 channel) at 16000 Hz - fallback')
                self.stereo_mode = False
            except Exception as e2:
                print(f"Failed to open mono PyAudio input stream: {e2}")
                # Try with default device
                try:
                    self.stream = self.p.open(
                        format=pyaudio.paFloat32,
                        channels=1,
                        rate=16000,
                        input=True,
                        frames_per_buffer=256  # 优化：从512减至256，降低延迟约16ms
                    )
                    print('Opened with default input device (mono) at 16000 Hz')
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
        
        while True:
            try:
                # 使用非阻塞读取，避免线程被阻塞
                data = self.stream.read(256, exception_on_overflow=False)
                
                if len(data) > 0:
                    frame_count += 1
                    
                    # 每 5 秒打印一次状态
                    current_time = time.time()
                    if current_time - last_log_time >= 5.0:
                        print(f"🎵 音频捕获正常... 帧数: {frame_count}, 数据长度: {len(data)}")
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
                    compressed_data = int16_data.tobytes()
                    
                    # 发送到客户端队列
                    try:
                        import sys
                        main_module = sys.modules['__main__']
                        if hasattr(main_module, 'AudioRXHandlerClients'):
                            global AudioRXHandlerClients
                            AudioRXHandlerClients = getattr(main_module, 'AudioRXHandlerClients')
                            client_count = len(AudioRXHandlerClients)

                            if client_count > 0:
                                for c in AudioRXHandlerClients:
                                    # 限制每个客户端的队列长度，防止积压
                                    if len(c.Wavframes) < 20:
                                        c.Wavframes.append(compressed_data)
                                    else:
                                        # 队列满时丢弃最旧的帧
                                        c.Wavframes.pop(0)
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
                rate=itrate,
                output=True,
                output_device_index=device_index,
                frames_per_buffer=256  # 优化：从512减至256，降低延迟约16ms
            )
            print(f'PyAudio output stream opened successfully at {itrate}Hz with low latency settings')
        except Exception as e:
            print(f"Failed to open PyAudio output stream: {e}")
            # Try with default device
            try:
                self.stream = self.p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=itrate,
                    output=True,
                    frames_per_buffer=256  # 优化：从512减至256，降低延迟约16ms
                )
                print('Opened with default output device')
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
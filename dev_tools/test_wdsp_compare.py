#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WDSP 快速对比测试 - 一次录音生成多个配置
"""

import pyaudio
import numpy as np
import wave
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wdsp_wrapper import WDSPProcessor, WDSPAGCMode, _wdsp
import ctypes

CHUNK = 512
FORMAT = pyaudio.paFloat32
CHANNELS = 2  # USB Audio CODEC 是立体声
RATE = 48000
DURATION = 10

OUTPUT_DIR = "/Users/cheenle/UHRR/MRRC/dev_tools"

def get_default_input_device():
    p = pyaudio.PyAudio()
    try:
        # 优先使用 MRRC 配置的声卡 - 找输入设备
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0 and 'USB Audio CODEC' in info['name']:
                print(f"🎯 找到 MRRC 声卡输入: {info['name']} ({info['maxInputChannels']} 通道)")
                return i
        # 备用默认设备
        return p.get_default_input_device_info()['index']
    finally:
        p.terminate()

def record_with_wdsp(duration, output_file, device_index, agc_mode, nr2_level, nr2_ae=True):
    """使用 WDSP 录音"""
    p = pyaudio.PyAudio()
    
    try:
        # 初始化 WDSP (使用 256 帧缓冲区，与主程序一致)
        wdsp = WDSPProcessor(
            sample_rate=RATE,
            buffer_size=256,
            mode=1,  # USB
            enable_nr2=True,
            enable_nb=False,
            enable_anf=False,
            agc_mode=agc_mode
        )
        wdsp.set_nr2_level(nr2_level)
        
        # 设置 AE (使用对象方法，确保 channel 已初始化)
        wdsp.set_nr2_ae_run(nr2_ae)
        
        # 打开音频流
        stream = p.open(
            format=FORMAT, channels=CHANNELS, rate=RATE,
            input=True, input_device_index=device_index,
            frames_per_buffer=CHUNK
        )
        
        # 录音
        wav = wave.open(output_file, 'wb')
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        
        total = int(RATE // CHUNK * duration)
        wdsp_buffer_size = 256  # 与 WDSP 初始化一致
        for i in range(total):
            data = stream.read(CHUNK, exception_on_overflow=False)
            # USB Audio CODEC: 麦克风在右声道 (索引 1,3,5...)
            audio = np.frombuffer(data, dtype=np.float32)
            audio_mono = audio[1::2]  # 只取右声道
            audio_float64 = audio_mono.astype(np.float64)
            
            # 将 512 帧分成两个 256 帧处理（与主程序逻辑一致）
            processed_frames = []
            for j in range(0, len(audio_float64), wdsp_buffer_size):
                frame = audio_float64[j:j+wdsp_buffer_size]
                if len(frame) == wdsp_buffer_size:  # 只处理完整帧
                    processed_frame = wdsp.process(frame)
                    if processed_frame is not None and len(processed_frame) == wdsp_buffer_size:
                        processed_frames.append(processed_frame)
                    else:
                        # WDSP 输出异常，使用原始数据
                        processed_frames.append(frame)
            
            if processed_frames:
                processed = np.concatenate(processed_frames)
                # 转换为立体声（复制到左右声道）
                stereo = np.zeros(len(processed) * 2, dtype=np.int16)
                stereo[0::2] = (processed * 32767).astype(np.int16)  # 左声道
                stereo[1::2] = (processed * 32767).astype(np.int16)  # 右声道
                wav.writeframes(stereo.tobytes())
            
            if (i+1) % (RATE//CHUNK) == 0:
                print(f"  { (i+1)//(RATE//CHUNK) }/{duration}s", end='\r')
        
        wav.close()
        stream.close()
        wdsp.close()
        p.terminate()
        return True
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        if 'wdsp' in locals():
            wdsp.close()
        p.terminate()
        return False


def record_raw(duration, output_file, device_index):
    """无 WDSP 处理 - 原始录音"""
    p = pyaudio.PyAudio()
    
    try:
        stream = p.open(
            format=FORMAT, channels=CHANNELS, rate=RATE,
            input=True, input_device_index=device_index,
            frames_per_buffer=CHUNK
        )
        
        wav = wave.open(output_file, 'wb')
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        
        total = int(RATE // CHUNK * duration)
        for i in range(total):
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio = np.frombuffer(data, dtype=np.float32)
            wav.writeframes((audio * 32767).astype(np.int16).tobytes())
            if (i+1) % (RATE//CHUNK) == 0:
                print(f"  { (i+1)//(RATE//CHUNK) }/{duration}s", end='\r')
        
        wav.close()
        stream.close()
        p.terminate()
        return True
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        p.terminate()
        return False


print("\n" + "="*60)
print("🎛️  WDSP 对比测试")
print("="*60)

device = get_default_input_device()
print(f"🎤 设备: {device}")

tests = [
    ("1_原始无WDSP.wav", "原始", "无处理", lambda: record_raw(DURATION, os.path.join(OUTPUT_DIR, "1_原始无WDSP.wav"), device)),
    ("2_WDSP_OFF_L1.wav", "AGC OFF + NR2 L1", "agc=0,nr2=1", lambda: record_with_wdsp(DURATION, os.path.join(OUTPUT_DIR, "2_WDSP_OFF_L1.wav"), device, WDSPAGCMode.OFF, 1, True)),
    ("3_WDSP_SLOW_L1.wav", "AGC SLOW + NR2 L1", "agc=2,nr2=1", lambda: record_with_wdsp(DURATION, os.path.join(OUTPUT_DIR, "3_WDSP_SLOW_L1.wav"), device, WDSPAGCMode.SLOW, 1, True)),
    ("4_WDSP_SLOW_L3.wav", "AGC SLOW + NR2 L3", "agc=2,nr2=3", lambda: record_with_wdsp(DURATION, os.path.join(OUTPUT_DIR, "4_WDSP_SLOW_L3.wav"), device, WDSPAGCMode.SLOW, 3, True)),
    ("5_WDSP_SLOW_L5.wav", "AGC SLOW + NR2 L5", "agc=2,nr2=5", lambda: record_with_wdsp(DURATION, os.path.join(OUTPUT_DIR, "5_WDSP_SLOW_L5.wav"), device, WDSPAGCMode.SLOW, 5, True)),
]

print("\n准备测试... 请对着麦克风说话或播放音频")
print("开始录音...\n")

for idx, (filename, desc, params, func) in enumerate(tests):
    print(f"\n[{idx+1}/{len(tests)}] {desc} ({params})")
    func()
    print(f"  ✅ {filename}")
    if idx < len(tests) - 1:
        print("  ⏳ 准备下一个...")
        import time; time.sleep(1)

print("\n" + "="*60)
print("✅ 完成！生成的文件:")
print("="*60)
for f, d, p, _ in tests:
    filepath = os.path.join(OUTPUT_DIR, f)
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        print(f"  {f} - {size/1024:.1f}KB ({d})")
    else:
        print(f"  {f} - (文件不存在)")

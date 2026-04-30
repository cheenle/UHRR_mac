#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用优化的参数测试WDSP NF功能
增加更宽的陷波来更好地消除CW
"""

import sys
sys.path.insert(0, '/Users/cheenle/UHRR/MRRC')

import numpy as np
import wave
from wdsp_wrapper import WDSPProcessor, WDSPMode

def process_wav_with_notch(input_file, output_file, notch_freq=1475, notch_width=300):
    """使用WDSP NF处理WAV文件"""
    
    # 读取WAV文件
    with wave.open(input_file, 'rb') as wf:
        n_channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        
        print(f"输入文件: {input_file}")
        print(f"  采样率: {sample_rate} Hz")
        
        audio_data = wf.readframes(n_frames)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        if n_channels == 2:
            audio_array = audio_array.reshape(-1, 2).mean(axis=1).astype(np.int16)
    
    # 创建WDSP处理器
    print("\n初始化WDSP处理器...")
    processor = WDSPProcessor(
        sample_rate=48000,
        buffer_size=256,
        mode=WDSPMode.USB,
        enable_nr2=False,
        enable_nb=False,
        enable_anf=False,
        agc_mode=3
    )
    
    # 启用Notch Filter
    print("启用Notch Filter...")
    processor.set_notches_enabled(True)
    
    # 添加更宽的陷波点
    print(f"添加主陷波点: {notch_freq}Hz, 宽度: {notch_width}Hz")
    result = processor.add_notch(notch_freq, notch_width)
    print(f"  结果: 索引={result}")
    
    # 重采样到48kHz
    if sample_rate != 48000:
        print(f"\n重采样: {sample_rate}Hz -> 48000Hz")
        old_length = len(audio_array)
        new_length = int(old_length * 48000 / sample_rate)
        indices = np.linspace(0, old_length - 1, new_length)
        audio_array = np.interp(indices, np.arange(old_length), audio_array).astype(np.int16)
    
    # 分帧处理
    print("\n处理音频数据...")
    buffer_size = 256
    processed_frames = []
    
    # WDSP预热
    print("WDSP预热...")
    for _ in range(20):
        processor.process(np.zeros(buffer_size, dtype=np.int16))
    
    # 处理实际音频
    for i in range(0, len(audio_array), buffer_size):
        frame = audio_array[i:i+buffer_size]
        if len(frame) < buffer_size:
            frame = np.pad(frame, (0, buffer_size - len(frame)), 'constant')
        
        processed = processor.process(frame)
        if processed is not None and len(processed) > 0:
            processed_frames.append(processed)
        else:
            processed_frames.append(frame)
    
    processed_audio = np.concatenate(processed_frames)
    
    # 重采样回原始采样率
    if sample_rate != 48000:
        print(f"重采样回原始采样率: 48000Hz -> {sample_rate}Hz")
        old_length = len(processed_audio)
        new_length = int(old_length * sample_rate / 48000)
        indices = np.linspace(0, old_length - 1, new_length)
        processed_audio = np.interp(indices, np.arange(old_length), processed_audio).astype(np.int16)
    
    # 保存输出文件
    print(f"\n保存输出文件: {output_file}")
    with wave.open(output_file, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(processed_audio.tobytes())
    
    processor.close()
    
    print("\n✅ 处理完成！")
    print(f"   陷波频率: {notch_freq}Hz")
    print(f"   陷波宽度: {notch_width}Hz (更宽，覆盖更多)")

if __name__ == "__main__":
    input_file = "/Users/cheenle/UHRR/MRRC/recordings/07050kHz_20260402_070548.wav"
    output_file = "/Users/cheenle/UHRR/MRRC/recordings/07050kHz_20260402_070548_nf_optimized.wav"
    
    try:
        # 使用300Hz宽度，覆盖1475Hz附近的干扰
        process_wav_with_notch(input_file, output_file, notch_freq=1475, notch_width=300)
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

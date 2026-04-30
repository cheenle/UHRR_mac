#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 WDSP NF (Notch Filter) 功能
处理录音文件，添加 1486Hz 陷波点
"""

import sys
sys.path.insert(0, '/Users/cheenle/UHRR/MRRC')

import numpy as np
import wave
from wdsp_wrapper import WDSPProcessor, WDSPMode

def process_wav_with_notch(input_file, output_file, notch_freq=1486, notch_width=100):
    """使用 WDSP NF 处理 WAV 文件"""
    
    # 读取 WAV 文件
    with wave.open(input_file, 'rb') as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        
        print(f"输入文件: {input_file}")
        print(f"  通道数: {n_channels}")
        print(f"  采样率: {sample_rate} Hz")
        print(f"  采样宽度: {sample_width} bytes")
        print(f"  总帧数: {n_frames}")
        
        # 读取音频数据
        audio_data = wf.readframes(n_frames)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # 如果是立体声，转换为单声道
        if n_channels == 2:
            audio_array = audio_array.reshape(-1, 2).mean(axis=1).astype(np.int16)
            print("  已转换为单声道")
    
    # 创建 WDSP 处理器
    print("\n初始化 WDSP 处理器...")
    processor = WDSPProcessor(
        sample_rate=48000,  # WDSP 使用 48kHz
        buffer_size=256,
        mode=WDSPMode.USB,
        enable_nr2=False,
        enable_nb=False,
        enable_anf=False,
        agc_mode=3
    )
    
    # 启用 Notch Filter
    print("启用 Notch Filter...")
    processor.set_notches_enabled(True)
    
    # 添加陷波点
    print(f"添加陷波点: {notch_freq}Hz, 宽度: {notch_width}Hz")
    result = processor.add_notch(notch_freq, notch_width)
    if result < 0:
        print(f"⚠️ 添加陷波点失败: {result}")
    else:
        print(f"✅ 陷波点已添加，索引: {result}")
    
    # 如果采样率不是 48kHz，需要重采样
    if sample_rate != 48000:
        print(f"\n重采样: {sample_rate}Hz -> 48000Hz")
        # 简单线性重采样
        old_length = len(audio_array)
        new_length = int(old_length * 48000 / sample_rate)
        indices = np.linspace(0, old_length - 1, new_length)
        audio_array = np.interp(indices, np.arange(old_length), audio_array).astype(np.int16)
    
    # 分帧处理
    print("\n处理音频数据...")
    buffer_size = 256
    processed_frames = []
    
    # 添加一些静音填充，确保 WDSP 有足够数据启动
    padding = np.zeros(buffer_size * 10, dtype=np.int16)
    audio_array = np.concatenate([padding, audio_array, padding])
    
    for i in range(0, len(audio_array), buffer_size):
        frame = audio_array[i:i+buffer_size]
        
        # 确保帧长度正确
        if len(frame) < buffer_size:
            frame = np.pad(frame, (0, buffer_size - len(frame)), 'constant')
        
        # 通过 WDSP 处理
        processed = processor.process(frame)
        
        if processed is not None and len(processed) > 0:
            processed_frames.append(processed)
        else:
            processed_frames.append(frame)
    
    # 合并处理后的帧
    processed_audio = np.concatenate(processed_frames)
    
    # 移除填充
    processed_audio = processed_audio[len(padding):len(padding)+len(audio_array)-2*len(padding)]
    
    # 如果原始采样率不是 48kHz，重采样回去
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
    
    # 关闭处理器
    processor.close()
    
    print("\n✅ 处理完成！")
    print(f"   原始文件: {input_file}")
    print(f"   处理后文件: {output_file}")
    print(f"   陷波频率: {notch_freq}Hz")
    print(f"   陷波宽度: {notch_width}Hz")

if __name__ == "__main__":
    input_file = "/Users/cheenle/UHRR/MRRC/recordings/07050kHz_20260402_070548.wav"
    output_file = "/Users/cheenle/UHRR/MRRC/recordings/07050kHz_20260402_070548_nf.wav"
    
    try:
        process_wav_with_notch(input_file, output_file, notch_freq=1486, notch_width=100)
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

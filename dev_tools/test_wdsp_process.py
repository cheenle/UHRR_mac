#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WDSP 音频处理测试工具
用法: python3 test_wdsp_process.py [录音秒数] [输出文件名]

示例:
  python3 test_wdsp_process.py 10 test_with_wdsp.wav
"""

import pyaudio
import numpy as np
import wave
import sys
import os

# 添加项目根目录到路径
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wdsp_wrapper import WDSPProcessor, WDSPAGCMode, _wdsp
import ctypes

# 配置参数
CHUNK = 512          # 每次读取的帧数
FORMAT = pyaudio.paFloat32
CHANNELS = 2  # USB Audio CODEC 是立体声
RATE = 48000         # WDSP 需要 48kHz

# 使用 USB Audio CODEC (服务器声卡)
DEVICE_INDEX = 3  # USB Audio CODEC 输入
OUTPUT_DEVICE_INDEX = 2  # USB Audio CODEC 输出

# NR2 参数配置
NR2_ENABLED = True   # 开启 NR2
NR2_LEVEL = 3        # NR2 Level 3

# WDSP 功能开关
WDSP_ENABLED = True  # 开启 WDSP
NR2_GAIN_METHOD = 0  # 0=Gaussian保守, 1=中等, 2=Gamma激进
NR2_NPE_METHOD = 0   # 0=OSMS, 1=MMSE
NR2_AE_RUN = True    # 自动均衡

# AGC 参数
AGC_MODE = WDSPAGCMode.SLOW  # SLOW

def list_audio_devices():
    """列出所有音频设备"""
    p = pyaudio.PyAudio()
    print("\n🎤 可用音频输入设备:")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            print(f"  [{i}] {info['name']}")
    p.terminate()
    return None

def get_default_input_device():
    """获取默认输入设备"""
    p = pyaudio.PyAudio()
    try:
        default_info = p.get_default_input_device_info()
        print(f"🎯 默认输入设备: {default_info['name']}")
        return default_info['index']
    except:
        return None
    finally:
        p.terminate()

def test_wdsp_with_mic(duration_seconds=15, output_file="wdsp_test.wav", device_index=None):
    """
    从麦克风录音并通过 WDSP 处理
    
    Args:
        duration_seconds: 录音时长（秒）
        output_file: 输出 WAV 文件名
        device_index: 音频设备索引（None 为默认设备）
    """
    print(f"\n{'='*60}")
    print(f"🎙️  WDSP 实时处理测试")
    print(f"{'='*60}")
    print(f"📋 配置:")
    print(f"   - 录音时长: {duration_seconds} 秒")
    print(f"   - 采样率: {RATE} Hz")
    print(f"   - 缓冲区: {CHUNK} 帧")
    nr2_status = "开启" if NR2_ENABLED else "关闭"
    print(f"   - NR2: {nr2_status}")
    print(f"   - NR2 Gain Method: {NR2_GAIN_METHOD} (0=Gaussian保守)")
    print(f"   - NR2 NPE Method: {NR2_NPE_METHOD} (0=OSMS)")
    print(f"   - NR2 AE Run: {NR2_AE_RUN}")
    print(f"   - AGC Mode: {AGC_MODE} (2=SLOW)")
    print(f"   - 输出文件: {output_file}")
    print(f"{'='*60}\n")
    
    # 初始化 PyAudio
    p = pyaudio.PyAudio()
    
    # 选择设备
    if device_index is None:
        device_index = get_default_input_device()
    
    # 初始化 WDSP 处理器
    print("🔧 初始化 WDSP 处理器...")
    try:
        wdsp = WDSPProcessor(
            sample_rate=RATE,
            buffer_size=CHUNK,
            mode=1,  # USB mode
            enable_nr2=NR2_ENABLED,
            enable_nb=False,
            enable_anf=False,
            agc_mode=AGC_MODE
        )
        # 设置 NR2 参数（仅当 NR2 开启时）
        if NR2_ENABLED:
            wdsp.set_nr2_level(NR2_LEVEL)
        
        # 设置 AE (Amplitude Estimation) - 与 test_wdsp_compare.py 一致
        _wdsp.SetRXAEMNRaeRun(ctypes.c_int(0), ctypes.c_int(1 if NR2_ENABLED else 0))
        
        print(f"✅ WDSP 初始化完成\n")
    except Exception as e:
        print(f"❌ WDSP 初始化失败: {e}")
        p.terminate()
        return
    
    # 打开音频流
    print("🎤 打开音频流...")
    try:
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK
        )
        print(f"✅ 音频流已打开\n")
    except Exception as e:
        print(f"❌ 打开音频流失败: {e}")
        wdsp = None
        p.terminate()
        return
    
    # 准备 WAV 文件
    print(f"📁 准备写入文件: {output_file}")
    wav_file = wave.open(output_file, 'wb')
    wav_file.setnchannels(CHANNELS)
    wav_file.setsampwidth(2)  # 16-bit
    wav_file.setframerate(RATE)
    
    # 录音循环
    print(f"🔴 开始录音... (按 Ctrl+C 停止)")
    print(f"   请对着麦克风说话或播放音频...\n")
    
    # 临时禁用实时输出，只录音
    # output_device_index = OUTPUT_DEVICE_INDEX
    # print(f"   📢 输出设备: [{output_device_index}] {p.get_device_info_by_index(output_device_index)['name']}")
    # output_stream = p.open(
    #     format=FORMAT,
    #     channels=CHANNELS,
    #     rate=RATE,
    #     output=True,
    #     output_device_index=output_device_index,
    #     frames_per_buffer=CHUNK
    # )
    
    total_frames = int(RATE / CHUNK * duration_seconds)
    audio_frames = []
    
    try:
        for i in range(total_frames):
            # 读取音频数据
            data = stream.read(CHUNK, exception_on_overflow=False)
            
            # 转换为 numpy 数组 (float32)
            audio_data = np.frombuffer(data, dtype=np.float32)
            # USB Audio CODEC: 麦克风在右声道 (索引 1,3,5...)
            audio_mono = audio_data[1::2]  # 只取右声道
            
            # 转换为 float64 (WDSP 要求)
            audio_float64 = audio_mono.astype(np.float64)
            
            # 通过 WDSP 处理
            processed = wdsp.process(audio_float64)
            
            # 调试：检查 WDSP 输入输出范围
            if i % 50 == 0:
                print(f"   🔍 输入: min={audio_float64.min():.4f}, max={audio_float64.max():.4f}, mean={audio_float64.mean():.4f}")
                print(f"   🔍 输出: min={processed.min():.4f}, max={processed.max():.4f}, mean={processed.mean():.4f}")
            
            # 转回 float32 并添加到列表
            processed_int16 = (processed * 32767.0).astype(np.int16)
            wav_file.writeframes(processed_int16.tobytes())
            
            # 实时输出已禁用
            # stereo_output = np.zeros(len(processed) * 2, dtype=np.float32)
            # stereo_output[0::2] = processed  # 左声道
            # stereo_output[1::2] = processed  # 右声道
            # output_stream.write(stereo_output)
            
            # 进度显示
            if (i + 1) % (RATE // CHUNK) == 0:
                seconds = (i + 1) // (RATE // CHUNK)
                print(f"   ⏱️  {seconds}/{duration_seconds} 秒...", end='\r')
        
        print(f"\n\n✅ 录音完成! 已保存到: {output_file}")
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️ 用户中断，已保存当前录音到: {output_file}")
    
    # 清理
    finally:
        stream.stop_stream()
        stream.close()
        output_stream.stop_stream()
        output_stream.close()
        wav_file.close()
        p.terminate()
        
        if wdsp:
            wdsp.close()
        
        print(f"\n👋 测试结束")

if __name__ == "__main__":
    # 解析参数
    duration = 15
    output = "wdsp_test.wav"
    device = DEVICE_INDEX  # 默认使用 USB Audio CODEC
    
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except:
            print(f"用法: python3 {sys.argv[0]} [秒数] [输出文件] [设备索引]")
            sys.exit(1)
    
    if len(sys.argv) > 2:
        output = sys.argv[2]
    
    if len(sys.argv) > 3:
        try:
            device = int(sys.argv[3])
        except:
            pass
    
    # 列出设备
    list_audio_devices()
    
    # 运行测试
    test_wdsp_with_mic(duration, output, device)

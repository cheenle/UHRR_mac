#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WDSP 批量对比测试工具
生成多个配置对比的录音文件
"""

import pyaudio
import numpy as np
import wave
import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wdsp_wrapper import WDSPProcessor, WDSPAGCMode

# 配置参数
CHUNK = 512
FORMAT = pyaudio.paFloat32
CHANNELS = 1
RATE = 48000
DURATION = 10  # 每次测试10秒

OUTPUT_DIR = "/Users/cheenle/UHRR/MRRC/dev_tools"

def get_default_input_device():
    """获取默认输入设备"""
    p = pyaudio.PyAudio()
    try:
        default_info = p.get_default_input_device_info()
        return default_info['index']
    except:
        return None
    finally:
        p.terminate()

def record_with_config(duration, output_file, device_index, 
                       enable_wdsp=True, 
                       agc_mode=WDSPAGCMode.SLOW,
                       nr2_level=1,
                       nr2_gain_method=0,
                       nr2_npe_method=0,
                       nr2_ae_run=True):
    """使用指定配置录音"""
    
    p = pyaudio.PyAudio()
    wdsp = None
    
    try:
        # 初始化 WDSP（如果需要）
        if enable_wdsp:
            wdsp = WDSPProcessor(
                sample_rate=RATE,
                buffer_size=CHUNK,
                mode=1,
                enable_nr2=True,
                enable_nb=False,
                enable_anf=False,
                agc_mode=agc_mode
            )
            wdsp.set_nr2_level(nr2_level)
            # 手动设置 AE
            import ctypes
            wdsp._wdsp.SetRXAEMNRaeRun(ctypes.c_int(0), ctypes.c_int(1 if nr2_ae_run else 0))
        
        # 打开音频流
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK
        )
        
        # 准备 WAV 文件
        wav_file = wave.open(output_file, 'wb')
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(2)
        wav_file.setframerate(RATE)
        
        # 录音
        total_frames = int(RATE / CHUNK * duration)
        
        for i in range(total_frames):
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.float32)
            
            if wdsp:
                audio_float64 = audio_data.astype(np.float64)
                processed = wdsp.process(audio_float64)
                processed_int16 = (processed * 32767.0).astype(np.int16)
            else:
                # 无 WDSP 处理，直接转换
                processed_int16 = (audio_data * 32767.0).astype(np.int16)
            
            wav_file.writeframes(processed_int16.tobytes())
            
            if (i + 1) % (RATE // CHUNK) == 0:
                print(f"   { (i + 1) // (RATE // CHUNK) }/{duration}s", end='\r')
        
        wav_file.close()
        stream.close()
        
    finally:
        if wdsp:
            wdsp.close()
        p.terminate()
    
    return True


def main():
    print("\n" + "="*60)
    print("🎛️  WDSP 批量对比测试")
    print("="*60)
    
    device = get_default_input_device()
    if device is None:
        print("❌ 找不到音频输入设备")
        return
    
    # 等待用户准备
    print(f"\n🎤 使用设备索引: {device}")
    print(f"⏱️  每次测试 {DURATION} 秒")
    print("\n" + "-"*60)
    print("配置列表:")
    print("  [1] 原始录音 (无 WDSP)")
    print("  [2] AGC OFF + NR2 Level 1")
    print("  [3] AGC SLOW + NR2 Level 1")  
    print("  [4] AGC SLOW + NR2 Level 3")
    print("  [5] AGC SLOW + NR2 Level 5")
    print("-"*60)
    
    configs = [
        ("原始录音(无WDSP)", False, WDSPAGCMode.OFF, 0, 0, 0, False),
        ("AGC_OFF_NR2_L1", True, WDSPAGCMode.OFF, 1, 0, 0, True),
        ("AGC_SLOW_NR2_L1", True, WDSPAGCMode.SLOW, 1, 0, 0, True),
        ("AGC_SLOW_NR2_L3", True, WDSPAGCMode.SLOW, 3, 0, 0, True),
        ("AGC_SLOW_NR2_L5", True, WDSPAGCMode.SLOW, 5, 0, 0, True),
    ]
    
    for idx, (name, enable_wdsp, agc, nr2_level, gm, npm, ae) in enumerate(configs):
        filename = f"test_{name}.wav"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        print(f"\n[{idx+1}/{len(configs)}] 测试: {name}")
        print(f"   AGC={'OFF' if agc==0 else 'SLOW' if agc==2 else 'MED'}, NR2={nr2_level}, AE={ae}")
        
        record_with_config(
            DURATION, filepath, device,
            enable_wdsp=enable_wdsp,
            agc_mode=agc,
            nr2_level=nr2_level,
            nr2_gain_method=gm,
            nr2_npe_method=npm,
            nr2_ae_run=ae
        )
        
        print(f"   ✅ 已保存: {filename}")
        
        # 每次间隔1秒
        if idx < len(configs) - 1:
            print("   ⏳ 准备下一个测试...")
            time.sleep(1)
    
    print("\n" + "="*60)
    print("✅ 所有测试完成！")
    print("="*60)
    print("\n📁 生成的文件:")
    for idx, (name, _, _, _, _, _, _) in enumerate(configs):
        filename = f"test_{name}.wav"
        filepath = os.path.join(OUTPUT_DIR, filename)
        size = os.path.getsize(filepath)
        print(f"   {filename} ({size/1024:.1f} KB)")

if __name__ == "__main__":
    main()

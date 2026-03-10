#!/usr/bin/env python3
"""
WDSP 服务器端测试 - 验证各项功能是否正常工作
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import wave
from wdsp_wrapper import WDSPProcessor, WDSPMode

# 测试参数
SAMPLE_RATE = 48000
BUFFER_SIZE = 256
DURATION = 5  # 秒

def generate_test_signal(freq=1000, noise_level=0.5):
    """生成测试信号：正弦波 + 噪声"""
    t = np.linspace(0, DURATION, SAMPLE_RATE * DURATION)
    # 正弦波
    sine = np.sin(2 * np.pi * freq * t) * 0.3
    # 噪声
    noise = np.random.randn(len(t)) * noise_level
    # 混合
    signal = sine + noise
    return signal.astype(np.float64)

def test_wdsp_basic():
    """测试WDSP基本功能"""
    print("=" * 60)
    print("测试 1: WDSP 基本处理 (直通)")
    print("=" * 60)
    
    wdsp = WDSPProcessor(
        sample_rate=SAMPLE_RATE,
        buffer_size=BUFFER_SIZE,
        mode=WDSPMode.USB,
        enable_nr2=False,
        enable_nb=False,
        enable_anf=False,
        agc_mode=0  # OFF
    )
    
    # 生成测试信号
    signal = generate_test_signal()
    
    # 处理
    processed_frames = []
    for i in range(0, len(signal), BUFFER_SIZE):
        frame = signal[i:i+BUFFER_SIZE]
        if len(frame) == BUFFER_SIZE:
            processed = wdsp.process(frame)
            processed_frames.append(processed)
    
    processed = np.concatenate(processed_frames)
    
    # 计算能量
    in_energy = np.sum(signal[:len(processed)] ** 2)
    out_energy = np.sum(processed ** 2)
    
    print(f"  输入能量: {in_energy:.2f}")
    print(f"  输出能量: {out_energy:.2f}")
    print(f"  能量比例: {out_energy/in_energy:.2f}")
    
    wdsp.close()
    
    # 保存音频
    save_wav("/tmp/test1_basic.wav", processed)
    print(f"  已保存: /tmp/test1_basic.wav")
    
    return out_energy / in_energy

def test_wdsp_bandpass():
    """测试带通滤波器"""
    print("\n" + "=" * 60)
    print("测试 2: WDSP 带通滤波器 (300-2700Hz)")
    print("=" * 60)
    
    wdsp = WDSPProcessor(
        sample_rate=SAMPLE_RATE,
        buffer_size=BUFFER_SIZE,
        mode=WDSPMode.USB,
        enable_nr2=False,
        enable_nb=False,
        enable_anf=False,
        agc_mode=0
    )
    
    # 设置带通滤波器
    wdsp.set_bandpass(300.0, 2700.0)
    print(f"  带通滤波器: 300Hz - 2700Hz")
    
    # 生成测试信号（包含低频和高频）
    t = np.linspace(0, DURATION, SAMPLE_RATE * DURATION)
    # 低频100Hz（应该被滤除）
    low_freq = np.sin(2 * np.pi * 100 * t) * 0.3
    # 中频1000Hz（应该通过）
    mid_freq = np.sin(2 * np.pi * 1000 * t) * 0.3
    # 高频5000Hz（应该被滤除）
    high_freq = np.sin(2 * np.pi * 5000 * t) * 0.3
    
    signal = (low_freq + mid_freq + high_freq).astype(np.float64)
    
    # 处理
    processed_frames = []
    for i in range(0, len(signal), BUFFER_SIZE):
        frame = signal[i:i+BUFFER_SIZE]
        if len(frame) == BUFFER_SIZE:
            processed = wdsp.process(frame)
            processed_frames.append(processed)
    
    processed = np.concatenate(processed_frames)
    
    # 计算能量
    in_energy = np.sum(signal[:len(processed)] ** 2)
    out_energy = np.sum(processed ** 2)
    
    print(f"  输入能量: {in_energy:.2f}")
    print(f"  输出能量: {out_energy:.2f}")
    print(f"  能量比例: {out_energy/in_energy:.2f}")
    print(f"  预期: 应该衰减到约1/3 (因为滤除了低频和高频)")
    
    wdsp.close()
    
    # 保存音频
    save_wav("/tmp/test2_bandpass.wav", processed)
    print(f"  已保存: /tmp/test2_bandpass.wav")
    
    return out_energy / in_energy

def test_wdsp_agc():
    """测试AGC"""
    print("\n" + "=" * 60)
    print("测试 3: WDSP AGC (模式3=MED)")
    print("=" * 60)
    
    wdsp = WDSPProcessor(
        sample_rate=SAMPLE_RATE,
        buffer_size=BUFFER_SIZE,
        mode=WDSPMode.USB,
        enable_nr2=False,
        enable_nb=False,
        enable_anf=False,
        agc_mode=3  # MED
    )
    
    # 生成不同强度的信号
    results = []
    for amp in [0.01, 0.1, 1.0]:
        signal = np.random.randn(SAMPLE_RATE * 2) * amp  # 2秒
        
        # 预热
        for i in range(100):
            frame = signal[i*BUFFER_SIZE:(i+1)*BUFFER_SIZE]
            if len(frame) == BUFFER_SIZE:
                wdsp.process(frame)
        
        # 测试
        frame = signal[100*BUFFER_SIZE:101*BUFFER_SIZE]
        processed = wdsp.process(frame)
        
        in_e = np.sum(np.abs(frame))
        out_e = np.sum(np.abs(processed))
        ratio = out_e / in_e if in_e > 0 else 0
        
        print(f"  输入幅度 {amp:.2f}: 输入={in_e:.2f}, 输出={out_e:.2f}, 增益={ratio:.2f}")
        results.append(ratio)
    
    wdsp.close()
    
    # AGC应该让不同输入幅度的输出幅度趋于一致
    return results

def test_wdsp_nr2():
    """测试NR2降噪"""
    print("\n" + "=" * 60)
    print("测试 4: WDSP NR2 降噪 (Level 4)")
    print("=" * 60)
    
    wdsp = WDSPProcessor(
        sample_rate=SAMPLE_RATE,
        buffer_size=BUFFER_SIZE,
        mode=WDSPMode.USB,
        enable_nr2=True,
        enable_nb=False,
        enable_anf=False,
        agc_mode=0
    )
    
    # 设置NR2
    wdsp.set_nr2_level(4)
    print(f"  NR2 Level: 4 (强力)")
    
    # 生成带噪声的信号
    signal = generate_test_signal(noise_level=0.8)
    
    # 预热100帧
    for i in range(100):
        frame = signal[i*BUFFER_SIZE:(i+1)*BUFFER_SIZE]
        if len(frame) == BUFFER_SIZE:
            wdsp.process(frame)
    
    # 测试
    processed_frames = []
    for i in range(100, 200):
        frame = signal[i*BUFFER_SIZE:(i+1)*BUFFER_SIZE]
        if len(frame) == BUFFER_SIZE:
            processed = wdsp.process(frame)
            processed_frames.append(processed)
    
    processed = np.concatenate(processed_frames)
    
    # 计算能量
    in_energy = np.sum(signal[100*BUFFER_SIZE:200*BUFFER_SIZE] ** 2)
    out_energy = np.sum(processed ** 2)
    
    print(f"  输入能量: {in_energy:.2f}")
    print(f"  输出能量: {out_energy:.2f}")
    print(f"  降噪比例: {100*(1-out_energy/in_energy):.1f}%")
    
    wdsp.close()
    
    # 保存音频
    save_wav("/tmp/test4_nr2.wav", processed)
    print(f"  已保存: /tmp/test4_nr2.wav")
    
    return out_energy / in_energy

def save_wav(filename, data):
    """保存音频到WAV文件"""
    # 转换为int16
    data_int16 = (data * 32767).astype(np.int16)
    
    # 创建立体声（复制到左右声道）
    stereo = np.zeros((len(data_int16), 2), dtype=np.int16)
    stereo[:, 0] = data_int16
    stereo[:, 1] = data_int16
    
    with wave.open(filename, 'wb') as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(stereo.tobytes())

def main():
    print("WDSP 服务器端功能测试")
    print("=" * 60)
    
    # 运行测试
    ratio1 = test_wdsp_basic()
    ratio2 = test_wdsp_bandpass()
    ratios3 = test_wdsp_agc()
    ratio4 = test_wdsp_nr2()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)
    print(f"1. 基本处理: 能量比例 = {ratio1:.2f} (应为1.0)")
    print(f"2. 带通滤波: 能量比例 = {ratio2:.2f} (应<1.0)")
    print(f"3. AGC: 不同输入的增益 = {[f'{r:.2f}' for r in ratios3]}")
    print(f"   (AGC应该让不同输入的输出趋于一致)")
    print(f"4. NR2降噪: 能量比例 = {ratio4:.2f} (应<1.0)")
    
    print("\n音频文件已保存到 /tmp/test*.wav")
    print("请使用以下命令播放测试:")
    print("  ffplay -nodisp -autoexit /tmp/test2_bandpass.wav")
    print("  ffplay -nodisp -autoexit /tmp/test4_nr2.wav")

if __name__ == "__main__":
    main()
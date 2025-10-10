#!/usr/bin/env python3
"""
测试Int16优化效果
"""

import numpy as np
import time

def test_int16_optimization():
    """测试Int16优化效果"""
    print("🧪 测试Int16优化效果...")
    
    # 模拟12kHz音频数据
    sample_rate = 12000
    frame_size = 512
    duration = 1.0
    
    # 生成测试音频
    t = np.linspace(0, duration, int(sample_rate * duration))
    signal = np.sin(2 * np.pi * 200 * t)
    signal += 0.3 * np.sin(2 * np.pi * 400 * t)
    signal += 0.1 * np.random.randn(len(t))
    signal = signal / np.max(np.abs(signal))
    
    # 原始Float32数据
    float32_data = signal.astype(np.float32)
    original_size = len(float32_data) * 4  # Float32 = 4 bytes
    
    # Int16压缩
    int16_data = (float32_data * 32767).astype(np.int16)
    compressed_size = len(int16_data) * 2  # Int16 = 2 bytes
    
    # 解压缩
    decompressed_float = int16_data.astype(np.float32) / 32767.0
    
    # 计算指标
    compression_ratio = original_size / compressed_size
    bandwidth_saved = (1 - compressed_size / original_size) * 100
    mse = np.mean((float32_data - decompressed_float) ** 2)
    snr = 20 * np.log10(np.sqrt(np.mean(float32_data ** 2)) / np.sqrt(mse)) if mse > 0 else float('inf')
    
    print(f"📊 Int16优化结果:")
    print(f"   原始大小: {original_size} 字节")
    print(f"   压缩大小: {compressed_size} 字节")
    print(f"   压缩比: {compression_ratio:.2f}x")
    print(f"   带宽节省: {bandwidth_saved:.1f}%")
    print(f"   信噪比: {snr:.2f} dB")
    print(f"   均方误差: {mse:.6f}")
    
    # 计算实际带宽
    frames_per_second = sample_rate / frame_size
    bandwidth_kbps = (compressed_size * frames_per_second * 8) / 1000
    
    print(f"\n🌐 网络带宽:")
    print(f"   采样率: {sample_rate} Hz")
    print(f"   帧大小: {frame_size} 样本")
    print(f"   帧率: {frames_per_second:.1f} 帧/秒")
    print(f"   实际带宽: {bandwidth_kbps:.1f} kbps")
    
    return compression_ratio > 1.8 and bandwidth_saved > 45

if __name__ == "__main__":
    success = test_int16_optimization()
    if success:
        print("\n✅ Int16优化测试通过！")
    else:
        print("\n❌ Int16优化测试失败！")

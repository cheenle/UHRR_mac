#!/usr/bin/env python3
"""
调试Int16数据格式
"""

import numpy as np
import struct

def test_int16_conversion():
    """测试Int16转换过程"""
    print("🔍 测试Int16转换过程...")
    
    # 模拟12kHz音频数据
    sample_rate = 12000
    frame_size = 512
    
    # 生成测试音频
    t = np.linspace(0, frame_size / sample_rate, frame_size)
    signal = np.sin(2 * np.pi * 200 * t)
    signal += 0.3 * np.sin(2 * np.pi * 400 * t)
    signal += 0.1 * np.random.randn(len(t))
    signal = signal / np.max(np.abs(signal))
    
    print(f"📊 原始音频数据:")
    print(f"   样本数: {len(signal)}")
    print(f"   数据类型: {signal.dtype}")
    print(f"   数据范围: [{np.min(signal):.4f}, {np.max(signal):.4f}]")
    
    # 1. 服务器端：Float32 → Int16
    float32_data = signal.astype(np.float32)
    int16_data = (float32_data * 32767).astype(np.int16)
    compressed_bytes = int16_data.tobytes()
    
    print(f"\n🔄 服务器端转换:")
    print(f"   Float32数据: {len(float32_data)} 样本")
    print(f"   Int16数据: {len(int16_data)} 样本")
    print(f"   Int16范围: [{np.min(int16_data)}, {np.max(int16_data)}]")
    print(f"   压缩字节: {len(compressed_bytes)} 字节")
    
    # 2. 客户端：Int16 → Float32
    int16_received = np.frombuffer(compressed_bytes, dtype=np.int16)
    float32_reconstructed = int16_received.astype(np.float32) / 32767.0
    
    print(f"\n🔄 客户端转换:")
    print(f"   接收Int16: {len(int16_received)} 样本")
    print(f"   重构Float32: {len(float32_reconstructed)} 样本")
    print(f"   重构范围: [{np.min(float32_reconstructed):.4f}, {np.max(float32_reconstructed):.4f}]")
    
    # 3. 计算误差
    mse = np.mean((float32_data - float32_reconstructed) ** 2)
    snr = 20 * np.log10(np.sqrt(np.mean(float32_data ** 2)) / np.sqrt(mse)) if mse > 0 else float('inf')
    
    print(f"\n📈 质量评估:")
    print(f"   均方误差: {mse:.8f}")
    print(f"   信噪比: {snr:.2f} dB")
    print(f"   最大误差: {np.max(np.abs(float32_data - float32_reconstructed)):.6f}")
    
    # 4. 检查数据完整性
    print(f"\n🔍 数据完整性检查:")
    print(f"   原始样本数: {len(float32_data)}")
    print(f"   重构样本数: {len(float32_reconstructed)}")
    print(f"   样本数匹配: {'✅' if len(float32_data) == len(float32_reconstructed) else '❌'}")
    
    # 5. 检查数据范围
    original_range = np.max(float32_data) - np.min(float32_data)
    reconstructed_range = np.max(float32_reconstructed) - np.min(float32_reconstructed)
    range_ratio = reconstructed_range / original_range if original_range > 0 else 0
    
    print(f"   原始范围: {original_range:.6f}")
    print(f"   重构范围: {reconstructed_range:.6f}")
    print(f"   范围保持: {range_ratio:.4f} ({'✅' if range_ratio > 0.9 else '❌'})")
    
    return mse < 0.001 and snr > 60 and len(float32_data) == len(float32_reconstructed)

def test_web_audio_compatibility():
    """测试Web Audio API兼容性"""
    print(f"\n🌐 测试Web Audio API兼容性...")
    
    # 模拟Web Audio API期望的数据格式
    sample_rate = 12000
    frame_size = 512
    
    # 生成测试音频
    t = np.linspace(0, frame_size / sample_rate, frame_size)
    signal = np.sin(2 * np.pi * 200 * t)
    signal = signal / np.max(np.abs(signal))
    
    # 服务器端处理
    float32_data = signal.astype(np.float32)
    int16_data = (float32_data * 32767).astype(np.int16)
    compressed_bytes = int16_data.tobytes()
    
    # 客户端处理（模拟JavaScript）
    int16_received = np.frombuffer(compressed_bytes, dtype=np.int16)
    float32_reconstructed = int16_received.astype(np.float32) / 32767.0
    
    # 检查Web Audio API要求
    print(f"   Web Audio API要求:")
    print(f"   - 数据类型: Float32Array")
    print(f"   - 数据范围: [-1.0, 1.0]")
    print(f"   - 样本数: {frame_size}")
    
    print(f"   实际数据:")
    print(f"   - 数据类型: {float32_reconstructed.dtype}")
    print(f"   - 数据范围: [{np.min(float32_reconstructed):.4f}, {np.max(float32_reconstructed):.4f}]")
    print(f"   - 样本数: {len(float32_reconstructed)}")
    
    # 检查是否在有效范围内
    in_range = np.all(float32_reconstructed >= -1.0) and np.all(float32_reconstructed <= 1.0)
    print(f"   - 范围检查: {'✅' if in_range else '❌'}")
    
    return in_range and len(float32_reconstructed) == frame_size

if __name__ == "__main__":
    print("🚀 开始调试Int16数据格式...")
    
    # 测试Int16转换
    conversion_ok = test_int16_conversion()
    
    # 测试Web Audio API兼容性
    web_audio_ok = test_web_audio_compatibility()
    
    print(f"\n📊 调试结果:")
    print(f"   Int16转换: {'✅ 正常' if conversion_ok else '❌ 异常'}")
    print(f"   Web Audio兼容: {'✅ 正常' if web_audio_ok else '❌ 异常'}")
    
    if conversion_ok and web_audio_ok:
        print("🎉 数据格式检查通过！")
    else:
        print("⚠️ 发现数据格式问题！")

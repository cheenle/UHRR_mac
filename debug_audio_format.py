#!/usr/bin/env python3
"""
调试音频格式 - 检查服务器端实际发送的数据格式
"""

import numpy as np
import struct
import time

def analyze_audio_data_format():
    """分析音频数据格式"""
    print("🔍 分析音频数据格式...")
    
    # 模拟服务器端压缩过程
    sample_rate = 12000
    frame_size = 512
    
    # 生成测试音频数据
    t = np.linspace(0, frame_size / sample_rate, frame_size)
    signal = np.sin(2 * np.pi * 200 * t)
    signal += 0.3 * np.sin(2 * np.pi * 400 * t)
    signal += 0.1 * np.random.randn(len(t))
    signal = signal / np.max(np.abs(signal))
    
    print(f"📊 原始音频数据:")
    print(f"   样本数: {len(signal)}")
    print(f"   数据类型: {signal.dtype}")
    print(f"   数据范围: [{np.min(signal):.4f}, {np.max(signal):.4f}]")
    
    # 1. 动态范围压缩
    compressed_audio = np.tanh(signal * 2) * 0.5
    print(f"\n📈 动态范围压缩后:")
    print(f"   数据范围: [{np.min(compressed_audio):.4f}, {np.max(compressed_audio):.4f}]")
    
    # 2. 差分编码压缩
    first_sample = compressed_audio[0]
    diffs = np.diff(compressed_audio)
    
    print(f"\n🔢 差分编码:")
    print(f"   第一个样本: {first_sample:.6f}")
    print(f"   差值数量: {len(diffs)}")
    print(f"   差值范围: [{np.min(diffs):.6f}, {np.max(diffs):.6f}]")
    
    # 3. 量化差值
    diff_scale = 16384.0
    quantized_diffs = np.round(diffs * diff_scale).astype(np.int16)
    
    print(f"\n📦 量化后:")
    print(f"   量化差值范围: [{np.min(quantized_diffs)}, {np.max(quantized_diffs)}]")
    print(f"   量化差值类型: {quantized_diffs.dtype}")
    
    # 4. 组合数据
    first_sample_bytes = struct.pack('<f', first_sample)
    diff_bytes = quantized_diffs.tobytes()
    compressed_data = first_sample_bytes + diff_bytes
    
    print(f"\n📦 最终压缩数据:")
    print(f"   第一个样本字节: {len(first_sample_bytes)} 字节")
    print(f"   差值字节: {len(diff_bytes)} 字节")
    print(f"   总压缩数据: {len(compressed_data)} 字节")
    print(f"   原始数据: {len(signal) * 4} 字节")
    print(f"   压缩比: {len(signal) * 4 / len(compressed_data):.2f}x")
    
    # 5. 模拟客户端解压缩
    print(f"\n🔓 客户端解压缩模拟:")
    
    # 检查数据长度
    if len(compressed_data) > 4 and len(compressed_data) % 2 == 0:
        print("   ✅ 数据长度检查通过")
        
        # 读取第一个样本
        first_sample_decomp = struct.unpack('<f', compressed_data[:4])[0]
        print(f"   ✅ 第一个样本: {first_sample_decomp:.6f}")
        
        # 读取差值
        diff_bytes_decomp = compressed_data[4:]
        if len(diff_bytes_decomp) % 2 == 0:
            quantized_diffs_decomp = np.frombuffer(diff_bytes_decomp, dtype=np.int16)
            print(f"   ✅ 差值数量: {len(quantized_diffs_decomp)}")
            
            # 重构音频数据
            float32_data = np.zeros(len(quantized_diffs_decomp) + 1, dtype=np.float32)
            float32_data[0] = first_sample_decomp
            
            # 差分解压缩
            for i in range(len(quantized_diffs_decomp)):
                diff = quantized_diffs_decomp[i] / diff_scale
                float32_data[i + 1] = float32_data[i] + diff
            
            # 反向动态范围压缩
            for i in range(len(float32_data)):
                float32_data[i] = np.tanh(float32_data[i] * 2) * 0.5
            
            print(f"   ✅ 重构音频数据长度: {len(float32_data)}")
            print(f"   ✅ 重构数据范围: [{np.min(float32_data):.4f}, {np.max(float32_data):.4f}]")
            
            # 计算重构误差
            mse = np.mean((signal - float32_data) ** 2)
            snr = 20 * np.log10(np.sqrt(np.mean(signal ** 2)) / np.sqrt(mse)) if mse > 0 else float('inf')
            print(f"   ✅ 重构误差 (MSE): {mse:.6f}")
            print(f"   ✅ 信噪比: {snr:.2f} dB")
            
            return True
        else:
            print("   ❌ 差值字节长度不是2的倍数")
            return False
    else:
        print("   ❌ 数据长度检查失败")
        return False

def test_network_packet_format():
    """测试网络包格式"""
    print(f"\n🌐 测试网络包格式...")
    
    # 模拟4个音频帧
    frames = []
    for i in range(4):
        t = np.linspace(0, 512 / 12000, 512)
        signal = np.sin(2 * np.pi * 200 * t + i * 0.1)
        signal = signal / np.max(np.abs(signal))
        
        # 差分编码压缩
        compressed_audio = np.tanh(signal * 2) * 0.5
        first_sample = compressed_audio[0]
        diffs = np.diff(compressed_audio)
        quantized_diffs = np.round(diffs * 16384.0).astype(np.int16)
        
        frame_data = struct.pack('<f', first_sample) + quantized_diffs.tobytes()
        frames.append(frame_data)
    
    # 创建合并包
    total_size = sum(len(frame) for frame in frames)
    packet_header = struct.pack('<HH', total_size, len(frames))
    merged_packet = packet_header + b''.join(frames)
    
    print(f"   单个帧大小: {len(frames[0])} 字节")
    print(f"   合并包头部: {len(packet_header)} 字节")
    print(f"   合并包总大小: {len(merged_packet)} 字节")
    print(f"   包数量: {len(frames)}")
    
    # 模拟客户端解包
    data_view = np.frombuffer(merged_packet, dtype=np.uint8)
    total_size_decomp = struct.unpack('<H', merged_packet[:2])[0]
    frame_count_decomp = struct.unpack('<H', merged_packet[2:4])[0]
    
    print(f"   解包 - 总大小: {total_size_decomp}")
    print(f"   解包 - 帧数量: {frame_count_decomp}")
    
    if total_size_decomp == total_size and frame_count_decomp == len(frames):
        print("   ✅ 合并包格式正确")
        return True
    else:
        print("   ❌ 合并包格式错误")
        return False

if __name__ == "__main__":
    print("🚀 开始调试音频格式...")
    
    # 测试单个帧格式
    single_frame_ok = analyze_audio_data_format()
    
    # 测试合并包格式
    merged_packet_ok = test_network_packet_format()
    
    print(f"\n📊 调试结果:")
    print(f"   单个帧格式: {'✅ 正确' if single_frame_ok else '❌ 错误'}")
    print(f"   合并包格式: {'✅ 正确' if merged_packet_ok else '❌ 错误'}")
    
    if single_frame_ok and merged_packet_ok:
        print("🎉 所有格式检查通过！")
    else:
        print("⚠️ 发现格式问题，需要修复！")

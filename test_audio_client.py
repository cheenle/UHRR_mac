#!/usr/bin/env python3
"""
测试音频客户端 - 检查服务器是否发送音频数据
"""

import asyncio
import websockets
import ssl
import struct
import numpy as np

async def test_audio_connection():
    """测试音频连接"""
    print("🔌 连接到音频服务器...")
    
    # 创建SSL上下文
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        # 连接到WebSocket
        uri = "wss://localhost:8877/WSCTRX"
        async with websockets.connect(uri, ssl=ssl_context) as websocket:
            print("✅ WebSocket连接成功")
            
            # 发送初始化消息
            await websocket.send("ready")
            print("📤 发送ready消息")
            
            # 接收音频数据
            frame_count = 0
            total_bytes = 0
            
            print("🎵 开始接收音频数据...")
            
            async for message in websocket:
                if isinstance(message, bytes):
                    frame_count += 1
                    total_bytes += len(message)
                    
                    print(f"📦 帧 {frame_count}: {len(message)} 字节")
                    
                    # 分析数据格式
                    if len(message) > 4:
                        # 检查是否为合并包
                        data_view = np.frombuffer(message, dtype=np.uint8)
                        total_size = struct.unpack('<H', message[:2])[0]
                        frame_count_in_packet = struct.unpack('<H', message[2:4])[0]
                        
                        print(f"   合并包 - 总大小: {total_size}, 帧数: {frame_count_in_packet}")
                        
                        if frame_count_in_packet > 1:
                            print("   ✅ 检测到合并包格式")
                            
                            # 解包第一个帧
                            offset = 4
                            if offset + 4 < len(message):
                                first_sample = struct.unpack('<f', message[offset:offset+4])[0]
                                print(f"   第一个样本: {first_sample:.6f}")
                                
                                # 计算差值数据长度
                                remaining_bytes = len(message) - offset - 4
                                if remaining_bytes > 0:
                                    diff_bytes = message[offset+4:offset+4+remaining_bytes]
                                    if len(diff_bytes) % 2 == 0:
                                        quantized_diffs = np.frombuffer(diff_bytes, dtype=np.int16)
                                        print(f"   差值数量: {len(quantized_diffs)}")
                                        print(f"   差值范围: [{np.min(quantized_diffs)}, {np.max(quantized_diffs)}]")
                                        
                                        # 重构音频数据
                                        float32_data = np.zeros(len(quantized_diffs) + 1, dtype=np.float32)
                                        float32_data[0] = first_sample
                                        
                                        diff_scale = 16384.0
                                        for i in range(len(quantized_diffs)):
                                            diff = quantized_diffs[i] / diff_scale
                                            float32_data[i + 1] = float32_data[i] + diff
                                        
                                        # 反向动态范围压缩
                                        for i in range(len(float32_data)):
                                            float32_data[i] = np.tanh(float32_data[i] * 2) * 0.5
                                        
                                        print(f"   重构音频数据长度: {len(float32_data)}")
                                        print(f"   重构数据范围: [{np.min(float32_data):.4f}, {np.max(float32_data):.4f}]")
                                        
                                        # 计算带宽
                                        bandwidth_kbps = (len(message) * 8) / 1000  # 假设1秒
                                        print(f"   带宽: {bandwidth_kbps:.1f} kbps")
                                        
                                        if frame_count >= 5:  # 接收5个包后退出
                                            break
                    else:
                        print("   ❌ 数据太短，可能不是合并包格式")
                        
                else:
                    print(f"📝 文本消息: {message}")
                    
            print(f"\n📊 接收统计:")
            print(f"   总帧数: {frame_count}")
            print(f"   总字节数: {total_bytes}")
            print(f"   平均帧大小: {total_bytes/frame_count if frame_count > 0 else 0:.1f} 字节")
            
    except Exception as e:
        print(f"❌ 连接错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 开始测试音频连接...")
    asyncio.run(test_audio_connection())

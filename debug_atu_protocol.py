#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ATU协议调试工具
用于分析ATU设备发送的数据包结构
"""

import websocket
import json
import ssl
import time
import threading
import struct

# ATU命令定义
SCMD_FLAG = 0xFF
SCMD_SYNC = 1
SCMD_METER_STATUS = 2

def on_message(ws, message):
    try:
        if isinstance(message, bytes):
            data = bytearray(message)
            print(f"📥 接收到ATU二进制数据: {len(data)} 字节")
            
            # 显示所有字节的十六进制表示
            hex_data = ' '.join([f'{b:02X}' for b in data])
            print(f"   数据内容: {hex_data}")
            
            # 解析数据包头部
            if len(data) >= 3:
                flag = data[0]
                cmd = data[1]
                data_len = data[2]
                print(f"   包头: FLAG=0x{flag:02X}, CMD=0x{cmd:02X}, LEN={data_len}")
                
                # 检查是否为电表数据
                if cmd == SCMD_METER_STATUS and len(data) >= 10:
                    print("   📊 这是电表数据包")
                    
                    # 显示各个字段的值
                    if len(data) >= 4:
                        swr_bytes = bytes(data[4:6])
                        swr = struct.unpack('<H', swr_bytes)[0]
                        print(f"   SWR字段 (偏移4-5): 0x{swr_bytes[0]:02X} 0x{swr_bytes[1]:02X} = {swr}")
                    
                    if len(data) >= 6:
                        power_bytes = bytes(data[6:8])
                        power = struct.unpack('<H', power_bytes)[0]
                        print(f"   功率字段 (偏移6-7): 0x{power_bytes[0]:02X} 0x{power_bytes[1]:02X} = {power}")
                    
                    if len(data) >= 8:
                        max_power_bytes = bytes(data[8:10])
                        max_power = struct.unpack('<H', max_power_bytes)[0]
                        print(f"   最大功率字段 (偏移8-9): 0x{max_power_bytes[0]:02X} 0x{max_power_bytes[1]:02X} = {max_power}")
                    
                    # 尝试其他可能的偏移量
                    print("   🔍 尝试其他偏移量:")
                    for offset in range(3, min(len(data)-1, 15)):
                        if offset + 1 < len(data):
                            bytes_val = bytes(data[offset:offset+2])
                            val = struct.unpack('<H', bytes_val)[0]
                            print(f"      偏移{offset}-{offset+1}: 0x{bytes_val[0]:02X} 0x{bytes_val[1]:02X} = {val}")
        else:
            print(f"📥 接收到文本数据: {message}")
            
    except Exception as e:
        print(f"❌ 处理消息错误: {e}")

def on_error(ws, error):
    print(f"❌ WebSocket错误: {error}")

def on_close(ws, close_status_code, close_msg):
    print("🔒 WebSocket连接已关闭")

def on_open(ws):
    print("✅ ATU设备WebSocket连接已建立")
    
    # 发送同步命令
    def send_sync():
        time.sleep(1)
        sync_cmd = bytearray([SCMD_FLAG, SCMD_SYNC, 0x00])
        try:
            ws.send(sync_cmd, opcode=websocket.ABNF.OPCODE_BINARY)
            print("📤 发送同步命令")
        except Exception as e:
            print(f"❌ 发送同步命令失败: {e}")
    
    # 定期发送同步命令
    def send_sync_periodically():
        while True:
            time.sleep(0.5)
            sync_cmd = bytearray([SCMD_FLAG, SCMD_SYNC, 0x00])
            try:
                ws.send(sync_cmd, opcode=websocket.ABNF.OPCODE_BINARY)
                print("📤 发送同步命令")
            except Exception as e:
                print(f"❌ 发送同步命令失败: {e}")
                break
    
    # 启动同步命令发送
    sync_thread = threading.Thread(target=send_sync_periodically)
    sync_thread.daemon = True
    sync_thread.start()

if __name__ == "__main__":
    # ATU设备WebSocket地址
    ws_url = "ws://192.168.1.12:60001/"
    
    print(f"🔌 连接到ATU设备: {ws_url}")
    
    # 创建WebSocket连接
    ws = websocket.WebSocketApp(ws_url,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)
    
    # 启动WebSocket连接
    ws.run_forever()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import websocket
import json
import time
import threading
import ssl

def on_message(ws, message):
    try:
        data = json.loads(message)
        print(f"📥 收到消息: {data}")
        
        if data.get('type') == 'data' and data.get('data'):
            atu_data = data['data']
            power = atu_data.get('power', 0)
            swr = atu_data.get('swr', 0)
            efficiency = atu_data.get('efficiency', 0)
            print(f"📊 ATU实时数据 - 功率: {power}W, SWR: {swr}, 效率: {efficiency}%")
        elif data.get('type') == 'status':
            print(f"📋 状态消息: {data.get('message', '')} - 连接状态: {data.get('connected', False)}")
    except Exception as e:
        print(f"❌ 消息解析错误: {e}")
        print(f"原始消息: {message}")

def on_error(ws, error):
    print(f"❌ WebSocket错误: {error}")

def on_close(ws, close_status_code, close_msg):
    print("🔒 WebSocket连接已关闭")

def on_open(ws):
    print("✅ WebSocket连接已建立")
    print("📡 开始接收ATU数据...")
    
    # 发送状态查询命令
    status_command = {
        'type': 'command',
        'command': 'status'
    }
    ws.send(json.dumps(status_command))
    print("📤 已发送状态查询命令")

def main():
    # 连接到ATU服务器的WebSocket (使用正确的端口8889)
    ws_url = "wss://localhost:8889/atu/ws"
    
    print(f"🔌 尝试连接到ATU服务器: {ws_url}")
    
    # 创建WebSocket连接
    ws = websocket.WebSocketApp(ws_url,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    
    # 运行WebSocket连接
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

if __name__ == "__main__":
    main()
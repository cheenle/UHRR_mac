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
        print(f"收到消息: {data}")
        
        if data.get('type') == 'data' and data.get('data'):
            atu_data = data['data']
            print(f"📊 ATU数据 - 功率: {atu_data.get('power')}W, SWR: {atu_data.get('swr')}, 效率: {atu_data.get('efficiency')}%")
        elif data.get('type') == 'status':
            print(f"📋 状态消息: {data}")
    except Exception as e:
        print(f"消息解析错误: {e}")
        print(f"原始消息: {message}")

def on_error(ws, error):
    print(f"WebSocket错误: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket连接已关闭")

def on_open(ws):
    print("✅ WebSocket连接已建立")
    print("开始接收ATU数据...")
    
    # 发送同步命令
    def send_sync():
        while True:
            if ws.sock and ws.sock.connected:
                sync_command = {
                    'type': 'command',
                    'command': 'sync'
                }
                ws.send(json.dumps(sync_command))
                print("📤 已发送同步命令")
                time.sleep(1)
            else:
                break
    
    # 在后台线程中发送同步命令
    sync_thread = threading.Thread(target=send_sync)
    sync_thread.daemon = True
    sync_thread.start()

def main():
    # 连接到UHRR主程序的ATU WebSocket
    ws_url = "wss://localhost:8877/atu/ws"
    
    print(f"尝试连接到: {ws_url}")
    
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
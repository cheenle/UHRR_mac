#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import tornado.httpserver
import ssl
import tornado.ioloop
import tornado.web
import tornado.websocket
import threading
import time
import datetime
import configparser
import sys
import logging
import socket
import struct
import json
import websocket
import json

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('atu_server_websocket_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ATU_SERVER_WEBSOCKET')

# 全局变量
ATU_DEVICE_IP = os.environ.get('ATU_DEVICE_IP', '192.168.1.12')
ATU_DEVICE_PORT = int(os.environ.get('ATU_DEVICE_PORT', '60001'))
ATU_SERVER_PORT = int(os.environ.get('ATU_SERVER_PORT', '8889'))

# ATU设备连接状态
atu_device_connected = False
atu_ws_client = None

# WebSocket客户端列表
atu_ws_clients = []

# ATU命令定义
SCMD_FLAG = 0xFF
SCMD_SYNC = 1
SCMD_METER_STATUS = 2

# UHRR服务器配置
UHRR_SERVER_HOST = '::'
UHRR_SERVER_PORT = 8855


class AtuWebSocketClient:
    """ATU设备WebSocket客户端"""
    
    def __init__(self):
        self.ws = None
        self.running = True
        self.connected = False
        
    def connect(self):
        """连接到ATU设备WebSocket"""
        global atu_device_connected
        
        ws_url = f"ws://{ATU_DEVICE_IP}:{ATU_DEVICE_PORT}/"
        logger.info(f"尝试连接ATU设备WebSocket: {ws_url}")
        
        try:
            self.ws = websocket.WebSocketApp(ws_url,
                                            on_open=self.on_open,
                                            on_message=self.on_message,
                                            on_error=self.on_error,
                                            on_close=self.on_close)
            
            # 在后台线程中运行WebSocket
            def run_ws():
                self.ws.run_forever()
            
            ws_thread = threading.Thread(target=run_ws)
            ws_thread.daemon = True
            ws_thread.start()
            
        except Exception as e:
            logger.error(f"创建WebSocket连接失败: {e}")
    
    def on_open(self, ws):
        """WebSocket连接打开"""
        global atu_device_connected
        
        logger.info("✓ ATU设备WebSocket连接成功")
        self.connected = True
        atu_device_connected = True
        
        # 发送连接成功通知
        self.broadcast_to_clients({
            'type': 'status',
            'message': 'ATU设备已连接',
            'connected': True
        })
        
        # 发送同步命令
        self.send_sync()
        
        # 启动数据请求循环
        self.start_data_request_loop()
    
    def on_message(self, ws, message):
        """接收到ATU设备消息"""
        try:
            # 解析二进制数据
            if isinstance(message, bytes):
                data = bytearray(message)
                logger.debug(f"接收到ATU数据: {len(data)} 字节")
                
                # 解析数据
                parsed_data = self.parse_atu_data(data)
                if parsed_data:
                        
                    # 转发给WebSocket客户端
                    self.broadcast_to_clients({
                        'type': 'data',
                        'data': parsed_data,
                        'timestamp': datetime.datetime.now().isoformat()
                    })
            
        except Exception as e:
            logger.error(f"处理ATU消息错误: {e}")
    
    def on_error(self, ws, error):
        """WebSocket错误"""
        logger.error(f"ATU设备WebSocket错误: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """WebSocket连接关闭"""
        global atu_device_connected
        
        logger.warning("ATU设备WebSocket连接关闭")
        self.connected = False
        atu_device_connected = False
        
        # 发送连接断开通知
        self.broadcast_to_clients({
            'type': 'status',
            'message': 'ATU设备连接断开',
            'connected': False
        })
        
        # 尝试重新连接
        if self.running:
            logger.info("5秒后尝试重新连接...")
            time.sleep(5)
            self.connect()
    
    def parse_atu_data(self, data):
        """解析ATU设备数据"""
        try:
            if len(data) < 10:
                logger.info(f"ATU数据长度不足: {len(data)} 字节")
                return None
            
            # 解析二进制数据
            flag = data[0]
            cmd = data[1]
            data_len = data[2]
            
            # 检查是否为电表数据 (SCMD_METER_STATUS = 2)
            if cmd == SCMD_METER_STATUS and data_len >= 6:
                # 解析功率和SWR数据
                # 正确偏移：SWR(4-5), 功率(6-7), 最大功率(8-9)
                swr = struct.unpack('<H', bytes(data[4:6]))[0]
                fwd_power = struct.unpack('<H', bytes(data[6:8]))[0]  # 正向功率
                max_power = struct.unpack('<H', bytes(data[8:10]))[0]  # 最大功率
                
                # 处理SWR值格式
                display_swr = swr
                if swr >= 100:
                    display_swr = swr / 100.0
                
                # 计算传输效率
                efficiency = 0
                if max_power > 0:
                    efficiency = min(100, (fwd_power / max_power) * 100)
                
                parsed_data = {
                    'power': fwd_power,
                    'swr': round(display_swr, 2),
                    'max_power': max_power,
                    'efficiency': round(efficiency, 1)
                }
                
                logger.info(f"📡 ATU电表数据: 功率={fwd_power}W, SWR={display_swr}, 最大功率={max_power}W, 效率={efficiency}%")
                return parsed_data
            
            return None
            
        except Exception as e:
            logger.error(f"解析ATU数据错误: {e}")
            return None
    
    def send_sync(self):
        """发送同步命令到ATU设备"""
        if self.connected and self.ws:
            try:
                # ATU同步命令: [0xFF, 0x01, 0x00]
                sync_command = bytearray([SCMD_FLAG, SCMD_SYNC, 0x00])
                self.ws.send(sync_command, opcode=websocket.ABNF.OPCODE_BINARY)
            except Exception as e:
                logger.error(f"发送同步命令失败: {e}")
    
    def start_data_request_loop(self):
        """启动数据请求循环"""
        def data_request_loop():
            while self.running and self.connected:
                try:
                    self.send_sync()
                    time.sleep(0.2)  # 每200ms发送一次请求，提高更新频率
                except Exception as e:
                    logger.error(f"数据请求循环错误: {e}")
                    break
        
        data_thread = threading.Thread(target=data_request_loop)
        data_thread.daemon = True
        data_thread.start()
    
    def broadcast_to_clients(self, message):
        """广播消息给所有WebSocket客户端"""
        global atu_ws_clients
        
        for client in atu_ws_clients[:]:  # 使用副本避免修改时迭代
            try:
                client.write_message(json.dumps(message))
            except Exception as e:
                logger.error(f"发送消息到客户端失败: {e}")
                # 移除失效的客户端
                if client in atu_ws_clients:
                    atu_ws_clients.remove(client)
    
    def stop(self):
        """停止客户端"""
        self.running = False
        if self.ws:
            self.ws.close()

class AtuWebSocketHandler(tornado.websocket.WebSocketHandler):
    """ATU监控WebSocket处理器"""
    
    def check_origin(self, origin):
        # 允许跨域访问
        return True
    
    def open(self):
        global atu_ws_clients
        
        if self not in atu_ws_clients:
            atu_ws_clients.append(self)
        
        logger.info(f"新的ATU监控客户端连接，当前客户端数: {len(atu_ws_clients)}")
        logger.info(f"客户端信息: {self.request.remote_ip}, {self.request.headers}")
        
        # 发送当前状态
        self.write_message(json.dumps({
            'type': 'status',
            'message': '连接成功',
            'connected': atu_device_connected
        }))
    
    def on_message(self, message):
        try:
            data = json.loads(message)
            
            if data.get('type') == 'command':
                # 处理客户端命令
                command = data.get('command')
                if command == 'sync':
                    # 发送同步命令到ATU设备
                    if atu_ws_client and atu_ws_client.connected:
                        atu_ws_client.send_sync()
                elif command == 'status':
                    # 返回当前状态
                    self.write_message(json.dumps({
                        'type': 'status',
                        'message': '状态查询',
                        'connected': atu_device_connected
                    }))
                    
        except Exception as e:
            logger.error(f"处理客户端消息错误: {e}")
    
    def on_close(self):
        global atu_ws_clients
        
        if self in atu_ws_clients:
            atu_ws_clients.remove(self)
        
        logger.info(f"ATU监控客户端断开连接，剩余客户端数: {len(atu_ws_clients)}")

class AtuMonitorHandler(tornado.web.RequestHandler):
    """ATU监控页面处理器"""
    
    def get(self):
        try:
            # 读取ATU监控页面
            with open("www/atu_monitor.html", "r") as f:
                content = f.read()
            self.write(content)
        except Exception as e:
            logger.error(f"读取ATU监控页面失败: {e}")
            self.write("<html><body><h1>ATU监控系统</h1><p>页面加载失败，请检查服务器日志。</p></body></html>")

class AtuStatusHandler(tornado.web.RequestHandler):
    """ATU状态API处理器"""
    
    def get(self):
        global atu_device_connected
        
        status = {
            'atu_device_connected': atu_device_connected,
            'atu_device_ip': ATU_DEVICE_IP,
            'atu_device_port': ATU_DEVICE_PORT,
            'websocket_clients': len(atu_ws_clients),
            'server_time': datetime.datetime.now().isoformat()
        }
        
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(status))

def main():
    """主函数"""
    
    # 创建Tornado应用
    app = tornado.web.Application([
        (r'/atu/ws', AtuWebSocketHandler),
        (r'/atu/monitor', AtuMonitorHandler),
        (r'/atu/status', AtuStatusHandler),
        (r'/atu/(.*)', tornado.web.StaticFileHandler, {'path': './www'}),
        (r'/(.*)', tornado.web.StaticFileHandler, {'path': './www'})
    ], debug=True)
    
    # 配置SSL证书
    ssl_options = {
        "certfile": "certs/radio.vlsc.net.pem",
        "keyfile": "certs/radio.vlsc.net.key"
    }
    
    # 启动HTTPS服务器
    http_server = tornado.httpserver.HTTPServer(app, ssl_options=ssl_options)
    # 监听所有IPv6地址，支持远程访问
    http_server.listen(ATU_SERVER_PORT, address='::')
    
    logger.info(f"ATU服务器启动在端口 {ATU_SERVER_PORT}")
    logger.info(f"ATU监控页面: https://[::]:{ATU_SERVER_PORT}/atu/monitor (IPv6)")
    logger.info(f"ATU监控页面: https://localhost:{ATU_SERVER_PORT}/atu/monitor (IPv4)")
    logger.info(f"ATU状态API: https://[::]:{ATU_SERVER_PORT}/atu/status (IPv6)")
    logger.info(f"ATU状态API: https://localhost:{ATU_SERVER_PORT}/atu/status (IPv4)")
    
    # 启动ATU设备WebSocket客户端
    global atu_ws_client
    atu_ws_client = AtuWebSocketClient()
    atu_ws_client.connect()
    
    
    try:
        # 启动Tornado事件循环
        tornado.ioloop.IOLoop.current().start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务器...")
    finally:
        # 清理资源
        if atu_ws_client:
            atu_ws_client.stop()
        
        logger.info("ATU服务器已关闭")

if __name__ == "__main__":
    main()
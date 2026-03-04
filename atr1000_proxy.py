#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATR-1000 天调代理程序 - 独立运行

功能：
1. 通过 WebSocket 连接 ATR-1000 设备
2. 提供 Unix Socket 接口供 UHRR 主程序调用
3. 按需启动/停止，不占用主程序资源

使用方法：
    python3 atr1000_proxy.py --device 192.168.1.63 --port 60001

作者: UHRR Team
"""

import argparse
import json
import logging
import struct
import threading
import time
import socket
import os
import signal
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ATR1000-Proxy')

# ATR-1000 命令常量
SCMD_FLAG = 0xFF
SCMD_SYNC = 1
SCMD_METER_STATUS = 2

# 全局状态
running = True
connected = False
meter_data = {"power": 0, "swr": 0, "connected": False, "temperature": 0}
clients = []  # Unix Socket 客户端列表
data_lock = threading.Lock()

# Unix Socket 路径
UNIX_SOCKET_PATH = "/tmp/atr1000_proxy.sock"


class ATR1000Client:
    """ATR-1000 设备 WebSocket 客户端"""
    
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.ws = None
        self.thread = None
        self.request_interval = 1.0  # 数据请求间隔（秒）
        self.active = False  # 是否有活跃的客户端请求
        
    def connect(self):
        """连接到 ATR-1000 设备"""
        global connected
        
        try:
            import websocket
        except ImportError:
            logger.error("请安装 websocket-client: pip install websocket-client")
            return False
        
        try:
            url = f"ws://{self.host}:{self.port}/"
            logger.info(f"🔌 连接 ATR-1000: {url}")
            
            self.ws = websocket.WebSocketApp(
                url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # 启动 WebSocket 线程
            self.thread = threading.Thread(target=self._run_ws, daemon=True)
            self.thread.start()
            return True
            
        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False
    
    def _run_ws(self):
        """运行 WebSocket"""
        while running:
            try:
                self.ws.run_forever()
            except Exception as e:
                logger.error(f"WebSocket 错误: {e}")
            
            if running:
                logger.info("5秒后重连...")
                time.sleep(5)
    
    def _on_open(self, ws):
        """WebSocket 打开"""
        global connected
        connected = True
        meter_data["connected"] = True
        logger.info("✅ ATR-1000 已连接")
        
        # 发送同步命令
        self._send_sync()
        
        # 启动数据请求线程
        threading.Thread(target=self._request_loop, daemon=True).start()
    
    def _on_message(self, ws, data):
        """收到消息"""
        logger.debug(f"_on_message 被调用, 数据类型: {type(data)}")
        if isinstance(data, bytes):
            self._parse_meter_data(data)
        else:
            logger.debug(f"收到非二进制数据: {data[:50] if len(str(data)) > 50 else data}")
    
    def _on_error(self, ws, error):
        """WebSocket 错误"""
        global connected
        connected = False
        meter_data["connected"] = False
        logger.error(f"ATR-1000 错误: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket 关闭"""
        global connected
        connected = False
        meter_data["connected"] = False
        logger.info("ATR-1000 连接关闭")
    
    def _send_sync(self):
        """发送同步命令"""
        if self.ws and connected:
            try:
                cmd = bytes([SCMD_FLAG, SCMD_SYNC, 0])
                self.ws.send(cmd, opcode=0x02)
            except Exception as e:
                logger.error(f"发送同步命令失败: {e}")
    
    def _request_loop(self):
        """数据请求循环 - 只在有客户端时请求"""
        global running
        
        last_request_time = 0
        
        while running and connected:
            try:
                # 只有在有活跃客户端时才请求
                if self.active and len(clients) > 0:
                    now = time.time()
                    if now - last_request_time >= self.request_interval:
                        self._send_sync()
                        last_request_time = now
                else:
                    # 没有客户端时，每 10 秒发一次心跳
                    now = time.time()
                    if now - last_request_time >= 10:
                        self._send_sync()
                        last_request_time = now
                
                time.sleep(0.1)  # 100ms 检查间隔
                
            except Exception as e:
                logger.error(f"请求循环错误: {e}")
    
    def _parse_meter_data(self, data):
        """解析电表数据"""
        global meter_data
        
        try:
            # 调试：输出原始数据
            logger.debug(f"收到数据: len={len(data)}, hex={data.hex() if len(data) < 30 else data[:30].hex()+'...'}")
            
            if len(data) < 9:
                logger.debug(f"数据长度不足: {len(data)}")
                return
            
            cmd = data[1]
            logger.debug(f"命令类型: {cmd} (METER_STATUS={SCMD_METER_STATUS})")
            
            if cmd == SCMD_METER_STATUS:
                # 解析 SWR 和功率
                swr = struct.unpack("<H", data[4:6])[0]
                fwd = struct.unpack("<H", data[6:8])[0]
                
                logger.info(f"📊 原始数据: SWR={swr}, FWD={fwd}")
                
                # SWR 处理
                if swr >= 100:
                    swr_value = swr / 100.0
                else:
                    swr_value = float(swr)
                
                logger.info(f"📊 解析结果: 功率={fwd}W, SWR={swr_value}")
                
                # 更新数据
                with data_lock:
                    meter_data["power"] = fwd
                    meter_data["swr"] = swr_value
                    meter_data["connected"] = True
                
                # 广播到所有客户端
                broadcast_to_clients()
            else:
                logger.debug(f"非 METER_STATUS 命令: {cmd}")
                
        except Exception as e:
            logger.error(f"解析数据错误: {e}")
    
    def set_active(self, active):
        """设置活跃状态"""
        self.active = active
        logger.debug(f"ATR-1000 活跃状态: {active}")
    
    def close(self):
        """关闭连接"""
        if self.ws:
            try:
                self.ws.close()
            except:
                pass


def broadcast_to_clients():
    """广播数据到所有 Unix Socket 客户端"""
    global meter_data, clients
    
    if not clients:
        return
    
    with data_lock:
        data = json.dumps({
            "type": "atr1000_meter",
            "power": meter_data["power"],
            "swr": meter_data["swr"],
            "connected": meter_data["connected"]
        })
    
    for client in clients[:]:
        try:
            client.send(data.encode())
        except Exception as e:
            logger.debug(f"发送到客户端失败: {e}")
            clients.remove(client)


def handle_unix_client(conn, addr, atr1000):
    """处理 Unix Socket 客户端"""
    global clients
    
    clients.append(conn)
    logger.info(f"新客户端连接，当前 {len(clients)} 个")
    
    # 有客户端连接，激活数据请求
    atr1000.set_active(True)
    
    try:
        while running:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                
                # 解析命令
                try:
                    msg = json.loads(data.decode())
                    action = msg.get("action")
                    
                    if action == "start":
                        atr1000.set_active(True)
                        logger.info("客户端请求启动数据流")
                    
                    elif action == "stop":
                        atr1000.set_active(False)
                        logger.info("客户端请求停止数据流")
                    
                    elif action == "get_data":
                        # 立即发送当前数据
                        with data_lock:
                            response = json.dumps({
                                "type": "atr1000_meter",
                                "power": meter_data["power"],
                                "swr": meter_data["swr"],
                                "connected": meter_data["connected"]
                            })
                        conn.send(response.encode())
                    
                except json.JSONDecodeError:
                    pass
                
            except socket.timeout:
                continue
            except Exception as e:
                logger.debug(f"客户端处理错误: {e}")
                break
    
    finally:
        clients.remove(conn)
        conn.close()
        logger.info(f"客户端断开，剩余 {len(clients)} 个")
        
        # 没有客户端时，停止数据请求
        if not clients:
            atr1000.set_active(False)


def run_unix_server(atr1000):
    """运行 Unix Socket 服务器"""
    global running
    
    # 清理旧的 socket 文件
    if os.path.exists(UNIX_SOCKET_PATH):
        os.unlink(UNIX_SOCKET_PATH)
    
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(UNIX_SOCKET_PATH)
    server.listen(5)
    server.settimeout(1.0)
    
    logger.info(f"🔌 Unix Socket 服务器启动: {UNIX_SOCKET_PATH}")
    
    try:
        while running:
            try:
                conn, addr = server.accept()
                conn.settimeout(1.0)
                threading.Thread(
                    target=handle_unix_client,
                    args=(conn, addr, atr1000),
                    daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception as e:
                if running:
                    logger.error(f"Unix Socket 错误: {e}")
    finally:
        server.close()
        if os.path.exists(UNIX_SOCKET_PATH):
            os.unlink(UNIX_SOCKET_PATH)
        logger.info("Unix Socket 服务器关闭")


def signal_handler(sig, frame):
    """信号处理"""
    global running
    logger.info("收到终止信号，正在关闭...")
    running = False
    sys.exit(0)


def main():
    global running
    
    parser = argparse.ArgumentParser(description='ATR-1000 天调代理')
    parser.add_argument('--device', default='192.168.1.63', help='ATR-1000 设备 IP')
    parser.add_argument('--port', type=int, default=60001, help='ATR-1000 WebSocket 端口')
    parser.add_argument('--interval', type=float, default=1.0, help='数据请求间隔（秒）')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 50)
    logger.info("ATR-1000 天调代理程序启动")
    logger.info(f"设备地址: {args.device}:{args.port}")
    logger.info(f"数据间隔: {args.interval} 秒")
    logger.info("=" * 50)
    
    # 创建 ATR-1000 客户端
    atr1000 = ATR1000Client(args.device, args.port)
    atr1000.request_interval = args.interval
    
    # 连接设备
    if not atr1000.connect():
        logger.error("无法连接 ATR-1000，将自动重试")
    
    # 启动 Unix Socket 服务器
    unix_thread = threading.Thread(
        target=run_unix_server,
        args=(atr1000,),
        daemon=True
    )
    unix_thread.start()
    
    # 主循环
    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        running = False
        atr1000.close()
        logger.info("ATR-1000 代理程序已停止")


if __name__ == '__main__':
    main()

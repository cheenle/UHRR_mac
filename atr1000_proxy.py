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
SCMD_METER_STATUS = 2      # 电表状态（功率、SWR）
SCMD_TUNE_STATUS = 3       # 调谐状态
SCMD_TUNE_MODE = 4         # 调谐模式
SCMD_RELAY_STATUS = 5      # 继电器状态（LC/CL、电感、电容）
SCMD_MEMORY_STATUS = 6     # 存储状态
SCMD_MEMORY_INFO = 7       # 存储信息

# 全局状态
running = True
connected = False
meter_data = {
    "power": 0, 
    "swr": 0, 
    "connected": False, 
    "temperature": 0,
    "sw": 0,        # 网络类型: 0=LC, 1=CL
    "ind": 0,       # 电感索引
    "cap": 0,       # 电容索引
    "ind_uh": 0.0,  # 电感值 (uH)
    "cap_pf": 0     # 电容值 (pF)
}
clients = []  # Unix Socket 客户端列表
data_lock = threading.Lock()
last_broadcast_time = 0  # 上次广播时间（用于节流）

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
        """数据请求循环 - ATR-1000 设备主动推送数据，TX 期间定期发送 SYNC"""
        global running
        
        last_sync_time = 0
        last_data_time = 0  # 上次收到数据的时间
        
        while running and connected:
            try:
                now = time.time()
                
                # TX 活跃期间：每 500ms 发送一次 SYNC 确保数据流
                if self.active and len(clients) > 0:
                    if now - last_sync_time >= 0.5:  # TX 期间每 500ms 一次
                        self._send_sync()
                        last_sync_time = now
                else:
                    # 非 TX 期间：每 5 秒发送一次 SYNC 保持连接
                    if now - last_sync_time >= 5.0:
                        self._send_sync()
                        last_sync_time = last_data_time = now
                
                time.sleep(0.05)  # 50ms 检查间隔，更快响应
                
            except Exception as e:
                logger.error(f"请求循环错误: {e}")
    
    def _parse_meter_data(self, data):
        """解析 ATR-1000 数据 - 支持电表状态和继电器状态"""
        global meter_data
        
        try:
            # 数据长度检查
            if len(data) < 3:
                return  # 忽略极短帧
            
            # 检查帧头
            if data[0] != SCMD_FLAG:
                return  # 忽略非标准帧
            
            cmd = data[1]
            
            # 根据命令类型解析
            if cmd == SCMD_METER_STATUS:
                # 电表状态（功率、SWR）
                if len(data) < 10:
                    return
                
                swr_raw = struct.unpack("<H", data[4:6])[0]
                fwd = struct.unpack("<H", data[6:8])[0]
                maxfwd = struct.unpack("<H", data[8:10])[0]
                
                # SWR 处理
                if swr_raw >= 100:
                    swr_value = swr_raw / 100.0
                elif swr_raw == 0:
                    swr_value = 1.0
                else:
                    swr_value = float(swr_raw)
                
                logger.info(f"📊 功率={fwd}W, SWR={swr_value:.2f}, 最大功率={maxfwd}W")
                
                with data_lock:
                    meter_data["power"] = fwd
                    meter_data["swr"] = swr_value
                    meter_data["connected"] = True
                
                broadcast_to_clients()
                
            elif cmd == SCMD_RELAY_STATUS:
                # 继电器状态（LC/CL、电感、电容）
                if len(data) < 10:
                    return
                
                # 官方 JS 代码:
                # const relayData = {
                #     sw: dataView.getUint8(3),
                #     ind: dataView.getUint8(4),
                #     cap: dataView.getUint8(5),
                #     L: dataView.getUint16(6, true) / 100,  // 电感值 uH
                #     C: dataView.getUint16(8, true)         // 电容值 pF
                # };
                sw = data[3]           # 网络类型: 0=LC, 1=CL
                ind = data[4]          # 电感索引
                cap = data[5]          # 电容索引
                ind_uh = struct.unpack("<H", data[6:8])[0] / 100.0  # 电感值 uH
                cap_pf = struct.unpack("<H", data[8:10])[0]          # 电容值 pF
                
                sw_text = "LC" if sw == 0 else "CL"
                logger.info(f"🎛️ 继电器: {sw_text}, 电感={ind_uh:.2f}uH (索引{ind}), 电容={cap_pf}pF (索引{cap})")
                
                with data_lock:
                    meter_data["sw"] = sw
                    meter_data["ind"] = ind
                    meter_data["cap"] = cap
                    meter_data["ind_uh"] = ind_uh
                    meter_data["cap_pf"] = cap_pf
                
                broadcast_to_clients()
                
            # 其他命令类型静默忽略
                
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
    
    def set_relay(self, sw: int, ind: int, cap: int):
        """
        设置继电器参数
        
        Args:
            sw: 网络类型 (0=LC, 1=CL)
            ind: 电感索引 (0-127)
            cap: 电容索引 (0-127)
        """
        if self.ws and connected:
            try:
                # 根据官方 JS: setRelayStatus(sw, ind, cap)
                # buffer: [FLAG, SCMD_RELAY_STATUS, len, sw, ind, cap]
                cmd = bytes([SCMD_FLAG, SCMD_RELAY_STATUS, 3, sw, ind, cap])
                self.ws.send(cmd, opcode=0x02)
                logger.info(f"发送继电器命令: SW={sw}, IND={ind}, CAP={cap}")
            except Exception as e:
                logger.error(f"发送继电器命令失败: {e}")
    
    def start_tune(self, mode: int = 2):
        """
        启动自动调谐
        
        Args:
            mode: 调谐模式
                0 = 重置状态
                1 = 内存调谐
                2 = 完整调谐
                3 = 微调调谐
        """
        if self.ws and connected:
            try:
                # 根据官方 JS: setTuneMode(mode)
                # buffer: [FLAG, SCMD_TUNE_MODE, len, mode]
                cmd = bytes([SCMD_FLAG, SCMD_TUNE_MODE, 1, mode])
                self.ws.send(cmd, opcode=0x02)
                logger.info(f"发送调谐命令: mode={mode}")
            except Exception as e:
                logger.error(f"发送调谐命令失败: {e}")
    
    def set_tune_status(self, is_tune: bool):
        """
        设置调谐状态（信号直通/调谐状态）
        
        Args:
            is_tune: True=调谐状态, False=信号直通
        """
        if self.ws and connected:
            try:
                cmd = bytes([SCMD_FLAG, SCMD_TUNE_STATUS, 1, 1 if is_tune else 0])
                self.ws.send(cmd, opcode=0x02)
                logger.info(f"设置调谐状态: {is_tune}")
            except Exception as e:
                logger.error(f"设置调谐状态失败: {e}")


def broadcast_to_clients():
    """广播数据到所有 Unix Socket 客户端"""
    global meter_data, clients, last_broadcast_time
    
    client_count = len(clients)
    if client_count == 0:
        return
    
    # 节流：最多每 200ms 广播一次（提高响应速度）
    now = time.time()
    if now - last_broadcast_time < 0.2:
        return
    last_broadcast_time = now
    
    with data_lock:
        data = json.dumps({
            "type": "atr1000_meter",
            "power": meter_data["power"],
            "swr": meter_data["swr"],
            "connected": meter_data["connected"],
            # 继电器状态
            "sw": meter_data.get("sw", 0),
            "ind": meter_data.get("ind", 0),
            "cap": meter_data.get("cap", 0),
            "ind_uh": meter_data.get("ind_uh", 0.0),
            "cap_pf": meter_data.get("cap_pf", 0)
        })
    
    # 打印广播日志（只在有实际功率时）
    if meter_data["power"] > 0:
        logger.info(f"📤 广播: 功率={meter_data['power']}W, SWR={meter_data['swr']:.2f}")
    
    # 复制客户端列表以避免在迭代时修改
    clients_copy = clients[:]
    
    for client in clients_copy:
        try:
            client.send(data.encode())
        except Exception as e:
            logger.warning(f"发送到客户端失败: {e}")


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
                                "connected": meter_data["connected"],
                                "sw": meter_data.get("sw", 0),
                                "ind": meter_data.get("ind", 0),
                                "cap": meter_data.get("cap", 0),
                                "ind_uh": meter_data.get("ind_uh", 0.0),
                                "cap_pf": meter_data.get("cap_pf", 0)
                            })
                        conn.send(response.encode())
                    
                    elif action == "set_relay":
                        # 设置继电器参数
                        sw = msg.get("sw", 0)
                        ind = msg.get("ind", 0)
                        cap = msg.get("cap", 0)
                        atr1000.set_relay(sw, ind, cap)
                        logger.info(f"设置继电器: SW={sw}, IND={ind}, CAP={cap}")
                    
                    elif action == "tune":
                        # 启动自动调谐
                        mode = msg.get("mode", 2)  # 默认完整调谐
                        atr1000.start_tune(mode)
                        logger.info(f"启动自动调谐: mode={mode}")
                        
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

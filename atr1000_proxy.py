#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATR-1000 天调代理程序 - V4.5.15 增强版

设计理念：主动轮询 + 缓存广播 + 智能学习
1. 每 0.5 秒主动向 ATR-1000 发送 SYNC 获取数据
2. 数据缓存在本地
3. 客户端请求时直接返回缓存数据（不再请求设备）
4. 自动学习 SWR 1.0-1.5 的天调参数
5. 支持快速调谐到指定频率

使用方法：
    python3 atr1000_proxy.py --device 192.168.1.63 --port 60001

作者: MRRC Team
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

# 导入天调存储模块
from atr1000_tuner import get_storage

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

# ========== 简化的全局状态 ==========
running = True
connected = False
last_data_time = 0

# 缓存数据（主动轮询更新，客户端直接读取）
cache = {
    "power": 0,
    "swr": 1.0,
    "connected": False,
    "sw": 0,        # 网络类型: 0=LC, 1=CL
    "ind": 0,       # 电感索引
    "cap": 0,       # 电容索引
    "ind_uh": 0.0,  # 电感值 (uH)
    "cap_pf": 0,    # 电容值 (pF)
    "freq": 0       # 当前频率 (Hz) - 用于学习
}
cache_lock = threading.Lock()

clients = []  # Unix Socket 客户端列表

# Unix Socket 路径
UNIX_SOCKET_PATH = "/tmp/atr1000_proxy.sock"

# 轮询间隔（秒）
POLL_INTERVAL = 0.5


class ATR1000Client:
    """ATR-1000 设备 WebSocket 客户端 - 简化版"""
    
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.ws = None
        self.thread = None
        
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
        """WebSocket 打开 - V4.5.14: 主动轮询模式
        
        连接成功后启动主动轮询线程，每 0.5 秒发送 SYNC。
        """
        global connected, last_data_time, cache
        connected = True
        last_data_time = time.time()
        
        with cache_lock:
            cache["connected"] = True
        
        logger.info("✅ ATR-1000 已连接，启动主动轮询")
        
        # 启动主动轮询线程
        threading.Thread(target=self._poll_loop, daemon=True).start()
    
    def _on_message(self, ws, data):
        """收到消息 - 更新缓存"""
        global last_data_time
        last_data_time = time.time()
        
        if isinstance(data, bytes) and len(data) >= 3:
            self._parse_data(data)
    
    def _poll_loop(self):
        """主动轮询循环 - 每 0.5 秒发送 SYNC
        
        V4.5.14 核心设计：
        - 主动轮询，不等待客户端请求
        - 数据缓存，客户端直接读取
        """
        global connected, cache
        
        # 连接后立即发送第一次 SYNC
        self._send_sync()
        
        while running and connected:
            time.sleep(POLL_INTERVAL)
            if connected and self.ws:
                try:
                    self._send_sync()
                except Exception as e:
                    logger.error(f"发送 SYNC 失败: {e}")
                    break
        
        logger.info("🔄 轮询线程结束")
    
    def _on_error(self, ws, error):
        """WebSocket 错误"""
        global connected, cache
        connected = False
        with cache_lock:
            cache["connected"] = False
        logger.error(f"ATR-1000 错误: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket 关闭"""
        global connected, cache
        connected = False
        with cache_lock:
            cache["connected"] = False
        logger.info("ATR-1000 连接关闭")
    
    def _send_sync(self):
        """发送同步命令"""
        if self.ws and connected:
            try:
                cmd = bytes([SCMD_FLAG, SCMD_SYNC, 0])
                self.ws.send(cmd, opcode=0x02)
            except Exception as e:
                logger.error(f"发送 SYNC 失败: {e}")
    
    def _parse_data(self, data):
        """解析 ATR-1000 数据 - V4.5.14 简化版
        
        只解析功率/SWR 和继电器状态，更新缓存。
        """
        global cache
        
        if len(data) < 3 or data[0] != SCMD_FLAG:
            return
        
        cmd = data[1]
        
        with cache_lock:
            if cmd == SCMD_METER_STATUS and len(data) >= 10:
                # 功率/SWR
                swr_raw = struct.unpack('<H', data[4:6])[0]
                power = struct.unpack('<H', data[6:8])[0]

                # SWR 处理：>=100 时除以 100
                if swr_raw >= 100:
                    cache["swr"] = swr_raw / 100.0
                else:
                    cache["swr"] = swr_raw
                
                cache["power"] = power
                
                # V4.5.15: 自动学习天调参数
                # 当有功率且 SWR 在 1.0-1.5 时记录
                if power > 0 and 1.0 <= cache["swr"] <= 1.5:
                    freq = cache.get("freq", 0)
                    if freq > 0:
                        try:
                            tuner = get_storage()
                            tuner.learn(
                                freq=freq,
                                sw=cache["sw"],
                                ind=cache["ind"],
                                cap=cache["cap"],
                                swr=cache["swr"]
                            )
                        except Exception as e:
                            logger.debug(f"学习天调参数失败: {e}")
                
            elif cmd == SCMD_RELAY_STATUS and len(data) >= 11:
                # 继电器状态
                cache["sw"] = data[3]      # 网络类型
                cache["ind"] = data[4]     # 电感索引
                cache["cap"] = data[5]     # 电容索引
                
                # 计算实际值
                L = struct.unpack('<H', data[6:8])[0]
                C = struct.unpack('<H', data[8:10])[0]
                cache["ind_uh"] = L / 100.0
                cache["cap_pf"] = C
    
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
                pass


def handle_unix_client(conn, addr, atr1000):
    """处理 Unix Socket 客户端 - V4.5.15 增强版
    
    支持命令：
    - sync/get_data: 获取缓存数据
    - set_freq: 设置当前频率（用于学习）
    - quick_tune: 快速调谐到指定频率
    - get_tune_records: 获取所有天调记录
    - set_relay: 设置继电器参数
    - tune: 启动自动调谐
    """
    global clients, cache
    
    clients.append(conn)
    logger.info(f"新客户端连接，当前 {len(clients)} 个")
    
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
                    
                    if action in ("sync", "get_data"):
                        # 直接返回缓存数据
                        with cache_lock:
                            response = json.dumps({
                                "type": "atr1000_meter",
                                "power": cache["power"],
                                "swr": cache["swr"],
                                "connected": cache["connected"],
                                "sw": cache["sw"],
                                "ind": cache["ind"],
                                "cap": cache["cap"],
                                "ind_uh": cache["ind_uh"],
                                "cap_pf": cache["cap_pf"],
                                "freq": cache.get("freq", 0)
                            }) + "\n"
                        conn.send(response.encode())
                    
                    elif action == "set_freq":
                        # 设置当前频率（用于学习）
                        freq = msg.get("freq", 0)
                        with cache_lock:
                            cache["freq"] = freq
                        logger.info(f"设置频率: {freq}Hz")
                        conn.send(json.dumps({"type": "ack", "action": "set_freq", "freq": freq}).encode())
                    
                    elif action == "quick_tune":
                        # V4.5.15: 快速调谐到指定频率
                        freq = msg.get("freq", 0)
                        if freq > 0:
                            tuner = get_storage()
                            params = tuner.get_tune_params(freq)
                            if params:
                                sw, ind, cap = params
                                atr1000.set_relay(sw, ind, cap)
                                response = json.dumps({
                                    "type": "quick_tune_result",
                                    "success": True,
                                    "freq": freq,
                                    "sw": sw,
                                    "ind": ind,
                                    "cap": cap
                                }) + "\n"
                                logger.info(f"🎯 快速调谐: {freq/1000:.1f}kHz -> SW={'CL' if sw else 'LC'}, L={ind}, C={cap}")
                            else:
                                response = json.dumps({
                                    "type": "quick_tune_result",
                                    "success": False,
                                    "freq": freq,
                                    "message": "未找到匹配的天调参数"
                                }) + "\n"
                                logger.info(f"快速调谐失败: {freq/1000:.1f}kHz 无匹配参数")
                        else:
                            response = json.dumps({
                                "type": "quick_tune_result",
                                "success": False,
                                "message": "频率参数无效"
                            }) + "\n"
                        conn.send(response.encode())
                    
                    elif action == "get_tune_records":
                        # 获取所有天调记录
                        tuner = get_storage()
                        records = tuner.get_all()
                        response = json.dumps({
                            "type": "tune_records",
                            "count": len(records),
                            "records": records
                        }) + "\n"
                        conn.send(response.encode())
                    
                    elif action == "delete_tune_record":
                        # 删除天调记录
                        freq = msg.get("freq", 0)
                        if freq > 0:
                            tuner = get_storage()
                            deleted = tuner.delete(freq)
                            response = json.dumps({
                                "type": "delete_result",
                                "success": deleted,
                                "freq": freq
                            }) + "\n"
                            conn.send(response.encode())
                    
                    elif action == "start":
                        logger.info("客户端请求启动数据流")
                    
                    elif action == "stop":
                        logger.info("客户端请求停止数据流")
                    
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
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as e:
                logger.info(f"客户端连接断开: {type(e).__name__}")
                break
            except Exception as e:
                logger.debug(f"客户端处理错误: {e}")
                break
    
    finally:
        clients.remove(conn)
        conn.close()
        logger.info(f"客户端断开，剩余 {len(clients)} 个")


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

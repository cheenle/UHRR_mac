#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATR-1000 天调代理程序 - V4.5.18 通讯日志版

设计理念：动态轮询 + 缓存广播 + 智能学习 + 通讯监控
1. 动态轮询间隔，防止设备过载：
   - 空闲时：30秒
   - 有客户端：10秒
   - TX期间：0.5秒
2. 数据缓存在本地
3. 客户端请求时直接返回缓存数据（不再请求设备）
4. 自动学习 SWR 1.0-1.5 的天调参数
5. 支持快速调谐到指定频率
6. V4.5.18: 专门的通讯日志记录，分析设备压力

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
from datetime import datetime
from collections import deque

# 导入天调存储模块
from atr1000_tuner import get_storage

# 配置主日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ATR1000-Proxy')

# ========== 通讯日志配置 ==========
# 专门的通讯日志文件，用于分析设备压力和优化
COMM_LOG_FILE = None  # 将在 main() 中设置
comm_logger = None    # 通讯日志记录器

# 通讯统计
comm_stats = {
    'sync_sent': 0,        # 发送的 SYNC 命令数
    'meter_received': 0,   # 接收的功率/SWR 数据数
    'relay_received': 0,   # 接收的继电器状态数
    'relay_sent': 0,       # 发送的继电器命令数
    'tune_sent': 0,        # 发送的调谐命令数
    'bytes_sent': 0,       # 发送的字节数
    'bytes_received': 0,   # 接收的字节数
    'start_time': 0,       # 启动时间
    'poll_intervals': deque(maxlen=100),  # 最近100次轮询间隔
    'tx_count': 0,         # TX 模式进入次数
    'tx_total_time': 0,    # TX 模式总时间
    'tx_start_time': 0,    # 当前 TX 开始时间
}

def setup_comm_logger(instance=None):
    """设置通讯日志记录器"""
    global COMM_LOG_FILE, comm_logger
    
    # 日志文件名
    if instance:
        COMM_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'atr1000_comm_{instance}.log')
    else:
        COMM_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'atr1000_comm.log')
    
    # 创建专门的通讯日志记录器
    comm_logger = logging.getLogger('ATR1000-Comm')
    comm_logger.setLevel(logging.DEBUG)
    
    # 文件处理器
    fh = logging.FileHandler(COMM_LOG_FILE, mode='w')
    fh.setLevel(logging.DEBUG)
    
    # 格式：时间戳 | 方向 | 类型 | 数据 | 说明
    formatter = logging.Formatter('%(asctime)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S.%f')
    fh.setFormatter(formatter)
    
    comm_logger.addHandler(fh)
    
    # 记录启动信息
    comm_logger.info("=" * 80)
    comm_logger.info("START | ATR-1000 通讯监控启动")
    comm_logger.info("=" * 80)
    comm_logger.info("格式: 时间 | 方向 | 类型 | 数据(HEX) | 说明")
    comm_logger.info("-" * 80)
    
    comm_stats['start_time'] = time.time()
    
    return comm_logger

def log_comm(direction, msg_type, data_hex, description):
    """记录通讯日志
    
    Args:
        direction: TX(发送) / RX(接收)
        msg_type: SYNC / METER / RELAY / TUNE
        data_hex: 数据的十六进制表示
        description: 描述信息
    """
    if comm_logger:
        # METER 数据使用 DEBUG 级别，减少日志输出
        if msg_type == 'METER':
            comm_logger.debug(f"{direction:>3} | {msg_type:<8} | {data_hex:<30} | {description}")
        else:
            comm_logger.info(f"{direction:>3} | {msg_type:<8} | {data_hex:<30} | {description}")

def log_poll_interval(interval, reason):
    """记录轮询间隔变化"""
    if comm_logger:
        comm_logger.info(f"POLL | 间隔: {interval}s | 原因: {reason}")
        comm_stats['poll_intervals'].append(interval)

def log_stats_summary():
    """输出通讯统计摘要"""
    if comm_logger and comm_stats['start_time'] > 0:
        elapsed = time.time() - comm_stats['start_time']
        if elapsed > 0:
            comm_logger.info("=" * 80)
            comm_logger.info("通讯统计摘要:")
            comm_logger.info("-" * 80)
            comm_logger.info(f"运行时间: {elapsed:.1f} 秒 ({elapsed/60:.1f} 分钟)")
            comm_logger.info(f"发送 SYNC: {comm_stats['sync_sent']} 次 ({comm_stats['sync_sent']/elapsed:.2f}/秒)")
            comm_logger.info(f"接收 METER: {comm_stats['meter_received']} 次 ({comm_stats['meter_received']/elapsed:.2f}/秒)")
            comm_logger.info(f"接收 RELAY: {comm_stats['relay_received']} 次")
            comm_logger.info(f"发送 RELAY: {comm_stats['relay_sent']} 次")
            comm_logger.info(f"发送 TUNE: {comm_stats['tune_sent']} 次")
            comm_logger.info(f"发送字节: {comm_stats['bytes_sent']} ({comm_stats['bytes_sent']/elapsed:.1f} B/s)")
            comm_logger.info(f"接收字节: {comm_stats['bytes_received']} ({comm_stats['bytes_received']/elapsed:.1f} B/s)")
            comm_logger.info(f"TX 模式: {comm_stats['tx_count']} 次, 总时间 {comm_stats['tx_total_time']:.1f} 秒")
            
            if comm_stats['poll_intervals']:
                avg_interval = sum(comm_stats['poll_intervals']) / len(comm_stats['poll_intervals'])
                comm_logger.info(f"平均轮询间隔: {avg_interval:.2f} 秒")
            
            # 压力评估
            sync_per_sec = comm_stats['sync_sent'] / elapsed
            if sync_per_sec > 2:
                pressure = "🔴 高"
            elif sync_per_sec > 1:
                pressure = "🟡 中"
            else:
                pressure = "🟢 低"
            comm_logger.info(f"设备压力评估: {pressure} (SYNC {sync_per_sec:.2f}/秒)")
            comm_logger.info("=" * 80)

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
client_count = 0      # 当前连接的客户端数量
is_tx = False         # 是否正在发射

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

# 上次设置的继电器参数（用于节流）
last_relay_params = None
relay_throttle_time = 0

# 上次日志输出的值（用于减少日志频率）
last_log_power = 0
last_log_swr = 1.0
last_log_relay = None
last_learn_freq = 0  # 上次学习的频率（用于减少学习日志频率）
last_zero_power_log_time = 0  # 上次记录功率为0的时间（用于节流）

def set_relay_with_throttle(atr1000, sw, ind, cap):
    """带节流的继电器设置 - V4.5.19 增强版
    
    节流策略：
    1. 参数相同时：最小间隔 5 秒
    2. 参数变化时：立即发送
    3. 使用严格的时间比较，避免同一毫秒内的重复发送
    """
    global last_relay_params, relay_throttle_time
    
    current_params = (sw, ind, cap)
    current_time = time.time()
    
    # 计算时间差（处理首次调用）
    if relay_throttle_time > 0:
        time_diff = current_time - relay_throttle_time
    else:
        time_diff = 999  # 首次调用，视为时间已过
    
    # 检查参数是否变化
    params_changed = (last_relay_params is None) or (current_params != last_relay_params)
    
    # 决定是否发送
    should_send = params_changed or (time_diff >= 5.0)
    
    if should_send:
        atr1000.set_relay(sw, ind, cap)
        last_relay_params = current_params
        relay_throttle_time = current_time
        logger.debug(f"继电器命令已发送: SW={sw}, IND={ind}, CAP={cap} (参数变化:{params_changed}, 时间差:{time_diff:.2f}s)")
        return True
    else:
        logger.debug(f"继电器命令被节流: SW={sw}, IND={ind}, CAP={cap} (时间差:{time_diff:.2f}s)")
    return False


clients = []  # Unix Socket 客户端列表

# Unix Socket 路径
UNIX_SOCKET_PATH = "/tmp/atr1000_proxy.sock"

# 轮询间隔（秒）- V4.5.19 优化版：大幅降低设备压力
POLL_INTERVAL_IDLE = 600.0    # 空闲时：60秒一次（大幅降低压力）
POLL_INTERVAL_ACTIVE = 300.0  # 有客户端时：30秒一次（降低压力）
POLL_INTERVAL_TX = 300.0       # TX期间：不发送SYNC，设备会主动推送数据！


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
        """WebSocket 打开 - V4.5.17: 动态轮询模式
        
        连接成功后启动主动轮询线程，动态调整轮询间隔：
        - 空闲时：3秒
        - 有客户端：1秒
        - TX期间：0.5秒
        """
        global connected, last_data_time, cache
        connected = True
        last_data_time = time.time()
        
        with cache_lock:
            cache["connected"] = True
        
        logger.info("✅ ATR-1000 已连接，启动动态轮询")
        
        # 启动主动轮询线程
        threading.Thread(target=self._poll_loop, daemon=True).start()
    
    def _on_message(self, ws, data):
        """收到消息 - 更新缓存（V4.5.17: 减少日志输出）"""
        global last_data_time
        last_data_time = time.time()
        
        if isinstance(data, bytes) and len(data) >= 3:
            self._parse_data(data)
    
    def _poll_loop(self):
        """主动轮询循环 - V4.5.19: 大幅优化设备压力
        
        核心优化：
        - 空闲时：60秒轮询一次
        - 有客户端连接：30秒轮询一次
        - TX期间：不发送SYNC！设备会主动推送数据
        
        关键发现：ATR-1000 设备在 TX 模式下会主动持续推送数据，
        不需要 SYNC 查询。SYNC 只用于获取初始状态和空闲时的心跳。
        """
        global connected, cache, client_count, is_tx
        
        # 连接后立即发送第一次 SYNC
        self._send_sync()
        log_poll_interval(0, '初始同步')
        
        last_interval = 0
        while running and connected:
            # 根据状态选择轮询间隔
            if is_tx:
                # TX模式下不发送SYNC，设备会主动推送数据
                interval = 5000.0  # 只是检查连接状态
                reason = 'TX模式(不发送SYNC)'
                
                # TX模式下等待，不发送SYNC
                time.sleep(interval)
                continue
            elif client_count > 0:
                interval = POLL_INTERVAL_ACTIVE
                reason = f'有{client_count}个客户端'
            else:
                interval = POLL_INTERVAL_IDLE
                reason = '空闲'
            
            # 记录间隔变化
            if interval != last_interval:
                log_poll_interval(interval, reason)
                last_interval = interval
            
            time.sleep(interval)
            
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
        """发送同步命令 - V4.5.18: 记录通讯日志"""
        if self.ws and connected:
            try:
                cmd = bytes([SCMD_FLAG, SCMD_SYNC, 0])
                self.ws.send(cmd, opcode=0x02)
                
                # 通讯日志
                comm_stats['sync_sent'] += 1
                comm_stats['bytes_sent'] += len(cmd)
                log_comm('TX', 'SYNC', cmd.hex(), f'第{comm_stats["sync_sent"]}次')
            except Exception as e:
                logger.error(f"发送 SYNC 失败: {e}")
    
    def _parse_data(self, data):
        """解析 ATR-1000 数据 - V4.5.18 通讯日志版
        
        只解析功率/SWR 和继电器状态，更新缓存。
        自动学习：当功率 > 0 且 SWR 在 1.0-1.5 且参数有效时记录
        只在数据变化时输出日志，减少日志频率
        V4.5.18: 添加通讯日志记录
        """
        global cache, last_log_power, last_log_swr, last_log_relay, last_learn_freq
        
        if len(data) < 3 or data[0] != SCMD_FLAG:
            return
        
        cmd = data[1]
        
        # 通讯统计
        comm_stats['bytes_received'] += len(data)
        
        with cache_lock:
            if cmd == SCMD_METER_STATUS and len(data) >= 8:
                # 通讯日志
                comm_stats['meter_received'] += 1
                
                # 功率/SWR
                # 数据格式: FF 02 07 00 SWR_L SWR_H P_L P_H ...
                swr_raw = struct.unpack('<H', data[4:6])[0]
                power = struct.unpack('<H', data[6:8])[0]

                # SWR 处理：
                # >= 100: 除以 100 (如 147 → 1.47)
                # 1-99: 直接使用 (整数 SWR)
                # 0: 功率>0 时设为 1.0 (完美匹配)，否则保持 1.0
                if swr_raw >= 100:
                    cache["swr"] = swr_raw / 100.0
                elif swr_raw > 0:
                    cache["swr"] = float(swr_raw)
                else:
                    # swr_raw = 0，可能意味着反射功率为 0 (完美匹配)
                    # 或者设备未就绪。有功率时假设完美匹配
                    cache["swr"] = 1.0 if power > 0 else 1.0
                
                cache["power"] = power
                
                # 通讯日志 - 功率/SWR 数据
                if power > 0:
                    log_comm('RX', 'METER', data[:8].hex(), f'功率={power}W, SWR={cache["swr"]:.2f}')
                
                # 日志记录：TX 模式下记录变化，功率为0时限制频率
                if is_tx:
                    if power > 0:
                        logger.info(f"📊 功率/SWR: {power}W, SWR={cache['swr']:.2f}")
                    else:
                        # V4.5.18: 功率为0的日志节流，每5秒最多记录一次
                        import time
                        global last_zero_power_log_time
                        current_time = time.time()
                        if current_time - last_zero_power_log_time > 5:
                            logger.warning(f"📊 功率为 0！SWR={cache['swr']:.2f}")
                            last_zero_power_log_time = current_time
                elif power > 0 and (abs(power - last_log_power) > 1 or abs(cache["swr"] - last_log_swr) > 0.1):
                    # 非 TX 模式：只记录变化
                    logger.info(f"📊 功率/SWR: {power}W, SWR={cache['swr']:.2f}")
                
                last_log_power = power
                last_log_swr = cache["swr"]
                
                # V4.5.16: 智能学习天调参数
                # 条件：功率 > 0, SWR 1.01-1.5 (排除SWR=1.0的假数据), 参数有效（ind>0 或 cap>0）, 频率 > 0
                if power > 0 and 1.01 <= cache["swr"] <= 1.8:
                    freq = cache.get("freq", 0)
                    ind = cache.get("ind", 0)
                    cap = cache.get("cap", 0)
                    
                    # 检查参数有效性
                    if freq > 0 and (ind > 0 or cap > 0):
                        try:
                            tuner = get_storage()
                            if tuner.learn(
                                freq=freq,
                                sw=cache["sw"],
                                ind=ind,
                                cap=cap,
                                swr=cache["swr"]
                            ):
                                # 只在频率变化时输出学习日志，减少重复
                                if freq != last_learn_freq:
                                    logger.info(f"📝 学习成功: {freq/1000:.1f}kHz, SWR={cache['swr']:.2f}, {'CL' if cache['sw'] else 'LC'}, L={ind}, C={cap}")
                                    last_learn_freq = freq
                        except Exception as e:
                            logger.error(f"学习天调参数失败: {e}")
                
            elif cmd == SCMD_RELAY_STATUS and len(data) >= 7:
                # 通讯日志
                comm_stats['relay_received'] += 1
                
                # 继电器状态
                # 实际数据格式（根据实验结果修正）:
                # data[3] = SW (网络类型 0=LC, 1=CL)
                # data[4] = IND (电感值，如 47 = 4.7uH)
                # data[5] = CAP (电容值，如 79 = 790pF)
                # data[6] = 其他值（如 213，可能是SWR或其他）
                # 注意：实际观测发现字段位置与文档不符
                cache["sw"] = data[3]      # 网络类型在 data[3]
                cache["ind"] = data[4]     # 电感值在 data[4] (如 47 = 4.7uH)
                cache["cap"] = data[5]     # 电容值在 data[5] (如 79 = 790pF)
                
                # 计算实际值（如果有足够数据）
                if len(data) >= 11:
                    L = struct.unpack('<H', data[7:9])[0]
                    C = struct.unpack('<H', data[9:11])[0]
                    cache["ind_uh"] = L / 100.0
                    cache["cap_pf"] = C
                
                # 通讯日志 - 继电器状态
                relay_type = 'CL' if cache['sw'] else 'LC'
                log_comm('RX', 'RELAY', data[:7].hex(), f'SW={relay_type}, L={cache["ind"]}, C={cache["cap"]}')
                
                # 只在继电器状态变化时记录日志
                current_relay = (cache["sw"], cache["ind"], cache["cap"])
                if current_relay != last_log_relay:
                    logger.info(f"🎛️ 继电器: SW={'CL' if cache['sw'] else 'LC'}, L={cache['ind']}, C={cache['cap']}")
                    last_log_relay = current_relay
    
    def close(self):
        """关闭连接"""
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
    
    def set_relay(self, sw: int, ind: int, cap: int):
        """
        设置继电器参数 - V4.5.18: 添加通讯日志
        
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
                
                # 通讯日志
                comm_stats['relay_sent'] += 1
                comm_stats['bytes_sent'] += len(cmd)
                relay_type = 'CL' if sw else 'LC'
                log_comm('TX', 'RELAY', cmd.hex(), f'设置 SW={relay_type}, L={ind}, C={cap}')
                
                logger.info(f"发送继电器命令: SW={sw}, IND={ind}, CAP={cap}")
            except Exception as e:
                logger.error(f"发送继电器命令失败: {e}")
    
    def start_tune(self, mode: int = 2):
        """
        启动自动调谐 - V4.5.18: 添加通讯日志
        
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
    global clients, cache, client_count, is_tx
    
    clients.append(conn)
    client_count = len(clients)
    logger.info(f"新客户端连接，当前 {client_count} 个")
    
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
                        # 设置当前频率并自动调谐（如果有匹配参数）
                        freq = msg.get("freq", 0)
                        with cache_lock:
                            cache["freq"] = freq
                        
                        # 查找并应用天调参数
                        tune_result = None
                        if freq > 0:
                            tuner = get_storage()
                            params = tuner.get_tune_params(freq)
                            if params:
                                sw, ind, cap = params
                                # 统一参数顺序: (sw, ind, cap)
                                set_relay_with_throttle(atr1000, sw, ind, cap)
                                tune_result = {
                                    "sw": sw,
                                    "ind": ind,
                                    "cap": cap,
                                    "sw_name": "LC" if sw else "CL"
                                }
                                logger.info(f"🎯 自动调谐: {freq/1000:.1f}kHz -> {'CL' if sw else 'LC'}, L={ind}, C={cap}")
                        
                        response = json.dumps({
                            "type": "ack",
                            "action": "set_freq",
                            "freq": freq,
                            "auto_tuned": tune_result is not None,
                            "tune_params": tune_result
                        }) + "\n"
                        conn.send(response.encode())
                    
                    elif action == "quick_tune":
                        # V4.5.15: 快速调谐到指定频率
                        freq = msg.get("freq", 0)
                        if freq > 0:
                            tuner = get_storage()
                            params = tuner.get_tune_params(freq)
                            if params:
                                sw, ind, cap = params
                                # 统一参数顺序: (sw, ind, cap)
                                set_relay_with_throttle(atr1000, sw, ind, cap)
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
                    
                    elif action == "get_best_in_band":
                        # 获取波段内 SWR 最低的记录
                        band_start = msg.get("band_start", 0)
                        band_end = msg.get("band_end", 0)
                        
                        tuner = get_storage()
                        records = tuner.get_all()
                        
                        best_record = None
                        best_swr = 99.0
                        
                        for record in records:
                            freq = record.get("freq", 0)
                            swr = record.get("swr_avg") or record.get("swr", 99.0)
                            
                            if band_start <= freq <= band_end:
                                if swr < best_swr:
                                    best_swr = swr
                                    best_record = record
                        
                        if best_record:
                            response = json.dumps({
                                "type": "best_in_band",
                                "found": True,
                                "freq": best_record.get("freq"),
                                "sw": best_record.get("sw", 0),
                                "ind": best_record.get("ind", 64),
                                "cap": best_record.get("cap", 64),
                                "swr": best_swr
                            }) + "\n"
                        else:
                            response = json.dumps({
                                "type": "best_in_band",
                                "found": False
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
                        is_tx = True
                        comm_stats['tx_count'] += 1
                        comm_stats['tx_start_time'] = time.time()
                        log_comm('TX', 'STATUS', '', 'TX模式开始')
                        logger.info("客户端请求启动数据流 (TX开始)")
                    
                    elif action == "stop":
                        is_tx = False
                        if comm_stats['tx_start_time'] > 0:
                            tx_duration = time.time() - comm_stats['tx_start_time']
                            comm_stats['tx_total_time'] += tx_duration
                            log_comm('RX', 'STATUS', '', f'TX模式结束 (持续{tx_duration:.1f}秒)')
                        logger.info("客户端请求停止数据流 (TX结束)")
                    
                    elif action == "set_relay":
                        # 设置继电器参数
                        sw = msg.get("sw", 0)
                        ind = msg.get("ind", 0)
                        cap = msg.get("cap", 0)
                        # 统一参数顺序: (sw, ind, cap)
                        set_relay_with_throttle(atr1000, sw, ind, cap)
                        logger.info(f"设置继电器: SW={sw}, IND={ind}, CAP={cap}")
                    
                    elif action == "tune":
                        # 启动自动调谐
                        mode = msg.get("mode", 2)  # 默认完整调谐
                        atr1000.start_tune(mode)
                        logger.info(f"启动自动调谐: mode={mode}")
                    
                    elif action == "learn":
                        # 手动学习（保存调谐结果）
                        freq = msg.get("freq", 0)
                        sw = msg.get("sw", 0)
                        ind = msg.get("ind", 0)
                        cap = msg.get("cap", 0)
                        swr = msg.get("swr", 99.0)
                        if freq > 0:
                            tuner = get_storage()
                            tuner.learn(freq=freq, sw=sw, ind=ind, cap=cap, swr=swr)
                            logger.info(f"📝 手动学习: {freq/1000:.1f}kHz SWR={swr:.2f}")
                        
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
        client_count = len(clients)
        conn.close()
        logger.info(f"客户端断开，剩余 {client_count} 个")


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
    global UNIX_SOCKET_PATH
    
    parser = argparse.ArgumentParser(description='ATR-1000 天调代理 - V4.5.18 通讯日志版')
    parser.add_argument('--device', default='192.168.1.63', help='ATR-1000 设备 IP')
    parser.add_argument('--port', type=int, default=60001, help='ATR-1000 WebSocket 端口')
    parser.add_argument('--interval', type=float, default=1.0, help='数据请求间隔（秒）')
    parser.add_argument('--unix-socket', default='/tmp/atr1000_proxy.sock', help='Unix Socket 路径')
    parser.add_argument('--instance', '-i', default=None, help='实例名称 (如 radio1)')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    args = parser.parse_args()
    
    # 设置 Unix Socket 路径
    UNIX_SOCKET_PATH = args.unix_socket
    
    # 初始化通讯日志 - V4.5.18
    setup_comm_logger(args.instance)
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 50)
    logger.info("ATR-1000 天调代理程序启动 V4.5.18")
    logger.info(f"设备地址: {args.device}:{args.port}")
    logger.info(f"Unix Socket: {UNIX_SOCKET_PATH}")
    logger.info(f"通讯日志: {COMM_LOG_FILE}")
    logger.info(f"轮询间隔: 空闲{POLL_INTERVAL_IDLE}s / 活跃{POLL_INTERVAL_ACTIVE}s / TX{POLL_INTERVAL_TX}s")
    logger.info("=" * 50)
    
    # 通讯日志记录启动
    if comm_logger:
        comm_logger.info(f"CONFIG | 设备: {args.device}:{args.port}")
        comm_logger.info(f"CONFIG | Unix Socket: {UNIX_SOCKET_PATH}")
        comm_logger.info(f"CONFIG | 轮询间隔: 空闲{POLL_INTERVAL_IDLE}s / 活跃{POLL_INTERVAL_ACTIVE}s / TX{POLL_INTERVAL_TX}s")
    
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
        
        # 输出通讯统计摘要 - V4.5.18
        log_stats_summary()
        
        logger.info("ATR-1000 代理程序已停止")


if __name__ == '__main__':
    main()

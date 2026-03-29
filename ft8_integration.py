#!/usr/bin/env python3
"""
FT8 Integration Module for MRRC
深度整合 ULTRON Python 后端与 Web 前端

架构:
1. UDP 监听 (2237): 接收 JTDX/WSJT-X/MSHV 数据
2. WebSocket 桥接: 通过 /WSFT8 端点与前端通信
3. 双向通信:
   - 后端 → 前端: 解码消息、状态更新、QSO状态
   - 前端 → 后端: 发送CQ、停止CQ、配置参数
4. 集成到 MRRC: 使用现有 Tornado WebSocket 框架

Created by: 心流 CLI
Based on: ULTRON by LU9DCE / Eduardo Castillo
"""

import asyncio
import json
import logging
import os
import re
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import numpy as np

# 尝试导入 Tornado
try:
    import tornado.web
    import tornado.websocket
    import tornado.ioloop
    TORNADO_AVAILABLE = True
except ImportError:
    TORNADO_AVAILABLE = False
    logging.warning("Tornado not available, WebSocket functionality disabled")

# 配置
UDP_PORT = 2237
UDP_FORWARD_PORT = 2277
UDP_LISTEN_IP = "0.0.0.0"
UDP_FORWARD_IP = "127.0.0.1"
WSJT_X_MAX_LENGTH = 512
SIGNAL_THRESHOLD = -20  # dB

# ANSI 颜色
class Colors:
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    CYAN = '\033[36m'
    BRIGHT_GREEN = '\033[92m'
    RESET = '\033[0m'


@dataclass
class QSOState:
    """QSO 状态管理"""
    sendcq: bool = False
    current_call: str = ""
    tempo: int = 0
    tempu: int = 0
    rx_count: int = 0
    tx_count: int = 0
    mega: int = 0
    current_freq: int = 0
    current_mode: str = ""
    excluded_calls: Set[str] = field(default_factory=set)
    worked_calls: Set[str] = field(default_factory=set)


@dataclass
class DecodeMessage:
    """解码消息结构"""
    timestamp: str
    snr: int
    delta_f: int
    mode: str
    message: str
    status: str = ""
    dxcc_id: str = ""
    dxcc_name: str = ""
    dxcc_flag: str = ""
    priority: int = 0


class DXCCDatabase:
    """DXCC 数据库管理"""
    
    def __init__(self, db_file: str = None):
        if db_file is None:
            # 尝试多个可能的路径
            possible_paths = [
                "ft8/base.json",
                "base.json",
                "/Users/cheenle/UHRR/MRRC/ft8/base.json",
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    db_file = path
                    break
        
        self.db_file = db_file
        self.database = self.load_database()
    
    def load_database(self) -> List[Dict]:
        """加载 DXCC 数据库"""
        try:
            if self.db_file and os.path.exists(self.db_file):
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.warning(f"无法加载 DXCC 数据库: {e}")
        return []
    
    def locate_call(self, call: str) -> Dict[str, str]:
        """根据呼号查找 DXCC 信息"""
        call = call.upper()
        
        # 从长到短尝试匹配
        for i in range(len(call), 0, -1):
            partial_call = call[:i]
            for entry in self.database:
                pattern = r'\b' + re.escape(partial_call) + r'\b'
                if re.search(pattern, entry.get('licencia', ''), re.IGNORECASE):
                    return {
                        'id': entry.get('id', 'unknown'),
                        'flag': entry.get('flag', ''),
                        'name': entry.get('name', 'Unknown')
                    }
        
        return {'id': 'unknown', 'flag': '', 'name': 'Unknown'}


class ADIFProcessor:
    """ADIF 日志处理器"""
    
    @staticmethod
    def parse_adif(data: str) -> List[Dict[str, str]]:
        """解析 ADIF 格式数据"""
        qsos = []
        pattern = r'<([A-Z0-9_]+):(\d+)(?::[A-Z])?>([^<]*)'
        matches = re.findall(pattern, data, re.IGNORECASE)
        
        current_qso = {}
        for field, length, content in matches:
            field = field.lower()
            content = content.strip()
            if content:
                current_qso[field] = content
            
            if field == 'eor':
                if current_qso:
                    qsos.append(current_qso.copy())
                current_qso = {}
        
        if current_qso:
            qsos.append(current_qso)
            
        return qsos
    
    @staticmethod
    def generate_adif(qso: Dict[str, str]) -> str:
        """生成单条 ADIF 记录"""
        adif_entry = ""
        for field, content in qso.items():
            if field == 'eor':
                continue
            content = str(content).strip()
            field_length = len(content)
            adif_entry += f"<{field.upper()}:{field_length}>{content} "
        adif_entry += "<EOR>"
        return adif_entry


class WSJTXProtocol:
    """WSJT-X 协议解析器"""
    
    # 数据包类型
    PACKET_TYPE_STATUS = 1
    PACKET_TYPE_DECODE = 2
    PACKET_TYPE_CLEAR = 3
    PACKET_TYPE_REPLY = 4
    PACKET_TYPE_QSO_LOGGED = 5
    PACKET_TYPE_CLOSE = 6
    PACKET_TYPE_REPLAY = 7
    PACKET_TYPE_HALT_TX = 8
    PACKET_TYPE_FREE_TEXT = 9
    PACKET_TYPE_WSPR_DECODE = 10
    PACKET_TYPE_LOCATION = 11
    PACKET_TYPE_LOGGED_ADIF = 12
    PACKET_TYPE_HIGHLIGHT_CALLSIGN = 13
    PACKET_TYPE_SWITCH_CONFIGURATION = 14
    PACKET_TYPE_CONFIGURE = 15
    
    # Magic numbers
    VALID_MAGICS = [0xadbccb00, 0xadbccbda, 0xdacbbcad]
    
    def parse_packet(self, data: bytes) -> Optional[Dict[str, Any]]:
        """解析 WSJT-X 数据包"""
        if len(data) < 12:
            return None
        
        try:
            # 解析头部
            magic = int.from_bytes(data[0:4], byteorder='big')
            
            if magic not in self.VALID_MAGICS:
                return None
            
            version = int.from_bytes(data[4:8], byteorder='big')
            packet_type = int.from_bytes(data[8:12], byteorder='big')
            
            # 根据类型解析
            if packet_type == self.PACKET_TYPE_STATUS:
                return self._parse_status(data[12:])
            elif packet_type == self.PACKET_TYPE_DECODE:
                return self._parse_decode(data[12:])
            elif packet_type == self.PACKET_TYPE_QSO_LOGGED:
                return self._parse_qso_logged(data[12:])
            
            return None
            
        except Exception as e:
            logging.error(f"解析数据包错误: {e}")
            return None
    
    def _parse_status(self, data: bytes) -> Dict[str, Any]:
        """解析状态数据包"""
        try:
            offset = 0
            
            # ID 长度和字符串
            id_len = int.from_bytes(data[offset:offset+4], byteorder='big')
            offset += 4
            software_id = data[offset:offset+id_len].decode('utf-8', errors='replace')
            offset += id_len
            
            # 频率
            frequency = int.from_bytes(data[offset:offset+8], byteorder='big')
            offset += 8
            
            # 模式长度和字符串
            mode_len = int.from_bytes(data[offset:offset+4], byteorder='big')
            offset += 4
            mode = data[offset:offset+mode_len].decode('utf-8', errors='replace')
            offset += mode_len
            
            # 跳过后续字段（简化处理）
            
            return {
                'type': 'status',
                'software': software_id,
                'frequency': frequency,
                'mode': mode
            }
            
        except Exception as e:
            logging.error(f"解析状态包错误: {e}")
            return {'type': 'status'}
    
    def _parse_decode(self, data: bytes) -> Dict[str, Any]:
        """解析解码数据包"""
        try:
            offset = 0
            
            # ID 长度和字符串
            id_len = int.from_bytes(data[offset:offset+4], byteorder='big')
            offset += 4
            software_id = data[offset:offset+id_len].decode('utf-8', errors='replace')
            offset += id_len
            
            # 新解码标志
            new_decode = bool(data[offset])
            offset += 1
            
            # 时间戳 (毫秒)
            time_ms = int.from_bytes(data[offset:offset+4], byteorder='big')
            offset += 4
            
            # SNR
            snr = int.from_bytes(data[offset:offset+4], byteorder='big', signed=True)
            offset += 4
            
            # Delta F
            delta_f = int.from_bytes(data[offset:offset+4], byteorder='big', signed=True)
            offset += 4
            
            # 模式长度和字符串
            mode_len = int.from_bytes(data[offset:offset+4], byteorder='big')
            offset += 4
            mode = data[offset:offset+mode_len].decode('utf-8', errors='replace')
            offset += mode_len
            
            # 消息长度和字符串
            msg_len = int.from_bytes(data[offset:offset+4], byteorder='big')
            offset += 4
            message = data[offset:offset+msg_len].decode('utf-8', errors='replace').strip()
            
            return {
                'type': 'decode',
                'new_decode': new_decode,
                'time_ms': time_ms,
                'snr': snr,
                'delta_f': delta_f,
                'mode': mode,
                'message': message
            }
            
        except Exception as e:
            logging.error(f"解析解码包错误: {e}")
            return {'type': 'decode'}
    
    def _parse_qso_logged(self, data: bytes) -> Dict[str, Any]:
        """解析 QSO 记录数据包"""
        try:
            offset = 0
            
            # ID 长度和字符串
            id_len = int.from_bytes(data[offset:offset+4], byteorder='big')
            offset += 4
            offset += id_len  # 跳过 ID
            
            # 时间戳
            time_off = int.from_bytes(data[offset:offset+8], byteorder='big')
            offset += 8
            
            # 呼号长度和字符串
            call_len = int.from_bytes(data[offset:offset+4], byteorder='big')
            offset += 4
            dx_call = data[offset:offset+call_len].decode('utf-8', errors='replace')
            offset += call_len
            
            # 网格长度和字符串
            grid_len = int.from_bytes(data[offset:offset+4], byteorder='big')
            offset += 4
            dx_grid = data[offset:offset+grid_len].decode('utf-8', errors='replace')
            
            return {
                'type': 'qso_logged',
                'dx_call': dx_call,
                'dx_grid': dx_grid,
                'time_off': time_off
            }
            
        except Exception as e:
            logging.error(f"解析 QSO 记录包错误: {e}")
            return {'type': 'qso_logged'}
    
    def create_reply_packet(self, callsign: str, snr: int, mode: str) -> bytes:
        """创建回复数据包"""
        # 简化实现 - 实际需要构造完整的 WSJT-X 回复包
        magic = 0xadbccb00.to_bytes(4, byteorder='big')
        version = (2).to_bytes(4, byteorder='big')
        packet_type = self.PACKET_TYPE_REPLY.to_bytes(4, byteorder='big')
        
        # 这里应该构造完整的回复包
        return magic + version + packet_type


class FT8Integration:
    """FT8 集成主类 - 桥接 UDP 和 WebSocket"""
    
    def __init__(self):
        self.state = QSOState()
        self.protocol = WSJTXProtocol()
        self.dxcc_db = DXCCDatabase()
        self.adif_processor = ADIFProcessor()
        self.websocket_clients: Set[Any] = set()
        
        # 解码消息队列
        self.decode_queue: deque = deque(maxlen=100)
        self.qso_log: List[Dict] = []
        
        # 日志文件
        self.log_file = Path("ft8/wsjtx_log.adi")
        self._ensure_log_file()
        
        # 加载已通联呼号
        self.load_worked_calls()
        
        # 运行状态
        self.is_running = False
        self.udp_thread: Optional[threading.Thread] = None
        self.udp_socket: Optional[socket.socket] = None
        
        logging.info(f"{Colors.GREEN}FT8 Integration initialized{Colors.RESET}")
    
    def _ensure_log_file(self):
        """确保日志文件存在"""
        if not self.log_file.exists():
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self.log_file.touch()
    
    def load_worked_calls(self):
        """加载已通联的呼号"""
        try:
            content = self.log_file.read_text(encoding='utf-8')
            qsos = self.adif_processor.parse_adif(content)
            for qso in qsos:
                if 'call' in qso:
                    self.state.worked_calls.add(qso['call'].upper())
            logging.info(f"Loaded {len(self.state.worked_calls)} worked calls")
        except Exception as e:
            logging.warning(f"Error loading log: {e}")
    
    def add_websocket_client(self, client):
        """添加 WebSocket 客户端"""
        self.websocket_clients.add(client)
        logging.info(f"WebSocket client added, total: {len(self.websocket_clients)}")
    
    def remove_websocket_client(self, client):
        """移除 WebSocket 客户端"""
        self.websocket_clients.discard(client)
        logging.info(f"WebSocket client removed, total: {len(self.websocket_clients)}")
    
    def broadcast_to_web(self, message: Dict):
        """广播消息到所有 WebSocket 客户端"""
        if not self.websocket_clients:
            return
        
        json_message = json.dumps(message)
        
        # 使用 IOLoop 在主线程中执行 WebSocket 写操作
        # 避免 "There is no current event loop in thread" 错误
        try:
            loop = tornado.ioloop.IOLoop.current()
            if loop is None:
                # 如果没有当前 loop，尝试获取实例
                loop = tornado.ioloop.IOLoop.instance()
            
            loop.add_callback(self._do_broadcast, json_message)
        except Exception as e:
            logging.error(f"Error scheduling broadcast: {e}")
    
    def _do_broadcast(self, json_message: str):
        """在主线程中执行实际的广播"""
        disconnected = set()
        
        for client in list(self.websocket_clients):
            try:
                if hasattr(client, 'write_message'):
                    # Tornado WebSocket
                    client.write_message(json_message)
                elif hasattr(client, 'send'):
                    # 其他 WebSocket 实现
                    client.send(json_message)
            except Exception as e:
                logging.debug(f"Error sending to client: {e}")
                disconnected.add(client)
        
        # 清理断开的客户端
        for client in disconnected:
            self.websocket_clients.discard(client)
    
    def process_decode(self, decode_data: Dict[str, Any]):
        """处理解码消息"""
        message = decode_data.get('message', '')
        snr = decode_data.get('snr', -30)
        mode = decode_data.get('mode', 'FT8')
        delta_f = decode_data.get('delta_f', 0)
        
        # 解析消息
        parts = message.split()
        if len(parts) < 2:
            return
        
        call = parts[1] if len(parts) > 1 else ""
        
        # 查找 DXCC 信息
        dxcc_info = self.dxcc_db.locate_call(call)
        
        # 确定状态和优先级
        status = "   "
        priority = 0
        
        if call in self.state.excluded_calls:
            status = "XX"
            priority = 0
        elif snr <= SIGNAL_THRESHOLD:
            status = "Lo"
            priority = 1
        elif call in self.state.worked_calls:
            status = "--"
            priority = 2
        elif parts[0] == "CQ" or (len(parts) > 2 and parts[2] in ["73", "RR73", "RRR"]):
            if self.state.sendcq:
                status = "->"
                priority = 5
            else:
                status = ">>"
                priority = 10  # 高优先级
        
        # 创建解码消息对象
        decode_msg = DecodeMessage(
            timestamp=datetime.now(timezone.utc).strftime("%H%M%S"),
            snr=snr,
            delta_f=delta_f,
            mode=mode,
            message=message,
            status=status,
            dxcc_id=dxcc_info['id'],
            dxcc_name=dxcc_info['name'],
            dxcc_flag=dxcc_info['flag'],
            priority=priority
        )
        
        # 添加到队列
        self.decode_queue.append(decode_msg)
        
        # 广播到 Web
        self.broadcast_to_web({
            'type': 'decode',
            'data': {
                'timestamp': decode_msg.timestamp,
                'snr': decode_msg.snr,
                'delta_f': decode_msg.delta_f,
                'mode': decode_msg.mode,
                'message': decode_msg.message,
                'status': decode_msg.status,
                'dxcc_id': decode_msg.dxcc_id,
                'dxcc_name': decode_msg.dxcc_name,
                'dxcc_flag': decode_msg.dxcc_flag,
                'priority': decode_msg.priority
            }
        })
        
        # 处理响应逻辑
        self._handle_response_logic(parts, status, call, dxcc_info)
    
    def _handle_response_logic(self, parts: List[str], status: str, call: str, dxcc_info: Dict):
        """处理响应逻辑"""
        if status == ">>" and not self.state.sendcq:
            self.state.current_call = call
            self.state.sendcq = True
            self.state.tempo = int(time.time())
            
            logging.info(f"{Colors.BRIGHT_GREEN}Target: {call} ({dxcc_info['name']}){Colors.RESET}")
            
            # 广播状态变化
            self.broadcast_to_web({
                'type': 'status_change',
                'data': {
                    'sendcq': True,
                    'current_call': call,
                    'message': f"Targeting {call}"
                }
            })
    
    def process_status(self, status_data: Dict[str, Any]):
        """处理状态数据包"""
        software = status_data.get('software', 'Unknown')
        frequency = status_data.get('frequency', 0)
        mode = status_data.get('mode', 'Unknown')
        
        self.state.current_freq = frequency
        self.state.current_mode = mode
        
        # 广播到 Web
        self.broadcast_to_web({
            'type': 'status',
            'data': {
                'software': software,
                'frequency': frequency,
                'mode': mode,
                'band': self._freq_to_band(frequency)
            }
        })
    
    def _freq_to_band(self, freq: int) -> str:
        """频率转换为波段"""
        freq_mhz = freq / 1000000
        bands = [
            (1.8, '160m'), (3.5, '80m'), (5.3, '60m'), (7.0, '40m'),
            (10.1, '30m'), (14.0, '20m'), (18.1, '17m'), (21.0, '15m'),
            (24.9, '12m'), (28.0, '10m'), (50.0, '6m')
        ]
        for f, band in bands:
            if abs(freq_mhz - f) < 0.5:
                return band
        return f"{freq_mhz:.1f}MHz"
    
    def handle_web_command(self, command: str, params: Dict = None):
        """处理来自 Web 前端的命令"""
        params = params or {}
        
        if command == 'send_cq':
            self._send_cq_command()
        elif command == 'stop_cq':
            self._stop_cq_command()
        elif command == 'reply':
            callsign = params.get('callsign', '')
            message = params.get('message', '')
            self._send_reply(callsign, message)
        elif command == 'exclude':
            call = params.get('callsign', '')
            self.state.excluded_calls.add(call.upper())
        elif command == 'get_decodes':
            return self._get_decode_history()
        elif command == 'get_status':
            return self._get_status()
        
        return {'status': 'ok'}
    
    def _send_cq_command(self):
        """发送 CQ 命令"""
        self.state.sendcq = True
        self.broadcast_to_web({
            'type': 'command_ack',
            'data': {'command': 'send_cq', 'status': 'sent'}
        })
        logging.info(f"{Colors.CYAN}CQ command sent{Colors.RESET}")
    
    def _stop_cq_command(self):
        """停止 CQ"""
        self.state.sendcq = False
        self.state.current_call = ""
        self.broadcast_to_web({
            'type': 'command_ack',
            'data': {'command': 'stop_cq', 'status': 'stopped'}
        })
        logging.info(f"{Colors.YELLOW}CQ stopped{Colors.RESET}")
    
    def _send_reply(self, callsign: str, message: str):
        """发送回复"""
        # 这里需要实现实际的 UDP 发送逻辑
        logging.info(f"{Colors.CYAN}Reply to {callsign}: {message}{Colors.RESET}")
        self.broadcast_to_web({
            'type': 'command_ack',
            'data': {'command': 'reply', 'callsign': callsign, 'message': message}
        })
    
    def _get_decode_history(self) -> List[Dict]:
        """获取解码历史"""
        return [
            {
                'timestamp': msg.timestamp,
                'snr': msg.snr,
                'delta_f': msg.delta_f,
                'mode': msg.mode,
                'message': msg.message,
                'status': msg.status,
                'dxcc_id': msg.dxcc_id,
                'dxcc_name': msg.dxcc_name,
                'dxcc_flag': msg.dxcc_flag,
                'priority': msg.priority
            }
            for msg in self.decode_queue
        ]
    
    def _get_status(self) -> Dict:
        """获取当前状态"""
        return {
            'sendcq': self.state.sendcq,
            'current_call': self.state.current_call,
            'current_freq': self.state.current_freq,
            'current_mode': self.state.current_mode,
            'worked_calls_count': len(self.state.worked_calls),
            'excluded_calls_count': len(self.state.excluded_calls)
        }
    
    def _udp_listener_loop(self):
        """UDP 监听循环"""
        try:
            # 创建 UDP socket
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_socket.bind((UDP_LISTEN_IP, UDP_PORT))
            self.udp_socket.settimeout(1.0)
            
            # 转发 socket
            forward_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            logging.info(f"{Colors.GREEN}UDP listener started on port {UDP_PORT}{Colors.RESET}")
            
            while self.is_running:
                try:
                    data, addr = self.udp_socket.recvfrom(WSJT_X_MAX_LENGTH)
                    
                    # 转发数据
                    try:
                        forward_sock.sendto(data, (UDP_FORWARD_IP, UDP_FORWARD_PORT))
                    except:
                        pass
                    
                    # 解析数据包
                    packet = self.protocol.parse_packet(data)
                    if packet:
                        if packet['type'] == 'decode':
                            self.process_decode(packet)
                        elif packet['type'] == 'status':
                            self.process_status(packet)
                        elif packet['type'] == 'qso_logged':
                            self._handle_qso_logged(packet)
                            
                except socket.timeout:
                    continue
                except Exception as e:
                    logging.error(f"UDP listener error: {e}")
                    
        except Exception as e:
            logging.error(f"Failed to start UDP listener: {e}")
    
    def _handle_qso_logged(self, packet: Dict):
        """处理 QSO 记录"""
        dx_call = packet.get('dx_call', '')
        dx_grid = packet.get('dx_grid', '')
        
        if dx_call:
            self.state.worked_calls.add(dx_call.upper())
            
            # 写入 ADIF 日志
            qso = {
                'call': dx_call,
                'gridsquare': dx_grid,
                'mode': self.state.current_mode,
                'freq': str(self.state.current_freq),
                'qso_date': datetime.now(timezone.utc).strftime('%Y%m%d'),
                'time_on': datetime.now(timezone.utc).strftime('%H%M%S'),
                'eor': ''
            }
            
            adif_line = self.adif_processor.generate_adif(qso)
            
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(adif_line + '\n')
            except Exception as e:
                logging.error(f"Error writing log: {e}")
            
            # 广播到 Web
            self.broadcast_to_web({
                'type': 'qso_logged',
                'data': {
                    'dx_call': dx_call,
                    'dx_grid': dx_grid,
                    'adif': adif_line
                }
            })
    
    def start(self):
        """启动集成服务"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # 启动 UDP 监听线程
        self.udp_thread = threading.Thread(target=self._udp_listener_loop)
        self.udp_thread.daemon = True
        self.udp_thread.start()
        
        logging.info(f"{Colors.GREEN}FT8 Integration service started{Colors.RESET}")
    
    def stop(self):
        """停止集成服务"""
        self.is_running = False
        
        if self.udp_socket:
            self.udp_socket.close()
        
        if self.udp_thread:
            self.udp_thread.join(timeout=2.0)
        
        logging.info(f"{Colors.YELLOW}FT8 Integration service stopped{Colors.RESET}")


# 全局实例
_ft8_integration = None

def get_ft8_integration() -> FT8Integration:
    """获取 FT8 集成实例 (单例)"""
    global _ft8_integration
    if _ft8_integration is None:
        _ft8_integration = FT8Integration()
    return _ft8_integration


if __name__ == '__main__':
    # 测试运行
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    integration = get_ft8_integration()
    integration.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        integration.stop()

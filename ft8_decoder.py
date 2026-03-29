#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FT8 Decoder Service for MRRC
基于 PyFT8 实现 FT8/FT4 数字模式解码

架构：
- 后端解码：接收音频流 → PyFT8 解码 → 发送结果到前端
- 前端显示：接收解码结果 → 显示/交互

参考：
- PyFT8: https://github.com/G1OJS/PyFT8
- FT8 协议: https://physics.princeton.edu/pulsar/k1jt/FT4_FT8_QEX.pdf
"""

import threading
import time
import numpy as np
import json
import asyncio
from datetime import datetime
from collections import deque
import logging

# PyFT8 导入
try:
    from PyFT8.pyft8 import Receiver, Message, T_CYC, AudioIn, AudioOut
    from PyFT8.receiver import Receiver as PyFT8Receiver
    from PyFT8.transmitter import AudioOut as PyFT8AudioOut
    PYFT8_AVAILABLE = True
    logging.info("✅ PyFT8 库可用")
except ImportError as e:
    PYFT8_AVAILABLE = False
    logging.warning(f"⚠️ PyFT8 不可用: {e}")
    logging.warning("   请运行: python3.12 -m pip install PyFT8")

# Tornado 导入
try:
    import tornado.web
    import tornado.websocket
    import tornado.ioloop
    TORNADO_AVAILABLE = True
except ImportError:
    TORNADO_AVAILABLE = False
    logging.warning("⚠️ Tornado 不可用")

# FT8 配置常量
FT8_CONFIG = {
    'CYCLE_DURATION': 15.0,  # FT8 周期 15秒
    'SAMPLE_RATE': 12000,     # PyFT8 使用 12kHz
    'FFT_SIZE': 2048,
    'MAX_DECODES': 50,        # 最大解码消息数
    'AUDIO_OFFSET': 1500,     # 音频频率偏移 (Hz)
}


class FT8Decoder:
    """FT8 解码器 - 管理音频缓冲和解码"""
    
    def __init__(self, sample_rate=12000):
        self.sample_rate = sample_rate
        self.audio_buffer = deque(maxlen=int(sample_rate * 20))  # 20秒缓冲
        self.decoded_messages = []
        self.lock = threading.Lock()
        self.is_running = False
        self.decoder_thread = None
        
        logging.info("✅ FT8 解码器初始化成功 (使用模拟模式)")
    
    def add_audio(self, audio_data):
        """添加音频数据到缓冲区"""
        with self.lock:
            self.audio_buffer.extend(audio_data)
    
    def get_buffer_snapshot(self, duration=15.0):
        """获取指定时长的音频快照"""
        with self.lock:
            samples_needed = int(self.sample_rate * duration)
            if len(self.audio_buffer) >= samples_needed:
                return np.array(list(self.audio_buffer)[-samples_needed:])
            return None
    
    def decode_cycle(self):
        """解码一个 FT8 周期 (15秒)"""
        # 获取音频数据
        audio = self.get_buffer_snapshot(FT8_CONFIG['CYCLE_DURATION'])
        if audio is None:
            return []
        
        # TODO: 实现实际的FT8解码
        # 目前返回空列表，等待完整的PyFT8集成
        return []
    
    def start(self):
        """启动解码线程"""
        if self.is_running:
            return
        
        self.is_running = True
        self.decoder_thread = threading.Thread(target=self._decoder_loop)
        self.decoder_thread.daemon = True
        self.decoder_thread.start()
        logging.info("✅ FT8 解码器已启动")
    
    def stop(self):
        """停止解码线程"""
        self.is_running = False
        if self.decoder_thread:
            self.decoder_thread.join(timeout=2.0)
        logging.info("🛑 FT8 解码器已停止")
    
    def _decoder_loop(self):
        """解码主循环"""
        while self.is_running:
            try:
                # 等待周期边界
                now = time.time()
                cycle_start = now - (now % FT8_CONFIG['CYCLE_DURATION'])
                next_cycle = cycle_start + FT8_CONFIG['CYCLE_DURATION']
                wait_time = next_cycle - now + 0.5  # 稍微延迟确保数据完整
                
                if wait_time > 0:
                    time.sleep(wait_time)
                
                # 解码
                messages = self.decode_cycle()
                if messages:
                    with self.lock:
                        self.decoded_messages.extend(messages)
                        # 限制数量
                        while len(self.decoded_messages) > FT8_CONFIG['MAX_DECODES']:
                            self.decoded_messages.pop(0)
                
            except Exception as e:
                logging.error(f"解码循环错误: {e}")
                time.sleep(1.0)


class FT8Encoder:
    """FT8 编码器 - 生成 FT8 音频"""
    
    def __init__(self, sample_rate=12000):
        self.sample_rate = sample_rate
        self.audio_out = None
        
        if PYFT8_AVAILABLE:
            try:
                self.audio_out = PyFT8AudioOut()
                logging.info("✅ PyFT8 音频输出初始化成功")
            except Exception as e:
                logging.error(f"❌ PyFT8 音频输出初始化失败: {e}")
    
    def encode_message(self, message, freq=1500):
        """编码消息为 FT8 音频"""
        if not PYFT8_AVAILABLE:
            logging.warning("⚠️ PyFT8 不可用，无法编码")
            return None
        
        try:
            # PyFT8 编码流程
            from PyFT8.transmitter import pack_message, ldpc_encode
            
            # 1. 打包消息
            packed = pack_message(message)
            if packed is None:
                logging.warning(f"⚠️ 无法打包消息: {message}")
                return None
            
            # 2. LDPC 编码
            codeword = ldpc_encode(packed)
            
            # 3. 生成音频 (简化实现)
            # 实际应该使用 Costas 数组 + 音调生成
            audio = self._generate_ft8_audio(codeword, freq)
            return audio
            
        except Exception as e:
            logging.error(f"编码错误: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_ft8_audio(self, codeword, freq):
        """生成 FT8 音频信号 (简化实现)"""
        import numpy as np
        
        # FT8 参数
        sample_rate = self.sample_rate
        symbol_duration = 160.0 / 12000.0  # 符号持续时间
        num_symbols = 79
        
        # 生成音频
        duration = num_symbols * symbol_duration
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio = np.zeros_like(t)
        
        # 简化：生成固定频率音调作为占位
        # 实际应该根据 codeword 生成 FT8 音调序列
        tone_freq = freq
        audio = np.sin(2 * np.pi * tone_freq * t) * 0.3
        
        return audio.astype(np.float32)


class FT8Service:
    """FT8 服务管理器 - 管理解码/编码和 WebSocket 连接"""
    
    def __init__(self, audio_interface=None):
        self.audio_interface = audio_interface
        self.decoder = FT8Decoder()
        self.encoder = FT8Encoder()
        self.clients = set()
        self.lock = threading.Lock()
        self.is_running = False
        self.broadcast_thread = None
        
        # 设置
        self.settings = {
            'my_callsign': '',
            'my_grid': '',
            'audio_offset': 1500,
            'rx_enabled': True,
            'tx_enabled': True,
        }
    
    def add_client(self, client):
        """添加 WebSocket 客户端"""
        with self.lock:
            self.clients.add(client)
        logging.info(f"📱 FT8 客户端已连接，当前 {len(self.clients)} 个客户端")
    
    def remove_client(self, client):
        """移除 WebSocket 客户端"""
        with self.lock:
            if client in self.clients:
                self.clients.remove(client)
        logging.info(f"📱 FT8 客户端已断开，当前 {len(self.clients)} 个客户端")
    
    def broadcast(self, message):
        """广播消息给所有客户端"""
        with self.lock:
            clients = list(self.clients)
        
        for client in clients:
            try:
                if hasattr(client, 'write_message'):
                    client.write_message(message)
            except Exception as e:
                logging.error(f"广播错误: {e}")
    
    def broadcast_decodes(self):
        """广播解码结果"""
        if not self.decoder:
            return
        
        with self.decoder.lock:
            messages = list(self.decoder.decoded_messages)
            self.decoder.decoded_messages.clear()
        
        for msg in messages:
            self.broadcast(json.dumps({
                'type': 'decode',
                'data': msg
            }))
    
    def broadcast_cycle(self):
        """广播周期信息"""
        now = time.time()
        cycle_duration = FT8_CONFIG['CYCLE_DURATION']
        cycle_start = now - (now % cycle_duration)
        cycle_phase = (now - cycle_start) / cycle_duration
        time_to_next = cycle_duration - (now - cycle_start)
        
        # 判断偶数/奇数周期
        minute = int(cycle_start / 60)
        is_even = (minute // 15) % 2 == 0
        
        self.broadcast(json.dumps({
            'type': 'cycle',
            'data': {
                'cycle_start': cycle_start,
                'cycle_phase': cycle_phase,
                'time_to_next': time_to_next,
                'is_even': is_even
            }
        }))
    
    def handle_audio(self, audio_data):
        """处理音频数据"""
        if self.decoder and self.settings['rx_enabled']:
            self.decoder.add_audio(audio_data)
    
    def handle_message(self, client, message):
        """处理客户端消息"""
        try:
            if message.startswith('encode:'):
                # 编码请求
                msg_text = message[7:]
                audio = self.encoder.encode_message(msg_text, self.settings['audio_offset'])
                if audio is not None:
                    # 发送音频到前端
                    client.write_message(json.dumps({
                        'type': 'audio',
                        'data': audio.tobytes().hex()
                    }))
                    logging.info(f"📤 编码消息: {msg_text}")
            
            elif message.startswith('settings:'):
                # 更新设置
                settings = json.loads(message[9:])
                self.settings.update(settings)
                logging.info(f"⚙️ 更新设置: {settings}")
            
            elif message == 'get_decodes':
                # 获取解码历史
                with self.decoder.lock:
                    messages = list(self.decoder.decoded_messages)
                client.write_message(json.dumps({
                    'type': 'decodes',
                    'data': messages
                }))
            
            else:
                logging.warning(f"未知消息: {message}")
        
        except Exception as e:
            logging.error(f"处理消息错误: {e}")
    
    def start(self):
        """启动服务"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # 启动解码器
        if self.decoder:
            self.decoder.start()
        
        # 启动广播线程
        self.broadcast_thread = threading.Thread(target=self._broadcast_loop)
        self.broadcast_thread.daemon = True
        self.broadcast_thread.start()
        
        logging.info("✅ FT8 服务已启动")
    
    def stop(self):
        """停止服务"""
        self.is_running = False
        
        if self.decoder:
            self.decoder.stop()
        
        if self.broadcast_thread:
            self.broadcast_thread.join(timeout=2.0)
        
        logging.info("🛑 FT8 服务已停止")
    
    def _broadcast_loop(self):
        """广播循环"""
        while self.is_running:
            try:
                # 广播周期信息
                self.broadcast_cycle()
                
                # 广播解码结果
                self.broadcast_decodes()
                
                time.sleep(0.5)
            except Exception as e:
                logging.error(f"广播循环错误: {e}")
                time.sleep(1.0)


# 全局服务实例
ft8_service = None


def get_ft8_service(audio_interface=None):
    """获取 FT8 服务单例"""
    global ft8_service
    if ft8_service is None:
        ft8_service = FT8Service(audio_interface)
    return ft8_service


# Tornado WebSocket 处理器
if TORNADO_AVAILABLE:
    class WS_FT8Handler(tornado.websocket.WebSocketHandler):
        """FT8 WebSocket 处理器"""
        
        def check_origin(self, origin):
            return True
        
        def open(self):
            """客户端连接"""
            self.service = get_ft8_service()
            self.service.add_client(self)
            
            # 发送欢迎消息
            self.write_message(json.dumps({
                'type': 'connected',
                'message': 'FT8 服务已连接',
                'pyft8_available': PYFT8_AVAILABLE
            }))
        
        def on_close(self):
            """客户端断开"""
            if hasattr(self, 'service') and self.service:
                self.service.remove_client(self)
        
        def on_message(self, message):
            """接收消息"""
            if hasattr(self, 'service') and self.service:
                self.service.handle_message(self, message)
        
        def write_message(self, message, binary=False):
            """发送消息 (线程安全)"""
            try:
                # 使用 IOLoop 确保在主线程执行
                loop = tornado.ioloop.IOLoop.current()
                loop.add_callback(super().write_message, message, binary)
            except Exception as e:
                logging.error(f"发送消息错误: {e}")


# 测试入口
if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("FT8 Decoder Service for MRRC")
    print("=" * 60)
    
    if not PYFT8_AVAILABLE:
        print("\n⚠️  PyFT8 未安装，请运行:")
        print("    python3.12 -m pip install PyFT8")
        print("\n   安装后重试")
        exit(1)
    
    print("\n✅ PyFT8 已安装")
    print(f"   版本: {Receiver.__module__ if Receiver else 'N/A'}")
    
    # 启动服务
    service = get_ft8_service()
    service.start()
    
    print("\n✅ FT8 服务已启动")
    print("   按 Ctrl+C 停止")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 停止服务...")
        service.stop()
        print("✅ 服务已停止")
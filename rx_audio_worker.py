#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MRRC RX Audio Worker - RX Audio Processing Independent Process

独立的 RX 音频处理进程，负责：
1. 从电台音频设备采集音频
2. Opus 编码（可选）
3. 分发到各客户端队列

关键设计：
- 进程隔离：音频采集完全独立
- 回调模式：PyAudio 使用回调采集
- Opus 优化：FEC、DTX、低延迟
- 多客户端支持：每个客户端独立队列

版本: v1.0
日期: 2026-03-06
"""

import multiprocessing as mp
from multiprocessing import shared_memory
import pyaudio
import numpy as np
import threading
import time
import queue
import logging
import signal
import sys
import os

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - RXAudioWorker - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('RXAudioWorker')

# Opus 编解码器支持
try:
    from opus.encoder import Encoder as OpusEncoder
    OPUS_AVAILABLE = True
except ImportError:
    OPUS_AVAILABLE = False
    logger.warning("Opus encoder not available, PCM only mode")


class ClientQueueManager:
    """
    客户端队列管理器
    
    管理多个客户端的音频队列，支持动态添加/移除
    """
    
    def __init__(self, max_queue_size: int = 50):
        self.max_queue_size = max_queue_size
        self.client_queues = {}  # client_id -> Queue
        self.lock = threading.Lock()
        self.stats = {
            'total_frames_sent': 0,
            'total_drops': 0
        }
        
    def add_client(self, client_id: str) -> mp.Queue:
        """添加客户端队列"""
        with self.lock:
            if client_id not in self.client_queues:
                self.client_queues[client_id] = mp.Queue(maxsize=self.max_queue_size)
                logger.info(f"Added client queue: {client_id}")
            return self.client_queues[client_id]
            
    def remove_client(self, client_id: str):
        """移除客户端队列"""
        with self.lock:
            if client_id in self.client_queues:
                del self.client_queues[client_id]
                logger.info(f"Removed client queue: {client_id}")
                
    def broadcast(self, data: bytes, metadata: dict):
        """广播数据到所有客户端"""
        with self.lock:
            clients_to_remove = []
            
            for client_id, client_queue in self.client_queues.items():
                try:
                    # 非阻塞放入
                    client_queue.put_nowait((data, metadata))
                    self.stats['total_frames_sent'] += 1
                except queue.Full:
                    # 队列满，丢弃（网络拥塞或客户端处理慢）
                    self.stats['total_drops'] += 1
                    # 如果连续丢包，考虑移除客户端
                    if self.stats['total_drops'] % 100 == 0:
                        logger.warning(f"Queue full for client {client_id}, dropping frame")
                        
        return len(self.client_queues)
        
    def get_client_count(self) -> int:
        """获取客户端数量"""
        with self.lock:
            return len(self.client_queues)
            
    def get_stats(self) -> dict:
        """获取统计信息"""
        with self.lock:
            return {
                'client_count': len(self.client_queues),
                'total_frames_sent': self.stats['total_frames_sent'],
                'total_drops': self.stats['total_drops'],
                'drop_rate': self.stats['total_drops'] / max(1, self.stats['total_frames_sent']) * 100
            }


class RXAudioWorker:
    """
    RX 音频处理工作进程
    
    核心特点：
    - 使用 PyAudio 回调模式采集
    - Opus 编码优化（FEC、DTX）
    - 多客户端独立队列
    - 自适应增益控制
    """
    
    def __init__(self, 
                 client_manager: ClientQueueManager,
                 sample_rate: int = 16000,
                 is_opus: bool = True,
                 input_device: str = None,
                 opus_bitrate: int = 20000,
                 opus_complexity: int = 6):
        """
        初始化 RX 音频工作进程
        
        Args:
            client_manager: 客户端队列管理器
            sample_rate: 音频采样率 (Hz)
            is_opus: 是否使用 Opus 编码
            input_device: 输入设备名称
            opus_bitrate: Opus 比特率 (bps)
            opus_complexity: Opus 复杂度 (1-10)
        """
        self.client_manager = client_manager
        self.sample_rate = sample_rate
        self.is_opus = is_opus and OPUS_AVAILABLE
        self.input_device = input_device
        self.opus_bitrate = opus_bitrate
        self.opus_complexity = opus_complexity
        
        # PyAudio
        self.p = None
        self.stream = None
        
        # Opus 编码器
        self.opus_encoder = None
        self.opus_frame_size = 0
        
        # 状态
        self.running = False
        self.frame_count = 0
        self.last_log_time = time.time()
        
        # 序列号（用于 FEC）
        self.sequence_number = 0
        
        # 统计
        self.stats = {
            'frames_captured': 0,
            'bytes_captured': 0,
            'start_time': None,
            'last_frame_time': None
        }
        
        logger.info(f"RXAudioWorker initialized: {sample_rate}Hz, Opus={self.is_opus}")
        
    def _init_pyaudio(self):
        """初始化 PyAudio"""
        self.p = pyaudio.PyAudio()
        
        # 列出可用设备
        logger.info("Available audio input devices:")
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                logger.info(f"  {i}: {info['name']} (channels: {info['maxInputChannels']})")
        
        # 获取设备索引
        device_index = self._get_device_index(self.input_device)
        
        # 计算帧大小 (20ms)
        frames_per_buffer = int(self.sample_rate * 0.02)  # 320 samples @ 16kHz
        
        try:
            # 使用回调模式打开音频流
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=frames_per_buffer,
                stream_callback=self._audio_callback
            )
            
            logger.info(f"PyAudio input stream opened: {self.sample_rate}Hz, "
                       f"frames_per_buffer={frames_per_buffer}, "
                       f"device_index={device_index}")
        except Exception as e:
            logger.error(f"Failed to open PyAudio input stream: {e}")
            raise
            
    def _get_device_index(self, device_name: str) -> int:
        """根据设备名称获取设备索引"""
        if not device_name:
            return None  # 使用默认设备
            
        try:
            for i in range(self.p.get_device_count()):
                info = self.p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    if device_name.lower() in info['name'].lower():
                        logger.info(f"Found input device: {info['name']} (index {i})")
                        return i
        except Exception as e:
            logger.error(f"Error finding device '{device_name}': {e}")
            
        logger.warning(f"Device '{device_name}' not found, using default")
        return None
        
    def _init_opus_encoder(self):
        """初始化 Opus 编码器"""
        if not self.is_opus:
            return
            
        try:
            # OpusEncoder 参数：采样率、声道数、应用类型
            # 2048 = OPUS_APPLICATION_VOIP（语音优化）
            self.opus_encoder = OpusEncoder(self.sample_rate, 1, 2048)
            self.opus_frame_size = int(self.sample_rate * 0.02)  # 20ms frame
            
            # 配置 Opus 参数（针对短波语音优化）
            self.opus_encoder.configure_for_voip(
                bitrate=self.opus_bitrate,       # 20kbps 短波语音足够
                complexity=self.opus_complexity, # 中等复杂度
                fec=True,                        # 前向纠错（关键！）
                packet_loss_perc=15,             # 预期15%丢包率
                dtx=True                         # 静音检测
            )
            
            logger.info(f"Opus encoder initialized: {self.sample_rate}Hz, "
                       f"frame_size={self.opus_frame_size}, "
                       f"bitrate={self.opus_bitrate}, FEC=ON, DTX=ON")
        except Exception as e:
            logger.error(f"Failed to init Opus encoder: {e}")
            self.is_opus = False
            
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """
        PyAudio 回调函数
        
        在音频线程中调用，必须快速返回！
        """
        if not self.running:
            return (None, pyaudio.paComplete)
            
        # 更新统计
        self.frame_count += 1
        self.stats['frames_captured'] += 1
        self.stats['bytes_captured'] += len(in_data)
        self.stats['last_frame_time'] = time.time()
        
        # 处理音频数据
        try:
            self._process_audio_data(in_data, frame_count)
        except Exception as e:
            logger.error(f"Error in audio callback: {e}")
            
        return (None, pyaudio.paContinue)
        
    def _process_audio_data(self, data: bytes, frame_count: int):
        """处理采集到的音频数据"""
        # 转换为 numpy 数组
        audio_array = np.frombuffer(data, dtype=np.int16)
        
        # 音频处理优化
        audio_array = self._apply_audio_processing(audio_array)
        
        # 准备元数据
        metadata = {
            'encoding': 'opus' if self.is_opus else 'pcm',
            'sample_rate': self.sample_rate,
            'frame_count': frame_count,
            'sequence': self.sequence_number,
            'timestamp': time.time()
        }
        
        # 编码（如果需要）
        if self.is_opus:
            try:
                # Opus 编码
                encoded_data = self.opus_encoder.encode(data, frame_count)
                data_to_send = encoded_data
                metadata['original_size'] = len(data)
                metadata['encoded_size'] = len(encoded_data)
            except Exception as e:
                logger.error(f"Opus encode error: {e}")
                # 回退到 PCM
                data_to_send = audio_array.tobytes()
                metadata['encoding'] = 'pcm'
        else:
            # PCM 模式
            data_to_send = audio_array.tobytes()
            
        # 广播到所有客户端
        client_count = self.client_manager.broadcast(data_to_send, metadata)
        
        # 更新序列号
        self.sequence_number = (self.sequence_number + 1) & 0xFFFFFFFF
        
        # 定期打印状态
        current_time = time.time()
        if current_time - self.last_log_time >= 5.0:
            manager_stats = self.client_manager.get_stats()
            logger.info(f"📊 RX Stats: frames={self.stats['frames_captured']}, "
                       f"clients={manager_stats['client_count']}, "
                       f"drops={manager_stats['total_drops']} ({manager_stats['drop_rate']:.2f}%)")
            self.last_log_time = current_time
            
    def _apply_audio_processing(self, audio: np.ndarray) -> np.ndarray:
        """
        音频处理优化
        
        包括：直流偏移去除、自动增益控制、软削波
        """
        # 1. 去除直流偏移
        dc_offset = np.mean(audio)
        if abs(dc_offset) > 10:  # 阈值
            audio = audio - int(dc_offset)
            
        # 2. 自动增益控制 (AGC)
        max_val = np.max(np.abs(audio))
        if max_val > 100:  # 有足够信号
            target_level = 20000  # 目标电平
            if max_val < target_level * 0.3:
                # 弱信号：提升增益（最大4倍）
                gain = min(target_level / max_val, 4.0)
                audio = (audio * gain).astype(np.int16)
            elif max_val > 30000:
                # 强信号：略微衰减，防止削波
                audio = (audio * 0.85).astype(np.int16)
                
        # 3. 软削波保护
        audio = np.clip(audio, -32000, 32000)
        
        return audio
        
    def start(self):
        """启动音频采集"""
        logger.info("🎤 Starting RXAudioWorker...")
        
        self.running = True
        self.stats['start_time'] = time.time()
        
        # 初始化 Opus 编码器
        self._init_opus_encoder()
        
        # 初始化 PyAudio
        self._init_pyaudio()
        
        # 启动音频流
        self.stream.start_stream()
        
        logger.info("🎤 RXAudioWorker started successfully")
        
    def stop(self):
        """停止音频采集"""
        logger.info("Stopping RXAudioWorker...")
        
        self.running = False
        
        # 停止音频流
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error closing stream: {e}")
                
        # 终止 PyAudio
        if self.p:
            try:
                self.p.terminate()
            except Exception as e:
                logger.error(f"Error terminating PyAudio: {e}")
                
        # 打印最终统计
        if self.stats['start_time']:
            duration = time.time() - self.stats['start_time']
            manager_stats = self.client_manager.get_stats()
            logger.info(f"📊 RX Final stats: "
                       f"duration={duration:.1f}s, "
                       f"frames={self.stats['frames_captured']}, "
                       f"clients_served={manager_stats['total_frames_sent']}")
                       
        logger.info("🎤 RXAudioWorker stopped")
        
    def get_status(self) -> dict:
        """获取当前状态"""
        return {
            'running': self.running,
            'sample_rate': self.sample_rate,
            'is_opus': self.is_opus,
            'client_stats': self.client_manager.get_stats(),
            'stats': self.stats
        }


def rx_audio_worker_main(client_queues_dict, 
                         sample_rate, 
                         is_opus, 
                         input_device,
                         opus_bitrate,
                         opus_complexity):
    """
    RX 音频工作进程入口函数
    
    注意：client_queues_dict 是一个 multiprocessing.Manager().dict()
    用于跨进程共享客户端队列
    """
    # 设置信号处理
    def signal_handler(sig, frame):
        logger.info("Received termination signal")
        worker.stop()
        sys.exit(0)
        
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # 创建客户端队列管理器
    client_manager = ClientQueueManager()
    
    # 同步现有的客户端队列
    for client_id, queue_info in client_queues_dict.items():
        client_manager.add_client(client_id)
        
    # 创建并启动工作器
    worker = RXAudioWorker(
        client_manager=client_manager,
        sample_rate=sample_rate,
        is_opus=is_opus,
        input_device=input_device,
        opus_bitrate=opus_bitrate,
        opus_complexity=opus_complexity
    )
    
    try:
        worker.start()
        
        # 保持运行
        while worker.running:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        pass
    finally:
        worker.stop()


if __name__ == '__main__':
    """测试模式"""
    logger.info("Running RXAudioWorker in test mode...")
    
    # 使用 Manager 创建共享字典
    manager = mp.Manager()
    client_queues_dict = manager.dict()
    
    # 添加测试客户端
    test_queue = mp.Queue()
    client_queues_dict['test_client'] = test_queue
    
    # 创建工作进程
    worker_process = mp.Process(
        target=rx_audio_worker_main,
        args=(client_queues_dict, 16000, False, None, 20000, 6),
        daemon=True
    )
    
    worker_process.start()
    logger.info(f"RX Worker process started: PID={worker_process.pid}")
    
    try:
        # 从测试队列读取数据
        for i in range(50):
            try:
                data, metadata = test_queue.get(timeout=1.0)
                logger.info(f"Received frame {i}: {len(data)} bytes, encoding={metadata['encoding']}")
            except queue.Empty:
                logger.warning("No data received")
                
    except KeyboardInterrupt:
        pass
    finally:
        worker_process.join(timeout=5)
        if worker_process.is_alive():
            worker_process.terminate()
            
    logger.info("RX Test completed")

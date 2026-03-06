#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MRRC Audio Worker - TX Audio Processing Independent Process

独立的 TX 音频处理进程，负责：
1. 从主进程队列接收音频数据
2. Opus 解码（如果需要）
3. 通过 PyAudio 回调模式播放到电台

关键设计：
- 进程隔离：音频处理完全独立，不阻塞主进程
- 回调模式：PyAudio 使用回调而非阻塞写入
- 环形缓冲：平滑处理音频数据流
- 自动恢复：进程崩溃后可自动重启

版本: v1.0
日期: 2026-03-06
"""

import multiprocessing as mp
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
    format='%(asctime)s - AudioWorker - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('AudioWorker')

# Opus 编解码器支持
try:
    from opus.decoder import Decoder as OpusDecoder
    OPUS_AVAILABLE = True
except ImportError:
    OPUS_AVAILABLE = False
    logger.warning("Opus decoder not available, PCM only mode")


class RingBuffer:
    """
    线程安全的环形音频缓冲区
    
    用于平滑音频数据流，处理网络抖动
    """
    
    def __init__(self, size: int, dtype=np.int16):
        self.buffer = np.zeros(size, dtype=dtype)
        self.size = size
        self.write_pos = 0
        self.read_pos = 0
        self.available = 0
        self.lock = threading.Lock()
        self.overflow_count = 0
        self.underrun_count = 0
        
    def write(self, data: np.ndarray) -> int:
        """写入数据到缓冲区，返回实际写入的样本数"""
        with self.lock:
            data_len = len(data)
            space_available = self.size - self.available
            
            if data_len > space_available:
                # 缓冲区即将溢出，丢弃旧数据
                overflow = data_len - space_available
                self.overflow_count += 1
                if self.overflow_count % 10 == 1:
                    logger.warning(f"Buffer overflow, dropping {overflow} samples")
                    
                # 跳过旧数据
                self.read_pos = (self.read_pos + overflow) % self.size
                self.available = self.size
                data_len = space_available
                data = data[-data_len:]
            
            # 写入数据
            for i in range(data_len):
                self.buffer[self.write_pos] = data[i]
                self.write_pos = (self.write_pos + 1) % self.size
            
            self.available += data_len
            return data_len
            
    def read(self, count: int) -> np.ndarray:
        """从缓冲区读取数据"""
        with self.lock:
            if self.available < count:
                # 缓冲区欠载
                self.underrun_count += 1
                if self.underrun_count % 100 == 1:
                    logger.warning(f"Buffer underrun, requested {count}, available {self.available}")
                
                # 返回静音
                return np.zeros(count, dtype=np.int16)
            
            result = np.zeros(count, dtype=np.int16)
            for i in range(count):
                result[i] = self.buffer[self.read_pos]
                self.read_pos = (self.read_pos + 1) % self.size
            
            self.available -= count
            return result
            
    def get_available(self) -> int:
        """获取可用数据量"""
        with self.lock:
            return self.available
            
    def get_stats(self) -> dict:
        """获取缓冲区统计信息"""
        with self.lock:
            return {
                'size': self.size,
                'available': self.available,
                'utilization': self.available / self.size * 100,
                'overflow_count': self.overflow_count,
                'underrun_count': self.underrun_count
            }
            
    def reset(self):
        """重置缓冲区"""
        with self.lock:
            self.write_pos = 0
            self.read_pos = 0
            self.available = 0
            self.overflow_count = 0
            self.underrun_count = 0


class AudioWorker:
    """
    TX 音频处理工作进程
    
    核心特点：
    - 使用 PyAudio 回调模式，零阻塞
    - 环形缓冲区平滑网络抖动
    - 支持 Opus 和 PCM 双模式
    - 完整的状态监控和错误恢复
    """
    
    def __init__(self, 
                 tx_queue: mp.Queue,
                 sample_rate: int = 16000,
                 is_opus: bool = True,
                 output_device: str = None,
                 buffer_ms: int = 100):
        """
        初始化音频工作进程
        
        Args:
            tx_queue: 从主进程接收音频数据的队列
            sample_rate: 音频采样率 (Hz)
            is_opus: 是否使用 Opus 编码
            output_device: 输出设备名称
            buffer_ms: 缓冲区大小 (毫秒)
        """
        self.tx_queue = tx_queue
        self.sample_rate = sample_rate
        self.is_opus = is_opus and OPUS_AVAILABLE
        self.output_device = output_device
        self.buffer_ms = buffer_ms
        
        # 计算缓冲区大小
        self.buffer_samples = int(sample_rate * buffer_ms / 1000)
        
        # 环形缓冲区
        self.ring_buffer = RingBuffer(self.buffer_samples * 2)
        
        # PyAudio
        self.p = None
        self.stream = None
        
        # Opus 解码器
        self.opus_decoder = None
        self.opus_frame_size = 0
        
        # 状态
        self.running = False
        self.frame_count = 0
        self.last_log_time = time.time()
        
        # 统计
        self.stats = {
            'frames_processed': 0,
            'bytes_processed': 0,
            'start_time': None,
            'last_frame_time': None
        }
        
        logger.info(f"AudioWorker initialized: {sample_rate}Hz, Opus={self.is_opus}")
        
    def _init_pyaudio(self):
        """初始化 PyAudio"""
        self.p = pyaudio.PyAudio()
        
        # 获取设备索引
        device_index = self._get_device_index(self.output_device)
        
        # 计算帧大小 (20ms)
        frames_per_buffer = int(self.sample_rate * 0.02)  # 320 samples @ 16kHz
        
        try:
            # 使用回调模式打开音频流
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                output=True,
                output_device_index=device_index,
                frames_per_buffer=frames_per_buffer,
                stream_callback=self._audio_callback
            )
            
            logger.info(f"PyAudio stream opened: {self.sample_rate}Hz, "
                       f"frames_per_buffer={frames_per_buffer}, "
                       f"device_index={device_index}")
        except Exception as e:
            logger.error(f"Failed to open PyAudio stream: {e}")
            raise
            
    def _get_device_index(self, device_name: str) -> int:
        """根据设备名称获取设备索引"""
        if not device_name:
            return None  # 使用默认设备
            
        try:
            for i in range(self.p.get_device_count()):
                info = self.p.get_device_info_by_index(i)
                if info['maxOutputChannels'] > 0:
                    if device_name.lower() in info['name'].lower():
                        logger.info(f"Found output device: {info['name']} (index {i})")
                        return i
        except Exception as e:
            logger.error(f"Error finding device '{device_name}': {e}")
            
        logger.warning(f"Device '{device_name}' not found, using default")
        return None
        
    def _init_opus_decoder(self):
        """初始化 Opus 解码器"""
        if not self.is_opus:
            return
            
        try:
            self.opus_decoder = OpusDecoder(self.sample_rate, 1)
            self.opus_frame_size = int(self.sample_rate * 0.02)  # 20ms frame
            logger.info(f"Opus decoder initialized: {self.sample_rate}Hz, frame_size={self.opus_frame_size}")
        except Exception as e:
            logger.error(f"Failed to init Opus decoder: {e}")
            self.is_opus = False
            
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """
        PyAudio 回调函数
        
        这是在音频线程中调用的，必须快速返回！
        不能做任何阻塞操作。
        """
        # 从环形缓冲区读取数据
        audio_data = self.ring_buffer.read(frame_count)
        
        # 更新统计
        self.frame_count += 1
        
        return (audio_data.tobytes(), pyaudio.paContinue)
        
    def _process_queue(self):
        """处理来自主进程的音频数据队列"""
        while self.running:
            try:
                # 非阻塞获取，超时 5ms
                item = self.tx_queue.get(timeout=0.005)
                
                if item is None:
                    # 关闭信号
                    logger.info("Received shutdown signal")
                    break
                    
                # 解析数据
                if isinstance(item, tuple):
                    audio_data, metadata = item
                else:
                    audio_data = item
                    metadata = {}
                    
                # 处理音频数据
                self._process_audio_data(audio_data, metadata)
                
            except queue.Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                logger.error(f"Error processing queue: {e}")
                
    def _process_audio_data(self, data: bytes, metadata: dict):
        """处理音频数据"""
        try:
            encoding = metadata.get('encoding', 'pcm')
            
            if encoding == 'opus' and self.is_opus:
                # Opus 解码
                pcm_data = self._decode_opus(data)
                if pcm_data is not None:
                    self.ring_buffer.write(pcm_data)
            else:
                # PCM 数据直接写入
                pcm_data = np.frombuffer(data, dtype=np.int16)
                self.ring_buffer.write(pcm_data)
                
            # 更新统计
            self.stats['frames_processed'] += 1
            self.stats['bytes_processed'] += len(data)
            self.stats['last_frame_time'] = time.time()
            
            # 定期打印状态
            current_time = time.time()
            if current_time - self.last_log_time >= 5.0:
                buffer_stats = self.ring_buffer.get_stats()
                logger.info(f"📊 Stats: frames={self.stats['frames_processed']}, "
                           f"buffer_util={buffer_stats['utilization']:.1f}%, "
                           f"underruns={buffer_stats['underrun_count']}")
                self.last_log_time = current_time
                
        except Exception as e:
            logger.error(f"Error processing audio data: {e}")
            
    def _decode_opus(self, data: bytes) -> np.ndarray:
        """解码 Opus 数据"""
        if self.opus_decoder is None:
            return None
            
        try:
            # 解码 Opus 帧
            decoded = self.opus_decoder.decode(data, self.opus_frame_size, False)
            return np.frombuffer(decoded, dtype=np.int16)
        except Exception as e:
            logger.error(f"Opus decode error: {e}")
            return None
            
    def start(self):
        """启动音频处理"""
        logger.info("🔊 Starting AudioWorker...")
        
        self.running = True
        self.stats['start_time'] = time.time()
        
        # 初始化 Opus 解码器
        self._init_opus_decoder()
        
        # 初始化 PyAudio
        self._init_pyaudio()
        
        # 启动音频流
        self.stream.start_stream()
        
        # 启动队列处理线程
        self.queue_thread = threading.Thread(
            target=self._process_queue,
            daemon=True
        )
        self.queue_thread.start()
        
        logger.info("🔊 AudioWorker started successfully")
        
    def stop(self):
        """停止音频处理"""
        logger.info("Stopping AudioWorker...")
        
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
            logger.info(f"📊 Final stats: "
                       f"duration={duration:.1f}s, "
                       f"frames={self.stats['frames_processed']}, "
                       f"bytes={self.stats['bytes_processed']}")
                       
        logger.info("🔊 AudioWorker stopped")
        
    def get_status(self) -> dict:
        """获取当前状态"""
        return {
            'running': self.running,
            'sample_rate': self.sample_rate,
            'is_opus': self.is_opus,
            'buffer_stats': self.ring_buffer.get_stats(),
            'stats': self.stats
        }


def audio_worker_main(tx_queue, sample_rate, is_opus, output_device, buffer_ms):
    """
    音频工作进程入口函数
    
    这是 multiprocessing.Process 的 target 函数
    """
    # 设置信号处理
    def signal_handler(sig, frame):
        logger.info("Received termination signal")
        worker.stop()
        sys.exit(0)
        
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # 创建并启动工作器
    worker = AudioWorker(
        tx_queue=tx_queue,
        sample_rate=sample_rate,
        is_opus=is_opus,
        output_device=output_device,
        buffer_ms=buffer_ms
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
    logger.info("Running AudioWorker in test mode...")
    
    # 创建测试队列
    tx_queue = mp.Queue()
    
    # 创建工作进程
    worker_process = mp.Process(
        target=audio_worker_main,
        args=(tx_queue, 16000, False, None, 100),
        daemon=True
    )
    
    worker_process.start()
    logger.info(f"Worker process started: PID={worker_process.pid}")
    
    try:
        # 模拟发送测试音频
        import struct
        
        for i in range(100):
            # 生成正弦波测试数据
            t = np.linspace(0, 0.02, 320, dtype=np.float32)
            freq = 440  # A4 音符
            sine_wave = np.sin(2 * np.pi * freq * t) * 0.3
            test_data = (sine_wave * 32767).astype(np.int16).tobytes()
            
            tx_queue.put((test_data, {'encoding': 'pcm'}))
            time.sleep(0.02)  # 20ms per frame
            
        # 发送关闭信号
        tx_queue.put(None)
        
    except KeyboardInterrupt:
        pass
    finally:
        worker_process.join(timeout=5)
        if worker_process.is_alive():
            worker_process.terminate()
            
    logger.info("Test completed")

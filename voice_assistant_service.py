#!/usr/bin/env python3
"""
语音助手服务 - 后端语音识别与合成
使用本地Whisper模型进行语音识别，Piper TTS进行语音合成
"""

import asyncio
import json
import logging
import io
import wave
import tempfile
import os
import sys
from typing import Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 检查并导入依赖
def check_dependencies():
    """检查必要的依赖是否安装"""
    missing = []
    
    try:
        import numpy as np
    except ImportError:
        missing.append('numpy')
    
    try:
        import sounddevice as sd
    except ImportError:
        missing.append('sounddevice')
    
    try:
        import soundfile as sf
    except ImportError:
        missing.append('soundfile')
    
    try:
        import tornado
    except ImportError:
        missing.append('tornado')
    
    if missing:
        logger.error(f"缺少依赖包: {', '.join(missing)}")
        logger.error("请运行: pip3 install " + ' '.join(missing))
        sys.exit(1)

check_dependencies()

# 导入依赖
import numpy as np
import sounddevice as sd
import soundfile as sf
import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.ioloop import PeriodicCallback


@dataclass
class ASRResult:
    """语音识别结果"""
    text: str
    confidence: float
    language: str
    is_final: bool
    timestamp: str


@dataclass
class TTSRequest:
    """语音合成请求"""
    text: str
    voice_id: str = "default"
    speed: float = 1.0
    ptt_delay_ms: int = 500


class WhisperASR:
    """
    基于Whisper的本地语音识别
    """
    
    def __init__(self, model_size: str = "base", language: str = "zh"):
        self.model_size = model_size
        self.language = language
        self.model = None
        self.is_loaded = False
        self.whisper_available = False
        
        # 检查Whisper是否可用
        try:
            import whisper
            self.whisper_available = True
        except ImportError:
            logger.warning("Whisper未安装，语音识别功能将不可用")
            logger.warning("如需使用，请运行: pip3 install openai-whisper")
        
    def load_model(self):
        """加载Whisper模型"""
        if not self.whisper_available:
            logger.error("Whisper未安装，无法加载模型")
            return False
            
        try:
            import whisper
            logger.info(f"加载Whisper模型: {self.model_size}")
            self.model = whisper.load_model(self.model_size)
            self.is_loaded = True
            logger.info("Whisper模型加载完成")
            return True
        except Exception as e:
            logger.error(f"加载Whisper模型失败: {e}")
            return False
    
    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> Optional[ASRResult]:
        """
        识别音频
        
        Args:
            audio_data: 音频数据 (numpy array)
            sample_rate: 采样率
            
        Returns:
            ASRResult: 识别结果
        """
        if not self.is_loaded:
            logger.error("Whisper模型未加载")
            return None
        
        try:
            # Whisper需要float32格式
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # 归一化到 [-1, 1]
            if audio_data.max() > 1.0:
                audio_data = audio_data / 32768.0
            
            # 执行识别
            result = self.model.transcribe(
                audio_data,
                language=self.language,
                task="transcribe",
                fp16=False
            )
            
            text = result["text"].strip()
            confidence = result.get("confidence", 0.8)
            
            if text:
                return ASRResult(
                    text=text,
                    confidence=confidence,
                    language=self.language,
                    is_final=True,
                    timestamp=datetime.now().isoformat()
                )
            
            return None
            
        except Exception as e:
            logger.error(f"语音识别失败: {e}")
            return None


class PiperTTS:
    """
    Piper TTS 语音合成
    轻量级、高质量的本地TTS
    """
    
    def __init__(self, model_path: str = None, config_path: str = None):
        self.model_path = model_path
        self.config_path = config_path
        self.is_loaded = False
        self.use_pyttsx3 = False
        self.use_piper = False
        
    def load_model(self):
        """加载Piper模型"""
        # 首先尝试Piper
        try:
            from piper.voice import PiperVoice
            
            if self.model_path and os.path.exists(self.model_path):
                logger.info(f"加载Piper TTS模型: {self.model_path}")
                self.voice = PiperVoice.load(self.model_path, self.config_path)
                self.is_loaded = True
                self.use_piper = True
                logger.info("Piper TTS模型加载完成")
                return True
            else:
                logger.warning("Piper模型路径未指定或不存在")
                
        except ImportError:
            logger.debug("Piper TTS未安装")
        except Exception as e:
            logger.warning(f"加载Piper TTS失败: {e}")
        
        # 尝试使用pyttsx3
        return self._load_pyttsx3()
    
    def _load_pyttsx3(self):
        """使用pyttsx3作为备选"""
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 150)
            self.engine.setProperty('volume', 1.0)
            self.is_loaded = True
            self.use_pyttsx3 = True
            logger.info("pyttsx3 TTS加载完成")
            return True
        except Exception as e:
            logger.error(f"加载pyttsx3失败: {e}")
            return False
    
    def synthesize(self, text: str, output_path: Optional[str] = None, 
                   speed: float = 1.0) -> Optional[str]:
        """
        合成语音
        
        Args:
            text: 要合成的文本
            output_path: 输出文件路径（可选）
            speed: 语速
            
        Returns:
            str: 输出文件路径
        """
        if not self.is_loaded:
            logger.error("TTS模型未加载")
            return None
        
        try:
            if not output_path:
                # 创建临时文件
                fd, output_path = tempfile.mkstemp(suffix='.wav')
                os.close(fd)
            
            if self.use_pyttsx3:
                # 使用pyttsx3
                self.engine.setProperty('rate', int(150 * speed))
                self.engine.save_to_file(text, output_path)
                self.engine.runAndWait()
                
            elif self.use_piper:
                # 使用Piper
                import wave
                
                with wave.open(output_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(22050)
                    
                    # 合成音频流
                    try:
                        for audio_bytes in self.voice.synthesize_stream_raw(text):
                            wav_file.writeframes(audio_bytes)
                    except TypeError:
                        # 某些版本的Piper API不同
                        audio_data = self.voice.synthesize(text)
                        wav_file.writeframes(audio_data)
            
            return output_path
            
        except Exception as e:
            logger.error(f"语音合成失败: {e}")
            return None


class AudioCapture:
    """
    音频采集器 - 从声卡采集音频
    """
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1, 
                 chunk_duration: float = 3.0):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_duration = chunk_duration
        self.chunk_samples = int(sample_rate * chunk_duration)
        self.is_recording = False
        self.audio_buffer = []
        self.callback: Optional[Callable] = None
        self.stream = None
        
    def set_callback(self, callback: Callable):
        """设置音频数据回调"""
        self.callback = callback
    
    def start(self):
        """开始采集"""
        if self.is_recording:
            return
        
        try:
            self.is_recording = True
            self.audio_buffer = []
            
            def audio_callback(indata, frames, time_info, status):
                if status:
                    logger.warning(f"音频状态: {status}")
                
                # 将音频数据添加到缓冲区
                self.audio_buffer.extend(indata[:, 0].tolist())
                
                # 当缓冲区足够大时，触发回调
                if len(self.audio_buffer) >= self.chunk_samples:
                    # 提取数据并清空缓冲区
                    audio_data = np.array(self.audio_buffer[:self.chunk_samples])
                    self.audio_buffer = self.audio_buffer[self.chunk_samples:]
                    
                    if self.callback:
                        self.callback(audio_data)
            
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.float32,
                blocksize=int(self.sample_rate * 0.1),  # 100ms blocks
                callback=audio_callback
            )
            
            self.stream.start()
            logger.info("音频采集已启动")
            
        except Exception as e:
            logger.error(f"启动音频采集失败: {e}")
            self.is_recording = False
    
    def stop(self):
        """停止采集"""
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        logger.info("音频采集已停止")


class FileAudioCapture:
    """
    文件音频采集器 - 从recordings目录读取WAV文件
    """
    
    def __init__(self, recordings_dir: str = "recordings", 
                 sample_rate: int = 16000, chunk_duration: float = 5.0):
        self.recordings_dir = recordings_dir
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.is_recording = False
        self.callback: Optional[Callable] = None
        self.monitor_task = None
        self.processed_files = set()  # 已处理的文件
        
    def set_callback(self, callback: Callable):
        """设置音频数据回调"""
        self.callback = callback
    
    def start(self):
        """开始监视recordings目录"""
        if self.is_recording:
            return
        
        self.is_recording = True
        logger.info(f"开始监视录音目录: {self.recordings_dir}")
        
        # 启动异步监视任务
        import threading
        self.monitor_task = threading.Thread(target=self._monitor_files)
        self.monitor_task.daemon = True
        self.monitor_task.start()
    
    def stop(self):
        """停止监视"""
        self.is_recording = False
        logger.info("停止监视录音目录")
    
    def _monitor_files(self):
        """后台线程监视文件变化"""
        import time
        
        while self.is_recording:
            try:
                if os.path.exists(self.recordings_dir):
                    # 获取目录中所有WAV文件
                    wav_files = [f for f in os.listdir(self.recordings_dir) 
                                if f.endswith('.wav')]
                    
                    for wav_file in wav_files:
                        if wav_file not in self.processed_files:
                            # 新文件，进行处理
                            self._process_file(os.path.join(self.recordings_dir, wav_file))
                            self.processed_files.add(wav_file)
                            
                            # 只保留最近100个文件记录
                            if len(self.processed_files) > 100:
                                self.processed_files.pop()
                
                time.sleep(2)  # 每2秒检查一次
                
            except Exception as e:
                logger.error(f"监视文件出错: {e}")
                time.sleep(5)
    
    def _process_file(self, file_path: str):
        """处理单个WAV文件"""
        try:
            logger.info(f"处理录音文件: {file_path}")
            
            # 读取WAV文件
            with wave.open(file_path, 'rb') as wf:
                # 获取音频参数
                n_channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                orig_sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                
                logger.info(f"WAV文件参数: {n_channels}ch, {sample_width}bytes, "
                          f"{orig_sample_rate}Hz, {n_frames}frames")
                
                # 读取音频数据
                audio_data = wf.readframes(n_frames)
                
                # 转换为numpy数组
                if sample_width == 2:
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                elif sample_width == 4:
                    audio_array = np.frombuffer(audio_data, dtype=np.int32)
                else:
                    audio_array = np.frombuffer(audio_data, dtype=np.uint8)
                
                # 转换为float32并归一化
                audio_array = audio_array.astype(np.float32)
                if audio_array.max() > 1.0:
                    audio_array = audio_array / 32768.0
                
                # 如果是立体声，转换为单声道
                if n_channels == 2:
                    audio_array = audio_array.reshape(-1, 2).mean(axis=1)
                
                # 重采样到16kHz（如果需要）
                if orig_sample_rate != self.sample_rate:
                    logger.info(f"重采样: {orig_sample_rate}Hz -> {self.sample_rate}Hz")
                    audio_array = self._resample(audio_array, orig_sample_rate, self.sample_rate)
                
                # 触发回调
                if self.callback:
                    self.callback(audio_array)
                    logger.info(f"文件处理完成: {os.path.basename(file_path)}")
                
        except Exception as e:
            logger.error(f"处理文件失败 {file_path}: {e}")
    
    def _resample(self, audio: np.ndarray, orig_rate: int, target_rate: int) -> np.ndarray:
        """简单的线性重采样"""
        if orig_rate == target_rate:
            return audio
        
        # 计算重采样比例
        ratio = target_rate / orig_rate
        new_length = int(len(audio) * ratio)
        
        # 使用线性插值
        indices = np.linspace(0, len(audio) - 1, new_length)
        indices_floor = np.floor(indices).astype(np.int32)
        indices_ceil = np.minimum(indices_floor + 1, len(audio) - 1)
        fractions = indices - indices_floor
        
        return audio[indices_floor] * (1 - fractions) + audio[indices_ceil] * fractions
    
    def process_specific_file(self, file_path: str) -> bool:
        """处理指定文件（供手动调用）"""
        if os.path.exists(file_path):
            self._process_file(file_path)
            return True
        return False


class VoiceAssistantWebSocket(tornado.websocket.WebSocketHandler):
    """
    WebSocket处理器 - 与前端通信
    """
    
    clients = set()
    
    def initialize(self, asr: WhisperASR, tts: PiperTTS, audio_capture: AudioCapture,
                   file_capture: FileAudioCapture = None):
        self.asr = asr
        self.tts = tts
        self.audio_capture = audio_capture
        self.file_capture = file_capture
        self.is_listening = False
        
    def open(self):
        """客户端连接"""
        self.clients.add(self)
        logger.info(f"客户端连接，当前连接数: {len(self.clients)}")
        
        # 发送欢迎消息
        self.send_json({
            'type': 'connected',
            'message': '语音助手服务已连接',
            'asr_ready': self.asr.is_loaded,
            'tts_ready': self.tts.is_loaded
        })
    
    def on_close(self):
        """客户端断开"""
        self.clients.discard(self)
        self.is_listening = False
        logger.info(f"客户端断开，当前连接数: {len(self.clients)}")
    
    def on_message(self, message: str):
        """接收消息"""
        try:
            data = json.loads(message)
            action = data.get('action')
            
            if action == 'start_listening':
                self.handle_start_listening()
            elif action == 'stop_listening':
                self.handle_stop_listening()
            elif action == 'tts':
                self.handle_tts(data)
            elif action == 'ping':
                self.send_json({'type': 'pong'})
            else:
                logger.warning(f"未知动作: {action}")
                
        except json.JSONDecodeError:
            logger.error(f"无效的JSON消息: {message}")
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
    
    def handle_start_listening(self):
        """开始监听 - 从recordings目录读取录音文件"""
        if not self.asr.is_loaded:
            self.send_json({
                'type': 'error',
                'message': 'ASR模型未加载'
            })
            return
        
        self.is_listening = True
        
        # 设置音频回调
        def on_audio(audio_data):
            if self.is_listening and self.asr.is_loaded:
                # 执行语音识别
                result = self.asr.transcribe(audio_data)
                if result and result.text:
                    self.send_json({
                        'type': 'asr_result',
                        'data': asdict(result)
                    })
        
        # 优先使用文件采集器
        if hasattr(self, 'file_capture') and self.file_capture:
            self.file_capture.set_callback(on_audio)
            if not self.file_capture.is_recording:
                self.file_capture.start()
            logger.info("开始语音识别（文件模式）")
        else:
            # 回退到实时音频采集
            self.audio_capture.set_callback(on_audio)
            if not self.audio_capture.is_recording:
                self.audio_capture.start()
            logger.info("开始语音识别（实时模式）")
        
        self.send_json({
            'type': 'listening_started',
            'message': '开始语音识别'
        })
    
    def handle_stop_listening(self):
        """停止监听"""
        self.is_listening = False
        
        # 停止文件采集器
        if hasattr(self, 'file_capture') and self.file_capture:
            self.file_capture.stop()
        
        self.send_json({
            'type': 'listening_stopped',
            'message': '停止语音识别'
        })
        logger.info("停止语音识别")
    
    def handle_tts(self, data: dict):
        """处理TTS请求"""
        if not self.tts.is_loaded:
            self.send_json({
                'type': 'error',
                'message': 'TTS模型未加载'
            })
            return
        
        text = data.get('text', '')
        speed = data.get('speed', 1.0)
        
        if not text:
            self.send_json({
                'type': 'error',
                'message': 'TTS文本不能为空'
            })
            return
        
        # 通知客户端开始合成
        self.send_json({
            'type': 'tts_started',
            'text': text
        })
        
        # 合成语音
        output_path = self.tts.synthesize(text, speed=speed)
        
        if output_path:
            self.send_json({
                'type': 'tts_completed',
                'audio_path': output_path,
                'text': text
            })
            logger.info(f"TTS合成完成: {text[:30]}...")
        else:
            self.send_json({
                'type': 'error',
                'message': 'TTS合成失败'
            })
    
    def send_json(self, data: dict):
        """发送JSON消息"""
        try:
            self.write_message(json.dumps(data))
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
    
    def check_origin(self, origin):
        """允许跨域"""
        return True


class VoiceAssistantServer:
    """
    语音助手服务器
    """
    
    def __init__(self, port: int = 8878, recordings_dir: str = "recordings"):
        self.port = port
        self.recordings_dir = recordings_dir
        self.asr = WhisperASR(model_size="base", language="zh")
        self.tts = PiperTTS()
        self.audio_capture = AudioCapture(
            sample_rate=16000,
            channels=1,
            chunk_duration=3.0
        )
        # 创建文件音频采集器，用于从recordings目录读取录音
        self.file_capture = FileAudioCapture(
            recordings_dir=recordings_dir,
            sample_rate=16000,
            chunk_duration=5.0
        )
        self.app = None
        
    def load_models(self):
        """加载模型"""
        logger.info("正在加载模型...")
        
        # 加载ASR
        asr_loaded = self.asr.load_model()
        
        # 加载TTS
        tts_loaded = self.tts.load_model()
        
        if asr_loaded and tts_loaded:
            logger.info("所有模型加载完成")
            return True
        else:
            logger.warning("部分模型加载失败，服务将降级运行")
            return False
    
    def create_app(self):
        """创建Tornado应用"""
        handlers = [
            (r'/ws/voice', VoiceAssistantWebSocket, {
                'asr': self.asr,
                'tts': self.tts,
                'audio_capture': self.audio_capture,
                'file_capture': self.file_capture
            }),
            (r'/api/status', StatusHandler, {
                'asr': self.asr,
                'tts': self.tts
            }),
        ]
        
        self.app = tornado.web.Application(
            handlers,
            debug=True
        )
        
        return self.app
    
    def start(self):
        """启动服务器"""
        # 加载模型
        self.load_models()
        
        # 创建应用
        self.create_app()
        
        # 启动服务器
        self.app.listen(self.port)
        logger.info(f"语音助手服务已启动，端口: {self.port}")
        logger.info(f"WebSocket地址: ws://localhost:{self.port}/ws/voice")
        
        # 启动IOLoop
        tornado.ioloop.IOLoop.current().start()
    
    def stop(self):
        """停止服务器"""
        logger.info("正在停止语音助手服务...")
        self.audio_capture.stop()
        tornado.ioloop.IOLoop.current().stop()


class StatusHandler(tornado.web.RequestHandler):
    """状态查询接口"""
    
    def initialize(self, asr: WhisperASR, tts: PiperTTS):
        self.asr = asr
        self.tts = tts
    
    def get(self):
        """获取状态"""
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({
            'asr_loaded': self.asr.is_loaded,
            'tts_loaded': self.tts.is_loaded,
            'asr_model': self.asr.model_size if self.asr.is_loaded else None,
            'tts_model': 'piper' if hasattr(self.tts, 'voice') else 'pyttsx3'
        }))


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='语音助手服务')
    parser.add_argument('--port', type=int, default=8878, help='服务端口')
    parser.add_argument('--whisper-model', type=str, default='base', 
                        choices=['tiny', 'base', 'small', 'medium', 'large'],
                        help='Whisper模型大小')
    parser.add_argument('--language', type=str, default='zh', help='识别语言')
    parser.add_argument('--recordings-dir', type=str, default='recordings',
                        help='录音文件目录路径')
    
    args = parser.parse_args()
    
    # 创建服务器
    server = VoiceAssistantServer(port=args.port, recordings_dir=args.recordings_dir)
    server.asr.model_size = args.whisper_model
    server.asr.language = args.language
    
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


if __name__ == '__main__':
    main()

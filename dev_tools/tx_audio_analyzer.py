#!/usr/bin/env python3
"""
TX 音频分析测试工具
用途：录制并分析移动端发射音频的频谱特性

使用方法：
1. 启动此脚本：python3 dev_tools/tx_audio_analyzer.py
2. 在手机端按 PTT 讲话
3. 分析结果会自动保存到 recordings/ 目录

输出：
- WAV 录音文件
- 频谱分析图 (PNG)
- 文本分析报告
"""

import os
import sys
import wave
import time
import struct
import argparse
import tempfile
from datetime import datetime
from pathlib import Path

# 尝试导入 numpy 和 matplotlib
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    print("⚠️ numpy 未安装，频谱分析功能受限")
    print("   安装命令: pip install numpy")

try:
    import matplotlib
    matplotlib.use('Agg')  # 无GUI后端
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
    
    # 配置中文字体支持
    import matplotlib.font_manager as fm
    # macOS 中文字体列表（按优先级）
    chinese_fonts = [
        'PingFang SC',      # macOS 默认中文字体
        'Heiti SC',         # macOS 黑体
        'STHeiti',          # macOS 经典黑体
        'SimHei',           # Windows 黑体
        'WenQuanYi Micro Hei',  # Linux 文泉驿
    ]
    
    # 查找可用的中文字体
    HAS_CHINESE_FONT = False
    available_fonts = [f.name for f in fm.fontManager.ttflist]
    for font_name in chinese_fonts:
        if font_name in available_fonts:
            plt.rcParams['font.sans-serif'] = [font_name, 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
            HAS_CHINESE_FONT = True
            break
        
except ImportError:
    HAS_MATPLOTLIB = False
    HAS_CHINESE_FONT = False
    print("⚠️ matplotlib 未安装，无法生成频谱图")
    print("   安装命令: pip install matplotlib")

# 添加项目根目录到路径
SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

# 录音保存目录
RECORDINGS_DIR = SCRIPT_DIR / "recordings"


class TXAudioAnalyzer:
    """TX 音频分析器"""
    
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.frames = []
        self.is_recording = False
        self.start_time = None
        
        # 确保录音目录存在
        RECORDINGS_DIR.mkdir(exist_ok=True)
    
    def add_audio_data(self, data: bytes):
        """添加音频数据 (Int16 格式)"""
        if not self.is_recording:
            return
        
        self.frames.append(data)
    
    def start_recording(self):
        """开始录音"""
        self.frames = []
        self.is_recording = True
        self.start_time = time.time()
        print(f"🎙️ 开始录音... ({datetime.now().strftime('%H:%M:%S')})")
    
    def stop_recording(self) -> str:
        """停止录音并保存"""
        if not self.is_recording:
            return None
        
        self.is_recording = False
        duration = time.time() - self.start_time
        
        if not self.frames:
            print("⚠️ 没有录到音频数据")
            return None
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        wav_path = RECORDINGS_DIR / f"tx_audio_{timestamp}.wav"
        
        # 合并所有帧
        all_data = b''.join(self.frames)
        
        # 保存 WAV 文件
        with wave.open(str(wav_path), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(all_data)
        
        print(f"✅ 录音保存: {wav_path}")
        print(f"   时长: {duration:.1f}s, 大小: {len(all_data)} bytes")
        
        # 进行频谱分析
        self.analyze_audio(all_data, wav_path)
        
        return str(wav_path)
    
    def analyze_audio(self, raw_data: bytes, wav_path: Path):
        """分析音频频谱"""
        if not HAS_NUMPY:
            print("⚠️ 跳过频谱分析 (numpy 未安装)")
            return
        
        # 转换为 numpy 数组
        samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        if len(samples) < 100:
            print("⚠️ 样本数太少，跳过分析")
            return
        
        # 基本统计
        rms = np.sqrt(np.mean(samples ** 2))
        peak = np.max(np.abs(samples))
        dc_offset = np.mean(samples)
        
        print(f"\n📊 音频统计分析:")
        print(f"   样本数: {len(samples)}")
        print(f"   时长: {len(samples)/self.sample_rate:.2f}s")
        print(f"   RMS 电平: {rms:.4f} ({20*np.log10(rms+1e-10):.1f} dB)")
        print(f"   峰值电平: {peak:.4f} ({20*np.log10(peak+1e-10):.1f} dB)")
        print(f"   DC 偏移: {dc_offset:.6f}")
        
        # 频谱分析
        if HAS_MATPLOTLIB:
            self._generate_spectrum_plot(samples, wav_path)
        
        # 频段能量分析
        self._analyze_frequency_bands(samples)
    
    def _generate_spectrum_plot(self, samples: np.ndarray, wav_path: Path):
        """生成频谱分析图"""
        # FFT 分析
        n = len(samples)
        fft_result = np.fft.rfft(samples)
        freqs = np.fft.rfftfreq(n, 1/self.sample_rate)
        magnitude = np.abs(fft_result) / n
        db = 20 * np.log10(magnitude + 1e-10)
        
        # 根据中文字体可用性选择标签语言
        if HAS_CHINESE_FONT:
            labels = {
                'time': '时间 (秒)',
                'amplitude': '幅度',
                'waveform_title': 'TX 音频波形',
                'frequency': '频率 (Hz)',
                'magnitude_db': '幅度 (dB)',
                'spectrum_title': '频谱分析',
                'lowcut': '低切 100Hz',
                'midfreq': '中频 1500Hz',
                'highcut': '高切 2700Hz',
                'band': '频段',
                'energy_db': '能量 (dB)',
                'band_title': '频段能量分布',
                'bands': {
                    'Ultra Low\n(<100Hz)': '超低频\n(<100Hz)',
                    'Low\n(100-500Hz)': '低频\n(100-500Hz)',
                    'Low-Mid\n(500-1kHz)': '中低频\n(500-1000Hz)',
                    'Mid\n(1k-2kHz)': '中频\n(1k-2kHz)',
                    'High-Mid\n(2k-3kHz)': '中高频\n(2k-3kHz)',
                    'High\n(3k-5kHz)': '高频\n(3k-5kHz)',
                    'Ultra High\n(>5kHz)': '超高频\n(>5kHz)',
                }
            }
        else:
            labels = {
                'time': 'Time (s)',
                'amplitude': 'Amplitude',
                'waveform_title': 'TX Audio Waveform',
                'frequency': 'Frequency (Hz)',
                'magnitude_db': 'Magnitude (dB)',
                'spectrum_title': 'Spectrum Analysis',
                'lowcut': 'Low Cut 100Hz',
                'midfreq': 'Mid Freq 1500Hz',
                'highcut': 'High Cut 2700Hz',
                'band': 'Band',
                'energy_db': 'Energy (dB)',
                'band_title': 'Band Energy Distribution',
                'bands': {
                    'Ultra Low\n(<100Hz)': 'Ultra Low\n(<100Hz)',
                    'Low\n(100-500Hz)': 'Low\n(100-500Hz)',
                    'Low-Mid\n(500-1kHz)': 'Low-Mid\n(500-1kHz)',
                    'Mid\n(1k-2kHz)': 'Mid\n(1k-2kHz)',
                    'High-Mid\n(2k-3kHz)': 'High-Mid\n(2k-3kHz)',
                    'High\n(3k-5kHz)': 'High\n(3k-5kHz)',
                    'Ultra High\n(>5kHz)': 'Ultra High\n(>5kHz)',
                }
            }
        
        # 创建图表
        fig, axes = plt.subplots(3, 1, figsize=(12, 10))
        
        # 1. 波形图
        time_axis = np.arange(len(samples)) / self.sample_rate
        axes[0].plot(time_axis, samples, linewidth=0.5)
        axes[0].set_xlabel(labels['time'])
        axes[0].set_ylabel(labels['amplitude'])
        axes[0].set_title(labels['waveform_title'])
        axes[0].grid(True, alpha=0.3)
        axes[0].set_xlim(0, time_axis[-1])
        
        # 2. 频谱图
        axes[1].plot(freqs, db, linewidth=0.5)
        axes[1].set_xlabel(labels['frequency'])
        axes[1].set_ylabel(labels['magnitude_db'])
        axes[1].set_title(labels['spectrum_title'])
        axes[1].grid(True, alpha=0.3)
        axes[1].set_xlim(0, 8000)  # 只显示到 8kHz
        
        # 标注关键频段
        axes[1].axvline(x=100, color='r', linestyle='--', alpha=0.5, label=labels['lowcut'])
        axes[1].axvline(x=1500, color='g', linestyle='--', alpha=0.5, label=labels['midfreq'])
        axes[1].axvline(x=2700, color='b', linestyle='--', alpha=0.5, label=labels['highcut'])
        axes[1].legend(loc='upper right')
        
        # 3. 频段能量分布 (柱状图)
        bands = {
            labels['bands']['Ultra Low\n(<100Hz)']: (0, 100),
            labels['bands']['Low\n(100-500Hz)']: (100, 500),
            labels['bands']['Low-Mid\n(500-1kHz)']: (500, 1000),
            labels['bands']['Mid\n(1k-2kHz)']: (1000, 2000),
            labels['bands']['High-Mid\n(2k-3kHz)']: (2000, 3000),
            labels['bands']['High\n(3k-5kHz)']: (3000, 5000),
            labels['bands']['Ultra High\n(>5kHz)']: (5000, 8000)
        }
        
        band_energies = []
        band_labels = []
        for label, (low, high) in bands.items():
            mask = (freqs >= low) & (freqs < high)
            if np.any(mask):
                energy = np.mean(magnitude[mask] ** 2)
                band_energies.append(10 * np.log10(energy + 1e-10))
            else:
                band_energies.append(-100)
            band_labels.append(label)
        
        colors = ['#ff6b6b', '#ffa94d', '#ffd43b', '#69db7c', '#4dabf7', '#9775fa', '#f06595']
        bars = axes[2].bar(band_labels, band_energies, color=colors)
        axes[2].set_xlabel(labels['band'])
        axes[2].set_ylabel(labels['energy_db'])
        axes[2].set_title(labels['band_title'])
        axes[2].grid(True, alpha=0.3, axis='y')
        
        # 在柱子上标注数值
        for bar, energy in zip(bars, band_energies):
            height = bar.get_height()
            axes[2].annotate(f'{energy:.1f}',
                           xy=(bar.get_x() + bar.get_width()/2, height),
                           xytext=(0, 3),
                           textcoords="offset points",
                           ha='center', va='bottom', fontsize=8)
        
        plt.tight_layout()
        
        # 保存图片
        plot_path = wav_path.with_suffix('.png')
        plt.savefig(str(plot_path), dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"📈 频谱图保存: {plot_path}")
    
    def _analyze_frequency_bands(self, samples: np.ndarray):
        """分析各频段能量分布"""
        n = len(samples)
        fft_result = np.fft.rfft(samples)
        freqs = np.fft.rfftfreq(n, 1/self.sample_rate)
        magnitude = np.abs(fft_result) / n
        
        # 计算各频段能量占比
        total_energy = np.sum(magnitude ** 2)
        
        bands = {
            '超低频 (<100Hz)': (0, 100),
            '低频 (100-500Hz)': (100, 500),
            '中低频 (500-1000Hz)': (500, 1000),
            '中频 (1k-2kHz)': (1000, 2000),
            '中高频 (2k-3kHz)': (2000, 3000),
            '高频 (3k-5kHz)': (3000, 5000),
            '超高频 (>5kHz)': (5000, 8000)
        }
        
        print(f"\n📊 频段能量分布:")
        print("-" * 50)
        
        for name, (low, high) in bands.items():
            mask = (freqs >= low) & (freqs < high)
            if np.any(mask):
                energy = np.sum(magnitude[mask] ** 2)
                ratio = energy / total_energy * 100
                bar = '█' * int(ratio / 2)
                print(f"   {name:20s}: {ratio:5.1f}% {bar}")
        
        # 诊断建议
        print(f"\n🔍 诊断建议:")
        
        # 计算高频占比
        high_freq_mask = freqs >= 3000
        high_freq_energy = np.sum(magnitude[high_freq_mask] ** 2) / total_energy * 100
        
        if high_freq_energy > 20:
            print(f"   ⚠️ 高频能量占比过高 ({high_freq_energy:.1f}%)，声音可能偏尖锐")
            print(f"      建议：使用更强的 TX EQ 高频衰减 (-30 ~ -35dB)")
        elif high_freq_energy > 10:
            print(f"   ⚡ 高频能量适中 ({high_freq_energy:.1f}%)，可进一步优化")
        else:
            print(f"   ✅ 高频能量控制良好 ({high_freq_energy:.1f}%)")
        
        # 检查中频
        mid_freq_mask = (freqs >= 500) & (freqs < 2000)
        mid_freq_energy = np.sum(magnitude[mid_freq_mask] ** 2) / total_energy * 100
        
        if mid_freq_energy > 40:
            print(f"   ✅ 中频能量充足 ({mid_freq_energy:.1f}%)，语音清晰度好")
        else:
            print(f"   ⚠️ 中频能量不足 ({mid_freq_energy:.1f}%)，建议增强 TX EQ 中频")


class MockAudioCapture:
    """模拟音频捕获器 - 用于从 WebSocket 接收 TX 音频"""
    
    def __init__(self, analyzer: TXAudioAnalyzer):
        self.analyzer = analyzer
        self.is_tx_active = False
    
    def on_tx_start(self):
        """TX 开始回调"""
        self.is_tx_active = True
        self.analyzer.start_recording()
    
    def on_tx_stop(self):
        """TX 结束回调"""
        self.is_tx_active = False
        self.analyzer.stop_recording()
    
    def on_audio_data(self, data: bytes):
        """音频数据回调"""
        if self.is_tx_active:
            self.analyzer.add_audio_data(data)


def run_standalone_test():
    """独立测试模式 - 分析现有 WAV 文件"""
    print("=" * 60)
    print("🎤 TX 音频分析工具 - 独立模式")
    print("=" * 60)
    
    # 查找录音目录中的 WAV 文件
    if not RECORDINGS_DIR.exists():
        print(f"❌ 录音目录不存在: {RECORDINGS_DIR}")
        return
    
    wav_files = list(RECORDINGS_DIR.glob("*.wav"))
    
    if not wav_files:
        print(f"⚠️ 没有找到录音文件")
        print(f"   请先运行实时测试模式录制音频")
        return
    
    print(f"\n📁 找到 {len(wav_files)} 个录音文件:")
    for i, f in enumerate(wav_files[-10:], 1):  # 只显示最近10个
        stat = f.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"   {i}. {f.name} ({stat.st_size} bytes, {mtime})")
    
    # 分析最新的文件
    latest = max(wav_files, key=lambda f: f.stat().st_mtime)
    print(f"\n🔍 分析最新文件: {latest.name}")
    
    # 读取 WAV 文件
    with wave.open(str(latest), 'rb') as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        raw_data = wf.readframes(n_frames)
    
    print(f"   采样率: {sample_rate} Hz")
    print(f"   声道数: {n_channels}")
    print(f"   采样位数: {sample_width * 8} bit")
    print(f"   帧数: {n_frames}")
    print(f"   时长: {n_frames / sample_rate:.2f}s")
    
    # 分析
    analyzer = TXAudioAnalyzer(sample_rate)
    analyzer.analyze_audio(raw_data, latest)


def run_realtime_test(port=8877):
    """实时测试模式 - 等待 TX 音频"""
    print("=" * 60)
    print("🎤 TX 音频分析工具 - 实时模式")
    print("=" * 60)
    print(f"\n📡 等待 TX 音频...")
    print(f"   请在手机端按 PTT 讲话")
    print(f"   按 Ctrl+C 退出")
    print()
    
    analyzer = TXAudioAnalyzer(sample_rate=16000)
    
    # 这里需要集成到 MRRC 的 WebSocket 处理中
    # 暂时使用简单的文件监听方式
    
    print("⚠️ 实时模式需要修改 MRRC 主程序集成")
    print("   请使用独立模式分析现有录音:")
    print(f"   python3 {__file__} --analyze")
    
    return
    
    # TODO: 集成 WebSocket 监听
    # 需要 MRRC 主程序在收到 TX 音频时调用 analyzer.add_audio_data()


def integrate_with_mrrc():
    """打印集成说明"""
    print("""
📋 MRRC 集成说明
================

在 MRRC 主程序中添加以下代码：

1. 在文件开头导入:
   ```python
   from dev_tools.tx_audio_analyzer import TXAudioAnalyzer
   ```

2. 在全局变量区域创建分析器:
   ```python
   tx_audio_analyzer = TXAudioAnalyzer(sample_rate=16000)
   ```

3. 在 PTT 按下时:
   ```python
   tx_audio_analyzer.start_recording()
   ```

4. 在收到 TX 音频数据时:
   ```python
   tx_audio_analyzer.add_audio_data(audio_data)  # Int16 bytes
   ```

5. 在 PTT 释放时:
   ```python
   tx_audio_analyzer.stop_recording()
   ```
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='TX 音频分析测试工具')
    parser.add_argument('--analyze', action='store_true', help='分析现有录音文件')
    parser.add_argument('--realtime', action='store_true', help='实时测试模式')
    parser.add_argument('--integrate', action='store_true', help='显示集成说明')
    parser.add_argument('--port', type=int, default=8877, help='WebSocket 端口')
    
    args = parser.parse_args()
    
    if args.integrate:
        integrate_with_mrrc()
    elif args.realtime:
        run_realtime_test(args.port)
    else:
        # 默认运行独立分析
        run_standalone_test()

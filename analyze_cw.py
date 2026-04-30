#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析录音文件的频谱，找出CW信号的频率
"""

import numpy as np
import wave
import matplotlib.pyplot as plt
from scipy import signal

def analyze_wav_spectrum(filename, start_time=0, duration=5):
    """分析WAV文件的频谱"""
    
    # 读取WAV文件
    with wave.open(filename, 'rb') as wf:
        n_channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        
        print(f"文件: {filename}")
        print(f"采样率: {sample_rate} Hz")
        print(f"通道数: {n_channels}")
        print(f"总时长: {n_frames/sample_rate:.2f} 秒")
        
        # 读取音频数据
        audio_data = wf.readframes(n_frames)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # 如果是立体声，转换为单声道
        if n_channels == 2:
            audio_array = audio_array.reshape(-1, 2).mean(axis=1)
    
    # 提取指定时间段的音频
    start_sample = int(start_time * sample_rate)
    end_sample = int((start_time + duration) * sample_rate)
    segment = audio_array[start_sample:end_sample]
    
    # 计算FFT
    N = len(segment)
    yf = np.fft.fft(segment)
    xf = np.fft.fftfreq(N, 1/sample_rate)
    
    # 只取正频率部分
    positive_freq_mask = xf > 0
    xf_pos = xf[positive_freq_mask]
    yf_pos = np.abs(yf[positive_freq_mask])
    
    # 转换为dB
    yf_db = 20 * np.log10(yf_pos + 1e-10)
    
    # 只分析 100-3000 Hz 范围（语音和CW常见范围）
    freq_mask = (xf_pos >= 100) & (xf_pos <= 3000)
    xf_filtered = xf_pos[freq_mask]
    yf_db_filtered = yf_db[freq_mask]
    
    # 找出峰值
    peaks, properties = signal.find_peaks(yf_db_filtered, height=np.max(yf_db_filtered)-20, distance=50)
    peak_freqs = xf_filtered[peaks]
    peak_amplitudes = yf_db_filtered[peaks]
    
    # 按幅度排序
    sorted_indices = np.argsort(peak_amplitudes)[::-1]
    top_peaks = [(peak_freqs[i], peak_amplitudes[i]) for i in sorted_indices[:10]]
    
    print("\n🔍 频谱分析结果 (100-3000 Hz):")
    print("="*50)
    print(f"{'频率(Hz)':<12} {'幅度(dB)':<12}")
    print("-"*50)
    for freq, amp in top_peaks:
        print(f"{freq:<12.1f} {amp:<12.1f}")
    
    # 绘制频谱图
    plt.figure(figsize=(14, 6))
    
    # 子图1: 频谱
    plt.subplot(1, 2, 1)
    plt.plot(xf_filtered, yf_db_filtered, linewidth=0.8)
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude (dB)')
    plt.title(f'Spectrum Analysis\n{filename.split("/")[-1]}')
    plt.grid(True, alpha=0.3)
    plt.xlim(100, 3000)
    
    # 标记峰值
    for freq, amp in top_peaks[:5]:
        plt.axvline(x=freq, color='r', linestyle='--', alpha=0.5)
        plt.text(freq, amp, f'{freq:.0f}Hz', rotation=90, ha='right', va='bottom', fontsize=8)
    
    # 子图2: 时频图 (Spectrogram)
    plt.subplot(1, 2, 2)
    f, t, Sxx = signal.spectrogram(segment, sample_rate, nperseg=1024, noverlap=512)
    plt.pcolormesh(t, f, 10*np.log10(Sxx + 1e-10), shading='gouraud', cmap='viridis')
    plt.ylabel('Frequency (Hz)')
    plt.xlabel('Time (s)')
    plt.title('Spectrogram')
    plt.colorbar(label='Intensity (dB)')
    plt.ylim(0, 3000)
    
    plt.tight_layout()
    plt.savefig('/Users/cheenle/UHRR/MRRC/spectrum_analysis.png', dpi=150)
    print(f"\n📊 频谱图已保存: spectrum_analysis.png")
    
    # 估计CW频率（通常在 strongest peak 附近的单频）
    print("\n💡 CW频率估计:")
    print("-"*50)
    
    # CW信号通常是纯音调，找到最窄最强的峰
    for freq, amp in top_peaks[:5]:
        if 500 <= freq <= 2500:  # CW常见范围
            print(f"  候选CW频率: {freq:.1f} Hz (幅度: {amp:.1f} dB)")
    
    return top_peaks

if __name__ == "__main__":
    input_file = "/Users/cheenle/UHRR/MRRC/recordings/07050kHz_20260402_070548.wav"
    
    try:
        peaks = analyze_wav_spectrum(input_file, start_time=0, duration=10)
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

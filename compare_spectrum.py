#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比原始文件和NF处理后的文件频谱
"""

import numpy as np
import wave
import matplotlib.pyplot as plt
from scipy import signal

def analyze_file(filename, label, color, ax1, ax2):
    """分析单个文件的频谱"""
    
    with wave.open(filename, 'rb') as wf:
        n_channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        
        audio_data = wf.readframes(n_frames)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        if n_channels == 2:
            audio_array = audio_array.reshape(-1, 2).mean(axis=1)
    
    # 取中间5秒的数据
    duration = 5
    start_sample = len(audio_array) // 2
    end_sample = min(start_sample + int(duration * sample_rate), len(audio_array))
    segment = audio_array[start_sample:end_sample]
    
    # 计算FFT
    N = len(segment)
    yf = np.fft.fft(segment)
    xf = np.fft.fftfreq(N, 1/sample_rate)
    
    positive_freq_mask = xf > 0
    xf_pos = xf[positive_freq_mask]
    yf_pos = np.abs(yf[positive_freq_mask])
    yf_db = 20 * np.log10(yf_pos + 1e-10)
    
    # 只分析 100-3000 Hz
    freq_mask = (xf_pos >= 100) & (xf_pos <= 3000)
    xf_filtered = xf_pos[freq_mask]
    yf_db_filtered = yf_db[freq_mask]
    
    # 在第一个子图绘制频谱
    ax1.plot(xf_filtered, yf_db_filtered, label=label, color=color, linewidth=1.5, alpha=0.8)
    
    # 计算并绘制平滑后的频谱（用于更容易看出问题）
    window_size = 11
    smoothed = np.convolve(yf_db_filtered, np.ones(window_size)/window_size, mode='same')
    ax2.plot(xf_filtered, smoothed, label=f'{label} (平滑)', color=color, linewidth=2)
    
    # 找出峰值
    peaks, properties = signal.find_peaks(yf_db_filtered, height=np.max(yf_db_filtered)-15, distance=30)
    peak_freqs = xf_filtered[peaks]
    peak_amplitudes = yf_db_filtered[peaks]
    
    return list(zip(peak_freqs, peak_amplitudes))

# 创建图形
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10))

# 分析原始文件
print("分析原始文件...")
original_file = "/Users/cheenle/UHRR/MRRC/recordings/07050kHz_20260402_070548.wav"
original_peaks = analyze_file(original_file, "原始文件", "blue", ax1, ax2)

# 分析NF处理后文件
print("分析NF处理后文件...")
nf_file = "/Users/cheenle/UHRR/MRRC/recordings/07050kHz_20260402_070548_nf_correct.wav"
nf_peaks = analyze_file(nf_file, "NF处理后", "red", ax1, ax2)

# 设置第一个子图
ax1.set_xlabel('Frequency (Hz)')
ax1.set_ylabel('Magnitude (dB)')
ax1.set_title('Spectrum Comparison: Original vs NF Processed')
ax1.legend()
ax1.grid(True, alpha=0.3)
ax1.set_xlim(100, 3000)
ax1.axvline(x=1475, color='green', linestyle='--', alpha=0.5, label='Target 1475Hz')

# 设置第二个子图（平滑后）
ax2.set_xlabel('Frequency (Hz)')
ax2.set_ylabel('Magnitude (dB)')
ax2.set_title('Smoothed Spectrum (Easier to see issues)')
ax2.legend()
ax2.grid(True, alpha=0.3)
ax2.set_xlim(100, 3000)
ax2.axvline(x=1475, color='green', linestyle='--', alpha=0.5)

# 子图3: 差异频谱
print("\n计算差异...")
with wave.open(original_file, 'rb') as wf:
    sample_rate = wf.getframerate()
    audio_data = wf.readframes(wf.getnframes())
    original = np.frombuffer(audio_data, dtype=np.int16)

with wave.open(nf_file, 'rb') as wf:
    audio_data = wf.readframes(wf.getnframes())
    processed = np.frombuffer(audio_data, dtype=np.int16)

# 确保长度相同
min_len = min(len(original), len(processed))
original = original[:min_len]
processed = processed[:min_len]

# 计算差异
diff = original - processed

# 计算差异的频谱
N = len(diff)
yf_diff = np.fft.fft(diff)
xf_diff = np.fft.fftfreq(N, 1/sample_rate)
positive_mask = xf_diff > 0
xf_diff_pos = xf_diff[positive_mask]
yf_diff_db = 20 * np.log10(np.abs(yf_diff[positive_mask]) + 1e-10)

freq_mask = (xf_diff_pos >= 100) & (xf_diff_pos <= 3000)
ax3.plot(xf_diff_pos[freq_mask], yf_diff_db[freq_mask], color='purple', linewidth=1.5)
ax3.set_xlabel('Frequency (Hz)')
ax3.set_ylabel('Difference Magnitude (dB)')
ax3.set_title('Difference Spectrum (What was removed)')
ax3.grid(True, alpha=0.3)
ax3.set_xlim(100, 3000)
ax3.axvline(x=1475, color='green', linestyle='--', alpha=0.5)

plt.tight_layout()
plt.savefig('/Users/cheenle/UHRR/MRRC/spectrum_comparison.png', dpi=150)
print("\n📊 对比图已保存: spectrum_comparison.png")

# 打印峰值对比
print("\n" + "="*60)
print("原始文件主要频率成分:")
print("-"*60)
for freq, amp in sorted(original_peaks, key=lambda x: x[1], reverse=True)[:10]:
    marker = "🔴 CW干扰" if 1450 <= freq <= 1500 else ""
    print(f"  {freq:7.1f} Hz: {amp:6.1f} dB {marker}")

print("\n" + "="*60)
print("NF处理后主要频率成分:")
print("-"*60)
for freq, amp in sorted(nf_peaks, key=lambda x: x[1], reverse=True)[:10]:
    reduction = ""
    for ofreq, oamp in original_peaks:
        if abs(ofreq - freq) < 10:
            reduction = f"(降低 {oamp-amp:.1f}dB)"
            break
    print(f"  {freq:7.1f} Hz: {amp:6.1f} dB {reduction}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比三种处理方式的效果
"""

import numpy as np
import wave
from scipy import signal

def analyze_peak(filename, target_freq=1475):
    """分析特定频率的幅度"""
    with wave.open(filename, 'rb') as wf:
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        audio_data = wf.readframes(n_frames)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
    
    # 取中间5秒
    start = len(audio_array) // 2
    end = min(start + int(5 * sample_rate), len(audio_array))
    segment = audio_array[start:end]
    
    # FFT
    N = len(segment)
    yf = np.fft.fft(segment)
    xf = np.fft.fftfreq(N, 1/sample_rate)
    
    # 找到目标频率附近的峰值
    mask = (xf > 0) & (xf >= target_freq - 50) & (xf <= target_freq + 50)
    xf_filtered = xf[mask]
    yf_db = 20 * np.log10(np.abs(yf[mask]) + 1e-10)
    
    peak_idx = np.argmax(yf_db)
    return xf_filtered[peak_idx], yf_db[peak_idx]

# 分析三个文件
files = {
    "原始": "/Users/cheenle/UHRR/MRRC/recordings/07050kHz_20260402_070548.wav",
    "NF第一次(150Hz)": "/Users/cheenle/UHRR/MRRC/recordings/07050kHz_20260402_070548_nf_correct.wav",
    "NF优化(300Hz)": "/Users/cheenle/UHRR/MRRC/recordings/07050kHz_20260402_070548_nf_optimized.wav"
}

print("="*60)
print("CW干扰消除效果对比 (1475Hz附近)")
print("="*60)
print(f"{'处理方式':<20} {'频率(Hz)':<12} {'幅度(dB)':<12} {'降低':<10}")
print("-"*60)

original_freq, original_db = None, None
for name, filepath in files.items():
    freq, db = analyze_peak(filepath)
    if original_db is None:
        original_freq, original_db = freq, db
        reduction = "-"
    else:
        reduction = f"{original_db - db:.1f} dB"
    print(f"{name:<20} {freq:<12.1f} {db:<12.1f} {reduction:<10}")

print("="*60)
print("\n💡 建议:")
print("- 使用300Hz宽度可以获得更好的消除效果")
print("- 关键修复: 同时启用RXANBPSetRun和RXANBPSetNotchesRun")

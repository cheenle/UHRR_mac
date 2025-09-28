#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for audio interface on macOS
"""

import pyaudio
import time

def test_audio_devices():
    """Test audio device enumeration"""
    print("Testing audio device enumeration...")
    
    try:
        p = pyaudio.PyAudio()
        print(f"Number of audio devices: {p.get_device_count()}")
        
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            print(f"Device {i}: {info['name']}")
            print(f"  - Max input channels: {info['maxInputChannels']}")
            print(f"  - Max output channels: {info['maxOutputChannels']}")
            print(f"  - Default sample rate: {info['defaultSampleRate']}")
            print()
        
        p.terminate()
        print("Audio device enumeration test completed successfully!")
        return True
    except Exception as e:
        print(f"Error during audio device enumeration: {e}")
        return False

def test_audio_capture():
    """Test audio capture"""
    print("Testing audio capture...")
    
    try:
        p = pyaudio.PyAudio()
        
        # Open input stream
        stream = p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=8000,
            input=True,
            frames_per_buffer=256
        )
        
        print("Recording for 3 seconds...")
        frames = []
        for i in range(0, int(8000 / 256 * 3)):
            data = stream.read(256)
            frames.append(data)
        
        # Close stream
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        print(f"Captured {len(frames)} frames")
        print("Audio capture test completed successfully!")
        return True
    except Exception as e:
        print(f"Error during audio capture: {e}")
        return False

def test_audio_playback():
    """Test audio playback"""
    print("Testing audio playback...")
    
    try:
        p = pyaudio.PyAudio()
        
        # Open output stream
        stream = p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=8000,
            output=True,
            frames_per_buffer=256
        )
        
        # Generate simple sine wave
        import numpy as np
        duration = 2  # seconds
        frequency = 440  # Hz
        samples = np.sin(2 * np.pi * np.arange(8000 * duration) * frequency / 8000)
        samples = samples.astype(np.float32)
        
        # Play audio
        print("Playing sine wave for 2 seconds...")
        stream.write(samples.tobytes())
        
        # Close stream
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        print("Audio playback test completed successfully!")
        return True
    except Exception as e:
        print(f"Error during audio playback: {e}")
        return False

if __name__ == "__main__":
    print("=== Audio Interface Test on macOS ===")
    print()
    
    # Test device enumeration
    if test_audio_devices():
        print("✓ Device enumeration test passed")
    else:
        print("✗ Device enumeration test failed")
    
    print()
    
    # Test audio capture
    if test_audio_capture():
        print("✓ Audio capture test passed")
    else:
        print("✗ Audio capture test failed")
    
    print()
    
    # Test audio playback
    if test_audio_playback():
        print("✓ Audio playback test passed")
    else:
        print("✗ Audio playback test failed")
    
    print()
    print("=== Test Complete ===")
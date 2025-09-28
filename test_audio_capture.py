#!/usr/bin/env python3
import pyaudio
import time

def test_audio_capture():
    """Test if audio capture is working"""
    try:
        # Initialize PyAudio
        p = pyaudio.PyAudio()
        
        print("Available audio devices:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            print(f"  {i}: {info['name']} - Input channels: {info['maxInputChannels']}, Output channels: {info['maxOutputChannels']}")
        
        # Try to find a suitable input device
        input_device_index = None
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0 and 'USB' in info['name']:
                input_device_index = i
                print(f"Selected input device: {info['name']} (index {i})")
                break
        
        if input_device_index is None:
            print("No USB input device found, using default")
            input_device_index = None  # Use default
        
        # Try to open stream
        stream = p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=8000,
            input=True,
            input_device_index=input_device_index,
            frames_per_buffer=256
        )
        
        print("Audio stream opened successfully")
        
        # Try to read some data
        print("Testing audio capture...")
        for i in range(10):
            data = stream.read(256)
            if len(data) > 0:
                print(f"Audio data captured: {len(data)} bytes")
            else:
                print("No audio data")
            time.sleep(0.1)
        
        # Clean up
        stream.stop_stream()
        stream.close()
        p.terminate()
        print("Audio test completed successfully")
        
    except Exception as e:
        print(f"Audio test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_audio_capture()
#!/usr/bin/env python3
"""
Test PyAudio initialization to diagnose audio issues
"""

import sys
import traceback

def test_pyaudio():
    print("🔍 Testing PyAudio initialization...")
    
    try:
        import pyaudio
        print("✅ PyAudio module imported successfully")
        
        p = pyaudio.PyAudio()
        print(f"✅ PyAudio instance created, {p.get_device_count()} devices available")
        
        # List devices
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            print(f"  Device {i}: {info['name']} (in: {info['maxInputChannels']}, out: {info['maxOutputChannels']})")
        
        # Test input device
        try:
            stream = p.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=12000,
                input=True,
                frames_per_buffer=256
            )
            print("✅ Input stream opened successfully at 12000 Hz")
            
            # Try to read some data
            data = stream.read(256, exception_on_overflow=False)
            print(f"✅ Audio data read successfully: {len(data)} bytes")
            
            stream.close()
            print("✅ Input stream closed successfully")
            
        except Exception as e:
            print(f"❌ Input stream failed: {e}")
            traceback.print_exc()
        
        p.terminate()
        print("✅ PyAudio terminated successfully")
        
    except Exception as e:
        print(f"❌ PyAudio test failed: {e}")
        traceback.print_exc()
        return False
    
    return True

def test_audio_interface():
    print("\n🔍 Testing audio_interface module...")
    
    try:
        from audio_interface import PyAudioCapture, enumerate_audio_devices
        print("✅ audio_interface module imported successfully")
        
        # Test device enumeration
        devices = enumerate_audio_devices()
        print(f"✅ Device enumeration successful: {len(devices)} devices")
        
        # Test PyAudioCapture initialization
        config = {
            'AUDIO': {
                'inputdevice': 'USB Audio CODEC',
                'outputdevice': 'USB Audio CODEC'
            }
        }
        
        capture = PyAudioCapture(config)
        print("✅ PyAudioCapture instance created successfully")
        
        # Check if stream is available
        if hasattr(capture, 'stream') and capture.stream:
            print("✅ Audio stream is available")
        else:
            print("❌ Audio stream is not available")
        
        capture.close()
        print("✅ PyAudioCapture closed successfully")
        
    except Exception as e:
        print(f"❌ audio_interface test failed: {e}")
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 UHRR Audio Diagnostic Test")
    print("=" * 40)
    
    pyaudio_ok = test_pyaudio()
    interface_ok = test_audio_interface()
    
    print("\n📊 Test Results:")
    print("=" * 20)
    print(f"PyAudio: {'✅ PASS' if pyaudio_ok else '❌ FAIL'}")
    print(f"Audio Interface: {'✅ PASS' if interface_ok else '❌ FAIL'}")
    
    if pyaudio_ok and interface_ok:
        print("\n🎉 All tests passed! Audio should be working.")
    else:
        print("\n⚠️  Some tests failed. Audio may not be working properly.")

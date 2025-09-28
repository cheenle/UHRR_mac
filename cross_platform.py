#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cross-platform compatibility layer
Provides unified interfaces for audio, radio control, and other platform-specific features
"""

import platform
import sys

# Audio interface
try:
    import pyaudio
    from audio_interface import PyAudioCapture, PyAudioPlayback, enumerate_audio_devices
    AUDIO_BACKEND = "pyaudio"
except ImportError:
    try:
        import alsaaudio
        AUDIO_BACKEND = "alsa"
    except ImportError:
        AUDIO_BACKEND = "none"

# Radio control interface
RADIO_BACKEND = "none"
try:
    from hamlib_wrapper import HamlibWrapper, HAMLIB_AVAILABLE
    if HAMLIB_AVAILABLE:
        RADIO_BACKEND = "hamlib_ctypes"
except ImportError:
    pass

if RADIO_BACKEND == "none":
    try:
        import Hamlib
        RADIO_BACKEND = "hamlib_native"
    except ImportError:
        pass

def get_platform_info():
    """Get platform information"""
    return {
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor()
    }

def get_audio_backend():
    """Get current audio backend"""
    return AUDIO_BACKEND

def get_radio_backend():
    """Get current radio backend"""
    return RADIO_BACKEND

class CrossPlatformAudio:
    """Cross-platform audio interface"""
    
    def __init__(self, config):
        self.config = config
        self.backend = AUDIO_BACKEND
        
        if self.backend == "pyaudio":
            # Use PyAudio implementation
            pass
        elif self.backend == "alsa":
            # Use ALSA implementation
            import alsaaudio
        else:
            raise RuntimeError("No audio backend available")
    
    def create_capture(self):
        """Create audio capture instance"""
        if self.backend == "pyaudio":
            return PyAudioCapture(self.config)
        elif self.backend == "alsa":
            # Fallback to original ALSA implementation
            from UHRR import loadWavdata
            return loadWavdata()
        else:
            raise RuntimeError("No audio backend available")
    
    def create_playback(self, itrate, is_encoded, op_rate, op_frm_dur):
        """Create audio playback instance"""
        if self.backend == "pyaudio":
            return PyAudioPlayback(self.config, itrate, is_encoded, op_rate, op_frm_dur)
        elif self.backend == "alsa":
            # Return parameters needed for ALSA implementation
            return {
                'itrate': itrate,
                'is_encoded': is_encoded,
                'op_rate': op_rate,
                'op_frm_dur': op_frm_dur
            }
        else:
            raise RuntimeError("No audio backend available")
    
    def enumerate_devices(self):
        """Enumerate audio devices"""
        if self.backend == "pyaudio":
            devices = enumerate_audio_devices()
            # Convert to the same format as ALSA
            output_devices = [d['name'] for d in devices if d['max_output_channels'] > 0]
            input_devices = [d['name'] for d in devices if d['max_input_channels'] > 0]
            return {
                'output': output_devices,
                'input': input_devices
            }
        elif self.backend == "alsa":
            import alsaaudio
            output_devices = [s for s in alsaaudio.pcms(0) if "plughw" in s]
            input_devices = [s for s in alsaaudio.pcms(1) if "plughw" in s]
            return {
                'output': output_devices,
                'input': input_devices
            }
        else:
            return {'output': [], 'input': []}

class CrossPlatformRadio:
    """Cross-platform radio control interface"""
    
    def __init__(self):
        self.backend = RADIO_BACKEND
        self.radio = None
        
        if self.backend == "hamlib_ctypes":
            # Use ctypes-based Hamlib wrapper
            self.radio = HamlibWrapper()
        elif self.backend == "hamlib_native":
            # Use native Hamlib bindings
            import Hamlib
            self.radio = Hamlib
        else:
            raise RuntimeError("No radio backend available")
    
    def init_rig(self, rig_model):
        """Initialize radio"""
        if self.backend == "hamlib_ctypes":
            return self.radio.rig_init(rig_model)
        elif self.backend == "hamlib_native":
            return self.radio.Rig(rig_model)
        else:
            raise RuntimeError("No radio backend available")
    
    def set_conf(self, token, val):
        """Set configuration"""
        if self.backend == "hamlib_ctypes":
            return self.radio.rig_set_conf(token, val)
        elif self.backend == "hamlib_native":
            return self.radio.set_conf(token, val)
        else:
            raise RuntimeError("No radio backend available")
    
    def open_rig(self):
        """Open radio connection"""
        if self.backend == "hamlib_ctypes":
            return self.radio.rig_open()
        elif self.backend == "hamlib_native":
            return self.radio.open()
        else:
            raise RuntimeError("No radio backend available")
    
    def set_freq(self, vfo, freq):
        """Set frequency"""
        if self.backend == "hamlib_ctypes":
            return self.radio.rig_set_freq(vfo, freq)
        elif self.backend == "hamlib_native":
            return self.radio.set_freq(vfo, freq)
        else:
            raise RuntimeError("No radio backend available")
    
    def get_freq(self, vfo):
        """Get frequency"""
        if self.backend == "hamlib_ctypes":
            return self.radio.rig_get_freq(vfo)
        elif self.backend == "hamlib_native":
            return self.radio.get_freq()
        else:
            raise RuntimeError("No radio backend available")
    
    def set_ptt(self, vfo, ptt_state):
        """Set PTT"""
        if self.backend == "hamlib_ctypes":
            return self.radio.rig_set_ptt(vfo, ptt_state)
        elif self.backend == "hamlib_native":
            if ptt_state == 1:
                return self.radio.set_ptt(self.radio.RIG_PTT_ON)
            else:
                return self.radio.set_ptt(self.radio.RIG_PTT_OFF)
        else:
            raise RuntimeError("No radio backend available")
    
    def get_level(self, vfo, level):
        """Get level"""
        if self.backend == "hamlib_ctypes":
            return self.radio.rig_get_level(vfo, level)
        elif self.backend == "hamlib_native":
            return self.radio.get_level_i(level)
        else:
            raise RuntimeError("No radio backend available")
    
    def set_powerstat(self, power_state):
        """Set power state"""
        if self.backend == "hamlib_ctypes":
            return self.radio.rig_set_powerstat(power_state)
        elif self.backend == "hamlib_native":
            return self.radio.set_powerstat(power_state)
        else:
            raise RuntimeError("No radio backend available")

# Test the cross-platform layer
if __name__ == "__main__":
    print("=== Cross-Platform Compatibility Layer Test ===")
    print()
    
    # Test platform info
    platform_info = get_platform_info()
    print(f"Platform: {platform_info['system']} {platform_info['release']}")
    print(f"Machine: {platform_info['machine']}")
    print()
    
    # Test audio backend
    audio_backend = get_audio_backend()
    print(f"Audio backend: {audio_backend}")
    
    # Test radio backend
    radio_backend = get_radio_backend()
    print(f"Radio backend: {radio_backend}")
    print()
    
    # Test audio interface
    try:
        # This would normally use config, but we'll create a minimal one for testing
        config = {
            'AUDIO': {
                'inputdevice': '',
                'outputdevice': ''
            }
        }
        audio = CrossPlatformAudio(config)
        devices = audio.enumerate_devices()
        print(f"Audio devices found: {len(devices.get('input', []))} input, {len(devices.get('output', []))} output")
        print("✓ Cross-platform audio interface test passed")
    except Exception as e:
        print(f"✗ Cross-platform audio interface test failed: {e}")
    
    print()
    
    # Test radio interface
    try:
        radio = CrossPlatformRadio()
        print("✓ Cross-platform radio interface test passed")
    except Exception as e:
        print(f"✗ Cross-platform radio interface test failed: {e}")
    
    print()
    print("=== Test Complete ===")
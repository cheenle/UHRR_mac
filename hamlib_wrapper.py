#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Hamlib wrapper using ctypes
Provides a Python interface to the Hamlib library for radio control
"""

import ctypes
import ctypes.util
from ctypes import c_int, c_void_p, c_double, c_char_p, POINTER

# Load the Hamlib library
lib_path = ctypes.util.find_library('hamlib')
if not lib_path:
    # Try common paths on macOS
    import os
    common_paths = [
        '/opt/local/lib/libhamlib.dylib',
        '/opt/homebrew/lib/libhamlib.dylib',
        '/usr/local/lib/libhamlib.dylib'
    ]
    for path in common_paths:
        if os.path.exists(path):
            lib_path = path
            break

if not lib_path:
    raise ImportError("Hamlib library not found")

libham = ctypes.CDLL(lib_path)

# Define Hamlib constants
RIG_MODEL_FT817 = 123  # Example model
RIG_VFO_CURR = 0x00000001
RIG_PTT_ON = 1
RIG_PTT_OFF = 0
RIG_POWER_ON = 1
RIG_POWER_OFF = 0
RIG_LEVEL_STRENGTH = 1  # Example level

# Define data types
class value_t(ctypes.Union):
    _fields_ = [("i", c_int), ("f", c_double), ("s", c_char_p)]

# Define Hamlib function signatures
try:
    libham.rig_set_debug.argtypes = [c_int]
    libham.rig_set_debug.restype = None

    libham.rig_init.argtypes = [c_int]
    libham.rig_init.restype = c_void_p
    
    # Set device path during initialization
    libham.rig_set_pathname.argtypes = [c_void_p, c_char_p]
    libham.rig_set_pathname.restype = c_int

    libham.rig_open.argtypes = [c_void_p]
    libham.rig_open.restype = c_int

    libham.rig_set_conf.argtypes = [c_void_p, c_char_p, c_char_p]
    libham.rig_set_conf.restype = c_int

    libham.rig_get_vfo.argtypes = [c_void_p, POINTER(c_int)]
    libham.rig_get_vfo.restype = c_int

    libham.rig_set_freq.argtypes = [c_void_p, c_int, c_double]
    libham.rig_set_freq.restype = c_int

    libham.rig_get_freq.argtypes = [c_void_p, c_int, POINTER(c_double)]
    libham.rig_get_freq.restype = c_int

    libham.rig_set_ptt.argtypes = [c_void_p, c_int, c_int]
    libham.rig_set_ptt.restype = c_int

    libham.rig_get_level.argtypes = [c_void_p, c_int, c_int, POINTER(value_t)]
    libham.rig_get_level.restype = c_int

    libham.rig_set_powerstat.argtypes = [c_void_p, c_int]
    libham.rig_set_powerstat.restype = c_int

    libham.rig_set_mode.argtypes = [c_void_p, c_int, c_int, c_int]
    libham.rig_set_mode.restype = c_int

    libham.rig_get_mode.argtypes = [c_void_p, c_int, POINTER(c_int), POINTER(c_int)]
    libham.rig_get_mode.restype = c_int

    libham.rig_set_level.argtypes = [c_void_p, c_int, c_int, value_t]
    libham.rig_set_level.restype = c_int

    HAMLIB_AVAILABLE = True
except AttributeError as e:
    print(f"Warning: Some Hamlib functions not available: {e}")
    HAMLIB_AVAILABLE = False

class HamlibWrapper:
    """Wrapper class for Hamlib functions"""
    
    def __init__(self):
        self.rig = None
        if not HAMLIB_AVAILABLE:
            raise ImportError("Hamlib functions not fully available")
        
    def rig_set_debug(self, debug_level):
        """Set debug level"""
        libham.rig_set_debug(debug_level)
        
    def rig_init(self, rig_model):
        """Initialize rig"""
        self.rig = libham.rig_init(rig_model)
        return self.rig
        
    def rig_init_with_pathname(self, rig_model, pathname):
        """Initialize rig with specific pathname"""
        self.rig = libham.rig_init(rig_model)
        if self.rig:
            # Try to set the pathname using the internal structure
            # This is a workaround for the configuration issue
            try:
                result = libham.rig_set_conf(self.rig, b"rig_pathname", pathname.encode())
                print(f"Set pathname result: {result}")
            except:
                print("Could not set pathname via rig_set_conf")
        return self.rig
        
    def rig_set_conf(self, token, val):
        """Set configuration parameter"""
        if self.rig:
            return libham.rig_set_conf(self.rig, token.encode(), val.encode())
        return -1
        
    def rig_open(self):
        """Open rig connection"""
        if self.rig:
            return libham.rig_open(self.rig)
        return -1
        
    def rig_get_vfo(self):
        """Get current VFO"""
        if self.rig:
            vfo = c_int()
            result = libham.rig_get_vfo(self.rig, ctypes.byref(vfo))
            if result == 0:
                return vfo.value
        return None
        
    def rig_set_freq(self, vfo, freq):
        """Set frequency"""
        if self.rig:
            return libham.rig_set_freq(self.rig, vfo, c_double(freq))
        return -1
        
    def rig_get_freq(self, vfo):
        """Get frequency"""
        if self.rig:
            freq = c_double()
            result = libham.rig_get_freq(self.rig, vfo, ctypes.byref(freq))
            if result == 0:
                return freq.value
        return None
        
    def rig_set_ptt(self, vfo, ptt_state):
        """Set PTT state"""
        if self.rig:
            return libham.rig_set_ptt(self.rig, vfo, ptt_state)
        return -1
        
    def rig_get_level(self, vfo, level):
        """Get level value"""
        if self.rig:
            val = value_t()
            result = libham.rig_get_level(self.rig, vfo, level, ctypes.byref(val))
            if result == 0:
                return val.i  # Return integer value
        return -1
        
    def rig_set_powerstat(self, power_state):
        """Set power state"""
        if self.rig:
            return libham.rig_set_powerstat(self.rig, power_state)
        return -1
    
    def rig_set_mode(self, vfo, mode, passband):
        """Set mode"""
        if self.rig:
            return libham.rig_set_mode(self.rig, vfo, mode, passband)
        return -1
    
    def rig_get_mode(self, vfo):
        """Get mode"""
        if self.rig:
            mode = c_int()
            passband = c_int()
            result = libham.rig_get_mode(self.rig, vfo, ctypes.byref(mode), ctypes.byref(passband))
            if result == 0:
                return mode.value, passband.value
        return -1, 0
    
    def rig_set_level(self, vfo, level, val):
        """Set level value"""
        if self.rig:
            level_val = value_t()
            level_val.f = val  # Set as float value
            return libham.rig_set_level(self.rig, vfo, level, level_val)
        return -1

# Test the wrapper
if __name__ == "__main__":
    try:
        hamlib = HamlibWrapper()
        print("Hamlib wrapper created successfully")
    except Exception as e:
        print(f"Error creating Hamlib wrapper: {e}")
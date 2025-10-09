#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Final verification script to check if all audio streaming components are properly configured
"""

import os
import sys
import importlib.util

def check_file_exists(filepath, description):
    """Check if a file exists and print status"""
    if os.path.exists(filepath):
        print(f"✓ {description} exists")
        return True
    else:
        print(f"✗ {description} missing")
        return False

def check_python_module(module_name, description):
    """Check if a Python module can be imported"""
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is not None:
            print(f"✓ {description} available")
            return True
        else:
            print(f"✗ {description} not found")
            return False
    except ImportError:
        print(f"✗ {description} import failed")
        return False

def check_opus_decoder():
    """Check if the Opus decoder has been fixed"""
    decoder_path = "/Users/cheenle/UHRR/UHRR_mac/opus/api/decoder.py"
    if not os.path.exists(decoder_path):
        print("✗ Opus decoder file not found")
        return False
    
    try:
        with open(decoder_path, 'r') as f:
            content = f.read()
            
        # Check if the fix has been applied
        if ".tobytes()" in content and ".tostring()" not in content:
            print("✓ Opus decoder properly fixed for Python 3.12")
            return True
        else:
            print("✗ Opus decoder not properly fixed")
            return False
    except Exception as e:
        print(f"✗ Error reading Opus decoder: {e}")
        return False

def check_web_files():
    """Check if all necessary web files exist"""
    base_path = "/Users/cheenle/UHRR/UHRR_mac/www"
    files_to_check = [
        ("mobile_modern.html", "Mobile HTML interface"),
        ("mobile_modern.js", "Mobile JavaScript interface"),
        ("mobile_audio_direct_copy.js", "Mobile audio implementation"),
        ("controls.js", "Desktop audio controls")
    ]
    
    all_good = True
    for filename, description in files_to_check:
        filepath = os.path.join(base_path, filename)
        if not check_file_exists(filepath, description):
            all_good = False
    
    return all_good

def check_python_dependencies():
    """Check if all necessary Python dependencies are available"""
    modules_to_check = [
        ("tornado", "Tornado web framework"),
        ("pyaudio", "PyAudio library"),
        ("numpy", "NumPy library"),
        ("opus", "Opus codec library"),
        ("configparser", "Config parser"),
        ("websocket", "WebSocket library")
    ]
    
    all_good = True
    for module_name, description in modules_to_check:
        if not check_python_module(module_name, description):
            all_good = False
    
    return all_good

def main():
    print("=== UHRR Audio Streaming Verification ===\n")
    
    # Check Python version
    print(f"Python version: {sys.version}")
    if sys.version_info >= (3, 12):
        print("✓ Python 3.12+ compatibility verified")
    else:
        print("⚠ Python version may not be compatible with fixes")
    
    print("\n--- File System Check ---")
    # Check Opus decoder fix
    opus_good = check_opus_decoder()
    
    # Check web files
    web_files_good = check_web_files()
    
    print("\n--- Python Dependencies ---")
    # Check Python dependencies
    deps_good = check_python_dependencies()
    
    print("\n--- Summary ---")
    if opus_good and web_files_good and deps_good:
        print("✓ All checks passed - Audio streaming should work correctly")
        print("\nTo test audio streaming:")
        print("1. Start the UHRR server: ./UHRR")
        print("2. Open the mobile interface in a browser")
        print("3. Connect to the radio using the power button")
        print("4. Check that RX status becomes active")
        print("5. Test TX by pressing the PTT button")
        print("6. Use the 'Test Audio' button if issues occur")
    else:
        print("✗ Some checks failed - Audio streaming may not work correctly")
        if not opus_good:
            print("  - Opus decoder needs to be fixed")
        if not web_files_good:
            print("  - Missing web interface files")
        if not deps_good:
            print("  - Missing Python dependencies")

if __name__ == "__main__":
    main()
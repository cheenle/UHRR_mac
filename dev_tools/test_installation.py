#!/usr/bin/env python3
"""
Test script to verify that all dependencies are properly installed 
and the Universal HamRadio Remote HTML5 application can run correctly.
"""

import sys
import os

def test_python_version():
    """Test that we're using Python 3.7 or higher"""
    print("Testing Python version...")
    if sys.version_info < (3, 7):
        print(f"ERROR: Python 3.7+ required, but found {sys.version}")
        return False
    print(f"✓ Python {sys.version}")
    return True

def test_required_packages():
    """Test that all required packages can be imported"""
    required_packages = [
        ('tornado', 'Tornado web framework'),
        ('numpy', 'NumPy for numerical computing'),
        ('pyaudio', 'PyAudio for cross-platform audio'),
        ('opuslib', 'Opus audio codec library'),
        ('configparser', 'Configuration file parser')
    ]
    
    print("\nTesting required Python packages...")
    all_passed = True
    
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"✓ {description} ({package})")
        except ImportError as e:
            print(f"✗ {description} ({package}) - {e}")
            all_passed = False
    
    return all_passed

def test_hamlib_integration():
    """Test Hamlib integration"""
    print("\nTesting Hamlib integration...")
    try:
        from hamlib_wrapper import HamlibWrapper
        print("✓ Hamlib wrapper imported successfully")
        # Note: We don't actually try to connect to a radio here
        # Just testing that the wrapper can be imported
        return True
    except ImportError as e:
        print(f"✗ Hamlib wrapper import failed - {e}")
        return False
    except Exception as e:
        print(f"✓ Hamlib wrapper imported but runtime error (expected if no radio connected) - {e}")
        return True

def test_audio_interface():
    """Test audio interface"""
    print("\nTesting audio interface...")
    try:
        from audio_interface import PyAudioCapture, PyAudioPlayback, enumerate_audio_devices
        print("✓ Audio interface imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Audio interface import failed - {e}")
        return False

def test_config_file():
    """Test that configuration file exists and is readable"""
    print("\nTesting configuration file...")
    config_file = "UHRR.conf"
    if os.path.exists(config_file):
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read(config_file)
            print("✓ Configuration file exists and is readable")
            return True
        except Exception as e:
            print(f"✗ Configuration file error - {e}")
            return False
    else:
        print(f"✗ Configuration file {config_file} not found")
        return False

def test_ssl_certificates():
    """Test that SSL certificates exist"""
    print("\nTesting SSL certificates...")
    cert_file = "UHRH.crt"
    key_file = "UHRH.key"
    
    cert_exists = os.path.exists(cert_file)
    key_exists = os.path.exists(key_file)
    
    if cert_exists and key_exists:
        print("✓ SSL certificate and key files exist")
        return True
    else:
        missing = []
        if not cert_exists:
            missing.append(cert_file)
        if not key_exists:
            missing.append(key_file)
        print(f"✗ Missing SSL files: {', '.join(missing)}")
        return False

def main():
    """Run all tests"""
    print("Universal HamRadio Remote HTML5 - Installation Test")
    print("=" * 50)
    
    tests = [
        test_python_version,
        test_required_packages,
        test_hamlib_integration,
        test_audio_interface,
        test_config_file,
        test_ssl_certificates
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The application should run correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
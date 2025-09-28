# macOS Setup Guide for Universal HamRadio Remote

This guide provides instructions for setting up and running the Universal HamRadio Remote application on macOS.

## Prerequisites

1. Homebrew (https://brew.sh/)
2. Python 3.8 or higher
3. Xcode command line tools

## Installation Steps

### 1. Install Required Dependencies

```bash
# Install audio and radio libraries
brew install portaudio hamlib rtl-sdr

# Install Python packages
pip3 install pyaudio numpy tornado pyserial pyrtlsdr
```

### 2. Install Hamlib Python Bindings

The Hamlib Python bindings need to be installed separately. There are a few options:

#### Option A: Try to install from PyPI (if available)
```bash
pip3 install hamlib
```

#### Option B: Build from source
If the PyPI package is not available, you may need to build the Python bindings from the Hamlib source code.

### 3. Configure Audio Devices

The application uses specific audio device names. On macOS, you'll need to:

1. Identify your audio devices:
   ```bash
   python3 -c "import pyaudio; p = pyaudio.PyAudio(); for i in range(p.get_device_count()): dev = p.get_device_info_by_index(i); print(f'{i}: {dev['name']}')"
   ```

2. Update the `UHRR.conf` file with the correct device names for your system.

### 4. Configure Serial Port (for radio control)

Update the `UHRR.conf` file with the correct serial port for your radio:

```ini
[HAMLIB]
rig_pathname = /dev/tty.usbserial*  # or your specific device path
```

### 5. Run the Application

```bash
./UHRR
```

Access the interface at: https://localhost:8888/

## Platform-Specific Considerations

### Audio System
- **Linux**: Uses ALSA
- **macOS**: Uses CoreAudio via PyAudio/PortAudio

### Serial Ports
- **Linux**: `/dev/ttyUSB0`, `/dev/ttyACM0`, etc.
- **macOS**: `/dev/tty.usbserial*`, `/dev/cu.*`, etc.

### Authentication
- PAM authentication may not work the same way on macOS
- Consider using FILE-based authentication instead

## Troubleshooting

### Common Issues

1. **Audio device not found**: Check device names in `UHRR.conf`
2. **Serial port permissions**: Add user to dialout group or use sudo
3. **SSL certificate issues**: Generate new certificates or disable SSL for development
4. **Hamlib Python bindings**: If not available, consider using ctypes to interface directly with the library

### Testing Audio

To test if audio is working properly:

```bash
# List audio devices
python3 -c "import pyaudio; p = pyaudio.PyAudio(); print('Audio devices:'); [print(f'{i}: {p.get_device_info_by_index(i)['name']}') for i in range(p.get_device_count())]; p.terminate()"
```
# MRRC Complete Installation and Configuration Guide

## 📋 Table of Contents

1. [System Requirements](#system-requirements)
2. [Quick Start](#quick-start)
3. [macOS Detailed Installation](#macos-detailed-installation)
4. [Linux Detailed Installation](#linux-detailed-installation)
5. [WDSP Library Compilation and Installation](#wdsp-library-compilation-and-installation)
6. [Configuration File Details](#configuration-file-details)
7. [Multi-Instance Configuration](#multi-instance-configuration)
8. [TLS/SSL Certificate Configuration](#tlsssl-certificate-configuration)
9. [Service Management](#service-management)
10. [Troubleshooting](#troubleshooting)
11. [FAQ](#faq)

---

## System Requirements

### Minimum Configuration
- **CPU**: ARM64 (Apple Silicon) or x86_64, 2 cores or more
- **Memory**: 2GB RAM
- **Storage**: 1GB available space
- **Network**: Stable internet connection (for remote access)

### Recommended Configuration
- **CPU**: Apple M1/M2/M3 or 4+ core x86_64
- **Memory**: 4GB RAM
- **Storage**: 2GB available space
- **Network**: Wired network or stable Wi-Fi

### Supported Operating Systems
- **macOS**: 12.0+ (Monterey and above)
- **Linux**: Ubuntu 20.04+, Debian 11+, CentOS 8+
- **Python**: 3.9+ (3.12 recommended)

---

## Quick Start

### One-Click Installation (macOS)

```bash
# Clone repository
git clone https://github.com/cheenle/UHRR_mac.git
cd UHRR_mac

# Run installation script
./mrrc_setup.sh install
```

### One-Click Installation (Linux)

```bash
# Clone repository
git clone https://github.com/cheenle/UHRR_mac.git
cd UHRR_mac

# Install dependencies and configure
sudo ./install_linux.sh
```

---

## macOS Detailed Installation

### Step 1: Install Homebrew

If Homebrew is not installed yet:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Step 2: Install System Dependencies

```bash
# Basic dependencies
brew install python@3.12
brew install hamlib
brew install portaudio
brew install git

# Optional: WDSP DSP library (recommended for best noise reduction)
# See [WDSP Library Compilation and Installation](#wdsp-library-compilation-and-installation) section for details
```

### Step 3: Install Python Dependencies

```bash
# Install Python packages using pip3
pip3 install tornado numpy pyaudio pyrtlsdr opuslib pyserial

# If using WDSP (recommended)
pip3 install cffi

# If using RTL-SDR (for spectrum functionality)
pip3 install pyrtlsdr
```

### Step 4: Configure Audio Devices

#### 4.1 Find Audio Devices

```bash
python3 << 'EOF'
import pyaudio
p = pyaudio.PyAudio()
print("=" * 60)
print("Input Devices:")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0:
        print(f"  [{i}] {info['name']}")
print("\nOutput Devices:")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info["maxOutputChannels"] > 0:
        print(f"  [{i}] {info['name']}")
print("=" * 60)
p.terminate()
EOF
```

#### 4.2 Note Down Device Names

Find your radio audio device, for example:
- Input: `USB Audio CODEC`
- Output: `USB Audio CODEC`

#### 4.3 Edit Configuration File

```bash
# Copy example configuration
cp MRRC.conf.example MRRC.conf

# Edit configuration
nano MRRC.conf
```

Modify the `[AUDIO]` section:
```ini
[AUDIO]
outputdevice = USB Audio CODEC
inputdevice = USB Audio CODEC
```

### Step 5: Configure Radio Connection

#### 5.1 Find Serial Port Devices

```bash
# List all serial ports
ls -la /dev/cu.* /dev/tty.*

# Or find specific device
ls -la /dev/cu.usbserial-*
```

#### 5.2 Determine Radio Model Code

```bash
# View supported radio list
rigctl -l | grep -i "icom"
```

Common radio model codes:
- Icom IC-7300: `3073`
- Icom IC-7100: `3070`
- Icom IC-M710: `3073` (marine)
- Icom IC-R9000: `30003`

#### 5.3 Edit Radio Configuration

```ini
[HAMLIB]
rig_pathname = /dev/cu.usbserial-230
rig_model = 3073
rig_rate = 4800
stop_bits = 2
```

### Step 6: Start rigctld

```bash
# Run in foreground (for testing)
rigctld -m 3073 -r /dev/cu.usbserial-230 -s 4800 -C stop_bits=2

# Run in background (production)
./mrrc_control.sh start-rigctld
```

### Step 7: Start MRRC

```bash
# Run in foreground (for debugging)
python3 MRRC

# Or run in background
./mrrc_control.sh start-mrrc
```

### Step 8: Configure as System Service (Optional)

```bash
# Use installation script to configure launchd service
./mrrc_setup.sh install

# Start service
launchctl start com.user.mrrc

# View status
launchctl list | grep mrrc
```

---

## Linux Detailed Installation

### Step 1: Update System

```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL/Fedora
sudo yum update -y
# or
sudo dnf update -y
```

### Step 2: Install System Dependencies

#### Ubuntu/Debian

```bash
sudo apt install -y \
    python3 python3-pip python3-dev \
    libhamlib-utils libhamlib-dev \
    portaudio19-dev \
    git \
    build-essential \
    libasound2-dev \
    libffi-dev \
    libssl-dev
```

#### CentOS/RHEL/Fedora

```bash
# CentOS 8+/RHEL 8+/Fedora
sudo dnf install -y \
    python3 python3-pip python3-devel \
    hamlib hamlib-devel \
    portaudio-devel \
    git \
    gcc make \
    alsa-lib-devel \
    libffi-devel \
    openssl-devel

# For CentOS 7, you may need to enable EPEL
sudo yum install -y epel-release
sudo yum install -y python3 python3-pip hamlib hamlib-devel portaudio-devel git
```

### Step 3: Install Python Dependencies

```bash
pip3 install --user tornado numpy pyaudio opuslib pyserial

# If using RTL-SDR
pip3 install --user pyrtlsdr

# If using WDSP
pip3 install --user cffi
```

### Step 4: Configure Audio Devices

#### 4.1 Find Audio Devices

```bash
python3 << 'EOF'
import pyaudio
p = pyaudio.PyAudio()
print("=" * 60)
print("Input Devices:")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0:
        print(f"  [{i}] {info['name']}")
print("\nOutput Devices:")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info["maxOutputChannels"] > 0:
        print(f"  [{i}] {info['name']}")
print("=" * 60)
p.terminate()
EOF
```

#### 4.2 Configure ALSA (if needed)

```bash
# View ALSA devices
aplay -l
arecord -l

# Edit ALSA configuration (if needed)
sudo nano /etc/asound.conf
```

### Step 5: Configure Radio Connection

#### 5.1 Find Serial Port Devices

```bash
# List all serial ports
ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

# Or use dmesg to view newly connected devices
dmesg | grep tty

# Set permissions for serial port (temporary)
sudo chmod 666 /dev/ttyUSB0

# Permanent permission setup: create udev rule
echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="1234", ATTRS{idProduct}=="5678", MODE="0666"' | sudo tee /etc/udev/rules.d/99-radio.rules
sudo udevadm control --reload-rules
```

#### 5.2 Edit Configuration File

```bash
cp MRRC.conf.example MRRC.conf
nano MRRC.conf
```

Linux configuration example:
```ini
[HAMLIB]
rig_pathname = /dev/ttyUSB0
rig_model = 3073
rig_rate = 4800
stop_bits = 2
```

### Step 6: Start Services

```bash
# Start rigctld
rigctld -m 3073 -r /dev/ttyUSB0 -s 4800 -C stop_bits=2 &

# Start MRRC
python3 MRRC
```

### Step 7: Configure systemd Service (Optional)

Create service file:

```bash
sudo tee /etc/systemd/system/mrrc.service << 'EOF'
[Unit]
Description=MRRC Radio Control Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/UHRR_mac
ExecStart=/usr/bin/python3 /home/pi/UHRR_mac/MRRC
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable mrrc

# Start service
sudo systemctl start mrrc

# View status
sudo systemctl status mrrc

# View logs
sudo journalctl -u mrrc -f
```

---

## WDSP Library Compilation and Installation

WDSP provides professional amateur radio DSP processing, including NR2 spectral noise reduction, NB noise suppression, ANF auto-notch, and other features.

### macOS Compilation and Installation

```bash
# Clone WDSP repository
cd /tmp
git clone https://github.com/g0orx/wdsp.git
cd wdsp

# Compile
make clean
make

# Install to system library
sudo cp libwdsp.dylib /usr/local/lib/
sudo ln -sf /usr/local/lib/libwdsp.dylib /usr/local/lib/libwdsp.so

# Update library cache (if needed)
sudo update_dyld_shared_cache
```

### Linux Compilation and Installation

```bash
# Clone WDSP repository
cd /tmp
git clone https://github.com/g0orx/wdsp.git
cd wdsp

# Compile
make clean
make

# Install to system library
sudo cp libwdsp.so /usr/local/lib/
sudo ldconfig

# Verify installation
ls -la /usr/local/lib/libwdsp*
```

### Verify WDSP Installation

```bash
python3 -c "
import ctypes
try:
    lib = ctypes.CDLL('/usr/local/lib/libwdsp.dylib')  # macOS
    # lib = ctypes.CDLL('/usr/local/lib/libwdsp.so')     # Linux
    print('✅ WDSP library loaded successfully')
except Exception as e:
    print(f'❌ WDSP library failed to load: {e}')
"
```

---

## Configuration File Details

### MRRC.conf Main Configuration Items

```ini
[SERVER]
# Web service port
port = 8877

# TLS certificate path (for HTTPS)
certfile = certs/radio.vlsc.net.pem
keyfile = certs/radio.vlsc.net.key

# Authentication method: FILE or PAM
auth = FILE

# User database path (FILE mode)
db_users_file = MRRC_users.db

# Cookie secret (auto-generated, do not modify manually)
cookie_secret = xxxxx

# Debug mode
debug = False

[CTRL]
# S-meter update interval (seconds)
interval_smeter_update = 5.0

[AUDIO]
# Output device name (radio audio input)
outputdevice = USB Audio CODEC

# Input device name (radio audio output)
inputdevice = USB Audio CODEC

[HAMLIB]
# Radio serial port device path
# macOS: /dev/cu.usbserial-xxx
# Linux: /dev/ttyUSB0 or /dev/ttyACM0
rig_pathname = /dev/cu.usbserial-230

# Radio model code (use rigctl -l to query)
rig_model = 3073

# Serial port baud rate
rig_rate = 4800

# Stop bits (most radios use 2)
stop_bits = 2

# Auto power on radio
trxautopower = True

[WDSP]
# Enable WDSP processing
enabled = True

# Sample rate: 16000 or 48000
sample_rate = 48000

# NR2 spectral noise reduction switch
nr2_enabled = True

# NR2 strength level: 0-4 (0=off, 1=ultra gentle, 2=gentle, 3=medium, 4=strong)
nr2_level = 1

# Noise blanker
nb_enabled = True

# Auto notch filter
anf_enabled = True

# AGC mode: 0=off, 1=long, 2=slow, 3=medium, 4=fast
agc_mode = 2
```

---

## Multi-Instance Configuration

MRRC supports running multiple independent radio instances on a single server, each with its own configuration, ports, logs, and antenna tuner learning data.

### Use Cases

- **Multiple Radio Control**: Control multiple radios simultaneously (e.g., HF + VHF)
- **Primary/Backup Switching**: Quickly switch to backup radio when primary fails
- **Independent Bands**: Different bands using different antenna systems
- **Multi-User Sharing**: Different operators using different radios

### Multi-Instance Script `mrrc_multi.sh`

MRRC provides a dedicated multi-instance management script for unified startup, shutdown, and monitoring of multiple instances.

#### Script Features

| Command | Description | Example |
|---------|-------------|---------|
| `create <name>` | Create new instance configuration | `./mrrc_multi.sh create radio1` |
| `start <name>` | Start specified instance | `./mrrc_multi.sh start radio1` |
| `stop <name>` | Stop specified instance | `./mrrc_multi.sh stop radio1` |
| `restart <name>` | Restart specified instance | `./mrrc_multi.sh restart radio1` |
| `status [name]` | View instance status | `./mrrc_multi.sh status` or `status radio1` |
| `logs <name> [n]` | View logs | `./mrrc_multi.sh logs radio1 50` |
| `list` | List all instances | `./mrrc_multi.sh list` |
| `delete <name>` | Delete instance | `./mrrc_multi.sh delete radio1` |

### Quick Start (Recommended Method)

#### Step 1: Create First Instance

```bash
# Use script to automatically create configuration
./mrrc_multi.sh create radio1

# Output:
# [radio1] Created config: /path/to/MRRC.radio1.conf
# [radio1] MRRC Port: 8891
# [radio1] Rigctl Port: 4531
```

The script will automatically:
- Copy configuration from `MRRC.conf`
- Assign port numbers (radio1 → 8891, radio2 → 8892...)
- Set rigctld ports (4531, 4532...)
- Add `INSTANCE_SETTINGS` configuration section

#### Step 2: Edit Instance Configuration

```bash
# Edit instance configuration
nano MRRC.radio1.conf
```

Modify the following key configurations:

```ini
[SERVER]
# HTTP port (automatically set by script)
port = 8891

[AUDIO]
# Audio device name (modify according to actual situation)
outputdevice = USB Audio CODEC
inputdevice = USB Audio CODEC

[HAMLIB]
# Radio serial port device (modify according to actual situation)
# macOS: /dev/cu.usbserial-xxx
# Linux: /dev/ttyUSB0
rig_pathname = /dev/cu.usbserial-230

# Radio model code
rig_model = 3073

[INSTANCE_SETTINGS]
# Instance name
INSTANCE_NAME = radio1
# MRRC HTTP port
INSTANCE_PORT = 8891
# Radio serial port device
INSTANCE_RIGCTL_DEVICE = /dev/cu.usbserial-230
# Radio model
INSTANCE_RIGCTL_MODEL = 3073
# rigctld listening port (must be different for each instance)
INSTANCE_RIGCTL_PORT = 4531
# ATR-1000 tuner device IP (if available)
INSTANCE_ATR1000_DEVICE = 192.168.1.63
```

#### Step 3: Start Instance

```bash
# Start instance
./mrrc_multi.sh start radio1

# Example output:
# [radio1] Loaded config: MRRC.radio1.conf
# [radio1] Port: 8891
# [radio1] Rig: /dev/cu.usbserial-230
# [radio1] Audio In: USB Audio CODEC
# [radio1] Starting instance: radio1
# [radio1] Starting rigctld...
# [radio1] Starting MRRC server...
# [radio1] MRRC started (PID: 12345)
# [radio1] Access at: https://localhost:8891
```

#### Step 4: View Status

```bash
# View all instance statuses
./mrrc_multi.sh status

# Example output:
# ========== Instance: radio1 ==========
# [radio1] rigctld: running (PID: 12340)
# [radio1] MRRC: running (PID: 12345)
# [radio1]   URL: https://localhost:8891
# [radio1] ATR-1000: running (PID: 12350)
```

#### Step 5: View Logs

```bash
# View last 20 lines of logs
./mrrc_multi.sh logs radio1

# View last 100 lines of logs
./mrrc_multi.sh logs radio1 100
```

### Create Second Instance

```bash
# Create second instance
./mrrc_multi.sh create radio2

# Edit configuration (modify ports and devices)
nano MRRC.radio2.conf
```

Modify contents:
```ini
[SERVER]
port = 8892  # Different from radio1

[AUDIO]
outputdevice = USB Audio CODEC 2  # Second audio device
inputdevice = USB Audio CODEC 2

[HAMLIB]
rig_pathname = /dev/cu.usbserial-231  # Second radio serial port

[INSTANCE_SETTINGS]
INSTANCE_RIGCTL_PORT = 4532  # Different from radio1
```

Start:
```bash
./mrrc_multi.sh start radio2
```

### Multi-Instance Configuration File Details

#### Configuration File Structure

Each instance configuration file `MRRC.<instance_name>.conf` contains:

1. **Standard MRRC configuration sections**: `[SERVER]`, `[AUDIO]`, `[HAMLIB]`, `[WDSP]`, etc.
2. **Instance-specific configuration section**: `[INSTANCE_SETTINGS]` - used by `mrrc_multi.sh`

#### [INSTANCE_SETTINGS] Configuration Items Explained

```ini
[INSTANCE_SETTINGS]
# Instance identifier name
INSTANCE_NAME = radio1

# MRRC HTTP service port (must be different for each instance)
INSTANCE_PORT = 8891

# Radio serial port device path
INSTANCE_RIGCTL_DEVICE = /dev/cu.usbserial-230

# Hamlib radio model code
INSTANCE_RIGCTL_MODEL = 3073

# Serial port baud rate
INSTANCE_RIGCTL_SPEED = 4800

# Serial port stop bits
INSTANCE_RIGCTL_STOP_BITS = 2

# rigctld listening address
INSTANCE_RIGCTL_HOST = 127.0.0.1

# rigctld listening port (must be different for each instance)
INSTANCE_RIGCTL_PORT = 4531

# Audio input device name
INSTANCE_AUDIO_INPUT = USB Audio CODEC

# Audio output device name
INSTANCE_AUDIO_OUTPUT = USB Audio CODEC

# ATR-1000 tuner device IP address (optional)
INSTANCE_ATR1000_DEVICE = 192.168.1.63

# ATR-1000 WebSocket port
INSTANCE_ATR1000_PORT = 60001

# Log file directory
INSTANCE_LOG_DIR = /path/to/logs

# Unix Socket path (for ATR-1000 communication)
INSTANCE_UNIX_SOCKET = /tmp/mrrc_radio1.sock
```

### Access Multi-Instance

Access via different ports after starting:

| Instance | URL | Description |
|----------|-----|-------------|
| radio1 | `https://your-server:8891/mobile_modern.html` | Primary radio |
| radio2 | `https://your-server:8892/mobile_modern.html` | Backup radio |
| radio3 | `https://your-server:8893/mobile_modern.html` | Third radio |

### Manual Configuration Method (Without Script)

If you prefer manual configuration, you can also directly copy and edit configuration files:

```bash
# Copy main configuration
cp MRRC.conf MRRC.radio1.conf

# Edit configuration
nano MRRC.radio1.conf
```

Key modification items:
```ini
[SERVER]
port = 8891  # Ensure different ports for each instance

[HAMLIB]
rig_pathname = /dev/cu.usbserial-230  # First radio serial port

# Add [INSTANCE_SETTINGS] section (optional, for mrrc_multi.sh)
[INSTANCE_SETTINGS]
INSTANCE_NAME = radio1
INSTANCE_PORT = 8891
INSTANCE_RIGCTL_PORT = 4531
```

Manual startup:
```bash
# Start rigctld (specify different port)
rigctld -m 3073 -r /dev/cu.usbserial-230 -s 4800 -t 4531 &

# Start MRRC (specify configuration file)
python3 MRRC MRRC.radio1.conf &
```

### Multi-Instance Tuner Data

Each instance's tuner learning data is stored independently:

```
atr1000_tuner.json          # Default instance
atr1000_radio1.json         # radio1 instance
atr1000_radio2.json         # radio2 instance
```

Specify via `--instance` parameter when starting `atr1000_proxy.py`:

```bash
python3 atr1000_proxy.py --instance radio1
```

### Troubleshooting

#### Problem: Port Conflict

**Symptom**: "Address already in use" when starting

**Solution**:
```bash
# Check port usage
lsof -i :8891  # macOS
netstat -tlnp | grep 8891  # Linux

# Modify configuration to use other port
nano MRRC.radio1.conf
# Change port = 8893
```

#### Problem: rigctld Conflict

**Symptom**: Multiple instances using the same rigctld

**Solution**:
```bash
# Ensure each instance has different INSTANCE_RIGCTL_PORT
# radio1: 4531
# radio2: 4532
# radio3: 4533
```

#### Problem: Audio Device Conflict

**Symptom**: Two instances using the same audio device causing errors

**Solution**:
- Each instance must use different audio devices
- Or use virtual audio devices (such as BlackHole on macOS)

#### Problem: Insufficient Permissions (Linux)

**Symptom**: Cannot access serial port device

**Solution**:
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER
# Takes effect after re-login
```

---

## TLS/SSL Certificate Configuration

### Using Let's Encrypt Certificates (Recommended)

```bash
# Install certbot
# macOS
brew install certbot

# Ubuntu/Debian
sudo apt install certbot

# Apply for certificate (requires domain pointing to server)
sudo certbot certonly --standalone -d radio.yourdomain.com

# Copy certificate to project directory
sudo cp /etc/letsencrypt/live/radio.yourdomain.com/fullchain.pem certs/
sudo cp /etc/letsencrypt/live/radio.yourdomain.com/privkey.pem certs/radio.yourdomain.com.key
sudo chmod 644 certs/*

# Auto-renewal (add to crontab)
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && cp /etc/letsencrypt/live/radio.yourdomain.com/*.pem /path/to/mrrc/certs/") | crontab -
```

### Using Self-Signed Certificates (For Testing)

```bash
# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout certs/selfsigned.key \
    -out certs/selfsigned.pem \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# Update configuration
nano MRRC.conf
# Modify:
# certfile = certs/selfsigned.pem
# keyfile = certs/selfsigned.key
```

⚠️ **Note**: Self-signed certificates will show security warnings in browsers, you need to add exceptions manually.

### Running Without TLS (Local Testing Only)

```bash
# Edit MRRC, comment out TLS-related lines
# Near the beginning of the file, find and comment:
# ssl_options={
#     "certfile": config.get("SERVER", "certfile"),
#     "keyfile": config.get("SERVER", "keyfile"),
# }

# Use http_server instead of http_server_ssl
```

---

## Service Management

MRRC provides `mrrc_control.sh` script for daily service management, and `mrrc_setup.sh` for system service configuration.

### Control Script `mrrc_control.sh`

`mrrc_control.sh` is the main tool for daily MRRC service management, suitable for development and testing environments.

#### Basic Usage

```bash
./mrrc_control.sh <command> [parameters]
```

#### Available Commands

| Command | Description | Example |
|---------|-------------|---------|
| `start` | Start all services | `./mrrc_control.sh start` |
| `stop` | Stop all services | `./mrrc_control.sh stop` |
| `restart` | Restart all services | `./mrrc_control.sh restart` |
| `status` | View service status | `./mrrc_control.sh status` |
| `logs [n]` | View logs (last n lines) | `./mrrc_control.sh logs 50` |
| `start-rigctld` | Start rigctld only | `./mrrc_control.sh start-rigctld` |
| `stop-rigctld` | Stop rigctld only | `./mrrc_control.sh stop-rigctld` |
| `start-mrrc` | Start MRRC only | `./mrrc_control.sh start-mrrc` |
| `stop-mrrc` | Stop MRRC only | `./mrrc_control.sh stop-mrrc` |
| `start-atr1000` | Start ATR-1000 proxy only | `./mrrc_control.sh start-atr1000` |
| `stop-atr1000` | Stop ATR-1000 proxy only | `./mrrc_control.sh stop-atr1000` |

#### Usage Examples

**Start all services**:
```bash
./mrrc_control.sh start

# Example output:
# [INFO] 2026-03-15 14:30:00 - Starting MRRC service...
# [INFO] 2026-03-15 14:30:00 - Starting rigctld...
# [SUCCESS] 2026-03-15 14:30:03 - rigctld started (PID: 12340)
# [INFO] 2026-03-15 14:30:03 - Starting MRRC...
# [SUCCESS] 2026-03-15 14:30:05 - MRRC started (PID: 12345)
# [INFO] 2026-03-15 14:30:05 - MRRC service startup complete
# [SUCCESS] 2026-03-15 14:30:05 - MRRC running, access at: https://localhost:8877
```

**View status**:
```bash
./mrrc_control.sh status

# Example output:
# [INFO] 2026-03-15 14:30:10 - Checking MRRC service status...
# rigctld: running (PID: 12340)
# MRRC: running (PID: 12345)
# ATR-1000: running (PID: 12350)
```

**View logs**:
```bash
# View last 20 lines (default)
./mrrc_control.sh logs

# View last 100 lines
./mrrc_control.sh logs 100
```

**Control services individually** (for debugging):
```bash
# Start rigctld only (for debugging)
./mrrc_control.sh start-rigctld

# Start MRRC only
./mrrc_control.sh start-mrrc

# Stop and restart MRRC individually
./mrrc_control.sh stop-mrrc
./mrrc_control.sh start-mrrc
```

### System Service Configuration (Production Environment)

For long-running production environments, it is recommended to configure as a system service.

#### macOS (launchd)

Use `mrrc_setup.sh` script to configure system service:

```bash
# Install and configure launchd service
./mrrc_setup.sh install

# After service installation:
# 1. Copy plist file to ~/Library/LaunchAgents/
# 2. Set correct paths and working directory
# 3. Load service configuration

# Start service
launchctl start com.user.mrrc

# Stop service
launchctl stop com.user.mrrc

# View status
launchctl list | grep mrrc

# View logs
tail -f ~/Library/Logs/mrrc.log

# Uninstall service
launchctl unload ~/Library/LaunchAgents/com.user.mrrc.plist
rm ~/Library/LaunchAgents/com.user.mrrc.plist
```

**launchd Service Features**:
- Auto-start after user login
- Auto-restart after crash (if KeepAlive is configured)
- Suitable for macOS servers or always-on Macs

#### Linux (systemd)

Create systemd service file:

```bash
# Create service file
sudo tee /etc/systemd/system/mrrc.service << 'EOF'
[Unit]
Description=MRRC Radio Control Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/UHRR_mac
ExecStart=/usr/bin/python3 /home/pi/UHRR_mac/MRRC
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

# Start service
sudo systemctl start mrrc

# Stop service
sudo systemctl stop mrrc

# Restart service
sudo systemctl restart mrrc

# View status
sudo systemctl status mrrc

# View logs
sudo journalctl -u mrrc -f

# Auto-start on boot
sudo systemctl enable mrrc
```

**systemd Service Features**:
- Auto-start on system boot
- Auto-restart after crash
- Complete log management (journalctl)
- Suitable for Linux servers

### Service Management Comparison

| Management Method | Use Case | Auto-Restart | Auto-Boot |
|-------------------|----------|--------------|-----------|
| `mrrc_control.sh` | Development/Testing | ❌ | ❌ |
| macOS launchd | macOS Server | ✅ | ✅ (User Login) |
| Linux systemd | Linux Server | ✅ | ✅ (System Boot) |
| `mrrc_multi.sh` | Multi-Instance | ❌ | ❌ |

### Log File Locations

Log storage locations for different startup methods:

**Started with `mrrc_control.sh`**:
- rigctld logs: `/tmp/rigctld.log`
- MRRC logs: `MRRC.log` (project directory)
- ATR-1000 logs: `atr1000_proxy.log`

**launchd service**:
- Logs: `~/Library/Logs/mrrc.log`

**systemd service**:
- Logs: `sudo journalctl -u mrrc`

**`mrrc_multi.sh` multi-instance**:
- rigctld logs: `rigctld_<instance_name>.log`
- MRRC logs: `mrrc_<instance_name>.log`
- ATR-1000 logs: `atr1000_<instance_name>.log`

---

## Troubleshooting

### 1. rigctld Connection Failed

**Symptom**: MRRC cannot connect to radio, frequency display is empty

**Troubleshooting Steps**:

```bash
# 1. Check if rigctld is running
ps aux | grep rigctld

# 2. Check serial port device
ls -la /dev/cu.usbserial-*  # macOS
ls -la /dev/ttyUSB*         # Linux

# 3. Check serial port permissions (Linux)
ls -la /dev/ttyUSB0
groups  # Confirm user is in dialout group

# 4. Test rigctld manually
rigctl -m 3073 -r /dev/ttyUSB0 -s 4800 f  # Get frequency

# 5. Check rigctld logs
cat /tmp/rigctld.log
```

**Solution**:

```bash
# Linux: Add user to dialout group
sudo usermod -a -G dialout $USER
# Takes effect after re-login

# Start rigctld
rigctld -m 3073 -r /dev/ttyUSB0 -s 4800 -C stop_bits=2 -vvvv
```

### 2. Audio Device Not Found

**Symptom**: Error "Audio device not found"

**Troubleshooting Steps**:

```bash
# 1. Check device connection
system_profiler SPUSBDataType | grep -A5 "Audio"  # macOS
lsusb | grep Audio                                # Linux

# 2. Check PyAudio device list
python3 << 'EOF'
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print(f"{i}: {info['name']}")
p.terminate()
EOF

# 3. Check device names in configuration file
# Ensure MRRC.conf device names match exactly with the output above
```

**Solution**:

```bash
# Modify device names in MRRC.conf
nano MRRC.conf

[AUDIO]
# Ensure names match PyAudio output exactly
outputdevice = USB Audio CODEC
inputdevice = USB Audio CODEC
```

### 3. WDSP Library Load Failed

**Symptom**: Log shows "WDSP library not available"

**Troubleshooting Steps**:

```bash
# 1. Check if library file exists
ls -la /usr/local/lib/libwdsp*

# 2. Check library loading
python3 -c "import ctypes; ctypes.CDLL('/usr/local/lib/libwdsp.dylib')"  # macOS
python3 -c "import ctypes; ctypes.CDLL('/usr/local/lib/libwdsp.so')"      # Linux

# 3. Check library path
# macOS
otool -L /usr/local/lib/libwdsp.dylib

# Linux
ldd /usr/local/lib/libwdsp.so
```

**Solution**:

```bash
# macOS
sudo cp /tmp/wdsp/libwdsp.dylib /usr/local/lib/

# Linux
sudo cp /tmp/wdsp/libwdsp.so /usr/local/lib/
sudo ldconfig
```

### 4. WebSocket Connection Failed

**Symptom**: Browser shows "Connection disconnected" or cannot load page

**Troubleshooting Steps**:

```bash
# 1. Check if MRRC is running
ps aux | grep "python3 MRRC"

# 2. Check if port is listening
lsof -i :8877  # macOS
netstat -tlnp | grep 8877  # Linux

# 3. Check firewall
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-ports  # CentOS

# 4. Check certificates
openssl x509 -in certs/radio.vlsc.net.pem -text -noout
```

**Solution**:

```bash
# Open firewall port (if needed)
# Ubuntu/Debian
sudo ufw allow 8877/tcp

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=8877/tcp
sudo firewall-cmd --reload
```

### 5. TLS/SSL Certificate Error

**Symptom**: Browser shows "Your connection is not private"

**Troubleshooting Steps**:

```bash
# 1. Check certificate files
ls -la certs/

# 2. Verify certificate format
openssl x509 -in certs/radio.vlsc.net.pem -text -noout

# 3. Check if certificate and key match
openssl x509 -noout -modulus -in certs/radio.vlsc.net.pem | openssl md5
openssl rsa -noout -modulus -in certs/radio.vlsc.net.key | openssl md5
```

**Solution**:

```bash
# If certificate doesn't match, regenerate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout certs/selfsigned.key \
    -out certs/selfsigned.pem \
    -subj "/CN=localhost"

# Update configuration to use new certificate
```

### 6. ATR-1000 Tuner Connection Failed

**Symptom**: Power/SWR not displayed

**Troubleshooting Steps**:

```bash
# 1. Check if ATR-1000 proxy is running
ps aux | grep atr1000_proxy

# 2. Check network connection
ping 192.168.1.63  # ATR-1000 default IP

# 3. Check logs
tail -f atr1000_proxy.log

# 4. Check Unix Socket
ls -la /tmp/atr1000_proxy.sock
```

**Solution**:

```bash
# Manually start ATR-1000 proxy
python3 atr1000_proxy.py --device 192.168.1.63 --port 60001 &

# Or use control script
./mrrc_control.sh start-atr1000
```

---

## FAQ

### Q1: Which radios are supported?

**A**: MRRC supports over 200 amateur radios through Hamlib. Common supported radios include:
- Icom: IC-7300, IC-7100, IC-7610, IC-7850, IC-9700, IC-M710, etc.
- Yaesu: FT-991A, FTDX-101D, FTDX-10, etc.
- Kenwood: TS-590S, TS-890S, etc.

Use `rigctl -l | grep -i "brand name"` to query specific model codes.

### Q2: Can it run on Windows?

**A**: Currently primarily supports macOS and Linux. Windows users can use WSL2 (Windows Subsystem for Linux) to run.

### Q3: How to achieve external network access?

**A**: Recommended solutions:
1. **VPN**: Safest, use WireGuard or OpenVPN
2. **Intranet Penetration**: Use frp, ngrok, etc.
3. **Port Forwarding**: Configure port forwarding on router (requires public IP)
4. **Reverse Proxy**: Use Nginx + SSL

⚠️ **Warning**: Direct exposure to the internet has security risks, be sure to enable authentication and TLS.

### Q4: Will multiple users conflict when controlling simultaneously?

**A**: MRRC supports multiple users connecting simultaneously, but note:
- Only one user can transmit (PTT interlock)
- Frequency settings will sync to all users
- Recommend operators take turns using PTT

### Q5: Audio has delay/stuttering, what should I do?

**A**: Troubleshooting steps:
1. Check network latency: `ping your-server`
2. Reduce WDSP processing intensity
3. Adjust RX buffer size
4. Use wired network connection
5. Close other bandwidth-consuming applications

### Q6: How to update MRRC?

**A**:
```bash
# Backup configuration
cp MRRC.conf MRRC.conf.backup

# Pull updates
git pull origin main

# Restore configuration
cp MRRC.conf.backup MRRC.conf

# Restart service
./mrrc_control.sh restart
```

### Q7: How to debug problems?

**A**:
1. Enable debug mode: Set `debug = True` in `MRRC.conf`
2. View logs: `./mrrc_control.sh logs` or `tail -f MRRC.log`
3. Browser developer tools: F12 → Console/Network
4. Use testing tools: `dev_tools/test_connection.html`

### Q8: What are the browser requirements for mobile?

**A**:
- **iOS**: Safari 14+ (recommended), Chrome, Firefox
- **Android**: Chrome 90+, Firefox, Samsung Internet
- **Required features**: Web Audio API, WebSocket, ES6

### Q9: What's the difference between WDSP and RNNoise?

**A**:
| Feature | WDSP | RNNoise |
|---------|------|---------|
| Algorithm | Spectral Subtraction | Neural Network |
| Optimization | SSB voice optimized | General voice |
| Latency | <20ms | 30-50ms |
| Quality | Better | Average |
| Resources | Low | Higher |

**Recommendation**: Use WDSP's NR2 feature, enabled by default.

### Q10: How to backup tuner learning data?

**A**:
```bash
# Backup
cp atr1000_tuner.json atr1000_tuner.json.backup

# Restore
cp atr1000_tuner.json.backup atr1000_tuner.json

# Multi-instance backup
cp atr1000_radio1.json atr1000_radio1.json.backup
```

---

## Getting Help

- **GitHub Issues**: https://github.com/cheenle/UHRR_mac/issues
- **Documentation**: See `docs/` directory
- **Logs**: `./mrrc_control.sh logs`

---

**Last Updated**: 2026-03-15
**Document Version**: V4.9.2

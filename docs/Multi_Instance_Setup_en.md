# MRRC Multi-Instance Configuration Guide

**Document Version**: V1.0 (2026-03-15)  
**Corresponding MRRC Version**: V4.9.1

## Overview

MRRC supports running multiple independent instances on the same server, each instance can:
- Connect to different radio devices (different serial ports/models)
- Use different audio devices (different sound cards)
- Independent antenna tuner parameter learning (each instance has its own learning records)
- Independent web service port

**Typical Use Cases**:
- One server controlling multiple radios (main radio + backup radio)
- Different antenna tuner parameters for different bands
- Personal radio + club shared radio

---

## Quick Start

### 1. Create New Instance Configuration

```bash
# Use multi-instance management script to create
cd /Users/cheenle/UHRR/MRRC
./mrrc_multi.sh create radio2
```

### 2. Edit Instance Configuration

```bash
# Edit configuration file
vim MRRC.radio2.conf
```

Key configuration items:
```ini
[INSTANCE_SETTINGS]
instance_name = radio2
instance_port = 8892                          # Web service port, must be unique
instance_rigctl_port = 4532                   # rigctld port, must be unique
instance_unix_socket = /tmp/mrrc_radio2.sock  # Unix Socket path, must be unique
instance_atr1000_device = 192.168.1.64        # ATR-1000 device IP
```

### 3. Start Instance

```bash
./mrrc_multi.sh start radio2
```

---

## Detailed Configuration Instructions

### Directory Structure

```
MRRC/
├── MRRC                      # Main program (supports multi-instance)
├── MRRC.conf                 # Default configuration (single instance mode)
├── MRRC.radio1.conf          # Instance 1 configuration
├── MRRC.radio2.conf          # Instance 2 configuration
├── mrrc_multi.sh             # Multi-instance management script
└── docs/
    └── Multi_Instance_Setup.md  # This document
```

### Configuration Parameters Detailed

#### [INSTANCE_SETTINGS] Section

| Parameter | Description | Example |
|-----------|-------------|---------|
| `instance_name` | Instance name for log identification | `radio2` |
| `instance_port` | Web service port, must be unique | `8892` |
| `instance_rigctl_port` | rigctld control port, must be unique | `4532` |
| `instance_rigctl_device` | Radio serial device | `/dev/tty.usbserial-ABAUOK9F` |
| `instance_rigctl_model` | Radio model number | `6006` |
| `instance_audio_input` | Audio input device | `USB PnP Sound Device` |
| `instance_audio_output` | Audio output device | `USB PnP Sound Device` |
| `instance_atr1000_device` | ATR-1000 device IP | `192.168.1.63` |
| `instance_atr1000_port` | ATR-1000 port | `60001` |
| `instance_unix_socket` | Unix Socket path, must be unique | `/tmp/mrrc_radio2.sock` |
| `instance_log_dir` | Log directory | `/Users/cheenle/UHRR/MRRC` |

### Port Allocation Principle

Each instance requires independent ports:

| Instance | Web Port | rigctld Port | Unix Socket |
|----------|----------|--------------|-------------|
| radio1 | 8891 | 4531 | /tmp/mrrc_radio1.sock |
| radio2 | 8892 | 4532 | /tmp/mrrc_radio2.sock |
| radio3 | 8893 | 4533 | /tmp/mrrc_radio3.sock |

**Important**: Port conflicts will cause instance startup failure!

---

## Management Commands

### mrrc_multi.sh Script

```bash
# View help
./mrrc_multi.sh help

# Create new instance (copy from default config)
./mrrc_multi.sh create <instance_name>

# Start instance
./mrrc_multi.sh start <instance_name>

# Stop instance
./mrrc_multi.sh stop <instance_name>

# Restart instance
./mrrc_multi.sh restart <instance_name>

# View status
./mrrc_multi.sh status <instance_name>

# View logs
./mrrc_multi.sh logs <instance_name> [lines]

# Delete instance
./mrrc_multi.sh delete <instance_name>

# List all instances
./mrrc_multi.sh list
```

### Manual Management

```bash
# Start single component
./mrrc_multi.sh start-rigctld radio2
./mrrc_multi.sh start-mrrc radio2
./mrrc_multi.sh start-atr1000 radio2

# Stop single component
./mrrc_multi.sh stop-rigctld radio2
./mrrc_multi.sh stop-mrrc radio2
./mrrc_multi.sh stop-atr1000 radio2
```

---

## Complete Configuration Example

### Instance 1: IC-M710 (radio1)

```ini
# MRRC.radio1.conf
[SERVER]
port = 8891
certfile = certs/radio.vlsc.net.pem
keyfile = certs/radio.vlsc.net.key
auth = FILE

[AUDIO]
outputdevice = USB Audio CODEC
inputdevice = USB Audio CODEC

[HAMLIB]
rig_pathname = /dev/cu.usbserial-120
rig_model = 30003
rig_rate = 4800
stop_bits = 2

[INSTANCE_SETTINGS]
instance_name = radio1
instance_port = 8891
instance_rigctl_device = /dev/cu.usbserial-120
instance_rigctl_model = 30003
instance_rigctl_speed = 4800
instance_rigctl_stop_bits = 2
instance_rigctl_host = 127.0.0.1
instance_rigctl_port = 4531
instance_audio_input = USB Audio CODEC
instance_audio_output = USB Audio CODEC
instance_atr1000_device = 192.168.1.63
instance_atr1000_port = 60001
instance_unix_socket = /tmp/mrrc_radio1.sock
```

### Instance 2: JRC NRD-535D (radio2)

```ini
# MRRC.radio2.conf
[SERVER]
port = 8892
certfile = certs/radio.vlsc.net.pem
keyfile = certs/radio.vlsc.net.key
auth = FILE

[AUDIO]
outputdevice = USB PnP Sound Device
inputdevice = USB PnP Sound Device

[HAMLIB]
rig_pathname = /dev/tty.usbserial-ABAUOK9F
rig_model = 6006
rig_rate = 4800
stop_bits = 1

[INSTANCE_SETTINGS]
instance_name = radio2
instance_port = 8892
instance_rigctl_device = /dev/tty.usbserial-ABAUOK9F
instance_rigctl_model = 6006
instance_rigctl_speed = 4800
instance_rigctl_stop_bits = 1
instance_rigctl_host = 127.0.0.1
instance_rigctl_port = 4532
instance_audio_input = USB PnP Sound Device
instance_audio_output = USB PnP Sound Device
instance_atr1000_device = 192.168.1.63
instance_atr1000_port = 60001
instance_unix_socket = /tmp/mrrc_radio2.sock
```

---

## Access Addresses

After starting instances, access via the following addresses:

| Instance | Address |
|----------|---------|
| radio1 | https://localhost:8891/mobile_modern.html |
| radio2 | https://localhost:8892/mobile_modern.html |

If using domain names:
- https://radio1.vlsc.net:8891/mobile_modern.html
- https://radio2.vlsc.net:8892/mobile_modern.html

---

## Troubleshooting

### 1. Port Conflict

**Symptom**: `Address already in use` error

**Solution**:
```bash
# Check port usage
lsof -i :8892
lsof -i :4532

# Modify configuration to use other ports
vim MRRC.radio2.conf
# Modify instance_port and instance_rigctl_port
```

### 2. ATR-1000 Connection Failed

**Symptom**: Log shows `No such file or directory`

**Troubleshooting**:
```bash
# Check if Socket file exists
ls -la /tmp/mrrc_radio2.sock

# Check ATR-1000 proxy log
tail -20 atr1000_radio2.log

# Restart instance
./mrrc_multi.sh restart radio2
```

### 3. Serial Device Not Exists

**Symptom**: `rigctld failed to start`

**Troubleshooting**:
```bash
# List available serial ports
ls /dev/cu.* /dev/tty.*

# Update device path in configuration
vim MRRC.radio2.conf
```

### 4. Frequency Not Syncing

**Symptom**: Antenna tuner parameters don't change with frequency

**Troubleshooting**:
```bash
# Check frequency sync records in MRRC log
grep "频率同步" mrrc_radio2.log

# Check if ATR-1000 proxy received frequency
grep "set_freq" atr1000_radio2.log
```

---

## Advanced Configuration

### Independent Antenna Tuner Storage

Each instance uses independent Unix Socket, so antenna tuner learning records are independent:

- radio1: Learning records stored in `atr1000_tuner.json` (via `/tmp/mrrc_radio1.sock`)
- radio2: Learning records stored in `atr1000_tuner.json` (via `/tmp/mrrc_radio2.sock`)

**Note**: Although file names are the same, proxy processes are independent and data won't conflict.

### Shared ATR-1000 Device

If multiple instances use the same ATR-1000 device (e.g., 192.168.1.63 in this example):

1. Each instance learns its own parameters independently
2. Parameters are applied automatically without interference
3. Recommended to configure different antennas for different radios on the ATR-1000 device

### System Service Configuration

Create system service for auto-start on boot:

```bash
# Create service for radio1
./mrrc_multi.sh enable-service radio1

# Create service for radio2
./mrrc_multi.sh enable-service radio2
```

Or use launchd (macOS):

```xml
<!-- com.user.mrrc.radio1.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.mrrc.radio1</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/cheenle/UHRR/MRRC/mrrc_multi.sh</string>
        <string>start</string>
        <string>radio1</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

---

## Performance Optimization

### Multi-Instance Resource Usage

Resource usage per instance:

| Component | CPU | Memory |
|-----------|-----|--------|
| rigctld | ~1% | ~10MB |
| MRRC | ~5-15% | ~50-100MB |
| ATR-1000 Proxy | ~1% | ~20MB |

**Recommendation**: A typical PC can stably run 3-5 instances.

### Log Management

Multi-instance generates multiple log files:

```bash
# Periodic log cleanup
./mrrc_multi.sh cleanup-logs

# Or manual cleanup
rm -f mrrc_radio*.log.* atr1000_radio*.log.*
```

---

## Security Considerations

### Network Isolation

- Each instance uses independent WebSocket port
- Recommended to configure independent TLS certificates for each instance
- Can use reverse proxy (nginx) for unified entry management

### Authentication Sharing

Multiple instances can share the same user database:

```ini
[SERVER]
db_users_file = MRRC_users.db  # All instances use the same auth file
```

---

## Changelog

- **2024-03-15**: Initial multi-instance support document
- Support for `mrrc_multi.sh` management script
- Independent Unix Socket path configuration
- Automated instance creation and deletion

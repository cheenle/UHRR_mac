# MRRC 安装配置完全指南

## 📋 目录

1. [系统要求](#系统要求)
2. [快速开始](#快速开始)
3. [macOS 详细安装](#macos-详细安装)
4. [Linux 详细安装](#linux-详细安装)
5. [WDSP 库编译安装](#wdsp-库编译安装)
6. [配置文件详解](#配置文件详解)
7. [多实例配置](#多实例配置)
8. [TLS/SSL 证书配置](#tlsssl-证书配置)
9. [服务管理](#服务管理)
10. [故障排查](#故障排查)
11. [常见问题 Q&A](#常见问题-qa)

---

## 系统要求

### 最低配置
- **CPU**: ARM64 (Apple Silicon) 或 x86_64, 2核以上
- **内存**: 2GB RAM
- **存储**: 1GB 可用空间
- **网络**: 稳定的互联网连接（用于远程访问）

### 推荐配置
- **CPU**: Apple M1/M2/M3 或 4核以上 x86_64
- **内存**: 4GB RAM
- **存储**: 2GB 可用空间
- **网络**: 有线网络或稳定的 Wi-Fi

### 操作系统支持
- **macOS**: 12.0+ (Monterey 及以上)
- **Linux**: Ubuntu 20.04+, Debian 11+, CentOS 8+
- **Python**: 3.9+ (推荐 3.12)

---

## 快速开始

### 一键安装 (macOS)

```bash
# 克隆仓库
git clone https://github.com/cheenle/UHRR_mac.git
cd UHRR_mac

# 运行安装脚本
./mrrc_setup.sh install
```

### 一键安装 (Linux)

```bash
# 克隆仓库
git clone https://github.com/cheenle/UHRR_mac.git
cd UHRR_mac

# 安装依赖并配置
sudo ./install_linux.sh
```

---

## macOS 详细安装

### 步骤 1: 安装 Homebrew

如果尚未安装 Homebrew：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 步骤 2: 安装系统依赖

```bash
# 基础依赖
brew install python@3.12
brew install hamlib
brew install portaudio
brew install git

# 可选：WDSP DSP库（推荐安装以获得最佳降噪效果）
# 详见 [WDSP 库编译安装](#wdsp-库编译安装) 章节
```

### 步骤 3: 安装 Python 依赖

```bash
# 使用 pip3 安装 Python 包
pip3 install tornado numpy pyaudio pyrtlsdr opuslib pyserial

# 如果使用 WDSP（推荐）
pip3 install cffi

# 如果使用 RTL-SDR（频谱功能）
pip3 install pyrtlsdr
```

### 步骤 4: 配置音频设备

#### 4.1 查找音频设备

```bash
python3 << 'EOF'
import pyaudio
p = pyaudio.PyAudio()
print("=" * 60)
print("输入设备:")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0:
        print(f"  [{i}] {info['name']}")
print("\n输出设备:")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info["maxOutputChannels"] > 0:
        print(f"  [{i}] {info['name']}")
print("=" * 60)
p.terminate()
EOF
```

#### 4.2 记录设备名称

找到您的电台音频设备，例如：
- 输入: `USB Audio CODEC`
- 输出: `USB Audio CODEC`

#### 4.3 编辑配置文件

```bash
# 复制示例配置
cp MRRC.conf.example MRRC.conf

# 编辑配置
nano MRRC.conf
```

修改 `[AUDIO]` 部分：
```ini
[AUDIO]
outputdevice = USB Audio CODEC
inputdevice = USB Audio CODEC
```

### 步骤 5: 配置电台连接

#### 5.1 查找串口设备

```bash
# 列出所有串口
ls -la /dev/cu.* /dev/tty.*

# 或查找特定设备
ls -la /dev/cu.usbserial-*
```

#### 5.2 确定电台型号代码

```bash
# 查看支持的电台列表
rigctl -l | grep -i "icom"
```

常见电台型号代码：
- Icom IC-7300: `3073`
- Icom IC-7100: `3070`
- Icom IC-M710: `3073` ( marine )
- Icom IC-R9000: `30003`

#### 5.3 编辑电台配置

```ini
[HAMLIB]
rig_pathname = /dev/cu.usbserial-230
rig_model = 3073
rig_rate = 4800
stop_bits = 2
```

### 步骤 6: 启动 rigctld

```bash
# 前台运行（测试用）
rigctld -m 3073 -r /dev/cu.usbserial-230 -s 4800 -C stop_bits=2

# 后台运行（生产环境）
./mrrc_control.sh start-rigctld
```

### 步骤 7: 启动 MRRC

```bash
# 前台运行（调试用）
python3 MRRC

# 或后台运行
./mrrc_control.sh start-mrrc
```

### 步骤 8: 配置为系统服务（可选）

```bash
# 使用安装脚本配置 launchd 服务
./mrrc_setup.sh install

# 启动服务
launchctl start com.user.mrrc

# 查看状态
launchctl list | grep mrrc
```

---

## Linux 详细安装

### 步骤 1: 更新系统

```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL/Fedora
sudo yum update -y
# 或
sudo dnf update -y
```

### 步骤 2: 安装系统依赖

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

# 对于 CentOS 7，可能需要启用 EPEL
sudo yum install -y epel-release
sudo yum install -y python3 python3-pip hamlib hamlib-devel portaudio-devel git
```

### 步骤 3: 安装 Python 依赖

```bash
pip3 install --user tornado numpy pyaudio opuslib pyserial

# 如果使用 RTL-SDR
pip3 install --user pyrtlsdr

# 如果使用 WDSP
pip3 install --user cffi
```

### 步骤 4: 配置音频设备

#### 4.1 查找音频设备

```bash
python3 << 'EOF'
import pyaudio
p = pyaudio.PyAudio()
print("=" * 60)
print("输入设备:")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0:
        print(f"  [{i}] {info['name']}")
print("\n输出设备:")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info["maxOutputChannels"] > 0:
        print(f"  [{i}] {info['name']}")
print("=" * 60)
p.terminate()
EOF
```

#### 4.2 配置 ALSA（如需要）

```bash
# 查看 ALSA 设备
aplay -l
arecord -l

# 编辑 ALSA 配置（如果需要）
sudo nano /etc/asound.conf
```

### 步骤 5: 配置电台连接

#### 5.1 查找串口设备

```bash
# 列出所有串口
ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

# 或使用 dmesg 查看新连接的设备
dmesg | grep tty

# 为串口设置权限（临时）
sudo chmod 666 /dev/ttyUSB0

# 永久设置权限：创建 udev 规则
echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="1234", ATTRS{idProduct}=="5678", MODE="0666"' | sudo tee /etc/udev/rules.d/99-radio.rules
sudo udevadm control --reload-rules
```

#### 5.2 编辑配置文件

```bash
cp MRRC.conf.example MRRC.conf
nano MRRC.conf
```

Linux 配置示例：
```ini
[HAMLIB]
rig_pathname = /dev/ttyUSB0
rig_model = 3073
rig_rate = 4800
stop_bits = 2
```

### 步骤 6: 启动服务

```bash
# 启动 rigctld
rigctld -m 3073 -r /dev/ttyUSB0 -s 4800 -C stop_bits=2 &

# 启动 MRRC
python3 MRRC
```

### 步骤 7: 配置 systemd 服务（可选）

创建服务文件：

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

# 重新加载 systemd
sudo systemctl daemon-reload

# 启用服务
sudo systemctl enable mrrc

# 启动服务
sudo systemctl start mrrc

# 查看状态
sudo systemctl status mrrc

# 查看日志
sudo journalctl -u mrrc -f
```

---

## WDSP 库编译安装

WDSP 提供专业的业余无线电 DSP 处理，包括 NR2 频谱降噪、NB 噪声抑制、ANF 自动陷波等功能。

### macOS 编译安装

```bash
# 克隆 WDSP 仓库
cd /tmp
git clone https://github.com/g0orx/wdsp.git
cd wdsp

# 编译
make clean
make

# 安装到系统库
sudo cp libwdsp.dylib /usr/local/lib/
sudo ln -sf /usr/local/lib/libwdsp.dylib /usr/local/lib/libwdsp.so

# 更新库缓存（如果需要）
sudo update_dyld_shared_cache
```

### Linux 编译安装

```bash
# 克隆 WDSP 仓库
cd /tmp
git clone https://github.com/g0orx/wdsp.git
cd wdsp

# 编译
make clean
make

# 安装到系统库
sudo cp libwdsp.so /usr/local/lib/
sudo ldconfig

# 验证安装
ls -la /usr/local/lib/libwdsp*
```

### 验证 WDSP 安装

```bash
python3 -c "
import ctypes
try:
    lib = ctypes.CDLL('/usr/local/lib/libwdsp.dylib')  # macOS
    # lib = ctypes.CDLL('/usr/local/lib/libwdsp.so')     # Linux
    print('✅ WDSP 库加载成功')
except Exception as e:
    print(f'❌ WDSP 库加载失败: {e}')
"
```

---

## 配置文件详解

### MRRC.conf 主要配置项

```ini
[SERVER]
# Web 服务端口
port = 8877

# TLS 证书路径（用于 HTTPS）
certfile = certs/radio.vlsc.net.pem
keyfile = certs/radio.vlsc.net.key

# 认证方式: FILE 或 PAM
auth = FILE

# 用户数据库路径（FILE 模式）
db_users_file = MRRC_users.db

# Cookie 密钥（自动生成，不要手动修改）
cookie_secret = xxxxx

# 调试模式
debug = False

[CTRL]
# S 表更新间隔（秒）
interval_smeter_update = 5.0

[AUDIO]
# 输出设备名称（电台音频输入）
outputdevice = USB Audio CODEC

# 输入设备名称（电台音频输出）
inputdevice = USB Audio CODEC

[HAMLIB]
# 电台串口设备路径
# macOS: /dev/cu.usbserial-xxx
# Linux: /dev/ttyUSB0 或 /dev/ttyACM0
rig_pathname = /dev/cu.usbserial-230

# 电台型号代码（使用 rigctl -l 查询）
rig_model = 3073

# 串口波特率
rig_rate = 4800

# 停止位（大多数电台使用 2）
stop_bits = 2

# 自动开启电台电源
trxautopower = True

[WDSP]
# 启用 WDSP 处理
enabled = True

# 采样率: 16000 或 48000
sample_rate = 48000

# NR2 频谱降噪开关
nr2_enabled = True

# NR2 强度级别: 0-4 (0=关, 1=极温和, 2=温和, 3=中等, 4=强力)
nr2_level = 1

# 噪声抑制器
nb_enabled = True

# 自动陷波器
anf_enabled = True

# AGC 模式: 0=关, 1=长, 2=慢, 3=中, 4=快
agc_mode = 2
```

---

## 多实例配置

MRRC 支持单服务器运行多个独立电台实例，每个实例有独立的配置、端口、日志和天调学习数据。

### 使用场景

- **多电台控制**: 同时控制多部电台（如 HF + VHF）
- **主备切换**: 主电台故障时快速切换到备用电台
- **多波段独立**: 不同波段使用不同天线系统
- **多人共享**: 不同操作员使用不同电台

### 多实例脚本 `mrrc_multi.sh`

MRRC 提供了专门的多实例管理脚本，可以统一管理多个实例的启动、停止和监控。

#### 脚本功能

| 命令 | 说明 | 示例 |
|------|------|------|
| `create <name>` | 创建新实例配置 | `./mrrc_multi.sh create radio1` |
| `start <name>` | 启动指定实例 | `./mrrc_multi.sh start radio1` |
| `stop <name>` | 停止指定实例 | `./mrrc_multi.sh stop radio1` |
| `restart <name>` | 重启指定实例 | `./mrrc_multi.sh restart radio1` |
| `status [name]` | 查看实例状态 | `./mrrc_multi.sh status` 或 `status radio1` |
| `logs <name> [n]` | 查看日志 | `./mrrc_multi.sh logs radio1 50` |
| `list` | 列出所有实例 | `./mrrc_multi.sh list` |
| `delete <name>` | 删除实例 | `./mrrc_multi.sh delete radio1` |

### 快速开始（推荐方式）

#### 步骤 1: 创建第一个实例

```bash
# 使用脚本自动创建配置
./mrrc_multi.sh create radio1

# 输出：
# [radio1] Created config: /path/to/MRRC.radio1.conf
# [radio1] MRRC Port: 8891
# [radio1] Rigctl Port: 4531
```

脚本会自动：
- 从 `MRRC.conf` 复制配置
- 分配端口号（radio1 → 8891, radio2 → 8892...）
- 设置 rigctld 端口（4531, 4532...）
- 添加 `INSTANCE_SETTINGS` 配置节

#### 步骤 2: 编辑实例配置

```bash
# 编辑实例配置
nano MRRC.radio1.conf
```

修改以下关键配置：

```ini
[SERVER]
# HTTP 端口（脚本已自动设置）
port = 8891

[AUDIO]
# 音频设备名称（根据实际情况修改）
outputdevice = USB Audio CODEC
inputdevice = USB Audio CODEC

[HAMLIB]
# 电台串口设备（根据实际情况修改）
# macOS: /dev/cu.usbserial-xxx
# Linux: /dev/ttyUSB0
rig_pathname = /dev/cu.usbserial-230

# 电台型号代码
rig_model = 3073

[INSTANCE_SETTINGS]
# 实例名称
INSTANCE_NAME = radio1
# MRRC HTTP 端口
INSTANCE_PORT = 8891
# 电台串口设备
INSTANCE_RIGCTL_DEVICE = /dev/cu.usbserial-230
# 电台型号
INSTANCE_RIGCTL_MODEL = 3073
# rigctld 监听端口（每个实例必须不同）
INSTANCE_RIGCTL_PORT = 4531
# ATR-1000 天调设备 IP（如果有）
INSTANCE_ATR1000_DEVICE = 192.168.1.63
```

#### 步骤 3: 启动实例

```bash
# 启动实例
./mrrc_multi.sh start radio1

# 输出示例：
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

#### 步骤 4: 查看状态

```bash
# 查看所有实例状态
./mrrc_multi.sh status

# 输出示例：
# ========== Instance: radio1 ==========
# [radio1] rigctld: running (PID: 12340)
# [radio1] MRRC: running (PID: 12345)
# [radio1]   URL: https://localhost:8891
# [radio1] ATR-1000: running (PID: 12350)
```

#### 步骤 5: 查看日志

```bash
# 查看最后 20 行日志
./mrrc_multi.sh logs radio1

# 查看最后 100 行日志
./mrrc_multi.sh logs radio1 100
```

### 创建第二个实例

```bash
# 创建第二个实例
./mrrc_multi.sh create radio2

# 编辑配置（修改端口和设备）
nano MRRC.radio2.conf
```

修改内容：
```ini
[SERVER]
port = 8892  # 与 radio1 不同

[AUDIO]
outputdevice = USB Audio CODEC 2  # 第二个音频设备
inputdevice = USB Audio CODEC 2

[HAMLIB]
rig_pathname = /dev/cu.usbserial-231  # 第二个电台串口

[INSTANCE_SETTINGS]
INSTANCE_RIGCTL_PORT = 4532  # 与 radio1 不同
```

启动：
```bash
./mrrc_multi.sh start radio2
```

### 多实例配置文件详解

#### 配置文件结构

每个实例配置文件 `MRRC.<实例名>.conf` 包含：

1. **标准 MRRC 配置节**: `[SERVER]`, `[AUDIO]`, `[HAMLIB]`, `[WDSP]` 等
2. **实例特有配置节**: `[INSTANCE_SETTINGS]` - 供 `mrrc_multi.sh` 使用

#### [INSTANCE_SETTINGS] 配置项说明

```ini
[INSTANCE_SETTINGS]
# 实例标识名称
INSTANCE_NAME = radio1

# MRRC HTTP 服务端口（每个实例必须不同）
INSTANCE_PORT = 8891

# 电台串口设备路径
INSTANCE_RIGCTL_DEVICE = /dev/cu.usbserial-230

# Hamlib 电台型号代码
INSTANCE_RIGCTL_MODEL = 3073

# 串口波特率
INSTANCE_RIGCTL_SPEED = 4800

# 串口停止位
INSTANCE_RIGCTL_STOP_BITS = 2

# rigctld 监听地址
INSTANCE_RIGCTL_HOST = 127.0.0.1

# rigctld 监听端口（每个实例必须不同）
INSTANCE_RIGCTL_PORT = 4531

# 音频输入设备名称
INSTANCE_AUDIO_INPUT = USB Audio CODEC

# 音频输出设备名称
INSTANCE_AUDIO_OUTPUT = USB Audio CODEC

# ATR-1000 天调设备 IP 地址（可选）
INSTANCE_ATR1000_DEVICE = 192.168.1.63

# ATR-1000 WebSocket 端口
INSTANCE_ATR1000_PORT = 60001

# 日志文件目录
INSTANCE_LOG_DIR = /path/to/logs

# Unix Socket 路径（用于 ATR-1000 通信）
INSTANCE_UNIX_SOCKET = /tmp/mrrc_radio1.sock
```

### 访问多实例

启动后通过不同端口访问：

| 实例 | URL | 说明 |
|------|-----|------|
| radio1 | `https://your-server:8891/mobile_modern.html` | 主电台 |
| radio2 | `https://your-server:8892/mobile_modern.html` | 备用电台 |
| radio3 | `https://your-server:8893/mobile_modern.html` | 第三个电台 |

### 手动配置方式（不使用脚本）

如果你更喜欢手动配置，也可以直接复制和编辑配置文件：

```bash
# 复制主配置
cp MRRC.conf MRRC.radio1.conf

# 编辑配置
nano MRRC.radio1.conf
```

关键修改项：
```ini
[SERVER]
port = 8891  # 确保每个实例端口不同

[HAMLIB]
rig_pathname = /dev/cu.usbserial-230  # 第一个电台串口

# 添加 [INSTANCE_SETTINGS] 节（可选，用于 mrrc_multi.sh）
[INSTANCE_SETTINGS]
INSTANCE_NAME = radio1
INSTANCE_PORT = 8891
INSTANCE_RIGCTL_PORT = 4531
```

手动启动：
```bash
# 启动 rigctld（指定不同端口）
rigctld -m 3073 -r /dev/cu.usbserial-230 -s 4800 -t 4531 &

# 启动 MRRC（指定配置文件）
python3 MRRC MRRC.radio1.conf &
```

### 多实例天调数据

每个实例的天调学习数据独立存储：

```
atr1000_tuner.json          # 默认实例
atr1000_radio1.json         # radio1 实例
atr1000_radio2.json         # radio2 实例
```

在 `atr1000_proxy.py` 启动时通过 `--instance` 参数指定：

```bash
python3 atr1000_proxy.py --instance radio1
```

### 故障排查

#### 问题：端口冲突

**症状**: 启动时提示 "Address already in use"

**解决**:
```bash
# 检查端口占用
lsof -i :8891  # macOS
netstat -tlnp | grep 8891  # Linux

# 修改配置文件使用其他端口
nano MRRC.radio1.conf
# 修改 port = 8893
```

#### 问题：rigctld 冲突

**症状**: 多个实例使用同一个 rigctld

**解决**:
```bash
# 确保每个实例的 INSTANCE_RIGCTL_PORT 不同
# radio1: 4531
# radio2: 4532
# radio3: 4533
```

#### 问题：音频设备冲突

**症状**: 两个实例使用同一个音频设备导致错误

**解决**:
- 每个实例必须使用不同的音频设备
- 或使用虚拟音频设备（如 BlackHole on macOS）

#### 问题：权限不足（Linux）

**症状**: 无法访问串口设备

**解决**:
```bash
# 添加用户到 dialout 组
sudo usermod -a -G dialout $USER
# 重新登录后生效
```

[HAMLIB]
# 实例2连接的电台
rig_pathname = /dev/cu.usbserial-231
rig_model = 3073
```

#### 步骤 4: 使用 mrrc_multi.sh 启动

```bash
# 编辑 mrrc_multi.sh 配置实例列表
nano mrrc_multi.sh

# 启动所有实例
./mrrc_multi.sh start

# 查看状态
./mrrc_multi.sh status

# 停止所有实例
./mrrc_multi.sh stop
```

### mrrc_multi.sh 配置示例

```bash
# 实例列表
INSTANCES=("radio1" "radio2")

# 每个实例的配置
RADIO1_NAME="Main Radio"
RADIO1_PORT="8877"
RADIO1_DEVICE="/dev/cu.usbserial-230"

RADIO2_NAME="Backup Radio"
RADIO2_PORT="8878"
RADIO2_DEVICE="/dev/cu.usbserial-231"
```

### 访问多实例

- 实例1: `https://your-server:8877/mobile_modern.html`
- 实例2: `https://your-server:8878/mobile_modern.html`

---

## TLS/SSL 证书配置

### 使用 Let's Encrypt 证书（推荐）

```bash
# 安装 certbot
# macOS
brew install certbot

# Ubuntu/Debian
sudo apt install certbot

# 申请证书（需要域名指向服务器）
sudo certbot certonly --standalone -d radio.yourdomain.com

# 复制证书到项目目录
sudo cp /etc/letsencrypt/live/radio.yourdomain.com/fullchain.pem certs/
sudo cp /etc/letsencrypt/live/radio.yourdomain.com/privkey.pem certs/radio.yourdomain.com.key
sudo chmod 644 certs/*

# 自动续期（添加到 crontab）
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && cp /etc/letsencrypt/live/radio.yourdomain.com/*.pem /path/to/mrrc/certs/") | crontab -
```

### 使用自签名证书（测试用）

```bash
# 生成自签名证书
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout certs/selfsigned.key \
    -out certs/selfsigned.pem \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# 更新配置
nano MRRC.conf
# 修改：
# certfile = certs/selfsigned.pem
# keyfile = certs/selfsigned.key
```

⚠️ **注意**: 自签名证书在浏览器中会显示安全警告，需要手动添加例外。

### 无 TLS 运行（仅本地测试）

```bash
# 编辑 MRRC，注释掉 TLS 相关行
# 大约在文件开头附近，找到并注释：
# ssl_options={
#     "certfile": config.get("SERVER", "certfile"),
#     "keyfile": config.get("SERVER", "keyfile"),
# }

# 使用 http_server 替代 http_server_ssl
```

---

## 服务管理

MRRC 提供了 `mrrc_control.sh` 脚本用于日常服务管理，以及系统服务配置脚本 `mrrc_setup.sh`。

### 控制脚本 `mrrc_control.sh`

`mrrc_control.sh` 是日常管理 MRRC 服务的主要工具，适合开发和测试环境。

#### 基本用法

```bash
./mrrc_control.sh <命令> [参数]
```

#### 可用命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `start` | 启动所有服务 | `./mrrc_control.sh start` |
| `stop` | 停止所有服务 | `./mrrc_control.sh stop` |
| `restart` | 重启所有服务 | `./mrrc_control.sh restart` |
| `status` | 查看服务状态 | `./mrrc_control.sh status` |
| `logs [n]` | 查看日志（最后n行） | `./mrrc_control.sh logs 50` |
| `start-rigctld` | 仅启动 rigctld | `./mrrc_control.sh start-rigctld` |
| `stop-rigctld` | 仅停止 rigctld | `./mrrc_control.sh stop-rigctld` |
| `start-mrrc` | 仅启动 MRRC | `./mrrc_control.sh start-mrrc` |
| `stop-mrrc` | 仅停止 MRRC | `./mrrc_control.sh stop-mrrc` |
| `start-atr1000` | 仅启动 ATR-1000 代理 | `./mrrc_control.sh start-atr1000` |
| `stop-atr1000` | 仅停止 ATR-1000 代理 | `./mrrc_control.sh stop-atr1000` |

#### 使用示例

**启动所有服务**:
```bash
./mrrc_control.sh start

# 输出示例：
# [INFO] 2026-03-15 14:30:00 - 启动 MRRC 服务...
# [INFO] 2026-03-15 14:30:00 - 启动 rigctld...
# [SUCCESS] 2026-03-15 14:30:03 - rigctld 已启动 (PID: 12340)
# [INFO] 2026-03-15 14:30:03 - 启动 MRRC...
# [SUCCESS] 2026-03-15 14:30:05 - MRRC 已启动 (PID: 12345)
# [INFO] 2026-03-15 14:30:05 - MRRC 服务启动完成
# [SUCCESS] 2026-03-15 14:30:05 - MRRC 运行中，访问: https://localhost:8877
```

**查看状态**:
```bash
./mrrc_control.sh status

# 输出示例：
# [INFO] 2026-03-15 14:30:10 - 检查 MRRC 服务状态...
# rigctld: 运行中 (PID: 12340)
# MRRC: 运行中 (PID: 12345)
# ATR-1000: 运行中 (PID: 12350)
```

**查看日志**:
```bash
# 查看最后 20 行（默认）
./mrrc_control.sh logs

# 查看最后 100 行
./mrrc_control.sh logs 100
```

**单独控制服务**（用于调试）:
```bash
# 仅启动 rigctld（调试用）
./mrrc_control.sh start-rigctld

# 仅启动 MRRC
./mrrc_control.sh start-mrrc

# 单独停止并重启 MRRC
./mrrc_control.sh stop-mrrc
./mrrc_control.sh start-mrrc
```

### 系统服务配置（生产环境）

对于长期运行的生产环境，建议配置为系统服务。

#### macOS (launchd)

使用 `mrrc_setup.sh` 脚本配置系统服务：

```bash
# 安装并配置 launchd 服务
./mrrc_setup.sh install

# 服务安装后会：
# 1. 复制 plist 文件到 ~/Library/LaunchAgents/
# 2. 设置正确的路径和工作目录
# 3. 加载服务配置

# 启动服务
launchctl start com.user.mrrc

# 停止服务
launchctl stop com.user.mrrc

# 查看状态
launchctl list | grep mrrc

# 查看日志
tail -f ~/Library/Logs/mrrc.log

# 卸载服务
launchctl unload ~/Library/LaunchAgents/com.user.mrrc.plist
rm ~/Library/LaunchAgents/com.user.mrrc.plist
```

**launchd 服务特点**:
- 用户登录后自动启动
- 崩溃后自动重启（如果配置了 KeepAlive）
- 适合 macOS 服务器或常开机的 Mac

#### Linux (systemd)

创建 systemd 服务文件：

```bash
# 创建服务文件
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

# 重新加载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start mrrc

# 停止服务
sudo systemctl stop mrrc

# 重启服务
sudo systemctl restart mrrc

# 查看状态
sudo systemctl status mrrc

# 查看日志
sudo journalctl -u mrrc -f

# 开机自启
sudo systemctl enable mrrc
```

**systemd 服务特点**:
- 系统启动时自动启动
- 崩溃后自动重启
- 完善的日志管理（journalctl）
- 适合 Linux 服务器

### 服务管理对比

| 管理方式 | 适用场景 | 自动重启 | 开机启动 |
|----------|----------|----------|----------|
| `mrrc_control.sh` | 开发/测试 | ❌ | ❌ |
| macOS launchd | macOS 服务器 | ✅ | ✅（用户登录） |
| Linux systemd | Linux 服务器 | ✅ | ✅（系统启动） |
| `mrrc_multi.sh` | 多实例管理 | ❌ | ❌ |

### 日志文件位置

不同方式启动的日志存储位置：

**`mrrc_control.sh` 启动**:
- rigctld 日志: `/tmp/rigctld.log`
- MRRC 日志: `MRRC.log`（项目目录）
- ATR-1000 日志: `atr1000_proxy.log`

**launchd 服务**:
- 日志: `~/Library/Logs/mrrc.log`

**systemd 服务**:
- 日志: `sudo journalctl -u mrrc`

**`mrrc_multi.sh` 多实例**:
- rigctld 日志: `rigctld_<实例名>.log`
- MRRC 日志: `mrrc_<实例名>.log`
- ATR-1000 日志: `atr1000_<实例名>.log`

---

## 故障排查

### 1. rigctld 连接失败

**症状**: MRRC 无法连接电台，频率显示为空

**排查步骤**:

```bash
# 1. 检查 rigctld 是否运行
ps aux | grep rigctld

# 2. 检查串口设备
ls -la /dev/cu.usbserial-*  # macOS
ls -la /dev/ttyUSB*         # Linux

# 3. 检查串口权限（Linux）
ls -la /dev/ttyUSB0
groups  # 确认用户在 dialout 组

# 4. 手动测试 rigctld
rigctl -m 3073 -r /dev/ttyUSB0 -s 4800 f  # 获取频率

# 5. 检查 rigctld 日志
cat /tmp/rigctld.log
```

**解决方案**:

```bash
# Linux：添加用户到 dialout 组
sudo usermod -a -G dialout $USER
# 重新登录后生效

# 启动 rigctld
rigctld -m 3073 -r /dev/ttyUSB0 -s 4800 -C stop_bits=2 -vvvv
```

### 2. 音频设备未找到

**症状**: 报错 "找不到音频设备"

**排查步骤**:

```bash
# 1. 检查设备连接
system_profiler SPUSBDataType | grep -A5 "Audio"  # macOS
lsusb | grep Audio                                # Linux

# 2. 检查 PyAudio 设备列表
python3 << 'EOF'
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print(f"{i}: {info['name']}")
p.terminate()
EOF

# 3. 检查配置文件中的设备名称
# 确保 MRRC.conf 中的设备名称与上一步输出完全一致
```

**解决方案**:

```bash
# 修改 MRRC.conf 中的设备名称
nano MRRC.conf

[AUDIO]
# 确保名称与 PyAudio 输出完全一致
outputdevice = USB Audio CODEC
inputdevice = USB Audio CODEC
```

### 3. WDSP 库加载失败

**症状**: 日志显示 "WDSP 库不可用"

**排查步骤**:

```bash
# 1. 检查库文件是否存在
ls -la /usr/local/lib/libwdsp*

# 2. 检查库加载
python3 -c "import ctypes; ctypes.CDLL('/usr/local/lib/libwdsp.dylib')"  # macOS
python3 -c "import ctypes; ctypes.CDLL('/usr/local/lib/libwdsp.so')"      # Linux

# 3. 检查库路径
# macOS
otool -L /usr/local/lib/libwdsp.dylib

# Linux
ldd /usr/local/lib/libwdsp.so
```

**解决方案**:

```bash
# macOS
sudo cp /tmp/wdsp/libwdsp.dylib /usr/local/lib/

# Linux
sudo cp /tmp/wdsp/libwdsp.so /usr/local/lib/
sudo ldconfig
```

### 4. WebSocket 连接失败

**症状**: 浏览器显示 "连接断开" 或无法加载页面

**排查步骤**:

```bash
# 1. 检查 MRRC 是否在运行
ps aux | grep "python3 MRRC"

# 2. 检查端口是否监听
lsof -i :8877  # macOS
netstat -tlnp | grep 8877  # Linux

# 3. 检查防火墙
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-ports  # CentOS

# 4. 检查证书
openssl x509 -in certs/radio.vlsc.net.pem -text -noout
```

**解决方案**:

```bash
# 打开防火墙端口（如果需要）
# Ubuntu/Debian
sudo ufw allow 8877/tcp

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=8877/tcp
sudo firewall-cmd --reload
```

### 5. TLS/SSL 证书错误

**症状**: 浏览器显示 "您的连接不是私密连接"

**排查步骤**:

```bash
# 1. 检查证书文件
ls -la certs/

# 2. 验证证书格式
openssl x509 -in certs/radio.vlsc.net.pem -text -noout

# 3. 检查证书和密钥是否匹配
openssl x509 -noout -modulus -in certs/radio.vlsc.net.pem | openssl md5
openssl rsa -noout -modulus -in certs/radio.vlsc.net.key | openssl md5
```

**解决方案**:

```bash
# 如果证书不匹配，重新生成
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout certs/selfsigned.key \
    -out certs/selfsigned.pem \
    -subj "/CN=localhost"

# 更新配置使用新证书
```

### 6. ATR-1000 天调连接失败

**症状**: 功率/SWR 不显示

**排查步骤**:

```bash
# 1. 检查 ATR-1000 代理是否运行
ps aux | grep atr1000_proxy

# 2. 检查网络连接
ping 192.168.1.63  # ATR-1000 默认IP

# 3. 检查日志
tail -f atr1000_proxy.log

# 4. 检查 Unix Socket
ls -la /tmp/atr1000_proxy.sock
```

**解决方案**:

```bash
# 手动启动 ATR-1000 代理
python3 atr1000_proxy.py --device 192.168.1.63 --port 60001 &

# 或使用控制脚本
./mrrc_control.sh start-atr1000
```

---

## 常见问题 Q&A

### Q1: 支持哪些电台？

**A**: MRRC 通过 Hamlib 支持超过 200 种业余电台。常见支持的电台包括：
- Icom: IC-7300, IC-7100, IC-7610, IC-7850, IC-9700, IC-M710 等
- Yaesu: FT-991A, FTDX-101D, FTDX-10 等
- Kenwood: TS-590S, TS-890S 等

使用 `rigctl -l | grep -i "品牌名"` 查询具体型号代码。

### Q2: 可以在 Windows 上运行吗？

**A**: 目前主要支持 macOS 和 Linux。Windows 用户可以使用 WSL2（Windows Subsystem for Linux）来运行。

### Q3: 如何实现外网访问？

**A**: 推荐方案：
1. **VPN**: 最安全，使用 WireGuard 或 OpenVPN
2. **内网穿透**: 使用 frp、ngrok 等工具
3. **端口转发**: 在路由器上配置端口转发（需公网IP）
4. **反向代理**: 使用 Nginx + SSL

⚠️ **警告**: 直接暴露到公网存在安全风险，务必启用认证和 TLS。

### Q4: 多用户同时控制会冲突吗？

**A**: MRRC 支持多用户同时连接，但需要注意：
- 只有一个用户可以发射（PTT 互锁）
- 频率设置会同步给所有用户
- 建议设置操作员轮流使用 PTT

### Q5: 音频有延迟/断续怎么办？

**A**: 排查步骤：
1. 检查网络延迟: `ping your-server`
2. 降低 WDSP 处理强度
3. 调整 RX 缓冲区大小
4. 使用有线网络连接
5. 关闭其他占用带宽的应用

### Q6: 如何更新 MRRC？

**A**: 
```bash
# 备份配置
cp MRRC.conf MRRC.conf.backup

# 拉取更新
git pull origin main

# 恢复配置
cp MRRC.conf.backup MRRC.conf

# 重启服务
./mrrc_control.sh restart
```

### Q7: 如何调试问题？

**A**: 
1. 开启调试模式：在 `MRRC.conf` 中设置 `debug = True`
2. 查看日志：`./mrrc_control.sh logs` 或 `tail -f MRRC.log`
3. 浏览器开发者工具：F12 → Console/Network
4. 使用测试工具：`dev_tools/test_connection.html`

### Q8: 移动端浏览器有什么要求？

**A**: 
- **iOS**: Safari 14+（推荐），Chrome, Firefox
- **Android**: Chrome 90+, Firefox, Samsung Internet
- **必需功能**: Web Audio API, WebSocket, ES6

### Q9: WDSP 和 RNNoise 有什么区别？

**A**: 
| 特性 | WDSP | RNNoise |
|------|------|---------|
| 算法 | 频谱减法 | 神经网络 |
| 优化 | 专门优化 SSB 语音 | 通用语音 |
| 延迟 | <20ms | 30-50ms |
| 音质 | 更好 | 一般 |
| 资源 | 低 | 较高 |

**推荐**: 使用 WDSP 的 NR2 功能，已默认启用。

### Q10: 如何备份天调学习数据？

**A**: 
```bash
# 备份
cp atr1000_tuner.json atr1000_tuner.json.backup

# 恢复
cp atr1000_tuner.json.backup atr1000_tuner.json

# 多实例备份
cp atr1000_radio1.json atr1000_radio1.json.backup
```

---

## 获取帮助

- **GitHub Issues**: https://github.com/cheenle/UHRR_mac/issues
- **文档**: 查看 `docs/` 目录
- **日志**: `./mrrc_control.sh logs`

---

**最后更新**: 2026-03-15  
**文档版本**: V4.9.2
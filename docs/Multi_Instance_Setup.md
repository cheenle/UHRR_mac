# MRRC 多实例配置指南

**文档版本**: V1.0 (2026-03-15)  
**对应 MRRC 版本**: V4.9.1

## 概述

MRRC 支持在同一台服务器上运行多个独立实例，每个实例可以：
- 连接不同的电台设备（不同串口/型号）
- 使用不同的音频设备（不同声卡）
- 独立的天调参数学习（每个实例有自己的学习记录）
- 独立的 Web 服务端口

**典型应用场景**：
- 一台服务器控制多部电台（主电台 + 备用电台）
- 不同的频段使用不同的天调参数
- 个人电台 + 俱乐部共享电台

---

## 快速开始

### 1. 创建新实例配置

```bash
# 使用多实例管理脚本创建
cd /Users/cheenle/UHRR/MRRC
./mrrc_multi.sh create radio2
```

### 2. 编辑实例配置

```bash
# 编辑配置文件
vim MRRC.radio2.conf
```

关键配置项：
```ini
[INSTANCE_SETTINGS]
instance_name = radio2
instance_port = 8892                          # Web服务端口，必须唯一
instance_rigctl_port = 4532                   # rigctld端口，必须唯一
instance_unix_socket = /tmp/mrrc_radio2.sock  # Unix Socket路径，必须唯一
instance_atr1000_device = 192.168.1.64        # ATR-1000设备IP
```

### 3. 启动实例

```bash
./mrrc_multi.sh start radio2
```

---

## 详细配置说明

### 目录结构

```
MRRC/
├── MRRC                      # 主程序（支持多实例）
├── MRRC.conf                 # 默认配置（单实例模式）
├── MRRC.radio1.conf          # 实例1配置
├── MRRC.radio2.conf          # 实例2配置
├── mrrc_multi.sh             # 多实例管理脚本
└── docs/
    └── Multi_Instance_Setup.md  # 本文档
```

### 配置参数详解

#### [INSTANCE_SETTINGS] 节

| 参数 | 说明 | 示例 |
|------|------|------|
| `instance_name` | 实例名称，用于日志标识 | `radio2` |
| `instance_port` | Web服务端口，必须唯一 | `8892` |
| `instance_rigctl_port` | rigctld控制端口，必须唯一 | `4532` |
| `instance_rigctl_device` | 电台串口设备 | `/dev/tty.usbserial-ABAUOK9F` |
| `instance_rigctl_model` | 电台型号编号 | `6006` |
| `instance_audio_input` | 音频输入设备 | `USB PnP Sound Device` |
| `instance_audio_output` | 音频输出设备 | `USB PnP Sound Device` |
| `instance_atr1000_device` | ATR-1000设备IP | `192.168.1.63` |
| `instance_atr1000_port` | ATR-1000端口 | `60001` |
| `instance_unix_socket` | Unix Socket路径，必须唯一 | `/tmp/mrrc_radio2.sock` |
| `instance_log_dir` | 日志目录 | `/Users/cheenle/UHRR/MRRC` |

### 端口分配原则

每个实例需要独立的端口：

| 实例 | Web端口 | rigctld端口 | Unix Socket |
|------|---------|-------------|-------------|
| radio1 | 8891 | 4531 | /tmp/mrrc_radio1.sock |
| radio2 | 8892 | 4532 | /tmp/mrrc_radio2.sock |
| radio3 | 8893 | 4533 | /tmp/mrrc_radio3.sock |

**重要**：端口冲突会导致实例启动失败！

---

## 管理命令

### mrrc_multi.sh 脚本

```bash
# 查看帮助
./mrrc_multi.sh help

# 创建新实例（从默认配置复制）
./mrrc_multi.sh create <实例名>

# 启动实例
./mrrc_multi.sh start <实例名>

# 停止实例
./mrrc_multi.sh stop <实例名>

# 重启实例
./mrrc_multi.sh restart <实例名>

# 查看状态
./mrrc_multi.sh status <实例名>

# 查看日志
./mrrc_multi.sh logs <实例名> [行数]

# 删除实例
./mrrc_multi.sh delete <实例名>

# 列出所有实例
./mrrc_multi.sh list
```

### 手动管理

```bash
# 启动单个组件
./mrrc_multi.sh start-rigctld radio2
./mrrc_multi.sh start-mrrc radio2
./mrrc_multi.sh start-atr1000 radio2

# 停止单个组件
./mrrc_multi.sh stop-rigctld radio2
./mrrc_multi.sh stop-mrrc radio2
./mrrc_multi.sh stop-atr1000 radio2
```

---

## 完整配置示例

### 实例1：IC-M710（radio1）

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

### 实例2：JRC NRD-535D（radio2）

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

## 访问地址

实例启动后，通过以下地址访问：

| 实例 | 地址 |
|------|------|
| radio1 | https://localhost:8891/mobile_modern.html |
| radio2 | https://localhost:8892/mobile_modern.html |

如果使用域名：
- https://radio1.vlsc.net:8891/mobile_modern.html
- https://radio2.vlsc.net:8892/mobile_modern.html

---

## 故障排查

### 1. 端口冲突

**症状**：`Address already in use` 错误

**解决**：
```bash
# 检查端口占用
lsof -i :8892
lsof -i :4532

# 修改配置使用其他端口
vim MRRC.radio2.conf
# 修改 instance_port 和 instance_rigctl_port
```

### 2. ATR-1000 连接失败

**症状**：日志显示 `No such file or directory`

**排查**：
```bash
# 检查 Socket 文件是否存在
ls -la /tmp/mrrc_radio2.sock

# 检查 ATR-1000 代理日志
tail -20 atr1000_radio2.log

# 重启实例
./mrrc_multi.sh restart radio2
```

### 3. 串口设备不存在

**症状**：`rigctld failed to start`

**排查**：
```bash
# 列出可用串口
ls /dev/cu.* /dev/tty.*

# 更新配置中的设备路径
vim MRRC.radio2.conf
```

### 4. 频率不同步

**症状**：天调参数不随频率变化

**排查**：
```bash
# 检查 MRRC 日志中的频率同步记录
grep "频率同步" mrrc_radio2.log

# 检查 ATR-1000 代理是否收到频率
grep "set_freq" atr1000_radio2.log
```

---

## 高级配置

### 天调参数独立存储

每个实例使用独立的 Unix Socket，因此天调学习记录是独立的：

- radio1: 学习记录存储在 `atr1000_tuner.json` 中（通过 `/tmp/mrrc_radio1.sock`）
- radio2: 学习记录存储在 `atr1000_tuner.json` 中（通过 `/tmp/mrrc_radio2.sock`）

**注意**：虽然文件名相同，但代理进程是独立的，数据不会冲突。

### 共享 ATR-1000 设备

如果多个实例使用同一个 ATR-1000 设备（如本例中的 192.168.1.63）：

1. 各实例独立学习自己的参数
2. 参数自动应用，不会互相干扰
3. 建议在 ATR-1000 设备上为不同电台配置不同的天线

### 系统服务配置

创建系统服务实现开机自启：

```bash
# 为 radio1 创建服务
./mrrc_multi.sh enable-service radio1

# 为 radio2 创建服务
./mrrc_multi.sh enable-service radio2
```

或使用 launchd（macOS）：

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

## 性能优化

### 多实例资源占用

每个实例的资源占用：

| 组件 | CPU | 内存 |
|------|-----|------|
| rigctld | ~1% | ~10MB |
| MRRC | ~5-15% | ~50-100MB |
| ATR-1000 Proxy | ~1% | ~20MB |

**建议**：一台普通 PC 可以稳定运行 3-5 个实例。

### 日志管理

多实例会产生多个日志文件：

```bash
# 定期清理日志
./mrrc_multi.sh cleanup-logs

# 或手动清理
rm -f mrrc_radio*.log.* atr1000_radio*.log.*
```

---

## 安全考虑

### 网络隔离

- 每个实例使用独立的 WebSocket 端口
- 建议为每个实例配置独立的 TLS 证书
- 可以使用反向代理（nginx）进行统一入口管理

### 认证共享

多个实例可以共享同一个用户数据库：

```ini
[SERVER]
db_users_file = MRRC_users.db  # 所有实例使用相同的认证文件
```

---

## 更新日志

- **2024-03-15**: 初始多实例支持文档
- 支持 `mrrc_multi.sh` 管理脚本
- 独立的 Unix Socket 路径配置
- 自动化的实例创建和删除

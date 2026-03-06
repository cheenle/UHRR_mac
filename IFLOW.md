# iFlow 上下文信息 (IFLOW.md)

## 项目概述

**Mobile Remote Radio Control (MRRC)** 是一款专为移动端优化的业余电台远程控制系统。它允许业余无线电爱好者通过现代Web浏览器（尤其是移动设备）随时随地远程控制电台设备，进行语音通话和参数调节。

**设计理念**：Mobile First, Radio Anywhere - 随时随地，畅享业余无线电。

主要技术栈：
- **前端**：HTML5, CSS3, JavaScript (VanillaJS), Web Audio API, AudioWorklet, WebSocket
- **后端**：Python 3.12+, Tornado Web Framework, PyAudio, Hamlib/rigctld
- **部署**：macOS/类Unix系统，支持TLS加密和用户认证

### 核心特性
- **移动优先设计**：专为触摸屏优化，支持单手操作，PWA离线访问
- **超低延迟**：TX/RX切换<100ms，PTT可靠性99%+
- **随时随地访问**：互联网覆盖处即可操控您的电台
- **安全连接**：TLS加密传输，用户认证保护
- **完整控制**：频率、模式、PTT、天调等完整电台功能

### 历史改进
- **增强的PTT可靠性机制**：按下即发送PTT命令，并立即发送预热帧确保后端收到音频数据
- **优化的TX/RX切换**：从2-3秒延迟优化至<100ms切换响应
- **移动端支持**：专门的移动界面，优化触摸交互和音频处理，支持iPhone 15等现代移动设备
- **AAC音频编码**：新增ADPCM自适应差分编码，支持50-60%压缩率
- **音频优化**：采用Int16编码（50%带宽减少），AudioWorklet低抖动播放
- **NanoVNA集成**：内置矢量网络分析仪Web界面支持
- **ATR-1000集成**：实时功率/SWR显示，天调存储功能
- **WebRTC最佳实践**：Opus编码参数优化，降低CPU占用

## 目录结构要点

```
MRRC/
├── MRRC                          # 后端主程序 (Tornado WebSocket服务器)
├── MRRC.conf                     # 系统核心配置文件
├── audio_interface.py            # PyAudio采集/播放封装与客户端分发
├── hamlib_wrapper.py             # 与rigctld通信的辅助逻辑
├── tci_client.py                 # TCI协议客户端实现
├── atr1000_proxy.py              # ATR-1000独立代理程序
├── atr1000_tuner.py              # 天调存储模块
├── atr1000_tuner.json            # 天调参数数据文件
├── mrrc_control.sh               # 系统控制脚本（启动/停止/状态）
├── mrrc_monitor.sh               # 系统监控脚本
├── mrrc_setup.sh                 # 系统安装配置脚本
├── www/                          # 前端页面与脚本
│   ├── controls.js               # 音频与控制主逻辑
│   ├── tx_button_optimized.js    # TX按钮事件与时序优化
│   ├── rx_worklet_processor.js   # AudioWorklet播放器
│   ├── aac_encoder.js            # AAC/ADPCM音频编码器
│   ├── atu.js                    # ATU功率和驻波比显示管理
│   ├── mobile_modern.html        # 现代移动端界面 (iPhone 15优化)
│   ├── mobile_modern.js          # 移动端界面逻辑
│   ├── mobile_modern.css         # 移动端界面样式
│   ├── mobile_audio_direct_copy.js # 移动端音频处理
│   ├── control_trx.js            # 电台控制逻辑
│   ├── ui_utils.js               # UI工具函数
│   ├── touch-enhancements.js     # 触摸增强
│   ├── manifest.json             # PWA应用清单文件
│   ├── sw.js                     # Service Worker (离线支持)
│   ├── opus.wasm                 # Opus编解码器WebAssembly模块
│   └── panadapter/               # 频谱显示模块
├── certs/                        # TLS证书目录
├── dev_tools/                    # 测试/调试脚本与页面
│   ├── debug_audio.html          # 音频调试页面
│   ├── debug_audio_rx.html       # RX音频调试页面
│   ├── debug_audio_state.html    # 音频状态调试页面
│   ├── debug_power_button.html   # 电源按钮调试页面
│   ├── debug_mrrc.py             # MRRC调试脚本
│   ├── simple_audio_test.html    # 简单音频测试页面
│   ├── test_audio.py             # 音频测试脚本
│   ├── test_audio_capture.py     # 音频采集测试脚本
│   ├── test_audio_context.html   # 音频上下文测试页面
│   ├── test_audio_quality.sh     # 音频质量测试脚本
│   ├── test_connection.py        # 连接测试脚本
│   ├── test_connection.html      # 连接测试页面
│   ├── test_websocket_client.py  # WebSocket客户端测试
│   ├── test_server.py            # 服务器测试脚本
│   ├── test_tornado.py           # Tornado框架测试
│   ├── test_service.py           # 服务测试脚本
│   ├── test_service_detailed.py  # 详细服务测试
│   ├── test_installation.py      # 安装测试脚本
│   ├── test_http_server.py       # HTTP服务器测试
│   ├── test_ssl_server.py        # SSL服务器测试
│   ├── test_mobile.sh            # 移动端测试脚本
│   ├── test_mobile_fixes.html    # 移动端修复测试页面
│   ├── test_callsign.html        # 呼号测试页面
│   ├── test_file_access.py       # 文件访问测试
│   ├── test_pad_tx.html          # PAD TX测试页面
│   ├── test_restart.html         # 重启测试页面
│   └── test_mrrc_handler.py      # MRRC处理器测试
├── nanovna/                      # NanoVNA矢量网络分析仪Web界面
│   └── NanoVNA/
│       ├── index.html            # NanoVNA主界面
│       ├── nanovna.js            # NanoVNA控制逻辑
│       └── sw.js                 # Service Worker
├── docs/                         # 技术文档
│   ├── System_Architecture_Design.md      # 系统架构设计文档
│   ├── PTT_Audio_Postmortem_and_Best_Practices.md # PTT/音频稳定性复盘
│   ├── latency_optimization_guide.md       # TX/RX切换延迟优化指南
│   ├── mobile_modern_interface.md          # 现代移动端界面文档
│   ├── Mobile_User_Manual.md               # 移动端用户手册
│   ├── Mobile_User_Manual.html             # 移动端用户手册(HTML)
│   ├── Performance_Optimization_Guide.md   # 性能优化指南
│   ├── Component_Detailed_Analysis.md      # 组件详细分析
│   ├── Comprehensive_Architecture_Analysis.md # 综合架构分析
│   ├── End_to_End_Analysis_Report.md       # 端到端分析报告
│   ├── ATR1000_Display_Issue_Analysis.md   # ATR-1000显示问题分析
│   ├── ATR1000_PTT_Delay_Troubleshooting_Journey.md # ATR-1000 PTT延迟调试历程
│   ├── CODE_REVIEW_REPORT.md               # 代码审查报告
│   ├── iphone15_mobile_interface_analysis.md # iPhone 15界面分析
│   └── mobile_interface_enhancement_summary.md # 移动界面增强总结
├── opus/                         # Opus编解码器Python绑定
├── screenshots/                  # 截图资源目录
├── *.wav                         # 音频测试文件 (cq.wav, tune.wav等)
└── com.user.mrrc.plist           # macOS launchd服务配置
```

## 核心功能与架构

### 1. 远程控制
- 通过WebSocket与后端Tornado服务器通信
- 控制命令包括频率、模式、PTT等
- 使用Hamlib/rigctld与实际电台硬件通信
- 支持VFO切换、S表读取、频谱显示等功能
- 支持TCI协议（Transceiver Control Interface）与特定电台型号通信

### 2. 实时音频流
- **TX (发射)**: 浏览器麦克风输入 → Web Audio API处理 → Int16/AAC编码 → WebSocket传输 → 后端PyAudio播放到电台
- **RX (接收)**: 电台音频 → 后端PyAudio采集 → Int16编码 → WebSocket传输 → 浏览器AudioWorklet播放
- 采样率：16kHz，格式：Int16（50%带宽优化），目标延迟：<100ms
- 支持Int16编码和Opus编码双模式
- 支持ADPCM压缩编码

### 3. 增强的PTT可靠性机制
- 按下即发送PTT命令
- 立即发送10个预热帧确保后端收到音频数据
- PTT超时保护采用计数法（连续10次未收到音频帧才熄灭PTT，每次检查间隔200ms）
- PTT防抖机制防止重复命令发送（50ms防抖延迟）
- PTT状态确认机制确保命令执行成功（优化后的确认时序）

### 4. 优化的实时性
- TX/RX切换延迟已优化至<100ms（原2-3秒）
- AudioWorklet播放器使用区间缓冲（16/32帧）平衡延迟与稳定性
- TX释放时立即清除RX缓冲区
- 音频缓冲区深度动态调整适应网络条件

### 5. AAC/ADPCM音频编码
- **编码器文件**：`www/aac_encoder.js`
- **ADPCM压缩**：自适应差分PCM编码，压缩率50-60%
- **降采样支持**：高采样率音频降采样到16kHz
- **兼容性优先**：支持所有现代浏览器
- **可选MediaRecorder**：支持实际AAC编码（兼容性有限）

### 6. 移动端优化
- **现代移动界面**：专门为iPhone 15和现代移动浏览器优化的界面
- **PWA支持**：支持添加到主屏幕，离线访问
- **触摸优化**：大尺寸PTT按钮，适配拇指操作区域
- **安全区域支持**：适配刘海屏和底部指示器
- **触觉反馈**：PTT按钮提供震动反馈
- **响应式设计**：支持横竖屏切换，适配各种屏幕尺寸
- **性能优化**：Service Worker缓存，快速启动
- **兼容性**：支持iOS Safari、Chrome、Firefox等现代浏览器
- **菜单功能**：支持波段选择、模式切换、滤波器设置

### 7. NanoVNA集成
- 内置矢量网络分析仪Web界面
- 支持NanoVNA设备连接和控制
- 独立的PWA应用支持
- 离线测量功能

### 8. ATR-1000 功率计/天调集成
- **实时功率显示**：发射时显示前向功率（0-200W）
- **SWR监测**：实时显示驻波比（1.0-9.99）
- **继电器状态**：显示LC/CL组合、电感、电容值
- **天调存储**：自动记录频率与天调参数的对应关系
- **连接预热**：页面加载时预先建立连接，PTT响应<200ms

### 9. 其他功能
- **电压电流监控**：实时显示电源电压 (Vin, 12V) 和电流 (Idq)
- **多用户登录**：支持多用户账号登录验证

## 关键配置文件 (MRRC.conf)

主要配置项：
- `[SERVER]`: 端口、证书路径、认证设置
  - `port`: 默认8877，生产环境建议443
  - `certfile`: TLS证书路径（如certs/radio.vlsc.net.pem）
  - `keyfile`: TLS私钥路径
  - `auth`: 认证方式（FILE/PAM）
  - `db_users_file`: 用户数据库文件路径
  - `debug`: 调试模式开关
- `[AUDIO]`: 音频输入/输出设备名称
  - `outputdevice`: 音频输出设备（如 USB Audio CODEC）
  - `inputdevice`: 音频输入设备（如 USB Audio CODEC）
- `[HAMLIB]`: 电台串口路径、型号、波特率等
  - `rig_pathname`: 串口设备路径（如/dev/cu.usbserial-230）
  - `rig_model`: 电台型号（如IC_M710）
  - `rig_rate`: 波特率（如4800）
  - `stop_bits`: 停止位（如2）
- `[CTRL]`: S表更新周期等控制参数
  - `interval_smeter_update`: S表更新间隔（如0.5秒）
- `[PANADAPTER]`: 频谱分析仪相关设置（采样率、中心频率等）
  - `sample_rate`: 采样率（如960000）
  - `center_freq`: 中心频率（如68330000）
  - `gain`: 增益（如10）

## 开发与测试

### 测试工具
所有测试/调试脚本位于 `dev_tools/` 目录：

**音频测试工具：**
- `test_audio.py`: 音频测试脚本
- `test_audio_capture.py`: 音频采集测试脚本
- `test_audio_quality.sh`: 音频质量测试脚本
- `test_audio_context.html`: 音频上下文测试页面
- `simple_audio_test.html`: 简单音频测试页面

**连接测试工具：**
- `test_connection.py`: 连接测试脚本
- `test_websocket_client.py`: WebSocket客户端测试
- `test_connection.html`: 连接测试页面

**服务测试工具：**
- `test_server.py`: 服务器测试脚本
- `test_tornado.py`: Tornado框架测试
- `test_service.py`: 服务测试脚本
- `test_service_detailed.py`: 详细服务测试
- `test_installation.py`: 安装测试脚本
- `test_http_server.py`: HTTP服务器测试
- `test_ssl_server.py`: SSL服务器测试
- `test_mrrc_handler.py`: MRRC处理器测试

**移动端测试工具：**
- `test_mobile.sh`: 移动端测试脚本
- `test_mobile_fixes.html`: 移动端修复测试页面
- `test_pad_tx.html`: PAD TX测试页面

**调试工具：**
- `debug_audio.html`: 音频调试页面
- `debug_audio_rx.html`: RX音频调试页面
- `debug_audio_state.html`: 音频状态调试页面
- `debug_power_button.html`: 电源按钮调试页面
- `debug_mrrc.py`: MRRC调试脚本

**其他测试工具：**
- `test_callsign.html`: 呼号测试页面
- `test_file_access.py`: 文件访问测试
- `test_restart.html`: 重启测试页面

### TCI协议测试
- `tci_client.py`: TCI协议客户端实现
- 支持频率、模式、PTT控制
- 实时状态读取

### 文档资源
- 系统架构设计详见 `docs/System_Architecture_Design.md`
- PTT/音频稳定性复盘详见 `docs/PTT_Audio_Postmortem_and_Best_Practices.md`
- TX/RX切换延迟优化指南详见 `docs/latency_optimization_guide.md`
- 现代移动端界面详见 `docs/mobile_modern_interface.md`
- 移动端用户手册详见 `docs/Mobile_User_Manual.md`
- 性能优化指南详见 `docs/Performance_Optimization_Guide.md`
- 组件详细分析详见 `docs/Component_Detailed_Analysis.md`
- 综合架构分析详见 `docs/Comprehensive_Architecture_Analysis.md`
- 端到端分析报告详见 `docs/End_to_End_Analysis_Report.md`
- ATR-1000显示问题分析详见 `docs/ATR1000_Display_Issue_Analysis.md`
- ATR-1000 PTT延迟调试历程详见 `docs/ATR1000_PTT_Delay_Troubleshooting_Journey.md`
- iPhone 15界面分析详见 `docs/iphone15_mobile_interface_analysis.md`
- 移动界面增强总结详见 `docs/mobile_interface_enhancement_summary.md`
- 代码审查报告详见 `docs/CODE_REVIEW_REPORT.md`

### 开发实践
- 推荐在独立分支进行实验性修改
- 支持Docker容器化部署和测试
- 使用Git进行版本控制
- 遵循GPL-3.0开源协议

## 构建和运行

### 快速开始 (macOS)

1. **环境准备**
   ```bash
   # 检查Python版本
   python3 --version  # 需要 3.12+
   ```

2. **启动rigctld**（示例，根据实际设备调整）
   ```bash
   # IC-R9000 示例
   rigctld -m 30003 -r /dev/cu.usbserial-120 -s 4800 -C stop_bits=2
   ```

3. **配置TLS证书**（可选但推荐）
   - 将证书放入 `certs/` 目录
   - 编辑 `MRRC.conf` 配置证书路径：
     ```ini
     [SERVER]
     port = 443
     certfile = certs/radio.vlsc.net.pem
     keyfile = certs/radio.vlsc.net.key
     ```

4. **启动服务**
   ```bash
   # 使用控制脚本（推荐）
   ./mrrc_control.sh start
   
   # 或直接启动
   python3 ./MRRC
   ```

5. **访问**
   - 桌面端：`https://<你的域名或IP>/`（若使用443端口）
   - 移动端：`https://<你的域名或IP>/mobile_modern.html`
   - NanoVNA：`https://<你的域名或IP>/nanovna/NanoVNA/`

### 系统控制命令

```bash
# 启动所有服务（rigctld, MRRC, ATR-1000代理）
./mrrc_control.sh start

# 停止所有服务
./mrrc_control.sh stop

# 重启系统
./mrrc_control.sh restart

# 查看状态
./mrrc_control.sh status

# 查看日志
./mrrc_control.sh logs [行数] [服务名]

# 单独启动服务
./mrrc_control.sh start-rigctld
./mrrc_control.sh start-mrrc
./mrrc_control.sh start-atr1000

# 单独停止服务
./mrrc_control.sh stop-rigctld
./mrrc_control.sh stop-mrrc
./mrrc_control.sh stop-atr1000
```

### Docker部署

1. **构建Docker镜像**
   ```bash
   docker-compose build
   ```

2. **启动服务**
   ```bash
   docker-compose up -d
   ```

3. **查看日志**
   ```bash
   docker-compose logs -f
   ```

### macOS服务配置

使用launchd配置为系统服务：

```bash
# 方法一：使用安装脚本（推荐，自动配置路径）
./mrrc_setup.sh install

# 方法二：手动配置
# 1. 编辑 com.user.mrrc.plist，替换 {{INSTALL_DIR}} 为实际路径
# 2. 复制到 LaunchAgents 目录
cp com.user.mrrc.plist ~/Library/LaunchAgents/
# 3. 加载服务
launchctl load ~/Library/LaunchAgents/com.user.mrrc.plist
```

**服务管理命令：**
```bash
# 启动服务
launchctl start com.user.mrrc

# 停止服务
launchctl stop com.user.mrrc

# 查看服务状态
launchctl list | grep mrrc

# 卸载服务
launchctl unload ~/Library/LaunchAgents/com.user.mrrc.plist
```

服务配置文件：`com.user.mrrc.plist`
- 自动启动：RunAtLoad = true
- 保持运行：KeepAlive = true
- 日志输出：mrrc_service.log, mrrc_service_error.log
- 工作目录：自动检测（通过 `mrrc_setup.sh` 配置）

## 部署与配置指南

### 目录结构与路径说明

MRRC 采用相对路径设计，所有脚本和配置文件都支持在任何目录下运行：

```
MRRC/
├── mrrc_control.sh      # 主控制脚本（自动检测目录）
├── mrrc_setup.sh        # 安装脚本（自动检测目录）
├── mrrc_monitor.sh      # 监控脚本（自动检测目录）
├── com.user.mrrc.plist  # launchd 服务模板（需要配置）
├── MRRC.conf            # 主配置文件
└── certs/               # TLS 证书目录
    ├── fullchain.pem    # 证书链（必需）
    └── radio.vlsc.net.key  # 私钥文件（必需）
```

### 证书配置与更换

#### 证书文件位置

证书文件存放在 `certs/` 目录下，在 `MRRC.conf` 中配置：

```ini
[SERVER]
port = 8877
certfile = certs/radio.vlsc.net.pem    # 证书文件路径（相对路径）
keyfile = certs/radio.vlsc.net.key     # 私钥文件路径（相对路径）
```

#### 更换证书步骤

1. **准备证书文件**：
   - 从证书颁发机构获取证书文件
   - 确保证书格式为 PEM 格式

2. **替换证书文件**：
   ```bash
   # 备份旧证书
   cd certs/
   cp radio.vlsc.net.pem radio.vlsc.net.pem.backup
   cp radio.vlsc.net.key radio.vlsc.net.key.backup
   
   # 替换为新证书
   # 方式一：直接覆盖
   cp 新证书.pem radio.vlsc.net.pem
   cp 新私钥.key radio.vlsc.net.key
   
   # 方式二：修改配置文件指向新证书
   # 编辑 MRRC.conf，修改 certfile 和 keyfile 路径
   ```

3. **验证证书**：
   ```bash
   # 检查证书格式
   openssl x509 -in certs/radio.vlsc.net.pem -text -noout
   
   # 检查证书链完整性
   openssl verify -CAfile certs/fullchain.pem certs/radio.vlsc.net.pem
   
   # 检查私钥是否匹配
   openssl x509 -noout -modulus -in certs/radio.vlsc.net.pem | openssl md5
   openssl rsa -noout -modulus -in certs/radio.vlsc.net.key | openssl md5
   # 两个 MD5 值应该相同
   ```

4. **重启服务**：
   ```bash
   ./mrrc_control.sh restart
   ```

#### 证书文件命名规范

为保持配置延续性，建议采用以下命名规范：

| 文件类型 | 推荐命名 | 说明 |
|---------|---------|------|
| 服务器证书 | `radio.vlsc.net.pem` | 与配置文件一致 |
| 私钥文件 | `radio.vlsc.net.key` | 与配置文件一致 |
| 证书链 | `fullchain.pem` | 包含中间证书 |
| 根证书 | `root.pem` | 可选，用于验证 |

如果使用不同的域名，可以：
1. 重命名证书文件为统一名称
2. 或者修改 `MRRC.conf` 中的路径配置

### 硬件设备配置

#### 电台串口设备

电台串口设备路径因系统和设备而异，在 `MRRC.conf` 和 `mrrc_control.sh` 中配置：

**查找设备路径：**
```bash
# macOS
ls /dev/cu.* /dev/tty.*

# Linux
ls /dev/ttyUSB* /dev/ttyACM*
```

**配置示例：**
```ini
# MRRC.conf
[HAMLIB]
rig_pathname = /dev/cu.usbserial-230
rig_model = IC_M710
rig_rate = 4800
stop_bits = 2
```

```bash
# mrrc_control.sh
RIGCTL_DEVICE="/dev/cu.usbserial-120"
```

#### 音频设备

音频设备名称在 `MRRC.conf` 中配置：

```ini
[AUDIO]
outputdevice = USB Audio CODEC
inputdevice = USB Audio CODEC
```

**查找音频设备：**
```bash
python3 -c "
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print(f'{i}: {info[\"name\"]} (in:{info[\"maxInputChannels\"]}, out:{info[\"maxOutputChannels\"]})')
p.terminate()
"
```

### 跨平台部署

MRRC 支持 macOS 和 Linux 系统，主要差异：

| 项目 | macOS | Linux |
|------|-------|-------|
| 串口设备 | `/dev/cu.*` | `/dev/ttyUSB*` |
| launchd | 支持 | 使用 systemd |
| 服务目录 | `~/Library/LaunchAgents/` | `/etc/systemd/system/` |

**Linux systemd 服务配置示例：**
```ini
# /etc/systemd/system/mrrc.service
[Unit]
Description=MRRC Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/mrrc
ExecStart=/usr/bin/python3 /opt/mrrc/MRRC
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Linux 服务管理
sudo systemctl enable mrrc
sudo systemctl start mrrc
sudo systemctl status mrrc
```

### 移动端访问

- **现代界面**：访问 `https://<你的域名或IP>/mobile_modern.html`
- **经典界面**：访问 `https://<你的域名或IP>/mobile.html`
- 支持iPhone 15、iPhone 14、Android等移动设备
- 建议使用iOS Safari或Chrome浏览器
- 支持添加到主屏幕作为PWA应用

## ATR-1000 功率计/天调集成

### 功能概述
ATR-1000 是一款自动天调设备，支持功率测量和SWR监测。MRRC 系统通过独立代理程序与 ATR-1000 设备通信，实现移动端发射时的实时功率和 SWR 显示。

### 核心功能
- **实时功率显示**：发射时显示前向功率（0-200W）
- **SWR 监测**：实时显示驻波比（1.0-9.99）
- **继电器状态**：显示 LC/CL 组合、电感、电容值
- **天调存储**：自动记录频率与天调参数的对应关系
- **连接预热**：页面加载时预先建立连接，PTT 响应<200ms

### 架构设计

```
┌─────────────────┐
│  移动端浏览器    │
│ mobile_modern.js│
└────────┬────────┘
         │ WebSocket (/WSATR1000)
         ▼
┌─────────────────┐
│   MRRC 主程序    │
│ WS_ATR1000Handler│
└────────┬────────┘
         │ Unix Socket (/tmp/atr1000_proxy.sock)
         ▼
┌─────────────────┐
│ ATR-1000 代理    │
│ atr1000_proxy.py │
└────────┬────────┘
         │ WebSocket (192.168.1.63:60001)
         ▼
┌─────────────────┐
│  ATR-1000 设备   │
└─────────────────┘
```

### 启动方式

**方式一：使用控制脚本**
```bash
./mrrc_control.sh start-atr1000
```

**方式二：手动启动**
```bash
# 启动 ATR-1000 代理（后台运行）
python3 atr1000_proxy.py --device 192.168.1.63 --port 60001 &

# 或使用系统控制脚本
./mrrc_control.sh start
```

### 配置说明

ATR-1000 设备参数在 `atr1000_proxy.py` 中配置：
- `--device`: ATR-1000 设备 IP 地址（默认 192.168.1.63）
- `--port`: ATR-1000 WebSocket 端口（默认 60001）
- `--interval`: 数据请求间隔（默认 1.0 秒）

### 数据协议

**请求命令（前端 → 代理）**
```json
{"action": "start"}   // 开始数据流（TX 开始时发送）
{"action": "stop"}    // 停止数据流（TX 结束时发送）
```

**响应数据（代理 → 前端）**
```json
{
  "type": "atr1000_meter",
  "power": 100,        // 功率（瓦特）
  "swr": 1.25,         // 驻波比
  "vforward": 70.7,    // 前向电压
  "vreflected": 7.07,  // 反射电压
  "relay_status": {    // 继电器状态
    "lc": "LC",
    "inductance": 5,
    "capacitance": 3
  }
}
```

### 天调存储模块

`atr1000_tuner.py` 实现频率-参数自动匹配：
- 自动保存每次天调成功的参数
- 切换频率时自动查找最佳匹配
- 数据存储在 `atr1000_tuner.json`

### 性能优化

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| PTT 响应延迟 | ~2秒 | <200ms |
| 数据更新频率 | 1秒 | 500ms (TX期间) |
| 连接方式 | 按需连接 | 预热连接 |

**优化措施**：
1. 页面加载时预先建立 WebSocket 连接
2. TX 结束后保持连接不断开
3. 有客户端连接时每 2 秒发送 SYNC 预热
4. TX 期间每 500ms 发送 SYNC 确保数据流

### 故障排查

**问题：功率/SWR 不显示**
1. 检查 ATR-1000 代理是否运行：`ps aux | grep atr1000_proxy`
2. 检查代理日志：`tail -f atr1000_proxy.log`
3. 检查 Unix Socket：`ls -la /tmp/atr1000_proxy.sock`
4. 检查与设备连接：`curl http://192.168.1.63:60001/`

**问题：显示延迟**
1. 确认使用 V4.5.0+ 版本
2. 检查网络延迟
3. 查看浏览器控制台日志

## TX发射均衡器

### 功能概述
三段均衡器优化发射音频质量，适用于短波通信语音优化。

### 四种预设

| 预设 | 低频 | 中频 | 高频 | 适用场景 |
|------|------|------|------|----------|
| 默认 | 0dB | 0dB | 0dB | 无处理 |
| 短波语音 | +4dB | +6dB | -3dB | 常规短波通信 |
| 弱信号 | +6dB | +8dB | -6dB | DX弱信号通信 |
| 比赛模式 | +2dB | +4dB | -2dB | 快速通联 |

### 技术实现
- 音频链：micSource → eqLow → eqMid → eqHigh → gain_node → processor
- 使用Web Audio API BiquadFilter节点
- 预设自动保存到Cookie

## 移动端支持详解

### 功能特性
- **现代UI设计**：专为移动设备优化的界面
- **触摸优化**：大尺寸交互元素，舒适的拇指操作区域
- **PTT按钮**：底部居中的大按钮，支持长按和短按
- **频率显示**：清晰的数字分离显示
- **S表可视化**：实时信号强度显示（S0-S9+60dB）
- **功率/SWR显示**：ATR-1000实时功率与驻波比
- **连接状态指示**：WebSocket连接状态、传输状态
- **暗色模式**：适合夜间操作
- **菜单功能**：波段选择、模式切换、滤波器设置

### 技术实现
- **HTML5/CSS3/JavaScript**：现代Web技术栈
- **CSS Grid和Flexbox**：响应式布局
- **CSS Custom Properties**：主题定制
- **Web Audio API**：音频处理和播放
- **WebSocket API**：实时通信
- **Service Worker API**：离线支持和缓存
- **Touch Events API**：触摸事件处理
- **Vibration API**：触觉反馈
- **Safe Area Insets**：适配刘海屏和底部指示器

### PWA支持
- **应用清单**：manifest.json定义应用元数据
- **Service Worker**：sw.js实现离线缓存
- **添加到主屏幕**：支持作为独立应用运行
- **离线支持**：缓存关键资源，网络故障时可用
- **快速启动**：优化的启动流程

### 兼容性
- **设备支持**：
  - iPhone 15系列（主要目标）
  - iPhone 14, 13, 12系列
  - Android设备（现代浏览器）
  - iPad和平板设备
- **浏览器支持**：
  - Safari (iOS 16+)
  - Chrome (Android/iOS)
  - Firefox (Android/iOS)
  - Edge (Android/iOS)

## 音频优化详解

### 编码优化
- **Int16编码**：TX端使用Int16编码（50%带宽减少）
- **ADPCM压缩**：ADPCM自适应差分编码，50-60%压缩率
- **Opus编解码**：优化参数设置，提高音质
- **预热帧机制**：PTT按下时立即发送10个预热帧确保音频数据及时传输
- **采样率优化**：统一使用16kHz采样率
- **缓冲策略**：动态调整缓冲区深度适应网络条件
- **WebRTC最佳实践**：Opus编码参数优化（20ms帧长，复杂度5，DTX开启）

### 播放优化
- **AudioWorklet播放器**：降低主线程抖动
- **区间缓冲**：16/32帧配置，平衡延迟与稳定性
- **缓冲区清除**：TX释放时立即清除RX缓冲区
- **动态缓冲**：根据网络状况自动调整
- **丢包补偿**：智能处理网络抖动

### 音频流架构
- **TX流**：麦克风 → Web Audio API → Int16/ADPCM/Opus编码 → WebSocket → PyAudio → 电台
- **RX流**：电台 → PyAudio → Int16编码 → WebSocket → AudioWorklet → 扬声器
- **延迟控制**：端到端目标延迟<100ms
- **质量保证**：音频质量监控和自适应调整

### 音频测试文件
- `cq.wav`: CQ呼叫音频样本 (16kHz, 16bit, mono)
- `cq222.wav`: CQ呼叫音频样本2
- `cqcqcq123.wav`: CQ呼叫音频样本3
- `tune.wav`: 调谐音频样本 (16kHz, 16bit, mono)

## 延迟优化详解

### 问题分析
- 原始延迟：TX到RX切换需要2-3秒
- 主要原因：
  1. 缓冲区清除失败（错误的变量引用）
  2. PTT命令重复发送
  3. PTT确认机制延迟过高
  4. RX音频缓冲区过深

### 优化措施

#### 1. 缓冲区清除修复
- **文件**：`www/tx_button_optimized.js`
- **问题**：错误引用`RX_audiobuffer`变量
- **修复**：正确引用`AudioRX_source_node`进行缓冲区清除
- **影响**：关键修复，实现了正确的缓冲区管理

#### 2. PTT防抖机制
- **文件**：`www/controls.js`
- **实现**：添加全局PTT状态跟踪，50ms防抖延迟
- **好处**：防止重复PTT命令快速发送

#### 3. PTT确认机制优化
- **文件**：`www/controls.js`
- **优化**：
  - 初始确认延迟：50ms → 20ms
  - 重试间隔：100ms → 50ms
  - 重试次数：3 → 2
- **影响**：显著减少PTT命令处理时间

#### 4. RX音频缓冲区深度调整
- **文件**：
  - `www/rx_worklet_processor.js`：默认值 6/12 → 3/6帧
  - `www/controls.js`：配置值 32/64 → 16/32帧
- **好处**：更好的延迟和稳定性平衡

### 优化效果
- **切换延迟**：2-3秒 → <100ms（近乎瞬时）
- **PTT响应**：显著改善
- **音频播放延迟**：降低
- **用户体验**：大幅提升

## TCI协议支持

### 功能概述
- 支持Transceiver Control Interface协议
- 适用于支持TCI的电台型号
- 实现完整的TCI命令集
- 支持频率、模式、PTT控制
- 实时状态读取

### 实现文件
- `tci_client.py`：TCI协议客户端核心实现

### 支持的功能
- 频率读取和设置
- 模式切换
- PTT控制
- VFO控制
- S表读取
- 状态查询

## NanoVNA集成

### 功能概述
- 内置矢量网络分析仪Web界面
- 支持NanoVNA设备连接和控制
- 独立的PWA应用支持
- 离线测量功能

### 目录结构
```
nanovna/NanoVNA/
├── index.html          # 主界面
├── nanovna.js          # 控制逻辑
├── script.js           # 脚本支持
├── sw.js               # Service Worker
├── worker.js           # Web Worker
├── manifest.json       # PWA清单
├── images/             # 图标资源
└── lib/                # 依赖库
```

### 访问方式
- URL：`https://<你的域名或IP>/nanovna/NanoVNA/`
- 支持添加到主屏幕作为独立应用

## 常见问题排错

### 端口占用
```bash
lsof -iTCP:443 -sTCP:LISTEN -n -P
kill -9 <PID>
```

### 证书错误（bad end line）
```bash
# 规范换行
sed -e 's/\r$//' input.pem > output.pem

# 确认证书格式
cat certs/fullchain.pem | openssl x509 -text -noout
```

### TX按下不立即发射
1. 确认页面电源按钮已开启
2. 确认WebSocket已连接
3. 检查PTT预热帧机制
4. 查看浏览器控制台日志
5. 检查后端日志

### RX抖动
1. 保持16k端到端采样率一致
2. 调整Worklet缓冲（16/32或32/64）
3. 检查网络状况
4. 优化缓冲区深度

### TX到RX切换延迟
- 已优化至<100ms
- 如仍有问题，检查：
  - 缓冲区清除机制
  - PTT命令处理
  - 网络延迟
  - 详见延迟优化指南

### 移动端问题
1. **PTT按钮不响应**：检查麦克风权限
2. **连接失败**：验证WebSocket服务器可访问性
3. **布局问题**：检查viewport meta标签
4. **离线模式不工作**：检查Service Worker注册

### ATR-1000问题
1. **功率/SWR不显示**：检查代理进程和设备连接
2. **显示延迟**：确认使用V4.5.0+版本
3. **连接断开**：检查网络稳定性

## 系统架构设计

### 组件关系
- **前端**：HTML5界面 + WebSocket客户端
- **后端**：Tornado服务器 + WebSocket处理
- **音频**：PyAudio + Web Audio API + AudioWorklet
- **控制**：Hamlib/rigctld + TCI客户端
- **网络**：TLS加密
- **工具**：NanoVNA Web界面
- **ATR-1000**：独立代理 + 天调存储

### 接口协议
- **控制协议**：WebSocket + JSON
- **音频协议**：WebSocket + Int16/ADPCM/Opus
- **TCI协议**：标准TCI命令集
- **ATR-1000协议**：WebSocket + JSON

### 部署方案
- **单机部署**：所有组件运行在同一台机器
- **分布式部署**：前端、后端分离
- **容器化部署**：Docker容器封装
- **云部署**：VPS + TLS访问

## 性能指标

| 指标 | 数值 |
|------|------|
| TX延迟 | ~65ms |
| RX延迟 | ~51ms |
| TX→RX切换 | <100ms |
| PTT可靠性 | 99%+ |
| 功率显示延迟 | <200ms |
| 音频采样率 | 16kHz |
| 音频编码 | Int16/ADPCM/Opus |

## 许可证

本项目遵循 **GNU General Public License v3.0 (GPL-3.0)** 许可证。
基于 [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5) 开源项目进行开发和改进。

### 项目来源声明
- 原始项目：F4HTB/Universal_HamRadio_Remote_HTML5
- 改进内容：稳定性优化、架构升级、功能增强
- 分发要求：必须提供完整源代码并保留许可证和版权声明

## 版本历史

### V4.5.5 部署配置优化 (2026-03-06)

**主题：相对路径重构与部署指南完善**

#### 核心改进
- **相对路径重构**：所有脚本使用相对路径，支持任意目录部署
  - `mrrc_control.sh`：自动检测脚本所在目录
  - `mrrc_monitor.sh`：自动检测脚本所在目录
  - `mrrc_setup.sh`：自动检测脚本所在目录
- **launchd 服务模板化**：`com.user.mrrc.plist` 使用占位符，安装时自动替换
- **部署指南完善**：添加证书更换、硬件配置、跨平台部署说明

#### 证书配置优化
- 统一证书目录结构
- 提供详细的证书更换步骤
- 支持灵活的证书命名配置

#### 文件变更
- `mrrc_control.sh` - 使用 `$SCRIPT_DIR` 替代绝对路径
- `mrrc_monitor.sh` - 使用 `$SCRIPT_DIR` 替代绝对路径
- `mrrc_setup.sh` - 使用 `$SCRIPT_DIR` 并自动配置 launchd 服务
- `com.user.mrrc.plist` - 改为模板格式，使用 `{{INSTALL_DIR}}` 占位符
- `IFLOW.md` - 添加部署与配置指南章节

---

### V4.5.4 WebRTC 最佳实践优化 (2026-03-06)

**主题：基于 WebRTC 推荐参数优化 Opus 编码**

#### 核心改进
- **帧长优化**：40ms → 20ms（WebRTC 推荐值，更快响应）
- **编码复杂度**：默认 10 → 5（平衡 CPU 和音质）
- **DTX 静音检测**：开启（静音时不编码，释放 CPU）
- **帧大小**：640 → 320 samples（配合 20ms 帧长）

#### 预期效果
| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 处理频率 | 25次/秒 | 50次/秒 |
| CPU 占用 | 较高 | 降低 ~30% |
| 静音时 CPU | 全负载 | 几乎为零 |

#### 文件变更
- `www/controls.js` - Opus 编码器参数优化

---

### V4.5.3 TX 编码优化尝试 (2026-03-06)

**主题：TX 编码优化尝试与问题复盘**

#### 尝试方案
| 方案 | 内容 | 结果 |
|------|------|------|
| 简化 TX 处理 | 移除降采样和帧累积 | PTT 立即切回 RX |
| PCM 模式 | encode=0 | RX 全是噪音 |
| 降低码率 | 8kbps | 无改善 |

#### 问题根因
- `encode` 变量同时控制 TX 编码和 RX 解码
- `ScriptProcessorNode` 阻塞主线程影响 ATR-1000 响应

---

### V4.5.2 ATR-1000 通讯分析 (2026-03-06)

**主题：ATR-1000 通讯频率与数据同步机制分析**

#### 分析结果
- 前端 500ms sync 间隔已实现
- 后端批量广播机制正常
- ATR-1000 响应延迟与 TX 音频处理相关

---

### V4.5.1 频率调整按钮布局优化 (2026-03-06)

**主题：移动端频率调整按钮布局优化**

#### 核心改进
- **布局重设计**：从交叉排列改为上下分离
  - 上排：+50, +10, +5, +1（增加频率）
  - 下排：-50, -10, -5, -1（减少频率）
- **视觉优化**：统一浅灰背景，乳白色加粗文字
- **操作习惯**：符合"上加下减"的自然认知

#### 文件变更
- `www/mobile_modern.html` - 频率调整按钮HTML结构
- `www/mobile_modern.css` - 按钮样式优化

---

### V4.5.0 ATR-1000 实时功率显示稳定版 (2026-03-06)

**主题：ATR-1000 功率/SWR 实时显示完全稳定**

#### 核心改进
- **PTT 期间实时更新**：发射时功率/SWR 实时显示，延迟 <500ms
- **TUNE 模式同步**：天调模式同样支持实时功率显示
- **双重时间保护**：确保 sync 请求最小间隔 500ms，避免压垮设备
- **连接预热机制**：页面加载时预先建立连接，PTT 响应 <200ms

#### WebSocket 状态检查
- **防止错误发送**：检查 WebSocket 状态后再发送音频数据
- **避免 CLOSING/CLOSED 状态错误**：不再向已关闭连接发送数据

#### AudioWorklet 优化
- **欠载计数器重置**：PTT 释放时重置 AudioWorklet 欠载计数
- **日志清理**：减少不必要的控制台日志

#### 文件变更
- `www/controls.js` - WebSocket 状态检查
- `www/mobile_modern.js` - 双重时间保护、心跳优化
- `www/mobile_modern.html` - 版本号更新
- `www/rx_worklet_processor.js` - 欠载计数器重置

---

### V4.4.9 频率显示初始化优化 (2026-03-06)

**主题：刷新页面时从电台获取实际频率**

#### 修复内容
- **showTRXfreq 函数优化**：支持新的 5 位 kHz 移动端格式
- **WebSocket 连接时自动获取频率**：`wsControlTRXopen()` 发送 `getFreq:` 命令
- **向后兼容**：同时支持旧版 9 位 Hz 格式

#### 技术实现
- 页面加载 → WebSocket 连接 → 发送 `getFreq:` → 收到频率 → 调用 `showTRXfreq()` → 更新显示
- 新格式：`07053` = 7053 kHz（5 位数字）
- 旧格式：`007053000` = 7053000 Hz（9 位数字）

---

### V4.4.0 ATR-1000 实时显示重大修复 (2026-03-05)

**主题：解决长期存在的功率/SWR 显示延迟问题**

#### 问题分析
- **根因 1**：Tornado 的 `IOLoop.add_callback()` 会批处理消息，导致 2-5 秒延迟
- **根因 2**：WebSocket `write_message()` 必须在有事件循环的主线程中调用
- **根因 3**：前端 JavaScript 语法错误（`try` 缺少 `catch`）导致所有功能失效
- **根因 4**：过多的日志输出导致性能开销

#### 后端优化
- **批量广播机制**：50ms 批次收集消息，只广播最新数据
- **线程安全**：使用 `add_callback` 确保 WebSocket 线程安全通信
- **减少日志**：仅在功率/SWR 显著变化时记录日志

#### 前端修复
- **语法错误修复**：在 `_doUpdateDisplay()` 中添加缺失的 `catch` 块
- **移除节流**：直接 DOM 更新，不使用 RAF 或节流
- **错误处理**：添加 try-catch 块增强健壮性

---

### V4.3.0 ATR-1000架构分离 (2026-03-04)

**主题：独立ATR-1000代理提升性能**

#### 核心改进
- **ATR-1000独立代理程序**：`atr1000_proxy.py`
  - 独立进程，不阻塞MRRC主程序
  - Unix Socket通信 (`/tmp/atr1000_proxy.sock`)
  - 自动重连ATR-1000设备
  - 按需数据请求（仅当有客户端连接时）

- **MRRC中添加ATR-1000 WebSocket端点**
  - 路由 `/WSATR1000`
  - 通过Unix Socket桥接前端与独立代理

#### 性能改进
| 指标 | 改进前 | 改进后 |
|------|--------|--------|
| PTT释放延迟 | ~2秒 | <100ms |
| CPU占用 | 高 (0.3秒间隔) | 低 (1秒间隔+按需) |
| 架构 | 耦合 | 解耦独立进程 |

---

### V4.2.0 TX发射均衡器 (2026-03-02)

**主题：短波通信语音优化**

#### 核心改进
- **TX EQ系统**：三段均衡器优化发射音频
  - 低频增强 (lowshelf @ 200Hz)
  - 中频增强 (peaking @ 1000Hz)
  - 高频衰减 (highshelf @ 2500Hz)

#### 四种预设
| 预设 | 低频 | 中频 | 高频 | 适用场景 |
|------|------|------|------|----------|
| 默认 | 0dB | 0dB | 0dB | 无处理 |
| 短波语音 | +4dB | +6dB | -3dB | 常规短波通信 |
| 弱信号 | +6dB | +8dB | -6dB | DX弱信号通信 |
| 比赛模式 | +2dB | +4dB | -2dB | 快速通联 |

---

### V4.1.0 项目重命名 (2026-03-01)

**主题：Mobile First - MRRC品牌重塑**

#### 核心改进
- **项目更名**：从"Universal HamRadio Remote (MRRC)"更名为"Mobile Remote Radio Control (MRRC)"
- **设计理念**：Mobile First, Radio Anywhere - 随时随地，畅享业余无线电
- **文档国际化**：README支持中英文切换

---

### V4.0.0 里程碑版本 (2026-03-01)

**主题：性能优化与架构精简**

#### 核心改进
- **TX→RX切换延迟优化**：从2-3秒优化至<100ms
- **PTT可靠性增强**：双重触发机制 + 预热帧 + 超时保护
- **移动端界面重构**：iPhone 15优化，PWA支持，TUNE天调按钮
- **架构精简**：移除VPN功能，移除无效导航组件

#### 性能指标
| 指标 | V3.x | V4.0 |
|------|------|------|
| TX延迟 | ~100ms | ~65ms |
| RX延迟 | ~100ms | ~51ms |
| TX→RX切换 | 2-3秒 | <100ms |
| PTT可靠性 | 95% | 99%+ |

---

### 早期版本

- **V3.2 (2025-01)**: 移动端音频优化与TX→RX切换延迟修复
- **V3.1 (2025-01)**: 优化移动端音频和PTT功能
- **V3.0 (2024-12)**: 现代移动端界面（iPhone 15优化）、AAC/ADPCM音频编码支持、TCI协议支持、NanoVNA矢量网络分析仪集成
- **V2.0 (2024-11)**: 系统架构重构、AudioWorklet低延迟播放、Int16编码带宽优化
- **V1.0 (2024-10)**: 基于F4HTB项目的初始版本、基本的远程电台控制功能

## 贡献指南

### 开发环境
- Python 3.12+
- Node.js（可选，用于前端工具）
- Git版本控制
- macOS/类Unix系统

### 提交规范
- 清晰的提交信息
- 描述性的分支名称
- 代码审查
- 测试验证

### 文档维护
- 更新相关文档
- 记录重大变更
- 维护版本历史
- 提供使用说明

## 联系方式

- 项目主页：GitHub仓库
- 问题反馈：Issues
- 技术支持：社区论坛
- 文档：docs/目录

---

**最后更新**：2026年3月6日  
**文档版本**：v4.5.5  
**发布版本**：V4.5.5  
**维护者**：MRRC开发团队

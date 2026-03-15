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
- **专业降噪**：集成 WDSP 库，提供 NR2 频谱降噪、噪声抑制、自动陷波等 DSP 功能
- **随时随地访问**：互联网覆盖处即可操控您的电台
- **安全连接**：TLS加密传输，用户认证保护
- **完整控制**：频率、模式、PTT、天调等完整电台功能
- **AI语音助手**：Whisper语音识别 + Qwen3-TTS语音合成
- **CW实时解码**：ONNX前端推理，QSO状态机智能建议
- **多实例支持**：单服务器多电台独立控制

### 历史改进
- **增强的PTT可靠性机制**：按下即发送PTT命令，并立即发送预热帧确保后端收到音频数据
- **优化的TX/RX切换**：从2-3秒延迟优化至<100ms切换响应
- **移动端支持**：专门的移动界面，优化触摸交互和音频处理，支持iPhone 15等现代移动设备
- **AAC音频编码**：新增ADPCM自适应差分编码，支持50-60%压缩率
- **音频优化**：采用Int16编码（50%带宽减少），AudioWorklet低抖动播放
- **NanoVNA集成**：内置矢量网络分析仪Web界面支持
- **ATR-1000集成**：实时功率/SWR显示，天调存储功能
- **WebRTC最佳实践**：Opus编码参数优化，降低CPU占用
- **语音助手**：Whisper + Qwen3-TTS 完整集成
- **CW解码**：ONNX实时推理，QSO状态机
- **SDR界面**：全新现代SDR控制界面
- **多实例**：独立配置，独立天调学习

## 目录结构要点

```
MRRC/
├── MRRC                          # 后端主程序 (Tornado WebSocket服务器)
├── MRRC.conf                     # 系统核心配置文件
├── audio_interface.py            # PyAudio采集/播放封装与客户端分发
├── wdsp_wrapper.py               # WDSP数字信号处理库Python封装
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
├── DESIGN/                       # 工程设计文档 (Vibe-SDD方法论)
│   ├── MRRC_SDD.md               # 软件设计说明 (IBM TeamSD)
│   ├── SPEC.md                   # 项目规格说明书
│   ├── REQUIREMENTS.md           # 需求矩阵
│   ├── ARCH-DECISIONS.md         # 架构决策记录
│   ├── CONTEXT.md                # 系统上下文图
│   └── API.md                   # API接口文档
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
- **RX (接收)**: 电台音频 → 后端PyAudio采集 → **WDSP降噪处理(NR2/NB/ANF/AGC)** → Int16编码 → WebSocket传输 → 浏览器AudioWorklet播放
- 采样率：48kHz（WDSP处理）/ 16kHz（传输），格式：Int16（50%带宽优化），目标延迟：<100ms
- 支持Int16编码和Opus编码双模式
- 支持ADPCM压缩编码
- **DSP降噪**：集成WDSP库，提供专业的NR2频谱降噪、噪声抑制、自动陷波等功能

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

## ATR-1000 天调智能学习与快速调谐模块

### 功能概述

ATR-1000 是一款自动天调设备，MRRC 系统实现了与其的深度集成，提供以下核心功能：

| 功能 | 说明 |
|------|------|
| 实时功率显示 | 发射时显示前向功率（0-200W） |
| SWR 监测 | 实时显示驻波比（1.0-9.99） |
| 智能学习 | 发射时自动记录频率与天调参数对应关系 |
| 快速调谐 | 切换频率时自动应用已学习的天调参数 |
| 参数持久化 | 学习记录保存在 JSON 文件，重启后自动加载 |

### 通信架构

```
┌─────────────────┐
│  移动端浏览器    │
│ mobile_modern.js│
└────────┬────────┘
         │ WebSocket (/WSATR1000)
         ▼
┌─────────────────┐
│   MRRC 主程序    │
│ 频率同步接口     │◄──── setFreq/getFreq 时同步频率
└────────┬────────┘
         │ Unix Socket (/tmp/atr1000_proxy.sock)
         ▼
┌─────────────────┐
│ ATR-1000 代理    │
│ atr1000_proxy.py │◄──── 天调学习与快速调谐逻辑
└────────┬────────┘
         │ WebSocket (192.168.1.63:60001)
         ▼
┌─────────────────┐
│  ATR-1000 设备   │
└─────────────────┘
```

### 通信协议详解

#### 基本帧格式

```
┌──────┬──────┬──────┬─────────────┐
│ FLAG │ CMD  │ LEN  │ DATA...     │
│ 0xFF │ 1字节│ 1字节│ LEN 字节    │
└──────┴──────┴──────┴─────────────┘
```

#### 命令类型

| 命令 | 值 | 方向 | 说明 |
|------|-----|------|------|
| SYNC | 0x01 | 请求 | 触发设备返回数据 |
| METER_STATUS | 0x02 | 响应 | 功率/SWR 状态 |
| RELAY_STATUS | 0x05 | 双向 | 继电器状态（读取/设置） |
| START_TUNE | 0x06 | 请求 | 启动自动调谐 |

#### 继电器状态帧解析（关键修正）

**响应格式**：`FF 05 07 DATA...`

```
偏移:  [3]   [4]   [5]   [6]
数据:  SW    ?     CAP   IND
```

| 字段 | 偏移 | 说明 |
|------|------|------|
| SW | data[3] | 网络类型：**0=LC，1=CL** |
| CAP | data[5] | 电容索引 |
| IND | data[6] | 电感索引 |

**示例数据解析**：

| 原始数据 | data[3] | SW类型 | data[5] CAP | data[6] IND |
|----------|---------|--------|-------------|-------------|
| `ff05070001090a005a00` | 00 | LC | 09 (90pF) | 0a (0.1uH) |
| `ff050701031b1e000e01` | 01 | CL | 1b (270pF) | 1e (0.3uH) |

#### IND/CAP 值转换规则

| 参数 | 存储值 | 发送值 | 设备显示 |
|------|--------|--------|----------|
| IND | 10 | 10÷10=1 | 0.1uH |
| IND | 30 | 30÷10=3 | 0.3uH |
| CAP | 9 | 9 | 90pF |
| CAP | 27 | 27 | 270pF |

**重要规则**：
- **IND 发送时需要除以 10**
- **CAP 发送时直接使用原值**

#### 设置继电器命令

**发送格式**：`FF 05 03 SW IND CAP`

```python
# 示例：设置 CL 网络，L=0.3uH，C=270pF
# 存储值: sw=1, ind=30, cap=27
# 发送值: sw=1, ind=3, cap=27
cmd = bytes([0xFF, 0x05, 0x03, 1, 3, 27])
```

### 智能学习机制

#### 学习条件

发射时自动学习，需同时满足：
1. **SWR 良好**：SWR 在 1.0 ~ 1.5 之间
2. **功率足够**：前向功率 > 5W
3. **样本积累**：连续 5 次采样满足条件才记录

#### 学习流程

```
开始发射
    │
    ▼
获取当前频率（从 MRRC 同步）
    │
    ▼
每 500ms 采样一次
    │
    ▼
SWR ≤ 1.5 且 Power > 5W?
    │
    ├─ 是 ─→ 累积样本
    │         │
    │         ▼
    │     样本数 ≥ 5?
    │         │
    │         ├─ 是 ─→ 记录/更新天调参数
    │         │
    │         └─ 否 ─→ 继续采样
    │
    └─ 否 ─→ 重置样本计数
    │
    ▼
结束发射
```

#### 存储数据结构

```json
{
  "version": "2.0",
  "records": [
    {
      "freq": 7050000,
      "sw": 1,
      "ind": 30,
      "cap": 27,
      "swr_avg": 1.08,
      "sample_count": 201
    }
  ]
}
```

### 快速调谐机制

#### 频率同步

MRRC 主程序在以下时机同步频率给 ATR 代理：

```python
# MRRC 主程序中的调用点
elif(action == "getFreq"):
    freq = CTRX.getFreq()
    yield self.send_to_all_clients("getFreq:"+str(freq))
    sync_freq_to_atr1000(freq)  # 同步频率

elif(action == "setFreq"):
    freq = CTRX.setFreq(datato)
    yield self.send_to_all_clients("getFreq:"+str(freq))
    sync_freq_to_atr1000(freq)  # 同步频率
```

#### 调谐流程

```
收到频率同步
    │
    ▼
查找存储记录（±10kHz 容差）
    │
    ├─ 找到 ─→ 发送继电器设置命令
    │           │
    │           ▼
    │       设备应用参数
    │           │
    │           ▼
    │       日志: 🎯 快速调谐: 7050.0kHz -> CL, L=30, C=27
    │
    └─ 未找到 ─→ 等待用户手动调谐
```

### 节流保护

防止频繁操作导致设备重启：

```python
def set_relay_with_throttle(sw, ind, cap):
    # 相同参数不重复发送
    # 最小发送间隔 5 秒
    if 参数变化 or 距上次 > 5秒:
        发送命令
```

### 启动与配置

**启动命令**：
```bash
# 使用控制脚本
./mrrc_control.sh start-atr1000

# 或完整启动
./mrrc_control.sh start
```

**配置参数**（在 `atr1000_proxy.py` 中）：
- `--device`: ATR-1000 设备 IP（默认 192.168.1.63）
- `--port`: WebSocket 端口（默认 60001）

### API 接口

| Action | 参数 | 说明 |
|--------|------|------|
| start | - | 开始数据流（TX 开始时） |
| stop | - | 停止数据流（TX 结束时） |
| set_freq | freq | 同步频率 |
| set_relay | sw, ind, cap | 设置继电器 |
| get_records | - | 获取学习记录 |
| delete_record | freq | 删除指定记录 |

### 调试日志

```
🎛️ 继电器原始: ff050701031b1e000e01 | SW=CL, L=30, C=27
📝 学习成功: 7050.0kHz, SWR=1.08, CL, L=30, C=27
🎯 快速调谐: 7050.0kHz -> SW=CL, L=30, C=27
```

### 故障排查

**功率/SWR 不显示**：
```bash
ps aux | grep atr1000_proxy  # 检查代理进程
tail -f atr1000_proxy.log    # 查看日志
ls -la /tmp/atr1000_proxy.sock  # 检查 Socket
```

**天调参数不正确**：
1. 检查日志中的原始数据和解析结果
2. 确认 SW 值：0=LC，1=CL
3. 确认 IND 发送值需除以 10

### 相关文件

| 文件 | 说明 |
|------|------|
| `atr1000_proxy.py` | ATR-1000 代理主程序 |
| `atr1000_tuner.py` | 天调存储模块 |
| `atr1000_tuner.json` | 学习记录存储文件 |
| `MRRC` | 主程序（含频率同步接口） |
| `docs/ATR1000_Tuner_Auto_Learning.md` | 完整技术文档 |

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

## WDSP 数字信号处理详解

### 功能概述

MRRC 集成 **WDSP (Warren Pratt's Digital Signal Processing)** 库，这是 OpenHPSDR 项目的高性能 DSP 库，被广泛应用于 Thetis、piHPSDR 等专业业余无线电软件中。

相比 RNNoise 等通用降噪算法，WDSP 专门针对**短波 SSB 语音通信**优化，提供更好的语音保真度和降噪效果。

### 核心功能

| 功能 | 算法 | 效果 | 推荐使用 |
|------|------|------|----------|
| **NR2** | 频谱降噪 (Spectral) | 15-20dB 降噪，语音保真度极高 | **✅ SSB语音（推荐）** |
| NR | LMS自适应 | 10-15dB 降噪，计算量小 | 通用背景噪声 |
| NB | 噪声抑制器 | 消除脉冲干扰 | 电器火花、雷电干扰 |
| ANF | 自动陷波 | 消除单频干扰 | CW报音、载波干扰 |
| AGC | 自动增益 | 4种模式可选 | 稳定输出电平 |

### 处理流程

```
电台音频 (48kHz Float32)
    ↓
DC去除 → AGC预放大 → 软削波
    ↓
Int16转换 (48kHz)
    ↓
WDSP处理
    ├── NR2 频谱降噪
    ├── NB 噪声抑制
    ├── ANF 自动陷波
    └── AGC 自动增益控制
    ↓
Opus编码 (16kHz)
    ↓
WebSocket传输
```

### 配置参数 (MRRC.conf)

```ini
[WDSP]
enabled = True              # 启用WDSP
sample_rate = 48000         # 采样率（推荐48kHz）
buffer_size = 256           # 缓冲区大小
nr2_enabled = True          # 频谱降噪
nb_enabled = True           # 噪声抑制
anf_enabled = False         # 自动陷波
agc_mode = 3                # AGC模式 (0=OFF, 1=LONG, 2=SLOW, 3=MED, 4=FAST)
bandpass_low = 300.0        # 低切频率
bandpass_high = 2700.0      # 高切频率
```

### 与RNNoise对比

| 特性 | WDSP (NR2) | RNNoise |
|------|-----------|---------|
| 算法类型 | 频谱减法 | 神经网络 |
| 降噪深度 | 15-20 dB | 10-15 dB |
| 语音保真度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| SSB优化 | ✅ 专门优化 | ❌ 通用语音 |
| 延迟 | < 20ms | 30-50ms |
| 参数可调 | ✅ 多项参数 | ❌ 固定模型 |

**结论**: 对于短波 SSB 语音通信，WDSP 明显优于 RNNoise。

### 安装WDSP库

**macOS:**
```bash
cd /tmp && git clone https://github.com/g0orx/wdsp.git
cd wdsp && make
sudo cp libwdsp.dylib /usr/local/lib/
```

**Linux:**
```bash
cd /tmp && git clone https://github.com/g0orx/wdsp.git
cd wdsp && make
sudo cp libwdsp.so /usr/local/lib/ && sudo ldconfig
```

### 前端控制

在移动端界面"设置"菜单中，可实时控制：
- WDSP 主开关
- NR2 频谱降噪
- NB 噪声抑制
- ANF 自动陷波
- AGC 模式选择

### 技术实现

**Python封装**: `wdsp_wrapper.py`
- 使用 `ctypes` 调用 WDSP C 库
- 提供 `WDSPProcessor` 类封装处理逻辑
- 支持动态参数调整

**集成位置**: `audio_interface.py`
- 在 Int16 转换后、Opus 编码前执行
- 48kHz 采样率处理，保持音质
- 与 PyAudioCapture 线程集成

### 故障排查

**WDSP未加载:**
```
⚠️ WDSP 已启用但库不可用
```
解决: 重新编译安装 libwdsp 到 /usr/local/lib/

**无音频输出:**
- 正常现象，WDSP需要约10帧预热（ring buffer机制）

**效果不明显:**
- 检查 `enabled = True` 和 `nr2_enabled = True`
- 调整带通滤波器频率匹配当前模式

---

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

### V4.5.12 ATR-1000 代理主动轮询与假死重连 (2026-03-07)

**主题：解决 ATR-1000 设备连接不稳定问题**

#### 问题分析
- 设备 WebSocket 连接后可能出现"假死"状态（TCP 连接正常但无数据）
- 原被动模式依赖前端心跳，设备无响应时无法自动恢复
- 1 秒 SYNC 间隔对设备压力过大

#### 核心改进
- **主动轮询模式**：代理主动定时发送 SYNC（2 秒间隔），保持数据流活跃
- **假死检测与重连**：检测到设备长时间无响应时主动关闭 WebSocket 触发重连
- **降低 SYNC 频率**：从 1 秒改为 2 秒，减少设备压力
- **前端 sync 仍有效**：前端 sync 命令立即广播缓存数据

#### 文件变更
- `atr1000_proxy.py` - 主动轮询、假死重连、SYNC 间隔优化

---

### V4.5.11 ATR-1000 功率/SWR 同步深度优化 (2026-03-07)

**主题：深度分析并修复功率/SWR 显示不流畅问题**

#### 问题诊断
| 环节 | 问题 | 影响 |
|------|------|------|
| 代理去重间隔 | 1.3秒太长 | 数据刷新慢 |
| 广播触发 | 只在数据变化时广播 | 数据不变时不更新 |
| sync响应 | 只发命令，不主动回数据 | 前端等设备响应 |
| 设备无响应 | 设备离线时无数据 | 前端显示空白 |

#### 核心修复
1. **去重间隔优化**：从 1.3 秒降低到 0.2 秒（提升 6.5 倍刷新率）
2. **sync 立即响应**：前端发 sync 后立即广播缓存数据，不等待设备
3. **设备离线友好**：即使设备无响应，前端也能看到最后已知状态

#### 文件变更
- `atr1000_proxy.py` - 去重间隔优化、sync 立即广播缓存数据

---

### V4.5.10 数据稳定性增强 (2026-03-07)

**主题：数据平滑与设备状态监测**

#### 核心改进
- **数据平滑处理**：smoothFactor = 0.3，避免数值跳变
- **数据超时检测**：3 秒无数据标记设备离线
- **设备状态指示**：● 在线 / ○ 离线
- **忽略数据保护**：PTT 释放后 500ms 内忽略新数据

#### 文件变更
- `www/mobile_modern.js` - 数据平滑、超时检测、状态指示

---

### V4.5.9 动态 Sync 间隔 (2026-03-07)

**主题：平衡刷新速度与设备压力**

#### 核心改进
- **动态间隔**：平时 500ms，PTT/TUNE 期间 200ms
- **更快检查**：心跳检查间隔从 200ms 降到 50ms

#### 文件变更
- `www/mobile_modern.js` - 动态 sync 间隔

---

### V4.5.8 TUNE 功率清零修复 (2026-03-07)

**主题：修复 TUNE 释放后功率不清零问题**

#### 问题根因
- `stopTune()` 没有调用 `ATR1000.onTXStop()` 和 `clearDisplay()`
- `startTune()` 没有调用 `onTXStart()`，导致 `_txActive` 始终为 false

#### 文件变更
- `www/controls.js` - 添加 TUNE 相关 ATR-1000 调用
- `www/tx_button_optimized.js` - 添加 PTT 释放时清零显示

---

### V4.5.13 ATR-1000 代理 SYNC 机制优化 (2026-03-07)

**主题：深入分析设备通讯协议，优化 SYNC 机制**

#### 关键发现
经过深入测试分析，发现 ATR-1000 设备通讯特性：
- **设备需要 SYNC 命令**：设备不会主动推送数据，必须发送 SYNC 命令才会返回数据
- **SYNC 返回完整状态**：发送一次 SYNC，设备返回所有状态数据（功率、SWR、继电器状态、存储信息等）
- **单次响应**：设备只返回一次数据，不会持续推送，需要定期发送 SYNC 更新

#### 核心优化
- **连接后延迟发送 SYNC**：延迟 0.3 秒发送初始 SYNC，确保连接稳定
- **SYNC 最小间隔降低**：从 1.0 秒降低到 0.5 秒，设备响应快可更频繁更新
- **简化日志输出**：减少不必要的日志，降低噪音
- **保持健康检查**：10 秒无响应触发重连

#### 技术细节
```
连接流程：
1. WebSocket 连接成功
2. 延迟 0.3 秒发送初始 SYNC
3. 设备返回所有状态数据
4. 前端定期发送 sync 命令（0.5 秒间隔）
5. 代理转发 SYNC 到设备并广播返回数据
```

#### 文件变更
- `atr1000_proxy.py` - 优化 SYNC 机制，降低节流间隔

---

### V4.5.16 ATR-1000 天调智能学习与快速调谐 (2026-03-08)

**主题：ATR-1000 协议修正与智能调谐**

#### 核心功能
- **智能学习**：发射时自动记录频率与天调参数（SW、IND、CAP）的对应关系
- **快速调谐**：切换频率时自动应用已学习的天调参数
- **频率同步**：MRRC 主程序实时同步频率给 ATR 代理
- **参数持久化**：学习记录保存在 `atr1000_tuner.json`，重启后自动加载

#### 协议修正
通过实际测试修正了 ATR-1000 协议解析：

| 项目 | 修正前 | 修正后 |
|------|--------|--------|
| SW 字段位置 | data[4] | data[3] |
| SW 映射 | 0=CL, 1=LC | 0=LC, 1=CL |
| IND 发送值 | 直接发送 | 原值÷10 |
| CAP 发送值 | 原值×10 | 直接发送 |

#### 文件变更
- `atr1000_proxy.py` - 修正协议解析，添加频率同步接口
- `atr1000_tuner.py` - 天调存储模块
- `atr1000_tuner.json` - 学习记录存储
- `MRRC` - 添加 `sync_freq_to_atr1000()` 频率同步函数
- `docs/ATR1000_Tuner_Auto_Learning.md` - 完整技术文档

---

### V4.5.17 ATU 天调系统修复与优化 (2026-03-08)

**主题：数据解析修正、参数统一、微调改存储调谐、第三方软件联动**

#### 数据解析修复
通过用户实际测试数据修正 RELAY_STATUS 解析：

| 字段 | 修正前位置 | 修正后位置 | 说明 |
|------|-----------|-----------|------|
| SW | data[4] | data[3] | 网络类型 (0=LC, 1=CL) |
| IND | data[5] | data[4] | 电感索引 (如 47=4.7uH) |
| CAP | data[6] | data[5] | 电容索引 (如 79=790pF) |

#### 数据清理
- 清理 JSON 中 6 条脏数据（sw=3/sw=47 等无效值）
- 保留 136 条有效学习记录

#### 参数调用统一
- 统一 `set_relay()` 调用参数顺序为 `(sw, ind, cap)`
- 修复三处调用点：
  - 第477行：自动调谐
  - 第503行：快速调谐  
  - 第603行：手动设置

#### 微调模式改为存储调谐
`_fine_tune()` 方法从扫描模式改为存储调谐模式：
- **原逻辑**：分三步扫描 L/C（约63次测试）
- **新逻辑**：从映射表获取参数直接应用（1-2次）
- 存储参数不达标时回退到初始参数

#### SWR 过滤增强
- 学习逻辑排除 SWR=1.0 假数据（阈值 1.01）
- 保存结果限制 SWR 在 1.01-2.0 范围内

#### 第三方软件联动支持（JTDX/flrig等）
**功能**：支持通过 rigctld 与 JTDX、flrig、wfview 等第三方软件联动

**实现原理**：
- MRRC 定期（每 0.5 秒）从 rigctld 读取当前频率
- 同步频率给 ATR-1000 代理，触发天调快速调谐
- 无需打开 MRRC 网页界面，频率变更自动同步

**使用场景**：
- JTDX 自动模式切换频率时，天调自动跟随
- flrig 手动调整频率时，天调自动跟随
- wfview 控制电台时，天调自动跟随

**配置要求**：
- 所有软件连接同一个 rigctld 实例
- MRRC 保持运行状态（后台即可）

#### 文件变更
- `atr1000_proxy.py` - 修正 RELAY_STATUS 解析，统一 set_relay 调用
- `atr1000_tuner.json` - 清理脏数据
- `atu_auto_tuner.py` - 微调改存储调谐
- `MRRC` - 添加定期频率同步给 ATR-1000 代理
- `CHANGELOG.md` - 版本发布说明

---

### V4.6.0 WDSP 数字信号处理集成 (2026-03-09)

**主题：集成专业业余无线电DSP库，替代RNNoise成为默认降噪方案**

#### 核心功能
- **WDSP库集成**: 集成OpenHPSDR项目的WDSP库，提供专业级DSP功能
- **NR2频谱降噪**: 基于谱减法的降噪算法，专门针对SSB语音优化
- **NB噪声抑制**: 消除脉冲干扰（电器火花、雷电等）
- **ANF自动陷波**: 自动消除单频干扰（CW报音、载波干扰）
- **AGC自动增益**: 4种模式（LONG/SLOW/MED/FAST）适应不同场景
- **带通滤波器**: 可配置低切/高切频率，默认300-2700Hz SSB优化

#### 架构改进
- **处理流程**: 48kHz采样率WDSP处理 → 16kHz Opus编码传输
- **替换RNNoise**: WDSP成为默认降噪方案，RNNoise降级为可选
- **前端控制**: 移动端设置面板实时控制所有DSP参数
- **WebSocket命令**: 支持动态开启/关闭各项DSP功能

#### 性能对比
| 特性 | WDSP (NR2) | RNNoise |
|------|-----------|---------|
| 降噪深度 | 15-20 dB | 10-15 dB |
| 语音保真度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| SSB优化 | ✅ 专门优化 | ❌ 通用语音 |
| 延迟 | < 20ms | 30-50ms |

#### 文件变更
- `wdsp_wrapper.py` - WDSP Python封装（新增）
- `audio_interface.py` - 集成WDSP到RX音频处理链
- `MRRC` - 添加WebSocket控制命令
- `www/mobile_modern.js` - 前端WDSP控制面板
- `www/mobile_modern.css` - WDSP UI样式
- `www/controls.js` - WebSocket消息处理
- `MRRC.conf` - WDSP配置段

#### 配置迁移
```ini
# 旧配置（RNNoise）
[RNNOISE]
enabled = True  # 改为 False

# 新配置（WDSP）
[WDSP]
enabled = True  # 默认启用
nr2_enabled = True
nb_enabled = True
agc_mode = 3
```

---

### V4.5.19 TX 音频优化 - 抗混叠滤波与短波语音 EQ (2026-03-08)

**主题：解决移动端发射声音尖锐问题**

#### 问题分析
- **根因**：降采样混叠 (Aliasing)
  - iPhone 麦克风采样率 48kHz，可记录高达 24kHz
  - 系统降采样到 16kHz，Nyquist 频率只有 8kHz
  - 8-24kHz 高频成分折叠到 0-8kHz，导致声音尖锐
- **iPhone 麦克风特性**：内置高频强调，进一步加剧问题

#### 核心改进
- **抗混叠低通滤波器**：6kHz lowpass，在降采样前滤除高频
- **TX EQ 重新设计**：针对短波通信 100-2700Hz 语音频段优化
  - 低频 <100Hz：衰减 -15 ~ -20 dB（减少超低频噪声）
  - 中频 1500Hz：增强 +6 ~ +10 dB（提高语音清晰度）
  - 高频 >2700Hz：衰减 -15 ~ -25 dB（减少尖锐音）

#### TX EQ 预设
| 预设 | 低频 <100Hz | 中频 1500Hz | 高频 >2700Hz | 用途 |
|------|-------------|-------------|--------------|------|
| 默认 | 0 dB | 0 dB | 0 dB | 无处理 |
| 短波语音 | -20 dB | +6 dB | -20 dB | 标准短波通信 |
| 手机优化 | -15 dB | +8 dB | -24 dB | 手机麦克风专用 |
| 弱信号 | -20 dB | +10 dB | -25 dB | DX 最大可读性 |
| 比赛模式 | -15 dB | +6 dB | -15 dB | 快速通联 |

#### 文件变更
- `www/controls.js` - 添加抗混叠滤波器，重新设计 TX EQ
- `www/mobile_modern.js` - 更新 TX EQ 面板预设和说明
- `www/test_aliasing.html` - 混叠测试页面（新增）

---

### V4.5.18 ATR-1000 优化与 API Server 重构 (2026-03-07)

**主题：动态轮询间隔与 API Server 架构修复**

#### 核心改进
- **动态轮询间隔**：
  - 空闲时：15秒一次
  - 有客户端连接时：5秒一次
  - TX 期间：0.5秒一次
- **API Server 重构**：使用 Unix Socket 连接独立代理，避免直接连接设备
- **半双工音频修复**：TX 时停止 RX 数据发送，避免自激回声

#### 文件变更
- `atr1000_proxy.py` - 动态轮询间隔
- `atr1000_api_server.py` - 重构为使用 Unix Socket
- `audio_interface.py` - 半双工音频优化

---

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

### V4.9.1 多实例支持深度优化 (2026-03-15)

**多实例架构修复**:
- **配置键大小写修复**: 修复 ConfigParser 键名大小写问题
  - `INSTANCE_UNIX_SOCKET` → `instance_unix_socket`
- **Socket 路径修复**: 修复硬编码的 Unix Socket 路径
  - `sync_freq_to_atr1000` 函数现在使用 `INSTANCE_UNIX_SOCKET` 配置

#### 文件变更
- `MRRC` - 配置键和 Socket 路径修复

---

### V4.9.0 语音助手、CW模式、SDR界面 (2026-03-14)

**语音文字助手**:
- 新增 `voice_assistant_service.py` 后端服务
- 集成 Whisper ASR 语音识别（支持中文/英文）
- 集成 Qwen3-TTS 语音合成
- 新增移动端界面: `mobile_voice_text.html`
- 新增移动端语音助手界面: `mobile_voice_assistant.html`

**CW 电波模式**:
- 新增 CW DSP 界面: `cw_dsp.html`
- 新增 CW 信号发生器: `cw_generator.html`
- 新增 CW 实时解码: `cw_live.html`
- 新增 CW 简单测试: `cw_simple.html`
- 新增 CW 测试页面: `cw_test.html`
- ONNX 前端推理 (<2MB)，双模式架构

**SDR 现代界面**:
- 全新 SDR 控制界面: `sdr_modern.html`
- 配套 JavaScript: `sdr_modern.js`
- 配套样式: `sdr_modern.css`

**多实例支持**:
- 单服务器运行多个独立实例
- 各电台独立控制
- 差异化天调参数学习

---

**最后更新**：2026年3月16日  
**文档版本**：v4.9.3  
**发布版本**：V4.9.3  
**维护者**：MRRC开发团队

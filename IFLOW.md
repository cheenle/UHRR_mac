# iFlow 上下文信息 (IFLOW.md)

## 项目概述

**Mobile Remote Radio Control (MRRC)** 是一款专为移动端优化的业余电台远程控制系统。它允许业余无线电爱好者通过现代Web浏览器（尤其是移动设备）随时随地远程控制电台设备，进行语音通话和参数调节。

**设计理念**：Mobile First, Radio Anywhere - 随时随地，畅享业余无线电。

主要技术栈：
- **前端**：HTML5, CSS3, JavaScript (VanillaJS), Web Audio API, AudioWorklet, WebSocket
- **后端**：Python 3.12+, Tornado Web Framework, PyAudio, Hamlib/rigctld
- **部署**：macOS/类Unix系统，支持TLS加密和用户认证

### 核心特性
- **📱 移动优先设计**：专为触摸屏优化，支持单手操作，PWA离线访问
- **⚡ 超低延迟**：TX/RX切换<100ms，PTT可靠性99%+
- **🌍 随时随地访问**：互联网覆盖处即可操控您的电台
- **🔒 安全连接**：TLS加密传输，用户认证保护
- **🎛️ 完整控制**：频率、模式、PTT、天调等完整电台功能

### 历史改进
- **增强的PTT可靠性机制**：按下即发送PTT命令，并立即发送预热帧确保后端收到音频数据
- **优化的TX/RX切换**：从2-3秒延迟优化至<100ms切换响应
- **移动端支持**：专门的移动界面，优化触摸交互和音频处理，支持iPhone 15等现代移动设备
- **AAC音频编码**：新增ADPCM自适应差分编码，支持50-60%压缩率
- **音频优化**：采用Int16编码（50%带宽减少），AudioWorklet低抖动播放
- **NanoVNA集成**：内置矢量网络分析仪Web界面支持

## 目录结构要点

```
MRRC/
├── UHRR                          # 后端主程序 (Tornado WebSocket服务器)
├── UHRR.conf                     # 系统核心配置文件
├── audio_interface.py            # PyAudio采集/播放封装与客户端分发
├── hamlib_wrapper.py             # 与rigctld通信的辅助逻辑
├── tci_client.py                 # TCI协议客户端实现
├── uhrr_control.sh               # 系统控制脚本（启动/停止/状态）
├── uhrr_monitor.sh               # 系统监控脚本
├── uhrr_setup.sh                 # 系统安装配置脚本
├── www/                          # 前端页面与脚本
│   ├── controls.js               # 音频与控制主逻辑
│   ├── tx_button_optimized.js    # TX按钮事件与时序优化
│   ├── rx_worklet_processor.js   # AudioWorklet播放器
│   ├── aac_encoder.js            # AAC/ADPCM音频编码器
│   ├── atu.js                    # ATU功率和驻波比显示管理
│   ├── mobile_modern.html        # 现代移动端界面 (iPhone 15优化) ⭐
│   ├── mobile_modern.js          # 移动端界面逻辑
│   ├── mobile_audio_direct_copy.js # 移动端音频处理
│   ├── manifest.json             # PWA应用清单文件
│   └── sw.js                     # Service Worker (离线支持)
├── certs/                        # TLS证书目录
├── atr1000_proxy.py              # ATR-1000独立代理程序 ⭐ 新增
├── dev_tools/                    # 测试/调试脚本与页面
│   ├── debug_audio.html          # 音频调试页面
│   ├── debug_audio_rx.html       # RX音频调试页面
│   ├── debug_audio_state.html    # 音频状态调试页面
│   ├── debug_power_button.html   # 电源按钮调试页面
│   ├── debug_uhrr.py             # UHRR调试脚本
│   ├── simple_audio_test.html    # 简单音频测试页面
│   ├── test_audio.py             # 音频测试脚本
│   ├── test_audio_capture.py     # 音频采集测试脚本
│   ├── test_audio_quality.sh     # 音频质量测试脚本
│   ├── test_connection.py        # 连接测试脚本
│   ├── test_websocket_client.py  # WebSocket客户端测试
│   ├── test_server.py            # 服务器测试脚本
│   ├── test_tornado.py           # Tornado框架测试
│   ├── test_service.py           # 服务测试脚本
│   ├── test_mobile.sh            # 移动端测试脚本
│   └── test_mobile_fixes.html    # 移动端修复测试页面
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
│   ├── Performance_Optimization_Guide.md   # 性能优化指南
│   ├── Component_Detailed_Analysis.md      # 组件详细分析
│   ├── Comprehensive_Architecture_Analysis.md # 综合架构分析
│   ├── iphone15_mobile_interface_analysis.md # iPhone 15界面分析
│   └── mobile_interface_enhancement_summary.md # 移动界面增强总结
├── opus/                         # Opus编解码器Python绑定
├── *.wav                         # 音频测试文件 (cq.wav, tune.wav等)
└── com.user.uhrr.plist           # macOS launchd服务配置
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
- 新增ADPCM压缩编码支持

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
- **新增编码器**：`www/aac_encoder.js`
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

### 8. 新增功能
- **电压电流监控**：实时显示电源电压 (Vin, 12V) 和电流 (Idq)
- **天调存储**：本地保存天调参数，频率-参数自动匹配
- **多用户登录**：支持多用户账号登录验证

## 关键配置文件 (UHRR.conf)

主要配置项：
- `[SERVER]`: 端口、证书路径、认证设置
  - `port`: 默认8877，生产环境建议443
  - `certfile`: TLS证书路径（如certs/radio.vlsc.net.pem）
  - `keyfile`: TLS私钥路径
  - `auth`: 认证方式
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

**移动端测试工具：**
- `test_mobile.sh`: 移动端测试脚本
- `test_mobile_fixes.html`: 移动端修复测试页面

**调试工具：**
- `debug_audio.html`: 音频调试页面
- `debug_audio_rx.html`: RX音频调试页面
- `debug_audio_state.html`: 音频状态调试页面
- `debug_power_button.html`: 电源按钮调试页面
- `debug_uhrr.py`: UHRR调试脚本

**其他测试工具：**
- `test_callsign.html`: 呼号测试页面
- `test_pad_tx.html`: PAD TX测试页面
- `test_restart.html`: 重启测试页面
- `test_file_access.py`: 文件访问测试
- `test_uhrr_handler.py`: UHRR处理器测试
- `simple_audio_test.html`: 简单音频测试页面

### TCI协议测试
- `tci_client.py`: TCI协议客户端实现
- 支持频率、模式、PTT控制
- 实时状态读取

### 文档资源
- 系统架构设计详见 `docs/System_Architecture_Design.md`
- PTT/音频稳定性复盘详见 `docs/PTT_Audio_Postmortem_and_Best_Practices.md`
- TX/RX切换延迟优化指南详见 `docs/latency_optimization_guide.md`
- 现代移动端界面详见 `docs/mobile_modern_interface.md`
- 性能优化指南详见 `docs/Performance_Optimization_Guide.md`
- 组件详细分析详见 `docs/Component_Detailed_Analysis.md`
- 综合架构分析详见 `docs/Comprehensive_Architecture_Analysis.md`
- iPhone 15界面分析详见 `docs/iphone15_mobile_interface_analysis.md`
- 移动界面增强总结详见 `docs/mobile_interface_enhancement_summary.md`

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
   - 编辑 `UHRR.conf` 配置证书路径：
     ```ini
     [SERVER]
     port = 443
     certfile = certs/radio.vlsc.net.pem
     keyfile = certs/radio.vlsc.net.key
     ```

4. **启动服务**
   ```bash
   # 使用控制脚本（推荐）
   ./uhrr_control.sh start
   
   # 或直接启动
   python3 ./UHRR
   ```

5. **访问**
   - 桌面端：`https://<你的域名或IP>/`（若使用443端口）
   - 移动端：`https://<你的域名或IP>/mobile_modern.html`
   - NanoVNA：`https://<你的域名或IP>/nanovna/NanoVNA/`

### 系统控制命令

```bash
# 启动所有服务
./uhrr_control.sh start

# 停止所有服务
./uhrr_control.sh stop

# 重启系统
./uhrr_control.sh restart

# 查看状态
./uhrr_control.sh status

# 查看日志
./uhrr_control.sh logs [行数] [服务名]

# 单独启动服务
./uhrr_control.sh start-rigctld
./uhrr_control.sh start-uhrr
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
# 加载服务配置
launchctl load com.user.uhrr.plist

# 启动服务
launchctl start com.user.uhrr

# 查看服务状态
launchctl list | grep uhrr
```

服务配置文件：`com.user.uhrr.plist`
- 自动启动：RunAtLoad = true
- 保持运行：KeepAlive = true
- 日志输出：uhrr_service.log, uhrr_service_error.log
- 工作目录：/Users/cheenle/UHRR/UHRR_mac

### 移动端访问

- **现代界面**：访问 `https://<你的域名或IP>/mobile_modern.html`
- **经典界面**：访问 `https://<你的域名或IP>/mobile.html`
- 支持iPhone 15、iPhone 14、Android等移动设备
- 建议使用iOS Safari或Chrome浏览器
- 支持添加到主屏幕作为PWA应用

## AAC音频编码器详解

### 功能特性
- **ADPCM压缩**：自适应差分PCM编码，实现50-60%压缩率
- **降采样支持**：将高采样率音频降采样到16kHz
- **浏览器兼容**：支持所有现代浏览器
- **可选AAC编码**：支持MediaRecorder进行实际AAC编码（兼容性有限）

### 技术实现
- **编码格式**：自定义AACM格式
  - 魔数：0x4141434D ("AACM")
  - 头部：8字节（魔数+采样率+声道数+编码类型）
  - 数据：8位差分编码
- **编码流程**：
  1. Float32 → Int16 转换
  2. 差分计算
  3. 8位量化
  4. 头部添加

### 使用方法
```javascript
const encoder = new AACEncoder(16000, 1, 64000);
await encoder.init();
const compressed = await encoder.encode(float32AudioData);
```

### 压缩效果
- 原始数据：Float32 (32位/样本)
- 压缩后：8位差分编码
- 压缩率：约75%（从32位到8位）

## 移动端支持详解

### 功能特性
- **现代UI设计**：专为移动设备优化的界面
- **触摸优化**：大尺寸交互元素，舒适的拇指操作区域
- **PTT按钮**：底部居中的大按钮，支持长按和短按
- **频率显示**：清晰的数字分离显示
- **S表可视化**：实时信号强度显示
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

### 移动端特定优化
1. **视口设置**：防止意外缩放
2. **触摸目标尺寸**：所有交互元素至少44px
3. **快速点击**：使用触摸事件替代鼠标事件
4. **防抖处理**：防止重复触发
5. **方向处理**：适配横竖屏切换
6. **性能优化**：减少重排重绘，优化动画

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
- **ADPCM压缩**：新增ADPCM自适应差分编码，50-60%压缩率
- **Opus编解码**：优化参数设置，提高音质
- **预热帧机制**：PTT按下时立即发送10个预热帧确保音频数据及时传输
- **采样率优化**：统一使用16kHz采样率
- **缓冲策略**：动态调整缓冲区深度适应网络条件

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
│   UHRR 主程序    │
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
./uhrr_control.sh start-atr1000
```

**方式二：手动启动**
```bash
# 启动 ATR-1000 代理（后台运行）
python3 atr1000_proxy.py --device 192.168.1.63 --port 60001 &

# 或使用系统控制脚本
./uhrr_control.sh start
```

### 配置说明

ATR-1000 设备参数在 `atr1000_proxy.py` 中配置：
- `--device`: ATR-1000 设备 IP 地址（默认 192.168.1.63）
- `--port`: ATR-1000 WebSocket 端口（默认 60001）
- `--socket`: Unix Socket 路径（默认 /tmp/atr1000_proxy.sock）

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
1. 确认使用 V4.3.3+ 版本
2. 检查网络延迟
3. 查看浏览器控制台日志

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

## 系统架构设计

### 组件关系
- **前端**：HTML5界面 + WebSocket客户端
- **后端**：Tornado服务器 + WebSocket处理
- **音频**：PyAudio + Web Audio API + AudioWorklet
- **控制**：Hamlib/rigctld + TCI客户端
- **网络**：TLS加密
- **工具**：NanoVNA Web界面

### 接口协议
- **控制协议**：WebSocket + JSON
- **音频协议**：WebSocket + Int16/ADPCM/Opus
- **TCI协议**：标准TCI命令集

### 部署方案
- **单机部署**：所有组件运行在同一台机器
- **分布式部署**：前端、后端分离
- **容器化部署**：Docker容器封装
- **云部署**：VPS + TLS访问

## 性能优化指南

### 音频性能
- 使用AudioWorklet降低主线程负载
- 优化缓冲区大小
- 实现丢包补偿
- 自适应码率调整
- ADPCM压缩减少带宽占用

### 网络性能
- WebSocket长连接复用
- 智能缓冲区管理
- 网络状况监控
- 自适应重传策略

### 渲染性能
- 减少DOM操作
- 使用CSS动画替代JS动画
- 事件委托
- 虚拟滚动（长列表）

### 内存优化
- 及时释放资源
- 对象池复用
- 避免内存泄漏
- 垃圾回收优化

## 许可证

本项目遵循 **GNU General Public License v3.0 (GPL-3.0)** 许可证。
基于 [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5) 开源项目进行开发和改进。

### 项目来源声明
- 原始项目：F4HTB/Universal_HamRadio_Remote_HTML5
- 改进内容：稳定性优化、架构升级、功能增强
- 分发要求：必须提供完整源代码并保留许可证和版权声明

## 版本历史

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

#### 性能结果
| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 广播延迟 | 2-5 秒 | <500ms |
| 显示更新 | 经常丢失 | 实时更新 |
| 电源按钮 | 不工作 | 已修复 |

#### 文件变更
- `UHRR` - 批量广播机制，线程安全 WebSocket
- `www/mobile_modern.js` - 语法修复，优化 DOM 更新

---

### V4.3.5 系统架构文档更新 (2026-03-04)

**主题：V4.3架构文档完整重构**

#### 文档更新
- **System_Architecture_Design.md**：完整架构重构
  - 添加 ATR-1000 集成模块
  - 添加 TX EQ 三段均衡器组件
  - 更新架构图与新组件
  - 添加 ATR-1000 WebSocket 协议文档
  - 更新数据流图
  - 添加天调存储模块说明

#### 新增组件文档
- ATR-1000 桥接器 (UHRR)
- ATR-1000 独立代理 (atr1000_proxy.py)
- 天调存储模块 (atr1000_tuner.py)
- TX 均衡器 (三段音频EQ)
- ATR-1000 客户端模块 (mobile_modern.js)

---

### V4.3.4 ATR-1000集成文档 (2026-03-04)

**主题：完整ATR-1000集成指南**

#### 文档新增
- **IFLOW.md**：添加完整的ATR-1000集成文档
  - 架构设计图
  - 启动方法与配置
  - 数据协议规范
  - 天调存储模块说明
  - 性能优化详情
  - 故障排查指南

---

### V4.3.3 ATR-1000连接预热 (2026-03-04)

**主题：减少PTT按下延迟**

#### 性能优化
- **预连接**：页面加载时预先建立ATR-1000 WebSocket连接
- **连接持久化**：TX结束后保持连接不断开
- **SYNC预热**：有客户端连接时每2秒发送SYNC预热
- **移除**：TX停止时关闭连接 - 连接保持温热状态

#### 效果
- PTT按下到功率显示：~1-2秒 → ~100-200ms
- 页面刷新后首次TX：即时响应

---

### V4.3.2 ATR-1000显示优化 (2026-03-04)

**主题：改进实时显示响应性**

#### 修复内容
- **前端显示更新**：收到数据时始终调用`updateDisplay()`，移除变更检测依赖
- **代理日志输出**：恢复功率>0时的广播日志
- **调试控制台日志**：添加功率/SWR变化日志便于排查

#### 优化
- 减少前端消息处理中不必要的条件检查
- 更清晰的日志输出（仅在实际有功率时显示）

---

### V4.3.1 ATR-1000显示修复与天调存储 (2026-03-04)

**主题：实时功率/SWR显示与天调参数存储**

#### 新增功能
- **ATR-1000天调存储模块** (`atr1000_tuner.py`)
  - 按频率存储天调参数（LC/CL、电感、电容）
  - 频率变化时自动加载匹配参数
  - JSON文件持久化 (`atr1000_tuner.json`)

- **继电器状态解析**：ATR-1000代理
  - 解析 SCMD_RELAY_STATUS (命令5)
  - 提取 SW (LC/CL)、电感索引、电容索引
  - 前端UI显示

- **前端UI**：天调操作按钮
  - "Tune"按钮：启动自动调谐
  - "Save"按钮：保存当前参数
  - "Records"按钮：查看已保存参数

#### 修复
- **ATR-1000 WebSocket数据转发**：UHRR中使用`IOLoop.add_callback()`实现线程安全WebSocket写入
- 移动端显示延迟修复

#### 技术细节
- **数据流**：代理 → Unix Socket → UHRR → WebSocket (IOLoop) → 前端
- **天调存储**：基于频率的参数查找，±50kHz容差
- **命令**：`set_relay`、`tune`、`save_tuner` 操作

---

### V4.3.0 ATR-1000架构分离 (2026-03-04)

**主题：独立ATR-1000代理提升性能**

#### 核心改进
- **ATR-1000独立代理程序**：`atr1000_proxy.py`
  - 独立进程，不阻塞UHRR主程序
  - Unix Socket通信 (`/tmp/atr1000_proxy.sock`)
  - 自动重连ATR-1000设备
  - 按需数据请求（仅当有客户端连接时）

- **UHRR中添加ATR-1000 WebSocket端点**
  - 路由 `/WSATR1000`
  - 通过Unix Socket桥接前端与独立代理

#### 架构图
```
前端 (mobile_modern.js)
    ↓ WebSocket (/WSATR1000)
UHRR 主程序
    ↓ Unix Socket (/tmp/atr1000_proxy.sock)
ATR-1000 独立代理 (atr1000_proxy.py)
    ↓ WebSocket
ATR-1000 设备 (192.168.1.63:60001)
```

#### 性能改进
| 指标 | 改进前 | 改进后 |
|------|--------|--------|
| PTT释放延迟 | ~2秒 | <100ms |
| CPU占用 | 高 (0.3秒间隔) | 低 (1秒间隔+按需) |
| 架构 | 耦合 | 解耦独立进程 |

#### 使用方法
```bash
# 启动ATR-1000代理（后台）
python3 atr1000_proxy.py --device 192.168.1.63 --port 60001 &

# 启动UHRR主程序
./uhrr_control.sh start
```

#### 文件变更
- `atr1000_proxy.py` - 新增独立ATR-1000代理程序
- `UHRR` - 添加 `WS_ATR1000Handler` 类和路由
- `www/mobile_modern.js` - 优化ATR-1000模块，修复轮询管理

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

#### 技术细节
- 音频链：micSource → eqLow → eqMid → eqHigh → gain_node → processor
- 使用Web Audio API BiquadFilter节点
- 预设自动保存到Cookie

#### 文件变更
- `www/controls.js` - TX EQ核心逻辑
- `www/mobile_modern.js` - showTXEQPanel函数
- `www/mobile_modern.html` - 菜单项
- `www/mobile_modern.css` - EQ面板样式

---

### V4.1.0 项目重命名 (2026-03-01)

**主题：Mobile First - MRRC品牌重塑**

#### 核心改进
- **项目更名**：从"Universal HamRadio Remote (UHRR)"更名为"Mobile Remote Radio Control (MRRC)"
- **设计理念**：Mobile First, Radio Anywhere - 随时随地，畅享业余无线电
- **文档国际化**：README支持中英文切换

#### 文件变更
- `README.md` - 主入口，语言选择页面
- `README_CN.md` - 中文文档（从README.md重命名）
- `README_en.md` - 英文文档
- `CHANGELOG.md` - 添加V4.1.0版本记录
- `IFLOW.md` - 更新项目概述

---

### V4.0.1 移动端界面增强 (2026-03-01)

**主题：S表显示与音量控制改进**

#### 核心改进
- **S表显示修复**：使用正确的SP映射表，准确显示S0-S9+60dB信号级别
- **主界面音量控制**：新增AF增益滑块，实时调节音量（0-100%）
- **音频设置完善**：AF增益、MIC增益、静噪功能完整可用
- **双向同步机制**：主界面与设置面板音量滑块双向同步

#### 技术细节
- S表映射：S0(0px) → S9(123px) → S9+60(240px)
- AF增益：0-100%映射到内部0-1000范围
- Cookie持久化：音频设置自动保存和加载

#### 文件变更
- `www/mobile_modern.html` - 添加音量控制区域和隐藏元素
- `www/mobile_modern.css` - 音量滑块样式（渐变色背景）
- `www/mobile_modern.js` - S表绘制、音量控制、双向同步

---

### V4.0 里程碑版本 (2026-03-01)

**主题：性能优化与架构精简**

#### 核心改进
- **TX→RX切换延迟优化**：从2-3秒优化至<100ms
- **PTT可靠性增强**：双重触发机制 + 预热帧 + 超时保护
- **移动端界面重构**：iPhone 15优化，PWA支持，TUNE天调按钮
- **架构精简**：移除VPN功能，移除无效导航组件
- **文档完善**：端到端分析报告，架构文档更新

#### 详细变更
- `fix: 修复TX→RX切换延迟问题` - PTT命令格式修正，停止命令触发PTT关闭
- `feat: 调整频率调整按钮布局` - 步进值改为10k/5k/1kHz
- `feat: 添加TUNE天调按钮` - 替换步进按钮，长按发射1kHz单音
- `refactor: 移除移动端底部导航栏` - 清理无效UI组件
- `chore: 移除VPN相关功能和文件` - 精简系统架构
- `docs: 添加端到端深度分析报告` - 性能瓶颈分析与优化建议

#### 性能指标
| 指标 | V3.x | V4.0 |
|------|------|------|
| TX延迟 | ~100ms | ~65ms |
| RX延迟 | ~100ms | ~51ms |
| TX→RX切换 | 2-3秒 | <100ms |
| PTT可靠性 | 95% | 99%+ |

---

### V3.2 (2025-01)
- 移动端音频优化与TX→RX切换延迟修复
- iOS Safari AudioContext挂起问题修复

### V3.1 (2025-01)
- 优化移动端音频和PTT功能
- 修复iPhone浏览器兼容性问题

### V3.0 (2024-12)
- 现代移动端界面（iPhone 15优化）
- AAC/ADPCM音频编码支持
- TCI协议支持
- NanoVNA矢量网络分析仪集成

### V2.0 (2024-11)
- 系统架构重构
- AudioWorklet低延迟播放
- Int16编码带宽优化

### V1.0 (2024-10)
- 基于F4HTB项目的初始版本
- 基本的远程电台控制功能

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

**最后更新**：2026年3月5日
**文档版本**：v4.4.0
**发布版本**：V4.4.0
**维护者**：MRRC开发团队

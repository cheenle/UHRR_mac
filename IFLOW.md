# iFlow 上下文信息 (IFLOW.md)

## 项目概述

Universal HamRadio Remote (UHRR) 是一个面向业余无线电爱好者的远程电台控制与音频流系统。它允许用户通过现代Web浏览器界面远程控制电台设备，进行语音通话和参数调节。

主要技术栈：
- **前端**：HTML5, CSS3, JavaScript (VanillaJS), Web Audio API, AudioWorklet, WebSocket
- **后端**：Python 3.12+, Tornado Web Framework, PyAudio, Hamlib/rigctld
- **部署**：macOS/类Unix系统，支持TLS加密和用户认证

### 核心改进
- **增强的PTT可靠性机制**：按下即发送PTT命令，并立即发送预热帧确保后端收到音频数据
- **优化的TX/RX切换**：从2-3秒延迟优化至<100ms切换响应
- **移动端支持**：专门的移动界面，优化触摸交互和音频处理，支持iPhone 15等现代移动设备
- **ATU监控系统**：支持天线调谐器功率和驻波比实时监控（ATR-1000设备）
- **音频优化**：采用Int16编码（50%带宽减少），AudioWorklet低抖动播放
- **延迟优化**：TX到RX切换延迟从2-3秒优化到<100ms
- **VPN支持**：集成WireGuard VPN配置，支持安全的远程访问

## 目录结构要点

```
UHRR_mac/
├── UHRR                          # 后端主程序 (Tornado WebSocket服务器)
├── UHRR.conf                     # 系统核心配置文件
├── audio_interface.py            # PyAudio采集/播放封装与客户端分发
├── hamlib_wrapper.py             # 与rigctld通信的辅助逻辑
├── ATU_SERVER_WEBSOCKET.py       # ATU设备WebSocket服务器 (端口8889)
├── tci_client.py                 # TCI协议客户端实现
├── www/                          # 前端页面与脚本
│   ├── controls.js               # 音频与控制主逻辑
│   ├── tx_button_optimized.js    # TX按钮事件与时序优化
│   ├── rx_worklet_processor.js   # AudioWorklet播放器
│   ├── atu.js                    # ATU功率和驻波比显示管理
│   ├── mobile_modern.html        # 现代移动端界面 (iPhone 15优化)
│   ├── mobile_modern.js          # 移动端界面逻辑
│   ├── mobile_audio_direct_copy.js # 移动端音频处理
│   ├── manifest.json             # PWA应用清单文件
│   └── sw.js                     # Service Worker (离线支持)
├── certs/                        # TLS证书目录
├── dev_tools/                    # 测试/调试脚本与页面
├── ATU/                          # ATU监控界面和相关文件
├── VPN/                          # WireGuard VPN配置和脚本
├── docs/                         # 技术文档
│   ├── System_Architecture_Design.md      # 系统架构设计文档
│   ├── PTT_Audio_Postmortem_and_Best_Practices.md # PTT/音频稳定性复盘
│   ├── latency_optimization_guide.md       # TX/RX切换延迟优化指南
│   ├── mobile_modern_interface.md          # 现代移动端界面文档
│   └── Performance_Optimization_Guide.md   # 性能优化指南
├── opus/                         # Opus编解码器Python绑定
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
- **TX (发射)**: 浏览器麦克风输入 → Web Audio API处理 → Opus编码 → WebSocket传输 → 后端PyAudio播放到电台
- **RX (接收)**: 电台音频 → 后端PyAudio采集 → Int16编码 → WebSocket传输 → 浏览器AudioWorklet播放
- 采样率：16kHz，格式：Int16（50%带宽优化），目标延迟：<100ms
- 支持Int16编码和Opus编码双模式

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

### 5. ATU监控系统
- 实时监控天线调谐器功率输出和驻波比
- 支持WebSocket连接ATR-1000设备（端口81）
- 提供功率、SWR、最大功率、传输效率等关键参数显示
- 智能告警系统和历史趋势图表
- 支持预设频率配置和自动调谐参数应用
- ATU服务器运行在8889端口，独立于主UHRR服务

### 6. 移动端优化
- **现代移动界面**：专门为iPhone 15和现代移动浏览器优化的界面
- **PWA支持**：支持添加到主屏幕，离线访问
- **触摸优化**：大尺寸PTT按钮，适配拇指操作区域
- **安全区域支持**：适配刘海屏和底部指示器
- **触觉反馈**：PTT按钮提供震动反馈
- **响应式设计**：支持横竖屏切换，适配各种屏幕尺寸
- **性能优化**：Service Worker缓存，快速启动
- **兼容性**：支持iOS Safari、Chrome、Firefox等现代浏览器

### 7. VPN远程访问
- WireGuard VPN配置支持
- 服务器：www.vlsc.net (端口9090/UDP)
- 支持macOS和OpenWrt客户端
- 内置DNS (Unbound) 和MASQUERADE NAT
- 提供安全加密的远程访问通道

## 关键配置文件 (UHRR.conf)

主要配置项：
- `[SERVER]`: 端口、证书路径、认证设置
  - `port`: 默认8877，生产环境建议443
  - `certfile`: TLS证书路径（如certs/radio.vlsc.net.pem）
  - `keyfile`: TLS私钥路径
  - `auth`: 认证方式
  - `db_users_file`: 用户数据库文件路径
- `[AUDIO]`: 音频输入/输出设备名称
- `[HAMLIB]`: 电台串口路径、型号、波特率等
  - `rig_pathname`: 串口设备路径（如/dev/cu.usbserial-230）
  - `rig_model`: 电台型号（如IC_M710）
  - `rig_rate`: 波特率（如4800）
- `[CTRL]`: S表更新周期等控制参数
- `[PANADAPTER]`: 频谱分析仪相关设置（采样率、中心频率等）

## 开发与测试

### 测试工具
- 所有测试/调试脚本位于 `dev_tools/` 目录
- 音频测试脚本：`test_audio.py`, `test_audio_quality.sh`
- 连接测试：`test_connection.py`, `test_websocket_client.py`
- 服务测试：`test_server.py`, `test_tornado.py`
- 移动端测试：`test_mobile.sh`

### TCI协议测试
- `tci_client.py`: TCI协议客户端实现
- `test_tci_connection.py`: TCI连接测试
- `test_uhrr_tci.py`: UHRR TCI集成测试
- `set_tci_frequency.py`: 频率设置工具
- `check_tci_status.py`: TCI状态检查

### 文档资源
- 系统架构设计详见 `docs/System_Architecture_Design.md`
- PTT/音频稳定性复盘详见 `docs/PTT_Audio_Postmortem_and_Best_Practices.md`
- TX/RX切换延迟优化指南详见 `docs/latency_optimization_guide.md`
- 现代移动端界面详见 `docs/mobile_modern_interface.md`
- 性能优化指南详见 `docs/Performance_Optimization_Guide.md`

### 开发实践
- 推荐在独立分支进行实验性修改
- 支持Docker容器化部署和测试
- 使用Git进行版本控制
- 遵循GPL-3.0开源协议

## 构建和运行

### 快速开始 (macOS)

1. **环境准备**
   ```bash
   # 运行健康检查脚本
   ./health_check.sh
   ```

2. **启动rigctld**（示例，根据实际设备调整）
   ```bash
   rigctld -m 335 -r /dev/cu.usbserial-230 -s 4800
   ```

3. **配置TLS证书**（可选但推荐）
   - 将证书放入 `certs/` 目录
   - 编辑 `UHRR.conf` 配置证书路径：
     ```ini
     [SERVER]
     port = 443
     certfile = certs/fullchain.pem
     keyfile = certs/radio.vlsc.net.key
     ```

4. **启动服务**
   ```bash
   # 直接启动
   python3 ./UHRR
   
   # 或使用控制脚本
   ./uhrr_control.sh start
   ```

5. **访问**
   - 桌面端：`https://<你的域名或IP>/`（若使用443端口）
   - 移动端：`https://<你的域名或IP>/mobile_modern.html`
   - ATU监控：`https://<你的域名或IP>:8889/atu/monitor`

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

### 移动端访问

- **现代界面**：访问 `https://<你的域名或IP>/mobile_modern.html`
- **经典界面**：访问 `https://<你的域名或IP>/mobile.html`
- 支持iPhone 15、iPhone 14、Android等移动设备
- 建议使用iOS Safari或Chrome浏览器
- 支持添加到主屏幕作为PWA应用

### ATU监控系统

1. **启动ATU服务器**
   ```bash
   python3 ./ATU_SERVER_WEBSOCKET.py
   ```
   
2. **访问ATU监控页面**
   - `https://<你的域名或IP>:8889/atu/monitor`
   - `https://<你的域名或IP>:8889/atu/realtime_display`

3. **ATU设备配置**
   - 设备IP：192.168.1.63（可配置）
   - WebSocket端口：60001
   - HTTP端口：81

### VPN远程访问

1. **macOS客户端**
   ```bash
   # 启动VPN
   sudo VPN/scripts/wg-up.sh
   
   # 停止VPN
   sudo VPN/scripts/wg-down.sh
   
   # 查看状态
   VPN/scripts/wg-status.sh
   ```

2. **OpenWrt客户端**
   - 配置已持久化，重启网络接口即可
   - 默认路由走VPN隧道
   - 特定IP走直连路由

3. **服务器配置**
   - WireGuard监听端口：9090/UDP
   - 内部DNS：10.77.0.1:53
   - MTU：1360

## ATU监控系统详解

### 功能特性
- 实时监控天线调谐器功率输出和驻波比
- 支持WebSocket连接ATR-1000设备
- 提供功率、SWR、最大功率、传输效率等关键参数显示
- 智能告警系统和历史趋势图表
- 预设频率配置支持（7MHz, 14MHz, 21MHz, 28MHz）
- 自动调谐参数应用
- PTT联动监控

### 技术实现
- 使用WebSocket协议与ATU设备通信
- 解析二进制数据包获取电表数据
- 数据格式：flag(1字节) + cmd(1字节) + swr(2字节) + fwd(2字节) + maxfwd(2字节)
- 使用小端序解析16位整数
- SWR值需要除以100得到实际值
- 定期发送同步命令获取实时数据
- 支持多客户端同时监控

### 数据验证
- 功率值范围：0-10000W
- SWR值范围：1.0-10.0
- 过滤异常数据包
- 数据校验和验证

### 部署架构
- ATU服务器独立运行在8889端口
- 通过WebSocket与ATU设备通信（端口60001）
- 提供HTTP/WebSocket接口给前端监控页面
- 支持实时数据推送和历史数据查询

## 移动端支持详解

### 功能特性
- **现代UI设计**：专为移动设备优化的界面
- **触摸优化**：大尺寸交互元素，舒适的拇指操作区域
- **PTT按钮**：底部居中的大按钮，支持长按和短按
- **频率显示**：清晰的数字分离显示
- **S表可视化**：实时信号强度显示
- **连接状态指示**：WebSocket连接状态、传输状态
- **暗色模式**：适合夜间操作

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
- **TX流**：麦克风 → Web Audio API → Int16/Opus编码 → WebSocket → PyAudio → 电台
- **RX流**：电台 → PyAudio → Int16编码 → WebSocket → AudioWorklet → 扬声器
- **延迟控制**：端到端目标延迟<100ms
- **质量保证**：音频质量监控和自适应调整

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
- `test_tci_connection.py`：连接测试工具
- `test_uhrr_tci.py`：集成测试
- `set_tci_frequency.py`：频率设置工具
- `check_tci_status.py`：状态检查工具
- `direct_tci_test.py`：直接测试工具
- `detailed_tci_test.py`：详细测试工具

### 支持的功能
- 频率读取和设置
- 模式切换
- PTT控制
- VFO控制
- S表读取
- 状态查询

## VPN远程访问详解

### 网络拓扑
- **服务器 (VPS)**：www.vlsc.net
  - WireGuard接口：wg0
  - 监听端口：9090/UDP
  - 服务端地址：10.77.0.1/24
  - NAT：MASQUERADE到公网出口
  - 内部DNS：Unbound 10.77.0.1:53
- **macOS客户端**：
  - 接口：utunX
  - 地址：10.77.0.2/24
  - DNS：10.77.0.1
- **OpenWrt客户端**：
  - 接口：wg0
  - 默认路由：走wg0
  - 回避路由：特定IP走直连
  - 防火墙：vpn区域（启用masq和mtu_fix）

### 配置文件
- **macOS客户端**：`vlsc-wg-client.conf`
  - DNS：10.77.0.1
  - MTU：1360
  - Endpoint：www.vlsc.net:9090
- **脚本**：`VPN/scripts/`
  - `wg-up.sh`：启动wg0
  - `wg-down.sh`：停止wg0
  - `wg-status.sh`：查看状态

### 优化要点
- **MTU/MSS**：MTU=1360，配合nft TCPMSS=1320
- **端口**：9090/UDP（变更需同步服务器和客户端）
- **DNS**：使用10.77.0.1（Unbound缓存）
- **安全性**：WireGuard加密，安全访问

### 排错建议
- **RX=0**：检查服务器NAT、FORWARD规则、内核转发
- **网页慢/打不开**：检查MTU/MSS，必要时下调MTU到1320-1380
- **DNS失败**：
  - macOS：确认DNS=10.77.0.1，重连隧道
  - OpenWrt：确认上游10.77.0.1，重启dnsmasq
- **端口变更**：同步修改Endpoint/ListenPort与防火墙规则

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

### ATU显示问题
1. 检查ATU设备网络连接
2. 确认设备IP地址
3. 验证WebSocket端口
4. 查看ATU服务器日志

## 系统架构设计

### 组件关系
- **前端**：HTML5界面 + WebSocket客户端
- **后端**：Tornado服务器 + WebSocket处理
- **音频**：PyAudio + Web Audio API + AudioWorklet
- **控制**：Hamlib/rigctld + TCI客户端
- **监控**：ATU服务器 + 实时数据显示
- **网络**：WireGuard VPN + TLS加密

### 接口协议
- **控制协议**：WebSocket + JSON
- **音频协议**：WebSocket + Int16/Opus
- **ATU协议**：自定义二进制协议
- **TCI协议**：标准TCI命令集

### 部署方案
- **单机部署**：所有组件运行在同一台机器
- **分布式部署**：前端、后端、ATU服务器分离
- **容器化部署**：Docker容器封装
- **云部署**：VPS + VPN访问

## 性能优化指南

### 音频性能
- 使用AudioWorklet降低主线程负载
- 优化缓冲区大小
- 实现丢包补偿
- 自适应码率调整

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

### 当前版本
- 提交：bc4caa2 - 现代浏览器风格界面：完整功能实现
- 主要特性：
  - 现代移动端界面（iPhone 15优化）
  - TX/RX切换延迟优化（<100ms）
  - 增强的PTT可靠性机制
  - ATU实时监控系统
  - TCI协议支持
  - WireGuard VPN集成

### 关键改进
- v3.1：优化移动端音频和PTT功能，修复iPhone浏览器兼容性问题
- 深度代码分析与文档完善
- 系统架构设计文档
- PTT/音频稳定性复盘
- 延迟优化指南

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

**最后更新**：2026年2月13日
**文档版本**：v2.0
**维护者**：UHRR开发团队
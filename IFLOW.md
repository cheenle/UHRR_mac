# iFlow 上下文信息 (IFLOW.md)

## 项目概述

Universal HamRadio Remote (UHRR) 是一个面向业余无线电爱好者的远程电台控制与音频流系统。它允许用户通过现代Web浏览器界面远程控制电台设备，进行语音通话和参数调节。

主要技术栈：
- **前端**：HTML5, CSS3, JavaScript (VanillaJS), Web Audio API, AudioWorklet, WebSocket
- **后端**：Python 3.12+, Tornado Web Framework, PyAudio, Hamlib/rigctld
- **部署**：macOS/类Unix系统，支持TLS加密和用户认证

### 核心特性
- **增强的PTT可靠性机制**：按下即发送PTT命令，预热帧确保音频传输
- **优化的TX/RX切换**：<100ms切换响应
- **移动端全面支持**：iPhone/Android专用界面，触摸优化
- **音频优化**：Int16编码（50%带宽减少），AudioWorklet低延迟播放
- **波段/模式控制**：完整电台控制功能

## 目录结构

```
UHRR_mac/
├── UHRR                          # 后端主程序 (Tornado WebSocket服务器)
├── UHRR.conf                     # 系统核心配置文件
├── audio_interface.py            # PyAudio采集/播放封装
├── hamlib_wrapper.py             # rigctld通信辅助
├── tci_client.py                 # TCI协议客户端
├── uhrr_control.sh               # 服务控制脚本
├── uhrr_setup.sh                 # 服务安装脚本
├── uhrr_monitor.sh               # 服务监控脚本
├── com.user.uhrr.plist           # macOS launchd配置
├── www/                          # 前端页面
│   ├── controls.js               # 桌面版主逻辑
│   ├── tx_button_optimized.js    # TX按钮优化
│   ├── rx_worklet_processor.js   # AudioWorklet播放器
│   ├── aac_encoder.js            # AAC编码器
│   ├── mobile_modern.html        # 移动端界面 ★
│   ├── mobile_modern.js          # 移动端逻辑 ★
│   ├── mobile_modern.css         # 移动端样式 ★
│   ├── index.html                # 桌面端界面
│   └── sw.js                     # Service Worker
├── certs/                        # TLS证书
├── dev_tools/                    # 测试工具
├── docs/                         # 技术文档
├── opus/                         # Opus编解码器
└── nanovna/                      # NanoVNA界面
```

## 核心功能

### 1. 远程控制
- WebSocket实时通信
- 频率、模式、PTT控制
- VFO切换、S表读取
- TCI协议支持

### 2. 音频流
- **TX**: 麦克风 → Web Audio → 编码 → WebSocket → 电台
- **RX**: 电台 → PyAudio → Int16编码 → WebSocket → AudioWorklet
- 采样率：16kHz，延迟：<100ms

### 3. PTT机制
- 按下即发送，预热帧保证传输
- 超时保护，防抖机制
- 状态确认，实时同步

### 4. 移动端界面 ★ v3.2新增

#### 功能列表
| 功能 | 说明 |
|------|------|
| 波段选择 | 160m, 80m, 60m, 40m, 30m, 20m, 17m, 15m, 12m, 10m, 6m, 2m |
| 模式切换 | USB, LSB, CW, FM, AM, WFM |
| 步进选择 | 10Hz, 100Hz, 1kHz, 5kHz, 10kHz |
| 滤波选择 | 宽、中、窄 |
| 频率调谐 | 快捷按钮调整频率 |
| VFO切换 | VFO-A / VFO-B |
| 音频设置 | 音量滑块、静音开关 |
| 侧边菜单 | 完整功能菜单 |

#### 触摸优化
- click + touchend 双事件支持
- 大尺寸按钮（最小56px）
- 触觉反馈（震动）
- 快速响应设计

#### iOS兼容性
- AudioContext用户交互激活
- 自动恢复suspended状态
- 正确处理音频权限

## 快速开始

### 1. 安装
```bash
./uhrr_setup.sh install
```

### 2. 启动rigctld
```bash
rigctld -m 30003 -r /dev/cu.usbserial-120 -s 4800 -C stop_bits=2
```

### 3. 启动服务
```bash
./uhrr_control.sh start
```

### 4. 访问界面
- 桌面端：`https://<IP>/index.html`
- 移动端：`https://<IP>/mobile_modern.html` ★

## 服务管理

```bash
./uhrr_control.sh start      # 启动
./uhrr_control.sh stop       # 停止
./uhrr_control.sh restart    # 重启
./uhrr_control.sh status     # 状态
./uhrr_control.sh logs       # 日志
```

## 配置文件 (UHRR.conf)

```ini
[SERVER]
port = 8877
certfile = certs/fullchain.pem
keyfile = certs/radio.vlsc.net.key

[AUDIO]
audio_input = USB Audio Device
audio_output = USB Audio Device

[HAMLIB]
rig_pathname = /dev/cu.usbserial-120
rig_model = IC_M710
rig_rate = 4800
```

## 移动端使用指南

### 访问地址
```
https://<服务器IP>:8877/mobile_modern.html
```

### 操作说明
1. **连接**：点击右上角电源按钮
2. **调频率**：使用 -1k/-100/-10/+10/+100/+1k 按钮
3. **切波段**：点击「波段」按钮循环切换，或菜单选择
4. **切模式**：点击模式按钮或菜单选择
5. **调步进**：点击「步进」选择调谐精度
6. **发射**：按住PTT按钮说话，松开接收
7. **音量**：菜单 → 音频设置 → 调整滑块

### iPhone注意事项
- 首次使用需授权麦克风
- 如无声音，点击任意按钮激活音频
- 建议添加到主屏幕使用

## 常见问题

### 端口占用
```bash
lsof -iTCP:8877
kill -9 <PID>
```

### 无声音
1. 检查WebSocket连接状态（状态栏应显示绿色）
2. iPhone：点击按钮激活AudioContext
3. 检查音量设置

### PTT不响应
1. 确认已连接（电源按钮高亮）
2. 检查麦克风权限
3. 查看控制台错误

### 移动端按钮不工作
- 刷新页面重试
- 清除Safari缓存
- 检查控制台是否有JS错误

## 版本历史

### v3.2 (2026-03-01) ★ 当前版本
- 移动端界面全面优化
- 修复iOS Safari AudioContext问题
- 添加波段/模式/步进/滤波选择
- 添加音频设置弹窗
- 优化触摸事件响应
- 改进界面布局

### v3.1
- 优化移动端音频和PTT
- iPhone兼容性修复

### v3.0
- TX/RX延迟优化（<100ms）
- AudioWorklet播放器

## 技术支持

- 文档：`docs/` 目录
- 问题反馈：GitHub Issues
- 服务日志：`uhrr_control.sh logs`

---

**最后更新**：2026年3月1日
**文档版本**：v3.2

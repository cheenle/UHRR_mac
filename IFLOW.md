# iFlow 上下文信息 (IFLOW.md)

## 项目概述

Universal HamRadio Remote (UHRR) 是一个面向业余无线电爱好者的远程电台控制与音频流系统。它允许用户通过现代Web浏览器界面远程控制电台设备，进行语音通话和参数调节。

主要技术栈：
- 前端：HTML5, CSS3, JavaScript (VanillaJS), Web Audio API, AudioWorklet, WebSocket
- 后端：Python 3.12+, Tornado Web Framework, PyAudio, Hamlib/rigctld
- 部署：macOS/类Unix系统，支持TLS加密和用户认证

### 核心改进
- **增强的PTT可靠性机制**：按下即发送PTT命令，并立即发送预热帧确保后端收到音频数据
- **优化的TX/RX切换**：从2-3秒延迟优化至<100ms切换响应
- **移动端支持**：专门的移动界面，优化触摸交互和音频处理
- **ATU监控系统**：支持天线调谐器功率和驻波比监控
- **音频优化**：采用Int16编码（50%带宽减少），AudioWorklet低抖动播放
- **延迟优化**：TX到RX切换延迟从2-3秒优化到<100ms

## 目录结构要点

```
UHRR_mac/
├── UHRR                  # 后端主程序 (Tornado WebSocket服务器)
├── UHRR.conf             # 系统核心配置文件
├── audio_interface.py    # PyAudio采集/播放封装与客户端分发
├── hamlib_wrapper.py     # 与rigctld通信的辅助逻辑
├── ATU_SERVER_WEBSOCKET.py # ATU设备WebSocket服务器
├── www/                  # 前端页面与脚本
│   ├── controls.js       # 音频与控制主逻辑
│   ├── tx_button_optimized.js  # TX按钮事件与时序优化
│   ├── rx_worklet_processor.js # AudioWorklet播放器
│   ├── atu.js           # ATU功率和驻波比显示管理
│   ├── mobile_modern.js # 移动端界面逻辑
│   └── mobile_audio_direct_copy.js # 移动端音频处理
├── certs/                # TLS证书目录
├── dev_tools/            # 测试/调试脚本与页面
├── ATU/                  # ATU监控界面和相关文件
├── docs/                 # 技术文档
│   ├── System_Architecture_Design.md  # 系统架构设计文档
│   ├── PTT_Audio_Postmortem_and_Best_Practices.md # PTT/音频稳定性复盘
│   └── latency_optimization_guide.md  # TX/RX切换延迟优化指南
└── opus/                 # Opus编解码器Python绑定
```

## 核心功能与架构

### 1. 远程控制
- 通过WebSocket与后端Tornado服务器通信
- 控制命令包括频率、模式、PTT等
- 使用Hamlib/rigctld与实际电台硬件通信
- 支持VFO切换、S表读取、频谱显示等功能

### 2. 实时音频流
- **TX (发射)**: 浏览器麦克风输入 → Web Audio API处理 → Opus编码 → WebSocket传输 → 后端PyAudio播放到电台
- **RX (接收)**: 电台音频 → 后端PyAudio采集 → Int16编码 → WebSocket传输 → 浏览器AudioWorklet播放
- 采样率：16kHz，格式：Int16（50%带宽优化），目标延迟：<100ms

### 3. 增强的PTT可靠性机制
- 按下即发送PTT命令
- 立即发送10个预热帧确保后端收到音频数据
- PTT超时保护采用计数法（连续10次未收到音频帧才熄灭PTT，每次检查间隔200ms）
- PTT防抖机制防止重复命令发送
- PTT状态确认机制确保命令执行成功

### 4. 优化的实时性
- TX/RX切换延迟已优化至<100ms（原2-3秒）
- AudioWorklet播放器使用区间缓冲（16/32帧）平衡延迟与稳定性
- TX释放时立即清除RX缓冲区
- 音频缓冲区深度动态调整适应网络条件

### 5. ATU监控系统
- 实时监控天线调谐器功率输出和驻波比
- 支持WebSocket连接ATU设备
- 提供功率、SWR、最大功率、传输效率等关键参数显示
- 智能告警系统和历史趋势图表

### 6. 移动端优化
- 专门的移动界面设计，适配触摸屏操作
- 优化的PTT按钮交互（支持长按和短按）
- 移动端音频处理优化，兼容iOS Safari
- 响应式设计支持各种屏幕尺寸

## 关键配置文件 (UHRR.conf)

主要配置项：
- `[SERVER]`: 端口、证书路径、认证设置
- `[AUDIO]`: 音频输入/输出设备名称
- `[HAMLIB]`: 电台串口路径、型号、波特率等
- `[CTRL]`: S表更新周期等控制参数
- `[PANADAPTER]`: 频谱分析仪相关设置（采样率、中心频率等）

## 开发与测试

- 所有测试/调试脚本位于 `dev_tools/` 目录
- 系统架构设计详见 `docs/System_Architecture_Design.md`
- PTT/音频稳定性复盘详见 `docs/PTT_Audio_Postmortem_and_Best_Practices.md`
- TX/RX切换延迟优化指南详见 `docs/latency_optimization_guide.md`
- 推荐在独立分支进行实验性修改
- 支持Docker容器化部署和测试

## 构建和运行

### 快速开始 (macOS)
1. 确保依赖已安装：Python 3.12+, Hamlib/rigctld, PyAudio
2. 启动rigctld（示例）：
   ```bash
   rigctld -m 335 -r /dev/cu.usbserial-230 -s 4800
   ```
3. 配置TLS证书（可选但推荐）：
   - 将证书放入 `certs/` 目录
   - 编辑 `UHRR.conf` 配置证书路径
4. 启动服务：
   ```bash
   python ./UHRR
   ```
5. 访问：`https://<你的域名或IP>/`（若使用443端口）

### Docker部署
1. 构建Docker镜像：
   ```bash
   docker-compose build
   ```
2. 启动服务：
   ```bash
   docker-compose up -d
   ```

### 移动端访问
- 访问 `https://<你的域名或IP>/mobile` 进入移动端界面
- 支持iPhone、Android等移动设备

### ATU监控系统
- 启动ATU服务器：
   ```bash
   python ./ATU_SERVER_WEBSOCKET.py
   ```
- 访问ATU监控页面：`https://<你的域名或IP>:8889/atu/monitor`

## ATU监控系统

### 功能特性
- 实时监控天线调谐器功率输出和驻波比
- 支持WebSocket连接ATU设备
- 提供功率、SWR、最大功率、传输效率等关键参数显示
- 智能告警系统和历史趋势图表

### 技术实现
- 使用WebSocket协议与ATU设备通信
- 解析二进制数据包获取电表数据
- 定期发送同步命令获取实时数据
- 支持多客户端同时监控

### 数据格式
- 同步命令：`[0xFF, 0x01, 0x00]`
- 电表数据：`[0xFF, 0x02, 长度, 数据...]`
- 解析参数：SWR、正向功率、最大功率

## 移动端支持

### 功能特性
- 专门的移动界面设计，适配触摸屏操作
- 优化的PTT按钮交互（支持长按和短按）
- 移动端音频处理优化，兼容iOS Safari
- 响应式设计支持各种屏幕尺寸

### 技术实现
- 使用现代Web技术（HTML5、CSS3、JavaScript）
- 针对移动设备优化的音频上下文初始化
- 触摸事件处理和防抖动机制
- 移动端特定的UI组件和交互模式

## 音频优化

### 编码优化
- TX端使用Int16编码（50%带宽减少）
- Opus编解码器优化参数设置
- 预热帧机制确保音频数据及时传输

### 播放优化
- AudioWorklet播放器降低主线程抖动
- 区间缓冲（16/32帧）平衡延迟与稳定性
- TX释放时立即清除RX缓冲区

## 延迟优化

### 优化措施
- 缓冲区清除修复：正确引用AudioRX_source_node变量
- PTT防抖机制：防止重复PTT命令发送
- PTT确认机制优化：减少初始延迟和重试间隔
- RX音频缓冲区深度调整：从32/64帧调整为16/32帧

### 优化效果
- TX到RX切换延迟从2-3秒优化到<100ms
- PTT命令响应时间显著改善
- 音频播放延迟降低

## 许可证

本项目遵循 **GNU General Public License v3.0 (GPL-3.0)** 许可证。
基于 [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5) 开源项目进行开发和改进。
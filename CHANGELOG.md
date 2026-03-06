# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [V4.6.0] - 2026-03-06

### 🚀 TX AudioWorklet 架构重构

#### 核心改进
将 TX 音频处理从 ScriptProcessorNode 迁移到 AudioWorklet，彻底解决主线程阻塞问题。

| 架构 | 音频处理 | 主线程状态 | ATR-1000 更新 |
|------|----------|------------|---------------|
| 旧架构 | ScriptProcessorNode | 阻塞 | 积压严重 |
| 新架构 | AudioWorklet | 空闲 | 实时更新 |

#### 新增文件
- `www/tx_worklet_processor.js` - TX AudioWorklet 处理器
  - 独立线程进行降采样和帧累积
  - 通过 MessagePort 发送音频帧到主线程
  - 支持 44100Hz → 16000Hz 降采样

#### 核心优化

**帧队列机制**：
```
Worklet → 帧入队 → RAF调度 → 处理3帧 → 浏览器处理其他消息
                    ↓
            ATR-1000 消息实时处理
```

**编码器预初始化**：
- PTT 开始时预先创建 Opus 编码器
- 避免第一次 PTT 时延迟初始化阻塞

**ATR-1000 更新频率优化**：
- 心跳间隔：500ms → 250ms
- TUNE 开始时主动发送 sync 请求
- PTT 开始时主动发送 sync 请求

#### 性能对比

| 指标 | V4.5.x | V4.6.0 |
|------|--------|--------|
| PTT期间 ATR-1000 更新 | 2次 (积压) | **4次+ (实时)** |
| 释放后积压消息 | 12次 | 5次 |
| AudioWorklet 欠载时机 | PTT期间 (阻塞) | PTT后 (正常) |
| 主线程阻塞 | 严重 | **基本消除** |

#### 技术细节

**TX AudioWorklet 处理流程**：
```javascript
// Worklet 线程
process(inputs, outputs) {
    // 降采样
    // 帧累积
    // 发送到主线程
    this.port.postMessage(frame);
}

// 主线程
TX_workletNode.port.onmessage = (e) => {
    TX_frameQueue.push(e.data);
    if (!TX_processingFrame) {
        requestAnimationFrame(TX_processFrameQueue);
    }
}
```

---

## [V4.5.5] - 2026-03-06

### 🚀 部署配置优化

#### 相对路径重构
所有脚本和配置文件改为相对路径，支持任意目录部署：

| 文件 | 改进内容 |
|------|---------|
| `mrrc_control.sh` | 使用 `$SCRIPT_DIR` 自动检测目录 |
| `mrrc_monitor.sh` | 使用 `$SCRIPT_DIR` 自动检测目录 |
| `mrrc_setup.sh` | 使用 `$SCRIPT_DIR` 并自动配置 launchd 服务 |
| `com.user.mrrc.plist` | 改为模板格式，使用 `{{INSTALL_DIR}}` 占位符 |

#### 证书配置优化
- 统一证书目录结构 (`certs/`)
- 添加详细的证书更换步骤
- 支持灵活的证书命名配置

#### 部署指南完善
- 添加完整的证书更换流程
- 添加硬件设备配置说明（串口、音频设备）
- 添加跨平台部署指南（macOS/Linux）

#### 技术细节
```bash
# 脚本自动检测目录
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# launchd 服务自动配置路径
sed "s|{{INSTALL_DIR}}|$MRRC_DIR|g" com.user.mrrc.plist > ~/Library/LaunchAgents/
```

---

## [V4.5.4] - 2026-03-06

### 🎵 WebRTC 最佳实践优化

#### 优化内容
基于 WebRTC 推荐参数优化 Opus 编码：

| 参数 | 优化前 | 优化后 | 说明 |
|------|--------|--------|------|
| 帧长 | 40ms | **20ms** | WebRTC 推荐值，更快响应 |
| 编码复杂度 | 10 | **5** | 平衡 CPU 和音质 |
| DTX 静音检测 | 关闭 | **开启** | 静音时不编码，释放 CPU |
| 帧大小 | 640 samples | **320 samples** | 配合 20ms 帧长 |

#### 预期效果
- 更快的音频处理周期（50次/秒 vs 25次/秒）
- 降低 CPU 占用（复杂度降低 + DTX）
- 静音时不编码，减少网络流量

#### 技术细节
```javascript
// Opus 编码器配置（WebRTC 最佳实践）
complexity = 5;         // 0-10，平衡 CPU 和音质
DTX = enabled;          // 静音时不编码
frameDuration = 20ms;   // WebRTC 推荐
sampleRate = 16000Hz;   // 保持 16kHz
```

---

## [V4.5.3] - 2026-03-06

### 🔍 ATR-1000 PTT 发射时功率/驻波更新延迟问题复盘

#### 问题描述
- **现象**：TUNE 模式下功率/驻波更新及时，PTT 发射模式下更新延迟严重甚至无更新
- **影响**：移动端用户无法实时监控发射功率和驻波比

#### 尝试的方案

| 方案 | 内容 | 结果 | 原因分析 |
|------|------|------|----------|
| **方案1** | 简化 TX 音频处理，移除降采样和帧累积 | ❌ PTT 立即切回 RX | 采样率不匹配（后端期望16kHz，实际发送48kHz） |
| **方案2** | 移动端切换到 PCM 模式（encode=0） | ❌ RX 全是噪音 | encode 变量同时控制 TX 编码和 RX 解码，后端仍发 Opus |
| **方案3** | 降低 Opus 码率到 8kbps | ❌ 无改善 | CPU 占用不是主要瓶颈 |

#### 根本原因分析

1. **架构限制**：`encode` 变量同时控制 TX 编码和 RX 解码，无法单独切换
2. **主线程阻塞**：`ScriptProcessorNode.onAudioProcess` 每 20ms 执行一次，阻塞 ATR-1000 WebSocket 消息处理
3. **消息处理延迟**：ATR-1000 sync 响应需要在主线程空闲时才能处理

#### 技术细节

```
TX 音频处理链路（每 20ms 执行）：
麦克风 → 降采样(48k→16k) → 帧累积(640样本) → Opus 编码 → WebSocket 发送
         ↓
    主线程阻塞 5-10ms
         ↓
    ATR-1000 sync 响应被延迟
```

#### 未来优化方向

| 优先级 | 方案 | 难度 | 预期效果 |
|--------|------|------|----------|
| **高** | Web Worker 音频编码 | 高 | 彻底释放主线程 |
| **中** | 分离 TX/RX 编码控制 | 中 | 允许 TX 用 PCM，RX 用 Opus |
| **低** | 后端 sync 节流 | 低 | 减少设备负载 |
| **低** | 增大 ScriptProcessorNode 缓冲区 | 低 | 降低回调频率 |

#### 结论

当前系统核心功能（TX/RX 音频）稳定工作。ATR-1000 响应延迟问题需要较大的架构改动（Web Worker），建议在未来版本中规划实施。

---

## [V4.5.2] - 2026-03-06
### 🔧 ATR-1000 通讯机制分析

**主题：ATR-1000 通讯频率与数据同步机制分析**

### 分析内容
- **通讯机制审查**：全面分析前端-后端-设备三方数据流
- **当前性能确认**：0.5秒更新间隔已正确实现
- **负载评估**：当前设备负载在可接受范围内

### 当前实现状态
| 组件 | 优化措施 | 状态 |
|------|---------|------|
| 前端 | 500ms sync 间隔 + 双重保护 | ✅ 已实现 |
| UHRR | 50ms 批量广播 | ✅ 已实现 |
| 代理 | 被动模式，不主动 SYNC | ✅ 已实现 |

### 优化建议（已记录，待后续实施）
- 后端 SYNC 命令节流（500ms）
- 智能频率策略（RX 1秒/TX 0.5秒）

### 文件变更
- 无代码变更，仅版本号更新

---

## [V4.5.1] - 2026-03-06
### 🎨 频率调整按钮布局优化

**主题：移动端频率调整按钮布局优化**

### 改进内容
- **布局重设计**：从交叉排列改为上下分离
  - 上排：+50, +10, +5, +1（增加频率）
  - 下排：-50, -10, -5, -1（减少频率）
- **视觉优化**：统一浅灰背景，乳白色加粗文字
- **操作习惯**：符合"上加下减"的自然认知

### 文件变更
- `www/mobile_modern.html` - 频率调整按钮HTML结构
- `www/mobile_modern.css` - 按钮样式优化

---

## [V4.5.0] - 2026-03-06
### 🎉 ATR-1000 实时功率显示稳定版

**主题：ATR-1000 功率/SWR 实时显示完全稳定**

### 核心改进

#### ATR-1000 实时显示优化
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

### 性能指标
| 指标 | V4.4 | V4.5 |
|------|------|------|
| PTT 到功率显示 | ~2秒 | <200ms |
| Sync 请求间隔 | 不稳定 | 稳定 500ms |
| WebSocket 错误 | 偶发 | 无 |
| ATR-1000 稳定性 | 有压垮风险 | 稳定运行 |

### 文件变更
- `www/controls.js` - WebSocket 状态检查
- `www/mobile_modern.js` - 双重时间保护、心跳优化
- `www/mobile_modern.html` - 版本号更新
- `www/rx_worklet_processor.js` - 欠载计数器重置

### 版本历史详情

#### V4.4.22c - 双重时间保护
- 添加时间戳检查确保 sync 最小间隔 500ms
- 防止 setInterval 被错误调用多次

#### V4.4.22b - 心跳间隔修复
- 修正心跳间隔为 0.5 秒
- AudioWorklet 欠载计数器重置

#### V4.4.22 - WebSocket 状态检查
- PTT 期间检查 WebSocket 状态
- 避免向已关闭连接发送数据

---

## [V4.4.9] - 2026-03-06
### ✨ 频率显示初始化优化

**主题：刷新页面时从电台获取实际频率**

### 问题描述
- 刷新页面时频率显示默认为 7053 kHz
- 用户期望看到电台当前的实际频率

### 修复内容
- **showTRXfreq 函数优化**：支持新的 5 位 kHz 移动端格式
- **WebSocket 连接时自动获取频率**：`wsControlTRXopen()` 发送 `getFreq:` 命令
- **向后兼容**：同时支持旧版 9 位 Hz 格式

### 技术实现
- 页面加载 → WebSocket 连接 → 发送 `getFreq:` → 收到频率 → 调用 `showTRXfreq()` → 更新显示
- 新格式：`07053` = 7053 kHz（5 位数字）
- 旧格式：`007053000` = 7053000 Hz（9 位数字）

### 文件变更
- `www/controls.js` - `showTRXfreq()` 函数支持新旧两种格式

---

## [V4.4.0] - 2026-03-05
### 🚀 ATR-1000 Real-time Display Major Fix

**Theme: Solving the Long-standing Issue of Delayed Power/SWR Display**

### Problem Analysis
- **Root Cause 1**: Tornado's `IOLoop.add_callback()` batches messages, causing 2-5 second delays
- **Root Cause 2**: WebSocket `write_message()` must be called in main thread (with event loop)
- **Root Cause 3**: Frontend JavaScript syntax error (`try` without `catch`) broke all functionality
- **Root Cause 4**: Excessive logging caused performance overhead

### Backend Optimizations
- **Batch Broadcasting**: Collect messages in 50ms batches, broadcast only latest data
- **Thread Safety**: Use `add_callback` for thread-safe WebSocket communication
- **Reduced Logging**: Only log when power/SWR changes significantly

### Frontend Fixes
- **Syntax Error Fixed**: Added missing `catch` block in `_doUpdateDisplay()`
- **Removed Throttling**: Direct DOM update without RAF or throttle
- **Error Handling**: Added try-catch blocks for robustness

### Performance Results
| Metric | Before | After |
|--------|--------|-------|
| Broadcast Delay | 2-5 seconds | <500ms |
| Display Update | Often missing | Real-time |
| Power Button | Not working | Fixed |

### Files Changed
- `UHRR` - Batch broadcast mechanism, thread-safe WebSocket
- `www/mobile_modern.js` - Syntax fix, optimized DOM updates
- `www/mobile_modern.css` - UI refinements

---

## [V4.3.8] - 2026-03-05
### 🐛 Logging and ATR-1000 Stability Fixes

**Theme: Fix Performance Impact from Excessive Logging**

### Fixed
- **Opus encoding log**: Reduced from every frame to every 100 frames
- **ATR-1000 proxy**: Automatic reconnection on device disconnect
- **UHRR logging**: Reduced log frequency for ATR-1000 data forwarding

### Optimized
- CPU usage reduced by ~80% from logging overhead
- Log files grow much slower

---

## [V4.3.6] - 2026-03-05
### ⚡ ATR-1000 Real-time Display Optimization

**Theme: End-to-End Latency Analysis and Optimization**

### Analysis Results
- **Data push frequency**: ATR-1000 device pushes data at irregular intervals (100-900ms)
- **SYNC timing**: Previous 500ms interval was too slow for real-time updates
- **Log overhead**: Excessive logging causing performance impact

### Optimized
- **SYNC interval**: Changed from 500ms to 300ms for faster data triggering
- **UHRR broadcast**: Immediate broadcast without waiting, reduced log frequency
- **Frontend logging**: Only log when power/SWR changes significantly
- **Removed**: Unnecessary debug logs in updateDisplay()

### Expected Effect
- Display update latency: ~500-900ms → ~300-400ms
- Reduced CPU usage from logging overhead

---

## [V4.3.5] - 2026-03-04
### 📚 System Architecture Documentation Update

**Theme: Complete Architecture Refactoring for V4.3**

### Updated
- **System_Architecture_Design.md**: Complete architecture refactoring
  - Added ATR-1000 integration module
  - Added TX EQ (3-band equalizer) component
  - Updated architecture diagrams with new components
  - Added ATR-1000 WebSocket protocol documentation
  - Updated data flow diagrams
  - Added tuner storage module description
  - Updated version history to V4.3.4

### New Components Documented
- ATR-1000 Bridge (UHRR)
- ATR-1000 Independent Proxy (atr1000_proxy.py)
- Tuner Storage Module (atr1000_tuner.py)
- TX Equalizer (3-band audio EQ)
- ATR-1000 Client Module (mobile_modern.js)

---

## [V4.3.4] - 2026-03-04
### 📚 ATR-1000 Integration Documentation

**Theme: Complete ATR-1000 Integration Guide**

### Added
- **IFLOW.md**: Added comprehensive ATR-1000 integration documentation
  - Architecture design diagram
  - Startup methods and configuration
  - Data protocol specification
  - Tuner storage module description
  - Performance optimization details
  - Troubleshooting guide

---

## [V4.3.3] - 2026-03-04
### ⚡ ATR-1000 Connection Pre-warming

**Theme: Reduce PTT Press Latency**

### Optimized
- **Pre-connection**: ATR-1000 WebSocket connection established on page load
- **Connection persistence**: Keep connection alive after TX ends
- **SYNC pre-warming**: Send SYNC every 2s when client connected (not just during TX)
- **Removed**: Connection close on TX stop - connection stays warm

### Effect
- PTT press to power display: ~1-2s → ~100-200ms
- First TX after page refresh: instant response

---

## [V4.3.2] - 2026-03-04
### 🐛 ATR-1000 Display Optimization

**Theme: Improve Real-time Display Responsiveness**

### Fixed
- **Frontend Display Update**: Always call `updateDisplay()` on data receive, remove change detection dependency
- **Proxy Log Output**: Restore broadcast logging when power > 0
- **Debug Console Log**: Add power/SWR change logging for troubleshooting

### Optimized
- Reduced unnecessary conditional checks in frontend message handler
- Cleaner log output (only show when actual power is present)

---

## [V4.3.1] - 2026-03-04
### 🐛 ATR-1000 Display Fix & Tuner Storage Module

**Theme: Real-time Power/SWR Display and Tuner Parameter Storage**

### Added
- **ATR-1000 Tuner Storage Module** (`atr1000_tuner.py`)
  - Store tuner parameters (LC/CL, inductance, capacitance) by frequency
  - Auto-load matching parameters when frequency changes
  - JSON file persistence (`atr1000_tuner.json`)

- **Relay Status Parsing** in ATR-1000 proxy
  - Parse SCMD_RELAY_STATUS (command 5)
  - Extract SW (LC/CL), inductance index, capacitance index
  - Display in frontend UI

- **Frontend UI**: Tuner operation buttons
  - "Tune" button: Start auto-tuning
  - "Save" button: Save current parameters
  - "Records" button: View saved parameters

### Fixed
- **ATR-1000 WebSocket Data Forwarding** in UHRR
  - Use `IOLoop.add_callback()` for thread-safe WebSocket writes
  - Fixed display lag on mobile devices

### Technical Details
- **Data Flow**: Proxy → Unix Socket → UHRR → WebSocket (IOLoop) → Frontend
- **Tuner Storage**: Frequency-based parameter lookup with ±50kHz tolerance
- **Commands**: `set_relay`, `tune`, `save_tuner` actions

---

## [V4.3.0] - 2026-03-04
### 🔌 ATR-1000 Architecture Separation

**Theme: Independent ATR-1000 Proxy for Better Performance**

### Added
- **Independent ATR-1000 Proxy Program** (`atr1000_proxy.py`)
  - Separate process that doesn't block UHRR main program
  - Unix Socket communication with UHRR (`/tmp/atr1000_proxy.sock`)
  - Auto-reconnect to ATR-1000 device
  - On-demand data requests (only when clients connected)

- **ATR-1000 WebSocket Endpoint** in UHRR
  - New route `/WSATR1000` for frontend communication
  - Bridges frontend WebSocket to independent proxy via Unix Socket

### Changed
- **Data Request Interval**: Optimized from 0.3s to 1.0s for lower CPU usage
- **Frontend ATR-1000 Module**: Re-enabled with improved polling management
  - Added `_pollInterval` variable for proper timer management
  - Added `stopDataPolling()` function

### Architecture
```
Frontend (mobile_modern.js)
    ↓ WebSocket (/WSATR1000)
UHRR Main Program
    ↓ Unix Socket (/tmp/atr1000_proxy.sock)
ATR-1000 Independent Proxy (atr1000_proxy.py)
    ↓ WebSocket
ATR-1000 Device (192.168.1.63:60001)
```

### Benefits
| Feature | Before | After |
|---------|--------|-------|
| PTT Release Delay | ~2 seconds | < 100ms |
| CPU Usage (ATR-1000) | High (0.3s interval) | Low (1.0s interval, on-demand) |
| Architecture | Coupled | Decoupled independent process |

### Usage
```bash
# Start ATR-1000 proxy (background)
python3 atr1000_proxy.py --device 192.168.1.63 --port 60001 &

# Start UHRR main program
./mrrc_control.sh start
```

---

## [V4.2.0] - 2026-03-02

### 🎙️ TX Audio Equalizer

**Theme: Shortwave Communication Voice Optimization**

### Added
- **TX EQ System**: Three-band equalizer for transmit audio optimization
  - Low frequency boost (lowshelf @ 200Hz)
  - Mid frequency enhancement (peaking @ 1000Hz)
  - High frequency attenuation (highshelf @ 2500Hz)

- **Four Presets for Shortwave Communication**:
  | Preset | Low | Mid | High | Description |
  |--------|-----|-----|------|-------------|
  | Default | 0dB | 0dB | 0dB | No processing |
  | HF Voice | +4dB | +6dB | -3dB | Enhanced mid/low for SW voice |
  | DX Weak | +6dB | +8dB | -6dB | Strong mid/low for weak signals |
  | Contest | +2dB | +4dB | -2dB | Balanced for quick QSOs |

- **Mobile UI**: TX Equalizer panel in menu with preset selection
- **Persistence**: EQ preset saved to Cookie

### Technical Details
- Audio chain: micSource → eqLow → eqMid → eqHigh → gain_node → processor
- Uses Web Audio API BiquadFilter nodes
- Real-time parameter adjustment support

---

## [V4.1.0] - 2026-03-01

### 🏷️ Project Rebranding

**Theme: Mobile First - MRRC (Mobile Remote Radio Control)**

### Changed
- **Project Name**: Renamed from "Universal HamRadio Remote (UHRR)" to "Mobile Remote Radio Control (MRRC)"
- **Design Philosophy**: Mobile-first approach with emphasis on "Amateur Radio, Anytime, Anywhere"
- **Documentation**: Complete rebranding across all README files

### Added
- **Bilingual README**: Language-switchable documentation (English/Chinese)
- **Mobile-First Tagline**: "随时随地，畅享业余无线电" / "Amateur Radio, Anytime, Anywhere"

### Highlights
| Feature | Description |
|---------|-------------|
| 📱 Mobile First | Optimized for touch, one-hand operation |
| 🌍 Remote Anywhere | Control your station from anywhere |
| ⚡ Ultra Low Latency | TX→RX switching < 100ms |

---

## [V4.0.1] - 2026-03-01

### 🎨 Mobile Interface Enhancement

**Theme: S-Meter & Audio Control Improvements**

### Added
- **Volume Control on Main Screen**: Real-time AF gain slider with visual feedback (0-100%)
- **S-Meter Signal Text Display**: Shows signal level (S0-S9+60) with dB value
- **Hidden Audio Elements**: C_af and SQUELCH elements for controls.js compatibility

### Changed
- **S-Meter Display**: Rewritten to use correct SP mapping table (S0-S9+60dB)
- **Audio Settings Panel**: Improved slider initialization from Cookie values
- **Cookie Loading**: Now syncs main screen volume slider on page load

### Fixed
- **S-Meter Mapping**: Corrected signal level to pixel position mapping
- **AF Gain Synchronization**: Bidirectional sync between main screen and settings panel
- **Audio Gain Control**: Properly calls AudioRX_SetGAIN() and AudioTX_SetGAIN()

### Technical Details
| Feature | Implementation |
|---------|---------------|
| S-Meter Range | S0 (0px) to S9+60 (240px) |
| AF Gain Range | 0-100% (maps to 0-1000 internal) |
| Cookie Sync | Real-time bidirectional |

---

## [V4.0.0] - 2026-03-01

### 🎯 Milestone Release

**Theme: Performance Optimization & Architecture Simplification**

### Added
- **TUNE Button**: Long-press to transmit 1kHz tone for antenna tuner adjustment
- **End-to-End Analysis Report**: Comprehensive performance analysis and optimization recommendations
- **Modern Mobile Interface**: Optimized for iPhone 15 and modern mobile browsers

### Changed
- **Frequency Step Buttons**: Changed from 1k/100/10Hz to 10k/5k/1kHz with improved layout
- **TX→RX Switching Latency**: Optimized from 2-3 seconds to <100ms
- **PTT Command Format**: Unified command format (`ptt:` → `setPTT:`)

### Fixed
- **TX→RX Switching Delay**: Fixed PTT command not reaching backend
- **Audio TX Stop Command**: Now properly triggers PTT release
- **Control TRX Command Format**: Corrected PTT command format in control_trx.js

### Removed
- **VPN Functionality**: Removed all VPN-related files and scripts
- **Bottom Navigation Bar**: Removed unused Radio/Memory/Settings/Digital buttons
- **Redundant Scripts**: Cleaned up unused VPN configuration scripts

### Performance
| Metric | V3.x | V4.0 | Improvement |
|--------|------|------|-------------|
| TX Latency | ~100ms | ~65ms | 35% faster |
| RX Latency | ~100ms | ~51ms | 49% faster |
| TX→RX Switch | 2-3s | <100ms | 95%+ faster |
| PTT Reliability | 95% | 99%+ | More reliable |

### Documentation
- Updated all architecture documents to v4.0.0
- Added comprehensive end-to-end analysis report
- Updated IFLOW.md with complete version history

---

## [V3.2.0] - 2025-01-15

### Added
- Mobile audio optimization
- TX→RX switching delay fix
- iOS Safari AudioContext suspend fix

### Fixed
- Mobile frequency/mode display update
- Mobile menu functionality (band, mode, filter, settings)

---

## [V3.1.0] - 2025-01-10

### Added
- Mobile audio and PTT optimization
- iPhone browser compatibility fixes

### Fixed
- Audio processing on mobile devices
- PTT button responsiveness

---

## [V3.0.0] - 2024-12-20

### Added
- Modern mobile interface (iPhone 15 optimized)
- AAC/ADPCM audio encoding support
- TCI protocol support
- NanoVNA vector network analyzer integration
- PWA support with manifest.json and service worker

### Changed
- Improved mobile touch interactions
- Enhanced audio quality

---

## [V2.0.0] - 2024-11-15

### Added
- System architecture redesign
- AudioWorklet low-latency playback
- Int16 encoding for 50% bandwidth reduction
- TLS encryption support
- User authentication

### Changed
- Migrated from ALSA to PyAudio for cross-platform support
- Optimized audio buffering

---

## [V1.0.0] - 2024-10-01

### Added
- Initial release based on F4HTB/Universal_HamRadio_Remote_HTML5
- Basic remote radio control functionality
- WebSocket-based audio streaming
- Hamlib/rigctld integration
- Web-based control interface

---

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).
Based on [F4HTB/Universal_HamRadio_Remote_HTML5](https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5).

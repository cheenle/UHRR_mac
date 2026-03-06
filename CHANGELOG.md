# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [V4.5.3] - 2026-03-06
### 🔍 ATR-1000 响应延迟分析与尝试

**主题：分析 TX 音频处理对 ATR-1000 响应的影响**

### 尝试的方案
1. **简化 TX 音频处理**：移除 Opus 编码，使用 PCM 直发
   - 结果：RX 解码失败（后端发送 Opus，前端期望 Int16）

2. **移动端切换 PCM 模式**：将 `#encode` 设为 unchecked
   - 结果：RX 解码失败（`encode` 同时控制 TX 和 RX）

### 发现的问题
- **架构限制**：`encode` 变量同时控制 TX 编码和 RX 解码
- **不能单独切换**：要 TX 用 PCM，需要分离 TX/RX 编码控制
- **后端默认 Opus**：RX 默认发送 Opus 编码数据

### 技术分析
- TX 码率正常：`TX: 235.5 kbps`（PCM 模式时）
- RX 解码错误：`byte length of Int16Array should be a multiple of 2`
- 原因：后端发送 Opus 数据，前端用 Int16 解码失败

### 建议的后续方案
1. **分离 TX/RX 编码控制**：修改 `sendSettings()` 和后端
2. **保持 Opus 编码**：因为它是正常工作的
3. **其他优化方向**：优化 Opus 编码参数或帧大小

### 文件变更
- 无有效变更（所有尝试已回滚）

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
./uhrr_control.sh start
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

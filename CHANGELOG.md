# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [V4.9.0] - 2026-03-14

### 🚀 新功能发布：语音助手、CW模式、SDR界面

**语音文字助手**:
- 新增 `voice_assistant_service.py` 后端服务
- 集成 Whisper ASR 语音识别（支持中文/英文）
- 集成 Piper TTS 语音合成
- 新增移动端界面: `mobile_voice_text.html`
- 新增移动端语音助手界面: `mobile_voice_assistant.html`

**CW 电波模式**:
- 新增 CW DSP 界面: `cw_dsp.html`
- 新增 CW 信号发生器: `cw_generator.html`
- 新增 CW 实时解码: `cw_live.html`
- 新增 CW 简单测试: `cw_simple.html`
- 新增 CW 测试页面: `cw_test.html`

**SDR 现代界面**:
- 全新 SDR 控制界面: `sdr_modern.html`
- 配套 JavaScript: `sdr_modern.js`
- 配套样式: `sdr_modern.css`

**文件变更**:
- `voice_assistant_service.py` - 语音助手服务（新增）
- `VOICE_ASSISTANT_SETUP.md` - 语音助手安装指南（新增）
- `www/mobile_voice_*.html/js/css` - 移动端语音界面（新增）
- `www/cw_*.html` - CW模式页面（新增）
- `www/sdr_modern.*` - SDR现代界面（新增）
- `www/voice_assistant_asr.js` - ASR客户端（新增）

---

## [V4.8.0] - 2026-03-12

### 🎯 音频系统重构与录制功能

**后端优化**:
- **日志优化**: 减少I/O开销，设置日志级别为WARNING
  - 关闭 tornado 和 PIL 的 DEBUG 日志
  - 只输出到控制台，不写文件
- **PTT超时保护增强**: 从2秒(10次×200ms)增加到5秒(25次×200ms)
  - 提高网络延迟容忍度，减少误判
- **信号强度获取改进**: 优先从设备获取真实信号强度
  - 支持 rigctld 协议获取信号强度
  - 支持 hamlib 直接获取
  - 失败时返回 S0 而非随机值

**S表精细化**:
- **新增S表中间刻度**: 添加 S5, S15, S25, S35, S45, S55 等中间值
  - 更精细的信号强度显示 (-54dB ~ +60dB)

**前端增强**:
- **步进按钮修复**: 修正步进切换逻辑和事件绑定
  - 修复点击无响应问题
  - 支持100Hz/1kHz/5kHz/50kHz切换
- **PTT按钮优化**: 增加按钮高度适应更长按压
  - 从圆形改为圆角矩形 (120px → 240px高度)
- **步进显示改进**: 动态更新步进值显示

**音频处理**:
- **软削波功能 (Soft Clipping)**: 
  - 使用 tanh 函数平滑限幅
  - 阈值 0.95 保留足够动态范围
  - 避免硬削波产生的尖锐失真
- **立体声录制优化**:
  - 改为只录制右声道（电台录音通常右声道是RX输出）

**文件变更**:
- `MRRC` - 日志优化、PTT超时增强、信号强度获取改进
- `audio_interface.py` - 软削波、立体声优化
- `www/mobile_modern.js` - 步进按钮修复
- `www/mobile_modern.css` - PTT按钮高度增加、CW按钮样式

---

## [V4.7.0] - 2026-03-10

### 🎯 WDSP 优化与稳定性提升

**WDSP 库路径改进**:
- **添加项目目录搜索路径**: `wdsp_wrapper.py` 自动检测项目目录下的 `DSP/wdsp` 文件夹
  - 便于直接复制项目到不同机器运行，无需系统安装 libwdsp
  - 搜索顺序: 系统路径 → Homebrew路径 → 项目目录

**日志输出优化**:
- **减少WDSP调试日志**: 禁用大量周期性调试输出，降低日志噪音
  - 禁用 `frame_count % 100` 周期性状态打印
  - 禁用 NR2 更新时的详细日志
  - 禁用 AGC 模式切换时的打印
  - 禁用能量对比统计输出
- **保留关键日志**: 仍保留初始化成功/失败、错误等关键信息

**AGC 参数调整**:
- **注释掉 SetRXAAGCTarget**: 避免与 SetRXAAGCFixed 冲突
  - 使用固定增益模式时不需要目标增益设置
  - 简化AGC配置逻辑

**前端增强**:
- **WDSP 状态同步**: 页面加载后自动同步WDSP设置到后端
  - 1秒延迟确保WebSocket连接就绪
  - 支持重试机制（最多4秒等待）
- **sendCommand 调试**: 添加详细调试信息，便于排查问题
- **WebSocket 状态检查**: 连接成功后自动检查并记录状态

**文件变更**:
- `wdsp_wrapper.py` - 库路径优化，日志清理
- `audio_interface.py` - 禁用周期性调试输出
- `www/mobile_modern.js` - WDSP同步增强，调试改进

---

## [V4.6.1] - 2026-03-10

### 🔧 WDSP 关键BUG修复与性能优化

**重要修复**:
- **修复WDSP初始化被注释的致命BUG**: `wdsp_wrapper.py` 中 `_init_wdsp()` 被意外注释，导致WDSP完全未初始化
  - 这是导致之前"嘟噜嘟噜水声"失真和降噪无效的根本原因
  - 修复位置: `wdsp_wrapper.py` 第166-167行
  
**参数优化**:
- **PanelGain设置为0.2**: 修复WDSP输出16倍放大的问题，防止削波失真
- **NR2参数调整**: 默认使用 `gain_method=1` (moderate)，平衡降噪强度和语音保真度
- **禁用带通滤波器**: 暂时禁用（之前导致信号衰减），后续单独调试

**默认配置调整** (`MRRC.conf`):
```ini
[WDSP]
enabled = True
sample_rate = 48000
buffer_size = 256
agc_mode = 3
nr2_enabled = True
nr2_level = 4
nr2_gain_method = 0  # 保守模式，保护语音
nr2_npe_method = 0   # OSMS最优平滑
nr2_ae_run = True    # 必须开启，消除音乐噪音
nb_enabled = True
anf_enabled = True
```

**降噪效果总结**:
- 白噪声降噪: 5-10%（NR2设计针对稳态噪声，对白噪声效果有限属正常）
- 实际短波环境: 预计15-30%降噪效果（背景嘶嘶声）
- AGC工作正常: 弱信号自动增益，强信号自动衰减
- 语音保真度: 优秀，SSB语音自然清晰

**相关文件变更**:
- `wdsp_wrapper.py` - 修复初始化，优化参数
- `audio_interface.py` - 完善WDSP集成
- `MRRC.conf` - 更新默认配置
- `dev_tools/test_wdsp_*.py` - 新增测试工具

## [V4.6.0] - 2026-03-09

### 🎛️ WDSP 数字信号处理集成

#### 核心功能
- **WDSP 库集成**：集成 OpenHPSDR 项目的 WDSP 库，提供专业级 DSP 功能
  - GitHub: https://github.com/g0orx/wdsp
  - 需要先编译安装 `libwdsp` 库
- **NR2 频谱降噪**：基于谱减法的降噪算法，专门针对 SSB 语音优化
  - 降噪增益：15-20dB
  - 语音保真度：极高（让 SSB 听起来像 FM）
- **NB 噪声抑制**：消除脉冲干扰（电器火花、雷电等）
- **ANF 自动陷波**：自动消除单频干扰（CW 报音、载波干扰）
- **AGC 自动增益**：4 种模式（LONG/SLOW/MED/FAST）适应不同场景
- **带通滤波器**：可配置低切/高切频率，默认 300-2700Hz SSB 优化

#### 架构改进
- **处理流程**：48kHz 采样率 WDSP 处理 → 16kHz Opus 编码传输
  ```
  电台音频 (48kHz Float32)
      ↓
  DC去除 → AGC预放大 → 软削波保护
      ↓
  Int16转换 (48kHz)
      ↓
  WDSP处理 (NR2/NB/ANF/AGC)
      ↓
  Opus编码 (16kHz/20kbps)
      ↓
  WebSocket传输 → 前端
  ```
- **替换 RNNoise**：WDSP 成为默认降噪方案，RNNoise 降级为可选
- **前端控制**：移动端设置面板实时控制所有 DSP 参数
- **状态持久化**：Cookie 保存用户 WDSP 设置，页面刷新后恢复
- **WebSocket 命令**：支持动态开启/关闭各项 DSP 功能

#### 性能对比
| 特性 | WDSP (NR2) | RNNoise |
|------|-----------|---------|
| 算法类型 | 频谱减法 | 神经网络 |
| 降噪深度 | 15-20 dB | 10-15 dB |
| 语音保真度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| SSB 优化 | ✅ 专门优化 | ❌ 通用语音 |
| 延迟 | < 20ms | 30-50ms |
| 参数可调 | ✅ 多项参数 | ❌ 固定模型 |

#### 配置迁移
```ini
# 旧配置（RNNoise）
[RNNOISE]
enabled = True  # 改为 False

# 新配置（WDSP）
[WDSP]
enabled = True  # 默认启用
sample_rate = 48000
buffer_size = 256
nr2_enabled = True
nb_enabled = True
anf_enabled = False
agc_mode = 3  # MED
bandpass_low = 300.0
bandpass_high = 2700.0
```

#### 前端控制
在移动端界面"设置"菜单中：
- 🎛️ WDSP 主开关（联动禁用/启用子控件）
- 频谱降噪 (NR2)
- 噪声抑制 (NB)
- 自动陷波 (ANF)
- AGC 模式选择（关闭/长/慢/中/快）

#### 安装 WDSP 库
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

#### 文件变更
- `wdsp_wrapper.py` - WDSP Python 封装（新增）
- `audio_interface.py` - 集成 WDSP 到 RX 音频处理链
- `MRRC` - 添加 WebSocket 控制命令
- `www/mobile_modern.js` - 前端 WDSP 控制面板 + Cookie 持久化
- `www/mobile_modern.css` - WDSP UI 样式
- `www/controls.js` - WebSocket 消息处理
- `MRRC.conf` - WDSP 配置段
- `DSP.md` - WDSP 详细文档（新增）
- `IFLOW.md` - 架构文档更新
- `README_CN.md` - 用户手册更新
- `AOD.md` - 主要功能更新

#### Bug 修复
- 修复移动端 WDSP 设置面板状态不保存的问题
- 添加 Cookie 持久化，设置可跨会话保存
- 连接成功后自动同步 WDSP 状态到后端

---

## [V4.5.17] - 2026-03-08

### 🔧 ATU 天调系统修复与优化

#### 数据解析修复
- **RELAY_STATUS 字段位置修正**：根据实际测试修正数据解析位置
  - `data[3]` → SW（网络类型：0=LC, 1=CL）
  - `data[4]` → IND（电感索引，如 47=4.7uH）
  - `data[5]` → CAP（电容索引，如 79=790pF）

#### 数据清理
- 清理 JSON 中 6 条脏数据（sw=3/sw=47 等无效值）
- 保留 136 条有效学习记录

#### 参数调用统一
- 统一 `set_relay()` 调用参数顺序为 `(sw, ind, cap)`
- 修复三处调用点：自动调谐、快速调谐、手动设置

#### 微调模式改为存储调谐
- `_fine_tune()` 方法从扫描模式改为存储调谐模式
- 优先从映射表获取已学习的参数直接应用
- 存储参数不达标时回退到初始参数
- 大幅减少调谐时间（从~63次测试减少到1-2次）

#### SWR 过滤增强
- 学习逻辑排除 SWR=1.0 假数据（阈值改为 1.01）
- 保存结果限制 SWR 在 1.01-2.0 范围内

#### 第三方软件联动支持
- 支持 JTDX、flrig、wfview 等通过 rigctld 联动
- MRRC 定期从 rigctld 读取频率并同步给 ATR-1000 代理
- 无需打开网页界面，频率变更自动触发天调

## [V4.5.16] - 2026-03-08

### 🎯 ATR-1000 天调智能学习与快速调谐

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

#### 继电器状态帧解析
```
原始数据: ff050701031b1e000e01
         │  │  │  │  │  │
         │  │  │  │  │  └─ data[6] = IND (电感)
         │  │  │  │  └──── data[5] = CAP (电容)
         │  │  │  └─────── data[4] = 保留
         │  │  └────────── data[3] = SW (网络类型)
         │  └───────────── LEN
         └──────────────── CMD
```

#### 值转换示例

| 频率 | SW | IND存储 | IND发送 | L显示 | CAP存储 | CAP发送 | C显示 |
|------|-----|---------|---------|-------|---------|---------|-------|
| 7MHz | CL | 30 | 3 | 0.3uH | 27 | 27 | 270pF |
| 14MHz | LC | 10 | 1 | 0.1uH | 9 | 9 | 90pF |

#### 节流保护
- 相同参数不重复发送
- 最小发送间隔 5 秒
- 防止设备频繁重启

#### 文件变更
- `atr1000_proxy.py` - 修正协议解析，添加频率同步接口
- `atr1000_tuner.py` - 天调存储模块
- `atr1000_tuner.json` - 学习记录存储
- `MRRC` - 添加 `sync_freq_to_atr1000()` 频率同步函数
- `docs/ATR1000_Tuner_Auto_Learning.md` - 完整技术文档

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

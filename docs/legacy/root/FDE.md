# MRRC 项目 FDE 模式复盘与提炼

> Forward Deployed Engineering — 以 Palantir FDE 方法论重新审视 MRRC 项目演进
> 综合来源: 208 commits, CHANGELOG, SDD (14章), DESIGN (6文档), AOD, DSP, 26+ 技术文档
> 覆盖周期: 2024-10 ~ 2026-05, V1.0.0 → V5.2.0

---

## 一、什么是 FDE？

**FDE (Forward Deployed Engineering)** 源自 Palantir，是一种**驻场工程师驱动的产品探索与交付模式**。核心理念：

| 维度 | 传统 SaaS (PMF) | FDE 模式 |
|------|----------------|---------|
| 交付物 | 标准化软件许可证 | 可衡量的**成果 (Outcome)** |
| 团队位置 | 总部远程 | **驻扎客户现场** |
| 工作方式 | 产品→销售→客户 | 工程师直接对接→构建→抽象 |
| 扩展逻辑 | 减少每个客户定制工作量 | 提高**交付成果的价值** |
| 合同规模 | 可重复的小额合同 | 随价值递增的大额合同 |
| 产品团队角色 | 直接做功能 | 把现场"碎石路"抽象为"高速公路" |

**核心公式：**

```
FDE = Echo(需求发现) + Delta(原型交付) + Product(抽象泛化)
```

- **Echo 团队**：嵌入式分析师，深入用户场景，定义有价值的 demo/use case，同时是客户关系管理者
- **Delta 团队**：部署工程师，擅长快速原型，在时间线内以软件形式交付成果（代码粗糙但能跑）
- **Product 团队**：总部产品/工程，把现场做法抽象为可服务接下来 5-10 个客户的通用能力

**FDE 不是咨询**：咨询是一次性服务，FDE 是产品探索过程。FDE 在现场铺"碎石路"，总部修"高速公路"。交付成果的单位价值成本随时间下降，利润率从负转正。

---

## 二、MRRC 项目的 FDE 角色映射

在 MRRC 项目中，这三个角色由同一个人（或极小团队）在不同时间段切换承担：

| FDE 角色 | MRRC 对应行为 | 典型时间段 |
|---------|--------------|-----------|
| **Echo (需求发现)** | 分析用户场景（移动端操作、本地通联需求）、识别痛点（延迟大、无功率显示、UI难用）、定义 demo | 每个 FDE Cycle 前期 |
| **Delta (原型交付)** | 快速写代码验证、修复 Bug、构建功能原型（ATR-1000 集成、RagChew 音频链） | 每个 FDE Cycle 中期 |
| **Product (抽象泛化)** | 将现场方案抽象为通用模块（WDSP 封装、音频接口抽象、多实例架构）、更新文档体系 | 每个 FDE Cycle 后期 |

---

## 三、FDE Cycle 全景

```
2024-10      2024-11       2024-12        2025-01         2026-03        2026-04       2026-05
  ┃            ┃             ┃              ┃               ┃              ┃             ┃
  ▼            ▼             ▼              ▼               ▼              ▼             ▼
┌────────┐ ┌────────┐  ┌────────┐  ┌────────────┐  ┌────────────┐  ┌────────┐  ┌──────────┐
│ Cycle1 │ │ Cycle2 │  │ Cycle3 │  │ Gap Period │  │ Cycle 4-7  │  │Cycle 8 │  │ Cycle 9  │
│ 奠基   │ │ 架构   │  │ 移动端 │  │ (运营维护)  │  │ 爆发式增长  │  │UI现代化 │  │ 音频精化  │
│ V1.0   │ │ V2.0   │  │ V3.0   │  │ V3.0-V3.2  │  │ V4.0-V4.9  │  │ V5.0   │  │ V5.1     │  │ V5.2     │
│ ~4周   │ │ ~4周   │  │ ~4周   │  │ ~14个月    │  │ ~6周       │  │ ~4周   │  │ ~1.5周   │  │ ~1周     │
└────────┘ └────────┘  └────────┘  └────────────┘  └────────────┘  └────────┘  └──────────┘  └──────────┘
                                                      分拆为:
                                                    ┌──────────┐  ┌──────────┐  ┌──────────┐
                                                    │ Cycle 4  │  │ Cycle 5  │  │ Cycle 6  │
                                                    │ 延迟优化  │  │ATR-1000  │  │ 功能扩展  │
                                                    │ V4.0     │  │ V4.3-V4.5│  │ V4.6-V4.9│
                                                    │ ~1周     │  │ ~3周     │  │ ~2周     │
                                                    └──────────┘  └──────────┘  └──────────┘
                                                    ┌──────────┐
                                                    │ Cycle 7  │
                                                    │ 部署自动化│
                                                    │ V5.1.x   │
                                                    │ ~1周     │
                                                    └──────────┘
```

**关键观察**：从 V4.0 开始进入爆发式创新期（2026-03 ~ 2026-05），12 周内完成 6 个次版本迭代，平均每 2 周一个版本。之前的 V3.x 维持了约 14 个月的稳定运营期。

---

## 四、各 FDE Cycle 详细复盘

### Cycle 1: 奠基 (2024-10)

**Outcome**: 从 F4HTB/Universal_HamRadio_Remote_HTML5 项目 fork，搭建基础远程电台控制框架

| FDE 阶段 | 活动 | 产出 |
|---------|------|------|
| **Echo** | 评估上游项目架构，识别基础功能需求：WebSocket 通信、音频流传输、hamlib 集成 | 项目初始化决策 |
| **Delta** | Fork 上游代码，建立基本的 Tornado WebSocket 服务器，搭建音频传输管道 | `MRRC` (初版), `audio_interface.py`, `hamlib_wrapper.py` |
| **Product** | 选择技术栈：Tornado + WebSocket + PyAudio + Hamlib | AD-001 (WebSocket), AD-002 (Tornado), AD-003 (Int16) |

**技术选型决策**：

| 决策 | 方案 | 备选 | 理由 |
|------|------|------|------|
| 通信协议 | WebSocket | HTTP轮询、SSE、WebRTC | 全双工低延迟，浏览器原生支持 |
| Web框架 | Tornado | Flask-SocketIO, FastAPI, aiohttp | 原生WebSocket，异步I/O |
| 音频编码 | Int16 | Float32, Opus, AAC | 带宽减半，解码简单 |

**版本产出**: V1.0.0 (2024-10-01) — 基于 GPL-3.0 协议

---

### Cycle 2: 架构重构 (2024-11)

**Outcome**: 从上游代码走向独立架构 — AudioWorklet 低延迟播放、PyAudio 跨平台、TLS 安全、用户认证

| FDE 阶段 | 活动 | 产出 |
|---------|------|------|
| **Echo** | 发现 ALSA 仅限 Linux，macOS/Windows 无法运行；ScriptProcessor 主线程阻塞导致高延迟；无安全传输 | 跨平台需求、低延迟需求、安全需求 |
| **Delta** | 用 PyAudio 替代 ALSA 实现跨平台音频 I/O；引入 AudioWorklet 替代 ScriptProcessor；Int16 编码优化 50% 带宽；TLS 加密 | `audio_interface.py` 重写, `rx_worklet_processor.js` |
| **Product** | 跨平台音频抽象层、环形缓冲区架构、用户认证系统 (SQLite)、TLS 证书体系 | `audio_interface.py` 统一接口, `MRRC_users.db` |

**碎石路 → 高速公路**：

```
碎石路: ALSA + Linux 独占 + ScriptProcessor 主线程阻塞
    ↓ 抽象
高速公路: PyAudio 跨平台统一接口 + AudioWorklet 音频线程低延迟播放
```

**关键架构转折**：这是项目最重要的架构决策之一 — 从上游 Linux-only 走向跨平台。AudioWorklet 的引入使 RX 播放延迟从 50ms 降至 5ms 以内。

**版本产出**: V2.0.0 (2024-11-15)

---

### Cycle 3: 移动端优化 (2024-12 ~ 2025-01)

**Outcome**: 移动端专属界面、iPhone 兼容、音频编码扩展

| FDE 阶段 | 活动 | 产出 |
|---------|------|------|
| **Echo** | 桌面界面在手机上无法操作；iPhone Safari 音频兼容性问题；编码格式单一 | 移动端需求、兼容性需求 |
| **Delta** | 移动端独立 HTML 界面 `mobile_modern.html`；AAC/ADPCM 编码支持；iOS Safari AudioContext suspend 修复 | `www/mobile_modern.html`, `www/mobile_modern.css`, `www/mobile_modern.js` |
| **Product** | PWA 支持 (manifest.json + service worker)；TCI 协议支持；NanoVNA 集成 | 移动端架构框架 |

**版本产出**: V3.0.0 (2024-12-20) → V3.1.0 (2025-01-10) → V3.2.0 (2025-01-15)

---

### Gap Period: 运营维护期 (2025-01 ~ 2026-02)

**约 14 个月**。

这段时间 git 历史中没有活跃开发提交，项目处于稳定运营状态。实际电台 `radio.vlsc.net:8877` 持续运行，用户通过现有功能进行日常通联。

这符合 FDE 模式的特征：**现场运行本身就是需求发现的过程**。长时间的运行暴露了深层次问题：

| 积累的痛点 | 影响 | 触发后续 Cycle |
|-----------|------|---------------|
| TX→RX 切换 2-3 秒延迟 | 通联流畅度差 | Cycle 4 (延迟优化) |
| 无功率/SWR 显示 | 无法判断天调效率 | Cycle 5 (ATR-1000) |
| 背景噪声大，无降噪 | SSB 语音疲劳 | Cycle 6 (WDSP) |
| 无 TX 音质调整 | 发射声音刺耳 | Cycle 6 (TX EQ) |
| UI 陈旧 | 使用意愿低 | Cycle 8 (UI现代化) |
| 部署操作繁琐 | 维护成本高 | Cycle 7 (Ansible) |

**FDE 洞察**：运营维护期不是"空白期"，而是**最长的 Echo 阶段**。真正的用户痛点需要长时间运行才能暴露。

---

### Cycle 4: 延迟优化 — V4.0 (2026-03-01)

**Outcome**: TX→RX 切换延迟从 2-3 秒降至 <100ms，PTT 可靠性达 99%+

| FDE 阶段 | 活动 | 产出 |
|---------|------|------|
| **Echo** | 发现 TX→RX 切换 2-3s 延迟是用户最大痛点；PTT 按下不响应问题；无功率显示 | `docs/PTT_Audio_Postmortem_and_Best_Practices.md` |
| **Delta** | AudioWorklet 优化、PTT 预热帧机制、计数超时保护、TUNE 按钮长按单音发射 | `www/rx_worklet_processor.js`, `www/tx_button_optimized.js` |
| **Product** | 环形缓冲区架构、区间缓冲策略、端到端延迟 <100ms 架构、V4.0 里程碑文档 | `docs/latency_optimization_guide.md`, `docs/Comprehensive_Architecture_Analysis.md`, `docs/End_to_End_Analysis_Report.md` |

**性能指标**：

| 指标 | V3.x | V4.0 | 提升 |
|------|------|------|------|
| TX 延迟 | ~100ms | ~65ms | 35% |
| RX 延迟 | ~100ms | ~51ms | 49% |
| TX→RX 切换 | 2-3s | <100ms | 95%+ |
| PTT 可靠性 | 95% | 99%+ | — |

**命名变更**：此版本正式从 "UHRR (Universal HamRadio Remote)" 更名为 **"MRRC (Mobile Remote Radio Control)"**，确立 Mobile First 产品定位。

**碎石路 → 高速公路**：

```
碎石路: 每次 PTT 按下都等待电台响应，导致 2-3s 延迟
    ↓ 抽象
高速公路: 预热帧 + 计数超时机制 → 通用 PTT 可靠性框架

碎石路: ScriptProcessor 主线程阻塞导致播放延迟
    ↓ 抽象
高速公路: AudioWorklet 音频线程 → 通用低延迟播放架构
```

**Demo 驱动开发**：向用户演示"按下 PTT 立即发射，松开立即接收"的流畅体验，创造了强烈的用户渴望。

**版本产出**: V4.0.0 (2026-03-01) → V4.1.0 (项目更名 MRRC) → V4.2.0 (TX均衡器)

---

### Cycle 5: ATR-1000 天调集成 — V4.3 ~ V4.5 (2026-03-04 ~ 2026-03-08)

**Outcome**: 实时功率/SWR 显示 + 智能学习 + 快速调谐 + REST API — 这是项目中最典型的 FDE 抽象过程

| FDE 阶段 | 活动 | 产出 |
|---------|------|------|
| **Echo** | 用户需要实时功率/SWR 显示；频繁发现设备假死问题；快速调谐需求；PTT 发射时功率数据不更新 | `docs/ATR1000_Display_Issue_Analysis.md`, `docs/ATR1000_PTT_Delay_Troubleshooting_Journey.md` |
| **Delta** | 5 次迭代修复功率显示问题、独立代理进程、智能学习 JSON 存储、协议逆向工程修正 | `atr1000_proxy.py`, `atr1000_tuner.py`, 14+ commits |
| **Product** | 独立代理架构 (AD-008)、动态轮询 15s/5s/0.5s 三态、REST API Server、频率-参数智能学习 | `atr1000_api_server.py`, `docs/ATR1000_Tuner_Auto_Learning.md` |

**最典型的 FDE 抽象过程**（5 次迭代逐步抽象）：

```
第1次 (V4.3.0): ATR-1000 集成在主进程 → 设备假死，TX→RX 切换延迟 2s
    ↓ 现场调试
第2次 (V4.3.1~V4.3.8): 直接连接 + SYNC 机制 → 更新太慢，日志过多压垮 CPU
    ↓ 用户反馈："数据一直在转，但数值不更新"
第3次 (V4.4.0~V4.4.9): 加快 SYNC 间隔到 300ms，50ms 批量广播 → 设备压力过大
    ↓ 问题定位：设备因频繁请求挂起
第4次 (V4.5.0~V4.5.11): 动态轮询 + 节流保护 + 双重时间保护 + 连接预热 → 终于稳定
    ↓ 抽象为通用模式
高速公路 (V4.5.12~V4.5.18):
  • 独立代理进程 (Unix Socket 隔离)
  • 动态轮询策略 (idle/active/tx 三态: 15s/5s/0.5s)
  • 频率-参数智能学习 (JSON 持久化, ±50kHz 容差)
  • REST API Server (:8080 端口)
  • 第三方软件联动 (JTDX/flrig/wfview 频率自动同步)
```

**协议逆向工程**：通过实际测试修正了 ATR-1000 协议解析：

| 项目 | 修正前 (手册) | 修正后 (实测) |
|------|--------------|--------------|
| SW 字段位置 | data[4] | data[3] |
| SW 映射 | 0=CL, 1=LC | 0=LC, 1=CL |
| IND 发送值 | 直接发送 | 原值÷10 |
| CAP 发送值 | 原值×10 | 直接发送 |

**Land & Expand 模式**：
```
Land: 解决第一个问题 — 功率/SWR 实时显示
  ↓ 在现场发现更多问题
Expand: 智能学习 → 快速调谐 → REST API → 外部软件集成 → 第三方频率联动
```

**版本产出**: V4.3.0 → V4.5.18 (15+ 次版本的密集迭代)

---

### Cycle 6: 数字信号处理与功能扩展 — V4.6 ~ V4.9 (2026-03-09 ~ 2026-03-16)

**Outcome**: WDSP 专业降噪、TX 三段均衡器、语音助手、CW 解码、多实例、FT8/ULTRON

**子 Cycle 6a: WDSP 集成 (V4.6.0 ~ V4.6.1)**

| FDE 阶段 | 活动 | 产出 |
|---------|------|------|
| **Echo** | 用户反馈"背景噪声大，听 SSB 很累"；RNNoise 降噪效果一般（10-15dB） | 降噪需求分析 |
| **Delta** | 集成 WDSP 库 (OpenHPSDR)、NR2 频谱降噪、NB/ANF/AGC、修复初始化 BUG (16 倍放大) | `wdsp_wrapper.py`, `audio_interface.py` WDSP 集成 |
| **Product** | 48kHz WDSP 处理 → 16kHz Opus 编码架构、wdsp_wrapper.py Python 封装、DSP.md 文档 | `DSP.md`, `docs/WDSP_Manual.md` |

**WDSP vs RNNoise 对比**：

| 特性 | WDSP (NR2) | RNNoise |
|------|-----------|---------|
| 算法类型 | 频谱减法 (Spectral) | 神经网络 |
| 降噪深度 | 15-20 dB | 10-15 dB |
| 语音保真度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| SSB 语音优化 | ✅ 专门优化 | ❌ 通用 |
| 延迟 | < 20ms | 30-50ms |
| 参数可调 | ✅ 多项参数 | ❌ 固定模型 |

**Demo 驱动开发**：向用户演示"嘈杂环境中开启 NR2，SSB 语音听起来像 FM"的效果。

**子 Cycle 6b: RX 音频重构 (V4.7.0 ~ V4.8.0)**

- WDSP 库路径自动检测（系统 → Homebrew → 项目目录）
- 多格式解码 (Int16/Float32 自适应)
- S 表精细化（S5-S55 中间刻度）
- 音频录制功能 (WAV/MP3 导出)
- 软削波 (tanh 函数, 阈值 0.95)
- 立体声录制优化 (右声道)
- 远程服务管理 (SSH start/stop/status)

**子 Cycle 6c: 扩展功能矩阵 (V4.9.0)**

| 功能 | 技术实现 | 新增文件 |
|------|---------|---------|
| **语音助手** | Whisper ASR + Qwen3-TTS 本地部署 | `voice_assistant_service.py`, `mobile_voice_*.html` |
| **CW 解码** | ONNX Runtime 前端推理 + QSO 状态机 | `cw_live.html`, `cw_dsp.html`, `cw_generator.html` |
| **SDR 界面** | 现代化频谱显示控制 | `sdr_modern.html`, `sdr_modern.js`, `sdr_modern.css` |
| **多实例** | 独立配置/端口/Socket 隔离 | `MRRC.radio1.conf`, `mrrc_multi.sh` |
| **FT8/ULTRON** | Python 重写 PHP 版 + DXCC 智能白名单 | `ft8/ultron.py`, `ft8/ultron_dxcc.py`, `ft8/dxcc_*.py` |

**子 Cycle 6d: UI 改版 (V4.9.2)**

- 蓝色系专业风格 UI（青色 #00d4ff 主色调）
- CSS 变量系统化重构
- SDR 风格蓝色数码管频率显示
- 全屏模式 (iOS Safari + Android Chrome 兼容)
- WDSP 高级设置面板 (NR2 级别选择)
- 频率步进默认 1kHz
- Vibration API 震动反馈
- S 表独立分析器

**子 Cycle 6e: 多实例与语言体系 (V4.9.1 ~ V4.9.3)**

- 多实例深度优化：配置键大小写修复、Socket 路径修复
- 频率同步线程：`FrequencySyncThread` 独立线程，2 秒检测频率联动
- JTDX/flrig/wfview 第三方软件频率联动修复
- **完整英文文档体系**：9 个核心文档的完整翻译
- **中文版界面**：`index_zh.html`, `mobile_modern_zh.html`
- 综合配置指南 `INSTALLATION.md`

**碎石路 → 高速公路** (本 Cycle)：

```
碎石路: 直接调用 libwdsp.dylib C 接口
    ↓ 抽象
高速公路: wdsp_wrapper.py — Python 封装，统一 NR2/NB/ANF/AGC 接口

碎石路: 为 radio1 写专用配置
    ↓ 抽象
高速公路: 多实例架构 — 每个实例独立配置、独立端口、独立天调

碎石路: JTDX/flrig 各自独立，无频率联动
    ↓ 抽象
高速公路: FrequencySyncThread — 独立线程统一监控，所有第三方软件自动联动

碎石路: ULTRON PHP 版 (单平台)
    ↓ 抽象
高速公路: ULTRON Python 版 + DXCC 智能白名单 + 跨平台
```

**版本产出**: V4.6.0 → V4.9.3 (8 个次版本，密集迭代)

---

### Cycle 7: 部署自动化 — V5.1.x (2026-04 ~ 2026-05)

**Outcome**: 从手动 SSH 部署升级为 Ansible 自动化 — 可重复、幂等、配置驱动

| FDE 阶段 | 活动 | 产出 |
|---------|------|------|
| **Echo** | 每次部署需手动 SSH + SCP (7 步操作)；确认步骤多；无回滚机制；多服务器扩展困难 | 操作痛点分析 |
| **Delta** | `deploy.sh` 快速部署脚本（tar + scp + ssh + apache reload），单次部署可用 | `website/deploy.sh` |
| **Product** | Ansible playbook：inventory 管理、synchronize 增量同步、ownership/permissions 自动修复、部署后 stat 验证 | `ansible/deploy_website.yml`, `ansible/inventory`, `ansible/ansible.cfg` |

**碎石路 → 高速公路**：

```
碎石路 (deploy.sh): tar打包 → scp上传 → ssh远程解压 → 手动确认 → 无回滚
    ↓ 抽象
高速公路 (Ansible):
  • inventory 声明式主机管理
  • synchronize 模块 rsync 增量同步 + --delete 清理
  • 幂等操作：目录存在检查、权限自动修复
  • 部署验证：stat index.html 自动检查
  • 时间戳备份: mrrc_20260510_120000

碎石路: 证书手动 scp 到服务器，无备份
    ↓ 抽象
高速公路: certs/backup/ 自动时间戳备份
```

**关键指标**：
- 部署操作从 7 步减少到 1 步 (`ansible-playbook deploy_website.yml`)
- Inventory 驱动 → 一行配置即可部署到新服务器

**版本产出**: V5.1.x (ansible/ + website/ 基础设施)

---

### Cycle 8: UI 现代化 — V5.0 (2026-04-30)

**Outcome**: 移动端 UI 全面现代化 — 玻璃拟态、Unicode 图标、触摸优化、CSS 瘦身 15%

| FDE 阶段 | 活动 | 产出 |
|---------|------|------|
| **Echo** | 移动端 UI 陈旧（V3.0 时代遗留）；Emoji 图标跨平台不一致；按钮触控热区仅 ~20px；CSS 冗余 324 行 | `docs/iphone15_mobile_interface_analysis.md` |
| **Delta** | 玻璃拟态 CSS 重写、Unicode 图标替换、单行调谐布局、Vibration API、TX 频率红色呼吸光效 | `www/mobile_modern.css`, `www/mobile_modern.html` |
| **Product** | CSS 瘦身 15%、触摸热区标准化 44px (WCAG)、设计系统文档、截图文档更新 | `docs/mobile_modern_interface.md`, `screenshots/main.png` |

**玻璃拟态设计系统**：

```
┌──────────────────────────────────────────────┐
│            Glassmorphism Design               │
├──────────────────────────────────────────────┤
│  background: rgba(20, 30, 50, 0.65)          │
│  backdrop-filter: blur(12px)                 │
│  border: 1px solid rgba(255, 255, 255, 0.1)  │
│  border-radius: 16px                         │
│  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3)  │
└──────────────────────────────────────────────┘
```

**Unicode 图标系统**（解决跨平台一致性）：

| 功能 | 旧方案 (Emoji) | 新方案 (Unicode) |
|------|---------------|-----------------|
| 电源 | 🔴 | `&#x23FB;` |
| 音量 | 🔊 | `&#x1F50A;` |
| 录音 | 🔴 | `&#x25CF;` |
| NR2 | — | 波形 SVG |
| NB | — | 闪电 SVG |
| 设置 | ⚙️ | `&#x2699;` |

**ATR-1000 同时期增强**：
- 天调防断连优化（自动重连 + 心跳保活）
- Opus HPF 高通滤波器支持
- 频谱分析工具集成
- TX Audio Boost 发射音频增强

**版本产出**: V5.0.0 (2026-04-30)

---

### Cycle 9: 音频精化 — V5.1.0 RagChew (2026-05-10)

**Outcome**: RagChew TX 语音美化 + Safari 兼容性修复 + ATR-1000 PTT 功率显示增强 + SDD 体系完成

| FDE 阶段 | 活动 | 产出 |
|---------|------|------|
| **Echo** | 本地强信号通联需要"温暖自然"的人声；移动端 Safari TypeError 导致音频链初始化失败；PTT 发射时功率/SWR 更新延迟 | 用户反馈 + ATR-1000 PTT 调试历程 |
| **Delta** | Web Audio API 全链路处理（EQ + Compressor + NoiseGate）、Safari setValueAtTime 第二参数修复、PTT 发射时 ATR-1000 主动轮询加速 | `www/controls.js` (V5.1.0), `atr1000_proxy.py` (PTT 轮询优化) |
| **Product** | RagChew 音频链抽象为通用 TX 预设系统、WebAudio_Skill.md 技能文档、ATR-1000 0.5s 动态轮询标准、SDD V2.1 更新 | `docs/WebAudio_Skill.md`, 12 个 .md 更新, SDD/ 全面更新 |

**RagChew 音频链**：

```
micSource → preGain → antiAlias(6kHz LPF) → antiAlias2
  → eqLow(HPF 150Hz) → eqMid → eqHigh
  → midCut(500Hz -2dB) → presence(2.4kHz +3dB) → highCut(LPF 3.0kHz)
  → compressor(3:1 ratio, -24dB threshold, 3ms attack, 250ms release)
  → noiseGate(-50dB RMS, 300ms release)
  → gain_node → AudioProcessor(encoder)
```

| 模块 | Web Audio API 实现 | 作用 |
|------|-------------------|------|
| EQ 均衡器 | BiquadFilterNode 级联（highpass + lowshelf + peaking + highshelf + lowpass） | 低切 150Hz 去噪，500Hz 减浊音，2.4kHz 增强清晰度 |
| 动态压缩器 | DynamicsCompressorNode (ratio 3:1, threshold -24dB) | 说话时自动稳幅，避免音量忽大忽小 |
| 噪声门 | ScriptProcessorNode RMS 检测 + GainNode 条件控制 | 不说话时完全静音，释放 300ms 避免断字 |

**Safari 兼容修复** — V5.1.0 关键 Bug 修复：
```
Safari 是唯一强制要求 setValueAtTime 传第二参数 (currentTime) 的浏览器
Chrome/Firefox 默认可省略 → Safari 报 "TypeError: not enough arguments"
修复：统一 audioParam.setValueAtTime(value, audioContext.currentTime)
影响：所有 BiquadFilterNode.Q.setValueAtTime() 调用
```

**SDD 文档体系完成** (V2.1)：
- 14 章完整 IBM TeamSD 方法论文档
- 覆盖 V1.0 → V5.2.0 全部版本
- 系统上下文、用例模型、架构决策、服务模型、组件模型完整

**版本产出**: V5.1.0 (RagChew + Safari fix + ATR-1000 PTT + stereo recording + TX boost + SDD V2.1)

### Cycle 10: 性能调优 — V5.2.0 (2026-05-18)

| 要素 | 内容 |
|------|------|
| **Echo** | RX 音频帧间间隙导致 pops/clicks；WDSP 每帧 100+ 行属性检查造成 CPU 开销 |
| **Delta** | 多 BufferSourceNode 精确时间对齐调度、WDSP 参数哈希缓存机制、Opus 帧对齐 (960 samples@48kHz) |
| **Product** | `www/audio_rx.js` (播放引擎重写), `audio_interface.py` (WDSP 哈希缓存 + Opus 帧对齐), `mrrc_multi.sh` (Python 路径固定) |

**RX 播放引擎重写** — V5.2.0 核心改进：
- 单节点复用 → 多 BufferSourceNode 调度：每个 Opus 解码帧独立创建 source node
- `_rx_nextStartTime` 精确时间对齐，消除帧间间隙
- 非递归调度 + `onended` 链式触发，限制并发调度数 (`_rx_maxScheduled=3`)
- 队列深度 10→20，解码失败时丢弃帧而非断裂时间线

**WDSP 性能优化**：
- 7 个关键参数哈希对比替代每帧属性检查，仅变更时重建处理器
- `frames_per_buffer` 256→960，对齐 Opus 帧 (20ms@48kHz → 320samples@16kHz)

**版本产出**: V5.2.0 (WDSP 哈希缓存 + RX 多节点调度播放引擎 + Opus 帧对齐 + SDD V2.2)

---

## 五、FDE 核心模式在 MRRC 中的体现

### 5.1 "碎石路 → 高速公路" 抽象总结

| 碎石路 (现场方案) | 高速公路 (抽象产物) | 服务客户数 |
|------------------|-------------------|-----------|
| ALSA Linux 独占 | `audio_interface.py` PyAudio 跨平台抽象 | 3 (macOS/Linux/Windows) |
| ScriptProcessor 主线程阻塞 | AudioWorklet 音频线程低延迟架构 | 所有浏览器 |
| 直接 PTT 控制 | 预热帧 + 计数超时通用框架 | 所有电台型号 |
| ATR-1000 直连崩溃 | 独立代理 + 动态轮询 (15s/5s/0.5s) + REST API | 所有 ATR-1000 用户 |
| libwdsp C 调用 | `wdsp_wrapper.py` Python 封装 | 所有 WDSP 用户 |
| 单实例配置 | 多实例架构 (独立配置/端口/Socket) | N 个独立电台 |
| RNNoise 通用降噪 | WDSP NR2 SSB 专用降噪 (15-20dB) | SSB 语音用户 |
| 硬编码音频参数 | TX 预设系统 (DEFAULT/RAGCHEW) | 可扩展 |
| 手动 SSH 部署 | Ansible Playbook 自动化幂等部署 | N 台 Web 服务器 |
| 手动 ULTRON PHP | Python 重构 + DXCC 智能白名单 | 24/7 FT8/FT4 自动化 |
| 单机 JTDX 控制 | Web 界面 + PHP 后端代理 | 远程浏览器访问 |
| 第三方频率各管各 | FrequencySyncThread 统一监控 | 所有第三方软件 (JTDX/flrig/wfview) |

### 5.2 "Land & Expand" 模式总结

| 进入点 (Land) | 扩展发现 (Expand) | 交付价值增长 |
|--------------|------------------|-------------|
| 远程控制电台 | → 功率监测 → 天调学习 → REST API → 第三方联动 | 单次通联 → 完整电台管理 |
| 基础音频传输 | → WDSP 降噪 → TX 均衡 → RagChew 全链路 | 能听清 → 听得舒服 → 说得温暖 |
| 移动端网页 | → PWA → UI 现代化 → 触摸优化 → 玻璃拟态 | 能用 → 好用 → 爱用 |
| 单实例部署 | → 多实例 → 远程管理 → Ansible 自动化 | 一台电台 → N 台电台集群 |

### 5.3 Demo 驱动开发总结

| Demo | 创造的渴望 | 验证的痛点 |
|------|-----------|-----------|
| 按下 PTT 立即发射 | "终于不用等 3 秒了！" | 延迟是通联体验杀手 |
| NR2 降噪开启 | "SSB 听起来像 FM！" | 背景噪声影响专注度 |
| 功率/SWR 实时显示 | "一眼就知道天调好不好" | 盲目发射效率低 |
| 玻璃拟态 UI | "比原生 App 还好看" | UI 陈旧影响使用意愿 |
| RagChew 语音 | "声音温暖有温度" | 默认预设太刺耳 |

### 5.4 产品杠杆演进

```
V1.0: 产品杠杆 = 0 (直接从 F4HTB fork，基础框架)
V2.0: 产品杠杆 = 1 (AudioWorklet 低延迟 + PyAudio 跨平台 + TLS 安全)
V3.0: 产品杠杆 = 2 (移动端独立界面 + PWA + 多编码支持)
V4.0: 产品杠杆 = 3 (PTT 预热帧 + <100ms 切换 + 端到端延迟优化架构)
V4.3: 产品杠杆 = 4 (ATR-1000 独立代理 + 动态轮询 + 智能学习)
V4.6: 产品杠杆 = 5 (WDSP 封装 + NR2 降噪 + TX 均衡器)
V4.8: 产品杠杆 = 6 (多实例架构 + 音频录制 + 远程管理)
V4.9: 产品杠杆 = 7 (语音助手 + CW 解码 + SDR + FT8/ULTRON + FrequencySyncThread)
V5.0: 产品杠杆 = 8 (统一设计系统 + 玻璃拟态 + Unicode 图标 + Opus HPF)
V5.1: 产品杠杆 = 9 (TX 预设系统 + RagChew + Ansible 部署自动化 + SDD 文档体系)

衡量标准: 同样的成果，后续部署所需代码量是否减少？
答案: 是。每个 Cycle 后，新增功能的边际开发成本递减。
```

---

## 六、FDE 模式下的关键教训

### 6.1 做对的

1. **从现场出发，不是从产品出发**：每个 Cycle 都由用户场景/问题驱动，而非"我要加这个功能"
2. **Demo 驱动验证**：每次交付都通过实际演示验证用户渴望，而非纸上规划。V4.0 PTT 演示、V4.6 NR2 演示、V5.1 RagChew 演示
3. **及时抽象**：每次 Cycle 后期都有 Product 角色介入，将现场方案抽象为通用模块
4. **文档即产出**：26+ 技术文档、14 章 SDD、4 个 DESIGN 文件、6 个设计文档，确保知识可传承
5. **跨平台从一开始**：V2.0 就用 PyAudio 替代 ALSA，避免了 Linux 锁定
6. **运营期也是 Echo 期**：14 个月的"静默期"积累了大量真实的用户痛点，为后续爆发式创新奠定基础

### 6.2 可改进的

1. **抽象时机偏晚**：ATR-1000 经历了 5 次迭代才完成抽象（4.3→4.5），可以在第 2 次就引入 Product 视角
2. **Echo 与 Delta 角色切换成本高**：同一人在需求发现和编码交付间切换，存在上下文切换损耗
3. **合同规模思维缺失**：MRRC 是个人项目，未引入"成果定价"和"合同递增"的 FDE 商业逻辑
4. **Gap Period 过度**：14 个月无代码变更意味着现场问题未及时修复，部分小问题积累成大问题
5. **版本号跳跃大**：从 V3.2 (2025-01) 直接跳到 V4.0 (2026-03)，中间 14 个月的维护版本未记录

### 6.3 FDE 成功要素对照表

| Palantir FDE 要素 | MRRC 体现程度 | 说明 |
|------------------|-------------|------|
| 驻场需求发现 (Echo) | ★★★☆☆ | 自我需求分析（非第三方驻场），但运营期 14 个月提供了独特洞察 |
| 快速原型交付 (Delta) | ★★★★★ | 快速编码验证，代码质量让位于速度（ATR-1000 5 次迭代即稳定） |
| 抽象泛化 (Product) | ★★★★☆ | 有抽象意识但有时偏晚；wdsp_wrapper.py 是优秀的抽象案例 |
| Demo 驱动开发 | ★★★★★ | 每次交付都验证用户体验（PTT、NR2、RagChew 三次关键演示） |
| Land & Expand | ★★★★☆ | 自然发生非刻意规划（ATR-1000 功率显示→智能学习→REST API） |
| 成果定价 | ☆☆☆☆☆ | 个人项目，未引入商业逻辑 |
| 文档体系 | ★★★★★ | 26+ 技术文档 + 14 章 SDD + 6 设计文档，知识传承完整 |
| 产品杠杆递增 | ★★★★★ | 每个 Cycle 后边际成本递减，V1→V5.1 杠杆从 0 增至 9 |

---

## 七、FDE 视角下的项目全景图

```
┌──────────────────────────────────────────────────────────────────────┐
│                    MRRC FDE Journey (2024-10 ~ 2026-05)              │
│                                                                      │
│  问题域 (Problem Space)          方案域 (Solution Space)              │
│  ──────────────────────          ───────────────────────              │
│                                                                      │
│  P0: 无远程电台控制    ───►  S1: WebSocket + Tornado + HTML5(V1.0)  │
│  P1: Linux 独占       ───►  S2: PyAudio 跨平台(V2.0)               │
│  P2: 播放延迟高       ───►  S3: AudioWorklet 音频线程(V2.0)         │
│  P3: 桌面界面手机难用   ───►  S4: mobile_modern.html 移动界面(V3.0) │
│  P4: iPhone 无声      ───►  S5: iOS AudioContext unlock(V3.2)      │
│  P5: TX→RX 延迟 2-3s  ───►  S6: PTT 预热帧 + 计数超时(V4.0)        │
│  P6: 无功率/SWR 显示   ───►  S7: 独立代理 + 动态轮询(V4.3→V4.5)    │
│  P7: 背景噪声大        ───►  S8: WDSP NR2 15-20dB 降噪(V4.6)       │
│  P8: TX 音质刺耳       ───►  S9: TX 均衡器 + RagChew(V4.2→V5.1)    │
│  P9: 多电台管理难      ───►  S10: 多实例架构(V4.9)                  │
│  P10: 无语音控制       ───►  S11: Whisper + Qwen3-TTS(V4.9)        │
│  P11: CW 人工解码      ───►  S12: ONNX 实时解码(V4.9)              │
│  P12: UI 陈旧难用      ───►  S13: 玻璃拟态 + Unicode(V5.0)         │
│  P13: 移动端初始化失败  ───►  S14: Safari setValueAtTime 修复(V5.1) │
│  P14: 部署繁琐          ───►  S15: Ansible 自动化(V5.1.x)           │
│  P15: FT8 手工操作      ───►  S16: ULTRON Python + DXCC(V4.9)      │
│  P16: 文档缺失/过时     ───►  S17: SDD + DESIGN + docs 体系(V5.1)  │
│                                                                      │
│  每个 P→S 都是一个完整的 Echo → Delta → Product 循环                   │
│  每个 S 都成为下一个 P 的产品杠杆                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 八、文档体系全景

### 8.1 DESIGN 层 (产品设计)
| 文件 | 内容 |
|------|------|
| `DESIGN/CONTEXT.md` | 系统上下文图、外部实体、数据流设计、安全性边界 |
| `DESIGN/REQUIREMENTS.md` | 需求矩阵：18 个功能需求、5 类非功能需求、验证状态 |
| `DESIGN/ARCH-DECISIONS.md` | 7 个架构决策记录 (ADR-001 ~ ADR-007) |
| `DESIGN/API.md` | API 接口定义 |
| `DESIGN/SPEC.md` | 产品规格说明 |
| `DESIGN/MRRC_SDD.md` | SDD 概要 |

### 8.2 SDD 层 (系统设计) — IBM TeamSD 方法论
| 章节 | 内容 | 最新版本 |
|------|------|---------|
| 01-executive-summary.md | 执行摘要、核心特性、架构层次 | V2.1 |
| 02-business-direction.md | 业务方向 | V2.1 |
| 03-project-definition.md | 项目范围、成功标准、里程碑 | V2.1 |
| 04-system-context.md | 系统上下文 | V2.1 |
| 05-non-functional-requirements.md | 非功能需求 | V2.1 |
| 06-use-case-model.md | 10 个用例 (UC-001~UC-010) | V2.1 |
| 07-subject-area-model.md | 领域模型 (含 RagChew TX) | V2.1 |
| 08-architecture-decisions.md | 架构决策 (AD-001~AD-007) | V2.1 |
| 09-architecture-overview.md | 架构概览 (企业视图、服务视图) | V2.1 |
| 10-service-model.md | 11 个服务 (核心/支持/扩展) | V2.1 |
| 11-component-model.md | 21 个组件 + 接口定义 + 协作路径 | V2.1 |
| 12-operational-model.md | 运维模型 | V2.1 |
| 13-feasibility-assessment.md | 8 风险 + 6 假设 + 4 问题 + 7 依赖 | V2.1 |
| 14-version-history.md | SDD V1.0 → V2.0 → V2.1 变更追踪 | V2.1 |

### 8.3 docs/ 层 (技术文档)
| 分类 | 文档 |
|------|------|
| **架构** | `System_Architecture_Design.md`, `Comprehensive_Architecture_Analysis.md`, `End_to_End_Analysis_Report.md`, `Component_Detailed_Analysis.md` |
| **延迟优化** | `latency_optimization_guide.md`, `PTT_Audio_Postmortem_and_Best_Practices.md` |
| **ATR-1000** | `ATR1000_Tuner_Auto_Learning.md`, `ATR1000_Display_Issue_Analysis.md`, `ATR1000_PTT_Delay_Troubleshooting_Journey.md`, `ATU_Auto_Tuner_Design.md` |
| **DSP** | `WDSP_Manual.md`, `DSP.md` |
| **移动端** | `mobile_modern_interface.md`, `iphone15_mobile_interface_analysis.md`, `mobile_interface_enhancement_summary.md` |
| **用户手册** | `Mobile_User_Manual.md`, `Mobile_User_Manual_en.md` (含 HTML 版本) |
| **部署** | `Multi_Instance_Setup.md`, `Performance_Optimization_Guide.md` |
| **技能** | `WebAudio_Skill.md`, `CODE_REVIEW_REPORT.md` |
| **翻译** | 9 个核心文档的完整英中双语版本 |

### 8.4 文件索引 (按 FDE Cycle)

#### Cycle 1: 奠基 (V1.0)
`MRRC` (初版), `audio_interface.py` (初版), `hamlib_wrapper.py` (初版), `Dockerfile`

#### Cycle 2: 架构重构 (V2.0)
`audio_interface.py` (PyAudio 重写), `hamlib_wrapper.py` (跨平台),
`rx_worklet_processor.js`, `MRRC_users.db`,
`certs/` (TLS 证书体系), `DESIGN/CONTEXT.md`, `DESIGN/REQUIREMENTS.md`, `DESIGN/ARCH-DECISIONS.md`

#### Cycle 3: 移动端优化 (V3.0)
`www/mobile_modern.html`, `www/mobile_modern.css`, `www/mobile_modern.js`,
`manifest.json`, `service-worker.js`, `DESIGN/API.md`, `DESIGN/SPEC.md`, `DESIGN/MRRC_SDD.md`

#### Cycle 4: 延迟优化 (V4.0)
`www/rx_worklet_processor.js` (优化), `www/tx_button_optimized.js`,
`docs/PTT_Audio_Postmortem_and_Best_Practices.md`, `docs/latency_optimization_guide.md`,
`docs/Comprehensive_Architecture_Analysis.md`, `docs/End_to_End_Analysis_Report.md`,
`README.md`, `README_CN.md`, `README_en.md`, `CHANGELOG.md`

#### Cycle 5: ATR-1000 集成 (V4.3~V4.5)
`atr1000_proxy.py`, `atr1000_api_server.py`, `atr1000_tuner.py`, `atr1000_tuner.json`,
`docs/ATR1000_Tuner_Auto_Learning.md`, `docs/ATR1000_Display_Issue_Analysis.md`,
`docs/ATR1000_PTT_Delay_Troubleshooting_Journey.md`, `docs/ATU_Auto_Tuner_Design.md`,
`atr1000_tuner.py`, `docs/Component_Detailed_Analysis.md`

#### Cycle 6: 功能扩展 (V4.6~V4.9)
`wdsp_wrapper.py`, `DSP.md`, `docs/WDSP_Manual.md`, `docs/WDSP_Manual_en.md`,
`voice_assistant_service.py`, `VOICE_ASSISTANT_SETUP.md`,
`www/mobile_voice_assistant.html`, `www/mobile_voice_text.html`, `www/voice_assistant_asr.js`,
`www/cw_live.html`, `www/cw_dsp.html`, `www/cw_generator.html`, `www/cw_simple.html`, `www/cw_test.html`,
`www/sdr_modern.html`, `www/sdr_modern.js`, `www/sdr_modern.css`,
`www/recordings.html`, `www/index_zh.html`, `www/mobile_modern_zh.html`,
`MRRC.radio1.conf`, `mrrc_multi.sh`, `mrrc_remote_start.sh`,
`docs/Multi_Instance_Setup.md`, `docs/Multi_Instance_Setup_en.md`,
`docs/Mobile_User_Manual.md`, `docs/Mobile_User_Manual_en.md`,
`docs/Performance_Optimization_Guide.md`, `docs/Performance_Optimization_Guide_en.md`,
`INSTALLATION.md`, `AOD.md`, `CLAUDE.md`,
`ft8/ultron.py`, `ft8/ultron_dxcc.py`, `ft8/dxcc_analyzer.py`, `ft8/run_ultron.py`, `ft8/ultron_manager.sh`
`ft8/dxcc_whitelist_*.json` (10 个波段), `ft8/jtdx_web_interface.php`

#### Cycle 7: 部署自动化 (V5.1.x)
`ansible/deploy_website.yml`, `ansible/inventory`, `ansible/ansible.cfg`,
`website/deploy.sh`, `website/` (MRRC 官网), `certs/backup/` (证书备份)

#### Cycle 8: UI 现代化 (V5.0)
`www/mobile_modern.css` (玻璃拟态 + Unicode + 15% 瘦身),
`www/mobile_modern.html` (英文标签 + Unicode 图标),
`www/mobile_modern.js` (震动反馈 + TX 光效联动),
`docs/mobile_modern_interface.md`, `docs/iphone15_mobile_interface_analysis.md`,
`docs/mobile_interface_enhancement_summary.md`,
`screenshots/main.png`, `docs/System_Architecture_Design.md` (V5.0)

#### Cycle 9: 音频精化 (V5.1)
`www/controls.js` (RagChew EQ + compressor + noiseGate 全链),
`www/mobile_modern.js` (RagChew 面板 + Safari 修复),
`www/mobile_modern.html` (版本号更新),
`docs/WebAudio_Skill.md` (技能文档 + RagChew 实战案例),
`SDD/` (14 章全面更新到 V2.1)

---

## 九、增长曲线与 FDE 节奏

```
代码复杂度 / 功能数量
    │
    │                                               ● V5.1 RagChew
    │                                            ● V5.0 UI Modern
    │                                        ● V4.9 语音/CW/FT8
    │                                   ● V4.8 录音/远程管理
    │                              ● V4.6 WDSP 降噪
    │                        ● V4.3 ATR-1000 抽象
    │                   ● V4.0 PTT 延迟优化
    │              ● V3.0 移动端
    │         ● V2.0 架构重构
    │    ● V1.0 Fork
    └───────────────────────────────────────────► 时间
    2024-10  2025-01               2026-03   2026-05

    阶段:  [奠基]→[架构]→[移动]→[运营]→[爆发式创新期]→[UI]→[精化]
            Cycle1  C2   C3   Gap    C4 C5 C6 C7   C8   C9

    FDE 洞察:
    - Gap Period (14个月) 是蓄力期，不是空白期
    - 爆发期 (12周) 完成了 6 个次版本，相当于每 2 周一个版本
    - 每个版本都在前一个版本的产品杠杆上构建
    - V4.0→V5.1 的产品杠杆从 3 增长到 9 (3x 增长)
```

---

*本文档基于 FDE (Forward Deployed Engineering) 方法论，对 MRRC 项目进行全面复盘。*
*资料来源: 208 commits, CHANGELOG (V1.0→V5.2.0), SDD (14章), DESIGN (6文档), 26+ 技术文档, AOD, DSP*
*FDE 理念源自 Palantir，详见 Bob O'Brien 访谈记录。*
*文档版本: V3.1 | 2026-05-18 (V5.2.0 更新: 10 个 FDE Cycle 完整覆盖 V1.0→V5.2.0，综合所有文档源)*

# MRRC 主要功能

**版本**: V4.7.0 (2026-03-10)

1. **远程电台控制** - 频率/模式/VFO切换、PTT发射控制(99%+可靠性)、S表读取、频谱显示
2. **实时音频流** - TX/RX双向音频、Int16/ADPCM/Opus编码、端到端延迟<100ms、**WDSP专业降噪**
3. **DSP数字处理** - **WDSP库集成**：NR2频谱降噪(15-20dB)、NB噪声抑制、ANF自动陷波、AGC自动增益
4. **移动端优化** - iPhone/Android现代Web界面、PWA支持、触摸优化、离线访问
5. **ATR-1000天调集成** - 实时功率/SWR显示、智能学习、快速调谐、第三方软件联动、**PTT/TUNE功率实时显示**
6. **音频优化** - TX均衡器(短波/弱信号/比赛预设)、抗混叠滤波器、低延迟处理

## V4.7.0 更新要点

### WDSP 优化
- 库路径优化：支持项目目录直接运行，无需系统安装
- 日志清理：大幅减少调试输出，降低日志噪音
- AGC参数调优：修复与固定增益的冲突

### ATR-1000 PTT功率显示修复
- 修复PTT按下时功率/SWR不显示的问题
- 调整脚本加载顺序，确保ATR1000对象先定义
- PTT和TUNE现在都正确触发onTXStart

---

┌─────────────────────────────────────────────────────────────────────────┐
│                        Client Layer / 客户端层                          │
├───────────────────────────┬─────────────────────────────────────────────┤
│      Mobile Browser       │         External Software / API             │
│ Desktop/Phone/Pad 浏览器  │         外部软件 / API: JTDX/WSJT etc       │
└─────────────┬─────────────┴──────────────────────┬──────────────────────┘
              │ HTTPS / WebSocket                  │ HTTP REST
              ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Service Layer / 服务层                            │
├───────────────────────────┬─────────────────────────────────────────────┤
│      MRRC Main Program    │         ATR-1000 API Server                 │
│      MRRC 主程序          │         RESTful API (:8080)                 │
│                           │                                             │
│  • Radio Control          │   • /api/v1/status    Status query          │
│  • Audio TX/RX            │   • /api/v1/relay     Relay control         │
│  • WDSP DSP Processing    │   • /api/v1/tune      Quick tune            │
│  • User Auth              │                                             │
└─────────────┬─────────────┴──────────────────────┬──────────────────────┘
              │                                    │
              │ rigctld + Audio                    │ Unix Socket
              │ + WDSP (NR2/NB/ANF/AGC)            │
              ▼                                    ▼
┌───────────────────────────┐         ┌─────────────────────────────────────┐
│       Radio Device        │         │    ATR-1000 Proxy / 天调代理        │
│       IC-M710             │         │       atr1000_proxy.py              │
│                           │         │                                     │
│  • Freq/Mode (rigctld)    │         │  • Single device connection         │
│  • PTT Control            │         │  • Dynamic polling: 15s/5s/0.5s     │
│  • Audio TX/RX            │         │  • Smart Learning + Quick Tune      │
└───────────────────────────┘         └──────────────┬──────────────────────┘
                                                     │ WebSocket
                                                     ▼
                                     ┌─────────────────────────────────────┐
                                     │      ATR-1000 Tuner / 天调设备      │
                                     │                                     │
                                     │  • Power/SWR Display                │
                                     │  • Relay Params (SW/IND/CAP)        │
                                     └─────────────────────────────────────┘

---

## WDSP DSP 处理流程

```
Radio Audio (48kHz Float32)
        ↓
┌─────────────────────────────────┐
│  DC Removal → AGC Pre-amp      │  audio_interface.py
│  → Soft Limiter                 │
└─────────────────────────────────┘
        ↓
Int16 Conversion (48kHz)
        ↓
┌─────────────────────────────────┐
│  WDSP Processing                │  wdsp_wrapper.py
│  ├── NR2 Spectral Denoise      │  (15-20dB noise reduction)
│  ├── NB Noise Blanker          │  (pulse interference)
│  ├── ANF Auto Notch            │  (CW/interference)
│  └── AGC Auto Gain Control     │  (4 modes)
└─────────────────────────────────┘
        ↓
Opus Encode (16kHz, 20kbps)
        ↓
WebSocket → Browser

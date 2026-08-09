# RagChew TX 链路修复 + 压缩器启用设计

- 日期: 2026-08-09
- 状态: 已批准(用户确认)
- 范围: 前端 TX 音频链(`www/modules/tx_audio_eq.js`、`www/controls.js`、`www/mobile_modern.js`)

## 背景

RagChew 是 MRRC 的 4 个 TX EQ 预设之一,定位"本地强信号:温暖自然,平稳舒适,纯净背景"。
但实际实现存在 4 个问题,导致其宣称的 3 个核心卖点(低切/高切/压缩)名不副实:

| # | 问题 | 位置 |
|---|------|------|
| A | 低切 150Hz 失效:`AudioTX_highCut` 被设置成 highpass@150 但从未 connect 进音频链,是死节点 | tx_audio_eq.js:200 / controls.js:1917-1929 |
| B | 3kHz 高切未实现:注释声称用 antiAlias2 做 3k 低通,实际设成 22000Hz(直通) | tx_audio_eq.js:196,219-220 |
| C | "压缩比 3:1"是假的:压缩器实际 threshold=0/ratio=1 透明旁路,console.log 与 UI 仍显示 3:1 | tx_audio_eq.js:236 / mobile_modern.js:2961 |
| D | UI 面板硬编码预设值与真实预设脱节 | mobile_modern.js:2945-2946 vs tx_audio_eq.js:48-58 |

## 目标 TX 链路(RagChew 模式下)

```
mic → preamp(0dB) → highCut(lowpass@150Hz, HPF) → antiAlias(4.5k→22k 直通)
    → antiAlias2(3kHz LPF) → eqLow/Mid/High(0/0/0 直通)
    → midCut(500Hz -2dB) → presence(2.4kHz +3dB)
    → compressor(-18dB / 3:1 / knee 6) → noiseGate(RMS -50dB)
    → gain_node → tx-capture worklet → pushSamples(Opus 48k) → server
```

DEFAULT/MEDIUM/STRONG 预设链路不受影响(highCut 直通、antiAlias2 恢复 4.5k、压缩器仍旁路)。

## 改动方案

### 1. 修复低切 150Hz 接线(修 bug A)

`www/controls.js:1920` — `MediaHandler.callback` 中,把

```js
AudioTX_preamp.connect(AudioTX_antiAlias);
```

改为

```js
AudioTX_preamp.connect(AudioTX_highCut);
AudioTX_highCut.connect(AudioTX_antiAlias);
```

- 标准模式:highCut 保持 `peaking @1000Hz / gain 0dB`(直通),不影响其他预设。
- RagChew 模式:`tx_audio_eq.js:200-205` 已把它切为 `highpass@150Hz`。

### 2. 实现 3kHz 高切(修 bug B)

`www/modules/tx_audio_eq.js:196` — RagChew 分支中,把

```js
AudioTX_antiAlias2.frequency.setValueAtTime(22000, ctx.currentTime);
```

改为

```js
AudioTX_antiAlias2.frequency.setValueAtTime(3000, ctx.currentTime);
```

- antiAlias2 在 RagChew 分支承担 3kHz 高切(低通)。
- 标准分支(line 242-247)仍恢复 4500Hz,不受影响。
- `AudioTX_antiAlias`(第一级)保持 22k 直通不变——高切由第二级承担,保留 Opus 编码前的最低抗混叠。

### 3. 启用压缩器(修 bug C)

`www/modules/tx_audio_eq.js:223-229` — RagChew 分支中,把

```js
AudioTX_compressor.threshold.setValueAtTime(0, ctx.currentTime);
AudioTX_compressor.knee.setValueAtTime(0, ctx.currentTime);
AudioTX_compressor.ratio.setValueAtTime(1, ctx.currentTime);
```

改为

```js
AudioTX_compressor.threshold.setValueAtTime(-18, ctx.currentTime);  // -18dB
AudioTX_compressor.knee.setValueAtTime(6, ctx.currentTime);          // 软拐点
AudioTX_compressor.ratio.setValueAtTime(3, ctx.currentTime);         // 3:1
AudioTX_compressor.release.setValueAtTime(0.200, ctx.currentTime);   // 200ms(与噪声门 300ms 错开)
```

- attack 3ms 保持现状,release 显式设 200ms。
- 日志(line 236)的"压缩比=3:1"变为真实。
- 标准分支(line 222-229 的 else 路径,即 `tx_audio_eq.js:224-229`)保持 threshold=0/ratio=1 旁路,严格遵守 V5.7 保真哲学。

### 4. 修复 UI 预设值脱节(修 bug D)

`www/mobile_modern.js:2944-2947` — `showTXEQPanel` 内的 `presets` 硬编码:

```js
var presets = {
    'MEDIUM': { name: '中', low: -15, mid: 10, high: -20, desc: '平衡清晰度与厚度' },
    'STRONG': { name: '强', low: -20, mid: 12, high: -35, desc: 'iPhone/手机专用' }
};
```

与 `tx_audio_eq.js:46-59` 的真实预设(MEDIUM low:9/mid:10/high:-12;STRONG low:12/mid:12/high:-18)不符。

改为:若 `getTX_EQ_Presets()` 可用,则从它读取 MEDIUM/STRONG 的真实 `low/mid/high` 值构建面板显示;否则回退到当前硬编码。

### 5. 噪声门

保持不变(release 300ms 与压缩器 200ms 已错开,无叠加拖尾)。

## 非改动项

- `AudioTX_preamp` 保持 0dB 直通(V5.7 保真哲学)。
- DEFAULT/MEDIUM/STRONG 预设完全不变。
- server 端 `soft_peak_limiter`(knee 0.9/ceiling 0.98)不变——与前端压缩器不冲突(一个峰值保护、一个动态平滑)。
- Opus 编码器参数(48kHz/64kbps CBR)不变。

## 验证

1. **静态检查**:`python3 -m py_compile MRRC`(前端 JS 无编译,检查引用一致性)。
2. **DevTools 音频图**:浏览器打开 `/mobile`,切到 RagChew 预设,确认:
   - `highCut` 显示 `highpass @150Hz`(此前为 dead node 无信号)
   - `antiAlias2` 显示 `lowpass @3000Hz`(此前 22k 直通)
   - `compressor` 参数 `-18dB / 3:1 / knee 6`(此前旁路)
   - 切回 DEFAULT:`highCut` 回到 `peaking 1000Hz/0dB`,`antiAlias2` 回到 `4500Hz`,compressor 回旁路
3. **PTT 试音**:RagChew 模式下低声说话→无 150Hz 以下隆隆声;高声喊话→峰值被 3:1 温和压缩,无削波。

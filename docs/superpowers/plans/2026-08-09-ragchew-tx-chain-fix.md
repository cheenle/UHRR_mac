# RagChew TX 链路修复 + 压缩器启用 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 RagChew 预设的 3 个实现 bug(低切断线/高切缺失/假压缩),让预设名副其实;DEFAULT/MEDIUM/STRONG 与 server 端不受影响。

**Architecture:** 前端 Web Audio 链修复。将死节点 `AudioTX_highCut` 接入 preamp→antiAlias 之间承担 150Hz 低切;RagChew 分支把 antiAlias2 设为 3kHz 低通承担高切;压缩器在 RagChew 分支从透明旁路改为 -18dB/3:1/knee 6/release 200ms。UI 面板改为从真实预设读取。spec: `docs/superpowers/specs/2026-08-09-ragchew-tx-chain-fix-design.md`。

**Tech Stack:** 原生 JS(Web Audio API),无构建步骤,无测试框架(前端音频,静态验证 + 手动 DevTools 验证)。

## Global Constraints

- 仅改 3 个前端文件:`www/controls.js`、`www/modules/tx_audio_eq.js`、`www/mobile_modern.js`。
- DEFAULT/MEDIUM/STRONG 预设的行为必须完全不变(highCut 直通、antiAlias2 恢复 4500Hz、compressor 保持旁路)。
- server 端 `audio_interface.py`、`MRRC`、Opus 编码参数一律不动。
- preamp 保持 0dB 直通(V5.7 保真哲学)。
- commit message 遵循仓库惯例,结尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`。
- 无 JS 测试框架——验证方式是代码静态检查 + 浏览器 DevTools 音频图确认。

---

### Task 1: 接入低切节点 + 启用 3kHz 高切

**Files:**
- Modify: `www/controls.js:1920`
- Modify: `www/modules/tx_audio_eq.js:196`

**Interfaces:**
- Consumes: `AudioTX_highCut`(已在 `tx_audio_eq.js` 声明并 init,当前为死节点)
- Produces: 音频链变为 `preamp → highCut → antiAlias → ...`;RagChew 模式 antiAlias2 为 lowpass@3000Hz

- [ ] **Step 1: 接入 highCut 到音频链**

在 `www/controls.js` 音频链构建处(`MediaHandler.callback`),把:

```js
        AudioTX_preamp.connect(AudioTX_antiAlias);
```

改为:

```js
        AudioTX_preamp.connect(AudioTX_highCut);
        AudioTX_highCut.connect(AudioTX_antiAlias);
```

同时更新链注释(第 1917 行):

```js
        // 音频链: micSource → preamp → highCut → antiAlias → antiAlias2 → eqLow → eqMid → eqHigh → midCut → presence → compressor → noiseGate → gain_node → processor
```

- [ ] **Step 2: RagChew 分支启用 3kHz 高切**

在 `www/modules/tx_audio_eq.js` 的 RagChew 分支(line ~196),把:

```js
        AudioTX_antiAlias2.type = 'lowpass';
        AudioTX_antiAlias2.frequency.setValueAtTime(22000, ctx.currentTime);
        AudioTX_antiAlias2.Q.setValueAtTime(0.707, ctx.currentTime);
```

改为:

```js
        AudioTX_antiAlias2.type = 'lowpass';
        AudioTX_antiAlias2.frequency.setValueAtTime(3000, ctx.currentTime);
        AudioTX_antiAlias2.Q.setValueAtTime(0.707, ctx.currentTime);
```

(注意:这是 RagChew 分支内的第二个 `AudioTX_antiAlias2` 块,第一个是 `AudioTX_antiAlias` 设 22k 直通,不要混淆。高切只作用于第二级 antiAlias2。)

- [ ] **Step 3: 静态验证接线**

检查音频链无悬空/重复连接:

```bash
grep -n 'AudioTX_preamp.connect\|AudioTX_highCut.connect\|AudioTX_antiAlias.connect\|AudioTX_antiAlias2.frequency.setValueAtTime' www/controls.js www/modules/tx_audio_eq.js
```

Expected:
- `controls.js` 有 `AudioTX_preamp.connect(AudioTX_highCut)` 和 `AudioTX_highCut.connect(AudioTX_antiAlias)`
- `tx_audio_eq.js` RagChew 分支 antiAlias2 = 3000,标准分支 = 4500

- [ ] **Step 4: 验证无重复引用问题**

检查 `AudioTX_highCut` 是否在标准模式保持直通(应为 `peaking @1000Hz / gain 0`):

```bash
grep -n 'AudioTX_highCut.type\|AudioTX_highCut.frequency\|AudioTX_highCut.gain' www/modules/tx_audio_eq.js
```

Expected: 标准分支(line ~250-255)设 `peaking/1000/0.5/0`(直通),RagChew 分支(line ~200-205)设 `highpass/150`。

- [ ] **Step 5: Commit**

```bash
git add www/controls.js www/modules/tx_audio_eq.js
git commit -m "fix: RagChew 低切 150Hz 接入链路 + 3kHz 高切启用

- AudioTX_highCut 接入 preamp→antiAlias 之间(原为死节点)
- RagChew 分支 antiAlias2 从 22k 直通改为 3kHz 低通

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: 启用压缩器 + 修复 UI 预设脱节

**Files:**
- Modify: `www/modules/tx_audio_eq.js:223-229`
- Modify: `www/mobile_modern.js:2943-2947`

**Interfaces:**
- Consumes: Task 1 的音频链接线;`getTX_EQ_Presets()` 已在 `tx_audio_eq.js` 定义
- Produces: RagChew 模式压缩器 `-18dB / 3:1 / knee 6 / release 200ms`;UI 面板显示真实预设值

- [ ] **Step 1: RagChew 分支启用压缩器**

在 `www/modules/tx_audio_eq.js` 的 RagChew 分支(line ~223-229),把:

```js
        // 压缩器: 透明旁路（threshold=0/ratio=1 永不触发，保真优先）
        if (AudioTX_compressor) {
            AudioTX_compressor.threshold.setValueAtTime(0, ctx.currentTime);
            AudioTX_compressor.knee.setValueAtTime(0, ctx.currentTime);
            AudioTX_compressor.ratio.setValueAtTime(1, ctx.currentTime);
            AudioTX_compressor.attack.setValueAtTime(0.003, ctx.currentTime);
            AudioTX_compressor.release.setValueAtTime(0.250, ctx.currentTime);
        }
```

改为:

```js
        // 压缩器: 温和 3:1（RagChew 平稳定位；默认链仍透明旁路）
        if (AudioTX_compressor) {
            AudioTX_compressor.threshold.setValueAtTime(-18, ctx.currentTime);  // -18dB
            AudioTX_compressor.knee.setValueAtTime(6, ctx.currentTime);          // 软拐点
            AudioTX_compressor.ratio.setValueAtTime(3, ctx.currentTime);         // 3:1
            AudioTX_compressor.attack.setValueAtTime(0.003, ctx.currentTime);
            AudioTX_compressor.release.setValueAtTime(0.200, ctx.currentTime);   // 200ms(与噪声门 300ms 错开)
        }
```

同时更新 RagChew 分支的 console.log(line ~236)使描述准确:

```js
        console.log('🎛️ TX EQ RagChew: 低切=' + preset.lowCut + 'Hz, 500Hz=' + preset.midCutGain + 'dB, 2.4kHz=' + preset.presenceGain + 'dB, 高切=' + preset.highCut + 'Hz, 压缩=3:1 knee6');
```

- [ ] **Step 2: 修复 UI 预设值脱节**

`www/mobile_modern.js:2943-2947` 的 `showTXEQPanel` 里,fallback 硬编码块与真实预设脱节(MEDIUM low:-15 应为 9、STRONG low:-20 应为 12)。`getTX_EQ_Presets()` 存在时用真实值(已是现状);修正 fallback 使其与 `tx_audio_eq.js:46-59` 一致:

```js
    const presets = typeof getTX_EQ_Presets === 'function' ? getTX_EQ_Presets() : {
        'DEFAULT': { name: '默认', low: 0, mid: 0, high: 0, desc: '无EQ处理' },
        'MEDIUM': { name: '中', low: 9, mid: 10, high: -12, desc: '适中调节：增强厚度与清晰度' },
        'STRONG': { name: '强', low: 12, mid: 12, high: -18, desc: '最大发射功率：iPhone/手机专用' }
    };
```

(注意:RAGCHEW 预设也在 `TX_EQ_PRESETS` 中,`getTX_EQ_Presets()` 返回后 `Object.keys(presets)` 会包含它,`preset.lowCut`/`preset.highCut` 在 line 2961 使用,无需改动。)

- [ ] **Step 3: 静态验证参数**

```bash
grep -n 'AudioTX_compressor.threshold\|AudioTX_compressor.ratio\|AudioTX_compressor.knee\|AudioTX_compressor.release' www/modules/tx_audio_eq.js
```

Expected:
- RagChew 分支: threshold=-18, ratio=3, knee=6, release=0.200
- 标准分支: threshold=0, ratio=1, knee=0(保持旁路)

- [ ] **Step 4: 验证 UI fallback 修正**

```bash
grep -n "low: 9, mid: 10\|low: 12, mid: 12" www/mobile_modern.js
```

Expected: fallback 块显示真实值 9/10/-12 和 12/12/-18。

- [ ] **Step 5: Commit**

```bash
git add www/modules/tx_audio_eq.js www/mobile_modern.js
git commit -m "fix: RagChew 启用 3:1 压缩 + UI 面板真实预设值

- RagChew 压缩器 -18dB/3:1/knee6/release200ms(原透明旁路)
- UI fallback 预设值与 tx_audio_eq.js 对齐(原硬编码旧值)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: 端到端验证

**Files:**
- (无代码改动,仅验证)

**Interfaces:**
- Consumes: Task 1+2 的全部改动

- [ ] **Step 1: 代码一致性检查**

```bash
python3 -m py_compile MRRC audio_interface.py hamlib_wrapper.py   # 确认后端未被误改
git status --short
```

Expected: 仅 3 个 www 文件被修改;后端无改动。

- [ ] **Step 2: DevTools 音频图手动验证**

在浏览器打开 `https://localhost:8877/mobile`(或静态 `mobile_modern.html`),按 F12 打开 Web Audio 检查器,或运行前端时观察 console:

1. 菜单 → TX Equalizer → 选择 **RagChew**
2. 确认 console 输出 `🎛️ TX EQ RagChew: 低切=150Hz, ..., 高切=3000Hz, 压缩=3:1 knee6`
3. Web Audio 图: `highCut` 为 `highpass @150Hz`(此前为死节点)、`antiAlias2` 为 `lowpass @3000Hz`(此前 22k 直通)、compressor 参数 `-18dB/3:1/knee6`
4. 切回 **DEFAULT**:`highCut` 回 `peaking 1000Hz/0dB`、`antiAlias2` 回 `4500Hz`、compressor 回旁路(threshold 0/ratio 1)

Expected: 全部符合。

- [ ] **Step 3: PTT 试音**

RagChew 模式下按住 PTT 说话:
1. 低沉轰鸣(150Hz 以下)明显减弱 → 低切生效
2. 大声喊话时峰值被温和压缩,无削波方波 → 压缩生效
3. 停止说话 300ms 后静音,无电流底噪 → 噪声门正常

Expected: 三项符合。

- [ ] **Step 4: 版本号 bump**

改动涉及前端功能,`www/index.html` 与 `www/mobile_modern.html` 中 `tx_audio_eq.js`、`controls.js`、`mobile_modern.js` 的 `?v=5.7.1` 缓存版本号提升到 `?v=5.7.2`(防止浏览器缓存旧 JS)。检查:

```bash
grep -n 'v=5.7' www/index.html www/mobile_modern.html
```

将 `tx_audio_eq.js?v=5.7.1`、`controls.js?v=5.7.1`、`mobile_modern.js?v=5.7.1` 及相关脚本的版本号改为 `5.7.2`。

- [ ] **Step 5: Commit**

```bash
git add www/index.html www/mobile_modern.html
git commit -m "chore: TX 前端缓存版本号 5.7.1 → 5.7.2(RagChew 修复)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

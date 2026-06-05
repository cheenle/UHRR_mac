# PTT 释放→恢复RX音频 延迟深度排查报告

## 概述

用户报告 PTT 释放后 RX 音频恢复需要约 **2 秒**。已有分析文档 (`ptt_release_delay_analysis.md`) 估算桌面端仅 15-30ms、iOS 端 140-160ms。本报告深入搜索能造成约 2000ms 延迟的真正原因。

## 🔴🔴🔴 一级发现：2秒延迟的核心原因

### 1. `sdr_modern.js` AudioWorklet 缓冲区配置错误 `min=10`

**文件**: `www/sdr_modern.js:302-313`
**找到**: 第305行配置 `min: 10, max: 60`

```javascript
async setupAudioWorklet() {
    try {
        await this.audioContext.audioWorklet.addModule('rx_worklet_processor.js');
        this.rxPlayer = new AudioWorkletNode(this.audioContext, 'rx-player');
        this.rxPlayer.connect(this.gainNode);
        this.rxPlayer.port.postMessage({
            type: 'config',
            min: 10,       // 🔴 最小缓冲10帧！
            max: 60
        });
    }
}
```

**问题**: AudioWorklet 需要累积 **10 帧** 数据才开始播放。PTT 释放后队列被清空，新数据需要先填满 10 帧：
- Opus 40ms 编码模式: **10 × 40ms = 400ms** 
- Int16 PCM 模式 (256 samples @ 48kHz → ~85 samples @ 16kHz): **10 × 85/16000 ≈ 53ms**
- AudioContext render quantum (128 samples): **10 × 128/16000 = 80ms**

**对比**: `controls.js` 第403行使用 `min: 1`，在任何模式下都能立即播放。

**对比**: `tx_button_optimized.js` 第260行也使用 `min: 1`（发送给 `AudioRX_source_node`）。

**但 `sdr_modern.js` 的 `min:10` 不会导致 2 秒，只是 50-400ms。** 需要与下面其他因素叠加。

---

### 2. `sdr_modern.js` 接管了 `wsAudioRX.onmessage` — 双音频链路冲突

**文件**: `www/sdr_modern.js:207-225`
**找到**: 第214行覆写了 controls.js 的音频消息处理器

```javascript
initAudioRX() {
    const waitForWSAndInit = () => {
        if (typeof wsAudioRX !== 'undefined' && wsAudioRX && wsAudioRX.readyState === WebSocket.OPEN) {
            // 覆盖 onmessage 处理
            wsAudioRX.onmessage = (event) => {
                this.handleAudioRX(event.data);  // 走 sdr_modern 的路径
            };
        } else {
            setTimeout(waitForWSAndInit, 100);
        }
    };
    setTimeout(waitForWSAndInit, 500);
}
```

**后果**:
- `controls.js` 的 AudioWorklet (`AudioRX_source_node`, min=1) **永远不会收到数据**
- `sdr_modern.js` 创建了自己的 `AudioContext` (`this.audioContext`) 和 AudioWorklet (`this.rxPlayer`, min=10)
- **`tx_button_optimized.js` 的 flush/reset 命令发送给 `AudioRX_source_node`，影响的是 controls.js 的工作线程，不影响 sdr_modern.js 的工作线程**
- 结果是：PTT 释放后，controls.js 的队列被清空（但本就不接收数据），sdr_modern.js 的队列从未被清空（但 TX 期间也无数据流入，所以可能已经是空的）

---

### 3. ⚡ `pttUp()` 中 `toggleaudioRX(true)` 是反向操作！

**文件**: `www/sdr_modern.js:1632-1636`
**找到**: PTT 释放时错误地静音了 RX！

```javascript
// 3. 恢复 RX 音频 (使用 controls.js 的函数)
if (typeof toggleaudioRX === 'function') {
    toggleaudioRX(true);   // 🔴🔴🔴 BUG! 应该是 toggleaudioRX(false)!
}
```

**问题**: `toggleaudioRX(true)` 设置 `muteRX = true` → `AudioRX_SetGAIN(0)` → 音量设为 0。

**影响**:
- `controls.js` 的 AudioContext 增益被设为 0
- 但 `sdr_modern.js` 使用自己的 `this.gainNode`，不受此影响
- 所以如果用户使用 `modern.html`（加载 `audio_rx.js` + `controls.js`，不加载 `sdr_modern.js`），这个 bug 不触发
- 如果用户使用 `sdr_modern.html`（加载 `controls.js` + `sdr_modern.js`），这个 bug 使 controls.js 的增益为 0，但 sdr_modern.js 的音频路径仍能播放

---

### 4. `sdr_modern.html` 未加载 `ptt_manager.js` 和 `tx_button_optimized.js`

**文件**: `www/sdr_modern.html:344-345`
```html
<script src="controls.js"></script>
<script src="sdr_modern.js"></script>
```

`sendTRXptt()` 定义在 `ptt_manager.js` 中，该文件未被加载！`sdr_modern.js` 的 `pttUp()` 在第 1621-1624 行调用 `sendTRXptt(false)` 会静默失败（被 try/catch 捕获）。这意味着 `setPTT:false` 命令可能根本没发送到后端。

`TXControl()` 定义在 `tx_button_optimized.js` 中，该文件也未加载。`sdr_modern.js` 的 `pttDown()` 不调用 `toggleaudioRX(true)` 来在 TX 期间静音 RX。

---

### 5. `modern.html` 加载 `audio_rx.js` + `controls.js` 的函数覆盖

**文件**: `www/modern.html:325-329`
```html
<script src="modern.js"></script>
<script src="tx_button_optimized.js"></script>
<script src="audio_rx.js"></script>
<script src="control_trx.js"></script>
<script src="controls.js"></script>
```

- `audio_rx.js` 先定义 `AudioRX_start()`（使用 `decodeAudioData` 的旧路径）
- `controls.js` 后加载，覆盖为 AudioWorklet 版本
- `tx_button_optimized.js` 两秒看门狗（30秒超时）不影响正常释放
- **但 `controls.js` 的 `wsAudioRX.onmessage` 在异步块中设置，存在竞态**（见下文）

---

### 6. `controls.js` 的 `wsAudioRX.onmessage` 竞态条件

**文件**: `www/controls.js:246-425`

```javascript
wsAudioRX = new WebSocket(...);  // Line 246 - WebSocket 开始连接
// Line 248-250: onopen, onclose, onerror 设置
// ...
(async () => {                     // Line 395 - 异步块
    if (useAudioWorklet) {
        await AudioRX_context.audioWorklet.addModule('rx_worklet_processor.js');
        // ...
        wsAudioRX.onmessage = function(msg){...};  // Line 408 - onmessage 在异步块内设置
    }
})();
```

WebSocket 在 `onmessage` 设置前就可能收到数据。浏览器会缓冲消息，直到 `onmessage` 被赋值。这只在首次连接时影响，不影响 PTT 切换。

---

### 7. 后端 `stoppttontimeout` 看门狗清理问题

**文件**: `MRRC:532-554`

```python
def stoppttontimeout(self):
    # ...
    tornado.ioloop.IOLoop.instance().add_timeout(
        datetime.timedelta(seconds=0.2), self.stoppttontimeout)
```

`on_close()`（第716行）**没有取消这个定时器**。当 WS_AudioTX 连接关闭后，定时器继续运行：
- 200ms 间隔，无限期运行
- `self.ws_connection` 在 `on_close` 后为 `None`，所以 `stoppttontimeout` 不会触发 `CTRX.setPTT("false")`
- **但 Python 对象引用泄漏** — `WS_AudioTXHandler` 实例因定时器闭包而无法被 GC 回收

这不直接导致 2 秒延迟，但会消耗服务器资源，随着时间推移可能影响整体响应。

---

### 8. `syncPTTStatusDisplay` 的 `getPTT` 轮询

**文件**: `www/modules/ptt_manager.js:131-148`

```javascript
function syncPTTStatusDisplay() {
    if (PTT_DEVICE_STATE !== PTT_USER_INTENT) {
        wsControlTRX.send("getPTT");  // 强制查询
    }
    updatePTTStatusDisplay(PTT_DEVICE_STATE, true);
    setTimeout(syncPTTStatusDisplay, 1000);  // 每1秒轮询
}
```

在 PTT 释放后 `PTT_USER_INTENT`（在 `sendTRXptt` 中设置）和 `PTT_DEVICE_STATE`（从服务器响应更新）都变为 `false`，不会触发额外查询。但两者同步存在微小窗口期，不导致 2 秒延迟。

---

### 9. rigctld `T 0` 命令的 3 秒套接字超时

**文件**: `MRRC:2533`

```python
sock.settimeout(3)  # 3秒超时
sock.connect((self.rigctld_host, self.rigctld_port))
command = f"T {ptt_value}\n"
sock.sendall(command.encode())
response = sock.recv(1024).decode().strip()
```

如果电台响应 `T 0` 较慢（例如电台 PTT 继电器释放需要时间），**每次 setPTT 调用最多等待 3 秒！** 加上 3 次重试（每次 +50ms），最坏情况可达 ~9 秒。

但 `infos["PTT"] = False` 在 rigctld 交互前已设置（第2523行），所以音频线程立即响应，不受 rigctld 延迟影响。

---

### 10. PyAudioCapture 线程循环时序

**文件**: `audio_interface.py:467-479`

```python
is_ptt_on = main_module.CTRX.infos.get("PTT", False)
if is_ptt_on:
    continue  # 跳过发送
```

- 读取间隔：PyAudio `CHUNK` 大小默认 256 帧 @ 48kHz ≈ **5.3ms**
- `continue` 跳过当前帧后，下一循环检查 `infos["PTT"]`
- `infos["PTT"]` 在 `setPTT()` 中立即设为 `False`（第2523行）
- `_flush_opus_accumulator` 标志在下一循环清除残留数据

**最大延迟**: ~5.3ms + Opus 累积帧填充时间（~7ms）= ~12ms。不造成 2 秒延迟。

---

## 总结：各因素延迟贡献

| # | 因素 | 延迟 | 影响页面 | 严重程度 |
|---|------|------|---------|---------|
| **1** | `sdr_modern.js` AudioWorklet `min=10` | **50-400ms** | sdr_modern.html | 🔴 中 |
| **2** | `pttUp()` 调用 `toggleaudioRX(true)` BUG | **永久静音** | sdr_modern.html | 🔴🔴🔴 严重 |
| **3** | `sdr_modern.html` 未加载 ptt_manager.js | **PTT 命令不发** | sdr_modern.html | 🔴🔴🔴 严重 |
| **4** | `controls.js` vs `sdr_modern.js` 双音频链路 | **架构问题** | sdr_modern.html | 🔴🔴 高 |
| **5** | rigctld 3秒套接字超时 | 0-3000ms | 所有页面 | 🔴 中（仅影响反馈） |
| **6** | `stoppttontimeout` 定时器泄漏 | 内存泄漏 | 所有页面 | 🟡 低 |
| **7** | `syncPTTStatusDisplay` 1秒轮询 | ~1秒显示同步 | 所有页面 | 🟢 无影响 |
| **8** | `PTT_DEBOUNCE_DELAY=50ms` | 0-50ms | 所有页面 | 🟢 已优化 |
| **9** | `opus_accumulator` 残留 | ~7-15ms | 所有页面 | 🟢 已修复 |

## 修复建议（按优先级）

### P0: 修复 `sdr_modern.js` `pttUp()` 的 `toggleaudioRX` 参数

`www/sdr_modern.js` 第 1634 行: `toggleaudioRX(true)` → `toggleaudioRX(false)`

### P1: 修复 `sdr_modern.js` AudioWorklet `min` 参数

`www/sdr_modern.js` 第 311 行: `min: 10` → `min: 1`

### P2: 确保 `sdr_modern.html` 加载 `modules/ptt_manager.js`

`sdr_modern.html` 应加载 `modules/ptt_manager.js` 或确保 `sendTRXptt()` 可用。

### P3: PTT 释放时向所有 AudioWorklet 发送 flush

`sdr_modern.js` 的 `pttUp()` 也应向 `this.rxPlayer` 发送 flush+reset 消息。

### P4: 修复 `stoppttontimeout` 定时器泄漏

`MRRC` 中 `WS_AudioTXHandler.on_close()` 应取消 `stoppttontimeout` 的 `add_timeout`。

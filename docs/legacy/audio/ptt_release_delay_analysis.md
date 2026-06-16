# PTT 释放后延迟返回 RX 的全面分析

## TX→RX 切换完整流程

```
用户松开PTT按钮
  ↓
touchstart/touchend → TXControl('stop')
  ├─ 1. sendTRXptt(false)    → wsControlTRX → setPTT:false
  ├─ 2. toggleRecord()        → stopRecord() → wsAudioTX → s:
  ├─ 3. 清空前端RX缓冲区
  │    ├─ AudioRX_audiobuffer = []
  │    ├─ AudioWorklet: flush + reset + config(min=1, max=20)
  │    └─ ScriptProcessor: __rxAccumulatedBuffer = []
  ├─ 4. toggleaudioRX(false)  → 恢复RX增益
  └─ 5. updatePTTStatus(false) / 清除看门狗 / ATR-1000清理

后端收到 setPTT:false
  ├─ 清空所有 AudioRXHandlerClients[i].Wavframes（服务器RX队列）
  ├─ CTRX.infos["PTT"] = False（立即生效，audio_interface.py 半双工检查据此恢复）
  ├─ rigctld: T 0（最多3次重试，每次间隔50ms）
  └─ 广播 getPTT:false 给所有客户端

后端收到 s:
  ├─ audio_playback.close()（关闭PyAudio TX输出流）
  ├─ 再次 CTRX.setPTT("false")（冗余保护）
  └─ 广播 getPTT:false

audio_interface.py PyAudioCapture 线程
  ├─ 检测 is_ptt_on = False，恢复发送RX数据
  └─ Opus 编码器有累积残留帧，需填充到完整的 opus_frame_size
```

---

## 发现的所有延迟因素

### 1. 🔴 CTRX.setPTT() 中的 rigctld 重试机制

**位置**：`MRRC` 第 2529-2569 行，`TRXRIG.setPTT()`

**代码**：
```python
for attempt in range(max_retries):  # max_retries = 3
    # send T 0/1 to rigctld
    if not success and attempt < max_retries - 1:
        time.sleep(0.05)  # 50ms delay between retries
```

**延迟**：首次成功发送 ≈ 0ms；如果失败，每重试一次 +50ms，最多 +100ms。

**优化程度**：⭐⭐⭐⭐⭐ 高 — 如果 rigctld 通常一次成功，这部分无延迟。但代码中每次 setPTT 都建立新的 TCP 连接（无连接池），这本身就有开销。可缓存 rigctld socket 连接减少延迟。

---

### 2. 🔴 WS_AudioTX 的 stoppttontimeout() —— 误触发的 PTT 超时

**位置**：`MRRC` 第 532-554 行

**代码**：
```python
if time.time() > last_AudioTXHandler_msg_time + 0.2:
    self.miss_count += 1
    if self.miss_count >= 25 and ...:
        CTRX.setPTT("false")
```

**机制**：每 200ms 检查一次，连续 25 次未收到 TX 音频帧（即 5 秒）强制 PTT=Off。这是 PTT 看门狗，不影响正常释放。

**但有一个问题**：`stoppttontimeout` 每 200ms 注册一次 `add_timeout`，如果 TX 结束后 `on_close` 没有取消这个定时器，它可能仍在运行。但代码中 `on_close` 不会取消它，所以 PTT 释放后这个定时器仍可能触发。

**优化程度**：⭐⭐ 低 — 不影响正常 PTT 释放流程，但看门狗未清理有潜在 bug。

---

### 3. 🔴 前端 PTT 按钮 debounce 延迟（50ms）

**位置**：`www/modules/ptt_manager.js` 第 15 行

```javascript
var PTT_DEBOUNCE_DELAY = 50;
```

**机制**：防抖机制仅在相同状态的重复命令时生效，不影响首次 `sendTRXptt(false)`。**但** `lastPTTState` 跨 PTT 周期保持，如果上一次 stop 时间戳距本次 < 50ms，可能意外跳过。

**优化程度**：⭐⭐⭐ 中 — 正常情况不影响，但状态边界有隐患。

---

### 4. 🔴 setPTT 内部调用套娃——双重 setPTT(false)

**位置**：
- `MRRC` 第 2806 行：`WS_ControlTRX.on_message` → `CTRX.setPTT(datato)`
- `MRRC` 第 650 行：`WS_AudioTXHandler.on_message('s:')` → `CTRX.setPTT("false")`

**问题**：  
`setPTT:false` 走 ControlTRX WebSocket 触发一次 setPTT，`s:` 走 AudioTX WebSocket 再 trigger 一次。两次都调用 rigctld `T 0`，第一次成功后第二次是冗余操作。

但这并非延迟问题——第一次 setPTT 已经立即更新了 `infos["PTT"]=False`，audio_interface 的半双工检查在第一次就生效了。

**优化程度**：⭐⭐ 低 — 冗余但无害，可以忽略。

---

### 5. 🔴🔴 PyAudioCapture RX 音频 opus_accumulator 残留帧延迟

**位置**：`audio_interface.py` 第 503-511 行

```python
opus_accumulator = np.concatenate([opus_accumulator, int16_data])
while len(opus_accumulator) >= opus_frame_size:
    frame_data = opus_accumulator[:opus_frame_size]
    opus_accumulator = opus_accumulator[opus_frame_size:]
    # encode and send...
```

**机制**：  
PTT 释放前，`is_ptt_on = True` 时，PyAudioCapture 执行 `continue` 跳过整个发送逻辑（第 478 行）。但 opus_accumulator **不会**被清零，只是一直累积不被处理。  
PTT 释放后，`is_ptt_on = False`，下一帧数据被追加到残留的 opus_accumulator 中，只有当累积达到 `opus_frame_size` 后才发送。  
如果 opus_frame_size=320 (16kHz@20ms) 且残留 200 个样本，则需要再等约 120 样本（~7.5ms）才编码发送。

**关键问题**：PTT 释放时 `opus_accumulator` **没有被清空或刷新**。  
残留数据是 TX 期间累积的旧数据，PTT 释放后第一条 RX 数据必须填补这些残留帧后才能送达客户端。

**优化程度**：⭐⭐⭐⭐⭐ 非常高  
**修复建议**：在 PTT 释放时清空 `opus_accumulator`，或者检测 PTT 状态变化时重置累加器。

---

### 6. 🔴🔴 AudioRXHandlerClients Wavframes 队列清空后重新填满的延迟

**位置**：`MRRC` 第 2799-2802 行

```python
if datato.lower() == "false":
    for client in AudioRXHandlerClients:
        client.Wavframes = []
```

**机制**：PTT 释放时立即清空服务器端 RX 队列。这**消除了旧数据**，但问题是：
- PyAudioCapture 线程正在运行，在 `is_ptt_on` 变为 False 的那个循环周期，如果已经执行了 `continue`，需要再等一个 PyAudio.read() 周期（256 帧 @48kHz ≈ 5.3ms）
- 新数据写入 Wavframes 后，tailstream() 协程需要 2ms 的 sleep 检测到非空队列，然后发送
- WebSocket 有网络延迟

**这是必要的**——不清空会听到旧数据。但清空后到新数据到达之间存在一个**不可避免的空窗期**。

**优化程度**：⭐⭐⭐⭐ 高  
可考虑在 PTT 释放后立即发送一个"静音填充帧"来覆盖空窗期，客户端收到后立即播放（保持 AudioContext 活跃），等真正的 RX 数据到达时用新数据替换。

---

### 7. 🔴 AudioWorklet 缓冲区清空后的初始帧延迟

**位置**：`www/rx_worklet_processor.js` 第 30-34 行

```javascript
else if (data && data.type === 'flush') {
    this.queue.length = 0;  // 清空队列
}
```

以及 `www/tx_button_optimized.js` 第 259-260 行：
```javascript
AudioRX_source_node.port.postMessage({type: 'config', min: 1, max: 20});
```

**机制**：  
flush + reset 清空了 AudioWorklet 内部队列。config(min=1) 意味着只要有 1 帧数据就立即播放（不再等待缓冲填满）。  
这已经是**当前代码做的最好的优化**。min=1 确保 TX→RX 切换后立即播放第一帧。

**优化程度**：✅ 已优化，不需要再改。

---

### 8. 🔴 ScriptProcessor 模式的累积缓冲区清空延迟

**位置**：`www/controls.js` 第 438-444 行

```javascript
window.__rxAccumulatedBuffer = [];
window.__rxTotalSamples = 0;
```

以及前端 TX 停止时 `www/tx_button_optimized.js` 第 268-271 行：
```javascript
window.__rxAccumulatedBuffer = [];
window.__rxTotalSamples = 0;
```

**机制**：  
ScriptProcessor 模式（iOS Safari）下，清空累积缓冲区后，需要等 `onaudioprocess` 被调用（2048 帧回调周期）才开始从空缓冲区读取数据。下一次回调在 2048/16000 ≈ 128ms 后才会触发。

**优化程度**：⭐⭐⭐⭐ 高  
iOS Safari 的 ScriptProcessor 128ms 回调间隔是硬伤。可考虑对 iOS 使用更小的 BUFF_SIZE（如 1024 将延迟降到 64ms），但 iOS 要求 2 的幂次方且不能太小否则有性能问题。

---

### 9. 🔴 startRecord() 中 sendSettings() 的开销

**位置**：`www/controls.js` 第 1916 行

```javascript
function startRecord() {
    sendSettings();  // 发送 "m:rate,encode,opusRate,opusFrameDur"
    isRecording = true;
}
```

**问题**：这仅在 TX **开始**时，不影响 TX→RX 切换的延迟。

---

### 10. 🔴🔴 PyAudioCapture 半双工 continue 导致的一帧数据丢失

**位置**：`audio_interface.py` 第 469-478 行

```python
is_ptt_on = main_module.CTRX.infos.get("PTT", False)
if is_ptt_on:
    # TX 时跳过 RX 数据发送，但保持连接
    continue
```

**问题**：  
当 PTT 状态刚变为 False，但 PyAudioCapture 线程可能正在处理一个之前已读取的音频帧（即 `continue` 已经在执行中）。下一个循环迭代才能发送数据。  
这导致最多丢失 1 帧数据（256 float32 samples @48kHz ≈ 5.3ms）。

**叠加效果**：  
opus_accumulator 残留 + 1 帧丢失 + WebSocket 传输 = **总延迟约 12-20ms**。

这属于**正常的架构延迟**，但如果用户感知到延迟明显更大（>100ms），则问题可能在其他地方。

**优化程度**：⭐⭐⭐ 中  
可通过在 PTT 释放时设置一个标志，迫使线程立即发送下一个可用帧来减少 1 帧延迟。

---

### 11. 🔴 前端 WebSocket 消息串行发送——setPTT 先发但等待后端响应

**位置**：`www/tx_button_optimized.js` 第 232-236 行

```javascript
// 1. sendTRXptt(false) — 通过 wsControlTRX 发送
sendTRXptt(false);

// 2. toggleRecord() — 通过 wsAudioTX 发送 "s:"
toggleRecord();
```

这两个 WebSocket 消息是**串行**发送的，JavaScript 没有 await/并行。  
实际从浏览器的角度看，`send()` 调用是异步缓冲的（WebSocket 有 send buffer），所以两者几乎同时到达服务器。

但服务器端处理是有顺序的：先处理 `setPTT:false`（清空 Wavframes + rigctld），再处理 `s:`（close playback + rigctld again）。

**优化程度**：⭐⭐ 低 — 实际影响很小，因为 WebSocket 是 TCP 流式，两消息几乎同时到达。

---

### 12. 🔴 前端 PTT 按钮事件处理器的 touchstart/touchend 延迟

**位置**：`www/tx_button_optimized.js` 第 361-413 行

**机制**：所有触摸事件使用 `{ passive: false, capture: true }`，这确保事件被优先处理。  
但 `touchend` 到 `TXControl('stop')` 调用之间有一层条件判断（`touch.identifier !== TXState.touchId`），在正常操作下无延迟。

**优化程度**：✅ 已优化。

---

### 13. 🔴 IS_MOBILE 检测 + 移动端页面初始化竞争

**位置**：`www/controls.js` 第 53-56 行

```javascript
// TX按钮处理由tx_button_optimized.js统一管理
console.log('主界面加载完成');
```

以及 `www/tx_button_optimized.js` 第 491-497 行：
```javascript
document.addEventListener('DOMContentLoaded', function() {
    ensureTXButtonReady();
});
```

**问题**：tx_button_optimized.js 和 controls.js 的 `toggleRecord` / `stopRecord` 函数可能在 DOM 加载完成前调用。  
但 `ensureTXButtonReady()` 有重试机制（每 100ms 重试），实际不影响。

**优化程度**：✅ 已优化。

---

## 总结：延迟分布表

| # | 延迟因素 | 典型延迟 | 代码位置 | 优化优先级 |
|---|---------|---------|---------|-----------|
| 1 | **opus_accumulator 残留帧** | ~7-15ms | `audio_interface.py:503` | ⭐⭐⭐⭐⭐ |
| 2 | **Wavframes 清空后重新填充** | ~5-10ms | `MRRC:2799-2802` + `audio_interface.py:546-559` | ⭐⭐⭐⭐ |
| 3 | **PyAudioCapture 半双工 continue 丢帧** | ~5ms | `audio_interface.py:478` | ⭐⭐⭐ |
| 4 | **rigctld 重试机制** | 0-100ms（罕见） | `MRRC:2529-2569` | ⭐⭐⭐ |
| 5 | **ScriptProcessor 128ms 回调间隔** | ~128ms（仅 iOS） | `www/controls.js:438` | ⭐⭐⭐⭐ |
| 6 | **前端 debounce 边界问题** | 0-50ms（罕见） | `www/modules/ptt_manager.js:15` | ⭐⭐ |
| 7 | **stoppttontimeout 定时器未清理** | 不影响释放 | `MRRC:532-554` | ⭐⭐ |

**估算总延迟**：
- 桌面端（AudioWorklet）：**~15-30ms**（主要是 accu 残留 + 队列清空重填）
- iOS Safari（ScriptProcessor）：**~140-160ms**（额外 +128ms 回调间隔）

**用户感知的可见延迟**可能还包括：
- PTT 指示灯变更到 RX 音频恢复之间的视觉延迟
- 电台硬件 PTT 释放到音频输出恢复的硬件延迟（radio relay click）
- 用户期望听到的 RX 背景噪声恢复时间

## 推荐的快速修复（按优先级）

### P0：清空 opus_accumulator
在 `WS_ControlTRX.on_message` 的 `setPTT:false` 处理中，或在 `CTRX.setPTT("false")` 执行时，增加对 PyAudioCapture opus_accumulator 的清空。

```python
# MRRC 第 2800 行附近，增加：
from audio_interface import PyAudioCapture
# 通过类变量传递清空信号（跨线程通信）
PyAudioCapture._flush_opus_accumulator = True
```

然后在 `audio_interface.py` 的 run() 循环中检测这个标志：
```python
if PyAudioCapture._flush_opus_accumulator:
    opus_accumulator = np.array([], dtype=np.int16)
    PyAudioCapture._flush_opus_accumulator = False
```

### P1：PTT 释放后立即发送填充帧
在 Wavframes 清空后，立即插入一帧静音数据，让前端 AudioWorklet 立即有数据播放，避免 underrun。

### P2（仅 iOS）：减小 ScriptProcessor buffer size
将 `BUFF_SIZE` 从 2048 改为 1024，减少 iOS 的回调延迟到 ~64ms。

### P3：优化 rigctld 连接池
缓存 rigctld socket 连接，避免每次 setPTT 都新建 TCP 连接。

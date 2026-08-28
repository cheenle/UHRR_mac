# iOS 前后台切换恢复设计

## 背景

iPhone Chrome 与 Safari 一样使用 WebKit。页面反复进入后台时，WebKit 会冻结 JavaScript、将音频上下文置为 `suspended` 或非标准的 `interrupted`，并可能留下 `readyState === OPEN` 的半开 WebSocket。当前 V5.8.4 恢复路径还存在旧 socket 延迟 `onclose` 回调误操作新连接的竞态。

## 已确认根因

`resumeAudioAfterBackground()` 判定 RX 断流后会关闭旧连接并立即创建新连接。旧连接稍后触发 `wsAudioRXclose()`，安排 3 秒重连。定时器执行时，`AudioRX_start()` 先关闭当前 AudioContext，之后才发现当前 WebSocket 已经 OPEN 并返回。因此页面会留下“WebSocket 正常、AudioContext 已关闭”的假健康状态。

同时存在以下放大因素：

- socket 回调和重连定时器均通过全局变量操作连接，无法区分旧实例与当前实例；
- 音频恢复只识别 `suspended`，不识别 iOS WebKit 的 `interrupted` 和不可恢复的 `closed`；
- RX 的异步 AudioWorklet 初始化可能在连接已被替换后继续绑定全局 socket；
- 控制通道有两个独立的 5 秒 PTT 查询定时器；
- 多个前台事件没有统一去重；
- TX AudioContext 和麦克风轨道未纳入完整健康检查。

## 设计

### 1. 连接实例所有权

RX、TX 和控制 WebSocket 的事件处理器接收创建时的 socket 实例。处理器及延迟重连执行前必须确认该实例仍等于当前全局 socket。旧实例的 `close`、`error` 或异步初始化结果直接忽略，不能改变状态灯、关闭上下文或安排重连。

### 2. RX 原子重建

`AudioRX_start()` 首先检查当前 socket 与 AudioContext 是否同时健康。只有完整健康时才复用；socket 存活但上下文关闭时关闭该 socket并建立全新链路。创建时捕获本地 socket 和 AudioContext，AudioWorklet 完成异步加载后再次验证两者仍为当前实例。

### 3. 统一前台恢复

`resumeAudioAfterBackground(reason)` 使用共享 Promise 去重并按固定顺序执行：

1. 若电源关闭则退出；
2. 恢复 RX、TX 的 `suspended`/`interrupted` AudioContext；
3. RX 上下文关闭、socket 非 OPEN 或数据超过 3 秒未更新时重建 RX；
4. 控制 socket 非 OPEN 时重建，否则立即发送 PING 复用现有 PONG 超时机制；
5. TX 上下文关闭、麦克风轨道结束时完整重建；仅 socket 失效或发生真实后台/网络恢复时只重建 TX socket，保留麦克风和音频图；
6. 清空旧 RX 缓冲。

`visibilitychange`、`pageshow` 和 `online` 进入同一调度入口。`pagehide`/hidden 只记录页面确实进入过后台。触摸监听同时恢复 RX/TX 的所有非 running、非 closed 上下文，作为 WebKit 用户手势解锁兜底。

### 4. 定时器收敛

控制通道只保留一个 5 秒 PTT 状态查询定时器。心跳调度器保持单例，并让 PONG 超时绑定到发出 PING 的 socket，避免旧超时关闭新连接。

## 安全边界

- 页面隐藏时仍由现有 PTT 安全逻辑立即释放发射，不改变该流程。
- 电源关闭时不执行自动恢复。
- TX socket 重建默认不重新申请麦克风；只有音频上下文关闭或轨道 ended 才完整重建。
- 不修改服务端协议。

## 验证

使用 Node VM 和可控的 WebSocket/AudioContext/定时器替身覆盖：

- 旧 RX socket 延迟 close 不影响新链路；
- OPEN socket 加 closed AudioContext 不被误判健康；
- `interrupted` RX/TX 上下文被调用 resume；
- 连续前台事件共享一次恢复；
- TX socket 可独立重建且保留 MediaHandler；
- 控制心跳和 PTT 查询均只有一个定时器。

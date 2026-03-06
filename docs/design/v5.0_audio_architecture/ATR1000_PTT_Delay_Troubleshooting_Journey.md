# ATR-1000 PTT 发射时功率/SWR 更新延迟问题调试历程

**文档版本**: v1.0  
**日期**: 2026-03-06  
**状态**: 问题未解决，记录调试过程供后续参考

---

## 一、问题背景

### 1.1 现象描述
- **TUNE 模式**：功率/SWR 正常实时更新
- **PTT 发射模式**：功率/SWR 更新延迟严重或完全不更新
- **本地电台操作**：正常实时更新（关键线索！）

### 1.2 系统架构回顾

```
┌─────────────────┐
│  移动端浏览器    │
│ mobile_modern.js│
└────────┬────────┘
         │ WebSocket (/WSATR1000)
         ▼
┌─────────────────┐
│   UHRR 主程序    │
│ WS_ATR1000Handler│
└────────┬────────┘
         │ Unix Socket (/tmp/atr1000_proxy.sock)
         ▼
┌─────────────────┐
│ ATR-1000 代理    │
│ atr1000_proxy.py │
└────────┬────────┘
         │ WebSocket (192.168.1.63:60001)
         ▼
┌─────────────────┐
│  ATR-1000 设备   │
└─────────────────┘
```

---

## 二、调试过程

### 2.1 关键测试：两台 iPhone 对比

**测试方法**：
1. 两台 iPhone 同时连接到 UHRR
2. 一台执行 TUNE，另一台执行 PTT
3. 观察功率/SWR 显示

**测试结果**：
- TUNE 在两台手机上都正常显示
- PTT 在两台手机上都失败

**结论**：问题不是前端 CPU 压力导致，而是后端问题！

### 2.2 本地 vs 远程对比

**关键发现**：
> "这个状态在电台本地（不通过任何远程操作）工作发射的时候，ATR1000的功率和驻波可以实时的同步到各个手机端"

这意味着：
- ATR-1000 代理本身工作正常
- Unix Socket 通信正常
- 问题出在远程 PTT 时 UHRR 主程序的处理逻辑

---

## 三、根因分析

### 3.1 后端代码分析

**文件**: `/Users/cheenle/UHRR/UHRR_mac/UHRR`

**问题代码 1 - 音频处理阻塞**（第 563-575 行）:
```python
def on_message(self, data):
    # ...
    if PYAUDIO_AVAILABLE:
        if hasattr(self, 'audio_playback') and self.audio_playback:
            self.audio_playback.write(data)  # 同步阻塞写入！
            gc.collect()  # 强制垃圾回收，阻塞！
```

**问题代码 2 - ATR-1000 广播线程不安全**（第 1307-1340 行）:
```python
def _broadcast_batch(self, message_batch):
    # 从读取线程调用，直接调用 write_message()
    for client in clients_snapshot:
        client.write_message(latest_data, binary=False)  # 线程不安全！
```

### 3.2 问题链分析

```
远程 PTT 按下
    ↓
WebSocket 接收音频数据
    ↓
audio_playback.write(data)  ← 阻塞！每帧约 20ms
    ↓
gc.collect()  ← 阻塞！触发完整 GC
    ↓
主线程忙于音频处理
    ↓
Tornado IOLoop 事件循环被阻塞
    ↓
WebSocket 消息队列堆积
    ↓
ATR-1000 数据无法及时广播到前端
    ↓
功率/SWR 显示延迟或丢失
```

---

## 四、尝试的修复方案

### 4.1 方案 A：异步音频写入（ThreadPoolExecutor）

**思路**：将 `audio_playback.write()` 放入线程池异步执行

**实现代码**：
```python
from concurrent.futures import ThreadPoolExecutor
audio_executor = ThreadPoolExecutor(max_workers=2)

def on_message(self, data):
    # ...
    if PYAUDIO_AVAILABLE and hasattr(self, 'audio_playback'):
        def async_write():
            self.audio_playback.write(data)
        self.audio_executor.submit(async_write)
```

**结果**：**程序崩溃！**

**崩溃日志**：
```
Thread 14 Crashed::  # 0x0000000104e07c30 libportaudio.dylib`PaUtil_WriteRingBuffer + 48
Thread 0::  Dispatch queue: com.apple.main-thread
  # Pa_CloseStream in progress...
```

**原因**：PyAudio stream 对象 **不是线程安全的**！
- 线程池在写入音频数据
- 主线程同时关闭音频流
- PortAudio 内部状态不一致导致 SIGBUS

**教训**：**永远不要在多线程环境中共享 PyAudio stream 对象！**

### 4.2 方案 B + C：移除 gc.collect() + add_callback 广播

**思路**：
1. 移除每帧的 `gc.collect()` 调用
2. 使用 `IOLoop.add_callback()` 进行线程安全的 WebSocket 广播

**实现代码**：
```python
def _broadcast_batch(self, message_batch):
    # 使用 add_callback 确保在主线程执行
    if self.main_ioloop:
        self.main_ioloop.add_callback(
            lambda: self._do_broadcast_batch(message_batch)
        )

def _do_broadcast_batch(self, message_batch):
    # 在主线程中执行
    for client in clients:
        client.write_message(latest_data, binary=False)
```

**结果**：**TUNE 也失效了！**

**调试发现**：
- `_do_broadcast_batch` 从未被调用
- `main_ioloop` 在某些情况下为 None
- 读取线程退出，显示 "共处理 0 条消息"

**原因**：
1. `main_ioloop` 引用不正确
2. Unix Socket 读取线程的异常处理导致静默退出

---

## 五、最终回滚

所有修改都导致了更严重的问题，最终回滚：

```bash
git checkout UHRR
./uhrr_control.sh restart
```

系统恢复到 V4.5.4 稳定状态。

---

## 六、经验教训

### 6.1 技术教训

| 教训 | 详情 |
|------|------|
| **PyAudio 非线程安全** | PortAudio stream 对象不能跨线程共享，任何尝试都会导致崩溃 |
| **Tornado IOLoop 线程限制** | WebSocket 操作必须在主线程（IOLoop 所在线程）执行 |
| **add_callback 引用问题** | 在子线程中获取正确的 IOLoop 实例需要特别小心 |
| **GC 不应频繁调用** | `gc.collect()` 是重量级操作，不应在音频处理路径中调用 |

### 6.2 调试方法论

| 方法 | 收获 |
|------|------|
| **两设备对比测试** | 排除了前端 CPU 压力假设 |
| **本地 vs 远程对比** | 确认问题在后端音频处理路径 |
| **逐步回滚** | 快速恢复到稳定状态 |
| **崩溃日志分析** | 发现 PyAudio 线程安全问题 |

### 6.3 不要做的修改

1. ❌ 不要用 ThreadPoolExecutor 包装 PyAudio 操作
2. ❌ 不要在音频处理路径调用 `gc.collect()`
3. ❌ 不要从非 IOLoop 线程直接调用 `write_message()`
4. ❌ 不要假设 `IOLoop.current()` 总是返回正确实例

---

## 七、可能的解决方向

### 7.1 短期方案：减少阻塞

```python
# 移除 gc.collect()
# 减少 audio_playback.write 的等待
if hasattr(self, 'audio_playback') and self.audio_playback:
    # 非阻塞写入检查
    frames_to_write = len(data) // 2  # 16-bit samples
    if self.audio_playback.get_write_available() >= frames_to_write:
        self.audio_playback.write(data)
```

### 7.2 中期方案：独立的音频处理进程

```
移动端 WebSocket
    ↓
UHRR 主程序 (控制 + ATR-1000 广播)
    ↓ (独立进程间通信)
音频播放进程 (PyAudio 独立进程)
```

这样音频处理不会阻塞主程序的事件循环。

### 7.3 长期方案：重构音频架构

使用专门的音频中间件（如 PulseAudio/PipeWire）处理音频流，UHRR 只负责控制协议。

---

## 八、当前状态

- **系统版本**: V4.5.4
- **问题状态**: 未解决
- **稳定性**: 恢复稳定
- **功能状态**: 
  - TUNE 功率显示：✅ 正常
  - PTT 功率显示：❌ 延迟/丢失
  - 音频传输：✅ 正常

---

## 九、后续计划

1. 深入研究 Tornado 异步音频处理模式
2. 考虑将音频播放移至独立进程
3. 研究 PortAudio 的回调模式替代阻塞写入
4. 考虑使用 `aiowebsocket` 或其他异步 WebSocket 库

---

**文档维护者**: MRRC 开发团队  
**最后更新**: 2026-03-06

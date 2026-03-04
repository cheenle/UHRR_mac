# ATR-1000 功率/SWR 显示问题分析文档

**创建日期**: 2026-03-03  
**状态**: 已修复代码，待设备验证

---

## 问题描述

手机端在 TX 发射时无法及时显示 ATR-1000 的功率和驻波数据。

**用户反馈**:
- 广播延迟严重（数据更新后 10+ 秒才显示）
- 一次广播多条消息（批量发送，不是 0.5 秒节奏）
- 前端显示不及时

---

## 端到端数据流架构

```
ATR-1000设备 → WebSocket → 后端解析 → 前端WebSocket → 显示更新
    (1)          (2)         (3)          (4)           (5)
```

| 环节 | 描述 |
|------|------|
| (1) 设备→后端 | ATR-1000 通过 WebSocket 发送 METER_STATUS 数据 |
| (2) 后端接收 | Tornado WebSocket 处理二进制数据 |
| (3) 数据解析 | `_parse_meter_data()` 解析 SWR/FWD 功率 |
| (4) 广播 | 通过 `/WSATR1000` WebSocket 发送到前端 |
| (5) 前端显示 | JavaScript 更新 DOM 元素 |

---

## 发现的问题

### 问题 1: 定时器广播导致延迟（旧数据）

**原代码逻辑**:
```python
# _data_request_loop()
time.sleep(0.3)
sync_cmd = bytes([SCMD_FLAG, SCMD_SYNC, 0])
self.ws.send(sync_cmd, opcode=0x02)

# 立即广播 - 但数据还没返回！
self.main_ioloop.add_callback(self._do_broadcast)
```

**问题**: 发送 SYNC 命令后**立即广播**，但设备还没返回数据，广播的是**旧数据**。

### 问题 2: add_callback 积压

**原因**: `add_callback` 会将回调放入 Tornado 主线程队列，多个回调会累积。

**现象**: 
```
16:16:50.809 - 广播完成 (连续20条)
16:16:50.810 - 广播完成
16:16:50.811 - 广播完成
...
```

### 问题 3: 前端重复发送 start/stop

**原因**: TX 按钮事件可能被快速触发多次，导致 `onTXStart/onTXStop` 被重复调用。

**现象** (日志):
```
16:33:16,541 - start 命令
16:33:16,544 - stop 命令  (只过 3ms!)
16:33:16,547 - start 命令
```

---

## 修复内容

### 修复 1: 改为数据驱动广播

**新逻辑**:
```
发送 SYNC 命令
    ↓
设备返回 METER_STATUS
    ↓
_parse_meter_data() 解析数据
    ↓
_schedule_broadcast() 调度广播 ← 新增
    ↓
_do_broadcast() 发送到前端
```

**代码变更** (`UHRR`):
- 移除 `_data_request_loop` 中的立即广播
- 在 `_parse_meter_data()` 中调用 `_schedule_broadcast()`
- 新增 `_schedule_broadcast()` 和 `_do_broadcast_throttled()` 函数

### 修复 2: 广播节流机制

```python
def _schedule_broadcast(self):
    # 如果已有待广播，跳过
    if self._broadcast_scheduled:
        return
    
    current_time = time.time()
    time_since_last = current_time - self.last_broadcast_time
    
    # 最小广播间隔 300ms
    if time_since_last >= self.broadcast_min_interval:
        self.last_broadcast_time = current_time
        self._broadcast_scheduled = True
        self.main_ioloop.add_callback(self._do_broadcast)
    else:
        # 延迟广播
        delay = self.broadcast_min_interval - time_since_last
        self.main_ioloop.call_later(delay, self._do_broadcast_throttled)
```

### 修复 3: 前端防抖

**代码变更** (`mobile_modern.js`):
```javascript
// 添加 _txActive 标志
_txActive: false,

onTXStart: function() {
    // 防抖
    if (this._txActive) {
        console.log('已在 TX 模式，跳过');
        return;
    }
    this._txActive = true;
    // ... 原有逻辑
},

onTXStop: function() {
    // 防抖
    if (!this._txActive) {
        console.log('已在 RX 模式，跳过');
        return;
    }
    this._txActive = false;
    // ... 原有逻辑
}
```

---

## 参数配置

| 参数 | 值 | 说明 |
|------|-----|------|
| SYNC 间隔 | 300ms | 定时发送 SYNC 命令请求数据 |
| 广播间隔 | 300ms | 最小广播间隔，防止过度发送 |
| 广播间隔 | 100ms | 延迟广播间隔（节流时使用） |

---

## 待验证项

### ✅ 代码已修复
- [x] 后端广播逻辑改为数据驱动
- [x] 添加广播节流机制
- [x] 前端添加防抖标志

### ⏳ 待设备验证
- [ ] ATR-1000 设备在线时，手机端 TX 发射能否实时显示功率
- [ ] 广播间隔是否稳定在 300ms
- [ ] 是否还有批量广播问题
- [ ] start/stop 命令是否不再重复发送

### 📋 验证步骤
1. 等待 ATR-1000 设备恢复在线
2. 打开手机端 `mobile_modern.html`
3. 开启 Power 按钮
4. 按住 TX 按钮发射
5. 观察功率/SWR 显示是否实时更新
6. 检查后端日志确认广播节奏

---

## 关键技术点

### ATR-1000 协议
- **SYNC 命令**: `0xFF 0x01 0x00` - 请求设备返回实时数据
- **METER_STATUS**: `0xFF 0x02 [LEN] [SWR(2)] [FWD(2)] [MAXFWD(2)]`
- **SWR 解析**: 如果值 >= 100，需除以 100 (如 101 = 1.01)

### Tornado IOLoop 线程安全
- `add_callback()`: 将回调放入主线程队列（从工作线程调用）
- `call_later()`: 延迟执行回调
- **注意**: 多个 `add_callback` 会累积在队列中，导致批量执行

### WebSocket 二进制帧
- ATR-1000 使用 `opcode=0x02` (二进制帧)
- Python websocket-client 库: `ws.send(data, opcode=0x02)`

---

## 相关文件

| 文件 | 修改内容 |
|------|----------|
| `UHRR` | ATR-1000 代理客户端，添加数据驱动广播 |
| `www/mobile_modern.js` | ATR1000 模块，添加 `_txActive` 防抖 |
| `www/tx_button_optimized.js` | TX 按钮事件处理 |
| `www/mobile_modern.html` | ATR 功率计 UI 元素 |

---

## 历史日志参考

```
# 问题表现
16:16:41,678 - 🔊 广播完成 (连续5条)
16:16:43,776 - 🔊 广播完成 (连续5条)
16:16:50,809 - 🔊 广播完成 (连续20条)

# 修复后预期
16:33:04,850 - 📤 同步命令已发送
16:33:05,173 - 📊 收到数据
16:33:05,174 - 🔊 广播完成 (单条)
```

---

**最后更新**: 2026-03-03

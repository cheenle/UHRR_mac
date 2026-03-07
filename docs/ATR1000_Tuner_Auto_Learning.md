# ATR-1000 天调智能学习与快速调谐

## 概述

ATR-1000 是一款自动天调设备，MRRC 系统实现了与其的深度集成，支持：
- **智能学习**：发射时自动记录频率与天调参数的对应关系
- **快速调谐**：切换频率时自动应用已学习的天调参数
- **实时监测**：发射时实时显示功率和 SWR

## 通信架构

```
┌─────────────────┐
│  移动端浏览器    │
│ mobile_modern.js│
└────────┬────────┘
         │ WebSocket (/WSATR1000)
         ▼
┌─────────────────┐
│   MRRC 主程序    │
│ 频率同步接口     │
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

## 通信协议

### 基本帧格式

ATR-1000 使用二进制 WebSocket 协议，帧格式如下：

```
┌──────┬──────┬──────┬─────────────┐
│ FLAG │ CMD  │ LEN  │ DATA...     │
│ 0xFF │ 1字节│ 1字节│ LEN 字节    │
└──────┴──────┴──────┴─────────────┘
```

- **FLAG**: 固定值 `0xFF`，帧起始标志
- **CMD**: 命令类型（见下表）
- **LEN**: 数据长度
- **DATA**: 命令数据

### 命令类型定义

| 命令 | 值 | 方向 | 说明 |
|------|-----|------|------|
| SCMD_SYNC | 0x01 | 请求 | 同步请求，触发设备返回数据 |
| SCMD_METER_STATUS | 0x02 | 响应 | 功率/SWR 状态 |
| SCMD_RELAY_STATUS | 0x05 | 双向 | 继电器状态（读取/设置） |
| SCMD_START_TUNE | 0x06 | 请求 | 启动自动调谐 |

### 功率/SWR 状态 (0x02)

**响应格式**：`FF 02 0A DATA...`（10 字节数据）

```
偏移:  [3]   [4]   [5]   [6]   [7]   [8]   [9]   [10]  [11]  [12]
数据:  Vf_H  Vf_L  Vr_H  Vr_L  ?     ?     ?     ?     ?     ?
```

**解析方法**：
- 前向电压: `Vforward = (data[3] << 8 | data[4]) / 100.0` (伏特)
- 反射电压: `Vreflected = (data[5] << 8 | data[6]) / 100.0` (伏特)
- 功率计算: `Power = Vforward² / 100` (瓦特，假设 50Ω 负载)
- SWR 计算: `SWR = (Vforward + Vreflected) / (Vforward - Vreflected)`

### 继电器状态 (0x05)

**响应格式**：`FF 05 07 DATA...`（7 字节数据）

```
偏移:  [3]   [4]   [5]   [6]   [7]   [8]   [9]
数据:  SW    ?     CAP   IND   ?     ?     ?
```

**数据解析**（关键修正点）：

| 字段 | 偏移 | 说明 |
|------|------|------|
| SW | data[3] | 网络类型：0=LC，1=CL |
| CAP | data[5] | 电容索引 |
| IND | data[6] | 电感索引 |

**示例数据解析**：

| 原始数据 | data[3] | data[5] | data[6] | SW | L | C |
|----------|---------|---------|---------|-----|------|------|
| `ff05070001090a005a00` | 00 | 09 | 0a | LC | 0.1uH | 90pF |
| `ff050701031b1e000e01` | 01 | 1b | 1e | CL | 0.3uH | 270pF |

**IND/CAP 与实际值转换**：

| 存储值 | 发送值 | 设备显示 |
|--------|--------|----------|
| IND=10 | 10÷10=1 | 0.1uH |
| IND=30 | 30÷10=3 | 0.3uH |
| CAP=9 | 9 | 90pF |
| CAP=27 | 27 | 270pF |

**重要发现**：
- **IND 发送时需要除以 10**：存储值 30 → 发送 3 → 显示 0.3uH
- **CAP 发送时直接使用原值**：存储值 27 → 发送 27 → 显示 270pF
- **SW 字段位置**：`data[3]`，不是 `data[4]`

### 设置继电器命令

**发送格式**：`FF 05 03 SW IND CAP`

```
字节:  [0]  [1]  [2]  [3]  [4]  [5]
数据:  FF   05   03   SW   IND  CAP
```

**参数说明**：
- SW: 网络类型，0=LC，1=CL
- IND: 电感索引（需要除以 10 后发送）
- CAP: 电容索引（直接发送）

**示例**：
```python
# 设置 CL 网络，L=0.3uH，C=270pF
# 存储值: sw=1, ind=30, cap=27
# 发送值: sw=1, ind=3, cap=27
cmd = bytes([0xFF, 0x05, 0x03, 1, 3, 27])
```

### 同步命令 (0x01)

**发送格式**：`FF 01 00`

触发设备返回当前功率和继电器状态。

## 智能学习机制

### 学习条件

发射时自动学习，需满足以下条件：

1. **SWR 良好**：SWR 在 1.0 ~ 1.5 之间
2. **功率足够**：前向功率 > 5W
3. **样本积累**：连续 5 次采样满足条件才记录

### 学习流程

```
开始发射
    │
    ▼
获取当前频率（从 MRRC 同步）
    │
    ▼
每 500ms 采样一次
    │
    ▼
SWR ≤ 1.5 且 Power > 5W?
    │
    ├─ 是 ─→ 累积样本
    │         │
    │         ▼
    │     样本数 ≥ 5?
    │         │
    │         ├─ 是 ─→ 记录/更新天调参数
    │         │
    │         └─ 否 ─→ 继续采样
    │
    └─ 否 ─→ 重置样本计数
    │
    ▼
结束发射
```

### 存储数据结构

```json
{
  "version": "2.0",
  "updated": "2026-03-08T01:10:00",
  "records": [
    {
      "freq": 7050000,
      "sw": 1,
      "ind": 30,
      "cap": 27,
      "swr_avg": 1.08,
      "swr_min": 1.04,
      "swr_max": 1.5,
      "sample_count": 201,
      "last_update": 1772902060.2
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| freq | 频率（Hz） |
| sw | 网络类型：0=LC，1=CL |
| ind | 电感索引（发送时需÷10） |
| cap | 电容索引（直接发送） |
| swr_avg | 平均 SWR |
| swr_min | 最小 SWR |
| swr_max | 最大 SWR |
| sample_count | 采样次数 |

## 快速调谐机制

### 触发时机

1. **频率变化时**：MRRC 主程序检测到频率变化，同步给 ATR 代理
2. **发射开始时**：如果频率有变化，重新查找并应用天调参数

### 匹配算法

```python
def get_tune_params(freq, tolerance=10000):
    """
    根据频率查找天调参数
    
    Args:
        freq: 目标频率（Hz）
        tolerance: 频率容差（Hz），默认 ±10kHz
    
    Returns:
        (sw, ind, cap) 或 None
    """
    for record in records:
        if abs(record['freq'] - freq) <= tolerance:
            return (record['sw'], record['ind'], record['cap'])
    return None
```

### 调谐流程

```
收到频率同步
    │
    ▼
查找存储记录
    │
    ├─ 找到 ─→ 发送继电器设置命令
    │           │
    │           ▼
    │       设备应用参数
    │
    └─ 未找到 ─→ 等待用户手动调谐
```

## 频率同步

### MRRC 主程序接口

```python
def sync_freq_to_atr1000(freq):
    """同步频率给 ATR-1000 代理"""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    sock.connect("/tmp/atr1000_proxy.sock")
    sock.sendall(json.dumps({
        "action": "set_freq",
        "freq": freq
    }).encode())
    sock.close()
```

### 触发点

MRRC 主程序在以下时机同步频率：

1. **getFreq 命令**：客户端请求当前频率时
2. **setFreq 命令**：客户端设置新频率时

```python
# MRRC 主程序中的调用点
elif(action == "getFreq"):
    freq = CTRX.getFreq()
    yield self.send_to_all_clients("getFreq:"+str(freq))
    sync_freq_to_atr1000(freq)  # 同步频率

elif(action == "setFreq"):
    freq = CTRX.setFreq(datato)
    yield self.send_to_all_clients("getFreq:"+str(freq))
    sync_freq_to_atr1000(freq)  # 同步频率
```

## 节流保护机制

为防止频繁操作导致设备重启，实现了节流保护：

```python
def set_relay_with_throttle(atr1000, sw, ind, cap):
    """带节流的继电器设置"""
    global last_relay_params, relay_throttle_time
    
    current_params = (sw, ind, cap)
    current_time = time.time()
    
    # 只在参数变化或超过5秒时才发送
    if (current_params != last_relay_params or 
        current_time - relay_throttle_time > 5):
        atr1000.set_relay(sw, ind, cap)
        last_relay_params = current_params
        relay_throttle_time = current_time
        return True
    return False
```

## API 接口

### WebSocket 命令

前端通过 `/WSATR1000` WebSocket 端点与 ATR 代理通信：

| Action | 参数 | 说明 |
|--------|------|------|
| start | - | 开始数据流（TX 开始时） |
| stop | - | 停止数据流（TX 结束时） |
| set_freq | freq | 同步频率 |
| set_relay | sw, ind, cap | 设置继电器 |
| get_records | - | 获取学习记录 |
| delete_record | freq | 删除指定记录 |

### 示例

```javascript
// 同步频率
ws.send(JSON.stringify({
    action: "set_freq",
    freq: 7050000
}));

// 设置继电器
ws.send(JSON.stringify({
    action: "set_relay",
    sw: 1,      // CL
    ind: 30,    // 存储30，发送3，显示0.3uH
    cap: 27     // 存储27，发送27，显示270pF
}));
```

## 调试日志

### 继电器状态日志

```
🎛️ 继电器原始: ff050701031b1e000e01 | SW=CL, L=30, C=27
```

### 学习日志

```
📝 学习成功: 7050.0kHz, SWR=1.08, CL, L=30, C=27
```

### 调谐日志

```
🎯 快速调谐: 7050.0kHz -> SW=CL, L=30, C=27
```

## 常见问题

### Q: 为什么发送的 IND 值要除以 10？

A: 设备内部协议规定，电感索引与显示值有 10 倍关系：
- 发送值 1 → 显示 0.1uH
- 发送值 3 → 显示 0.3uH

存储时保留原始值（如 30），发送时除以 10。

### Q: SW 字段为什么是 data[3] 而不是 data[4]？

A: 通过对比不同频率的原始数据发现：
- 14MHz (LC): `ff05070001090a005a00` → data[3]=0x00
- 7MHz (CL): `ff050701031b1e000e01` → data[3]=0x01

data[4] 是其他信息，不是网络类型。

### Q: 如何验证天调参数是否正确？

A: 在设备屏幕上确认显示值与存储值对应：
1. 7MHz 频段应显示：CL, L=0.3uH, C=270pF
2. 14MHz 频段应显示：LC, L=0.1uH, C=90pF

### Q: 设备重启怎么办？

A: 检查是否频繁发送继电器命令。节流保护机制：
- 相同参数不重复发送
- 最小发送间隔 5 秒

## 文件清单

| 文件 | 说明 |
|------|------|
| atr1000_proxy.py | ATR-1000 代理主程序 |
| atr1000_tuner.py | 天调存储模块 |
| atr1000_tuner.json | 天调参数存储文件 |
| MRRC | 主程序（含频率同步接口） |

## 版本历史

- **V1.0** (2026-03-08): 初始版本，完成智能学习和快速调谐功能
  - 修正 SW 字段位置：data[4] → data[3]
  - 修正 IND 发送值：需要除以 10
  - 修正 CAP 发送值：直接发送
  - 修正 SW 映射：sw=0 是 LC，sw=1 是 CL

# ATR-1000 天调智能学习与快速调谐

## 概述

ATR-1000 是一款自动天调设备，MRRC 系统实现了与其的深度集成，支持：
- **智能学习**：发射时自动记录频率与天调参数的对应关系
- **快速调谐**：切换频率时自动应用已学习的天调参数
- **实时监测**：发射时实时显示功率和 SWR

## 通信架构

```
┌─────────────────┐     ┌─────────────────┐
│  移动端浏览器    │     │   外部软件/API   │
│ mobile_modern.js│     │  Python/SDR/等   │
└────────┬────────┘     └────────┬────────┘
         │ WebSocket             │ HTTP REST
         │ /WSATR1000            │ :8080
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│   MRRC 主程序    │     │  API Server     │
│ 频率同步接口     │     │ atr1000_api_    │
└────────┬────────┘     │ server.py V2    │
         │              └────────┬────────┘
         │ Unix Socket            │ Unix Socket
         │ /tmp/atr1000_proxy.sock│
         └──────────┬─────────────┘
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

**注意**：MRRC 主程序同时直接控制电台设备（通过 rigctld 控制频率，通过 PyAudio 处理音频 TX/RX），ATR-1000 Proxy 只负责与 ATR-1000 天调设备通信。

**架构说明**：
- **Proxy 是唯一 ATR-1000 设备连接**：所有天调请求通过 Unix Socket 汇聚到 Proxy
- **API Server V2**：不再直接连接设备，改为通过 Proxy 通信
- **减少设备压力**：避免多进程同时连接 ATR-1000 导致挂起

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

## 动态轮询间隔

为避免设备因频繁 SYNC 请求而挂起，实现了动态轮询机制：

| 状态 | 轮询间隔 | 说明 |
|------|----------|------|
| 空闲 | 15秒 | 无客户端连接时 |
| 活跃 | 5秒 | 有客户端连接，保持连接活跃 |
| TX 发射 | 0.5秒 | 发射期间快速更新功率/SWR |

```python
# 动态轮询逻辑
def _poll_loop(self):
    while running and connected:
        if is_tx:
            interval = 0.5      # TX 期间：快速更新
        elif client_count > 0:
            interval = 5.0      # 有客户端：保持连接
        else:
            interval = 15.0     # 空闲：降低压力
        time.sleep(interval)
        self._send_sync()
```

**优化效果**：
- 空闲时设备压力降低 **97%**（从 0.5s → 15s）
- 有客户端时保持连接响应
- TX 期间实时更新不受影响

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

- **V4.9.3** (2026-03-29): 文档全面更新
  - 同步最新功能文档

- **V4.7.0** (2026-03-10): PTT功率显示修复
  - 修复PTT按下时功率/SWR不显示的问题
  - 原因：`tx_button_optimized.js` 未调用 `ATR1000.onTXStart()`
  - 修复：添加 `ATR1000.onTXStart()` 调用，与TUNE保持一致
  - 修复：调整脚本加载顺序，`mobile_modern.js` 先于 `tx_button_optimized.js` 加载
  - 确保ATR1000对象在PTT事件处理前已定义

- **V2.0** (2026-03-08): API Server V2 架构重构
  - API Server 改为通过 Unix Socket 调用 Proxy
  - 避免 API Server 和 Proxy 同时连接设备
  - 实现动态轮询间隔（空闲15s/活跃5s/TX 0.5s）
  - 减少日志输出频率（只在数据变化时记录）
  - 添加 `/api/v1/freq` 端点

- **V1.1** (2026-03-15): 多实例支持更新
  - 配置键大小写修复 (instance_unix_socket)
  - Socket 路径使用 INSTANCE_UNIX_SOCKET 配置

- **V1.0** (2026-03-08): 初始版本，完成智能学习和快速调谐功能
  - 修正 SW 字段位置：data[4] → data[3]
  - 修正 IND 发送值：需要除以 10
  - 修正 CAP 发送值：直接发送
  - 修正 SW 映射：sw=0 是 LC，sw=1 是 CL

---

## 独立 API 服务

ATR-1000 提供独立的 RESTful API 服务，供外部软件调用天调功能。

### V2 架构改进

**V1 问题**：API Server 直接连接设备，与 Proxy 冲突导致设备压力过大

**V2 解决**：API Server 通过 Unix Socket 调用 Proxy，Proxy 作为唯一设备连接

```
V1 (有问题):                    V2 (推荐):
┌──────────┐                   ┌──────────┐
│API Server│──┐                │API Server│──┐
└──────────┘  │    ┌───────┐   └──────────┘  │
              ├───▶│设备   │                ▼ Unix Socket
┌──────────┐  │    └───────┘          ┌──────────┐
│  Proxy   │──┘                       │  Proxy   │──▶ 设备
└──────────┘                          └──────────┘
(两个进程同时连接)                     (唯一设备连接)
```

### 启动方式

```bash
# 前置条件：确保 Proxy 已启动
./mrrc_control.sh start-atr1000

# 启动 API Server（默认端口 8080）
nohup python3 atr1000_api_server.py > atr1000_api.log 2>&1 &

# 自定义端口
python3 atr1000_api_server.py --port 9000

# 自定义 Proxy Socket 路径
python3 atr1000_api_server.py --proxy-socket /tmp/atr1000_proxy.sock
```

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查，包含 Proxy 连接状态 |
| GET | `/api/v1/status` | 获取当前状态（功率、SWR、继电器） |
| GET | `/api/v1/relay` | 获取继电器参数 |
| POST | `/api/v1/relay` | 设置继电器参数 |
| GET | `/api/v1/tuner` | 获取学习记录列表 |
| POST | `/api/v1/tuner` | 手动添加学习记录 |
| DELETE | `/api/v1/tuner` | 删除学习记录 |
| GET | `/api/v1/tuner/lookup` | 根据频率查找参数 |
| POST | `/api/v1/tune` | 执行快速调谐（查找+应用） |
| POST | `/api/v1/freq` | 设置频率（触发自动调谐） |

### 使用示例

**健康检查**
```bash
curl http://localhost:8080/health
# 返回: {"status":"ok","proxy_connected":true,"proxy_socket":"/tmp/atr1000_proxy.sock"}
```

**获取当前状态**
```bash
curl http://localhost:8080/api/v1/status
# 返回: {"success":true,"data":{"power":100,"swr":1.25,"relay":{"sw":1,"ind":30,"cap":27},...}}
```

**设置继电器参数**
```bash
# sw: 0=LC, 1=CL; ind: 电感索引; cap: 电容索引
curl -X POST -H "Content-Type: application/json" \
     -d '{"sw":1,"ind":30,"cap":27}' \
     http://localhost:8080/api/v1/relay
```

**查找天调参数**
```bash
curl "http://localhost:8080/api/v1/tuner/lookup?freq=7050"
# 返回: {"success":true,"found":true,"data":{"sw":1,"sw_name":"CL","ind":30,"cap":28}}
```

**执行快速调谐**
```bash
# 自动查找 7050 kHz 的参数并应用到设备
curl -X POST -H "Content-Type: application/json" \
     -d '{"freq_khz":7050}' \
     http://localhost:8080/api/v1/tune
```

**设置频率**
```bash
# 设置频率（触发自动调谐）
curl -X POST -H "Content-Type: application/json" \
     -d '{"freq_khz":14270}' \
     http://localhost:8080/api/v1/freq
```

**获取学习记录**
```bash
# 所有记录
curl http://localhost:8080/api/v1/tuner

# 按频率筛选
curl "http://localhost:8080/api/v1/tuner?freq=7050&limit=10"
```

**添加学习记录**
```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{"freq_khz":14270,"sw":0,"ind":30,"cap":7,"swr":1.18}' \
     http://localhost:8080/api/v1/tuner
```

**删除学习记录**
```bash
curl -X DELETE "http://localhost:8080/api/v1/tuner?freq=14270"
```

### 响应格式

所有 API 返回 JSON 格式：

**成功响应**
```json
{
  "success": true,
  "data": { ... }
}
```

**错误响应**
```json
{
  "success": false,
  "error": "错误描述"
}
```

### 外部软件集成

API 服务支持 CORS，可从任意域名调用。适合：

- **SDR 软件**：自动获取/设置天调参数
- **日志软件**：记录 SWR 和功率数据
- **自动化脚本**：批量管理天调记录
- **移动应用**：独立控制界面

### Python 调用示例

```python
import requests

API_URL = "http://localhost:8080"

# 健康检查
resp = requests.get(f"{API_URL}/health")
print(resp.json())
# {'status': 'ok', 'proxy_connected': True, ...}

# 获取状态
resp = requests.get(f"{API_URL}/api/v1/status")
print(resp.json())
# {'success': True, 'data': {'power': 0, 'swr': 1.0, ...}}

# 快速调谐
resp = requests.post(f"{API_URL}/api/v1/tune", json={"freq_khz": 7050})
print(resp.json())
# {'success': True, 'found': True, 'applied': True, ...}

# 设置继电器
resp = requests.post(f"{API_URL}/api/v1/relay", json={
    "sw": 1,   # CL
    "ind": 30, # 存储30，显示0.3uH
    "cap": 27  # 存储27，显示270pF
})
print(resp.json())
```

### 命令行工具集成

```bash
#!/bin/bash
# quick_tune.sh - 快速调谐脚本

FREQ=$1
API="http://localhost:8080"

if [ -z "$FREQ" ]; then
    echo "用法: $0 <频率kHz>"
    exit 1
fi

echo "调谐到 ${FREQ} kHz..."
curl -s -X POST -H "Content-Type: application/json" \
     -d "{\"freq_khz\":$FREQ}" \
     "$API/api/v1/tune" | python3 -m json.tool
```

# MRRC API 接口文档

> 基于 Vibe-SDD 方法论的API设计

---

## 1. WebSocket API

### 1.1 控制命令接口

#### 频率设置

| 属性 | 值 |
|------|-----|
| 方法 | WebSocket |
| 端点 | /WSMRRC |
| 方向 | 双向 |

**请求**:
```json
{"action": "setFreq", "data": "7074000"}
```

| 字段 | 类型 | 描述 |
|------|------|------|
| action | string | "setFreq" |
| data | string | 频率 (Hz) |

**响应**:
```json
{"action": "getFreq", "data": "7074000"}
```

#### 模式设置

**请求**:
```json
{"action": "setMode", "data": "USB"}
```

| 字段 | 类型 | 描述 |
|------|------|------|
| action | string | "setMode" |
| data | string | 模式: USB/LSB/CW/AM/FM/CWR |

**响应**:
```json
{"action": "getMode", "data": "USB"}
```

#### PTT控制

**请求**:
```json
{"action": "ptt", "data": true}
```

| 字段 | 类型 | 描述 |
|------|------|------|
| action | string | "ptt" |
| data | boolean | true=发射, false=接收 |

**响应**:
```json
{"action": "ptt", "data": true, "status": "ok"}
```

#### TUNE控制

**请求**:
```json
{"action": "tune", "data": true}
```

| 字段 | 类型 | 描述 |
|------|------|------|
| action | string | "tune" |
| data | boolean | true=开始调谐, false=停止 |

#### 获取频率

**请求**:
```json
{"action": "getFreq"}
```

**响应**:
```json
{"action": "getFreq", "data": "7074000"}
```

#### 获取S表

**请求**:
```json
{"action": "getSMeter"}
```

**响应**:
```json
{"action": "getSMeter", "data": "-73", "rx": true}
```

---

### 1.2 ATR-1000接口

#### 功率/SWR同步

**请求**:
```json
{"action": "atr_sync"}
```

**响应**:
```json
{
  "action": "atr_status",
  "data": {
    "power": 50,
    "swr": 1.2,
    "sw": "LC",
    "ind": 10,
    "cap": 27
  }
}
```

#### 手动设置继电器

**请求**:
```json
{"action": "atr_set_relay", "data": {"sw": 1, "ind": 30, "cap": 27}}
```

| 字段 | 类型 | 描述 |
|------|------|------|
| sw | int | 网络类型: 0=LC, 1=CL |
| ind | int | 电感值 (除10) |
| cap | int | 电容值 |

#### 获取学习记录

**请求**:
```json
{"action": "atr_get_records"}
```

**响应**:
```json
{
  "action": "atr_records",
  "data": [
    {"freq": 7070000, "sw": 1, "ind": 30, "cap": 27, "swr_avg": 1.08}
  ]
}
```

---

### 1.3 WDSP控制接口

#### 设置NR2

**请求**:
```json
{"action": "wdsp_nr2", "data": true}
```

#### 设置NB

**请求**:
```json
{"action": "wdsp_nb", "data": true}
```

#### 设置ANF

**请求**:
```json
{"action": "wdsp_anf", "data": true}
```

#### 设置AGC

**请求**:
```json
{"action": "wdsp_agc", "data": 3}
```

| 值 | 模式 |
|----|------|
| 0 | OFF |
| 1 | LONG |
| 2 | SLOW |
| 3 | MED |
| 4 | FAST |

---

### 1.4 音频接口

#### TX音频帧

| 属性 | 值 |
|------|-----|
| 方法 | WebSocket Binary |
| 格式 | Int16 LE |
| 采样率 | 16kHz |
| 帧大小 | 320 samples |

#### RX音频帧

| 属性 | 值 |
|------|-----|
| 方法 | WebSocket Binary |
| 格式 | Int16 LE |
| 采样率 | 16kHz |
| 帧大小 | 320 samples |

---

## 2. HTTP API

### 2.1 静态资源

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | / | 主界面 |
| GET | /mobile_modern.html | 移动端界面 |
| GET | /controls.js | 控制脚本 |
| GET | /mobile_modern.js | 移动端脚本 |
| GET | /mobile_modern.css | 移动端样式 |

### 2.2 服务端状态

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | /status | 服务器状态 |

**响应**:
```json
{
  "status": "running",
  "version": "V4.9.1",
  "clients": 2,
  "ptt": false,
  "freq": 7074000,
  "mode": "USB"
}
```

---

## 3. 错误码

### 3.1 通用错误

| 码 | 含义 | 处理方式 |
|----|------|----------|
| 400 | 请求错误 | 返回详细错误信息 |
| 401 | 未认证 | 引导登录 |
| 403 | 无权限 | 权限不足提示 |
| 404 | 不存在 | 返回友好提示 |
| 500 | 服务器错误 | 记录日志 |

### 3.2 WebSocket错误

| 码 | 含义 | 处理方式 |
|----|------|----------|
| W1000 | 未知错误 | 断开连接 |
| W1001 | 客户端断开 | 清理资源 |
| W1002 | 协议错误 | 断开连接 |

---

## 4. ATR-1000协议

### 4.1 帧格式

```
┌──────┬──────┬──────┬─────────────┐
│ FLAG │ CMD  │ LEN  │ DATA...     │
│ 0xFF │ 1字节│ 1字节│ LEN 字节    │
└──────┴──────┴──────┴─────────────┘
```

### 4.2 命令类型

| 命令 | 值 | 方向 | 说明 |
|------|-----|------|------|
| SYNC | 0x01 | 请求 | 触发设备返回数据 |
| METER_STATUS | 0x02 | 响应 | 功率/SWR 状态 |
| RELAY_STATUS | 0x05 | 双向 | 继电器状态 |
| START_TUNE | 0x06 | 请求 | 启动自动调谐 |

### 4.3 METER_STATUS解析

```
偏移:  [3]   [4]   [5]   [6]
数据:  PFH  PFM  PFL  SWRH  SWRL

PF = Power Forward (前向功率)
SWR = Standing Wave Ratio (驻波比)
```

**计算公式**:
- Power = (PFH << 8) | PFL
- SWR = ((SWRH << 8) | SWRL) / 100

---

**文档信息**
- 版本: 1.0
- 创建日期: 2026-03-15
- 最后更新: 2026-03-15
- 作者: MRRC Team

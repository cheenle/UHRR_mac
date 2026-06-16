# MRRC 系统上下文

> 基于 Vibe-SDD 方法论的系统上下文图和外部实体

---

## 1. 系统上下文图

```mermaid
graph TB
    subgraph 用户层
        HAM[业余无线电爱好者]
        Browser[Web浏览器]
        Mobile[移动设备]
    end

    subgraph MRRC系统
        WebServer[Tornado Web服务器]
        WSHandler[WebSocket处理器]
        AudioTX[TX音频处理]
        AudioRX[RX音频处理]
        DSP[WDSP降噪]
        ATRProxy[ATR-1000代理]
        VoiceAI[语音助手服务]
        CWDecoder[CW解码器]
    end

    subgraph 外部系统
        Rigctld[Hamlib rigctld]
        Radio[电台设备 IC-7100/IC-9000]
        ATR1000[ATR-1000天调]
        Internet[互联网]
    end

    HAM -->|HTTPS/WSS| Internet
    Mobile -->|HTTPS/WSS| Internet
    Internet --> WebServer
    WebServer --> WSHandler
    WSHandler -->|频率/模式/PTT| Rigctld
    Rigctld -->|Cat控制| Radio
    WSHandler --> AudioTX
    AudioTX --> DSP
    DSP -->|音频流| Radio
    Radio -->|音频流| AudioRX
    AudioRX --> DSP
    DSP --> WSHandler
    WSHandler -->|WSS| Browser
    WSHandler -->|WSS| Mobile
    ATRProxy -->|WebSocket| ATR1000
    WSHandler -->|Unix Socket| ATRProxy
    VoiceAI -->|gRPC| WSHandler
    CWDecoder -->|推理| WSHandler
```

---

## 2. 外部实体说明

### 2.1 用户 (User)

| 实体 | 描述 | 接口 |
|------|------|------|
| HAM | 业余无线电爱好者 | HTTPS/WSS |
| Mobile | 移动端用户 | HTTPS/WSS |

**职责**:
- 发起控制请求
- 提供麦克风输入
- 接收音频输出
- 查看仪表显示

### 2.2 电台 (Radio)

| 实体 | 描述 | 接口 |
|------|------|------|
| IC-7100 | Icom业余电台 | USB Cat控制 |
| IC-R9000 | Icom接收机 | USB Cat控制 |
| 其他电台 | Hamlib支持 | 串口/USB |

**职责**:
- 频率/模式控制
- 音频输入/输出
- PTT控制
- S表数据提供

### 2.3 天调 (ATR-1000)

| 实体 | 描述 | 接口 |
|------|------|------|
| ATR-1000 | 自动天调 | WebSocket |

**职责**:
- 功率测量
- SWR监测
- 自动调谐
- 存储学习参数

### 2.4 Hamlib

| 实体 | 描述 | 接口 |
|------|------|------|
| rigctld | Hamlib守护进程 | TCP:4532 |

**职责**:
- 电台控制协议转换
- 频率/模式同步
- S表数据读取

---

## 3. 数据流设计

### 3.1 控制数据流

```mermaid
sequenceDiagram
    participant U as 用户
    participant W as Web服务器
    participant R as rigctld
    participant Radio

    U->>W: setFreq: 7074000
    W->>R: F 7074000\n
    R->>Radio: Cat命令
    Radio-->>R: 确认
    R-->>W: OK
    W-->>U: getFreq:7074000
```

### 3.2 TX音频数据流

```mermaid
sequenceDiagram
    participant M as 麦克风
    participant B as 浏览器
    participant W as Web服务器
    participant D as WDSP
    participant R as 电台

    M->>B: 48kHz PCM
    B->>B: 降采样16kHz
    B->>B: Int16编码
    B->>W: WebSocket帧
    W->>D: NR2降噪
    D->>R: 音频输出
```

### 3.3 RX音频数据流

```mermaid
sequenceDiagram
    participant R as 电台
    participant W as Web服务器
    participant D as WDSP
    participant B as 浏览器
    participant S as 扬声器

    R->>W: 48kHz PCM
    W->>D: NR2降噪
    D->>W: 48kHz处理后
    W->>B: WebSocket帧
    B->>B: 解码
    B->>B: 升采样48kHz
    B->>S: 播放
```

### 3.4 ATR-1000数据流

```mermaid
sequenceDiagram
    participant B as 浏览器
    participant W as Web服务器
    participant A as ATR代理
    participant ATR as ATR-1000

    B->>W: sync
    W->>A: forward
    A->>ATR: SYNC命令
    ATR-->>A: 功率/SWR数据
    A-->>W: JSON数据
    W-->>B: 功率/SWR显示
```

---

## 4. 边界接口定义

### 4.1 用户接口 (User Interface)

| 接口 | 协议 | 描述 |
|------|------|------|
| Web界面 | HTTPS | 静态HTML/CSS/JS |
| 控制API | WSS | JSON格式控制命令 |
| 音频流 | WSS | 二进制音频帧 |

**接口格式**:

```json
// 控制命令
{"action": "setFreq", "data": "7074000"}
{"action": "setMode", "data": "USB"}
{"action": "ptt", "data": true}

// 响应
{"action": "getFreq", "data": "7074000"}
{"action": "getMode", "data": "USB"}
```

### 4.2 电台接口 (Radio Interface)

| 接口 | 协议 | 描述 |
|------|------|------|
| Cat控制 | 串口/USB | Icom CI-V协议 |
| 音频输入 | 3.5mm | 电台AF输出 |
| 音频输出 | 3.5mm | 电台MIC输入 |
| PTT控制 | 电台ACC | 发射控制 |

### 4.3 ATR-1000接口

| 接口 | 协议 | 描述 |
|------|------|------|
| 控制 | WebSocket | JSON帧格式 |
| 端口 | TCP:60001 | 网络连接 |

---

## 5. 安全性边界

```mermaid
graph TB
    subgraph 外部网络
        User[用户设备]
    end

    subgraph 边界防火墙
        TLS[TLS终止]
    end

    subgraph DMZ
        Web[Tornado服务器]
    end

    subgraph 内部网络
        Audio[音频处理]
        DSP[WDSP处理]
        Hamlib[rigctld]
    end

    subgraph 硬件层
        Radio[电台]
        ATR[ATR-1000]
    end

    User -->|HTTPS/WSS| TLS
    TLS --> Web
    Web --> Audio
    Audio --> DSP
    DSP --> Hamlib
    Hamlib --> Radio
    Web -->|Unix Socket| ATR
```

**安全措施**:
- TLS 1.2+ 加密传输
- 用户认证 (密码/证书)
- 防火墙端口限制
- Unix Socket进程隔离

---

**文档信息**
- 版本: 1.0
- 创建日期: 2026-03-15
- 最后更新: 2026-03-15
- 作者: MRRC Team

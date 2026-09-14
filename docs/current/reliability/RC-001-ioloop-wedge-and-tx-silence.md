# RC-001：IOLoop 楔死致端口无响应 + 蓝牙 DAC 抖动致 TX 静默发射

> **元信息**
> - 日期：2026-09-14（上午 08:12 首次报告）
> - 影响版本：V6.0.1 及之前（修复合入 V6.0.2）
> - 影响实例：`radio1`（IC-M710，HTTPS/WSS 端口 8891，macOS 主机）
> - 严重级别：可用性（高）+ 发射安全（中，见 §5）
> - 修复标记：F4（异步初始化 + 看门狗 + 日志轮转）、F4b（帧缓存 + 丢弃强制释放 PTT + 设备缓存 + 耗时打点）
> - 关联文档：`CHANGELOG.md` V6.0.2、`docs/legacy/audio/PTT_Audio_Postmortem_and_Best_Practices.md`

---

## 1. 现象与时间线

### 1.1 三个阶段

本次问题分两期暴露，修复也分两轮落地：

**第一期（端口假死）**：08:12 左右，web 界面（8891 端口）突然完全无响应——页面打不开、WebSocket 全断、PTT 无反应。但 SSH 到主机上查进程，MRRC **活着**，CPU 正常，音频捕获线程照常跑。重启后恢复。当天早上重复出现数次，用户多次手动重启。

**第二期（TX 间歇静默）**：F4 修复上线后端口不再假死，但用户报告"还是卡"——按 PTT 电台正常发射，**有时**对面听不到任何声音。日志上看一切正常：每次 PTT 都打印 `PyAudio output stream opened successfully`，无任何报错。

### 1.2 关键时间线（2026-09-14）

| 时间 | 事件 |
|------|------|
| 08:12:52–55 | 旧实例（PID 4835）在 AUHAL `SelectDevice` 中消失——卡死在打开音频输出流 |
| 08:13:43 | 用户手动重启（`mrrc_multi.sh restart radio1`），旧日志被启动脚本截断 |
| 08:52 / 09:01 | F4 修复后的两个实例：端口零故障，但 TX 静默间歇出现 |
| 09:20:54 | 触发一次"初始化完成后用户已松手"丢弃事件（0.3s 发射，ATR 记录） |
| 10:24–10:28 | 用户测试 5 次发射：2 次正常调制（126–153W），2 次完全静默（平坦 6–7W） |
| 10:40–10:45 | `bluetoothd` 爆发 `Jitter Buffer … error 312`（蓝牙 DAC 抖动） |
| 11:23 | 断开蓝牙 DAC（PCM1794X2 BT5.1） |
| 11:25–11:28 | 同样设备、同样操作连续 11 段发射，**全部正常调制**（111–133W 为主） |
| 11:28:57 | 重启加载 F4b；此后 jitter error 零复发 |

---

## 2. 根因分析（端到端因果链）

### 2.1 完整因果链

```
蓝牙 DAC（系统默认输出，杂牌固件 255.15.15）
  → 系统声/浏览器音频频繁触发 A2DP 流启动
  → 每次启动时 DAC 不应答 macOS 的 Jitter Buffer 配置（L2CAP control cmd 0x0B，error 312）
  → bluetoothd 反复重协商（AVDTP 信令风暴）
  → CoreAudio HAL 全局阻塞（任何设备的音频操作都被拖住）
  → MRRC 按 PTT 时 PyAudioPlayback.__init__ 的 p.open() 被拖慢 0.3s~15s+
      ├─ 一期：该调用跑在 Tornado IOLoop 线程上 → 事件循环整体楔死 → 8891 端口假死
      └─ 二期（F4 后改到工作线程）：端口保住了，但阻塞期间 TX 音频帧被静默丢弃
          → 电台已键控、全程发射无调制载波（SSB 无语音时仅 ~6-7W 馈通）
          → 用户体感"PTT 有时好有时卡"
```

叠加因素：Mac 主机当时在 **2.4GHz Wi-Fi**（Ch1）上，与蓝牙同频段竞争（路由器有 5GHz 可用）。

### 2.2 一期根因：阻塞调用跑在 IOLoop 线程

按 PTT 时浏览器向 `/WSaudioTX` 发 `m:` 初始化消息，调用链：

- `WS_AudioTXHandler.on_message`（IOLoop 线程）→ `TX_init` → `PyAudioPlayback(...)`
- 构造函数内同步执行 `pyaudio.PyAudio()` + 设备枚举 + `p.open()`（`audio_interface.py`）

项目此前已按同样模式修过两处，唯独漏了构造函数：

| 修复 | 内容 | 位置 |
|------|------|------|
| F2 | `stream.write()` 挪到专用 writer 线程，永不阻塞 IOLoop | `audio_interface.py` `PyAudioPlayback` |
| F3 | rigctld 阻塞 I/O（最长 ~9s）挪到线程执行器 | `MRRC` `setPTT` / `on_message` |
| **F4（本次）** | **构造 + `p.open()` 挪到执行器** | `MRRC` `_start_tx_init_async` |

证据：unified log 中旧实例最后的活动停在 `p.open` 内部的 AUHAL `SelectDevice`（设备 101→113 切换，08:12:55），之后进程安静直到被杀——进程活着、端口死掉、无崩溃报告、无内存压力事件，符合"IOLoop 线程被同步调用楔死"的全部特征。

### 2.3 二期根因：阻塞窗口内 TX 帧被静默丢弃

F4 把 `p.open()` 挪到工作线程后，端口问题根治，但暴露第二段因果：

- `p.open()` 阻塞期间，浏览器的 TX 音频帧照常到达（50 帧/秒）
- `on_message` 音频分支判断 `self.audio_playback` 还没赋值 → **静默丢弃**，无日志
- 阻塞多久，就静默多久；阻塞超过用户按住 PTT 的时长，整段发射无声

**关键判定证据**（排除客户端/服务端其他环节）：
- 5 秒无帧的 `stoppttontimeout` 保护从未触发 → 帧全程都在到达
- `write()`/writer 线程所有错误分支（`TX normalize error`、`TX stream write error`）零打印 → 到达的帧被无错消费
- ATR-1000 功率计：静默段平坦 6–7W（SSB 无调制），正常段 126–153W 剧烈摆动

### 2.4 环境根因：蓝牙 DAC 的 A2DP 协商失败

- 设备：`PCM1794X2 BT5.1`（地址 `53:4A:52:FE:00:2D`，A2DP+AVRCP，Vendor ID 0x000A，固件 255.15.15）
- 它是 **macOS 系统默认输出设备** → 系统提示音/浏览器音频频繁拉起 A2DP 流
- `bluetoothd` 日志反复出现：`Failed to send Jitter Buffer (control cmd 0x0B) as 150 ms … error 312` / `Failed to configure jitter buffer to 0x96 with error 312` → DAC 固件不应答抖动缓冲配置 → 重协商风暴
- 每个 AVDTP 协商窗口 CoreAudio 全局阻塞，USB Audio CODEC 的 `p.open` 被拖慢（蓝牙设备即使不是目标设备也拖住整个 HAL）

**A/B 验证**：11:23 断开 DAC 后——
- `Jitter Buffer error 312` 自 10:45:33 起零复发（44 分钟观察窗覆盖整个复测）
- 11:25–11:28 连续 11 段发射全部正常调制（111–133W 为主，仅 25 个 7W 无语音间隙读数）
- 输出设备列表 5→4，系统默认输出自动切到显示器音箱

---

## 3. 修复措施

### 3.1 F4（一期，MRRC + mrrc_multi.sh）

1. **TX 初始化异步化**：`m:` 消息 → `_start_tx_init_async()` → `run_in_executor` 工作线程执行 `TX_init`；构造期间重复 `m:` 直接丢弃
2. **取消竞态**：`s:`/`on_close` 置 `_tx_init_cancel`，工作线程完成后不补键 PTT（安全关键）
3. **广播线程安全**：`TX_init` 内 PTT 广播改经 `MAIN_IOLOOP.add_callback`（`write_message` 非线程安全）
4. **IOLoop 假死看门狗** `arm_ioloop_watchdog()`：2s 心跳、晚于预定 8s 即判定假死，`faulthandler.dump_traceback` 打印全部线程栈，30s 冷却；`HTTP server started.` 后武装
5. **日志轮转**：`mrrc_multi.sh` 启动时 `> 日志` 改为先 `mv` 为 `.prev`——本次事故的第一份死亡现场即被启动脚本截断，无法考证；`delete` 命令同步清理 `.prev`

### 3.2 F4b（二期，MRRC + audio_interface.py）

1. **初始化期帧缓存**：`p.open` 阻塞期间到达的帧进 `_tx_pending_frames`（上限 250 帧≈5s，超出丢最旧），初始化完成后补放——慢也只延迟，不再静默
2. **丢弃路径强制释放 PTT**：覆盖"s: 先处理完、工作线程后补键"的乱序竞态（该漏洞若不堵，极端时序下电台会滞留发射，靠 5s 超时/TOT 兜底）
3. **输出设备索引缓存**：每次按 PTT 全量枚举 6+ 设备（抖动期每次 CoreAudio 查询可阻塞数百 ms）降为缓存命中 1 次校验（名称+输出通道不符才全量枚举）
4. **耗时打点**：`⏱️ TX audio init: 枚举 X.XXs, p.open X.XXs` 进日志，持续量化

### 3.3 环境处置（当前状态）

- 蓝牙 DAC 断开为常态；听音乐时手动连接，不听时断开（连着就持续制造协商噪音）
- 未动系统设置：默认输出、Wi-Fi 保持原样（用户决策"维持现状观察"）

---

## 4. 验证方法

### 4.1 本次使用的判定手段（都可复用）

| 手段 | 用法 |
|------|------|
| ATR-1000 功率计 | **SSB 调制判据**：读数在 1–150W 间剧烈摆动=有调制；平坦 6–7W=无调制（静默发射）。比任何软件日志都直接 |
| `stoppttontimeout` 反证 | 5s 无帧自动收 PTT；若长时间发射未触发，说明帧一直在到达 |
| unified log | `log show --predicate 'process=="bluetoothd" AND eventMessage CONTAINS[c] "Jitter Buffer"'` 看协商错误；`eventMessage CONTAINS[c] "audio start condition"` 看 A2DP 拉起频率 |
| IOLoop 看门狗 | `🚨 IOLoop stall` + 全线程栈；两个新实例零触发即一期根治 |
| ⏱️ 打点 | 每次 PTT 的 `枚举/p.open` 分段耗时；预期 <0.2s，>2s 说明抖动回归 |
| `.prev` 日志 | 重启后第一份死亡现场；`mrrc_radio1.log.prev` 尾部即上一实例临终状态 |

### 4.2 复测数据摘要

- F4 后两实例（08:52–11:28）：`🚨` 零触发；getPTT 轮询全程连续
- DAC 断开前：5 次测试中 2 次全程无调制（10:24:18、10:28:15）
- DAC 断开后：11 段发射全部调制正常（11:25–11:28），`error 312` 零复发

---

## 5. 安全影响分析

| 风险 | 严重度 | 处置 |
|------|--------|------|
| 端口假死期间无法收 PTT/无法控制电台 | 中（可用性） | F4 根治 |
| **静默发射**：用户以为在通话，实际发射无调制载波数秒~十几秒（占用频率、空发） | 中 | F4b 帧缓存根治；ATR 功率计可事后发现 |
| **PTT 滞留**（丢弃竞态未修前）：松手后电台被补键滞留发射，最长靠 `stoppttontimeout`（5s）/ TOT 硬上限兜底 | 中高（安全） | F4b 丢弃路径强制释放 PTT |
| 发射中无 PTT 超时保护误触发 | 无 | `stoppttontimeout` 全程未误动 |

既有安全设计在本案中按预期工作：`setPTT` 的方向感知状态机（R3，释放失败绝不乐观置 False）、PTTSafetyMonitor 后台重试与 TOT、5s 无帧自动收 PTT。

---

## 6. 经验教训（模式沉淀）

1. **"IOLoop 线程零阻塞"是纪律不是一次性修复**。F2 修了 write、F3 修了 rigctld、漏了构造函数——同类问题应按"枚举所有在 IOLoop 线程上的阻塞点"排查，而不是等事故补洞。看门狗（心跳延迟检测）是这类问题的通用探针，应永久在线。
2. **异步化会移动 bug，不会消灭 bug**。把 `p.open` 挪出 IOLoop 后，阻塞从"端口假死"变成"帧静默丢弃"——改动阻塞点时，必须同时问"阻塞窗口内到达的数据/事件去哪了"。
3. **环境设备可以毒害全局音频子系统**。杂牌蓝牙音频设备作为系统默认输出时，其协商失败会拖住 CoreAudio 中**所有**设备（包括无关的 USB 声卡）。macOS 上排查音频卡顿应先查 `bluetoothd` 错误，再查自己的代码。
4. **日志可观测性先于根因**。本次三份关键证据（线程栈、分段耗时、临终日志）分别来自看门狗、⏱️ 打点、`.prev` 轮转——全部是事故发生后补的观测手段。阻塞类操作一律加耗时打点，服务重启一律保留旧日志。
5. **单文件混写 stdout/stderr 会撒谎**。print（stdout 块缓冲）与 logging（stderr 行缓冲）交错时，行顺序不代表真实时序；跨线程的 print 顺序也只是近似。判定时序要依赖带时间戳的日志（logging/ATR/unified log）。
6. **TX 是否正常，功率计是最短真相路径**。软件链路每层都"正常"而对面听不到时，发射功率读数一眼定性。

## 7. 排查工具箱（速查）

```bash
# IOLoop 假死/线程栈
grep "🚨\|IOLoop stall\|watchdog armed" mrrc_radio1.log

# TX 初始化耗时（F4b 起每次 PTT 都有）
grep "⏱️\|📦\|discarding" mrrc_radio1.log

# 上一实例临终现场
tail -50 mrrc_radio1.log.prev

# 蓝牙 A2DP 协商错误（DAC 抖动探针）
log show --last 1h --predicate 'process == "bluetoothd" AND eventMessage CONTAINS[c] "Jitter Buffer"' --style compact

# 当前音频输出设备/默认输出
SwitchAudioSource -c; SwitchAudioSource -a -t output

# ATR 发射段与功率
grep "TX模式开始\|TX模式结束" atr1000_radio1.log
grep "功率/SWR" atr1000_radio1.log | tail -50
```

蓝牙控制注意：macOS TCC 把蓝牙权限归到**发起操作的 App 本体**（本案例中是 `kimi` 进程而非 Terminal），`sudo` 与 `BLUEUTIL_ALLOW_ROOT=1` 均不能绕过；`blueutil` 被拒的典型表现是"看到空设备列表/报 power off"。

## 8. 后续监控与决策触发线

- 日常：`grep "⏱️" mrrc_radio1.log` 应稳定在 0.2s 内；出现 `📦` 行说明 F4b 补放生效（偶发可接受，频繁说明慢到影响操作）
- `⏱️` 中 p.open 经常 >2s → 先切 5GHz Wi-Fi（成本最低）
- 确认要长期通过蓝牙 DAC 听电台 → MRRC 网页加 `AudioContext.setSinkId` 输出选择器，电台音频固定走指定声卡，与系统默认输出解耦
- 出现 `🚨 IOLoop stall` → 日志内附全线程栈，直接定位阻塞调用点

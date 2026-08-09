# ATR-1000 SWR>2 自动完整调谐 — 设计文档

日期: 2026-08-09
状态: 已确认（用户批准）

## 背景与诊断结论

用户要求：检查 ATR 天调自动学习/自动更新是否正常；并在「当前参数配置 SWR > 2」时自动触发 ATR-1000 完整调谐。

### 诊断结果（基于运行日志 atr1000_radio1.log、通讯日志 atr1000_comm.log、atr1000_tuner.json）

1. **自动更新/自动调谐（set_freq 应用存储参数）— 正常**。日志确认频率切换时自动应用存储的天调参数（如 12:20 21074kHz → LC L=0 C=15；12:34 28074kHz → SW=0 L=3 C=6）。链路：MRRC `FrequencySyncThread` → Unix socket → proxy `set_freq` → `set_relay_with_throttle`。

2. **自动学习 — 机制完好但当前运行实例未在学习**：
   - 存储文件有历史积累（7050kHz 557 次采样），最后写盘为今天 07:38（重启前）。
   - 代理进程 07:50 启动后，运行日志中零次「学习成功」。
   - 用当前磁盘代码模拟 08:02 那次发射（350–459W、SWR 1.01–1.03，条件达标），**代码能正确触发学习并写盘**。
   - 运行中的代理（07:50 启动）对同样数据未学习 → 疑为运行实例加载旧代码或存在运行时状态问题。**建议重启代理后用当前代码重新观察。**

3. **观察到的其它情况**：
   - 12:18–12:23 发射功率仅 2W，低于学习阈值 5W，该段不学习属正常。
   - 学习依赖前端/MRRC 发送的 TX「start」信号（`is_tx`）。09:45 后未再收到 start，故 12:18 的 38–41W 真实发射也未学习。属设计局限：非 MRRC 路径发射（电台直接 PTT / 外部软件）会静默失效。

### 对本设计的影响

- SWR 守卫采用**实测功率判定**发射中（非 is_tx），天然覆盖非 MRRC 路径发射场景。
- SWR 守卫需**独立于学习门控**，但仍复用 `cache["tuning"]` 标志避免调谐期间重复触发。

## 设计目标

发射期间持续实时监测 SWR；当 SWR 严格大于 2.0、持续 ≥1.5s 且不在调谐/冷却期时，自动发送一次 ATR-1000 **完整调谐（mode=2）**。同一频率连续 3 次自动调谐仍不达标则放弃，直到频率变化或 SWR 好转。

## 组件

全部实现于 `atr1000_proxy.py`，沿用现有模块级全局状态模式。

### 1. 新常量（置于现有学习常量旁）

```python
SWR_RETUNE_THRESHOLD     = 2.0   # SWR 严格大于此值视为过高
SWR_RETUNE_MIN_POWER     = 10    # 实测功率 ≥10W 视为发射中（过滤空闲/调谐扫描的 1–2W）
SWR_RETUNE_DEBOUNCE      = 1.5   # SWR>2 持续 ≥1.5s 才触发（约 10 个采样）
SWR_RETUNE_COOLDOWN      = 30    # 两次自动完整调谐最小间隔（秒）
SWR_RETUNE_MAX_FAILS     = 3     # 同一频率连续失败次数上限
```

### 2. 模块级状态

```python
_swr_high_since   = 0      # 高 SWR 连续起点时间戳（0=不在连续段）
_last_retune_time = 0      # 上次自动调谐时间戳（冷却）
_retune_fail_count = {}    # freq_key → 连续失败次数
```
并发：`_parse_data` 运行于 WebSocket 消息线程，unix-socket 线程并发写 cache。对上述状态的读写用 `state_lock`（已存在）保护 read-modify-write。

### 3. 核心函数 `_check_swr_retune(atr1000, power, swr)`

调用位置：`_parse_data` 的 METER 处理路径、`cache_lock` 之外的「锁外学习区」旁（避免持锁期间执行 start_tune 网络 I/O）。

```
跳过条件（任一满足即重置连续段并 return）:
  - cache["tuning"] 为 True（调谐中）
  - power < SWR_RETUNE_MIN_POWER
  - swr <= SWR_RETUNE_THRESHOLD → 同时清零该频率失败计数（当前匹配可接受）
  - 继电器变化后 1s 忽略窗口内（复用 LEARN_IGNORE_WINDOW）
  - 频率无效（cache["freq"] <= 0）

失败保护：_retune_fail_count[freq_key] >= SWR_RETUNE_MAX_FAILS
  → 记 INFO 日志「已放弃自动调谐（3次）」，return（不触发）

首次进入连续段（_swr_high_since == 0）→ 置 _swr_high_since = now

触发条件（全部满足）:
  - now - _swr_high_since >= SWR_RETUNE_DEBOUNCE
  - now - _last_retune_time >= SWR_RETUNE_COOLDOWN
  → with cache_lock:
      cache["tuning"]=True; cache["tuning_started_at"]=now
      cache["tuning_relay_stable_since"]=0
      _retune_fail_count[freq_key] += 1
    atr1000.start_tune(2)          # 完整调谐，锁外执行
    _last_retune_time = now; _swr_high_since = 0
    INFO 日志「⚡ SWR>2 自动触发完整调谐 (freq, 第N次)」
```

SWR 回落到 ≤2.0 或频率变化（>1kHz）时清零该频率失败计数（复位逻辑见下）。

### 4. 集成点

- `_parse_data` METER 分支末尾（锁外），学习检查之后追加：`_check_swr_retune(atr1000, power, cache["swr"])`。
- `set_freq` / `quick_tune` 应用中在频率变化时：清 `_retune_fail_count`（换频率即重置失败保护）。
- `stop`（TX 结束）时：重置 `_swr_high_since = 0`，避免跨发射携带陈旧连续段。

### 5. 与现有机制交互

- **调谐完成**：复用现有逻辑（继电器稳定 >5s，或相同继电器确认 >1.5s）自动清除 `tuning` 标志。清除后守卫恢复评估。
- **成败判定**：调谐完成后，若 SWR 回落到 ≤2.0（守卫复位路径）→ 清零失败计数；若仍 >2.0 且冷却期过后再次触发 → 计数递增，最多 3 次。
- **学习**：自动调谐期间 `tuning=True` 屏蔽学习（现有门控）；调谐成功后 SWR 达标，学习路径继续记录新参数。

## 数据流

```
METER 包 (功率/SWR)
  → _parse_data METER 分支更新 cache
  → 锁外：现有学习检查（tuning 时跳过）
  → 锁外：_check_swr_retune(power, swr)
       ├─ 不达标/跳过 → 维持连续段或复位
       └─ 达标 → cache["tuning"]=True → atr1000.start_tune(2)
                 → 设备扫描 → 继电器稳定 → tuning 自动清除
                 → SWR≤2? → 清失败计数 / 仍>2 → 冷却后重评估（≤3次）
```

## 边界情况

| 场景 | 处理 |
|---|---|
| 设备自主扫描（非代理发起，如 12:20）| 扫描期功率 1–2W < 10W，功率门控跳过 |
| 非 MRRC 路径发射 | 按功率判定，天然覆盖 |
| 话音峰值瞬时 SWR 尖峰 | 1.5s 去抖滤除 |
| 继电器切换瞬态 | 1s 忽略窗口 + 去抖滤除 |
| 天线问题调不好 | 30s 冷却 + 3 次失败保护 |
| 频率频繁切换 | 频率变化即清失败计数，各频率独立评估 |
| 调谐命令发出但无功率（操作员中途松 PTT）| 设备自行处理；tuning 超时/继电器稳定逻辑自动清除 |

## 配置与可调性

阈值为 `atr1000_proxy.py` 顶部具名常量，便于按站点调优。本轮不做配置项外置（YAGNI），如后续需要可加 `MRRC.conf` 项。

## 验证计划

1. **单元测试 `_check_swr_retune`**：
   - 高 SWR 连续段 → 恰好触发一次 `start_tune(2)`；
   - 触发后 30s 冷却期内不重复触发；
   - 失败计数 3 次后不再触发；
   - SWR ≤2 / 功率不足 / tuning 中 → 不触发。
2. **集成验证**：重启代理加载新代码；模拟一次 SWR>2 的发射，确认日志出现触发记录、设备收到完整调谐命令、学习恢复（对应诊断建议）。
3. **回归**：确认现有 set_freq 自动调谐、学习路径行为不变。

# ATR-1000 SWR>2 自动完整调谐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `atr1000_proxy.py` 中实现 SWR 守卫：发射期间（实测功率≥10W）SWR 严格 >2.0 持续 ≥1.5s 时自动发送 ATR-1000 完整调谐（mode=2），30s 冷却，同一频率连续 3 次失败后放弃。

**Architecture:** 在代理的 `_parse_data` METER 处理路径（现有「锁外学习区」旁）追加一个独立的模块级函数 `check_swr_retune(atr1000, power, swr)`。它按实测功率判定发射中（不依赖 `is_tx`，覆盖非 MRRC 路径发射），复用 `cache["tuning"]` 标志避免调谐期间重复触发，用新模块全局状态 `_swr_high_since` / `_last_retune_time` / `_retune_fail_count` 维护去抖、冷却与失败保护。全部改动集中在一个文件加一个测试脚本。

**Tech Stack:** Python 3.11、websocket-client、`atr1000_proxy.py` 现有模块级全局模式、`dev_tools/` 独立断言脚本（无 pytest，遵循 AGENTS.md「use focused dev tools」）。

## Global Constraints

- 只修改 `atr1000_proxy.py` 与 `dev_tools/`（新增测试脚本）；不改 MRRC 主进程、前端、其他设备模块。
- 锁顺序约束：`check_swr_retune` 内先 `cache_lock` 快照、后 `state_lock`；不得出现 `state_lock` 内再取 `cache_lock`，避免与既有代码死锁。
- `handle_unix_client` 内改 `_swr_high_since` 需在函数顶部 `global` 声明中加入该名字。
- 运行测试：`venv/bin/python dev_tools/test_swr_retune.py`（已验证 `atr1000_proxy` 可在 venv 下无网络导入）。
- 不重命名/移动现有函数；新增代码风格与文件一致（中文注释、具名常量、INFO 日志）。
- 每次任务结束提交一个 commit（留在 main 分支，与仓库现有「直接提交 main」实践一致）。

---

### Task 1: `check_swr_retune` 函数 + 常量 + 状态（TDD）

**Files:**
- Modify: `atr1000_proxy.py:175`（学习常量块后加守卫常量）
- Modify: `atr1000_proxy.py:301`（`_last_learned_state = {}` 后加守卫状态）
- Modify: `atr1000_proxy.py:342`（`set_relay_with_throttle` 后加函数）
- Test: `dev_tools/test_swr_retune.py`（新建）

**Interfaces:**
- Consumes: 模块既有 `cache`、`cache_lock`、`state_lock`、`logger`、`LEARN_IGNORE_WINDOW`。
- Produces: 模块级常量 `SWR_RETUNE_THRESHOLD`、`SWR_RETUNE_MIN_POWER`、`SWR_RETUNE_DEBOUNCE`、`SWR_RETUNE_COOLDOWN`、`SWR_RETUNE_MAX_FAILS`；模块级状态 `_swr_high_since`、`_last_retune_time`、`_retune_fail_count`；函数 `check_swr_retune(atr1000, power, swr) -> None`（atr1000 需有 `start_tune(mode)` 方法）。

- [ ] **Step 1: 写失败测试**

新建 `dev_tools/test_swr_retune.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATR-1000 SWR>2 自动完整调谐守卫单元测试
运行: venv/bin/python dev_tools/test_swr_retune.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import atr1000_proxy as ap


class FakeClock:
    now = 1000.0
    @classmethod
    def time(cls):
        return cls.now


class FakeATR:
    def __init__(self):
        self.tune_calls = []  # [(mode, ts), ...]
    def start_tune(self, mode=2):
        self.tune_calls.append((mode, FakeClock.now))


def _reset(freq=21074000, swr=1.0, power=0, tuning=False, relay_changed=0):
    ap._swr_high_since = 0
    ap._last_retune_time = 0
    ap._retune_fail_count.clear()
    with ap.cache_lock:
        ap.cache["freq"] = freq
        ap.cache["swr"] = swr
        ap.cache["power"] = power
        ap.cache["tuning"] = tuning
        ap.cache["tuning_started_at"] = 0
        ap.cache["tuning_relay_stable_since"] = 0
        ap.cache["relay_changed_at"] = relay_changed


def _feed(fake_atr, swr, power, n=1, dt=0.2):
    for _ in range(n):
        FakeClock.now += dt
        ap.check_swr_retune(fake_atr, power, swr)


def test_triggers_once_after_debounce():
    _reset(swr=2.5, power=40)
    fake = FakeATR()
    _feed(fake, 2.5, 40, n=6, dt=0.2)   # 累计 1.2s，未满 1.5s
    assert fake.tune_calls == [], f"不应提前触发: {fake.tune_calls}"
    _feed(fake, 2.5, 40, n=2, dt=0.2)   # 累计 1.6s
    assert len(fake.tune_calls) == 1, f"应恰好触发一次: {fake.tune_calls}"
    assert fake.tune_calls[0][0] == 2, "应为完整调谐 mode=2"
    print("✓ 去抖后恰好触发一次完整调谐 (mode=2)")


def test_cooldown_blocks_repeat():
    _reset(swr=2.5, power=40)
    fake = FakeATR()
    _feed(fake, 2.5, 40, n=8, dt=0.2)   # 触发第一次
    assert len(fake.tune_calls) == 1
    _feed(fake, 2.5, 40, n=10, dt=0.2)  # 冷却期内继续高 SWR
    assert len(fake.tune_calls) == 1, "冷却期内不应再次触发"
    print("✓ 冷却期内不重复触发")


def test_gives_up_after_max_fails():
    _reset(swr=2.5, power=40)
    fake = FakeATR()
    for i in range(3):
        FakeClock.now += 31            # 过 30s 冷却
        ap._swr_high_since = 0         # 模拟 SWR 回落再升高
        _feed(fake, 2.5, 40, n=8, dt=0.2)
        assert len(fake.tune_calls) == i + 1, f"第{i+1}次应触发"
    # 第 4 次连续段：失败计数已达上限 → 不再触发
    FakeClock.now += 31
    ap._swr_high_since = 0
    _feed(fake, 2.5, 40, n=8, dt=0.2)
    assert len(fake.tune_calls) == 3, "3 次失败后不应再触发"
    print("✓ 3 次失败后放弃自动调谐")


def test_skips_when_not_conditions():
    _reset(swr=2.5, power=5)           # 功率不足
    fake = FakeATR()
    _feed(fake, 2.5, 5, n=8, dt=0.2)
    assert fake.tune_calls == [], "功率不足不应触发"

    _reset(swr=1.5, power=40)          # SWR 达标
    fake = FakeATR()
    _feed(fake, 1.5, 40, n=8, dt=0.2)
    assert fake.tune_calls == [], "SWR≤2 不应触发"

    _reset(swr=2.5, power=40, tuning=True)  # 调谐中
    fake = FakeATR()
    _feed(fake, 2.5, 40, n=8, dt=0.2)
    assert fake.tune_calls == [], "调谐中不应触发"

    _reset(swr=2.5, power=40, relay_changed=FakeClock.now - 0.2)  # 继电器忽略窗口
    fake = FakeATR()
    _feed(fake, 2.5, 40, n=8, dt=0.2)
    assert fake.tune_calls == [], "继电器变化 1s 内不应触发"
    print("✓ 功率不足/SWR达标/调谐中/继电器忽略窗口均不触发")


def main():
    ap.time.time = FakeClock.time      # 打桩模块级 time.time
    tests = [test_triggers_once_after_debounce, test_cooldown_blocks_repeat,
             test_gives_up_after_max_fails, test_skips_when_not_conditions]
    for t in tests:
        FakeClock.now = 1000.0
        t()
    print(f"\n全部 {len(tests)} 个测试通过")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `venv/bin/python dev_tools/test_swr_retune.py`
Expected: 首行报 `AttributeError: module 'atr1000_proxy' has no attribute 'check_swr_retune'`（或 `_retune_fail_count` 等不存在）——即测试先于实现失败。

- [ ] **Step 3: 实现常量与状态**

在 `atr1000_proxy.py` 学习常量块（`LEARN_SWR_MAX = 1.8` 之后，第 175 行后）追加：

```python
# ========== SWR 过高自动完整调谐参数 ==========
SWR_RETUNE_THRESHOLD     = 2.0   # SWR 严格大于此值视为过高
SWR_RETUNE_MIN_POWER     = 10    # 实测功率 ≥10W 视为发射中（过滤空闲/调谐扫描的 1–2W）
SWR_RETUNE_DEBOUNCE      = 1.5   # SWR>2 持续 ≥1.5s 才触发
SWR_RETUNE_COOLDOWN      = 30    # 两次自动完整调谐最小间隔（秒）
SWR_RETUNE_MAX_FAILS     = 3     # 同一频率连续失败次数上限
```

在 `_last_learned_state = {}`（第 301 行）后追加：

```python
# SWR 过高自动调谐状态
_swr_high_since   = 0      # 高 SWR 连续起点时间戳（0=不在连续段）
_last_retune_time = 0      # 上次自动调谐时间戳（冷却）
_retune_fail_count = {}    # freq_key → 连续失败次数
```

- [ ] **Step 4: 实现 `check_swr_retune`**

在 `set_relay_with_throttle` 函数结束后（第 342 行后）追加：

```python
def check_swr_retune(atr1000, power, swr):
    """SWR 过高自动完整调谐守卫 - V5.8.0

    发射期间（实测功率 ≥ SWR_RETUNE_MIN_POWER）持续监测 SWR；当
    SWR > SWR_RETUNE_THRESHOLD 且连续 ≥ SWR_RETUNE_DEBOUNCE 秒、不在
    调谐/冷却期时，自动发送一次 ATR-1000 完整调谐（mode=2）。
    同一频率连续 SWR_RETUNE_MAX_FAILS 次调谐仍不达标则放弃，直到频率
    变化或 SWR 回落到阈值以下。按实测功率判定发射中，不依赖 is_tx。
    """
    global _swr_high_since, _last_retune_time

    now = time.time()
    # 先取 cache 快照（cache_lock），再操作守卫状态（state_lock），
    # 严格保持该锁顺序，避免与既有代码死锁。
    with cache_lock:
        tuning = cache.get("tuning", False)
        freq = cache.get("freq", 0)
        relay_changed = cache.get("relay_changed_at", 0)

    with state_lock:
        # 调谐中：SWR 无意义，重置连续段
        if tuning:
            _swr_high_since = 0
            return
        # 功率不足：过滤空闲/调谐扫描期
        if power < SWR_RETUNE_MIN_POWER:
            _swr_high_since = 0
            return
        # SWR 可接受：重置连续段并清零失败计数
        if swr <= SWR_RETUNE_THRESHOLD:
            _swr_high_since = 0
            freq_key = str(freq // 1000)
            if freq_key in _retune_fail_count:
                del _retune_fail_count[freq_key]
            return
        # 继电器变化后忽略窗口（复用学习忽略窗口）
        if relay_changed > 0 and now - relay_changed < LEARN_IGNORE_WINDOW:
            _swr_high_since = 0
            return
        # 频率无效：不评估
        if freq <= 0:
            _swr_high_since = 0
            return

        freq_key = str(freq // 1000)

        # 失败保护：连续 N 次仍不达标 → 放弃该频率（每条连续段只公告一次）
        if _retune_fail_count.get(freq_key, 0) >= SWR_RETUNE_MAX_FAILS:
            if _swr_high_since == 0:
                logger.info(
                    f"⚡ SWR={swr:.2f} 仍过高，已放弃自动调谐"
                    f"（{SWR_RETUNE_MAX_FAILS}次）: {freq/1000:.1f}kHz"
                )
                _swr_high_since = now
            return

        # 进入/维持连续段
        if _swr_high_since == 0:
            _swr_high_since = now

        # 去抖 + 冷却未满足：等待
        if (now - _swr_high_since < SWR_RETUNE_DEBOUNCE or
                now - _last_retune_time < SWR_RETUNE_COOLDOWN):
            return

        # 触发完整调谐（标志在锁内置位，命令在锁外发送）
        with cache_lock:
            cache["tuning"] = True
            cache["tuning_started_at"] = now
            cache["tuning_relay_stable_since"] = 0
            _retune_fail_count[freq_key] = _retune_fail_count.get(freq_key, 0) + 1
        _last_retune_time = now
        _swr_high_since = 0
        atr1000.start_tune(2)
        logger.info(
            f"⚡ SWR={swr:.2f}>2 自动触发完整调谐: {freq/1000:.1f}kHz "
            f"(第{_retune_fail_count[freq_key]}次)"
        )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `venv/bin/python dev_tools/test_swr_retune.py`
Expected: 打印 4 个 `✓` 与「全部 4 个测试通过」。

- [ ] **Step 6: Commit**

```bash
git add atr1000_proxy.py dev_tools/test_swr_retune.py
git commit -m "feat: ATR-1000 SWR>2 自动完整调谐守卫 (check_swr_retune) + 单测"
```

---

### Task 2: 接入 `_parse_data` 与命令处理器

**Files:**
- Modify: `atr1000_proxy.py:832`（`_parse_data` 锁外学习区之后追加守卫调用）
- Modify: `atr1000_proxy.py:917`（`handle_unix_client` 的 `global` 声明加 `_swr_high_since`）
- Modify: `atr1000_proxy.py:948-982`（`set_freq`：频率变化 >1kHz 时清失败计数与连续段）
- Modify: `atr1000_proxy.py:984-1021`（`quick_tune`：重置守卫状态）
- Modify: `atr1000_proxy.py:1094-1115`（`stop`：重置 `_swr_high_since`）
- Test: `dev_tools/test_swr_retune.py`（追加 `_parse_data` 集成测试）

**Interfaces:**
- Consumes: Task 1 的 `check_swr_retune(atr1000, power, swr)`、`_swr_high_since`、`_retune_fail_count`。
- Produces: 无新接口——使守卫随 METER 数据流实时生效，并在频率变化/TX 结束重置状态。

- [ ] **Step 1: 在 `_parse_data` 中调用守卫**

在 `_parse_data` 的锁外学习区（`if _learn_freq > 0:` 整块、第 832 行的 `except` 之后、`def close` 之前）追加：

```python
        # ===== SWR 过高自动完整调谐守卫 (V5.8.0) =====
        if cmd == SCMD_METER_STATUS and len(data) >= 8:
            check_swr_retune(self, power, cache["swr"])
```

（`power` 为 METER 分支局部变量；`cmd` 定义于函数顶部。guard 确保仅 METER 路径调用。）

- [ ] **Step 2: 更新 `handle_unix_client` 的 global 声明**

把第 917 行：

```python
    global clients, cache, client_count, is_tx
```

改为：

```python
    global clients, cache, client_count, is_tx, _swr_high_since
```

- [ ] **Step 3: `set_freq` 频率变化时重置守卫**

把 `set_freq` 分支开头（原 `cache["freq"] = freq` 处）：

```python
            freq = msg.get("freq", 0)
            with cache_lock:
                cache["freq"] = freq
```

改为：

```python
            freq = msg.get("freq", 0)
            with cache_lock:
                old_freq = cache.get("freq", 0)
                cache["freq"] = freq
            # V5.8.0: 频率显著变化 → 重置 SWR 守卫连续段与失败计数
            if abs(freq - old_freq) > 1000:
                with state_lock:
                    _swr_high_since = 0
                    _retune_fail_count.clear()
```

- [ ] **Step 4: `quick_tune` 重置守卫状态**

在 `quick_tune` 分支的 `freq = msg.get("freq", 0)` 之后（`if freq > 0:` 之前）追加：

```python
            # V5.8.0: 手动快速调谐视为一次全新尝试 → 重置守卫失败保护
            with state_lock:
                _swr_high_since = 0
                _retune_fail_count.clear()
```

- [ ] **Step 5: `stop` 重置连续段**

在 `stop` 分支内（`learning_buffer.reset()` 之后、`with cache_lock:` 之前）追加：

```python
            _swr_high_since = 0  # V5.8.0: TX 结束重置 SWR 连续段
```

- [ ] **Step 6: 追加 `_parse_data` 集成测试**

在 `dev_tools/test_swr_retune.py` 的 `test_skips_when_not_conditions` 之后追加：

```python
def test_parse_data_integration():
    """通过 _parse_data 喂连续高 SWR METER 包，验证触发完整调谐。"""
    import struct
    _reset(swr=1.0, power=0)
    ap.is_tx = True
    fake = FakeATR()
    ap._parse_data = ap.ATR1000Client._parse_data.__get__(fake, FakeATR)
    ap.learning_buffer.set_relay(0, 0, 15)
    ap.learning_buffer.set_freq(21074000)
    for _ in range(10):                      # 10 个 SWR=2.5, P=40W 的 METER
        FakeClock.now += 0.2
        raw = struct.pack('<H', 250) + struct.pack('<H', 40)
        ap._parse_data(bytes([0xFF, 0x02, 0x07, 0x00]) + raw)
    assert fake.tune_calls, "高 SWR METER 流应触发完整调谐"
    assert fake.tune_calls[-1][0] == 2, "应为完整调谐 mode=2"
    assert ap.cache["tuning"] is True, "触发后应置 tuning 标志"
    print("✓ _parse_data 集成：高 SWR METER 流触发完整调谐并置 tuning")
```

并把 `main()` 的 tests 列表加上该函数：

```python
    tests = [test_triggers_once_after_debounce, test_cooldown_blocks_repeat,
             test_gives_up_after_max_fails, test_skips_when_not_conditions,
             test_parse_data_integration]
```

- [ ] **Step 7: 运行全部测试**

Run: `venv/bin/python dev_tools/test_swr_retune.py`
Expected: 5 个 `✓` 与「全部 5 个测试通过」。再跑语法检查：
Run: `venv/bin/python -m py_compile atr1000_proxy.py dev_tools/test_swr_retune.py`
Expected: 无输出（编译通过）。

- [ ] **Step 8: Commit**

```bash
git add atr1000_proxy.py dev_tools/test_swr_retune.py
git commit -m "feat: ATR-1000 SWR 守卫接入 _parse_data / set_freq / quick_tune / stop + 集成测试"
```

---

### Task 3: 文档、全量验证与实机检查清单

**Files:**
- Modify: `CHANGELOG.md`（顶部新增 V5.8.0 条目）
- Modify: `docs/superpowers/specs/2026-08-09-atr1000-swr-autotune-design.md`（可选：若实现与 spec 有出入则同步）

**Interfaces:**
- Consumes: Task 1、2 的成品。
- Produces: 版本说明、可交付验证记录。

- [ ] **Step 1: 更新 CHANGELOG**

在 `CHANGELOG.md` 顶部（`## [V5.7.2]` 之前）新增：

```markdown
## [V5.8.0] - 2026-08-09

### ⚡ ATR-1000 SWR>2 自动完整调谐

- **新增 SWR 守卫**：发射期间（实测功率 ≥10W）SWR 严格大于 2.0 持续 ≥1.5s 时，
  自动发送 ATR-1000 完整调谐（mode=2）；30s 冷却；同一频率连续 3 次失败后放弃，
  直到频率变化或 SWR 回落
- **按实测功率判定发射中**：不依赖前端 TX start 信号，覆盖电台直接 PTT / 外部软件发射场景
- **状态重置**：频率变化 >1kHz 或 TX 结束自动重置守卫状态；调谐期间复用 `tuning`
  标志避免重复触发，与自动学习互不干扰
```

- [ ] **Step 2: 全量测试运行**

Run: `venv/bin/python dev_tools/test_swr_retune.py`
Expected: 全部通过。
Run: `venv/bin/python -m py_compile atr1000_proxy.py`
Expected: 无输出。
Run: `git diff --stat HEAD~2 -- atr1000_proxy.py dev_tools/test_swr_retune.py CHANGELOG.md`
Expected: 仅这 3 个文件有改动。

- [ ] **Step 3: 实机验证清单（需要用户配合，涉及重启线上代理）**

先重启 radio1 实例的 ATR-1000 代理以加载新代码（`mrrc_multi.sh` 无单组件 restart，手动 kill+拉起；MRRC 的 `ATR1000ProxyManager` 会自动重连 unix socket，无需重启 MRRC）：

```bash
# 1) 找到并终止旧代理（radio1 实例，当前 PID 见 atr1000_radio1.pid 或 ps 输出）
pgrep -f "atr1000_proxy.py.*radio1" | xargs kill
sleep 1
rm -f /tmp/mrrc_radio1.sock
# 2) 用与启动时相同的参数重新拉起（输出追加到实例日志）
python3 /Users/cheenle/HAM/mrrc/atr1000_proxy.py \
    --device 192.168.1.63 --port 60001 --unix-socket /tmp/mrrc_radio1.sock \
    >> /Users/cheenle/UHRR/MRRC/atr1000_radio1.log 2>&1 &
```

重启后向用户提交验证清单，等待用户操作/确认后再继续：
1. 确认新代理日志出现启动信息、`atr1000_proxy_manager` 重连成功。
2. 在低 SWR（<1.5）频率正常发射一次 → 确认**不**触发自动调谐，学习照常。
3. 在匹配差的频率（或临时断开天线/切换天线）发射 → 确认 ~1.5s 后日志出现
   `⚡ SWR=...>2 自动触发完整调谐`，前端/设备收到完整调谐命令，调谐后 SWR 回落。
4. 若天线问题持续 → 确认 30s 冷却与「3 次失败后放弃」生效（日志出现「已放弃自动调谐」）。
5. 确认 `atr1000_tuner.json` 在调谐成功后恢复学习写盘（对应诊断建议的重启验证）。

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: CHANGELOG V5.8.0 — ATR-1000 SWR>2 自动完整调谐"
```

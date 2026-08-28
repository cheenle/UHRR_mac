# 单声道通联录音实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将 MRRC 录音改为 RX/TX 共用真实时间轴的 16 kHz 单声道 MP3，并录制 WDSP 后 RX 与实际播放 TX。

**架构：** 新建独立、无声卡依赖的 `RecordingSession`，按单调时钟保存带来源和样本偏移的音频事件，停止时先铺 RX、再以 TX 覆盖，得到单声道 PCM。`audio_interface.py` 在 WDSP 后提交 RX，`MRRC` 在 TX 归一化并进入播放队列后提交 TX；现有 WebSocket 命令和录音列表接口保持不变。

**技术栈：** Python 3、NumPy、`unittest`、PyAudio、Tornado WebSocket、ffmpeg/libmp3lame、浏览器 JavaScript。

---

## 文件结构

- 创建 `recording_session.py`：纯 Python/NumPy 的录音时间轴、分来源降采样、重叠优先级与状态管理。
- 创建 `dev_tools/test_recording_session.py`：不依赖声卡的时间轴、重采样、边界和状态测试。
- 修改 `audio_interface.py`：使用 `RecordingSession`，在 WDSP 后采集 RX，输出单声道 MP3，并让 TX 播放接口返回实际排队 PCM。
- 修改 `MRRC`：将实际归一化后的 TX PCM 及对应时间戳提交给录音会话。
- 修改 `www/mobile_modern.js`：服务端失败时恢复录音按钮状态并显示错误。

### 任务 1：实现可测试的统一录音时间轴

**文件：**
- 创建：`recording_session.py`
- 创建：`dev_tools/test_recording_session.py`

- [ ] **步骤 1：编写失败的顺序、静音和 TX 覆盖测试**

在 `dev_tools/test_recording_session.py` 使用标准库 `unittest`，以显式纳秒时间戳避免真实等待：

```python
import unittest
import numpy as np

from recording_session import RecordingSession


class RecordingSessionTests(unittest.TestCase):
    def setUp(self):
        self.session = RecordingSession(sample_rate=16000, max_seconds=60)
        self.t0 = 10_000_000_000
        self.assertTrue(self.session.start(freq=7_050_000, now_ns=self.t0))

    def test_rx_tx_rx_follow_real_timeline(self):
        rx1 = np.full(1600, 1000, dtype=np.int16)
        tx = np.full(1600, 2000, dtype=np.int16)
        rx2 = np.full(1600, 3000, dtype=np.int16)
        self.session.add_audio("rx", rx1, 16000, self.t0)
        self.session.add_audio("tx", tx, 16000, self.t0 + 200_000_000)
        self.session.add_audio("rx", rx2, 16000, self.t0 + 400_000_000)

        result = self.session.stop(now_ns=self.t0 + 500_000_000)

        np.testing.assert_array_equal(result.pcm[0:1600], rx1)
        self.assertTrue(np.all(result.pcm[1600:3200] == 0))
        np.testing.assert_array_equal(result.pcm[3200:4800], tx)
        self.assertTrue(np.all(result.pcm[4800:6400] == 0))
        np.testing.assert_array_equal(result.pcm[6400:8000], rx2)

    def test_tx_overwrites_rx_at_same_timeline_position(self):
        rx = np.full(1600, 1000, dtype=np.int16)
        tx = np.full(800, 2000, dtype=np.int16)
        self.session.add_audio("rx", rx, 16000, self.t0)
        self.session.add_audio("tx", tx, 16000, self.t0 + 50_000_000)

        result = self.session.stop(now_ns=self.t0 + 100_000_000)

        self.assertTrue(np.all(result.pcm[:800] == 1000))
        self.assertTrue(np.all(result.pcm[800:1600] == 2000))
```

- [ ] **步骤 2：运行测试并确认因模块不存在而失败**

运行：

```bash
python3 -m unittest dev_tools.test_recording_session -v
```

预期：`ModuleNotFoundError: No module named 'recording_session'`。

- [ ] **步骤 3：实现最小时间轴模型**

在 `recording_session.py` 定义以下稳定接口：

```python
from dataclasses import dataclass
from datetime import datetime
import threading
import time
import numpy as np


@dataclass(frozen=True)
class RecordingResult:
    pcm: np.ndarray
    freq: int
    started_at: datetime
    duration: float


class RecordingSession:
    def __init__(self, sample_rate=16000, max_seconds=3600): ...
    def start(self, freq=0, now_ns=None): ...
    def add_audio(self, source, pcm, source_rate, timestamp_ns=None): ...
    def stop(self, now_ns=None): ...
    def status(self, now_ns=None): ...
```

实现要求：

- `start()` 使用 `time.monotonic_ns()`，重复开始返回 `False` 且不清空当前事件。
- `add_audio()` 仅接受 `source in {"rx", "tx"}` 和正采样率；输入统一复制为一维 `int16`。
- 事件结构为 `(source, sample_offset, samples)`；偏移为 `(timestamp_ns - start_ns) * 16000 // 1_000_000_000`。
- `stop()` 的输出长度至少覆盖停止时间；先写全部 RX，再写全部 TX，因此 TX 确定性覆盖重叠位置。
- 返回后清空会话；未开始时 `stop()` 返回 `None`。
- 超过 `max_seconds * sample_rate` 的偏移或样本被截断，杜绝无界增长。

- [ ] **步骤 4：运行时间轴测试确认通过**

运行：

```bash
python3 -m unittest dev_tools.test_recording_session -v
```

预期：2 个测试均为 `ok`。

- [ ] **步骤 5：添加分块重采样和状态边界测试**

补充以下测试：

```python
def test_48k_chunked_resampling_keeps_16k_duration(self):
    tone = (np.sin(2 * np.pi * 1000 * np.arange(4800) / 48000) * 12000).astype(np.int16)
    for index in range(0, len(tone), 960):
        timestamp = self.t0 + index * 1_000_000_000 // 48000
        self.session.add_audio("rx", tone[index:index + 960], 48000, timestamp)
    result = self.session.stop(now_ns=self.t0 + 100_000_000)
    self.assertEqual(len(result.pcm), 1600)
    self.assertGreater(np.max(np.abs(result.pcm)), 5000)


def test_duplicate_start_and_empty_stop_are_safe(self):
    self.assertFalse(self.session.start(freq=14_270_000, now_ns=self.t0 + 1))
    result = self.session.stop(now_ns=self.t0 + 100_000_000)
    self.assertEqual(result.freq, 7_050_000)
    self.assertIsNone(self.session.stop(now_ns=self.t0 + 200_000_000))
```

实现 `RecordingSession` 内部的每来源有状态转换器：16 kHz 直通；48 kHz 使用窗口化 sinc FIR 和跨块抽取相位。RX、TX 必须使用不同转换器实例，`start()` 时重置。

- [ ] **步骤 6：运行完整会话测试**

运行：

```bash
python3 -m unittest dev_tools.test_recording_session -v
```

预期：4 个测试均为 `ok`。

- [ ] **步骤 7：提交时间轴组件**

```bash
git add recording_session.py dev_tools/test_recording_session.py
git commit -m "feat: 添加单声道录音时间轴"
```

### 任务 2：接入 WDSP 后 RX 并输出单声道 MP3

**文件：**
- 修改：`audio_interface.py:24-30, 205-215, 367-737, 767-890, 1031-1058`
- 修改：`dev_tools/test_recording_session.py`

- [ ] **步骤 1：添加 MP3 编码参数测试**

把 ffmpeg 调用封装为 `audio_interface._encode_recording_mp3(pcm, filepath, sample_rate=16000)`，在测试中用 `unittest.mock.patch("audio_interface.subprocess.run")` 验证：

```python
def test_mp3_encoder_receives_mono_16k_pcm(self):
    pcm = np.array([1, -1, 2, -2], dtype=np.int16)
    completed = type("Completed", (), {"returncode": 0, "stderr": b""})()
    with mock.patch("audio_interface.subprocess.run", return_value=completed) as run:
        audio_interface._encode_recording_mp3(pcm, "/tmp/test.mp3")
    command = run.call_args.args[0]
    self.assertEqual(command[command.index("-ar") + 1], "16000")
    self.assertEqual(command[command.index("-ac") + 1], "1")
    self.assertEqual(run.call_args.kwargs["input"], pcm.tobytes())
```

测试文件顶部增加 `from unittest import mock` 和 `import audio_interface`。

- [ ] **步骤 2：运行编码测试确认当前立体声实现失败**

运行：

```bash
python3 -m unittest dev_tools.test_recording_session.RecordingSessionTests.test_mp3_encoder_receives_mono_16k_pcm -v
```

预期：因 `_encode_recording_mp3` 尚不存在而报 `AttributeError`。

- [ ] **步骤 3：用 RecordingSession 替换双缓冲区保存逻辑**

在 `audio_interface.py`：

- 导入 `RecordingSession`，创建模块级 `_recording_session = RecordingSession(sample_rate=16000, max_seconds=3600)`。
- `PyAudioCapture.start_recording()` 委托 `_recording_session.start(freq)`。
- `PyAudioCapture.stop_recording()` 调用 `_recording_session.stop()`；结果为空返回 `None`，否则将 `result.pcm` 传给 `_encode_recording_mp3()`。
- ffmpeg 参数固定为 `-f s16le -ar 16000 -ac 1 -c:a libmp3lame -q:a 0`。
- `get_recording_status()` 返回会话 `status()`，继续提供 `recording`、`freq`、`start_time`、`duration`、`buffer_size` 键。
- 删除 `recording_buffer`、`tx_recording_buffer` 及左右声道拼接，不保留双重状态源。

- [ ] **步骤 4：将 RX 采集点移动到 WDSP 之后**

在 `PyAudioCapture.run()` 每次成功读取设备数据后保存：

```python
capture_timestamp_ns = time.monotonic_ns()
```

删除当前位于 WDSP 之前的“录音功能：保存原始音频数据”块。在 WDSP 处理完成、进入客户端编码之前读取主模块 PTT 状态；仅当 PTT 为假时调用：

```python
_recording_session.add_audio(
    "rx", int16_data, stream_rate, capture_timestamp_ns
)
```

录音不得依赖 `AudioRXHandlerClients` 数量；即使没有浏览器 RX WebSocket 客户端，已开始的服务端录音仍应继续。

- [ ] **步骤 5：运行测试与 Python 语法检查**

运行：

```bash
python3 -m unittest dev_tools.test_recording_session -v
python3 -m py_compile recording_session.py audio_interface.py
```

预期：全部测试通过，`py_compile` 无输出。

- [ ] **步骤 6：提交 RX 与编码接入**

```bash
git add audio_interface.py dev_tools/test_recording_session.py
git commit -m "feat: 录制 WDSP 后单声道接收音频"
```

### 任务 3：接入实际播放 TX 音频

**文件：**
- 修改：`audio_interface.py:1000-1058`
- 修改：`MRRC:699-875`
- 修改：`dev_tools/test_recording_session.py`

- [ ] **步骤 1：编写 TX 播放接口返回值测试**

不打开声卡，使用 `PyAudioPlayback.__new__()` 构造实例并放入假队列：

```python
def test_playback_write_returns_pcm_accepted_by_queue(self):
    playback = audio_interface.PyAudioPlayback.__new__(audio_interface.PyAudioPlayback)
    playback._tx_queue = audio_interface.queue.Queue(maxsize=2)
    playback._normalize = lambda data: b"normalized-" + data

    actual = playback.write(b"input")

    self.assertEqual(actual, b"normalized-input")
    self.assertEqual(playback._tx_queue.get_nowait(), b"normalized-input")
```

- [ ] **步骤 2：运行测试确认返回值当前为 None**

运行：

```bash
python3 -m unittest dev_tools.test_recording_session.RecordingSessionTests.test_playback_write_returns_pcm_accepted_by_queue -v
```

预期：FAIL，`None != b'normalized-input'`。

- [ ] **步骤 3：让播放接口返回实际入队 PCM**

修改 `PyAudioPlayback.write()`：

- `_normalize()` 失败返回 `None`。
- 正常入队后返回 `pcm`。
- 队列满时按现有策略丢弃最旧帧；若最终仍无法入队，返回 `None`，避免录下并未排队的 TX。

- [ ] **步骤 4：在 WebSocket TX 路径提交归一化 PCM**

在 `WS_AudioTXHandler.TX_init()` 保存：

```python
self.tx_input_rate = op_rate if is_encoded else itrate
```

在 `on_message()` 二进制音频分支入口保存 `tx_timestamp_ns = time.monotonic_ns()`。调用：

```python
played_pcm = self.audio_playback.write(data)
```

仅当 `played_pcm` 非空、录音开启且 `CTRX.mrrc_ptt_active` 为真时调用模块接口：

```python
from audio_interface import add_recording_audio
add_recording_audio("tx", played_pcm, self.tx_input_rate, tx_timestamp_ns)
```

删除旧的 `tx_recording_buffer.append()`、重复 Opus 解码和 `tx_int16[::ratio]` 简单抽取逻辑。TX 分析器继续使用已有 `last_decoded_pcm`，不改变其行为。

- [ ] **步骤 5：运行单元测试和后端语法检查**

运行：

```bash
python3 -m unittest dev_tools.test_recording_session -v
python3 -m py_compile recording_session.py audio_interface.py MRRC
```

预期：全部测试通过，三个文件语法检查无输出。

- [ ] **步骤 6：提交 TX 接入**

```bash
git add audio_interface.py MRRC dev_tools/test_recording_session.py
git commit -m "fix: 按真实时间轴录制发射音频"
```

### 任务 4：修正前端录音失败状态

**文件：**
- 修改：`www/mobile_modern.js:4820-4968`

- [ ] **步骤 1：确认当前失败状态不会恢复按钮**

检查 `handleRecordingStatus("failed")` 路径；当前既不调用 `updateRecordingUI(false)`，也不调用 `showRecordingStatus()`。记录此行为作为手工失败基线。

- [ ] **步骤 2：实现服务端确认驱动的失败恢复**

在 `handleRecordingStatus(status)` 简单字符串分支增加：

```javascript
} else if (status === 'failed') {
    updateRecordingUI(false);
    showRecordingStatus('录音失败', 'error');
```

`startRecording()` 发送后可保持现有乐观 UI；服务端返回 `failed` 时必须恢复。`stopRecording()` 若 WebSocket 未连接，也调用 `updateRecordingUI(false)` 并显示“连接失败”。

- [ ] **步骤 3：执行 JavaScript 语法检查**

运行：

```bash
node --check www/mobile_modern.js
```

预期：无输出，退出码 0。

- [ ] **步骤 4：提交前端状态修正**

```bash
git add www/mobile_modern.js
git commit -m "fix: 恢复录音失败后的按钮状态"
```

### 任务 5：端到端验证与回归检查

**文件：**
- 验证：`recording_session.py`
- 验证：`audio_interface.py`
- 验证：`MRRC`
- 验证：`www/mobile_modern.js`

- [ ] **步骤 1：运行所有录音单元测试**

```bash
python3 -m unittest dev_tools.test_recording_session -v
```

预期：全部测试为 `ok`。

- [ ] **步骤 2：运行静态诊断与语法检查**

```bash
python3 -m py_compile recording_session.py audio_interface.py MRRC
node --check www/mobile_modern.js
```

随后对四个修改文件运行 LSP diagnostics，并修复新增错误。

- [ ] **步骤 3：生成可探测的样例 MP3**

使用测试会话生成 0.1 秒 RX、0.1 秒静音、0.1 秒 TX 的 PCM，并调用 `_encode_recording_mp3()` 写入临时目录；运行：

```bash
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels -of default=noprint_wrappers=1 /tmp/mrrc_recording_test.mp3
```

预期：

```text
codec_name=mp3
sample_rate=16000
channels=1
```

删除临时文件。

- [ ] **步骤 4：检查录音线上的旧实现已完全移除**

```bash
rg -n "tx_recording_buffer|column_stack|samples?\[::ratio\]" audio_interface.py MRRC
```

预期：没有录音路径匹配；若其他非录音功能存在匹配，逐条确认与本次范围无关。

- [ ] **步骤 5：检查工作区和完整诊断**

```bash
git diff --check
git status --short
```

运行 `lens_diagnostics` 的 `mode=all`，确认本次编辑文件无阻塞错误。保留用户原有未提交改动，不暂存、不覆盖、不回滚。

- [ ] **步骤 6：提交遗漏的验证修正（仅在有修正时）**

```bash
git add recording_session.py audio_interface.py MRRC www/mobile_modern.js dev_tools/test_recording_session.py
git commit -m "test: 完善通联录音回归验证"
```

#!/usr/bin/env python3
"""TX 音频关闭路径有界性守卫测试：python3 dev_tools/test_audio_close_liveness.py

背景（RC-003，2026-10-04）：用户松 PTT 时，`WS_AudioTXHandler.on_message('s:')`
在 **IOLoop 线程**上直接调用 `PyAudioPlayback.close()`，而 close() 里的
PortAudio `Pa_StopStream()` 是 C 调用，设备/HAL 异常时**永不返回**——
整个 HTTP/WebSocket 服务（8891）楔死 2h23m：进程活着、音频仍跑、端口假死。
这与 RC-001（p.open 在 IOLoop 上）是同一族问题：F2/F4 修了 write/init，漏了 close。

F6 修复契约（本测试守这些）：
① `close()` 必须**有界返回**：stop/close 放一次性线程，超时即放弃（泄漏流），
   绝不让阻塞的 `Pa_StopStream` 拖住调用者；
② `close_async()` 供 IOLoop 调用点用：立即返回，拆流在后台线程完成；
③ 写线程仍卡在阻塞 write() 时，**不得**从别的线程再 stop/close 同一 stream
   （两个线程同时操作一个 PortAudio stream 是已知竞态）；
④ `close()` 幂等；⑤ MRRC 的 s:/on_close 调用点不得再裸调 close()。
"""
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

fails, notes = [], []


# ---------- 静态守卫：IOLoop 调用点必须走 close_async ----------

def _method_body(text):
    """从方法首行截到下一个顶层行（只按缩进定界，不依赖下一个 def 的位置）。"""
    out = []
    for line in text.split('\n'):
        if out and line and line[0] not in '\t ':
            break
        out.append(line)
    return '\n'.join(out)


def _static_guards():
    src = (ROOT / 'MRRC').read_text(encoding='utf-8')

    # s: 分支：从 elif str(data).startswith('s:') 到同缩进的 else
    marker = "elif str(data).startswith('s:')"
    if marker not in src:
        fails.append("MRRC 里找不到 s: 分支（静态守卫失效，请更新本测试）")
    else:
        branch = src[src.index(marker):]
        cut = branch.find("\n\t\telse")
        branch = branch[:cut] if cut > 0 else branch
        if 'close_async()' not in branch:
            fails.append("s: 分支仍直接调用 close()，未改走 close_async()（F6）")
        if 'audio_playback.close()' in branch:
            fails.append("s: 分支仍存在裸调 audio_playback.close()")
        if 'CTRX.setPTT("false")' in branch:
            fails.append("s: 分支仍在 IOLoop 上同步释放 PTT（rigctld 阻塞 IO，应走 "
                         "MAIN_IOLOOP.run_in_executor）")

    # on_close：MRRC 有多个 on_close，只取 WS_AudioTXHandler 里的那个
    cls_marker = "class WS_AudioTXHandler("
    if cls_marker not in src:
        fails.append("MRRC 里找不到 WS_AudioTXHandler（静态守卫失效，请更新本测试）")
    else:
        cls = src[src.index(cls_marker):]
        cut = cls.find("\nclass ")
        cls = cls[:cut] if cut > 0 else cls
        marker = "def on_close(self):"
        if marker not in cls:
            fails.append("WS_AudioTXHandler 里找不到 on_close（静态守卫失效）")
        else:
            body = cls[cls.index(marker):]
            body = _method_body(body)
            if 'close_async()' not in body:
                fails.append("on_close 仍直接调用 close()，未改走 close_async()（F6）")
            if 'audio_playback.close()' in body:
                fails.append("on_close 仍存在裸调 audio_playback.close()")
            if 'CTRX.setPTT("false")' in body:
                fails.append("on_close 仍在 IOLoop 上同步释放 PTT")

    # 看门狗必须有原生（非 IOLoop 线程）栈转储手段
    if 'dump_traceback_later' not in src:
        fails.append("看门狗缺少 faulthandler.dump_traceback_later（原生线程转储，"
                     "IOLoop 永久楔死时唯一能留下现场的手段）")


_static_guards()


# ---------- 功能守卫：假 stream 阻塞 stop_stream ----------

audio_interface: Any = None
_IMPORT_ERROR: Exception | None = None
try:
    import audio_interface as _mod  # noqa: F401
    audio_interface = _mod
except Exception as exc:  # 没有 pyaudio/numpy/opus 等依赖时只跑静态部分
    _IMPORT_ERROR = exc


class _FakeStream:
    """假输出流：block_stop=True 时 stop_stream() 永不返回（模拟 RC-003 现场）。"""

    def __init__(self, block_stop=False):
        self.block_stop = block_stop
        self.stop_called = False
        self.close_called = False
        self._gate = threading.Event()

    def is_active(self):
        return True

    def stop_stream(self):
        self.stop_called = True
        if self.block_stop:
            self._gate.wait()  # 永久阻塞（测试线程是 daemon，不会拖住进程退出）

    def close(self):
        self.close_called = True


class _FakePyAudio:
    def __init__(self):
        self.terminate_calls = 0

    def terminate(self):
        self.terminate_calls += 1


def _make(block_stop=False, writer_alive=False):
    pb = audio_interface.PyAudioPlayback.__new__(audio_interface.PyAudioPlayback)
    pb._writer_stop = threading.Event()
    pb._tx_queue = queue.Queue()
    pb.stream = _FakeStream(block_stop=block_stop)
    pb.p = _FakePyAudio()
    if writer_alive:
        t = threading.Thread(target=threading.Event().wait, daemon=True)
        t.start()
        pb._writer_thread = t
    else:
        pb._writer_thread = None
    return pb, pb.stream, pb.p


def _safe(fn):
    try:
        fn()
        return None
    except BaseException as exc:  # noqa: BLE001 - 测试要区分"抛异常"与"卡死"
        return exc


def _run_bounded(fn, limit):
    """在子线程里跑 fn，返回 (是否在 limit 内结束, 耗时, 异常)。"""
    box = {}
    t = threading.Thread(target=lambda: box.setdefault('exc', _safe(fn)), daemon=True)
    t0 = time.time()
    t.start()
    t.join(limit)
    return (not t.is_alive()), time.time() - t0, box.get('exc')


def _functional_guards():
    # ① 阻塞的 stop_stream 不得拖死 close()（RC-003 现场）
    pb, _, _ = _make(block_stop=True)
    finished, elapsed, exc = _run_bounded(pb.close, 10.0)
    if not finished:
        fails.append("close() 被阻塞的 stop_stream 拖死（>10s 未返回）—— RC-003 未修")
    elif exc is not None:
        fails.append(f"close() 在阻塞场景抛异常：{exc!r}")
    else:
        notes.append(f"close() 阻塞场景 {elapsed:.2f}s 内返回")

    # ② close_async() 必须立即返回（IOLoop 调用点）
    if not hasattr(audio_interface.PyAudioPlayback, 'close_async'):
        fails.append("PyAudioPlayback 没有 close_async()（IOLoop 调用点仍需直接调用）")
    else:
        pb, _, _ = _make(block_stop=True)
        finished, elapsed, exc = _run_bounded(pb.close_async, 2.0)
        if not finished:
            fails.append("close_async() 没有立即返回")
        elif exc is not None:
            fails.append(f"close_async() 抛异常：{exc!r}")
        elif elapsed > 1.0:
            fails.append(f"close_async() 耗时 {elapsed:.2f}s，应 <1s")

    # ③ 写线程未退出时不许再碰同一 stream
    pb, stream, _ = _make(block_stop=False, writer_alive=True)
    finished, elapsed, exc = _run_bounded(pb.close, 10.0)
    if not finished:
        fails.append("写线程存活时 close() 未返回")
    else:
        if stream.stop_called:
            fails.append("写线程仍存活时仍调用了 stream.stop_stream()（跨线程操作竞态）")
        if elapsed > 5.0:
            fails.append(f"写线程存活时 close() 耗时 {elapsed:.2f}s，应快速放弃")

    # ④ 正常路径：stop/close/terminate 都要发生
    pb, stream, p = _make()
    finished, _, exc = _run_bounded(pb.close, 10.0)
    if not finished or exc is not None:
        fails.append(f"正常路径 close() 异常：finished={finished} exc={exc!r}")
    else:
        if not (stream.stop_called and stream.close_called):
            fails.append("正常路径 close() 未 stop/close 流")
        if p.terminate_calls != 1:
            fails.append(f"正常路径 PyAudio.terminate 调用 {p.terminate_calls} 次（应 1）")

        # ⑤ 幂等：重复 close() 不得再次操作已关闭的流
        pb.close()
        if p.terminate_calls != 1:
            fails.append(f"close() 不幂等：terminate 被调用 {p.terminate_calls} 次")


if audio_interface is None:
    notes.append(f"未安装音频依赖，功能部分跳过：{_IMPORT_ERROR!r}")
else:
    _functional_guards()


for n in notes:
    print(f'  提示: {n}')
if fails:
    print(f'❌ {len(fails)} 项不合格:')
    for f in fails:
        print('   -', f)
    sys.exit(1)
print('✅ TX 音频关闭路径有界性守卫通过（close 有界 / close_async 立即可用 / '
      '写线程竞态保护 / 幂等 / IOLoop 调用点无裸调）')

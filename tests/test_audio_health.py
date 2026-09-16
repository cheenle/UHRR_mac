"""采集健康摘要的单元测试。

背景（2026-09-16 诊断包事故）：`🎧 音频健康` 行与 `PyAudioCapture.last_health`
原本整段嵌在 `if _audio_diag:`（MRRC_AUDIO_DIAG=1）里，注释却写着"无需开关" ——
于是默认情况下诊断包永远看不到健康度，体检结论永远误报"可能未启动采集"。
这里把累计/成行/字节→帧换算提成纯函数并钉住行为。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import audio_interface
    _IMPORT_ERROR = None
except Exception as exc:                      # 没有 pyaudio 等依赖时跳过
    audio_interface = None
    _IMPORT_ERROR = exc


@unittest.skipIf(audio_interface is None, f"audio_interface 不可导入：{_IMPORT_ERROR}")
class CaptureHealthTest(unittest.TestCase):
    @staticmethod
    def _ai():
        """显式收窄 Optional（无 pyaudio 时整个类已被 skip，这里只是给类型检查看）。"""
        if audio_interface is None:
            raise unittest.SkipTest("audio_interface 不可导入")
        return audio_interface

    def _diag(self, since=0.0):
        return {"summary_since": since, "summary_reads": 0,
                "summary_samples": 0, "summary_max": 0.0}

    def _health(self, diag, **kwargs):
        """调用累计函数并断言成行（返回非 Optional 的字符串）。"""
        line = self._ai().accumulate_capture_health(diag, **kwargs)
        self.assertIsNotNone(line)
        return line or ""

    def test_no_line_before_window_but_counters_accumulate(self):
        diag = self._diag()
        self.assertIsNone(self._ai().accumulate_capture_health(
            diag, samples=48000, read_seconds=0.02, now=10.0))
        self.assertEqual(diag["summary_reads"], 1)
        self.assertEqual(diag["summary_samples"], 48000)
        self.assertAlmostEqual(diag["summary_max"], 0.02)
        self.assertEqual(diag["summary_since"], 0.0, "未到窗口不该重置统计窗口")

    def test_line_after_window_warns_when_starved(self):
        diag = self._diag()
        line = self._health(diag, samples=1440000, read_seconds=0.05, now=31.0)
        self.assertIn("🎧 音频健康", line)
        self.assertIn("96.8", line, "1440000 / (31*48000) ≈ 96.8%")
        self.assertIn("⚠", line, "低于 99% 必须给告警提示")
        self.assertEqual(diag["summary_since"], 31.0, "成行后要重置窗口")
        self.assertEqual(diag["summary_samples"], 0)
        self.assertEqual(diag["summary_max"], 0.0)

    def test_healthy_capture_has_no_warning(self):
        diag = self._diag()
        line = self._health(diag, samples=30 * 48000, read_seconds=0.01, now=30.0)
        self.assertIn("100.0", line)
        self.assertNotIn("⚠", line)

    def test_custom_window_seconds(self):
        diag = self._diag(since=100.0)
        self.assertIsNone(self._ai().accumulate_capture_health(
            diag, samples=100, read_seconds=0.0, now=105.0, window_seconds=10.0))
        self.assertIsNotNone(self._ai().accumulate_capture_health(
            diag, samples=100, read_seconds=0.0, now=111.0, window_seconds=10.0))

    def test_float32_stereo_read_counts_frames_not_int16_samples(self):
        """RX 采集是 paFloat32 + 立体声（960 帧 = 7680 字节）。旧代码用 int16 的
        len(data)//2 计数，恒放大 4 倍 → 健康度永远 400%，<99% 告警永远不触发。"""
        self.assertEqual(self._ai().capture_frame_count(960 * 2 * 4, channels=2), 960)
        self.assertEqual(self._ai().capture_frame_count(960 * 4, channels=1), 960)
        self.assertEqual(self._ai().capture_frame_count(0, channels=2), 0)

    def test_realtime_float32_stereo_capture_reports_100_percent(self):
        diag = self._diag()
        frames = sum(self._ai().capture_frame_count(960 * 2 * 4, channels=2)
                     for _ in range(1500))
        line = self._health(diag, samples=frames, read_seconds=0.02, now=30.0)
        self.assertIn("100.0", line, "30s × 50 次/s × 960 帧 正好是 48000 Hz 实时")
        self.assertNotIn("⚠", line)


if __name__ == "__main__":
    unittest.main(verbosity=2)

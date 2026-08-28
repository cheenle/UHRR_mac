#!/usr/bin/env python3
"""Tests for the time-aligned mono conversation recorder."""

import unittest
from unittest import mock

import numpy as np

import audio_interface
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

        assert result is not None
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

        assert result is not None
        self.assertTrue(np.all(result.pcm[:800] == 1000))
        self.assertTrue(np.all(result.pcm[800:1600] == 2000))

    def test_48k_chunked_resampling_keeps_16k_duration(self):
        tone = (
            np.sin(2 * np.pi * 1000 * np.arange(4800) / 48000) * 12000
        ).astype(np.int16)
        for index in range(0, len(tone), 960):
            timestamp = self.t0 + index * 1_000_000_000 // 48000
            self.session.add_audio("rx", tone[index:index + 960], 48000, timestamp)

        result = self.session.stop(now_ns=self.t0 + 100_000_000)

        assert result is not None
        self.assertEqual(len(result.pcm), 1600)
        self.assertGreater(np.max(np.abs(result.pcm)), 5000)

    def test_duplicate_start_and_empty_stop_are_safe(self):
        self.assertFalse(
            self.session.start(freq=14_270_000, now_ns=self.t0 + 1)
        )
        result = self.session.stop(now_ns=self.t0 + 100_000_000)
        assert result is not None
        self.assertEqual(result.freq, 7_050_000)
        self.assertIsNone(self.session.stop(now_ns=self.t0 + 200_000_000))

    def test_mp3_encoder_receives_mono_16k_pcm(self):
        pcm = np.array([1, -1, 2, -2], dtype=np.int16)
        completed = type(
            "Completed", (), {"returncode": 0, "stderr": b""}
        )()
        with mock.patch(
            "audio_interface.subprocess.run", return_value=completed
        ) as run:
            audio_interface._encode_recording_mp3(pcm, "/tmp/test.mp3")

        command = run.call_args.args[0]
        self.assertEqual(command[command.index("-ar") + 1], "16000")
        self.assertEqual(command[command.index("-ac") + 1], "1")
        self.assertEqual(run.call_args.kwargs["input"], pcm.tobytes())


if __name__ == "__main__":
    unittest.main()

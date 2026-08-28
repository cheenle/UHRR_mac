#!/usr/bin/env python3
"""Time-aligned mono recording sessions for RX/TX conversation audio."""

from dataclasses import dataclass
from datetime import datetime
import threading
import time

import numpy as np


class _StreamingDecimator:
    """Stateful FIR low-pass filter followed by integer-ratio decimation."""

    def __init__(self, source_rate, target_rate, ntaps=96):
        if source_rate % target_rate != 0:
            raise ValueError("source_rate must be an integer multiple of sample_rate")
        self.factor = source_rate // target_rate
        self._ntaps = ntaps
        n = np.arange(ntaps) - (ntaps - 1) / 2.0
        cutoff_hz = min(5500.0, target_rate * 0.4)
        coefficients = (
            2.0
            * cutoff_hz
            / source_rate
            * np.sinc(2.0 * cutoff_hz / source_rate * n)
        )
        coefficients *= np.hamming(ntaps)
        coefficients /= np.sum(coefficients)
        self._coefficients = coefficients.astype(np.float64)
        self._state = np.zeros(ntaps - 1, dtype=np.float64)
        self._phase = 0

    def process(self, samples):
        values = np.asarray(samples, dtype=np.float64)
        combined = np.concatenate((self._state, values))
        filtered = np.convolve(combined, self._coefficients)[
            self._ntaps - 1 : self._ntaps - 1 + values.size
        ]
        self._state = combined[-(self._ntaps - 1) :]
        output = filtered[self._phase :: self.factor]
        self._phase = (self._phase - values.size) % self.factor
        return np.clip(np.rint(output), -32768, 32767).astype(np.int16)


@dataclass(frozen=True)
class RecordingResult:
    """Rendered PCM and metadata for one completed recording session."""

    pcm: np.ndarray
    freq: int
    started_at: datetime
    duration: float


class RecordingSession:
    """Collect timestamped RX/TX PCM blocks on one mono timeline."""

    VALID_SOURCES = frozenset(("rx", "tx"))

    def __init__(self, sample_rate=16000, max_seconds=3600):
        self.sample_rate = int(sample_rate)
        self.max_seconds = float(max_seconds)
        self._max_samples = int(self.sample_rate * self.max_seconds)
        self._lock = threading.Lock()
        self._active = False
        self._start_ns = None
        self._started_at = None
        self._freq = 0
        self._events = []
        self._resamplers = {}

    def start(self, freq=0, now_ns=None):
        """Start a new session; return False if one is already active."""
        timestamp_ns = time.monotonic_ns() if now_ns is None else int(now_ns)
        with self._lock:
            if self._active:
                return False
            self._active = True
            self._start_ns = timestamp_ns
            self._started_at = datetime.now()
            self._freq = int(freq)
            self._events = []
            self._resamplers = {}
            return True

    def add_audio(self, source, pcm, source_rate, timestamp_ns=None):
        """Add one PCM block at its real position on the session timeline."""
        if source not in self.VALID_SOURCES:
            raise ValueError("source must be 'rx' or 'tx'")
        if int(source_rate) <= 0:
            raise ValueError("source_rate must be positive")

        samples = np.asarray(pcm, dtype=np.int16).reshape(-1).copy()
        timestamp_ns = time.monotonic_ns() if timestamp_ns is None else int(timestamp_ns)
        with self._lock:
            if not self._active or samples.size == 0:
                return False
            start_ns = self._start_ns
            if start_ns is None:
                return False
            source_rate = int(source_rate)
            if source_rate != self.sample_rate:
                resampler_key = (source, source_rate)
                resampler = self._resamplers.get(resampler_key)
                if resampler is None:
                    resampler = _StreamingDecimator(source_rate, self.sample_rate)
                    self._resamplers[resampler_key] = resampler
                samples = resampler.process(samples)
            sample_offset = max(
                0,
                (timestamp_ns - start_ns) * self.sample_rate // 1_000_000_000,
            )
            if sample_offset >= self._max_samples:
                return False
            samples = samples[: self._max_samples - sample_offset]
            self._events.append((source, sample_offset, samples))
            return True

    def stop(self, now_ns=None):
        """Finish and render the active session, or return None if inactive."""
        timestamp_ns = time.monotonic_ns() if now_ns is None else int(now_ns)
        with self._lock:
            if not self._active:
                return None
            start_ns = self._start_ns
            started_at = self._started_at
            if start_ns is None or started_at is None:
                return None
            stop_sample = max(
                0,
                (timestamp_ns - start_ns) * self.sample_rate // 1_000_000_000,
            )
            stop_sample = min(stop_sample, self._max_samples)
            events = self._events
            freq = self._freq
            self._active = False
            self._events = []
            self._resamplers = {}
            self._start_ns = None
            self._started_at = None
            self._freq = 0

        event_end = max((offset + len(samples) for _, offset, samples in events), default=0)
        output_size = min(max(stop_sample, event_end), self._max_samples)
        output = np.zeros(output_size, dtype=np.int16)
        for wanted_source in ("rx", "tx"):
            for source, offset, samples in events:
                if source != wanted_source or offset >= output_size:
                    continue
                end = min(offset + len(samples), output_size)
                output[offset:end] = samples[: end - offset]

        return RecordingResult(
            pcm=output,
            freq=freq,
            started_at=started_at,
            duration=output_size / self.sample_rate,
        )

    def status(self, now_ns=None):
        """Return a snapshot compatible with MRRC's recording status API."""
        timestamp_ns = time.monotonic_ns() if now_ns is None else int(now_ns)
        with self._lock:
            duration = 0.0
            if self._active and self._start_ns is not None:
                duration = max(0.0, (timestamp_ns - self._start_ns) / 1_000_000_000)
            return {
                "recording": self._active,
                "freq": self._freq,
                "start_time": self._started_at.isoformat() if self._started_at else None,
                "duration": duration,
                "buffer_size": sum(len(samples) for _, _, samples in self._events),
            }

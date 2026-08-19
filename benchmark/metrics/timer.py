"""
High-Resolution Precision Timer
Uses time.perf_counter_ns() to avoid float precision loss during sub-millisecond benchmarking.
"""

import time
from typing import Optional


class HighResolutionTimer:
    def __init__(self):
        self._start_ns: Optional[int] = None
        self._end_ns: Optional[int] = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self) -> None:
        self._start_ns = time.perf_counter_ns()
        self._end_ns = None

    def stop(self) -> int:
        self._end_ns = time.perf_counter_ns()
        if self._start_ns is None:
            raise RuntimeError("Timer was stopped before being started.")
        return self.elapsed_ns

    @property
    def elapsed_ns(self) -> int:
        if self._start_ns is None:
            return 0
        if self._end_ns is None:
            return time.perf_counter_ns() - self._start_ns
        return self._end_ns - self._start_ns

    @property
    def elapsed_ms(self) -> float:
        return self.elapsed_ns / 1_000_000.0

    @property
    def elapsed_sec(self) -> float:
        return self.elapsed_ns / 1_000_000_000.0

"""Aggregate, process-local performance diagnostics for Memory Review."""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager

logger = logging.getLogger(__name__)
_lock = threading.RLock()
_timings: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=50))
_counters: dict[str, int] = defaultdict(int)


@contextmanager
def measure_memory_review(name: str, *, items: int = 0):
    """Measure one aggregate UI operation without producing per-photo logs."""
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - started) * 1000.0
        with _lock:
            _timings[name].append(elapsed)
        logger.info("[PERF] Memory Review %s %.1f ms items=%d thread=%s",
                    name, elapsed, items, threading.current_thread().name)


def increment_memory_review_counter(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] += int(amount)


def record_memory_review(name: str, elapsed_ms: float, *, items: int = 0) -> None:
    with _lock:
        _timings[name].append(max(0.0, float(elapsed_ms)))
    logger.info("[PERF] Memory Review %s %.1f ms items=%d thread=%s",
                name, elapsed_ms, items, threading.current_thread().name)


def memory_review_performance_snapshot() -> dict[str, object]:
    with _lock:
        timings = {
            name: {"count": len(values), "last_ms": values[-1],
                   "average_ms": sum(values) / len(values), "max_ms": max(values)}
            for name, values in _timings.items() if values
        }
        return {"timings": timings, "counters": dict(_counters)}


def clear_memory_review_performance() -> None:
    with _lock:
        _timings.clear()
        _counters.clear()

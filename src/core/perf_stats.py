"""Low-overhead, thread-safe import performance profiling.

The profiler deliberately records aggregate spans only.  It neither repeats
work nor emits per-photo messages, so measurements describe the real import.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import sys
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class PerformanceStage:
    name: str
    start_time: float
    end_time: float
    elapsed_ms: float
    item_count: int = 0
    thread_kind: str = "background"

    @property
    def average_ms_per_item(self) -> float | None:
        return self.elapsed_ms / self.item_count if self.item_count else None

    def to_dict(self, total_ms: float = 0.0) -> dict[str, object]:
        value = asdict(self)
        value["average_ms_per_item"] = self.average_ms_per_item
        value["percentage_of_total"] = self.elapsed_ms * 100 / total_ms if total_ms else 0.0
        return value


class ImportPerformanceSession:
    """One import's monotonic timings and aggregate diagnostics."""

    def __init__(self, source_root: str | None = None) -> None:
        self.session_id = str(uuid4())
        self.source_root = source_root
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.started_at = time.perf_counter()
        self.ended_at: float | None = None
        self._stages: list[PerformanceStage] = []
        self._active: dict[str, tuple[float, str]] = {}
        self._counters: dict[str, int] = {}
        self._lock = threading.RLock()

    def start(self, name: str, *, thread_kind: str | None = None) -> None:
        with self._lock:
            self._active[name] = (time.perf_counter(), thread_kind or _thread_kind())

    def stop(self, name: str, item_count: int = 0) -> float:
        end = time.perf_counter()
        with self._lock:
            active = self._active.pop(name, None)
            if active is None:
                return 0.0
            start, kind = active
            return self._append(name, start, end, item_count, kind)

    def record(self, name: str, elapsed_ms: float, item_count: int = 0,
               thread_kind: str | None = None) -> None:
        end = time.perf_counter()
        with self._lock:
            self._append(name, end - float(elapsed_ms) / 1000, end,
                         item_count, thread_kind or _thread_kind())

    def _append(self, name: str, start: float, end: float, count: int, kind: str) -> float:
        elapsed = max(0.0, (end - start) * 1000)
        self._stages.append(PerformanceStage(name, start, end, elapsed, int(count), kind))
        logger.info("[PERF] %s %.1f ms items=%s thread=%s", name, elapsed, count, kind)
        return elapsed

    @contextmanager
    def measure(self, name: str, item_count: int = 0,
                thread_kind: str | None = None) -> Iterator[None]:
        self.start(name, thread_kind=thread_kind)
        try:
            yield
        finally:
            self.stop(name, item_count)

    def inc(self, key: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + int(amount)

    def get_counter(self, key: str) -> int:
        with self._lock:
            return self._counters.get(key, 0)

    @property
    def stages(self) -> tuple[PerformanceStage, ...]:
        with self._lock:
            return tuple(self._stages)

    @property
    def counters(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)

    @property
    def total_ms(self) -> float:
        end = self.ended_at or time.perf_counter()
        return max(0.0, (end - self.started_at) * 1000)

    def finish(self) -> None:
        with self._lock:
            if self.ended_at is None:
                self.ended_at = time.perf_counter()
                self.record("Total import time", self.total_ms, self.get_counter("processed_photos"), "UI thread")

    def identify_bottleneck(self) -> Optional[str]:
        candidates = [stage for stage in self.stages if stage.name != "Total import time"]
        return max(candidates, key=lambda stage: stage.elapsed_ms).name if candidates else None

    def summary(self) -> str:
        lines = [f"[PERF] Import session {self.session_id} total={self.total_ms:.1f} ms"]
        bottleneck = self.identify_bottleneck()
        lines.extend(
            f"[PERF] {s.name} {s.elapsed_ms:.1f} ms items={s.item_count}"
            f"{'  ← BOTTLENECK' if s.name == bottleneck else ''}" for s in self.stages)
        return "\n".join(lines)

    def print_summary(self) -> None:
        logger.info(self.summary())

    def reset(self) -> None:
        with self._lock:
            self.started_at = time.perf_counter(); self.ended_at = None
            self._stages.clear(); self._active.clear(); self._counters.clear()

    def to_dict(self, library_size: int | None = None) -> dict[str, object]:
        total = self.total_ms
        return {
            "session_id": self.session_id, "created_at": self.created_at,
            "source_root": self.source_root, "total_time_ms": total,
            "library_size": library_size if library_size is not None else self.get_counter("processed_photos"),
            "slowest_stage": self.identify_bottleneck(),
            "timings": [stage.to_dict(total) for stage in self.stages],
            "diagnostics": self.counters,
        }


PerfStats = ImportPerformanceSession  # compatibility for existing callers/tests
_lock = threading.RLock()
_session = ImportPerformanceSession()
_history: deque[ImportPerformanceSession] = deque(maxlen=20)


def begin_import_performance_session(source_root: str | None = None) -> ImportPerformanceSession:
    global _session
    with _lock:
        _session = ImportPerformanceSession(source_root)
        return _session


def finish_import_performance_session() -> ImportPerformanceSession:
    with _lock:
        _session.finish()
        if not _history or _history[-1] is not _session:
            _history.append(_session)
        return _session


def get_session_stats() -> ImportPerformanceSession:
    with _lock:
        return _session


def reset_session_stats() -> None:
    begin_import_performance_session()


def performance_history() -> tuple[ImportPerformanceSession, ...]:
    with _lock:
        return tuple(_history)


def clear_performance_history() -> None:
    with _lock:
        _history.clear()


def performance_report(session: ImportPerformanceSession | None = None,
                       library_size: int | None = None) -> dict[str, object]:
    selected = session or (_history[-1] if _history else _session)
    return {
        "report_version": 1,
        "hardware_info": {"machine": platform.machine(), "processor": platform.processor()},
        "os": {"system": platform.system(), "release": platform.release(), "version": platform.version()},
        "cpu_count": os.cpu_count(), "python_version": sys.version,
        **selected.to_dict(library_size),
        "stage_breakdown": selected.to_dict(library_size)["timings"],
        "future_optimization_hints": [
            "Investigate the slowest measured stage in PERF-001B.",
            "Compare first and incremental imports before changing algorithms.",
        ],
    }


def export_performance_report(path: str | Path, session: ImportPerformanceSession | None = None,
                              library_size: int | None = None) -> Path:
    destination = Path(path)
    destination.write_text(json.dumps(performance_report(session, library_size), indent=2), encoding="utf-8")
    return destination


def _thread_kind() -> str:
    return "UI thread" if threading.current_thread() is threading.main_thread() else "Background thread"

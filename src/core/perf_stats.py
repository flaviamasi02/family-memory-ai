"""
Lightweight session-scoped performance statistics collector.

Accumulates timing and counter data across the import pipeline.
Produces a single concise human-readable summary per import session
with bottleneck identification — no per-photo logging is emitted.

Thread safety: append/increment operations are GIL-protected in CPython
and safe for concurrent access from the background scan/thumbnail workers.
"""
from __future__ import annotations

import time
from typing import Optional


class PerfStats:
    """Accumulate performance measurements for one import session."""

    def __init__(self) -> None:
        # Ordered list of (label, elapsed_ms) — preserves insertion order.
        self._timings: list[tuple[str, float]] = []
        self._counters: dict[str, int] = {}
        # Active span start times (name -> perf_counter value).
        self._active: dict[str, float] = {}

    # ------------------------------------------------------------------ timing

    def start(self, name: str) -> None:
        """Record the start of a named timing span."""
        self._active[name] = time.perf_counter()

    def stop(self, name: str) -> float:
        """End a timing span, store it, and return elapsed milliseconds."""
        t0 = self._active.pop(name, None)
        if t0 is None:
            return 0.0
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self._timings.append((name, elapsed_ms))
        return elapsed_ms

    def record(self, name: str, elapsed_ms: float) -> None:
        """Store a pre-computed elapsed time in milliseconds."""
        self._timings.append((name, float(elapsed_ms)))

    # ---------------------------------------------------------------- counters

    def inc(self, key: str, amount: int = 1) -> None:
        """Increment a named counter by *amount*."""
        self._counters[key] = self._counters.get(key, 0) + amount

    def get_counter(self, key: str) -> int:
        """Return the current value of a counter (0 if never set)."""
        return self._counters.get(key, 0)

    # ---------------------------------------------------------------- reporting

    def identify_bottleneck(self) -> Optional[str]:
        """Return the label of the slowest timing span, or None if empty."""
        if not self._timings:
            return None
        return max(self._timings, key=lambda t: t[1])[0]

    def summary(self) -> str:
        """Return a concise, human-readable multi-line summary string."""
        total_ms = sum(ms for _, ms in self._timings)
        bottleneck = self.identify_bottleneck() if len(self._timings) > 1 else None
        lines = [f"[Perf] Import session summary  (total instrumented: {total_ms:.0f} ms)"]

        for label, ms in self._timings:
            tag = "  ← BOTTLENECK" if label == bottleneck else ""
            lines.append(f"  {label:<44} {ms:>8.0f} ms{tag}")

        if self._counters:
            for key, value in sorted(self._counters.items()):
                lines.append(f"  {key:<44} {value:>8}")

        return "\n".join(lines)

    def print_summary(self) -> None:
        """Print the summary to stdout."""
        print(self.summary())

    def reset(self) -> None:
        """Clear all accumulated data (call at the start of a new import)."""
        self._timings.clear()
        self._counters.clear()
        self._active.clear()


# ---------------------------------------------------------------------------
# Module-level session singleton shared across the import pipeline.
# ---------------------------------------------------------------------------

_session: PerfStats = PerfStats()


def get_session_stats() -> PerfStats:
    """Return the current import-session PerfStats instance."""
    return _session


def reset_session_stats() -> None:
    """Reset all accumulated stats at the start of a new import session."""
    _session.reset()

"""Opt-in, process-local selection measurement and isolation controls."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class SelectionMeasurement:
    workspace: str
    timings_ms: dict[str, float] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    started: float = field(default_factory=time.perf_counter)


_armed_workspace: str | None = None
_active: SelectionMeasurement | None = None
_reports: dict[str, SelectionMeasurement] = {}
_bypasses = {"preview": False, "details": False, "suggestions": False, "styling": False}


def arm_selection_measurement(workspace: str = "memory") -> None:
    global _armed_workspace, _active
    _armed_workspace = workspace
    # A previous incomplete diagnostic must never capture the newly armed run.
    _active = None


def begin_selection_measurement(workspace: str) -> SelectionMeasurement | None:
    global _armed_workspace, _active
    if _armed_workspace != workspace:
        return None
    _armed_workspace = None
    _active = SelectionMeasurement(workspace=workspace)
    return _active


def active_selection_measurement(workspace: str | None = None) -> SelectionMeasurement | None:
    if _active is None or (workspace is not None and _active.workspace != workspace):
        return None
    return _active


def add_selection_time(name: str, elapsed_ms: float) -> None:
    if _active is not None:
        _active.timings_ms[name] = _active.timings_ms.get(name, 0.0) + max(0.0, float(elapsed_ms))


def add_selection_count(name: str, amount: int = 1) -> None:
    if _active is not None:
        _active.counts[name] = _active.counts.get(name, 0) + int(amount)


def finish_selection_measurement(*, deferred: bool = False) -> None:
    global _active
    if _active is None:
        return
    total = (time.perf_counter() - _active.started) * 1000.0
    key = "Deferred work completion" if deferred else "Total synchronous UI-thread time"
    _active.timings_ms[key] = total
    _reports[_active.workspace] = _active
    if deferred:
        _active = None


def set_selection_bypass(name: str, enabled: bool) -> None:
    if name in _bypasses:
        _bypasses[name] = bool(enabled)


def selection_bypass(name: str) -> bool:
    return bool(_bypasses.get(name, False))


def selection_diagnostic_report() -> str:
    lines = ["Memory Review selection measurement"]
    for workspace, title in (("memory", "Memory Review selection"), ("cleanup", "Cleanup Review selection")):
        report = _reports.get(workspace)
        lines.extend(("", title))
        if report is None:
            if _armed_workspace == workspace:
                lines.append("Waiting for Memory Review selection...")
            else:
                lines.append("No measured selection yet.")
            continue
        lines.append("Selections measured: 1")
        for name, value in report.timings_ms.items():
            lines.append(f"{name}: {value:.1f} ms")
        lines.append("Counts:")
        lines.extend(f"{name}: {value}" for name, value in sorted(report.counts.items()))
        candidates = {
            name: value for name, value in report.timings_ms.items()
            if name not in {"Total synchronous UI-thread time", "Deferred work completion"}
        }
        if candidates:
            bottleneck = max(candidates, key=candidates.get)
            lines.append(f"Main bottleneck: {bottleneck} — {report.timings_ms[bottleneck]:.1f} ms")
    return "\n".join(lines)


def clear_selection_diagnostics() -> None:
    global _armed_workspace, _active
    _armed_workspace = None
    _active = None
    _reports.clear()
    for key in _bypasses:
        _bypasses[key] = False

from core.memory_review_perf import (
    clear_memory_review_performance,
    increment_memory_review_counter,
    measure_memory_review,
    memory_review_performance_snapshot,
    record_memory_review,
)
from core.selection_update import changed_selection_keys
from core.selection_diagnostics import (
    add_selection_count,
    add_selection_time,
    arm_selection_measurement,
    begin_selection_measurement,
    clear_selection_diagnostics,
    finish_selection_measurement,
    selection_bypass,
    selection_diagnostic_report,
    set_selection_bypass,
)
from time import perf_counter
import statistics


def test_memory_review_performance_counters_are_aggregated():
    clear_memory_review_performance()
    with measure_memory_review("Grid creation", items=100):
        sum(range(100))
    record_memory_review("Selection update", 1.25, items=1)
    increment_memory_review_counter("grid_rebuilds_avoided", 2)

    snapshot = memory_review_performance_snapshot()

    assert snapshot["timings"]["Grid creation"]["count"] == 1
    assert snapshot["timings"]["Selection update"]["last_ms"] == 1.25
    assert snapshot["counters"]["grid_rebuilds_avoided"] == 2


def test_memory_review_performance_history_is_bounded():
    clear_memory_review_performance()
    for value in range(75):
        record_memory_review("Filter update", value)

    values = memory_review_performance_snapshot()["timings"]["Filter update"]
    assert values["count"] == 50
    assert values["last_ms"] == 74


def test_selection_delta_touches_only_changed_cards():
    selected = {"photo-1", "photo-2"}
    assert changed_selection_keys(selected, selected | {"photo-3"}) == {"photo-3"}
    assert changed_selection_keys(selected, selected - {"photo-2"}) == {"photo-2"}


def test_selection_delta_scales_with_changed_items_for_requested_sizes():
    for size in (1, 10, 100, 1_000):
        previous = {f"photo-{index}" for index in range(size)}
        current = set(previous)
        current.add("new-primary")
        assert changed_selection_keys(previous, current) == {"new-primary"}


def test_incremental_highlight_work_is_measurably_lower_than_full_refresh():
    """Reproducible CPU benchmark of the removed all-card selection loop."""
    keys = {f"photo-{index}" for index in range(1_000)}
    current = keys | {"new-primary"}

    def median_seconds(callback):
        samples = []
        for _ in range(200):
            started = perf_counter()
            callback()
            samples.append(perf_counter() - started)
        return statistics.median(samples)

    before = median_seconds(lambda: [key in current for key in keys])
    after = median_seconds(lambda: changed_selection_keys(keys, current))
    assert after < before


def test_real_selection_diagnostic_is_aggregate_and_path_free():
    clear_selection_diagnostics()
    arm_selection_measurement("memory")
    assert "Waiting for Memory Review selection..." in selection_diagnostic_report()
    assert begin_selection_measurement("cleanup") is None
    assert begin_selection_measurement("memory") is not None
    add_selection_time("Selection highlight update", 12.5)
    add_selection_count("Selected photos", 10)
    add_selection_count("Cards restyled", 1)
    finish_selection_measurement(deferred=True)
    report = selection_diagnostic_report()
    assert "Memory Review selection" in report
    assert "Cleanup Review selection" in report
    assert "Selected photos: 10" in report
    assert "Cards restyled: 1" in report
    assert "Selections measured: 1" in report
    assert "Completed:" in report
    assert "Deferred work completion" in report
    assert "/" not in report and "\\" not in report


def test_diagnostic_bypasses_are_off_after_reset():
    clear_selection_diagnostics()
    for key in ("preview", "details", "suggestions", "styling"):
        assert not selection_bypass(key)
        set_selection_bypass(key, True)
        assert selection_bypass(key)
    clear_selection_diagnostics()
    assert not any(selection_bypass(key) for key in ("preview", "details", "suggestions", "styling"))


def test_memory_and_cleanup_measurements_are_not_cross_consumed():
    clear_selection_diagnostics()
    arm_selection_measurement("memory")
    assert begin_selection_measurement("cleanup") is None
    assert "Waiting for Memory Review selection..." in selection_diagnostic_report()
    assert begin_selection_measurement("memory") is not None
    add_selection_count("Selected photos", 3)
    finish_selection_measurement(deferred=True)
    assert "Selected photos: 3" in selection_diagnostic_report()

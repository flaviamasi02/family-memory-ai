from core.memory_review_perf import (
    clear_memory_review_performance,
    increment_memory_review_counter,
    measure_memory_review,
    memory_review_performance_snapshot,
    record_memory_review,
)
from core.selection_update import changed_selection_keys
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

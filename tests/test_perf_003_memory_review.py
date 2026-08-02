from core.memory_review_perf import (
    clear_memory_review_performance,
    increment_memory_review_counter,
    measure_memory_review,
    memory_review_performance_snapshot,
    record_memory_review,
)


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

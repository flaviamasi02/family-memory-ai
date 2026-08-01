import json
import threading
import time

from core.perf_stats import (
    ImportPerformanceSession,
    begin_import_performance_session,
    clear_performance_history,
    export_performance_report,
    finish_import_performance_session,
    performance_history,
)


def test_session_lifecycle_collects_precise_stage_statistics():
    session = ImportPerformanceSession("/photos")
    session.start("Filesystem scan", thread_kind="Background thread")
    time.sleep(0.001)
    elapsed = session.stop("Filesystem scan", 2)
    session.finish()

    stage = session.stages[0]
    assert elapsed > 0
    assert stage.end_time >= stage.start_time
    assert stage.item_count == 2
    assert stage.average_ms_per_item == stage.elapsed_ms / 2
    assert session.total_ms > 0


def test_history_keeps_only_last_twenty_imports():
    clear_performance_history()
    ids = []
    for _ in range(25):
        ids.append(begin_import_performance_session().session_id)
        finish_import_performance_session()
    assert len(performance_history()) == 20
    assert performance_history()[0].session_id == ids[5]


def test_json_export_contains_environment_breakdown_and_hints(tmp_path):
    session = ImportPerformanceSession()
    session.record("SQLite reads", 4.5, 3)
    session.inc("processed_photos", 3)
    session.finish()
    output = export_performance_report(tmp_path / "report.json", session)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["cpu_count"] is not None
    assert report["python_version"]
    assert report["library_size"] == 3
    assert report["stage_breakdown"]
    assert report["future_optimization_hints"]


def test_zero_photo_session_and_thread_safe_worker_aggregation():
    session = ImportPerformanceSession()

    def record_worker():
        for _ in range(100):
            session.inc("thumbnails_generated")
            session.record("ThumbnailWorker", 0.1, 0, "Background thread")

    threads = [threading.Thread(target=record_worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    session.finish()
    assert session.get_counter("processed_photos") == 0
    assert session.get_counter("thumbnails_generated") == 400
    assert len([s for s in session.stages if s.name == "ThumbnailWorker"]) == 400


def test_repeated_and_incremental_import_counters_are_independent():
    first = begin_import_performance_session("/same")
    first.inc("processed_photos", 10)
    finish_import_performance_session()
    second = begin_import_performance_session("/same")
    second.inc("processed_photos", 10)
    second.inc("reused_photos", 9)
    finish_import_performance_session()
    assert first.get_counter("reused_photos") == 0
    assert second.get_counter("reused_photos") == 9

from __future__ import annotations

import time
from threading import Thread
from pathlib import Path

from PySide6.QtWidgets import QApplication

from models.photo import Photo
from ui.main_window import MainWindow
from vision.batch_embedding_service import BatchEmbeddingService
from vision.embedding_provider import EmbeddingStore, FakeEmbeddingProvider
from workers.embedding_worker import EmbeddingWorker
from workers.scan_worker import ScanCompletion

JPEG_BYTES = bytes.fromhex("ffd8ffe000104a46494600010101006000600000ffdb0043000302020302020303030304030304050805050404050a070706080c0a0c0c0b0a0b0b0d0e12100d0e110e0b0b1016101113141515150c0f171816141812141514ffdb00430103040405040509050509140d0b0d141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414ffc00011080001000103012200021101031101ffc4001400010000000000000000000000000000000000000008ffc40014100100000000000000000000000000000000000000ffda000c03010002110311003f00b2c001ffd9")


def image(path: Path, marker: bytes = b"a") -> Path:
    path.write_bytes(JPEG_BYTES + marker)
    return path


def photo(path: Path) -> Photo:
    return Photo.from_path(path)


def test_import_worker_generates_embeddings_skips_unchanged_and_reuses_cache(tmp_path):
    p1 = image(tmp_path / "one.jpg")
    p2 = image(tmp_path / "two.jpg")
    db = tmp_path / "embeddings.sqlite3"
    provider = FakeEmbeddingProvider()
    service = BatchEmbeddingService(provider, EmbeddingStore(db))

    worker = EmbeddingWorker([photo(p1), photo(p2)], service_factory=lambda: service)
    completed = []
    worker.complete.connect(lambda _run_id, result: completed.append(result))
    worker.run()

    assert completed[-1].processed_successfully == 2
    assert len(completed) == 1
    assert provider.load_count == 1
    assert provider.embed_call_count == 2
    assert EmbeddingStore(db).get_valid(p1, provider.metadata) is not None

    second_provider = FakeEmbeddingProvider()
    second_service = BatchEmbeddingService(second_provider, EmbeddingStore(db))
    second = EmbeddingWorker([photo(p1), photo(p2)], service_factory=lambda: second_service)
    second_results = []
    second.complete.connect(lambda _run_id, result: second_results.append(result))
    second.run()

    assert second_results[-1].total_images_received == 2
    assert len(second_results) == 1
    assert second_results[-1].skipped_cached == 2
    assert second_provider.embed_call_count == 0


def test_repeated_imports_reopen_store_and_remain_cache_only(tmp_path):
    paths = [image(tmp_path / f"repeat-{index}.jpg", str(index).encode()) for index in range(4)]
    db = tmp_path / "embeddings.sqlite3"
    first_provider = FakeEmbeddingProvider()
    first = BatchEmbeddingService(first_provider, EmbeddingStore(db)).embed_images(paths)

    assert first.processed_successfully == 4
    assert first.skipped_cached == 0
    assert first.failed == 0

    for _ in range(3):
        provider = FakeEmbeddingProvider()
        # Production creates a service and reopens the persistent store for
        # every worker run; repeat that lifecycle rather than reusing objects.
        result = BatchEmbeddingService(provider, EmbeddingStore(db)).embed_images(paths)
        assert result.total_images_received == 4
        assert result.processed_successfully == 0
        assert result.skipped_cached == 4
        assert result.failed == 0
        assert result.cancelled == 0
        assert provider.load_count == 0
        assert provider.embed_call_count == 0


def test_422_cached_inputs_reach_one_terminal_result_with_timeout(tmp_path):
    paths = [image(tmp_path / f"cached-{index}.jpg", str(index).encode()) for index in range(422)]
    db = tmp_path / "embeddings.sqlite3"
    seeded = BatchEmbeddingService(FakeEmbeddingProvider(), EmbeddingStore(db)).embed_images(paths)
    assert seeded.processed_successfully == 422

    results = []
    provider = FakeEmbeddingProvider()
    thread = Thread(
        target=lambda: results.append(BatchEmbeddingService(provider, EmbeddingStore(db)).embed_images(paths)),
        daemon=True,
    )
    thread.start()
    thread.join(10)

    assert not thread.is_alive(), "cached indexing stalled before its terminal result"
    assert len(results) == 1
    result = results[0]
    assert (result.processed_successfully, result.skipped_cached, result.failed, result.cancelled) == (0, 422, 0, 0)
    assert provider.load_count == provider.embed_call_count == 0


def test_cached_final_partial_batch_and_missing_path_are_accounted(tmp_path):
    paths = [image(tmp_path / f"odd-{index}.jpg", str(index).encode()) for index in range(17)]
    missing = tmp_path / "missing.jpg"
    db = tmp_path / "embeddings.sqlite3"
    assert BatchEmbeddingService(FakeEmbeddingProvider(), EmbeddingStore(db)).embed_images(paths).processed_successfully == 17

    result = BatchEmbeddingService(FakeEmbeddingProvider(), EmbeddingStore(db)).embed_images([*paths, missing])

    assert result.total_images_received == 18
    assert (result.processed_successfully, result.skipped_cached, result.failed, result.cancelled) == (0, 17, 1, 0)


def test_changed_image_is_regenerated_but_unchanged_image_is_skipped(tmp_path):
    p1 = image(tmp_path / "changed.jpg", b"old")
    p2 = image(tmp_path / "same.jpg", b"same")
    db = tmp_path / "embeddings.sqlite3"
    provider = FakeEmbeddingProvider()
    service = BatchEmbeddingService(provider, EmbeddingStore(db))
    assert service.embed_images([p1, p2]).processed_successfully == 2
    calls = provider.embed_call_count

    time.sleep(0.01)
    image(p1, b"new")
    worker = EmbeddingWorker([photo(p1), photo(p2)], service_factory=lambda: service)
    results = []
    worker.complete.connect(lambda _run_id, result: results.append(result))
    worker.run()

    result = results[-1]
    assert result.total_images_received == 2
    assert result.processed_successfully == 1
    assert result.skipped_cached == 1
    assert result.failed == 0
    assert result.cancelled == 0
    assert provider.embed_call_count == calls + 1


def test_embedding_worker_supports_cancellation_and_progress(tmp_path):
    paths = [image(tmp_path / f"{i}.jpg", str(i).encode()) for i in range(3)]
    provider = FakeEmbeddingProvider()
    service = BatchEmbeddingService(provider, EmbeddingStore(tmp_path / "embeddings.sqlite3"))
    worker = EmbeddingWorker([photo(p) for p in paths], service_factory=lambda: service)
    progress = []
    results = []

    def on_progress(_run_id, item):
        progress.append(item)
        worker.cancel()

    worker.progress.connect(on_progress)
    worker.complete.connect(lambda _run_id, result: results.append(result))
    worker.run()

    assert len(progress) == 1
    assert progress[0].current_index == 1
    assert results[-1].processed_successfully == 1
    assert len(results) == 1
    assert results[-1].cancelled == 2


def test_main_window_startup_succeeds_and_scan_complete_starts_embedding_indexing(monkeypatch):
    QApplication.instance() or QApplication([])
    started = []

    class FakeThread:
        def __init__(self):
            self.started = _Signal()
            self.finished = _Signal()

        def start(self):
            started.append("started")

        def isRunning(self):
            return False

        def quit(self):
            pass

        def wait(self, _ms):
            pass

        def deleteLater(self):
            pass

    class FakeWorker:
        def __init__(self, photos, service_factory=None, run_id=0):
            self.photos = photos
            self.service_factory = service_factory
            self.progress = _Signal()
            self.complete = _Signal()
            self.error = _Signal()
            self.finished = _Signal()

        def moveToThread(self, _thread):
            pass

        def run(self):
            pass

        def cancel(self):
            pass

        def deleteLater(self):
            pass

    monkeypatch.setattr("ui.main_window.QThread", FakeThread)
    monkeypatch.setattr("ui.main_window.EmbeddingWorker", FakeWorker)
    monkeypatch.setattr(MainWindow, "start_thumbnail_loading", lambda self, photos: self._start_embedding_indexing(photos))
    monkeypatch.setattr(MainWindow, "_deferred_setup_cleanup_review", lambda self: None)
    window = MainWindow()
    window._on_scan_complete([])
    assert started == ["started"]
    assert window.embedding_worker.service_factory is not None
    service = window.embedding_worker.service_factory()
    assert service.provider.runtime_manager is window.ai_runtime_manager


class _Signal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback, *_args):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self._callbacks):
            callback(*args)


def test_slow_worker_is_not_abandoned_and_second_import_waits_for_finish(monkeypatch):
    window = _embedding_window_for_lifecycle_tests()
    threads = []
    workers = []

    class FakeThread:
        def __init__(self):
            self.started = _Signal()
            self.finished = _Signal()
            self.deleted = False
            self.running = False
            threads.append(self)

        def start(self):
            self.running = True

        def isRunning(self):
            return self.running

        def quit(self):
            self.running = False
            self.finished.emit()

        def wait(self, _ms):
            return not self.running

        def deleteLater(self):
            self.deleted = True

    class FakeWorker:
        def __init__(self, photos, service_factory=None, run_id=0):
            self.photos = list(photos)
            self.service_factory = service_factory
            self.progress = _Signal()
            self.complete = _Signal()
            self.error = _Signal()
            self.finished = _Signal()
            self.cancelled = False
            workers.append(self)

        def moveToThread(self, _thread):
            pass

        def run(self):
            pass

        def cancel(self):
            self.cancelled = True

        def deleteLater(self):
            pass

    monkeypatch.setattr("ui.main_window.QThread", FakeThread)
    monkeypatch.setattr("ui.main_window.EmbeddingWorker", FakeWorker)

    window._start_embedding_indexing(["first"])
    first_thread = window.embedding_thread
    first_worker = window.embedding_worker
    window._start_embedding_indexing(["second"])

    assert len(workers) == 1
    assert first_worker.cancelled is True
    assert window.embedding_thread is first_thread
    assert window.embedding_worker is first_worker
    assert window._pending_embedding_photos == ["second"]
    assert first_worker.service_factory is not None
    assert first_worker.service_factory().provider.runtime_manager is window.ai_runtime_manager

    # A real worker emits one terminal result before finished.  This lifecycle
    # test supplies the same contract without running the service.
    window._embedding_run_lifecycle[1]["terminal_state"] = "Cancelled"
    first_worker.finished.emit()

    assert len(workers) == 2
    assert workers[1].photos == ["second"]
    assert workers[1].service_factory is not None
    assert window.embedding_thread is threads[1]
    assert window.embedding_worker is workers[1]


def test_stale_embedding_progress_and_completion_do_not_update_newer_import(capsys):
    window = _embedding_window_for_lifecycle_tests()
    window._active_embedding_run_id = 2
    progress = type(
        "Progress",
        (),
        {
            "current_index": 1,
            "total_count": 1,
            "processed_count": 1,
            "cached_count": 0,
            "failed_count": 0,
        },
    )()
    result = type(
        "Result",
        (),
        {
            "total_images_received": 1,
            "processed_successfully": 1,
            "skipped_cached": 0,
            "failed": 0,
            "cancelled": 0,
            "elapsed_seconds": 0.1,
        },
    )()

    window._on_embedding_progress(1, progress)
    window._on_embedding_complete(1, result)
    window._on_embedding_error(1, "old error")

    assert window.status_label.text == "initial"
    assert "EmbeddingIndex" not in capsys.readouterr().err


def test_embedding_completion_prints_limited_grouped_failure_diagnostics(capsys):
    window = _embedding_window_for_lifecycle_tests()
    window._active_embedding_run_id = 1
    outcomes = [
        type("Outcome", (), {"status": "failed", "image": f"/photos/{index}.jpg", "error_type": "RuntimeError", "error": "model load failed"})()
        for index in range(4)
    ]
    result = type(
        "Result",
        (),
        {
            "total_images_received": 4,
            "processed_successfully": 0,
            "skipped_cached": 0,
            "failed": 4,
            "cancelled": 0,
            "elapsed_seconds": 0.1,
            "outcomes": outcomes,
        },
    )()

    window._on_embedding_complete(1, result)

    err = capsys.readouterr().err
    assert "[EmbeddingIndex] processed=0 cached=0 failed=4 cancelled=0" in err
    assert "failure 1/1 x4" in err
    assert "/photos/0.jpg :: RuntimeError: model load failed" in err


def test_embedding_completion_success_does_not_print_failure_diagnostics(capsys):
    window = _embedding_window_for_lifecycle_tests()
    window._active_embedding_run_id = 1
    result = type(
        "Result",
        (),
        {
            "total_images_received": 1,
            "processed_successfully": 1,
            "skipped_cached": 0,
            "failed": 0,
            "cancelled": 0,
            "elapsed_seconds": 0.1,
            "outcomes": [],
        },
    )()

    window._on_embedding_complete(1, result)

    err = capsys.readouterr().err
    assert "[EmbeddingIndex] processed=1 cached=0 failed=0 cancelled=0" in err
    assert "failure 1/" not in err


def _embedding_result(processed, cached, failed):
    return type(
        "Result",
        (),
        {
            "total_images_received": processed + cached + failed,
            "processed_successfully": processed,
            "skipped_cached": cached,
            "failed": failed,
            "cancelled": 0,
            "elapsed_seconds": 0.1,
            "outcomes": [],
        },
    )()


def test_new_embedding_completion_is_persistent_success():
    window = _embedding_window_for_lifecycle_tests()
    window._active_embedding_run_id = 1

    window._on_embedding_complete(1, _embedding_result(12, 0, 0))

    assert window.ai_status_label.text.startswith(
        "✓ Semantic embedding indexing completed."
    )
    assert "12 new embeddings created · 0 reused · 0 failed" in window.ai_status_label.text


def test_cached_embedding_completion_is_success_not_warning():
    window = _embedding_window_for_lifecycle_tests()
    window._active_embedding_run_id = 1

    window._on_embedding_complete(1, _embedding_result(0, 12, 0))

    assert window.ai_status_label.text.startswith("✓ Semantic embeddings ready: 12/12")
    assert "0 new · 12 reused from cache · 0 failed" in window.ai_status_label.text
    assert "⚠" not in window.ai_status_label.text


def test_incremental_embedding_waits_for_mobileclip_recovery_then_resumes_once(monkeypatch):
    window = _embedding_window_for_lifecycle_tests()
    window.settings_page = type("Settings", (), {"_active_runtime_thread": object()})()
    launched = []
    monkeypatch.setattr(window, "_launch_embedding_worker", launched.append)

    window._start_embedding_indexing(["new-photo"])

    assert launched == []
    assert window._pending_embedding_photos == ["new-photo"]
    assert window.ai_status_label.text == "Waiting for MobileCLIP verification to finish…"

    window.settings_page._active_runtime_thread = None
    window._on_runtime_operation_finished("verify")
    window._on_runtime_operation_finished("verify")
    assert launched == [["new-photo"]]


def test_incremental_reconciliation_preserves_rich_review_domain_object():
    window = _embedding_window_for_lifecycle_tests()
    intelligence = type("Intelligence", (), {"year": 2024})()
    existing = type("Photo", (), {
        "id": "stable-photo", "path": Path("old/photo.jpg"),
        "filename": "photo.jpg", "extension": ".jpg", "file_size": 10,
        "created_at": None, "modified_at": None, "modified_time_ns": 1,
        "sync_state": "added", "previous_path": None,
        "intelligence": intelligence, "user_decision": "keep",
    })()
    incoming = type("Photo", (), {
        "id": "stable-photo", "path": Path("new/photo.jpg"),
        "filename": "photo.jpg", "extension": ".jpg", "file_size": 10,
        "created_at": None, "modified_at": None, "modified_time_ns": 2,
        "sync_state": "moved", "previous_path": Path("old/photo.jpg"),
    })()
    window._all_photos = [existing]

    reconciled = window._reconcile_incremental_photos([incoming])

    assert reconciled == [existing]
    assert existing.path == Path("new/photo.jpg")
    assert existing.intelligence.year == 2024
    assert existing.user_decision == "keep"


def test_matching_scan_completion_publishes_even_when_thread_finished_arrives_first():
    window = _embedding_window_for_lifecycle_tests()
    published = []
    discarded = []
    refreshed = []
    window._active_scan_run_id = 0
    window._scan_run_id = 4
    window.application_services = type("Services", (), {
        "publish_active_library": lambda self, value: published.append(value),
        "discard_prepared_library": lambda self, value: discarded.append(value),
    })()
    window.settings_page = type("Settings", (), {
        "refresh_developer_diagnostics": lambda self: refreshed.append(True),
    })()
    library = object()
    summary = object()
    completion = ScanCompletion(4, ["photo"], library, summary)

    assert window._apply_scan_completion(completion) == ["photo"]
    assert published == [library] and refreshed == [True] and discarded == []
    assert window._last_import_result is summary


def test_stale_scan_completion_cannot_replace_newer_active_library():
    window = _embedding_window_for_lifecycle_tests()
    published = []
    discarded = []
    window._active_scan_run_id = 5
    window._scan_run_id = 5
    window.application_services = type("Services", (), {
        "publish_active_library": lambda self, value: published.append(value),
        "discard_prepared_library": lambda self, value: discarded.append(value),
    })()
    window.settings_page = type("Settings", (), {
        "refresh_developer_diagnostics": lambda self: None,
    })()
    stale_library = object()

    assert window._apply_scan_completion(
        ScanCompletion(4, ["stale"], stale_library, object())) is None
    assert published == [] and discarded == [stale_library]


def test_mixed_new_and_cached_embedding_completion_is_success():
    window = _embedding_window_for_lifecycle_tests()
    window._active_embedding_run_id = 1

    window._on_embedding_complete(1, _embedding_result(5, 7, 0))

    assert window.ai_status_label.text.startswith("✓ Semantic embeddings ready: 12/12")
    assert "5 new · 7 reused from cache · 0 failed" in window.ai_status_label.text


def test_embedding_failures_use_warning_or_error_status():
    partial = _embedding_window_for_lifecycle_tests()
    partial._active_embedding_run_id = 1
    partial._on_embedding_complete(1, _embedding_result(5, 6, 1))
    assert partial.ai_status_label.text.startswith("⚠ AI embeddings ready: 11/12")

    complete = _embedding_window_for_lifecycle_tests()
    complete._active_embedding_run_id = 1
    complete._on_embedding_complete(1, _embedding_result(0, 0, 3))
    assert complete.ai_status_label.text.startswith(
        "✕ Semantic embedding indexing failed."
    )


def test_embedding_progress_replaces_previous_ready_state():
    window = _embedding_window_for_lifecycle_tests()
    window._active_embedding_run_id = 1
    window.ai_status_label.setText("✓ Semantic embeddings ready: 12/12")
    progress = type(
        "Progress",
        (),
        {
            "current_index": 3,
            "total_count": 12,
            "processed_count": 3,
            "cached_count": 0,
            "failed_count": 0,
        },
    )()

    window._on_embedding_progress(1, progress)

    assert window.ai_status_label.text.startswith("Indexing semantic embeddings 3/12")


def test_generic_scan_status_does_not_overwrite_embedding_ready_status(monkeypatch):
    window = _embedding_window_for_lifecycle_tests()
    window._active_embedding_run_id = 1
    window._on_embedding_complete(1, _embedding_result(0, 12, 0))

    window.status_label.setText("Found 12 review photos. Loading thumbnails…")

    assert window.ai_status_label.text.startswith("✓ Semantic embeddings ready: 12/12")


def test_starting_new_import_replaces_ready_status(monkeypatch):
    window = _embedding_window_for_lifecycle_tests()
    window.ai_status_label.setText("✓ Semantic embeddings ready: 12/12")
    monkeypatch.setattr(window, "_start_scan", lambda _folder: None)

    window._queue_or_start_scan("/new-import")

    assert window._import_phase == "Preparing"
    assert window.ai_status_label.text == "Scanning changes…"
    assert not window.ai_status_label.text.startswith("✓ Semantic embeddings ready:")


def test_empty_embedding_run_emits_summary_and_clears_preparing_state(capsys):
    window = _embedding_window_for_lifecycle_tests()
    window._active_embedding_run_id = 1

    window._on_embedding_complete(1, _embedding_result(0, 0, 0))

    assert window.ai_status_label.text == "AI embeddings: no eligible photos to index."
    assert "[EmbeddingIndex] processed=0 cached=0 failed=0 cancelled=0" in (
        capsys.readouterr().err
    )


def test_deleted_embedding_thread_wrapper_does_not_block_worker_launch(monkeypatch):
    window = _embedding_window_for_lifecycle_tests()
    launched = []

    class DeletedThread:
        def isRunning(self):
            raise RuntimeError("Internal C++ object already deleted")

    window.embedding_thread = DeletedThread()
    window.embedding_worker = object()
    window._active_embedding_run_id = 4
    window._embedding_run_lifecycle[4] = {"thread_finished": False, "terminal_state": None}
    monkeypatch.setattr(window, "_launch_embedding_worker", launched.append)

    window._start_embedding_indexing(["photo"])

    assert launched == [["photo"]]
    assert window.embedding_thread is None
    assert window.embedding_worker is None
    assert window._active_embedding_run_id == 0
    assert window._embedding_run_lifecycle == {}


def test_close_event_waits_for_running_embedding_thread_before_destroying(monkeypatch):
    window = _embedding_window_for_lifecycle_tests()
    waited = []

    class FakeApp:
        def processEvents(self):
            pass

    class FakeThread:
        def __init__(self):
            self.running = True
            self.quit_called = False

        def isRunning(self):
            return self.running

        def wait(self, ms):
            waited.append(ms)
            self.running = False
            return True

        def quit(self):
            self.quit_called = True

    class FakeWorker:
        def __init__(self):
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

    class FakeBase:
        closed = False

        def closeEvent(self, event):
            FakeBase.closed = True

    thread = FakeThread()
    worker = FakeWorker()
    window.embedding_thread = thread
    window.embedding_worker = worker
    monkeypatch.setattr("ui.main_window.QCoreApplication.instance", lambda: FakeApp())
    monkeypatch.setattr("ui.main_window.QMainWindow.closeEvent", FakeBase.closeEvent)

    window.closeEvent(object())

    assert worker.cancelled is True
    assert waited == [250]
    assert thread.quit_called is False
    assert FakeBase.closed is True


def test_thread_and_worker_references_clear_only_after_thread_completion():
    window = _embedding_window_for_lifecycle_tests()
    thread = object()
    worker = type("Worker", (), {"cancel": lambda self: None})()
    window.embedding_thread = thread
    window.embedding_worker = worker
    window._active_embedding_run_id = 3
    window._embedding_run_lifecycle[3] = {"thread_finished": False, "terminal_state": "Completed"}

    window._request_embedding_worker_cancel()
    assert window.embedding_thread is thread
    assert window.embedding_worker is worker

    window._on_embedding_thread_finished(2)
    assert window.embedding_thread is thread
    assert window.embedding_worker is worker

    window._on_embedding_thread_finished(3)
    assert window.embedding_thread is None
    assert window.embedding_worker is None


def test_second_import_during_embedding_waits_for_cancellation_before_scanning():
    window = _embedding_window_for_lifecycle_tests()
    scans_started = []

    class RunningThread:
        def isRunning(self):
            return True

    class RunningWorker:
        def __init__(self):
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

    worker = RunningWorker()
    window.embedding_thread = RunningThread()
    window.embedding_worker = worker
    window._active_embedding_run_id = 7
    window._embedding_run_lifecycle[7] = {"thread_finished": False, "terminal_state": "Cancelled"}
    window._start_scan = scans_started.append

    window._queue_or_start_scan("/second-folder")

    assert worker.cancelled is True
    assert scans_started == []
    assert window._pending_import_folder_path == "/second-folder"
    assert window.status_label.text == "Queued new import; finishing the current worker…"

    window._on_embedding_thread_finished(7)

    assert scans_started == ["/second-folder"]
    assert window.status_label.text == "Scanning changes…"
    assert window.embedding_thread is None
    assert window.embedding_worker is None


def test_third_import_also_resumes_exactly_once_after_embedding_cleanup():
    window = _embedding_window_for_lifecycle_tests()
    scans_started = []

    class RunningThread:
        def isRunning(self):
            return True

    class RunningWorker:
        def __init__(self):
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

    window._start_scan = scans_started.append
    expected_scans = []
    for run_id, folder in ((1, "/second-folder"), (2, "/third-folder")):
        worker = RunningWorker()
        window.embedding_thread = RunningThread()
        window.embedding_worker = worker
        window._active_embedding_run_id = run_id
        window._embedding_run_lifecycle[run_id] = {"thread_finished": False, "terminal_state": "Cancelled"}

        window._queue_or_start_scan(folder)
        assert worker.cancelled is True
        assert window._pending_import_folder_path == folder
        assert window.status_label.text == "Queued new import; finishing the current worker…"

        window._on_embedding_thread_finished(run_id)
        window._on_embedding_thread_finished(run_id)  # duplicate/stale delivery
        expected_scans.append(folder)
        assert scans_started == expected_scans
        assert window._pending_import_folder_path is None
        assert window.embedding_thread is None
        assert window.embedding_worker is None
        assert window.status_label.text == "Scanning changes…"
        assert window._embedding_close_requested is False


def test_worker_shutdown_does_not_depend_on_queued_gui_delivery():
    source = Path("src/ui/main_window.py").read_text(encoding="utf-8")
    assert source.count(
        "worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)"
    ) == 3


def test_terminal_result_survives_thread_cleanup_overtaking_queued_progress(capsys):
    window = _embedding_window_for_lifecycle_tests()
    run_id = 9
    window._active_embedding_run_id = run_id
    window.embedding_thread = object()
    window.embedding_worker = object()
    window._embedding_run_lifecycle[run_id] = {"thread_finished": False, "terminal_state": None}

    # Reproduce the Product Owner ordering: the worker thread exits while many
    # cache-hit progress events and the terminal result are still queued.
    window._on_embedding_thread_finished(run_id)
    assert window.embedding_worker is not None
    assert window.ai_status_label.text == "initial"

    window._on_embedding_complete_for_run(run_id, _embedding_result(0, 422, 0))

    assert window.embedding_thread is None
    assert window.embedding_worker is None
    assert window._active_embedding_run_id == 0
    assert run_id not in window._embedding_run_lifecycle
    assert window.ai_status_label.text.startswith("✓ Semantic embeddings ready: 422/422")
    assert "processed=0 cached=422 failed=0 cancelled=0" in capsys.readouterr().err


def test_terminal_callback_exception_becomes_explicit_failure(monkeypatch):
    window = _embedding_window_for_lifecycle_tests()
    run_id = 10
    window._active_embedding_run_id = run_id
    window.embedding_thread = object()
    window.embedding_worker = object()
    window._embedding_run_lifecycle[run_id] = {"thread_finished": True, "terminal_state": None}
    monkeypatch.setattr(window, "_on_embedding_complete", lambda *_args: (_ for _ in ()).throw(RuntimeError("callback broke")))

    window._on_embedding_complete_for_run(run_id, _embedding_result(0, 1, 0))

    assert window._import_phase == "Failed"
    assert "completion failed" in window.ai_status_label.text.lower()
    assert window.embedding_thread is None
    assert window.embedding_worker is None


def test_import_state_machine_reaches_embedding_after_thumbnail_completion(monkeypatch):
    window = _embedding_window_for_lifecycle_tests()
    displayed = []
    thumbnail_inputs = []
    embedding_inputs = []
    window.photo_model = type("PhotoModel", (), {"set_photos": lambda self, photos: displayed.append(list(photos))})()
    window._apply_browser_filter = lambda: None
    window._deferred_setup_cleanup_review = lambda: None
    window.start_thumbnail_loading = thumbnail_inputs.append
    window._start_embedding_indexing = embedding_inputs.append
    monkeypatch.setattr("ui.main_window.QTimer.singleShot", lambda _ms, callback: callback())

    window._on_scan_complete(["photo"])

    assert window._import_phase == "Thumbnail generation"
    assert displayed == [["photo"]]
    assert thumbnail_inputs == [["photo"]]
    assert embedding_inputs == []

    thread = object()
    window.thumbnail_thread = thread
    window.thumbnail_worker = object()
    window._active_thumbnail_run_id = 1
    window._thumbnail_import_started_at[1] = 0.0
    window._on_thumbnail_thread_finished(1, thread)

    assert window._import_phase == "Embedding indexing"
    assert embedding_inputs == [["photo"]]
    assert window.ai_status_label.text == "Indexing semantic embeddings: starting…"


def _embedding_window_for_lifecycle_tests():
    window = MainWindow.__new__(MainWindow)
    # MainWindow owns this dependency in production; lifecycle-only tests avoid
    # constructing the full UI but still preserve the worker composition contract.
    window.ai_runtime_manager = object()
    window.application_services = object()
    window.scan_thread = None
    window.scan_worker = None
    window._scan_run_id = 0
    window._active_scan_run_id = 0
    window.embedding_thread = None
    window.embedding_worker = None
    window._embedding_run_id = 0
    window._active_embedding_run_id = 0
    window._pending_embedding_photos = None
    window._embedding_run_lifecycle = {}
    window._pending_import_folder_path = None
    window._embedding_close_requested = False
    window._import_phase = "Idle"
    window._import_generation = 0
    window._current_import_photos = []
    window.thumbnail_thread = None
    window.thumbnail_worker = None
    window._thumbnail_run_id = 0
    window._active_thumbnail_run_id = 0
    window._pending_thumbnail_photos = None
    window._thumbnail_import_started_at = {}
    window._import_wall_t0 = 0.0
    window._first_thumbnail_logged = False
    window.status_label = _StatusLabel()
    window.ai_status_label = _StatusLabel()
    return window


def test_repeated_thumbnail_import_waits_for_prior_worker_shutdown(monkeypatch):
    window = _embedding_window_for_lifecycle_tests()
    threads = []
    workers = []

    class FakeThread:
        def __init__(self):
            self.started = _Signal()
            self.finished = _Signal()
            self.running = False
            threads.append(self)

        def start(self):
            self.running = True

        def isRunning(self):
            return self.running

        def quit(self):
            self.running = False
            self.finished.emit()

        def deleteLater(self):
            pass

    class FakeThumbnailWorker:
        def __init__(self, photos, **_kwargs):
            self.photos = list(photos)
            self.thumbnail_ready = _Signal()
            self.finished = _Signal()
            self.cancelled = False
            workers.append(self)

        def moveToThread(self, _thread):
            pass

        def run(self):
            pass

        def cancel(self):
            self.cancelled = True

        def deleteLater(self):
            pass

    monkeypatch.setattr("ui.main_window.QThread", FakeThread)
    monkeypatch.setattr("ui.main_window.ThumbnailWorker", FakeThumbnailWorker)

    window.start_thumbnail_loading(["first"])
    first_thread = threads[0]
    window.start_thumbnail_loading(["second"])

    assert len(workers) == 1
    assert workers[0].cancelled is True
    assert window.thumbnail_thread is first_thread
    assert window._pending_thumbnail_photos == ["second"]

    workers[0].finished.emit()

    assert len(workers) == 2
    assert workers[1].photos == ["second"]
    assert window.thumbnail_thread is threads[1]
    assert window._import_wall_t0 == 0.0
    assert window._embedding_close_requested is False


def test_superseded_thumbnail_completion_does_not_consume_new_import_timer(monkeypatch):
    window = _embedding_window_for_lifecycle_tests()
    recorded = []
    monkeypatch.setattr("ui.main_window.get_session_stats", lambda: type(
        "Stats", (), {"record": lambda self, name, value: recorded.append((name, value)), "print_summary": lambda self: None}
    )())
    window._thumbnail_import_started_at = {1: 10.0, 2: 20.0}
    window._import_wall_t0 = 20.0

    window._on_thumbnail_worker_finished(1)

    assert window._import_wall_t0 == 20.0
    assert recorded == []
    assert 1 not in window._thumbnail_import_started_at

    monkeypatch.setattr("ui.main_window.time.perf_counter", lambda: 20.5)
    window._on_thumbnail_worker_finished(2)

    assert window._import_wall_t0 == 0.0
    assert recorded == [("total_import_wall_clock [UI]", 500.0)]


class _StatusLabel:
    def __init__(self):
        self.text = "initial"

    def setText(self, text):
        self.text = text


def test_scan_thread_references_clear_after_matching_thread_finishes(monkeypatch):
    window = _embedding_window_for_lifecycle_tests()
    threads = []
    workers = []

    class FakeThread:
        def __init__(self):
            self.started = _Signal()
            self.finished = _Signal()
            self.deleted = False
            self.is_running_called = 0
            threads.append(self)

        def start(self):
            pass

        def isRunning(self):
            self.is_running_called += 1
            return False

        def quit(self):
            pass

        def wait(self, _ms):
            return True

        def deleteLater(self):
            self.deleted = True

    class FakeScanWorker:
        def __init__(self, folder_path, application_services, run_id):
            self.folder_path = folder_path
            self.application_services = application_services
            self.run_id = run_id
            self.scan_complete = _Signal()
            self.scan_error = _Signal()
            self.finished = _Signal()
            workers.append(self)

        def moveToThread(self, _thread):
            pass

        def run(self):
            pass

        def deleteLater(self):
            pass

    monkeypatch.setattr("ui.main_window.QThread", FakeThread)
    monkeypatch.setattr("ui.main_window.ScanWorker", FakeScanWorker)

    window._start_scan("/first")
    first_thread = window.scan_thread
    assert window.scan_worker is workers[0]
    assert workers[0].application_services is window.application_services
    assert workers[0].run_id == 1

    first_thread.finished.emit()

    assert window.scan_thread is None
    assert window.scan_worker is None
    assert window._active_scan_run_id == 0
    assert first_thread.deleted is True

    window._start_scan("/second")
    assert len(workers) == 2
    assert workers[1].folder_path == "/second"
    assert first_thread.is_running_called == 0


def test_stale_scan_finished_signal_cannot_clear_newer_scan():
    window = _embedding_window_for_lifecycle_tests()
    old_thread = object()
    new_thread = object()
    new_worker = object()
    window.scan_thread = new_thread
    window.scan_worker = new_worker
    window._active_scan_run_id = 2

    window._on_scan_thread_finished(1, old_thread)

    assert window.scan_thread is new_thread
    assert window.scan_worker is new_worker
    assert window._active_scan_run_id == 2


def test_deleted_scan_thread_wrapper_is_not_reused_for_second_scan(monkeypatch):
    window = _scan_lifecycle_harness()
    workers = []

    class DeletedThread:
        def __init__(self):
            self.quit_called = False
            self.wait_called = False

        def isRunning(self):
            raise RuntimeError("Internal C++ object already deleted")

        def quit(self):
            self.quit_called = True

        def wait(self, _ms):
            self.wait_called = True
            return True

    class FakeThread:
        def __init__(self):
            self.started = _Signal()
            self.finished = _Signal()
            self.started_called = False

        def start(self):
            self.started_called = True

        def isRunning(self):
            return False

        def quit(self):
            pass

        def wait(self, _ms):
            return True

        def deleteLater(self):
            pass

    class FakeScanWorker:
        def __init__(self, folder_path, application_services, run_id):
            self.folder_path = folder_path
            self.application_services = application_services
            self.run_id = run_id
            self.scan_complete = _Signal()
            self.scan_error = _Signal()
            self.finished = _Signal()
            workers.append(self)

        def moveToThread(self, _thread):
            pass

        def run(self):
            pass

        def deleteLater(self):
            pass

    deleted_thread = DeletedThread()
    window.scan_thread = deleted_thread
    window.scan_worker = object()
    window._active_scan_run_id = 1
    monkeypatch.setattr("ui.main_window.QThread", FakeThread)
    monkeypatch.setattr("ui.main_window.ScanWorker", FakeScanWorker)

    window._start_scan("/second")

    assert len(workers) == 1
    assert workers[0].folder_path == "/second"
    assert workers[0].application_services is window.application_services
    assert workers[0].run_id == 2
    assert window.scan_thread is not deleted_thread
    assert isinstance(window.scan_thread, FakeThread)
    assert window.scan_thread.started_called is True
    assert window.scan_worker is workers[0]
    assert deleted_thread.quit_called is False
    assert deleted_thread.wait_called is False

    second_thread = window.scan_thread
    second_thread.finished.emit()
    assert window.scan_thread is None
    assert window.scan_worker is None

    window._start_scan("/third")
    third_thread = window.scan_thread
    third_worker = window.scan_worker
    assert third_thread is not second_thread
    assert len(workers) == 2
    assert workers[1].folder_path == "/third"

    # A stale/duplicate completion from the second run cannot clear the third.
    window._on_scan_thread_finished(1, second_thread)
    assert window.scan_thread is third_thread
    assert window.scan_worker is third_worker

    third_thread.finished.emit()
    assert window.scan_thread is None
    assert window.scan_worker is None
    assert window._pending_import_folder_path is None
    assert window._import_phase != "Preparing"


def _scan_lifecycle_harness():
    class Harness:
        pass

    window = Harness()
    window.scan_thread = None
    window.scan_worker = None
    window._scan_run_id = 0
    window._active_scan_run_id = 0
    window.application_services = object()
    window._pending_import_folder_path = None
    window._import_phase = "Idle"
    window.sender = lambda: None
    window._start_scan = MainWindow._start_scan.__get__(window, Harness)
    window._scan_thread_is_running = MainWindow._scan_thread_is_running.__get__(window, Harness)
    window._on_active_scan_thread_finished = MainWindow._on_active_scan_thread_finished.__get__(window, Harness)
    window._on_scan_thread_finished = MainWindow._on_scan_thread_finished.__get__(window, Harness)
    window._on_scan_complete = lambda photos: None
    window._on_scan_error = lambda error: None
    return window


def test_second_folder_scan_completion_updates_photo_list_after_first_scan_cleanup(monkeypatch):
    window = _embedding_window_for_lifecycle_tests()
    displayed = []
    thumbnails = []
    deferred = []

    window.photo_model = type("PhotoModel", (), {"set_photos": lambda self, photos: displayed.append(list(photos))})()
    window._apply_browser_filter = lambda: None
    window._start_embedding_indexing = lambda photos: None
    window.start_thumbnail_loading = lambda photos: thumbnails.append(list(photos))
    window._deferred_setup_cleanup_review = lambda: deferred.append(True)
    monkeypatch.setattr("ui.main_window.QTimer.singleShot", lambda _ms, callback: callback())

    window._on_scan_complete(["second-photo"])

    assert window._all_photos == ["second-photo"]
    assert displayed == [["second-photo"]]
    assert thumbnails == [["second-photo"]]
    assert deferred == [True]
    assert window.status_label.text == "Scan complete — showing 1 photos. Loading thumbnails…"

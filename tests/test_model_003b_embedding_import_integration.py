from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from models.photo import Photo
from ui.main_window import MainWindow
from vision.batch_embedding_service import BatchEmbeddingService
from vision.embedding_provider import EmbeddingStore, FakeEmbeddingProvider
from workers.embedding_worker import EmbeddingWorker

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
    worker.complete.connect(completed.append)
    worker.run()

    assert completed[-1].processed_successfully == 2
    assert provider.load_count == 1
    assert provider.embed_call_count == 2
    assert EmbeddingStore(db).get_valid(p1, provider.metadata) is not None

    second_provider = FakeEmbeddingProvider()
    second_service = BatchEmbeddingService(second_provider, EmbeddingStore(db))
    second = EmbeddingWorker([photo(p1), photo(p2)], service_factory=lambda: second_service)
    second_results = []
    second.complete.connect(second_results.append)
    second.run()

    assert second_results[-1].total_images_received == 0
    assert second_provider.embed_call_count == 0


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
    worker.complete.connect(results.append)
    worker.run()

    assert results[-1].total_images_received == 1
    assert results[-1].processed_successfully == 1
    assert provider.embed_call_count == calls + 1


def test_embedding_worker_supports_cancellation_and_progress(tmp_path):
    paths = [image(tmp_path / f"{i}.jpg", str(i).encode()) for i in range(3)]
    provider = FakeEmbeddingProvider()
    service = BatchEmbeddingService(provider, EmbeddingStore(tmp_path / "embeddings.sqlite3"))
    worker = EmbeddingWorker([photo(p) for p in paths], service_factory=lambda: service)
    progress = []
    results = []

    def on_progress(item):
        progress.append(item)
        worker.cancel()

    worker.progress.connect(on_progress)
    worker.complete.connect(results.append)
    worker.run()

    assert len(progress) == 1
    assert progress[0].current_index == 1
    assert results[-1].processed_successfully == 1
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
        def __init__(self, photos):
            self.photos = photos
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
    monkeypatch.setattr(MainWindow, "start_thumbnail_loading", lambda self, photos: None)
    monkeypatch.setattr(MainWindow, "_deferred_setup_cleanup_review", lambda self: None)
    window = MainWindow()
    window._on_scan_complete([])
    assert started == ["started"]


class _Signal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
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
        def __init__(self, photos):
            self.photos = list(photos)
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

    first_worker.finished.emit()

    assert len(workers) == 2
    assert workers[1].photos == ["second"]
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

    window._request_embedding_worker_cancel()
    assert window.embedding_thread is thread
    assert window.embedding_worker is worker

    window._on_embedding_thread_finished(2)
    assert window.embedding_thread is thread
    assert window.embedding_worker is worker

    window._on_embedding_thread_finished(3)
    assert window.embedding_thread is None
    assert window.embedding_worker is None


def _embedding_window_for_lifecycle_tests():
    window = MainWindow.__new__(MainWindow)
    window.embedding_thread = None
    window.embedding_worker = None
    window._embedding_run_id = 0
    window._active_embedding_run_id = 0
    window._pending_embedding_photos = None
    window._embedding_close_requested = False
    window.status_label = _StatusLabel()
    return window


class _StatusLabel:
    def __init__(self):
        self.text = "initial"

    def setText(self, text):
        self.text = text

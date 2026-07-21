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

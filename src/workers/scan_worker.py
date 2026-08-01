"""
Background worker that runs folder scanning and metadata extraction
off the UI thread so the main window stays responsive during import.

Emits:
  scan_complete(object) — structured photos/library/import result on success.
  scan_error(str)      — when an unhandled exception occurs during scanning.
  finished()           — always emitted last, regardless of outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
import time

from PySide6.QtCore import QObject, Signal

from core.application_services import ApplicationServices
from core.perf_stats import get_session_stats
from core.photo_scanner import find_photos
from cache.thumbnail_cache import preserve_thumbnail_for_relocation
from storage.import_registration import ImportRegistrationService
from vision.embedding_provider import EmbeddingStore


@dataclass(frozen=True)
class ScanCompletion:
    run_id: int
    photos: list
    library: object | None
    import_result: object | None


class ScanWorker(QObject):
    scan_complete = Signal(object)
    scan_error = Signal(str)
    finished = Signal()

    def __init__(self, folder_path: str, application_services: ApplicationServices | None = None,
                 run_id: int = 0) -> None:
        super().__init__()
        self._folder_path = folder_path
        self._application_services = application_services
        self._run_id = run_id

    def run(self) -> None:
        worker_started = time.perf_counter()
        registration = None
        prepared_library = None
        try:
            if self._application_services is not None:
                prepared_library = self._application_services.prepare_import_library(self._folder_path)
                store = prepared_library.store
                registration = ImportRegistrationService(store, self._folder_path)
            photos = find_photos(self._folder_path, registration)
            import_result = None
            if registration is not None:
                import_result = registration.register(
                    photos,
                    skipped=get_session_stats().get_counter("unsupported_files_skipped"),
                )
                relocated = [photo for photo in photos
                             if photo.sync_state in {"moved", "renamed"} and photo.previous_path]
                embedding_store = (
                    EmbeddingStore(
                        self._application_services.paths.cache_dir("embeddings")
                        / "semantic_embeddings.sqlite3"
                    ) if relocated else None
                )
                for photo in relocated:
                    item = registration.plan.item_for(photo.path)
                    previous = item.previous_location
                    preserve_thumbnail_for_relocation(
                        previous.source_path, previous.modified_time_ns,
                        previous.file_size, str(photo.path))
                    embedding_store.preserve_for_relocation(photo.previous_path, photo.path)
            self.scan_complete.emit(ScanCompletion(
                self._run_id, photos, prepared_library, import_result))
        except Exception as exc:  # noqa: BLE001
            if registration is not None:
                try:
                    registration.fail(str(exc))
                except Exception:  # noqa: BLE001
                    pass
            if prepared_library is not None and self._application_services is not None:
                self._application_services.discard_prepared_library(prepared_library)
            self.scan_error.emit(str(exc))
        finally:
            get_session_stats().record("ScanWorker", (time.perf_counter() - worker_started) * 1000,
                                       thread_kind="Background thread")
            self.finished.emit()

"""Background worker for import/index-time semantic image embeddings."""
from __future__ import annotations

from threading import Event
from typing import Callable

from PySide6.QtCore import QObject, Signal

from vision.batch_embedding_service import BatchEmbeddingProgress, BatchEmbeddingResult, BatchEmbeddingService


class EmbeddingWorker(QObject):
    """Generate missing or outdated embeddings off the UI thread.

    The worker owns one BatchEmbeddingService instance for the run so the provider
    is loaded at most once while the service processes required images
    sequentially. Callers may inject a factory in tests or alternate indexing
    contexts while production uses the persistent default embedding cache.
    """

    progress = Signal(object)
    complete = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(self, photos, service_factory: Callable[[], BatchEmbeddingService] | None = None) -> None:
        super().__init__()
        self._photos = list(photos or [])
        self._service_factory = service_factory or BatchEmbeddingService
        self._cancel_event = Event()

    def cancel(self) -> None:
        """Request cancellation before or between sequential image processing."""
        self._cancel_event.set()

    def run(self) -> None:
        try:
            service = self._service_factory()
            required = [photo for photo in self._photos if service.needs_embedding(photo)]
            if self._cancel_event.is_set():
                result = BatchEmbeddingResult(total_images_received=len(required), cancelled=len(required))
                self.complete.emit(result)
                return
            if not required:
                result = BatchEmbeddingResult(total_images_received=0)
                self.complete.emit(result)
                return

            result = service.embed_images(
                required,
                progress_callback=self._emit_progress,
                cancellation_token=self._cancel_event,
            )
            self.complete.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self.finished.emit()

    def _emit_progress(self, progress: BatchEmbeddingProgress) -> None:
        self.progress.emit(progress)

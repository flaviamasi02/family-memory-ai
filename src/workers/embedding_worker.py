"""Background worker for import/index-time semantic image embeddings."""
from __future__ import annotations

import logging
from threading import Event
from typing import Callable

from PySide6.QtCore import QObject, Signal

from vision.batch_embedding_service import BatchEmbeddingProgress, BatchEmbeddingResult, BatchEmbeddingService

logger = logging.getLogger(__name__)


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
    progress_for_run = Signal(int, object)
    complete_for_run = Signal(int, object)
    error_for_run = Signal(int, str)
    finished = Signal()

    def __init__(self, photos, service_factory: Callable[[], BatchEmbeddingService] | None = None, run_id: int = 0) -> None:
        super().__init__()
        self._photos = list(photos or [])
        self._service_factory = service_factory or BatchEmbeddingService
        self._cancel_event = Event()
        self.run_id = int(run_id)

    def cancel(self) -> None:
        """Request cancellation before or between sequential image processing."""
        self._cancel_event.set()

    def run(self) -> None:
        logger.info("Embedding worker start run_id=%s inputs=%s", self.run_id, len(self._photos))
        try:
            service = self._service_factory()
            if self._cancel_event.is_set():
                result = BatchEmbeddingResult(
                    total_images_received=len(self._photos),
                    cancelled=len(self._photos),
                )
                self.complete.emit(result)
                self.complete_for_run.emit(self.run_id, result)
                return
            if not self._photos:
                result = BatchEmbeddingResult(total_images_received=0)
                self.complete.emit(result)
                self.complete_for_run.emit(self.run_id, result)
                return

            # Pass the complete import set through the batch service.  The service
            # owns cache validation and reports cached files as successful reuse;
            # pre-filtering here loses that result and leaves the UI in "preparing".
            result = service.embed_images(
                self._photos,
                progress_callback=self._emit_progress,
                cancellation_token=self._cancel_event,
            )
            self.complete.emit(result)
            self.complete_for_run.emit(self.run_id, result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Embedding worker failed run_id=%s", self.run_id)
            self.error.emit(str(exc))
            self.error_for_run.emit(self.run_id, str(exc))
        finally:
            logger.info("Embedding worker finish run_id=%s", self.run_id)
            self.finished.emit()

    def _emit_progress(self, progress: BatchEmbeddingProgress) -> None:
        self.progress.emit(progress)
        self.progress_for_run.emit(self.run_id, progress)

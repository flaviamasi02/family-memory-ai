"""Background worker for import/index-time semantic image embeddings."""
from __future__ import annotations

from threading import Event
from typing import Callable

from PySide6.QtCore import QObject, Signal

from ai_runtime.manager import AIRuntimeManager, create_default_runtime_manager
from vision.batch_embedding_service import BatchEmbeddingProgress, BatchEmbeddingResult, BatchEmbeddingService
from vision.managed_mobileclip_provider import ManagedMobileCLIPEmbeddingProvider


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

    def __init__(
        self,
        photos,
        service_factory: Callable[[], BatchEmbeddingService] | None = None,
    ) -> None:
        super().__init__()
        self._photos = list(photos or [])
        self._service_factory = service_factory
        self._runtime_manager: AIRuntimeManager | None = None
        self._cancel_event = Event()

    def set_runtime_manager(self, runtime_manager: AIRuntimeManager) -> None:
        """Inject the composition root's runtime before the worker is started."""
        self._runtime_manager = runtime_manager

    def _create_service(self) -> BatchEmbeddingService:
        if self._service_factory is not None:
            return self._service_factory()
        manager = self._runtime_manager or create_default_runtime_manager()
        return BatchEmbeddingService(
            provider=ManagedMobileCLIPEmbeddingProvider(runtime_manager=manager)
        )

    def cancel(self) -> None:
        """Request cancellation before or between sequential image processing."""
        self._cancel_event.set()

    def run(self) -> None:
        try:
            service = self._create_service()
            if self._cancel_event.is_set():
                result = BatchEmbeddingResult(
                    total_images_received=len(self._photos),
                    cancelled=len(self._photos),
                )
                self.complete.emit(result)
                return
            if not self._photos:
                result = BatchEmbeddingResult(total_images_received=0)
                self.complete.emit(result)
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
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self.finished.emit()

    def _emit_progress(self, progress: BatchEmbeddingProgress) -> None:
        self.progress.emit(progress)

import time
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QThread, QSize, Signal
from PySide6.QtGui import QImage

from cache.thumbnail_cache import get_thumbnail_cache_path
from core.image_display_loader import load_display_thumbnail_image, is_decode_failed
from core.perf_stats import get_session_stats
from core.supported_media import SUPPORTED_IMAGE_EXTENSIONS


THUMBNAIL_IMAGE_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS


class ThumbnailWorker(QObject):
    thumbnail_ready = Signal(object, QImage)
    thumbnail_status_updated = Signal(object)
    finished = Signal()


    def __init__(self, photos, thumbnail_size=160, batch_size=20, delay_ms=0):
        super().__init__()
        # The scanner is the authoritative filesystem filter. Keep trusted
        # domain/test values intact here; the extension guard in run() remains
        # a decode-safety fallback for direct callers.
        self.photos = list(photos or [])
        self.thumbnail_size = thumbnail_size
        self.batch_size = batch_size
        self.delay_ms = delay_ms
        self._cancel_event = Event()

    def cancel(self) -> None:
        """Cooperatively stop before decoding the next thumbnail."""
        self._cancel_event.set()

    def run(self):
        stats = get_session_stats()
        worker_started = time.perf_counter()
        _cache_hits = 0
        _cache_misses = 0
        _generated = 0
        _corrupt_skipped = 0
        _gen_ms = 0.0

        try:
            for start in range(0, len(self.photos), self.batch_size):
                if self._cancel_event.is_set():
                    break
                batch = self.photos[start : start + self.batch_size]

                for photo in batch:
                    if self._cancel_event.is_set():
                        break
                    try:
                        path = Path(photo.path)
                        if path.suffix.lower() not in THUMBNAIL_IMAGE_EXTENSIONS:
                            continue

                        # Skip files already known to be corrupted this session.
                        if is_decode_failed(str(path)):
                            _corrupt_skipped += 1
                            photo.set_status("error")
                            self.thumbnail_status_updated.emit(photo)
                            continue

                        cache_path = get_thumbnail_cache_path(str(photo.path))
                        cached_image = self._load_cached_thumbnail(cache_path)
                        if cached_image is not None:
                            _cache_hits += 1
                            self._mark_thumbnail_ready(photo, cache_path)
                            self.thumbnail_status_updated.emit(photo)
                            self.thumbnail_ready.emit(photo, cached_image)
                            continue

                        _cache_misses += 1
                        if getattr(photo, "sync_state", "added") not in {"added", "updated"}:
                            # Incremental sync never decodes unchanged content.
                            # A missing disposable cache can be regenerated only
                            # after the file itself changes or is newly added.
                            continue
                        photo.set_status("thumbnail_loading")
                        self.thumbnail_status_updated.emit(photo)

                        t_gen = time.perf_counter()
                        image = self._load_thumbnail_image(photo.path)
                        _gen_ms += (time.perf_counter() - t_gen) * 1000

                        if image is None or image.isNull():
                            _corrupt_skipped += 1
                            photo.set_status("error")
                            self.thumbnail_status_updated.emit(photo)
                            continue

                        _generated += 1
                        try:
                            image.save(str(cache_path), "JPG", quality=85)
                        except Exception as exc:
                            print(f"Failed to cache thumbnail for {photo.path}: {exc}")

                        self._mark_thumbnail_ready(photo, cache_path)

                        self.thumbnail_status_updated.emit(photo)
                        self.thumbnail_ready.emit(photo, image)

                    except Exception as exc:  # noqa: BLE001
                        # Log the error but continue so one bad file never stalls the queue.
                        print(f"[ThumbnailWorker] Unexpected error for {getattr(photo, 'path', '?')}: {exc}")

                if self.delay_ms > 0:
                    QThread.msleep(self.delay_ms)

            # Accumulate aggregate worker counters into session stats.
            stats.inc("thumbnail_cache_hits", _cache_hits)
            stats.inc("thumbnail_cache_misses", _cache_misses)
            stats.inc("thumbnails_generated", _generated)
            stats.inc("corrupt_unsupported_skipped", _corrupt_skipped)
            if _gen_ms > 0:
                stats.record("Thumbnail generation", _gen_ms, _generated, "Background thread")

        except Exception as exc:  # noqa: BLE001
            print(f"[ThumbnailWorker] Fatal error in run(): {exc}")
        finally:
            stats.record("ThumbnailWorker", (time.perf_counter() - worker_started) * 1000,
                         len(self.photos), "Background thread")
            self.finished.emit()

    def _load_thumbnail_image(self, image_path):
        path = Path(image_path)
        if not path.exists():
            return None

        image = load_display_thumbnail_image(path, QSize(self.thumbnail_size, self.thumbnail_size))
        if not isinstance(image, QImage) or image.isNull():
            return None
        return image

    def _load_cached_thumbnail(self, cache_path):
        path = Path(cache_path)
        if not path.exists() or not path.is_file():
            return None

        image = QImage(str(path))
        if not isinstance(image, QImage) or image.isNull():
            return None
        return image

    def _mark_thumbnail_ready(self, photo, cache_path):
        photo.thumbnail_path = str(cache_path)
        metadata = dict(getattr(photo, "metadata", {}) or {})
        metadata["thumbnail_path"] = str(cache_path)
        photo.metadata = metadata
        photo.set_status("thumbnail_ready")

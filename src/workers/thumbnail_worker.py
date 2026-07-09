from pathlib import Path

from PySide6.QtCore import QObject, QThread, QSize, Signal
from PySide6.QtGui import QImage

from cache.thumbnail_cache import get_thumbnail_cache_path
from core.image_display_loader import load_display_thumbnail_image, is_decode_failed


THUMBNAIL_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


class ThumbnailWorker(QObject):
    thumbnail_ready = Signal(object, QImage)
    thumbnail_status_updated = Signal(object)
    finished = Signal()


    def __init__(self, photos, thumbnail_size=160, batch_size=12, delay_ms=0):
        super().__init__()
        self.photos = photos
        self.thumbnail_size = thumbnail_size
        self.batch_size = batch_size
        self.delay_ms = delay_ms

    def run(self):
        for start in range(0, len(self.photos), self.batch_size):
            batch = self.photos[start : start + self.batch_size]

            for photo in batch:
                path = Path(photo.path)
                if path.suffix.lower() not in THUMBNAIL_IMAGE_EXTENSIONS:
                    continue

                # Skip files that are already known to be corrupted this session.
                if is_decode_failed(str(path)):
                    photo.set_status("error")
                    self.thumbnail_status_updated.emit(photo)
                    continue

                cache_path = get_thumbnail_cache_path(str(photo.path))
                cached_image = self._load_cached_thumbnail(cache_path)
                if cached_image is not None:
                    self._mark_thumbnail_ready(photo, cache_path)
                    self.thumbnail_status_updated.emit(photo)
                    self.thumbnail_ready.emit(photo, cached_image)
                    continue

                photo.set_status("thumbnail_loading")
                self.thumbnail_status_updated.emit(photo)
                image = self._load_thumbnail_image(photo.path)
                if image is None or image.isNull():
                    photo.set_status("error")
                    self.thumbnail_status_updated.emit(photo)
                    continue

                try:
                    image.save(str(cache_path), "JPG", quality=85)
                except Exception as exc:
                    print(f"Failed to cache thumbnail for {photo.path}: {exc}")

                self._mark_thumbnail_ready(photo, cache_path)

                self.thumbnail_status_updated.emit(photo)
                self.thumbnail_ready.emit(photo, image)

            if self.delay_ms > 0:
                QThread.msleep(self.delay_ms)

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

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QSize, Signal
from PySide6.QtGui import QImage

from cache.thumbnail_cache import get_thumbnail_cache_path
from core.image_display_loader import load_display_thumbnail_image


THUMBNAIL_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


class ThumbnailWorker(QObject):
    thumbnail_ready = Signal(object, QImage)
    thumbnail_status_updated = Signal(object)
    finished = Signal()


    def __init__(self, photos, thumbnail_size=160, batch_size=12, delay_ms=10):
        super().__init__()
        self.photos = photos
        self.thumbnail_size = thumbnail_size
        self.batch_size = batch_size
        self.delay_ms = delay_ms

    def run(self):
        print("thumbnail worker started")
        for start in range(0, len(self.photos), self.batch_size):
            batch = self.photos[start : start + self.batch_size]

            for photo in batch:
                if Path(photo.path).suffix.lower() not in THUMBNAIL_IMAGE_EXTENSIONS:
                    continue

                print(f"generating thumbnail: {photo.path}")
                photo.set_status("thumbnail_loading")
                self.thumbnail_status_updated.emit(photo)
                cache_path = get_thumbnail_cache_path(str(photo.path))
                image = self._load_thumbnail_image(photo.path)
                if image is None or image.isNull():
                    photo.set_status("error")
                    self.thumbnail_status_updated.emit(photo)
                    print(f"Skipping thumbnail for {photo.path}")
                    continue

                print(f"thumbnail qimage null before emit: {image.isNull()}")
                try:
                    image.save(str(cache_path), "JPG", quality=85)
                except Exception as exc:
                    print(f"Failed to cache thumbnail for {photo.path}: {exc}")

                photo.thumbnail_path = str(cache_path)
                metadata = dict(getattr(photo, "metadata", {}) or {})
                metadata["thumbnail_path"] = str(cache_path)
                photo.metadata = metadata

                photo.set_status("thumbnail_ready")
                self.thumbnail_status_updated.emit(photo)
                self.thumbnail_ready.emit(photo, image)
                print(f"thumbnail signal emitted: {photo.path}")

            if self.delay_ms > 0:
                QThread.msleep(self.delay_ms)

        self.finished.emit()

    def _load_thumbnail_image(self, image_path):
        path = Path(image_path)
        if not path.exists():
            return None

        image = load_display_thumbnail_image(path, QSize(self.thumbnail_size, self.thumbnail_size))
        if not isinstance(image, QImage) or image.isNull():
            print(f"Thumbnail decode error for {path}: unsupported/corrupt image")
            return None
        print(f"thumbnail generated: {path} null={image.isNull()}")
        return image

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QSize, Signal
from PySide6.QtGui import QImageReader, QPixmap

from cache.thumbnail_cache import get_thumbnail_cache_path


THUMBNAIL_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class ThumbnailWorker(QObject):
    thumbnail_ready = Signal(object, QPixmap)
    thumbnail_status_updated = Signal(object)
    finished = Signal()


    def __init__(self, photos, thumbnail_size=160, batch_size=12, delay_ms=10):
        super().__init__()
        self.photos = photos
        self.thumbnail_size = thumbnail_size
        self.batch_size = batch_size
        self.delay_ms = delay_ms

    def run(self):
        for start in range(0, len(self.photos), self.batch_size):
            batch = self.photos[start : start + self.batch_size]

            for photo in batch:
                if Path(photo.path).suffix.lower() not in THUMBNAIL_IMAGE_EXTENSIONS:
                    continue

                photo.set_status("thumbnail_loading")
                self.thumbnail_status_updated.emit(photo)
                cache_path = get_thumbnail_cache_path(str(photo.path))

                if cache_path.exists():
                    pixmap = QPixmap(str(cache_path))
                    if pixmap.isNull():
                        print(f"Failed to load cached thumbnail for {photo.path}")
                        continue
                else:
                    pixmap = self._load_thumbnail_pixmap(photo.path)
                    if pixmap is None:
                        photo.set_status("error")
                        self.thumbnail_status_updated.emit(photo)
                        print(f"Skipping thumbnail for {photo.path}")
                        continue

                    try:
                        pixmap.save(str(cache_path), "JPG", quality=85)
                    except Exception as exc:
                        print(f"Failed to cache thumbnail for {photo.path}: {exc}")

                photo.set_status("thumbnail_ready")
                self.thumbnail_status_updated.emit(photo)
                self.thumbnail_ready.emit(photo, pixmap)

            if self.delay_ms > 0:
                QThread.msleep(self.delay_ms)

        self.finished.emit()

    def _load_thumbnail_pixmap(self, image_path):
        path = Path(image_path)
        if not path.exists():
            return None

        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        reader.setScaledSize(QSize(self.thumbnail_size, self.thumbnail_size))

        try:
            image = reader.read()
        except Exception as exc:
            print(f"Thumbnail decode error for {path}: {exc}")
            return None

        if image.isNull():
            error_string = reader.errorString()
            if error_string:
                print(f"Thumbnail decode error for {path}: {error_string}")
            else:
                print(f"Thumbnail decode error for {path}: unknown image error")
            return None

        return QPixmap.fromImage(image)

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QPixmap

from cache.thumbnail_cache import get_thumbnail_cache_path


class ThumbnailWorker(QObject):
    thumbnail_ready = Signal(object, QPixmap)
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
                cache_path = get_thumbnail_cache_path(str(photo.path))

                if cache_path.exists():
                    pixmap = QPixmap(str(cache_path))
                else:
                    pixmap = QPixmap(str(photo.path))

                    if pixmap.isNull():
                        continue

                    pixmap = pixmap.scaled(
                        self.thumbnail_size,
                        self.thumbnail_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )

                    pixmap.save(str(cache_path), "JPG", quality=85)

                self.thumbnail_ready.emit(photo, pixmap)

            if self.delay_ms > 0:
                QThread.msleep(self.delay_ms)

        self.finished.emit()
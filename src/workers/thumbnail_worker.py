from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QPixmap

from cache.thumbnail_cache import get_thumbnail_cache_path


class ThumbnailWorker(QObject):
    thumbnail_ready = Signal(str, QPixmap)
    finished = Signal()

    def __init__(self, photos, thumbnail_size=160):
        super().__init__()
        self.photos = photos
        self.thumbnail_size = thumbnail_size

    def run(self):
        for photo_path in self.photos:
            cache_path = get_thumbnail_cache_path(str(photo_path))

            if cache_path.exists():
                pixmap = QPixmap(str(cache_path))
            else:
                pixmap = QPixmap(str(photo_path))

                if pixmap.isNull():
                    continue

                pixmap = pixmap.scaled(
                    self.thumbnail_size,
                    self.thumbnail_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

                pixmap.save(str(cache_path), "JPG", quality=85)

            self.thumbnail_ready.emit(str(photo_path), pixmap)

        self.finished.emit()
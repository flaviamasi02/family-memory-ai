from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt


class PhotoModel(QAbstractListModel):
    FullPathRole = Qt.UserRole + 1

    def __init__(self, photos=None):
        super().__init__()
        self._photos = list(photos or [])

    def rowCount(self, parent=QModelIndex()):
        return len(self._photos)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._photos):
            return None

        photo = self._photos[index.row()]

        if role == Qt.DisplayRole:
            return photo.display_name()

        if role == Qt.DecorationRole:
            return photo.thumbnail

        if role == self.FullPathRole:
            return str(photo.path)

        return None

    def set_photos(self, photos):
        self.beginResetModel()
        self._photos = list(photos)
        self.endResetModel()

    def update_thumbnail(self, photo, pixmap):
        target_path = photo.path if hasattr(photo, "path") else Path(photo)

        for index, existing_photo in enumerate(self._photos):
            if existing_photo.path == target_path or str(existing_photo.path) == str(target_path):
                existing_photo.thumbnail = pixmap
                self.dataChanged.emit(
                    self.createIndex(index, 0),
                    self.createIndex(index, 0),
                    [Qt.DecorationRole],
                )
                return True

        return False

    def get_photo_path(self, index):
        if not index.isValid():
            return None

        photo = self._photos[index.row()]
        return str(photo.path)

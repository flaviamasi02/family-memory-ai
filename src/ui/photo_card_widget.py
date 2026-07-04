from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PhotoCardWidget(QWidget):
    photo_clicked = Signal(object)

    def __init__(self, photo=None, parent=None):
        super().__init__(parent)

        self.photo = None
        self.thumbnail_label = QLabel("")
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setFixedSize(160, 160)
        self.thumbnail_label.setStyleSheet(
            "border: 1px solid #c0c0c0; border-radius: 4px; background-color: #f5f5f5;"
        )

        self.name_label = QLabel("")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setFixedHeight(40)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.thumbnail_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label, 0, Qt.AlignmentFlag.AlignCenter)

        self.setFixedWidth(180)
        self.setMinimumHeight(220)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background-color: white;")

        self.set_photo(photo)

        self.thumbnail_label.mousePressEvent = self._handle_thumbnail_click
        self.mousePressEvent = self._handle_widget_click

    def refresh_from_photo(self):
        if self.photo is None:
            return

        self.name_label.setText(self.photo.display_name())
        if getattr(self.photo, "thumbnail", None) is not None:
            self.set_thumbnail(self.photo.thumbnail)
        else:
            self.thumbnail_label.clear()

    def set_photo(self, photo):
        self.photo = photo
        if photo is None:
            self.thumbnail_label.clear()
            self.name_label.setText("")
            return

        self.name_label.setText(photo.display_name())
        if getattr(photo, "thumbnail", None) is not None:
            self.set_thumbnail(photo.thumbnail)
        else:
            self.thumbnail_label.clear()

    def set_thumbnail(self, pixmap):
        if pixmap is None or pixmap.isNull():
            self.thumbnail_label.clear()
            return

        scaled = pixmap.scaled(
            160,
            160,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.thumbnail_label.setPixmap(scaled)

    def _handle_thumbnail_click(self, event):
        self._emit_click()

    def _handle_widget_click(self, event):
        self._emit_click()

    def _emit_click(self):
        if self.photo is not None:
            self.photo_clicked.emit(self.photo)

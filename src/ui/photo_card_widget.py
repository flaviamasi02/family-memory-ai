from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QLabel, QVBoxLayout, QWidget


class PhotoCardWidget(QWidget):
    photo_clicked = Signal(object)

    def __init__(self, photo=None, parent=None):
        super().__init__(parent)

        self.photo = None
        self._is_selected = False

        self.setObjectName("photoCard")
        self.thumbnail_label = QLabel("")
        self.thumbnail_label.setObjectName("thumbnailLabel")
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setFixedSize(160, 160)

        self.name_label = QLabel("")
        self.name_label.setObjectName("nameLabel")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setFixedHeight(40)

        self.selected_badge = QLabel("Selected")
        self.selected_badge.setObjectName("selectedBadge")
        self.selected_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_badge.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.thumbnail_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.selected_badge, 0, Qt.AlignmentFlag.AlignCenter)

        self.setFixedWidth(180)
        self.setMinimumHeight(220)
        self.setAutoFillBackground(True)
        self._selected_shadow = QGraphicsDropShadowEffect(self)
        self._selected_shadow.setBlurRadius(16)
        self._selected_shadow.setOffset(0, 0)
        self._selected_shadow.setColor(QColor(0, 0, 0, 0))
        self._apply_style()

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

    def set_selected(self, selected: bool):
        self._is_selected = bool(selected)
        self.selected_badge.setVisible(self._is_selected)

        if self._is_selected:
            self._selected_shadow.setColor(QColor(37, 99, 235, 51))
            self.setGraphicsEffect(self._selected_shadow)
        else:
            self.setGraphicsEffect(None)

        self._apply_style()

    def _apply_style(self):
        if self._is_selected:
            card_background = "#eff6ff"
            card_border = "3px solid #2563eb"
        else:
            card_background = "#ffffff"
            card_border = "1px solid #e5e7eb"

        self.setStyleSheet(
            f"""
            QWidget#photoCard {{
                background-color: {card_background};
                border: {card_border};
                border-radius: 8px;
            }}
            QLabel#thumbnailLabel {{
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                background-color: #f5f5f5;
            }}
            QLabel#nameLabel {{
                border: none;
                color: #111827;
                background: transparent;
            }}
            QLabel#selectedBadge {{
                border: none;
                color: #1d4ed8;
                background-color: #dbeafe;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            """
        )

    def _handle_thumbnail_click(self, event):
        self._emit_click()

    def _handle_widget_click(self, event):
        self._emit_click()

    def _emit_click(self):
        if self.photo is not None:
            self.photo_clicked.emit(self.photo)

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)


class ImagePreviewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Preview")
        self.resize(1000, 800)

        self._photos: list[object] = []
        self._current_index = 0
        self._source_pixmap_cache: dict[str, QPixmap] = {}
        self._scaled_pixmap_cache: dict[tuple[str, int, int], QPixmap] = {}

        self.position_label = QLabel("0 of 0")

        self.image_label = QLabel("Preview unavailable")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid #9ca3af; background: #f8fafc;")
        self.image_label.setMinimumSize(640, 420)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.filename_value = QLabel("-")
        self.media_category_value = QLabel("-")
        self.user_decision_value = QLabel("-")
        self.score_value = QLabel("-")

        form = QFormLayout()
        form.addRow("Filename:", self.filename_value)
        form.addRow("Media category:", self.media_category_value)
        form.addRow("User decision:", self.user_decision_value)
        form.addRow("Score:", self.score_value)

        self.prev_button = QPushButton("Previous image")
        self.prev_button.clicked.connect(self.show_previous)
        self.next_button = QPushButton("Next image")
        self.next_button.clicked.connect(self.show_next)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)

        controls = QHBoxLayout()
        controls.addWidget(self.prev_button)
        controls.addWidget(self.next_button)
        controls.addStretch(1)
        controls.addWidget(self.position_label)
        controls.addStretch(1)
        controls.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.image_label, 1)
        layout.addLayout(form)
        layout.addLayout(controls)

    def set_items(self, photos: list[object], start_index: int = 0) -> None:
        self._photos = list(photos or [])
        if not self._photos:
            self._current_index = 0
            self._show_unavailable()
            self._update_controls()
            return

        safe_index = max(0, min(int(start_index), len(self._photos) - 1))
        self._current_index = safe_index
        self._render_current(force=True)

    def current_filename(self) -> str:
        photo = self._current_photo()
        return photo.display_name() if photo is not None else ""

    def show_next(self) -> None:
        if not self._photos:
            return
        self._current_index = min(self._current_index + 1, len(self._photos) - 1)
        self._render_current(force=True)

    def show_previous(self) -> None:
        if not self._photos:
            return
        self._current_index = max(self._current_index - 1, 0)
        self._render_current(force=True)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left:
            self.show_previous()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Right:
            self.show_next()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_current(force=False)

    def _current_photo(self):
        if not self._photos:
            return None
        if self._current_index < 0 or self._current_index >= len(self._photos):
            return None
        return self._photos[self._current_index]

    def _render_current(self, force: bool) -> None:
        photo = self._current_photo()
        if photo is None:
            self._show_unavailable()
            self._update_controls()
            return

        self.filename_value.setText(photo.display_name())
        self.media_category_value.setText(self._media_category(photo))
        self.user_decision_value.setText(self._user_decision(photo))
        self.score_value.setText(self._score_text(photo))

        signature, source = self._resolve_source_pixmap(photo)
        if source is None:
            self._show_unavailable()
            self._update_controls()
            return

        target_size = self._target_image_size()
        cache_key = (signature, target_size.width(), target_size.height())
        scaled = self._scaled_pixmap_cache.get(cache_key)
        if scaled is None or force:
            scaled = source.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._scaled_pixmap_cache[cache_key] = scaled

        self.image_label.setPixmap(scaled)
        self.image_label.setText("")
        self._update_controls()

    def _target_image_size(self) -> QSize:
        width = max(200, self.image_label.width() - 12)
        height = max(200, self.image_label.height() - 12)
        return QSize(width, height)

    def _show_unavailable(self) -> None:
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText("Preview unavailable")
        self.filename_value.setText(self.filename_value.text() or "-")

    def _update_controls(self) -> None:
        count = len(self._photos)
        index = (self._current_index + 1) if count else 0
        self.position_label.setText(f"{index} of {count}")
        self.prev_button.setEnabled(count > 1 and self._current_index > 0)
        self.next_button.setEnabled(count > 1 and self._current_index < count - 1)

    def _resolve_source_pixmap(self, photo) -> tuple[str, Optional[QPixmap]]:
        path = Path(getattr(photo, "path", ""))
        if path.exists() and path.is_file():
            signature = f"orig:{path}:{path.stat().st_mtime}"
            cached = self._source_pixmap_cache.get(signature)
            if isinstance(cached, QPixmap) and not cached.isNull():
                return signature, cached

            reader = QImageReader(str(path))
            reader.setAutoTransform(True)
            image = reader.read()
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                if not pixmap.isNull():
                    self._source_pixmap_cache[signature] = pixmap
                    return signature, pixmap

        thumb = getattr(photo, "thumbnail", None)
        if isinstance(thumb, QPixmap) and not thumb.isNull():
            signature = f"thumb:{int(thumb.cacheKey())}"
            self._source_pixmap_cache[signature] = thumb
            return signature, thumb

        return "none", None

    def _media_category(self, photo) -> str:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        category = (
            metadata.get("cleanup_effective_category")
            or metadata.get("effective_media_category")
            or metadata.get("relevance_category")
            or getattr(photo, "effective_media_category", "")
            or getattr(photo, "media_category", "")
            or getattr(photo, "relevance_category", "")
            or "unknown"
        )
        return str(category).replace("_", " ").title()

    def _user_decision(self, photo) -> str:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        decision = (
            metadata.get("cleanup_user_decision")
            or metadata.get("user_decision")
            or getattr(photo, "user_decision", "")
            or "-"
        )
        return str(decision).replace("_", " ")

    def _score_text(self, photo) -> str:
        intelligence = getattr(photo, "intelligence", None)
        if intelligence is not None:
            value = getattr(intelligence, "album_candidate_score", None)
            if isinstance(value, (int, float)):
                return f"{float(value):.2f}"

        metadata = dict(getattr(photo, "metadata", {}) or {})
        for key in ("album_candidate_score", "cleanup_confidence", "classification_confidence"):
            value = metadata.get(key)
            if isinstance(value, (int, float)):
                if "confidence" in key:
                    return f"{int(round(float(value) * 100))}%"
                return f"{float(value):.2f}"

        return "-"

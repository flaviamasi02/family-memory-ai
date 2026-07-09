from pathlib import Path

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGridLayout, QScrollArea, QSizePolicy, QWidget

from ui.photo_card_widget import PhotoCardWidget

# Approximate rendered width of each card (fixed 180px + 12px spacing).
_CARD_CELL_WIDTH = 192


class PhotoGridWidget(QWidget):
    photo_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._cards = []
        self._cards_by_key = {}
        self._photos = []
        self._pending_photo_index = 0
        self._target_render_count = 0
        self._initial_render_count = 60
        self._batch_size = 30
        self._pending_thumbnail_updates = {}
        self._selected_photo_key = None
        self._grid_columns = 3

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)

        self.content_widget = QWidget(self.scroll_area)
        self.content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.grid_layout = QGridLayout(self.content_widget)
        self.grid_layout.setContentsMargins(12, 12, 12, 12)
        self.grid_layout.setSpacing(12)
        self.scroll_area.setWidget(self.content_widget)
        self.scroll_area.viewport().installEventFilter(self)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll_area)

    def set_photos(self, photos):
        existing_pending = dict(self._pending_thumbnail_updates)

        self._clear_cards()
        self._cards = []
        self._cards_by_key = {}
        self._photos = list(photos or [])
        self._pending_photo_index = 0
        self._target_render_count = min(self._initial_render_count, len(self._photos))
        self._selected_photo_key = None
        self._grid_columns = self._calculate_grid_columns()

        valid_keys = {self._photo_key(photo) for photo in self._photos}
        self._pending_thumbnail_updates = {
            key: pixmap for key, pixmap in existing_pending.items() if key in valid_keys
        }

        self._schedule_batch_add()

    def update_thumbnail(self, photo, pixmap):
        key = self._photo_key(photo)
        card = self._cards_by_key.get(key)

        if isinstance(pixmap, QImage):
            pixmap = QPixmap.fromImage(pixmap)

        if not isinstance(pixmap, QPixmap) or pixmap.isNull():
            return

        if card is not None:
            card.set_thumbnail(pixmap)
            card.update()
            return

        self._pending_thumbnail_updates[key] = pixmap

    def refresh_photo_status(self, photo):
        key = self._photo_key(photo)
        card = self._cards_by_key.get(key)
        if card is not None:
            card.refresh_from_photo()

    def _handle_card_click(self, photo):
        self.set_selected_photo(photo)
        self.photo_selected.emit(photo)

    def set_selected_photo(self, photo):
        self._selected_photo_key = self._photo_key(photo) if photo is not None else None
        self._refresh_selection_styles()

    def _refresh_selection_styles(self):
        for key, card in self._cards_by_key.items():
            card.set_selected(key == self._selected_photo_key)

    def _clear_cards(self):
        for card in self._cards:
            self.grid_layout.removeWidget(card)
            card.deleteLater()
        self._cards = []
        self._cards_by_key = {}

    def _photo_key(self, photo):
        raw_path = getattr(photo, "path", photo)
        return self._normalize_path_key(raw_path)

    def _normalize_path_key(self, value) -> str:
        if value is None:
            return ""

        path = Path(str(value))
        try:
            return str(path.resolve())
        except Exception:
            return str(path)

    def eventFilter(self, watched, event):
        if watched is self.scroll_area.viewport() and event.type() == QEvent.Type.Resize:
            self._on_viewport_resized()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._on_viewport_resized()

    def _on_viewport_resized(self):
        self._sync_content_width()
        new_columns = self._calculate_grid_columns()
        if new_columns == self._grid_columns:
            return
        self._grid_columns = new_columns
        self._relayout_cards()

    def _calculate_grid_columns(self) -> int:
        viewport_width = self.scroll_area.viewport().width()
        if viewport_width <= 0:
            viewport_width = self.width()
        width = max(_CARD_CELL_WIDTH, viewport_width)
        return max(1, width // _CARD_CELL_WIDTH)

    def _relayout_cards(self) -> None:
        self.content_widget.setUpdatesEnabled(False)
        try:
            for index, card in enumerate(self._cards):
                self.grid_layout.removeWidget(card)
                row = index // self._grid_columns
                col = index % self._grid_columns
                self.grid_layout.addWidget(card, row, col)
        finally:
            self.content_widget.setUpdatesEnabled(True)

    def rendered_card_count(self) -> int:
        return len(self._cards)

    def _schedule_batch_add(self):
        if self._target_render_count <= 0 and self._photos:
            self._target_render_count = min(self._initial_render_count, len(self._photos))
        self._sync_content_width()
        QTimer.singleShot(0, self._add_next_batch)

    def _add_next_batch(self):
        render_limit = min(self._target_render_count, len(self._photos))
        if self._pending_photo_index >= render_limit:
            return

        batch_end = min(self._pending_photo_index + self._batch_size, render_limit)

        self.content_widget.setUpdatesEnabled(False)
        try:
            for index in range(self._pending_photo_index, batch_end):
                photo = self._photos[index]
                key = self._photo_key(photo)
                card = PhotoCardWidget(photo)
                card.photo_clicked.connect(self._handle_card_click)
                row = len(self._cards) // self._grid_columns
                column = len(self._cards) % self._grid_columns
                self.grid_layout.addWidget(card, row, column)
                self._cards.append(card)
                self._cards_by_key[key] = card

                card.set_selected(key == self._selected_photo_key)

                card.refresh_from_photo()

                pending_pixmap = self._pending_thumbnail_updates.pop(key, None)
                if pending_pixmap is not None:
                    card.set_thumbnail(pending_pixmap)
        finally:
            self.content_widget.setUpdatesEnabled(True)

        self._pending_photo_index = batch_end

        if self._pending_photo_index < render_limit:
            QTimer.singleShot(0, self._add_next_batch)

    def _on_scroll_changed(self, value: int):
        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar.maximum() <= 0:
            return
        if value < scrollbar.maximum() - 220:
            return
        if self._target_render_count >= len(self._photos):
            return

        self._target_render_count = min(
            self._target_render_count + self._batch_size,
            len(self._photos),
        )
        QTimer.singleShot(0, self._add_next_batch)

    def _sync_content_width(self):
        viewport_width = self.scroll_area.viewport().width()
        if viewport_width > 0:
            self.content_widget.setMinimumWidth(viewport_width)

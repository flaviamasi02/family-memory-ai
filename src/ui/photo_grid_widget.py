from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QScrollArea, QSizePolicy, QWidget

from ui.photo_card_widget import PhotoCardWidget


class PhotoGridWidget(QWidget):
    photo_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._cards = []
        self._cards_by_key = {}
        self._photos = []
        self._pending_photo_index = 0
        self._batch_size = 50
        self._pending_thumbnail_updates = {}
        self._selected_photo_key = None

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)

        self.content_widget = QWidget(self.scroll_area)
        self.content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.grid_layout = QGridLayout(self.content_widget)
        self.grid_layout.setContentsMargins(12, 12, 12, 12)
        self.grid_layout.setSpacing(12)
        self.scroll_area.setWidget(self.content_widget)

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
        self._selected_photo_key = None

        valid_keys = {self._photo_key(photo) for photo in self._photos}
        self._pending_thumbnail_updates = {
            key: pixmap for key, pixmap in existing_pending.items() if key in valid_keys
        }

        self._schedule_batch_add()

    def update_thumbnail(self, photo, pixmap):
        key = self._photo_key(photo)
        if key in self._cards_by_key:
            self._cards_by_key[key].set_thumbnail(pixmap)
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
        return str(getattr(photo, "path", ""))

    def _schedule_batch_add(self):
        QTimer.singleShot(0, self._add_next_batch)

    def _add_next_batch(self):
        if self._pending_photo_index >= len(self._photos):
            return

        batch_end = min(self._pending_photo_index + self._batch_size, len(self._photos))
        for index in range(self._pending_photo_index, batch_end):
            photo = self._photos[index]
            key = self._photo_key(photo)
            card = PhotoCardWidget(photo)
            card.photo_clicked.connect(self._handle_card_click)
            row = len(self._cards) // 3
            column = len(self._cards) % 3
            self.grid_layout.addWidget(card, row, column)
            self._cards.append(card)
            self._cards_by_key[key] = card

            card.set_selected(key == self._selected_photo_key)

            card.refresh_from_photo()

            pending_pixmap = self._pending_thumbnail_updates.pop(key, None)
            if pending_pixmap is not None:
                card.set_thumbnail(pending_pixmap)

        self._pending_photo_index = batch_end

        if self._pending_photo_index < len(self._photos):
            QTimer.singleShot(0, self._add_next_batch)

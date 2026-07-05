from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


@dataclass
class SharedGridItem:
    key: str
    filename: str
    thumbnail: Optional[QPixmap]
    badge_one: str
    badge_two: str
    badge_three: str


class SharedThumbnailCard(QFrame):
    clicked = Signal(str, int)
    double_clicked = Signal(str)

    def __init__(self, item: SharedGridItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.key = item.key

        self.setObjectName("sharedReviewCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedWidth(164)
        self.setFixedHeight(228)

        self.thumbnail_label = QLabel("No thumbnail")
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setFixedSize(140, 140)
        self.thumbnail_label.setStyleSheet("border: 1px solid #bbb; background: #f6f6f6;")

        self.filename_label = QLabel("")
        self.filename_label.setWordWrap(False)
        self.filename_label.setStyleSheet("font-weight: 600;")
        self.filename_label.setFixedWidth(148)
        self.filename_label.setMaximumHeight(20)

        self.badge_one = QLabel("")
        self.badge_two = QLabel("")
        self.badge_three = QLabel("")
        for badge in (self.badge_one, self.badge_two, self.badge_three):
            badge.setStyleSheet("background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 6px; padding: 2px 6px;")
            badge.setMaximumHeight(22)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(self.thumbnail_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.filename_label)

        badges = QHBoxLayout()
        badges.setContentsMargins(0, 0, 0, 0)
        badges.setSpacing(4)
        badges.addWidget(self.badge_one)
        badges.addWidget(self.badge_two)
        badges.addWidget(self.badge_three)
        layout.addLayout(badges)

        self.refresh(item)
        self.set_selected(False)

    def refresh(self, item: SharedGridItem) -> None:
        self.item = item
        self.key = item.key

        pixmap = item.thumbnail
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            scaled = pixmap.scaled(
                140,
                140,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.thumbnail_label.setPixmap(scaled)
            self.thumbnail_label.setText("")
        else:
            self.thumbnail_label.setPixmap(QPixmap())
            self.thumbnail_label.setText("No thumbnail")

        self.filename_label.setToolTip(item.filename)
        metrics = QFontMetrics(self.filename_label.font())
        self.filename_label.setText(metrics.elidedText(item.filename, Qt.TextElideMode.ElideRight, self.filename_label.width()))
        self.badge_one.setText(item.badge_one)
        self.badge_two.setText(item.badge_two)
        self.badge_three.setText(item.badge_three)

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet(
                "QFrame#sharedReviewCard { border: 2px solid #1f6feb; border-radius: 6px; background: #eef6ff; }"
            )
        else:
            self.setStyleSheet(
                "QFrame#sharedReviewCard { border: 1px solid #c9c9c9; border-radius: 6px; background: #ffffff; }"
            )

    def mousePressEvent(self, event):
        self.clicked.emit(self.key, int(event.modifiers().value))
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self.key)
        super().mouseDoubleClickEvent(event)


class SharedThumbnailGrid(QWidget):
    selection_changed = Signal(object, object)
    card_double_clicked = Signal(str)

    def __init__(self, parent=None, initial_render_count: int = 100, render_batch_size: int = 60):
        super().__init__(parent)

        self._items: list[SharedGridItem] = []
        self._items_by_key: dict[str, SharedGridItem] = {}
        self._pending_render_index = 0
        self._target_render_count = 0
        self._initial_render_count = int(initial_render_count)
        self._render_batch_size = int(render_batch_size)
        self._grid_columns = 4
        self._selection_anchor_key: Optional[str] = None
        self._selected_key: Optional[str] = None
        self._selected_keys: set[str] = set()

        self._cards_by_key: dict[str, SharedThumbnailCard] = {}
        self._rendered_keys: list[str] = []

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.content_widget = QWidget(self.scroll_area)
        self.content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.grid_layout = QGridLayout(self.content_widget)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(8)
        self.scroll_area.setWidget(self.content_widget)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.scroll_area)

    def set_items(self, items: list[SharedGridItem]) -> None:
        self._items = list(items or [])
        self._items_by_key = {item.key: item for item in self._items}

        visible_keys = {item.key for item in self._items}
        self._selected_keys = {key for key in self._selected_keys if key in visible_keys}
        if self._selected_key not in visible_keys:
            self._selected_key = None
        if not self._selected_keys and self._selected_key is not None:
            self._selected_keys = {self._selected_key}

        if not self._selected_keys and self._items:
            self._selected_key = self._items[0].key
            self._selected_keys = {self._selected_key}
            self._selection_anchor_key = self._selected_key

        self._rebuild_grid()

    def update_item(self, item: SharedGridItem) -> None:
        self._items_by_key[item.key] = item
        for index, existing in enumerate(self._items):
            if existing.key == item.key:
                self._items[index] = item
                break

        card = self._cards_by_key.get(item.key)
        if card is not None:
            card.refresh(item)
            card.set_selected(item.key in self._selected_keys)

    def visible_keys(self) -> list[str]:
        return [item.key for item in self._items]

    def selected_keys(self) -> list[str]:
        return sorted(self._selected_keys)

    def selected_count(self) -> int:
        return len(self._selected_keys)

    def selected_key(self) -> Optional[str]:
        return self._selected_key

    def set_single_selection(self, key: str) -> None:
        if key not in self._items_by_key:
            return
        self._selected_key = key
        self._selected_keys = {key}
        self._selection_anchor_key = key
        self._refresh_card_selection()
        self.selection_changed.emit(set(self._selected_keys), self._selected_key)

    def select_all_visible(self) -> None:
        self._selected_keys = {item.key for item in self._items}
        if self._items:
            self._selected_key = self._items[0].key
            self._selection_anchor_key = self._selected_key
        self._refresh_card_selection()
        self.selection_changed.emit(set(self._selected_keys), self._selected_key)

    def clear_selection(self) -> None:
        self._selected_keys.clear()
        self._selected_key = None
        self._selection_anchor_key = None
        self._refresh_card_selection()
        self.selection_changed.emit(set(self._selected_keys), self._selected_key)

    def grid_column_count(self) -> int:
        return self._grid_columns

    def compact_card_size(self) -> tuple[int, int]:
        if not self._cards_by_key:
            return 0, 0
        first_key = next(iter(self._cards_by_key.keys()))
        card = self._cards_by_key[first_key]
        return card.width(), card.height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_columns = self._calculate_grid_columns()
        if new_columns == self._grid_columns:
            return
        self._grid_columns = new_columns
        self._relayout_cards()

    def _rebuild_grid(self) -> None:
        for card in self._cards_by_key.values():
            self.grid_layout.removeWidget(card)
            card.deleteLater()

        self._cards_by_key.clear()
        self._rendered_keys.clear()
        self._pending_render_index = 0
        self._target_render_count = 0
        self._grid_columns = self._calculate_grid_columns()

        if not self._items:
            self.selection_changed.emit(set(self._selected_keys), self._selected_key)
            return

        self._target_render_count = min(self._initial_render_count, len(self._items))
        QTimer.singleShot(0, self._add_next_batch)

    def _add_next_batch(self) -> None:
        render_limit = min(self._target_render_count, len(self._items))
        if self._pending_render_index >= render_limit:
            self._refresh_card_selection()
            self.selection_changed.emit(set(self._selected_keys), self._selected_key)
            return

        batch_end = min(self._pending_render_index + self._render_batch_size, render_limit)
        for index in range(self._pending_render_index, batch_end):
            item = self._items[index]
            card = SharedThumbnailCard(item=item)
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self._on_card_double_clicked)
            self._cards_by_key[item.key] = card
            self._rendered_keys.append(item.key)

            card_index = len(self._rendered_keys) - 1
            grid_row = card_index // self._grid_columns
            grid_column = card_index % self._grid_columns
            self.grid_layout.addWidget(card, grid_row, grid_column)

        self._pending_render_index = batch_end
        self._refresh_card_selection()

        if self._pending_render_index >= render_limit:
            self.selection_changed.emit(set(self._selected_keys), self._selected_key)

    def _on_scroll_changed(self, value: int) -> None:
        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar.maximum() <= 0:
            return
        if value < scrollbar.maximum() - 180:
            return
        if self._target_render_count >= len(self._items):
            return

        self._target_render_count = min(self._target_render_count + self._render_batch_size, len(self._items))
        QTimer.singleShot(0, self._add_next_batch)

    def _on_card_clicked(self, key: str, modifiers: int) -> None:
        ctrl_pressed = bool(modifiers & int(Qt.KeyboardModifier.ControlModifier.value))
        shift_pressed = bool(modifiers & int(Qt.KeyboardModifier.ShiftModifier.value))

        if shift_pressed and self._selection_anchor_key:
            range_keys = self._range_keys_between(self._selection_anchor_key, key)
            if ctrl_pressed:
                self._selected_keys.update(range_keys)
            else:
                self._selected_keys = set(range_keys)
        elif ctrl_pressed:
            if key in self._selected_keys:
                self._selected_keys.remove(key)
            else:
                self._selected_keys.add(key)
            self._selection_anchor_key = key
        else:
            self._selected_keys = {key}
            self._selection_anchor_key = key

        self._selected_key = key
        self._refresh_card_selection()
        self.selection_changed.emit(set(self._selected_keys), self._selected_key)

    def _on_card_double_clicked(self, key: str) -> None:
        if key not in self._items_by_key:
            return
        if key not in self._selected_keys:
            self._selected_keys = {key}
        self._selected_key = key
        self._refresh_card_selection()
        self.selection_changed.emit(set(self._selected_keys), self._selected_key)
        self.card_double_clicked.emit(key)

    def _range_keys_between(self, start_key: str, end_key: str) -> list[str]:
        visible_keys = self.visible_keys()
        if start_key not in visible_keys or end_key not in visible_keys:
            return [end_key]

        start_index = visible_keys.index(start_key)
        end_index = visible_keys.index(end_key)
        if start_index <= end_index:
            return visible_keys[start_index:end_index + 1]
        return visible_keys[end_index:start_index + 1]

    def _calculate_grid_columns(self) -> int:
        width = max(176, self.scroll_area.viewport().width())
        return max(1, width // 172)

    def _relayout_cards(self) -> None:
        for index, key in enumerate(self._rendered_keys):
            card = self._cards_by_key.get(key)
            if card is None:
                continue
            self.grid_layout.removeWidget(card)
            row = index // self._grid_columns
            col = index % self._grid_columns
            self.grid_layout.addWidget(card, row, col)

    def _refresh_card_selection(self) -> None:
        for key, card in self._cards_by_key.items():
            card.set_selected(key in self._selected_keys)

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.safe_file_move_service import CLEANUP_REVIEW_FOLDER_NAME, move_files_to_cleanup_review


class IrrelevantMediaPage(QWidget):
    moved_photos = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._photos = []
        self._visible_photos = []
        self._row_by_key = {}
        self._imported_root: Optional[Path] = None

        self.summary_label = QLabel("Cleanup files: 0")
        self.result_label = QLabel("Select files to move them safely into the cleanup-review folder.")
        self.result_label.setWordWrap(True)

        self.category_combo = QComboBox()
        self.category_combo.currentTextChanged.connect(self._refresh_table)

        self.select_all_button = QPushButton("Select all in current category")
        self.select_all_button.clicked.connect(self.select_all_current_category)

        self.move_button = QPushButton("Move selected to cleanup review folder")
        self.move_button.clicked.connect(self.move_selected_to_quarantine)

        header_layout = QHBoxLayout()
        header_layout.addWidget(self.summary_label)
        header_layout.addWidget(QLabel("Category:"))
        header_layout.addWidget(self.category_combo)
        header_layout.addWidget(self.select_all_button)
        header_layout.addStretch(1)
        header_layout.addWidget(self.move_button)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Move", "Thumbnail", "Category", "Filename", "Reasons", "Recommended action"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 64)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 260)
        self.table.setColumnWidth(5, 180)

        layout = QVBoxLayout(self)
        layout.addLayout(header_layout)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.result_label)

    def set_photos(self, photos, imported_root: Optional[str | Path]) -> None:
        self._photos = list(photos or [])
        self._visible_photos = []
        self._imported_root = Path(imported_root) if imported_root else None

        categories = sorted({self._category_for_photo(photo) for photo in self._photos})
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("All cleanup files")
        for category in categories:
            self.category_combo.addItem(self._display_category_name(category))
        self.category_combo.blockSignals(False)
        self._refresh_table()

        destination_text = "-"
        if self._imported_root is not None:
            destination_text = str(self._imported_root / CLEANUP_REVIEW_FOLDER_NAME)
        self.summary_label.setText(f"Cleanup files: {len(self._photos)}")
        self.result_label.setText(f"Cleanup-review destination: {destination_text}")

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        self._row_by_key = {}

        current_category = self._current_category_filter()
        self._visible_photos = [
            photo for photo in self._photos
            if current_category is None or self._category_for_photo(photo) == current_category
        ]

        for photo in self._visible_photos:
            self._append_photo(photo)

    def _append_photo(self, photo) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        key = self._photo_key(photo)
        self._row_by_key[key] = row

        checkbox_item = QTableWidgetItem("")
        checkbox_item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        checkbox_item.setCheckState(Qt.CheckState.Checked)
        self.table.setItem(row, 0, checkbox_item)

        thumbnail_item = QTableWidgetItem("")
        thumbnail = getattr(photo, "thumbnail", None)
        if isinstance(thumbnail, QPixmap) and not thumbnail.isNull():
            thumbnail_item.setIcon(QIcon(thumbnail))
        self.table.setItem(row, 1, thumbnail_item)

        intelligence = getattr(photo, "intelligence", None)
        category = getattr(intelligence, "relevance_category", "unknown") if intelligence else "unknown"
        reasons = getattr(photo, "metadata", {}).get("cleanup_reasons") or []
        if not reasons:
            reason_value = getattr(intelligence, "relevance_reason", "-") if intelligence else "-"
            reasons = [reason_value] if reason_value and reason_value != "-" else []
        recommended_action = getattr(photo, "metadata", {}).get("cleanup_recommended_action", "review")

        self.table.setItem(row, 2, QTableWidgetItem(self._display_category_name(str(category))))
        self.table.setItem(row, 3, QTableWidgetItem(photo.display_name()))
        self.table.setItem(row, 4, QTableWidgetItem("; ".join(str(reason) for reason in reasons) or "-"))
        self.table.setItem(row, 5, QTableWidgetItem(str(recommended_action)))

    def update_thumbnail(self, photo, pixmap) -> None:
        row = self._row_by_key.get(self._photo_key(photo))
        if row is None:
            return

        item = self.table.item(row, 1)
        if item is None:
            item = QTableWidgetItem("")
            self.table.setItem(row, 1, item)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            item.setIcon(QIcon(pixmap))

    def selected_photos(self) -> list:
        selected = []
        for photo in self._visible_photos:
            row = self._row_by_key.get(self._photo_key(photo))
            if row is None:
                continue
            item = self.table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                selected.append(photo)
        return selected

    def select_all_current_category(self) -> None:
        for photo in self._visible_photos:
            row = self._row_by_key.get(self._photo_key(photo))
            if row is None:
                continue
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked)

    def move_selected_to_quarantine(self) -> None:
        if self._imported_root is None:
            self.result_label.setText("No imported folder is available for safe move.")
            return

        selected = self.selected_photos()
        if not selected:
            self.result_label.setText("No cleanup files are selected.")
            return

        destination = self._imported_root / CLEANUP_REVIEW_FOLDER_NAME
        confirmation = QMessageBox(self)
        confirmation.setIcon(QMessageBox.Icon.Warning)
        confirmation.setWindowTitle("Confirm safe move")
        confirmation.setText(
            f"Move {len(selected)} file(s) to {destination}?"
        )
        confirmation.setInformativeText(
            "Files will be moved out of the imported library into the cleanup-review folder. They will not be permanently deleted."
        )
        confirmation.setDetailedText("\n".join(photo.display_name() for photo in selected))
        confirmation.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirmation.setDefaultButton(QMessageBox.StandardButton.No)
        if confirmation.exec() != QMessageBox.StandardButton.Yes:
            self.result_label.setText("Safe move cancelled.")
            return

        result = move_files_to_cleanup_review(
            [photo.path for photo in selected],
            self._imported_root,
        )

        moved_source_keys = []
        for photo in selected:
            if str(photo.path) in result.skipped_files or str(photo.path) in result.failed_files:
                continue
            moved_source_keys.append(self._photo_key(photo))

        moved_photos = [photo for photo in self._photos if self._photo_key(photo) in moved_source_keys]
        if moved_photos:
            moved_key_set = set(moved_source_keys)
            self._photos = [photo for photo in self._photos if self._photo_key(photo) not in moved_key_set]
            self.set_photos(self._photos, self._imported_root)
            self.moved_photos.emit(moved_photos)

        self.result_label.setText(
            f"Safe move completed. moved={result.moved_count}, failed={result.failed_count}, skipped={result.skipped_count}."
        )

    def _photo_key(self, photo) -> str:
        return str(getattr(photo, "path", ""))

    def _current_category_filter(self) -> str | None:
        text = self.category_combo.currentText().strip()
        if not text or text == "All cleanup files":
            return None

        for category in self._available_categories():
            if self._display_category_name(category) == text:
                return category
        return None

    def _available_categories(self) -> list[str]:
        return sorted({self._category_for_photo(photo) for photo in self._photos})

    def _category_for_photo(self, photo) -> str:
        intelligence = getattr(photo, "intelligence", None)
        return str(getattr(intelligence, "relevance_category", "unknown") or "unknown")

    def _display_category_name(self, category: str) -> str:
        labels = {
            "family_photo_candidate": "Family photo candidates",
            "document_or_scan": "Documents/scans",
            "advertisement": "Advertisements",
            "screenshot": "Screenshots",
            "meme_or_graphic": "Memes/graphics",
            "video": "Videos",
            "duplicate_candidate": "Duplicates",
            "low_quality_photo": "Low quality",
            "unknown": "Unknown",
        }
        return labels.get(category, category)
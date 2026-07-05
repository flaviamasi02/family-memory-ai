from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.safe_file_move_service import CLEANUP_REVIEW_FOLDER_NAME, move_files_to_cleanup_review
from ui.image_preview_dialog import ImagePreviewDialog


CATEGORY_LABELS = {
    "family_photo_candidate": "Family photos",
    "document_or_scan": "Documents",
    "advertisement": "Advertisements",
    "screenshot": "Screenshots",
    "meme_or_graphic": "Memes",
    "video": "Videos",
    "duplicate_candidate": "Duplicates",
    "low_quality_photo": "Low quality",
    "unknown": "Unknown",
}

KNOWN_CATEGORIES = [
    "family_photo_candidate",
    "document_or_scan",
    "screenshot",
    "advertisement",
    "meme_or_graphic",
    "duplicate_candidate",
    "low_quality_photo",
    "unknown",
    "video",
]

RECOMMENDED_ACTION_LABELS = {
    "keep": "Keep",
    "move_to_cleanup_folder": "Move to Cleanup Folder",
    "move_to_cleanup_review": "Move to Cleanup Folder",
    "review": "Needs Review",
    "unknown": "Unknown",
}


@dataclass
class CleanupReviewRow:
    photo: object
    automatic_category: str
    user_corrected_category: str
    effective_category: str
    confidence: float
    recommended_action: str
    reasons: list[str]
    user_decision: str = "pending"


class CleanupReviewCardWidget(QFrame):
    clicked = Signal(str, int)
    double_clicked = Signal(str)

    def __init__(self, row: CleanupReviewRow, key: str, parent=None):
        super().__init__(parent)
        self.row = row
        self.key = key

        self.setObjectName("cleanupReviewCard")
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

        self.category_badge = QLabel("")
        self.confidence_badge = QLabel("")
        self.action_badge = QLabel("")
        for badge in (self.category_badge, self.confidence_badge, self.action_badge):
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
        badges.addWidget(self.category_badge)
        badges.addWidget(self.confidence_badge)
        badges.addWidget(self.action_badge)
        layout.addLayout(badges)

        self.refresh_from_row()
        self.set_selected(False)

    def refresh_from_row(self) -> None:
        photo = self.row.photo
        thumbnail = getattr(photo, "thumbnail", None)
        if isinstance(thumbnail, QPixmap) and not thumbnail.isNull():
            scaled = thumbnail.scaled(
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

        full_name = photo.display_name()
        self.filename_label.setToolTip(full_name)
        metrics = QFontMetrics(self.filename_label.font())
        self.filename_label.setText(metrics.elidedText(full_name, Qt.TextElideMode.ElideRight, self.filename_label.width()))

        category_text = _display_category(self.row.automatic_category)
        confidence_text = f"{max(0, min(100, int(round(self.row.confidence * 100))))}%"
        action_text = _display_action(self.row.recommended_action)

        self.category_badge.setText(_shorten_badge(category_text))
        self.confidence_badge.setText(confidence_text)
        self.action_badge.setText(_shorten_badge(action_text))

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet(
                "QFrame#cleanupReviewCard { border: 2px solid #1f6feb; border-radius: 6px; background: #eef6ff; }"
            )
        else:
            self.setStyleSheet(
                "QFrame#cleanupReviewCard { border: 1px solid #c9c9c9; border-radius: 6px; background: #ffffff; }"
            )

    def mousePressEvent(self, event):
        self.clicked.emit(self.key, int(event.modifiers().value))
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self.key)
        super().mouseDoubleClickEvent(event)


class IrrelevantMediaPage(QWidget):
    moved_photos = Signal(object)

    CATEGORY_FILTER_ALL = "All categories"
    CONFIDENCE_FILTER_ALL = "All"
    ACTION_FILTER_ALL = "All"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[CleanupReviewRow] = []
        self._visible_rows: list[CleanupReviewRow] = []
        self._cards_by_key: dict[str, CleanupReviewCardWidget] = {}
        self._rendered_keys: list[str] = []
        self._selected_keys: set[str] = set()
        self._selected_key: Optional[str] = None
        self._selection_anchor_key: Optional[str] = None
        self._details_key: Optional[str] = None
        self._imported_root: Optional[Path] = None
        self._imported_total_count = 0
        self._pending_render_index = 0
        self._target_render_count = 0
        self._initial_render_count = 100
        self._render_batch_size = 60
        self._grid_columns = 4
        self._preview_dialog: Optional[ImagePreviewDialog] = None

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(220)
        self._search_timer.timeout.connect(self._trigger_refresh)

        self.title_label = QLabel("Cleanup Review")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 600;")

        self.stats_label = QLabel("Imported: 0 | Cleanup candidates: 0 | Average confidence: 0%")
        self.stats_label.setWordWrap(True)

        self.category_filter_combo = QComboBox()
        self.category_filter_combo.currentTextChanged.connect(self._trigger_refresh)

        self.confidence_filter_combo = QComboBox()
        self.confidence_filter_combo.addItems([
            self.CONFIDENCE_FILTER_ALL,
            "High (>=80%)",
            "Medium (50-79%)",
            "Low (<50%)",
        ])
        self.confidence_filter_combo.currentTextChanged.connect(self._trigger_refresh)

        self.action_filter_combo = QComboBox()
        self.action_filter_combo.addItems([
            self.ACTION_FILTER_ALL,
            "Keep",
            "Move to Cleanup Folder",
            "Needs Review",
            "Unknown",
        ])
        self.action_filter_combo.currentTextChanged.connect(self._trigger_refresh)

        self.group_combo = QComboBox()
        self.group_combo.currentTextChanged.connect(self._on_group_changed)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search filename...")
        self.search_input.textChanged.connect(self._on_search_changed)

        self.selection_count_label = QLabel("Selected: 0")
        self.select_all_button = QPushButton("Select All Visible")
        self.select_all_button.clicked.connect(self.select_all_visible)
        self.clear_selection_button = QPushButton("Clear Selection")
        self.clear_selection_button.clicked.connect(self.clear_selection)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Category:"))
        toolbar.addWidget(self.category_filter_combo)
        toolbar.addWidget(QLabel("Confidence:"))
        toolbar.addWidget(self.confidence_filter_combo)
        toolbar.addWidget(QLabel("Recommended action:"))
        toolbar.addWidget(self.action_filter_combo)
        toolbar.addWidget(QLabel("Group:"))
        toolbar.addWidget(self.group_combo)
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(self.selection_count_label)
        toolbar.addWidget(self.select_all_button)
        toolbar.addWidget(self.clear_selection_button)

        self.results_label = QLabel("Showing 0 photos")

        self.grid_scroll = QScrollArea(self)
        self.grid_scroll.setWidgetResizable(True)
        self.grid_content = QWidget(self.grid_scroll)
        self.grid_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.grid_layout = QGridLayout(self.grid_content)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(8)
        self.grid_scroll.setWidget(self.grid_content)
        self.grid_scroll.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

        self.preview_label = QLabel("No preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(320, 220)
        self.preview_label.setStyleSheet("border: 1px solid #aaa;")

        self.filename_value = QLabel("-")
        self.automatic_category_value = QLabel("-")
        self.confidence_value = QLabel("-")
        self.recommended_action_value = QLabel("-")
        self.user_category_value = QLabel("-")
        self.effective_category_value = QLabel("-")
        self.decision_value = QLabel("-")
        self.metadata_summary_value = QLabel("-")
        self.metadata_summary_value.setWordWrap(True)

        details_form = QFormLayout()
        details_form.addRow("Filename:", self.filename_value)
        details_form.addRow("Automatic category:", self.automatic_category_value)
        details_form.addRow("Confidence:", self.confidence_value)
        details_form.addRow("Recommended action:", self.recommended_action_value)
        details_form.addRow("Current user category:", self.user_category_value)
        details_form.addRow("Effective category:", self.effective_category_value)
        details_form.addRow("Current decision:", self.decision_value)
        details_form.addRow("Metadata summary:", self.metadata_summary_value)

        self.reason_title = QLabel("Why was this classified?")
        self.reasons_list = QListWidget()
        self.reasons_list.setMinimumHeight(140)

        self.alternatives_title = QLabel("Possible alternatives")
        self.alternatives_list = QListWidget()
        self.alternatives_list.setMinimumHeight(100)

        self.keep_button = QPushButton("Keep")
        self.keep_button.clicked.connect(lambda: self._set_decision_for_selected("keep"))
        self.move_button = QPushButton("Move to Cleanup Folder")
        self.move_button.clicked.connect(self.move_selected_to_quarantine)
        self.mark_family_button = QPushButton("Mark as Family Photo")
        self.mark_family_button.clicked.connect(lambda: self._apply_category_to_selected("family_photo_candidate"))
        self.mark_document_button = QPushButton("Mark as Document")
        self.mark_document_button.clicked.connect(lambda: self._apply_category_to_selected("document_or_scan"))
        self.mark_ad_button = QPushButton("Mark as Advertisement")
        self.mark_ad_button.clicked.connect(lambda: self._apply_category_to_selected("advertisement"))
        self.mark_meme_button = QPushButton("Mark as Meme")
        self.mark_meme_button.clicked.connect(lambda: self._apply_category_to_selected("meme_or_graphic"))
        self.mark_screenshot_button = QPushButton("Mark as Screenshot")
        self.mark_screenshot_button.clicked.connect(lambda: self._apply_category_to_selected("screenshot"))
        self.mark_duplicate_button = QPushButton("Duplicate")
        self.mark_duplicate_button.clicked.connect(lambda: self._apply_category_to_selected("duplicate_candidate"))
        self.mark_unknown_button = QPushButton("Unknown")
        self.mark_unknown_button.clicked.connect(lambda: self._apply_category_to_selected("unknown"))

        actions_row_one = QHBoxLayout()
        actions_row_one.addWidget(self.keep_button)
        actions_row_one.addWidget(self.move_button)

        actions_row_two = QHBoxLayout()
        actions_row_two.addWidget(self.mark_family_button)
        actions_row_two.addWidget(self.mark_document_button)
        actions_row_two.addWidget(self.mark_ad_button)

        actions_row_three = QHBoxLayout()
        actions_row_three.addWidget(self.mark_meme_button)
        actions_row_three.addWidget(self.mark_screenshot_button)
        actions_row_three.addWidget(self.mark_duplicate_button)
        actions_row_three.addWidget(self.mark_unknown_button)

        details_layout = QVBoxLayout()
        details_layout.addWidget(QLabel("Preview"))
        details_layout.addWidget(self.preview_label)
        details_layout.addLayout(details_form)
        details_layout.addWidget(self.reason_title)
        details_layout.addWidget(self.reasons_list)
        details_layout.addWidget(self.alternatives_title)
        details_layout.addWidget(self.alternatives_list)
        details_layout.addLayout(actions_row_one)
        details_layout.addLayout(actions_row_two)
        details_layout.addLayout(actions_row_three)

        details_panel = QWidget()
        details_panel.setLayout(details_layout)
        details_panel.setMinimumWidth(440)

        grid_panel = QWidget()
        grid_panel_layout = QVBoxLayout(grid_panel)
        grid_panel_layout.setContentsMargins(0, 0, 0, 0)
        grid_panel_layout.addWidget(self.results_label)
        grid_panel_layout.addWidget(self.grid_scroll, 1)

        splitter = QSplitter()
        splitter.addWidget(grid_panel)
        splitter.addWidget(details_panel)
        splitter.setStretchFactor(0, 8)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([1000, 440])

        root = QVBoxLayout(self)
        root.addWidget(self.title_label)
        root.addWidget(self.stats_label)
        root.addLayout(toolbar)
        root.addWidget(splitter, 1)

        self._reset_filter_options()
        self._clear_details()
        self._refresh_alternatives_visibility(False)

    def set_photos(self, photos, imported_root: Optional[str | Path], total_imported_count: Optional[int] = None) -> None:
        self._imported_root = Path(imported_root) if imported_root else None
        self._imported_total_count = int(total_imported_count) if isinstance(total_imported_count, int) else len(photos or [])

        self._rows = [self._build_row(photo) for photo in list(photos or [])]
        self._selected_keys = set()
        self._selected_key = None
        self._selection_anchor_key = None
        self._details_key = None

        self._reset_filter_options()
        self._refresh_group_options()
        self._trigger_refresh(force=True)

    def update_thumbnail(self, photo, pixmap) -> None:
        key = self._photo_key(photo)
        for row in self._rows:
            if self._photo_key(row.photo) != key:
                continue
            if isinstance(pixmap, QPixmap) and not pixmap.isNull():
                row.photo.thumbnail = pixmap
            card = self._cards_by_key.get(key)
            if card is not None:
                card.refresh_from_row()
            if self._selected_key == key:
                self._show_details(row, force=True)
            break

    def visible_filenames(self) -> list[str]:
        return [row.photo.display_name() for row in self._visible_rows]

    def selected_count(self) -> int:
        return len(self._selected_keys)

    def select_photo_by_filename(self, filename: str) -> bool:
        target = (filename or "").strip()
        if not target:
            return False

        for row in self._visible_rows:
            if row.photo.display_name() == target:
                key = self._photo_key(row.photo)
                self._selected_key = key
                self._selected_keys = {key}
                self._selection_anchor_key = key
                self._refresh_card_selection()
                self._refresh_selection_label()
                self._show_details(row, force=True)
                return True
        return False

    def card_summary_for_filename(self, filename: str) -> Optional[dict[str, str]]:
        target = (filename or "").strip()
        if not target:
            return None

        for row in self._visible_rows:
            if row.photo.display_name() != target:
                continue
            card = self._cards_by_key.get(self._photo_key(row.photo))
            if card is None:
                return None
            return {
                "category": card.category_badge.text(),
                "confidence": card.confidence_badge.text(),
                "action": card.action_badge.text(),
            }
        return None

    def possible_alternatives_visible(self) -> bool:
        return (not self.alternatives_title.isHidden()) and (not self.alternatives_list.isHidden())

    def select_all_visible(self) -> None:
        self._selected_keys = {self._photo_key(row.photo) for row in self._visible_rows}
        if self._visible_rows:
            self._selected_key = self._photo_key(self._visible_rows[0].photo)
            self._selection_anchor_key = self._selected_key
            self._show_details(self._visible_rows[0], force=True)
        self._refresh_card_selection()
        self._refresh_selection_label()

    def clear_selection(self) -> None:
        self._selected_keys = set()
        self._selected_key = None
        self._selection_anchor_key = None
        self._refresh_card_selection()
        self._refresh_selection_label()
        self._clear_details()

    def move_selected_to_quarantine(self) -> None:
        if self._imported_root is None:
            return

        selected_rows = self._selected_rows()
        if not selected_rows:
            return

        destination = self._imported_root / CLEANUP_REVIEW_FOLDER_NAME
        response = QMessageBox.question(
            self,
            "Confirm safe move",
            (
                f"Move {len(selected_rows)} file(s) to {destination}?\n"
                "Files will be moved safely to cleanup review, never permanently deleted."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        result = move_files_to_cleanup_review([row.photo.path for row in selected_rows], self._imported_root)
        moved_sources = {
            str(row.photo.path)
            for row in selected_rows
            if str(row.photo.path) not in result.skipped_files and str(row.photo.path) not in result.failed_files
        }
        moved_photos = [row.photo for row in selected_rows if str(row.photo.path) in moved_sources]
        if moved_photos:
            self._rows = [row for row in self._rows if str(row.photo.path) not in moved_sources]
            self._selected_keys = {key for key in self._selected_keys if key not in moved_sources}
            self._selected_key = None if self._selected_key in moved_sources else self._selected_key
            self._refresh_group_options()
            self._trigger_refresh(force=True)
            self.moved_photos.emit(moved_photos)

    def _build_row(self, photo) -> CleanupReviewRow:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        automatic = _normalize_category(
            str(
                metadata.get("cleanup_automatic_category")
                or metadata.get("relevance_category")
                or getattr(getattr(photo, "intelligence", None), "relevance_category", "")
                or "unknown"
            )
        )
        corrected = _normalize_category(str(metadata.get("cleanup_user_corrected_category", "")), allow_empty=True)
        effective = corrected if corrected else automatic

        confidence = metadata.get("cleanup_confidence")
        if not isinstance(confidence, (int, float)):
            confidence = metadata.get("classification_confidence", 0.0)
        confidence_value = float(confidence or 0.0)

        reasons_raw = metadata.get("cleanup_reasons") or []
        if not reasons_raw:
            reason_single = metadata.get("relevance_reason") or metadata.get("classification_reason") or ""
            reasons_raw = [reason_single] if str(reason_single).strip() else []
        reasons = [str(item).strip() for item in reasons_raw if str(item).strip()]

        recommended = _normalize_action(str(metadata.get("cleanup_recommended_action", "review")))
        decision = str(metadata.get("cleanup_user_decision", "pending") or "pending").strip().lower()

        metadata["cleanup_automatic_category"] = automatic
        metadata["cleanup_user_corrected_category"] = corrected
        metadata["cleanup_effective_category"] = effective
        metadata["cleanup_recommended_action"] = recommended
        metadata["cleanup_confidence"] = confidence_value
        metadata["relevance_category"] = effective
        metadata["is_album_relevant_candidate"] = effective == "family_photo_candidate"
        photo.metadata = metadata
        photo.relevance_category = effective
        photo.is_album_relevant_candidate = effective == "family_photo_candidate"
        photo.sync_intelligence_from_metadata()

        return CleanupReviewRow(
            photo=photo,
            automatic_category=automatic,
            user_corrected_category=corrected,
            effective_category=effective,
            confidence=confidence_value,
            recommended_action=recommended,
            reasons=reasons,
            user_decision=decision,
        )

    def _on_search_changed(self) -> None:
        self._search_timer.start()

    def _on_group_changed(self) -> None:
        text = self.group_combo.currentText().strip()
        if not text or text == self.CATEGORY_FILTER_ALL:
            self.category_filter_combo.blockSignals(True)
            self.category_filter_combo.setCurrentText(self.CATEGORY_FILTER_ALL)
            self.category_filter_combo.blockSignals(False)
            self._trigger_refresh()
            return

        for category in KNOWN_CATEGORIES:
            label = _display_category(category)
            if text.startswith(f"{label} ("):
                self.category_filter_combo.blockSignals(True)
                self.category_filter_combo.setCurrentText(label)
                self.category_filter_combo.blockSignals(False)
                self._trigger_refresh()
                return

    def _trigger_refresh(self, force: bool = False) -> None:
        _ = force
        self._visible_rows = [
            row
            for row in self._rows
            if self._matches_category_filter(row)
            and self._matches_confidence_filter(row)
            and self._matches_action_filter(row)
            and self._matches_search(row)
        ]
        self._visible_rows.sort(key=lambda row: row.confidence, reverse=True)
        self._refresh_statistics()
        self._refresh_group_options()
        self._results_text()
        self._rebuild_grid()

    def _matches_category_filter(self, row: CleanupReviewRow) -> bool:
        selected = self.category_filter_combo.currentText().strip()
        if not selected or selected == self.CATEGORY_FILTER_ALL:
            return True
        return _display_category(row.effective_category) == selected

    def _matches_confidence_filter(self, row: CleanupReviewRow) -> bool:
        selected = self.confidence_filter_combo.currentText().strip()
        if selected == "High (>=80%)":
            return row.confidence >= 0.8
        if selected == "Medium (50-79%)":
            return 0.5 <= row.confidence < 0.8
        if selected == "Low (<50%)":
            return row.confidence < 0.5
        return True

    def _matches_action_filter(self, row: CleanupReviewRow) -> bool:
        selected = self.action_filter_combo.currentText().strip()
        if not selected or selected == self.ACTION_FILTER_ALL:
            return True
        return _display_action(row.recommended_action) == selected

    def _matches_search(self, row: CleanupReviewRow) -> bool:
        needle = self.search_input.text().strip().lower()
        if not needle:
            return True
        return needle in row.photo.display_name().lower()

    def _results_text(self) -> None:
        self.results_label.setText(
            f"Showing {len(self._visible_rows)} of {len(self._rows)} cleanup candidates"
        )

    def _refresh_statistics(self) -> None:
        counts = {category: 0 for category in KNOWN_CATEGORIES}
        total_conf = 0.0
        for row in self._rows:
            counts[row.effective_category] = counts.get(row.effective_category, 0) + 1
            total_conf += row.confidence

        avg_conf = (total_conf / len(self._rows)) if self._rows else 0.0
        self.stats_label.setText(
            (
                f"Imported: {self._imported_total_count} | Cleanup candidates: {len(self._rows)} | "
                f"Family photos: {counts.get('family_photo_candidate', 0)} | "
                f"Documents: {counts.get('document_or_scan', 0)} | "
                f"Screenshots: {counts.get('screenshot', 0)} | "
                f"Advertisements: {counts.get('advertisement', 0)} | "
                f"Memes: {counts.get('meme_or_graphic', 0)} | "
                f"Unknown: {counts.get('unknown', 0)} | "
                f"Average confidence: {int(round(avg_conf * 100))}%"
            )
        )

    def _refresh_group_options(self) -> None:
        current = self.group_combo.currentText().strip() or self.CATEGORY_FILTER_ALL
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItem(self.CATEGORY_FILTER_ALL)

        counts = {}
        for row in self._rows:
            counts[row.effective_category] = counts.get(row.effective_category, 0) + 1

        for category in KNOWN_CATEGORIES:
            count = counts.get(category, 0)
            if count <= 0:
                continue
            self.group_combo.addItem(f"{_display_category(category)} ({count})")

        index = self.group_combo.findText(current)
        self.group_combo.setCurrentIndex(index if index >= 0 else 0)
        self.group_combo.blockSignals(False)

    def _reset_filter_options(self) -> None:
        category_current = self.category_filter_combo.currentText().strip() or self.CATEGORY_FILTER_ALL
        self.category_filter_combo.blockSignals(True)
        self.category_filter_combo.clear()
        self.category_filter_combo.addItem(self.CATEGORY_FILTER_ALL)
        for category in KNOWN_CATEGORIES:
            self.category_filter_combo.addItem(_display_category(category))
        idx = self.category_filter_combo.findText(category_current)
        self.category_filter_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.category_filter_combo.blockSignals(False)

    def _rebuild_grid(self) -> None:
        for card in self._cards_by_key.values():
            self.grid_layout.removeWidget(card)
            card.deleteLater()

        self._cards_by_key = {}
        self._rendered_keys = []
        self._pending_render_index = 0
        self._grid_columns = self._calculate_grid_columns()

        visible_keys = {self._photo_key(row.photo) for row in self._visible_rows}
        self._selected_keys = {key for key in self._selected_keys if key in visible_keys}
        if self._selected_keys:
            self._selected_key = next(iter(self._selected_keys))
        elif self._visible_rows:
            self._selected_key = self._photo_key(self._visible_rows[0].photo)
            self._selected_keys = {self._selected_key}
            self._selection_anchor_key = self._selected_key
        else:
            self._selected_key = None

        if not self._visible_rows:
            self._refresh_selection_label()
            self._clear_details()
            return

        self._target_render_count = min(self._initial_render_count, len(self._visible_rows))
        self._schedule_render_batch()

    def _schedule_render_batch(self) -> None:
        QTimer.singleShot(0, self._add_next_batch)

    def _add_next_batch(self) -> None:
        render_limit = min(self._target_render_count, len(self._visible_rows))
        if self._pending_render_index >= render_limit:
            self._refresh_card_selection()
            self._refresh_selection_label()
            selected = self._selected_row()
            if selected is not None:
                self._show_details(selected)
            return

        batch_end = min(self._pending_render_index + self._render_batch_size, render_limit)
        for index in range(self._pending_render_index, batch_end):
            row = self._visible_rows[index]
            key = self._photo_key(row.photo)
            card = CleanupReviewCardWidget(row=row, key=key)
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self._on_card_double_clicked)
            self._cards_by_key[key] = card
            self._rendered_keys.append(key)

            card_index = len(self._rendered_keys) - 1
            grid_row = card_index // self._grid_columns
            grid_column = card_index % self._grid_columns
            self.grid_layout.addWidget(card, grid_row, grid_column)

        self._pending_render_index = batch_end
        self._refresh_card_selection()
        self._refresh_selection_label()

    def _on_scroll_changed(self, value: int) -> None:
        scrollbar = self.grid_scroll.verticalScrollBar()
        if scrollbar.maximum() <= 0:
            return
        if value < scrollbar.maximum() - 180:
            return
        if self._target_render_count >= len(self._visible_rows):
            return

        self._target_render_count = min(self._target_render_count + self._render_batch_size, len(self._visible_rows))
        self._schedule_render_batch()

    def _on_card_clicked(self, key: str, modifiers: int = 0) -> None:
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
        self._refresh_selection_label()
        selected = self._selected_row()
        if selected is None:
            self._clear_details()
            return
        self._show_details(selected)

    def _on_card_double_clicked(self, key: str) -> None:
        visible_keys = [self._photo_key(row.photo) for row in self._visible_rows]
        if key not in visible_keys:
            return

        self._selected_key = key
        if key not in self._selected_keys:
            self._selected_keys = {key}
        self._refresh_card_selection()
        self._refresh_selection_label()

        self.open_preview_for_key(key)

    def open_preview_for_key(self, key: str) -> None:
        visible_keys = [self._photo_key(row.photo) for row in self._visible_rows]
        if key not in visible_keys:
            return

        photos = [row.photo for row in self._visible_rows]
        start_index = visible_keys.index(key)
        if self._preview_dialog is None:
            self._preview_dialog = ImagePreviewDialog(self)
        self._preview_dialog.set_items(photos, start_index=start_index)
        self._preview_dialog.show()
        self._preview_dialog.raise_()
        self._preview_dialog.activateWindow()

    def _selected_row(self) -> Optional[CleanupReviewRow]:
        if not self._selected_key:
            return None
        for row in self._rows:
            if self._photo_key(row.photo) == self._selected_key:
                return row
        return None

    def _selected_rows(self) -> list[CleanupReviewRow]:
        selected_lookup = set(self._selected_keys)
        rows = []
        for row in self._rows:
            if self._photo_key(row.photo) in selected_lookup:
                rows.append(row)
        return rows

    def _range_keys_between(self, start_key: str, end_key: str) -> list[str]:
        keys = [self._photo_key(row.photo) for row in self._visible_rows]
        if start_key not in keys or end_key not in keys:
            return [end_key]
        start_index = keys.index(start_key)
        end_index = keys.index(end_key)
        if start_index <= end_index:
            return keys[start_index:end_index + 1]
        return keys[end_index:start_index + 1]

    def _refresh_card_selection(self) -> None:
        for key, card in self._cards_by_key.items():
            card.set_selected(key in self._selected_keys)

    def _refresh_selection_label(self) -> None:
        self.selection_count_label.setText(f"Selected: {len(self._selected_keys)}")

    def _show_details(self, row: CleanupReviewRow, force: bool = False) -> None:
        row_key = self._photo_key(row.photo)
        if self._details_key == row_key and not force:
            return

        self._details_key = row_key
        photo = row.photo

        thumbnail = getattr(photo, "thumbnail", None)
        if isinstance(thumbnail, QPixmap) and not thumbnail.isNull():
            preview = thumbnail.scaled(
                320,
                220,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setPixmap(preview)
            self.preview_label.setText("")
        else:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("No preview")

        self.filename_value.setText(photo.display_name())
        self.automatic_category_value.setText(_display_category(row.automatic_category))
        self.confidence_value.setText(f"{max(0, min(100, int(round(row.confidence * 100))))}%")
        self.recommended_action_value.setText(_display_action(row.recommended_action))
        self.user_category_value.setText(_display_category(row.user_corrected_category) if row.user_corrected_category else "-")
        self.effective_category_value.setText(_display_category(row.effective_category))
        self.decision_value.setText(row.user_decision)
        self.metadata_summary_value.setText(self._metadata_summary(photo))

        self.reasons_list.clear()
        for reason in self._explainable_reasons(row):
            self.reasons_list.addItem(f"[x] {reason}")

        alternatives = self._possible_alternatives(row)
        self.alternatives_list.clear()
        for label, pct in alternatives:
            self.alternatives_list.addItem(f"{label} ({pct}%)")
        self._refresh_alternatives_visibility(bool(alternatives))

    def _clear_details(self) -> None:
        self._details_key = None
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("No preview")
        self.filename_value.setText("-")
        self.automatic_category_value.setText("-")
        self.confidence_value.setText("-")
        self.recommended_action_value.setText("-")
        self.user_category_value.setText("-")
        self.effective_category_value.setText("-")
        self.decision_value.setText("-")
        self.metadata_summary_value.setText("-")
        self.reasons_list.clear()
        self.alternatives_list.clear()
        self._refresh_alternatives_visibility(False)

    def _refresh_alternatives_visibility(self, visible: bool) -> None:
        self.alternatives_title.setVisible(visible)
        self.alternatives_list.setVisible(visible)

    def _metadata_summary(self, photo) -> str:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        width = metadata.get("width")
        height = metadata.get("height")
        date_taken = metadata.get("date_taken")
        camera_make = metadata.get("camera_make") or ""
        camera_model = metadata.get("camera_model") or ""

        parts = []
        if isinstance(width, int) and isinstance(height, int):
            parts.append(f"{width}x{height}")
        if date_taken:
            parts.append(f"Date: {date_taken}")

        camera_text = " ".join(str(x).strip() for x in (camera_make, camera_model) if str(x).strip())
        if camera_text:
            parts.append(f"Camera: {camera_text}")

        if not parts:
            return "No metadata"
        return " | ".join(parts)

    def _explainable_reasons(self, row: CleanupReviewRow) -> list[str]:
        metadata = dict(getattr(row.photo, "metadata", {}) or {})
        filename = row.photo.display_name().lower()
        width = metadata.get("width")
        height = metadata.get("height")
        camera_make = str(metadata.get("camera_make", "") or "").strip()
        camera_model = str(metadata.get("camera_model", "") or "").strip()

        cleaned: list[str] = []
        for reason in row.reasons:
            text = str(reason).strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered.startswith("classified as") and "because" in lowered:
                text = text.split("because", 1)[1].strip().rstrip(".")
            text = text[:1].upper() + text[1:] if text else text
            if text and text not in cleaned:
                cleaned.append(text)

        if not camera_make and not camera_model:
            cleaned.append("No camera metadata")

        for keyword in ("buongiorno", "auguri", "sticker", "meme", "promo", "offerta", "screenshot"):
            if keyword in filename:
                cleaned.append(f"Filename contains '{keyword}'")
                break

        if isinstance(width, int) and isinstance(height, int):
            if abs(width - height) <= 40 and max(width, height) <= 1200:
                cleaned.append("Square low-resolution image")
            if max(width, height) <= 900:
                cleaned.append("Compact dimensions favor non-memory media")

        if any(token in filename for token in ("whatsapp", "wa", "forwarded", "download")):
            cleaned.append("Looks like downloaded/shared graphic")

        seen = set()
        ordered = []
        for item in cleaned:
            key = item.lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(item)
        return ordered

    def _possible_alternatives(self, row: CleanupReviewRow) -> list[tuple[str, int]]:
        if row.confidence >= 0.8:
            return []

        alternative_map = {
            "meme_or_graphic": [("Family Photo", 25), ("Meme", 45), ("Advertisement", 15), ("Screenshot", 15)],
            "advertisement": [("Meme", 30), ("Advertisement", 40), ("Screenshot", 15), ("Family Photo", 15)],
            "screenshot": [("Screenshot", 45), ("Meme", 25), ("Advertisement", 15), ("Family Photo", 15)],
            "document_or_scan": [("Document", 45), ("Screenshot", 20), ("Family Photo", 20), ("Unknown", 15)],
            "family_photo_candidate": [("Family Photo", 45), ("Meme", 20), ("Screenshot", 20), ("Unknown", 15)],
            "unknown": [("Family Photo", 25), ("Meme", 25), ("Advertisement", 25), ("Screenshot", 25)],
            "duplicate_candidate": [("Duplicate", 45), ("Family Photo", 20), ("Unknown", 20), ("Document", 15)],
            "low_quality_photo": [("Low quality", 45), ("Meme", 20), ("Unknown", 20), ("Family Photo", 15)],
            "video": [("Video", 55), ("Unknown", 20), ("Advertisement", 15), ("Meme", 10)],
        }
        return list(alternative_map.get(row.automatic_category, alternative_map["unknown"]))

    def _set_decision_for_selected(self, decision: str) -> None:
        normalized = str(decision or "pending").strip().lower()
        changed = False
        for row in self._selected_rows():
            if row.user_decision == normalized:
                continue
            row.user_decision = normalized
            metadata = dict(getattr(row.photo, "metadata", {}) or {})
            metadata["cleanup_user_decision"] = normalized
            row.photo.metadata = metadata
            row.photo.sync_intelligence_from_metadata()
            changed = True

        if not changed:
            return
        selected = self._selected_row()
        if selected is not None:
            self._show_details(selected, force=True)

    def _apply_category_to_selected(self, category: str) -> None:
        normalized_category = _normalize_category(category)
        changed = False
        for row in self._selected_rows():
            if row.effective_category == normalized_category and row.user_corrected_category == normalized_category:
                continue

            row.user_corrected_category = normalized_category
            row.effective_category = normalized_category
            metadata = dict(getattr(row.photo, "metadata", {}) or {})
            metadata["cleanup_user_corrected_category"] = normalized_category
            metadata["cleanup_effective_category"] = normalized_category
            metadata["relevance_category"] = normalized_category
            metadata["is_album_relevant_candidate"] = normalized_category == "family_photo_candidate"
            row.photo.metadata = metadata
            row.photo.relevance_category = normalized_category
            row.photo.is_album_relevant_candidate = normalized_category == "family_photo_candidate"
            row.photo.sync_intelligence_from_metadata()
            changed = True

        if not changed:
            return

        self._refresh_group_options()
        self._trigger_refresh(force=True)
        selected = self._selected_row()
        if selected is not None:
            self._show_details(selected, force=True)

    def _photo_key(self, photo) -> str:
        return str(getattr(photo, "path", ""))

    def _calculate_grid_columns(self) -> int:
        width = max(176, self.grid_scroll.viewport().width())
        return max(1, width // 172)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_columns = self._calculate_grid_columns()
        if new_columns == self._grid_columns:
            return
        self._grid_columns = new_columns
        for index, key in enumerate(self._rendered_keys):
            card = self._cards_by_key.get(key)
            if card is None:
                continue
            self.grid_layout.removeWidget(card)
            row = index // self._grid_columns
            col = index % self._grid_columns
            self.grid_layout.addWidget(card, row, col)


def _display_category(category: str) -> str:
    return CATEGORY_LABELS.get(category, category or "Unknown")


def _display_action(action: str) -> str:
    return RECOMMENDED_ACTION_LABELS.get(action, action.replace("_", " ").title() if action else "Unknown")


def _shorten_badge(text: str, max_len: int = 11) -> str:
    clean = str(text or "").strip()
    if len(clean) <= max_len:
        return clean
    return f"{clean[:max_len - 2]}.."


def _normalize_category(category_value: str, allow_empty: bool = False) -> str:
    value = str(category_value or "").strip().lower()
    if value in KNOWN_CATEGORIES:
        return value
    if allow_empty and not value:
        return ""
    return "unknown"


def _normalize_action(action_value: str) -> str:
    value = str(action_value or "").strip().lower()
    if value in {"move_to_cleanup_review", "move_to_cleanup_folder"}:
        return "move_to_cleanup_folder"
    if value in {"keep", "review", "unknown"}:
        return value
    return "review"

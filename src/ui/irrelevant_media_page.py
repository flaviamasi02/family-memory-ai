from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.category_registry import get_category_registry
from core.image_display_loader import load_display_thumbnail
from core.media_classifier import MediaCategory, MediaClassifier
from core.safe_file_move_service import CLEANUP_REVIEW_FOLDER_NAME, move_files_to_cleanup_review
from core.user_metadata_service import UserMetadataService
from learning.category_learning_engine import get_category_learning_engine
from learning.preference_learning_engine import get_preference_learning_engine
from ui.category_management_dialog import CategoryManagementDialog
from ui.components.workspace_header import WorkspaceHeader
from ui.components.workspace_info_content import WORKSPACE_INFO_CONTENT
from ui.components.workspace_info_panel import WorkspaceInfoPanel
from ui.image_preview_dialog import ImagePreviewDialog
from ui.shared_thumbnail_grid import SharedGridItem, SharedThumbnailGrid
from ui.help.workspace_help_content import CLEANUP_REVIEW_WORKSPACE
from workers.face_detection_worker import FaceDetectionWorker

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


class IrrelevantMediaPage(QWidget):
    moved_photos = Signal(object)
    categories_changed = Signal()
    faces_analyzed = Signal(object)
    help_requested = Signal(str)

    WORKSPACE_ID = CLEANUP_REVIEW_WORKSPACE

    CATEGORY_FILTER_ALL = "All categories"
    CONFIDENCE_FILTER_ALL = "All"
    ACTION_FILTER_ALL = "All"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[CleanupReviewRow] = []
        self._visible_rows: list[CleanupReviewRow] = []
        self._imported_root: Optional[Path] = None
        self._imported_total_count = 0
        self._details_key: Optional[str] = None
        self._preview_dialog: Optional[ImagePreviewDialog] = None
        self._thumbnail_cache: dict[str, tuple[int, QPixmap]] = {}
        self._user_metadata_service = UserMetadataService()
        self._category_registry = get_category_registry()
        self._category_learning_engine = get_category_learning_engine()
        self._preference_learning_engine = get_preference_learning_engine()
        self._media_classifier = MediaClassifier()
        self._face_detection_thread: Optional[QThread] = None
        self._face_detection_worker: Optional[FaceDetectionWorker] = None

        self.header = WorkspaceHeader("Cleanup Review")
        self.header.help_clicked.connect(self._on_help_clicked)
        info_content = WORKSPACE_INFO_CONTENT[self.WORKSPACE_ID]
        self.info_panel = WorkspaceInfoPanel(
            workspace_id=self.WORKSPACE_ID,
            title=info_content.title,
            purpose=info_content.purpose,
            purpose_details=info_content.purpose_details,
            typical_actions=info_content.typical_actions,
            tip=info_content.tip,
            collapsed_label=info_content.collapsed_label,
        )

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
        self.search_input.textChanged.connect(self._trigger_refresh)

        self.selection_count_label = QLabel("Selected: 0")
        self.user_saved_label = QLabel("")
        self.user_saved_label.setStyleSheet("font-size: 12px; color: #1f6feb;")
        self.user_saved_label.setVisible(False)
        self.select_all_button = QPushButton("Select All Visible")
        self.select_all_button.clicked.connect(self.select_all_visible)
        self.clear_selection_button = QPushButton("Clear Selection")
        self.clear_selection_button.clicked.connect(self.clear_selection)
        self.manage_categories_button = QPushButton("Manage Categories")
        self.manage_categories_button.clicked.connect(self._on_manage_categories)
        self.reclassify_unknowns_button = QPushButton("Reclassify Unknowns")
        self.reclassify_unknowns_button.clicked.connect(self.reclassify_unknowns_from_learning)
        self.analyze_faces_button = QPushButton("Analyze Faces for Visible")
        self.analyze_faces_button.clicked.connect(self.analyze_faces_for_visible)

        self.face_detection_status_label = QLabel("Face analysis idle")
        self.face_detection_status_label.setStyleSheet("font-size: 12px; color: #666;")

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
        toolbar.addWidget(self.user_saved_label)
        toolbar.addWidget(self.manage_categories_button)
        toolbar.addWidget(self.reclassify_unknowns_button)
        toolbar.addWidget(self.analyze_faces_button)
        toolbar.addWidget(self.face_detection_status_label)
        toolbar.addWidget(self.select_all_button)
        toolbar.addWidget(self.clear_selection_button)

        self.results_label = QLabel("Showing 0 photos")

        self.thumbnail_grid = SharedThumbnailGrid(self)
        self.thumbnail_grid.selection_changed.connect(self._on_grid_selection_changed)
        self.thumbnail_grid.card_double_clicked.connect(self._on_card_double_clicked)
        self._cards_by_key = self.thumbnail_grid._cards_by_key

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
        self.category_selector = QComboBox()
        self.apply_category_button = QPushButton("Apply Category to Selected")
        self.apply_category_button.clicked.connect(lambda: self._apply_category_to_selected(str(self.category_selector.currentData() or "unknown")))

        actions_row_one = QHBoxLayout()
        actions_row_one.addWidget(self.keep_button)
        actions_row_one.addWidget(self.move_button)

        actions_row_two = QHBoxLayout()
        actions_row_two.addWidget(QLabel("Category:"))
        actions_row_two.addWidget(self.category_selector, 1)
        actions_row_two.addWidget(self.apply_category_button)

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
        details_layout.addStretch(0)

        details_panel = QWidget()
        details_panel.setLayout(details_layout)
        details_panel.setMinimumWidth(440)

        grid_panel = QWidget()
        grid_layout = QVBoxLayout(grid_panel)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self.results_label)
        grid_layout.addWidget(self.thumbnail_grid, 1)

        splitter = QSplitter()
        splitter.addWidget(grid_panel)
        splitter.addWidget(details_panel)
        splitter.setStretchFactor(0, 8)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([1000, 440])

        root = QVBoxLayout(self)
        root.addWidget(self.header)
        root.addWidget(self.info_panel)
        root.addWidget(self.stats_label)
        root.addLayout(toolbar)
        root.addWidget(splitter, 1)

        self._reset_filter_options()
        self._reload_category_selector_options()
        self._clear_details()
        self._refresh_alternatives_visibility(False)

    def _on_help_clicked(self) -> None:
        self.help_requested.emit(self.WORKSPACE_ID)

    def refresh_category_options(self) -> None:
        self._reset_filter_options()
        self._reload_category_selector_options()
        self._refresh_group_options()
        self._trigger_refresh(force=True)

    def set_photos(self, photos, imported_root: Optional[str | Path], total_imported_count: Optional[int] = None) -> None:
        self._imported_root = Path(imported_root) if imported_root else None
        self._imported_total_count = int(total_imported_count) if isinstance(total_imported_count, int) else len(photos or [])

        self._rows = [self._build_row(photo) for photo in list(photos or [])]
        self._details_key = None
        self._reset_filter_options()
        self._reload_category_selector_options()
        self._refresh_group_options()
        self._trigger_refresh(force=True)

    def update_thumbnail(self, photo, pixmap) -> None:
        key = self._photo_key(photo)
        for row in self._rows:
            if self._photo_key(row.photo) != key:
                continue
            if isinstance(pixmap, QPixmap) and not pixmap.isNull():
                row.photo.thumbnail = pixmap
            self._thumbnail_cache.pop(key, None)
            self.thumbnail_grid.update_item(self._to_grid_item(row))
            if self.thumbnail_grid.selected_key() == key:
                self._show_details(row, force=True)
            break

    def visible_filenames(self) -> list[str]:
        return [row.photo.display_name() for row in self._visible_rows]

    def selected_count(self) -> int:
        return self.thumbnail_grid.selected_count()

    def selected_photos(self) -> list:
        return [row.photo for row in self._selected_rows()]

    def grid_column_count(self) -> int:
        return self.thumbnail_grid.grid_column_count()

    def rendered_card_count(self) -> int:
        return self.thumbnail_grid.rendered_card_count()

    def category_selector_values(self) -> list[str]:
        return [
            str(self.category_selector.itemData(index) or "")
            for index in range(self.category_selector.count())
        ]

    def category_filter_labels(self) -> list[str]:
        return [
            self.category_filter_combo.itemText(index)
            for index in range(self.category_filter_combo.count())
        ]

    def select_photo_by_filename(self, filename: str) -> bool:
        target = (filename or "").strip()
        if not target:
            return False

        for row in self._visible_rows:
            if row.photo.display_name() == target:
                key = self._photo_key(row.photo)
                self.thumbnail_grid.set_single_selection(key)
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
                "category": card.badge_one.text(),
                "confidence": card.badge_two.text(),
                "action": card.badge_three.text(),
            }
        return None

    def possible_alternatives_visible(self) -> bool:
        return (not self.alternatives_title.isHidden()) and (not self.alternatives_list.isHidden())

    def select_all_visible(self) -> None:
        self.thumbnail_grid.select_all_visible()

    def analyze_faces_for_visible(self) -> None:
        if self._face_detection_worker is not None or self._face_detection_thread is not None:
            return

        selected_rows = self._selected_rows()
        target_rows = selected_rows if selected_rows else list(self._visible_rows)
        if not target_rows:
            self.face_detection_status_label.setText("No visible photos to analyze")
            return

        target_photos = [row.photo for row in target_rows]
        self.face_detection_status_label.setText(f"Analyzing faces for {len(target_photos)} photo(s)...")
        self.analyze_faces_button.setEnabled(False)

        thread = QThread(self)
        worker = FaceDetectionWorker(target_photos, enabled=True)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_face_detection_progress)
        worker.finished.connect(self._on_face_detection_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_face_detection_thread_finished)

        self._face_detection_thread = thread
        self._face_detection_worker = worker
        thread.start()

    def clear_selection(self) -> None:
        self.thumbnail_grid.clear_selection()
        self._clear_details()

    def reclassify_unknowns_from_learning(self) -> int:
        changed_count = 0

        for index, row in enumerate(list(self._rows)):
            user_corrected = str(row.user_corrected_category or "").strip().lower()

            if user_corrected or row.effective_category != MediaCategory.Unknown.value:
                continue

            previous_category = row.effective_category
            self._media_classifier.classify_photo(row.photo)
            updated_row = self._build_row(row.photo)

            if updated_row.effective_category == previous_category:
                continue

            self._rows[index] = updated_row
            changed_count += 1

        self._show_user_saved_indicator(f"Reclassified {changed_count} unknown photos")

        if changed_count:
            selected_key = self.thumbnail_grid.selected_key()
            self._refresh_group_options()
            self._trigger_refresh(force=True)
            if selected_key:
                row = self._row_for_key(selected_key)
                if row is not None:
                    self._show_details(row, force=True)

        return changed_count

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
            self._refresh_group_options()
            self._trigger_refresh(force=True)
            self.moved_photos.emit(moved_photos)

    def _on_grid_selection_changed(self, selected_keys: set[str], selected_key: Optional[str]) -> None:
        _ = selected_keys
        self.selection_count_label.setText(f"Selected: {self.thumbnail_grid.selected_count()}")
        if not selected_key:
            self._clear_details()
            return
        row = self._row_for_key(selected_key)
        if row is None:
            self._clear_details()
            return
        self._show_details(row)

    def _on_card_double_clicked(self, key: str) -> None:
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
    def _build_row(self, photo) -> CleanupReviewRow:
        metadata = dict(getattr(photo, "metadata", {}) or {})

        automatic_category = str(
            metadata.get("cleanup_automatic_category", "")
            or metadata.get("automatic_media_category", "")
            or metadata.get("relevance_category", "")
            or getattr(photo, "automatic_media_category", "")
            or metadata.get("media_category", "")
            or getattr(photo, "media_category", "")
            or MediaCategory.Unknown.value
        ).strip().lower()

        user_corrected_category = str(
            metadata.get("cleanup_user_corrected_category", "")
            or metadata.get("user_corrected_media_category", "")
            or getattr(photo, "user_corrected_media_category", "")
            or ""
        ).strip().lower()

        effective_category = str(
            metadata.get("cleanup_effective_category", "")
            or metadata.get("effective_media_category", "")
            or metadata.get("relevance_category", "")
            or getattr(photo, "effective_media_category", "")
            or user_corrected_category
            or automatic_category
            or MediaCategory.Unknown.value
        ).strip().lower()

        confidence = float(
            metadata.get("cleanup_confidence", metadata.get("classification_confidence", getattr(photo, "classification_confidence", 0.0) or 0.0))
            or 0.0
        )

        cleanup_reasons = metadata.get("cleanup_reasons", "")
        if isinstance(cleanup_reasons, (list, tuple)):
            reason = "; ".join(str(item) for item in cleanup_reasons if str(item).strip())
        else:
            reason = str(cleanup_reasons or "").strip()
        if not reason:
            reason = str(
                metadata.get("cleanup_reason", "")
                or metadata.get("classification_reason", "")
                or getattr(photo, "classification_reason", "")
                or metadata.get("relevance_reason", "")
                or ""
            ).strip()

        if not reason:
            reason = "No classification reason available."

        action = str(metadata.get("cleanup_recommended_action", "") or "").strip() or self._recommended_action_for_category(effective_category)
        user_decision = str(
            metadata.get("user_decision", "")
            or getattr(photo, "user_decision", "")
            or "pending"
        ).strip().lower() or "pending"

        return CleanupReviewRow(
            photo=photo,
            automatic_category=automatic_category,
            user_corrected_category=user_corrected_category,
            effective_category=effective_category,
            confidence=confidence,
            recommended_action=action,
            reasons=self._split_reasons(reason),
            user_decision=user_decision,
        )

    def _recommended_action_for_category(self, category_id: str) -> str:
        category_id = str(category_id or "").strip().lower()
        registry = self._category_registry

        if registry.is_cleanup_category(category_id):
            return "move_to_cleanup_folder"

        if category_id in {
            MediaCategory.Unknown.value,
            MediaCategory.LowQuality.value,
            MediaCategory.DuplicateCandidate.value,
        }:
            return "review"

        return "keep"

    def _reset_filter_options(self) -> None:
        current = self.category_filter_combo.currentData()
        self.category_filter_combo.blockSignals(True)
        self.category_filter_combo.clear()
        self.category_filter_combo.addItem(self.CATEGORY_FILTER_ALL, self.CATEGORY_FILTER_ALL)
        for category_id in self._category_registry.ordered_ids():
            self.category_filter_combo.addItem(self._category_registry.label_for(category_id), category_id)
        if current is not None:
            index = self.category_filter_combo.findData(current)
            if index >= 0:
                self.category_filter_combo.setCurrentIndex(index)
        self.category_filter_combo.blockSignals(False)

    def _reload_category_selector_options(self) -> None:
        current = self.category_selector.currentData()
        self.category_selector.blockSignals(True)
        self.category_selector.clear()
        for category_id in self._category_registry.ordered_ids():
            self.category_selector.addItem(self._category_registry.label_for(category_id), category_id)
        if current is not None:
            index = self.category_selector.findData(current)
            if index >= 0:
                self.category_selector.setCurrentIndex(index)
        self.category_selector.blockSignals(False)

    def _refresh_group_options(self) -> None:
        current = self.group_combo.currentData()
        counts: dict[str, int] = {}
        for row in self._rows:
            counts[row.effective_category] = counts.get(row.effective_category, 0) + 1

        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItem("No grouping", "")
        for category_id in sorted(counts.keys(), key=lambda item: self._category_registry.label_for(item)):
            self.group_combo.addItem(
                f"{self._category_registry.label_for(category_id)} ({counts[category_id]})",
                category_id,
            )

        if current is not None:
            index = self.group_combo.findData(current)
            if index >= 0:
                self.group_combo.setCurrentIndex(index)
        self.group_combo.blockSignals(False)

    def _on_group_changed(self) -> None:
        selected_group = str(self.group_combo.currentData() or "").strip().lower()
        if selected_group:
            index = self.category_filter_combo.findData(selected_group)
            if index >= 0:
                self.category_filter_combo.setCurrentIndex(index)
        else:
            self.category_filter_combo.setCurrentIndex(0)
        self._trigger_refresh(force=True)

    def _trigger_refresh(self, force: bool = False) -> None:
        _ = force
        previous_scroll = self.thumbnail_grid.scroll_value()
        selected_key_before = self.thumbnail_grid.selected_key()
        self._visible_rows = self._filtered_rows()
        self.results_label.setText(f"Showing {len(self._visible_rows)} of {len(self._rows)} cleanup review items")
        self._update_stats()

        items = [self._to_grid_item(row) for row in self._visible_rows]
        self.thumbnail_grid.set_items(items)

        selected_key = self.thumbnail_grid.selected_key() or selected_key_before
        if selected_key:
            row = self._row_for_key(selected_key)
            if row is not None and selected_key in {self._photo_key(item.photo) for item in self._visible_rows}:
                self.thumbnail_grid.set_single_selection(selected_key)
                self._show_details(row, force=True)
                self.thumbnail_grid.restore_scroll_value(previous_scroll)
                return

        if self._visible_rows:
            first_key = self._photo_key(self._visible_rows[0].photo)
            self.thumbnail_grid.set_single_selection(first_key)
            self._show_details(self._visible_rows[0], force=True)
        else:
            self._clear_details()
        self.thumbnail_grid.restore_scroll_value(previous_scroll)
        QTimer.singleShot(
            50,
            lambda value=previous_scroll: self.thumbnail_grid.restore_scroll_value(value),
        )

    def _filtered_rows(self) -> list[CleanupReviewRow]:
        rows = list(self._rows)

        category = self.category_filter_combo.currentData()
        if category and category != self.CATEGORY_FILTER_ALL:
            rows = [row for row in rows if row.effective_category == category]

        confidence_filter = self.confidence_filter_combo.currentText()
        if confidence_filter.startswith("High"):
            rows = [row for row in rows if row.confidence >= 0.80]
        elif confidence_filter.startswith("Medium"):
            rows = [row for row in rows if 0.50 <= row.confidence < 0.80]
        elif confidence_filter.startswith("Low"):
            rows = [row for row in rows if row.confidence < 0.50]

        action_text = self.action_filter_combo.currentText()
        if action_text != self.ACTION_FILTER_ALL:
            wanted = self._action_value_from_label(action_text)
            rows = [row for row in rows if row.recommended_action == wanted]

        search_text = self.search_input.text().strip().lower()
        if search_text:
            rows = [row for row in rows if search_text in row.photo.display_name().lower()]

        rows.sort(
            key=lambda row: (
                row.effective_category,
                -float(row.confidence),
                row.photo.display_name().lower(),
            )
        )
        return rows

    def _to_grid_item(self, row: CleanupReviewRow) -> SharedGridItem:
        category_label = self._category_registry.label_for(row.effective_category)
        confidence_label = f"{max(0, min(100, int(round(row.confidence * 100))))}%"
        action_label = RECOMMENDED_ACTION_LABELS.get(row.recommended_action, row.recommended_action.replace("_", " ").title())
        thumbnail = self._get_cached_card_thumbnail(row)
        return SharedGridItem(
            key=self._photo_key(row.photo),
            filename=row.photo.display_name(),
            thumbnail=thumbnail,
            badge_one=category_label,
            badge_two=confidence_label,
            badge_three=action_label,
        )

    def _show_details(self, row: CleanupReviewRow, force: bool = False) -> None:
        key = self._photo_key(row.photo)
        if not force and self._details_key == key:
            return
        self._details_key = key

        photo = row.photo
        self.filename_value.setText(photo.display_name())
        self.automatic_category_value.setText(self._category_registry.label_for(row.automatic_category))
        self.confidence_value.setText(f"{max(0, min(100, int(round(row.confidence * 100))))}%")
        self.recommended_action_value.setText(
            RECOMMENDED_ACTION_LABELS.get(row.recommended_action, row.recommended_action.replace("_", " ").title())
        )
        self.user_category_value.setText(
            self._category_registry.label_for(row.user_corrected_category)
            if row.user_corrected_category
            else "-"
        )
        self.effective_category_value.setText(self._category_registry.label_for(row.effective_category))
        self.decision_value.setText(row.user_decision.replace("_", " ").title())
        self.metadata_summary_value.setText(self._metadata_summary(photo))

        self.reasons_list.clear()
        for reason in row.reasons:
            self.reasons_list.addItem(reason)

        self.alternatives_list.clear()
        for label, score in self._possible_alternatives(row):
            self.alternatives_list.addItem(f"{label} ({score}%)")
        self._refresh_alternatives_visibility(row.confidence < 0.80)

        pixmap = self._thumbnail_for_photo(photo, (320, 220), allow_original_decode=True)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self.preview_label.setPixmap(pixmap)
            self.preview_label.setText("")
        else:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("Preview unavailable")

        category_index = self.category_selector.findData(row.effective_category)
        if category_index >= 0:
            self.category_selector.setCurrentIndex(category_index)

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
        self.alternatives_title.setVisible(bool(visible))
        self.alternatives_list.setVisible(bool(visible))

    def _possible_alternatives(self, row: CleanupReviewRow) -> list[tuple[str, int]]:
        if row.confidence >= 0.80:
            return []
        current = row.effective_category
        base = [
            (self._category_registry.label_for(current), int(max(30, min(70, row.confidence * 100)))),
            (self._category_registry.label_for(MediaCategory.FamilyPhoto.value), 25),
            (self._category_registry.label_for(MediaCategory.Meme.value), 20),
            (self._category_registry.label_for(MediaCategory.Screenshot.value), 15),
            (self._category_registry.label_for(MediaCategory.Advertisement.value), 10),
        ]

        deduped: list[tuple[str, int]] = []
        seen = set()
        for label, score in base:
            if label in seen:
                continue
            seen.add(label)
            deduped.append((label, score))
        return deduped[:4]

    def _metadata_summary(self, photo) -> str:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        width = metadata.get("width")
        height = metadata.get("height")
        date_source = metadata.get("date_source") or metadata.get("source_of_date") or "Unknown"
        visual = metadata.get("visual_evidence") or metadata.get("visual_signals_summary") or ""
        has_faces = bool(metadata.get("has_faces", False))
        face_count = int(metadata.get("face_count", metadata.get("faces_count", 0)) or 0)
        face_confidence = float(metadata.get("face_detection_confidence", 0.0) or 0.0)

        parts = [
            f"Resolution: {width or 'Unknown'} x {height or 'Unknown'}",
            f"Date source: {date_source}",
            f"Faces: {'yes' if has_faces else 'no'} ({face_count}, {max(0, min(100, int(round(face_confidence * 100))))}%)",
        ]
        if visual:
            parts.append(f"Visual: {visual}")
        return " | ".join(parts)

    def _split_reasons(self, reason: str) -> list[str]:
        text = str(reason or "").strip()
        if not text:
            return ["No classification reason available."]

        separators = ["; ", " because ", ". "]
        fragments = [text]
        for separator in separators:
            if separator in text:
                fragments = [part.strip(" .") for part in text.split(separator) if part.strip(" .")]
                break

        cleaned = []
        for fragment in fragments:
            if fragment.lower().startswith("classified as"):
                cleaned.append(fragment)
            else:
                cleaned.append(f"- {fragment}")
        return cleaned or [text]

    def _action_value_from_label(self, label: str) -> str:
        for value, display in RECOMMENDED_ACTION_LABELS.items():
            if display == label:
                return value
        return str(label or "").strip().lower().replace(" ", "_")

    def _set_decision_for_selected(self, decision: str) -> None:
        selected_rows = self._selected_rows()
        for row in selected_rows:
            previous = row.user_decision
            row.user_decision = decision
            metadata = dict(getattr(row.photo, "metadata", {}) or {})
            metadata["user_decision"] = decision
            row.photo.metadata = metadata
            row.photo.user_decision = decision
            self._preference_learning_engine.record_cleanup_decision(
                row.photo,
                previous_decision=previous,
                new_decision=decision,
                source="user_bulk" if len(selected_rows) > 1 else "user",
            )
            self._save_photo_user_metadata(row.photo)
        if selected_rows:
            self._show_user_saved_indicator("Decision saved")
            self._trigger_refresh(force=True)

    def _apply_category_to_selected(self, category: str) -> None:
        category = str(category or "").strip().lower()
        if not category:
            return

        selected_rows = self._selected_rows()
        if not selected_rows:
            return

        affected_keys = [self._photo_key(row.photo) for row in selected_rows]
        preferred_key = self.thumbnail_grid.selected_key() or (affected_keys[0] if affected_keys else None)
        previous_visible_keys = [self._photo_key(row.photo) for row in self._visible_rows]
        previous_scroll = self.thumbnail_grid.scroll_value()

        for row in selected_rows:
            previous = row.effective_category
            metadata = dict(getattr(row.photo, "metadata", {}) or {})
            automatic = str(
                metadata.get("automatic_media_category", "")
                or row.automatic_category
                or getattr(row.photo, "automatic_media_category", "")
                or previous
            ).strip().lower()

            metadata["automatic_media_category"] = automatic
            metadata["user_corrected_media_category"] = category
            metadata["effective_media_category"] = category
            metadata["media_category"] = category
            metadata["cleanup_automatic_category"] = automatic
            metadata["cleanup_user_corrected_category"] = category
            metadata["cleanup_effective_category"] = category
            metadata["relevance_category"] = category
            row.photo.metadata = metadata

            row.photo.automatic_media_category = automatic
            row.photo.user_corrected_media_category = category
            row.photo.effective_media_category = category
            row.photo.media_category = category
            row.photo.sync_intelligence_from_metadata()

            self._category_learning_engine.record_category_correction(
                row.photo,
                previous_category=previous,
                corrected_category=category,
                source="user_bulk" if len(selected_rows) > 1 else "user",
            )
            self._category_learning_engine.start_pending_visual_analysis_worker(limit=25)
            self._preference_learning_engine.record_category_correction(
                row.photo,
                previous_category=previous,
                corrected_category=category,
                source="user_bulk" if len(selected_rows) > 1 else "user",
            )
            self._save_photo_user_metadata(row.photo)

        self._category_learning_engine.start_pending_visual_analysis_worker(limit=25)
        self._rows = [self._build_row(row.photo) for row in self._rows]
        self._show_user_saved_indicator("User category saved")
        self._refresh_group_options()
        self._refresh_after_category_change(
            affected_keys=affected_keys,
            preferred_key=preferred_key,
            previous_visible_keys=previous_visible_keys,
            previous_scroll=previous_scroll,
        )

    def _refresh_after_category_change(
        self,
        affected_keys: list[str],
        preferred_key: Optional[str],
        previous_visible_keys: list[str],
        previous_scroll: int,
    ) -> None:
        new_visible_rows = self._filtered_rows()
        new_visible_keys = [self._photo_key(row.photo) for row in new_visible_rows]

        self.results_label.setText(f"Showing {len(new_visible_rows)} of {len(self._rows)} cleanup review items")
        self._update_stats()

        if new_visible_keys == previous_visible_keys:
            self._visible_rows = new_visible_rows
            for key in affected_keys:
                row = self._row_for_key(key)
                if row is not None:
                    self.thumbnail_grid.update_item(self._to_grid_item(row))
            selected_key = self.thumbnail_grid.selected_key()
            if selected_key:
                selected_row = self._row_for_key(selected_key)
                if selected_row is not None:
                    self._show_details(selected_row, force=True)
            self.thumbnail_grid.restore_scroll_value(previous_scroll)
            return

        selected_key = self._choose_selection_after_filter_change(
            preferred_key=preferred_key,
            previous_visible_keys=previous_visible_keys,
            new_visible_keys=new_visible_keys,
        )
        self._visible_rows = new_visible_rows
        self.thumbnail_grid.set_items([self._to_grid_item(row) for row in self._visible_rows])

        if selected_key:
            self.thumbnail_grid.set_single_selection(selected_key)
            selected_row = self._row_for_key(selected_key)
            if selected_row is not None:
                self._show_details(selected_row, force=True)
        else:
            self._clear_details()
        self.thumbnail_grid.restore_scroll_value(previous_scroll)

    def _choose_selection_after_filter_change(
        self,
        preferred_key: Optional[str],
        previous_visible_keys: list[str],
        new_visible_keys: list[str],
    ) -> Optional[str]:
        if not new_visible_keys:
            return None
        if preferred_key in new_visible_keys:
            return preferred_key
        previous_index = 0
        if preferred_key in previous_visible_keys:
            previous_index = previous_visible_keys.index(preferred_key)
        return new_visible_keys[min(previous_index, len(new_visible_keys) - 1)]

    def _save_photo_user_metadata(self, photo) -> None:
        try:
            self._user_metadata_service.save_photo_metadata(photo)
        except Exception:
            pass

    def _on_face_detection_progress(self, index: int, total: int, filename: str) -> None:
        self.face_detection_status_label.setText(f"Analyzing faces {index}/{total}: {filename}")

    def _on_face_detection_finished(self, summary) -> None:
        analyzed_photos = list(getattr(summary, "photos", []) or [])
        analyzed_count = int(getattr(summary, "analyzed_count", len(analyzed_photos)) or 0)
        faces_detected_count = int(getattr(summary, "faces_detected_count", 0) or 0)
        reclassified_count = int(getattr(summary, "reclassified_count", 0) or 0)

        if analyzed_photos:
            self._rows = [self._build_row(row.photo) for row in self._rows]
            self._refresh_group_options()
            self._trigger_refresh(force=True)

        self.face_detection_status_label.setText(
            f"Face analysis complete: {analyzed_count} analyzed, {faces_detected_count} with faces, {reclassified_count} reclassified"
        )
        self.faces_analyzed.emit(analyzed_photos)
        self.categories_changed.emit()

    def _on_face_detection_thread_finished(self) -> None:
        self._face_detection_thread = None
        self._face_detection_worker = None
        self.analyze_faces_button.setEnabled(True)

    def _selected_rows(self) -> list[CleanupReviewRow]:
        selected_keys = self.thumbnail_grid.selected_keys()
        return [row for row in self._rows if self._photo_key(row.photo) in selected_keys]

    def _row_for_key(self, key: str) -> Optional[CleanupReviewRow]:
        for row in self._rows:
            if self._photo_key(row.photo) == key:
                return row
        return None

    def _photo_key(self, photo) -> str:
        return str(getattr(photo, "path", ""))

    def _thumbnail_for_photo(self, photo, target_size, *, allow_original_decode: bool = False) -> Optional[QPixmap]:
        thumbnail = getattr(photo, "thumbnail", None)
        if isinstance(thumbnail, QPixmap) and not thumbnail.isNull():
            return thumbnail

        thumbnail_path = str(getattr(photo, "thumbnail_path", "") or "")
        if thumbnail_path and Path(thumbnail_path).exists():
            thumbnail = load_display_thumbnail(thumbnail_path, target_size)
            if isinstance(thumbnail, QPixmap) and not thumbnail.isNull():
                return thumbnail

        # Only decode the original file when the caller explicitly opts in
        # (e.g. the user clicks on a card to open the detail view).
        # During the initial grid population this flag is False so that
        # thousands of original JPEGs are never decoded synchronously on the
        # UI thread, which is the root cause of the "Not Responding" freeze
        # and the repeated Qt JPEG warnings.
        if allow_original_decode:
            file_path = str(getattr(photo, "path", "") or "")
            if file_path and Path(file_path).exists():
                thumbnail = load_display_thumbnail(file_path, target_size)
                if isinstance(thumbnail, QPixmap) and not thumbnail.isNull():
                    return thumbnail

        return None

    def _get_cached_card_thumbnail(self, row: CleanupReviewRow) -> Optional[QPixmap]:
        key = self._photo_key(row.photo)
        cached = self._thumbnail_cache.get(key)
        if cached is not None:
            return cached[1]

        pixmap = self._thumbnail_for_photo(row.photo, (140, 140))
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self._thumbnail_cache[key] = (0, pixmap)
            return pixmap
        return None

    def _update_stats(self) -> None:
        imported = self._imported_total_count
        cleanup_candidates = len([
            row for row in self._rows
            if row.recommended_action in {"move_to_cleanup_folder", "move_to_cleanup_review", "review"}
        ])
        family = len([row for row in self._rows if row.effective_category == MediaCategory.FamilyPhoto.value])
        documents = len([
            row for row in self._rows
            if row.effective_category in {
                MediaCategory.Document.value,
                MediaCategory.Receipt.value,
                MediaCategory.Invoice.value,
                "document_or_scan",
            }
        ])
        screenshots = len([row for row in self._rows if row.effective_category == MediaCategory.Screenshot.value])
        advertisements = len([row for row in self._rows if row.effective_category == MediaCategory.Advertisement.value])
        memes = len([
            row for row in self._rows
            if row.effective_category in {MediaCategory.Meme.value, MediaCategory.Graphic.value, "meme_or_graphic"}
        ])
        unknown = len([row for row in self._rows if row.effective_category == MediaCategory.Unknown.value])

        avg_conf = 0
        if self._rows:
            avg_conf = int(round(sum(row.confidence for row in self._rows) / len(self._rows) * 100))

        self.stats_label.setText(
            " | ".join(
                [
                    f"Imported: {imported}",
                    f"Cleanup candidates: {cleanup_candidates}",
                    f"Family photos: {family}",
                    f"Documents: {documents}",
                    f"Screenshots: {screenshots}",
                    f"Advertisements: {advertisements}",
                    f"Memes: {memes}",
                    f"Unknown: {unknown}",
                    f"Average confidence: {avg_conf}%",
                ]
            )
        )

    def _on_manage_categories(self) -> None:
        usage = self._category_usage_counts()
        dialog = CategoryManagementDialog(
            registry=self._category_registry,
            usage_counts=usage,
            reassignment_callback=self._reassign_deleted_category,
            parent=self,
        )
        dialog.exec()
        self.refresh_category_options()
        self.categories_changed.emit()

    def _category_usage_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self._rows:
            counts[row.effective_category] = counts.get(row.effective_category, 0) + 1
        return counts

    def _reassign_deleted_category(self, old_category_id: str, new_category_id: str) -> None:
        old_id = str(old_category_id or "").strip().lower()
        new_id = str(new_category_id or "").strip().lower()
        if not old_id or not new_id or old_id == new_id:
            return

        for row in self._rows:
            metadata = dict(getattr(row.photo, "metadata", {}) or {})
            changed = False
            for field in ("automatic_media_category", "user_corrected_media_category", "effective_media_category", "media_category"):
                if str(metadata.get(field, "") or "").strip().lower() == old_id:
                    metadata[field] = new_id
                    changed = True
            if changed:
                row.photo.metadata = metadata
                row.photo.automatic_media_category = str(metadata.get("automatic_media_category", "") or "")
                row.photo.user_corrected_media_category = str(metadata.get("user_corrected_media_category", "") or "")
                row.photo.effective_media_category = str(metadata.get("effective_media_category", "") or "")
                row.photo.media_category = str(metadata.get("media_category", "") or "")
                row.photo.sync_intelligence_from_metadata()

        self._rows = [self._build_row(row.photo) for row in self._rows]

    def _show_user_saved_indicator(self, text: str) -> None:
        self.user_saved_label.setText(text)
        self.user_saved_label.setVisible(True)
        QTimer.singleShot(2500, lambda: self.user_saved_label.setVisible(False))

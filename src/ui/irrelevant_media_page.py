from __future__ import annotations

import logging
import hashlib
import time
from contextlib import ExitStack, nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings, Qt, QTimer, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QButtonGroup,
    QFormLayout,
    QFileDialog,
    QGroupBox,
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
from core.trash_workflow_service import TrashRecord, TrashWorkflowService
from cache.thumbnail_cache import get_thumbnail_cache_path, preserve_thumbnail_for_relocation
from core.user_metadata_service import UserMetadataService
from learning.category_learning_engine import get_category_learning_engine
from learning.preference_learning_engine import get_preference_learning_engine
from ui.category_management_dialog import CategoryManagementDialog
from ui.components.workspace_header import WorkspaceHeader
from ui.components.workspace_info_content import WORKSPACE_INFO_CONTENT
from ui.components.workspace_info_panel import WorkspaceInfoPanel
from ui.image_preview_dialog import ImagePreviewDialog
from ui.shared_thumbnail_grid import SharedGridItem, SharedThumbnailGrid
from core.selection_diagnostics import (
    add_selection_count,
    add_selection_time,
    begin_selection_measurement,
    finish_selection_measurement,
)
from ui.help.workspace_help_content import CLEANUP_REVIEW_WORKSPACE
from workers.face_detection_worker import FaceDetectionWorker

LOGGER = logging.getLogger(__name__)

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
    active_state_changed = Signal(object)
    history_thumbnails_requested = Signal(object)

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
        self._bulk_category_in_progress = False
        self._view_scroll_positions = {"review": 0, "history": 0}
        self._trash_destination: Optional[Path] = None
        self._trash_destination_error = "Import a library to choose a Trash destination."
        self._trash_settings = QSettings(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope,
            "FamilyMemoryAI", "CleanupReview",
        )
        self.last_bulk_performance: dict[str, int | float] = {}

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
        self.view_combo = QComboBox()
        self.view_combo.addItem("To review", "review")
        self.view_combo.addItem("Trash History", "history")
        self.view_combo.currentIndexChanged.connect(self._on_view_combo_changed)
        self.view_combo.setVisible(False)  # compatibility state; visible switch uses both labeled buttons
        self.view_to_review_button = QPushButton("To review")
        self.view_history_button = QPushButton("Trash History")
        for button in (self.view_to_review_button, self.view_history_button):
            button.setCheckable(True)
            button.setMinimumSize(150, 38)
            button.setStyleSheet(
                "QPushButton { font-weight: 600; padding: 7px 18px; } "
                "QPushButton:checked { background: #1f6feb; color: white; border: 2px solid #174ea6; }"
            )
        self.view_to_review_button.setChecked(True)
        self.view_button_group = QButtonGroup(self)
        self.view_button_group.setExclusive(True)
        self.view_button_group.addButton(self.view_to_review_button)
        self.view_button_group.addButton(self.view_history_button)
        self.view_to_review_button.clicked.connect(lambda: self._select_cleanup_view("review"))
        self.view_history_button.clicked.connect(lambda: self._select_cleanup_view("history"))
        self.view_explanation_label = QLabel("Photos still requiring cleanup decisions.")
        self.view_explanation_label.setWordWrap(True)

        self.view_switch = QGroupBox("View")
        self.view_switch.setObjectName("cleanupViewSwitch")
        view_switch_layout = QVBoxLayout(self.view_switch)
        view_buttons = QHBoxLayout()
        view_buttons.addWidget(self.view_to_review_button)
        view_buttons.addWidget(self.view_history_button)
        view_buttons.addStretch(1)
        view_switch_layout.addLayout(view_buttons)
        view_switch_layout.addWidget(self.view_explanation_label)

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
        self.trash_status_value = QLabel("-")
        self.original_path_value = QLabel("-")
        self.original_path_value.setWordWrap(True)
        self.current_trash_path_value = QLabel("-")
        self.current_trash_path_value.setWordWrap(True)
        self.trash_moved_at_value = QLabel("-")
        self.metadata_summary_value = QLabel("-")
        self.metadata_summary_value.setWordWrap(True)

        details_form = QFormLayout()
        details_form.addRow("Filename:", self.filename_value)
        details_form.addRow("Automatic category:", self.automatic_category_value)
        details_form.addRow("Confidence:", self.confidence_value)
        details_form.addRow("Recommended action:", self.recommended_action_value)
        details_form.addRow("Current user category:", self.user_category_value)
        details_form.addRow("Effective category:", self.effective_category_value)
        details_form.addRow("Status:", self.trash_status_value)
        details_form.addRow("Original path:", self.original_path_value)
        details_form.addRow("Current Trash path:", self.current_trash_path_value)
        details_form.addRow("Moved date:", self.trash_moved_at_value)
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
        self.confirm_trash_button = QPushButton("Confirm selected for Trash")
        self.confirm_trash_button.clicked.connect(self.confirm_selected_for_trash)
        self.move_trash_button = QPushButton("Move confirmed photos to Trash")
        self.move_trash_button.clicked.connect(self.move_confirmed_to_trash)
        self.move_trash_button.setMinimumSize(340, 48)
        self.move_trash_button.setStyleSheet(
            "QPushButton { background: #b42318; color: white; font-size: 14px; "
            "font-weight: 700; border-radius: 5px; padding: 10px 16px; } "
            "QPushButton:disabled { background: #aaa; color: #eee; }"
        )
        self.trash_counts_label = QLabel()
        self.trash_counts_label.setObjectName("trashWorkflowCounts")
        self.trash_counts_label.setWordWrap(True)
        self.trash_destination_label = QLabel("No valid Trash destination")
        self.trash_destination_label.setObjectName("trashDestinationPath")
        self.trash_destination_label.setWordWrap(True)
        self.trash_destination_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.trash_explanation_label = QLabel(
            "Only photos explicitly confirmed for Trash will move. Files are never permanently deleted."
        )
        self.trash_explanation_label.setWordWrap(True)
        self.change_trash_folder_button = QPushButton("Change Trash folder…")
        self.change_trash_folder_button.clicked.connect(self.change_trash_folder)
        self.restore_trash_button = QPushButton("Restore selected photos")
        self.restore_trash_button.clicked.connect(self.restore_selected_photos)
        self.restore_trash_button.setMinimumSize(300, 44)
        self.restore_trash_button.setStyleSheet(
            "QPushButton { background: #1f6feb; color: white; font-size: 14px; "
            "font-weight: 700; border-radius: 5px; padding: 9px 16px; }"
        )
        self.trash_action_status_label = QLabel("")
        self.trash_action_status_label.setObjectName("trashActionStatus")
        self.trash_action_status_label.setWordWrap(True)
        self.category_selector = QComboBox()
        self.apply_category_button = QPushButton("Apply Category to Selected")
        self.apply_category_button.clicked.connect(lambda: self._apply_category_to_selected(str(self.category_selector.currentData() or "unknown")))
        self.category_action_status_label = QLabel("")
        self.category_action_status_label.setObjectName("cleanupCategoryActionStatus")
        self.category_action_status_label.setAccessibleName("Category action status")
        self.category_action_status_label.setWordWrap(True)
        self.category_action_status_label.setMinimumHeight(30)
        self.category_action_status_label.setVisible(False)
        self._category_status_timer = QTimer(self)
        self._category_status_timer.setSingleShot(True)
        self._category_status_timer.setInterval(8000)
        self._category_status_timer.timeout.connect(self.category_action_status_label.hide)
        self._last_category_status = ""
        self._category_status_show_count = 0

        actions_row_one = QHBoxLayout()
        actions_row_one.addWidget(self.keep_button)
        actions_row_one.addWidget(self.move_button)
        actions_row_one.addWidget(self.confirm_trash_button)

        actions_row_two = QHBoxLayout()
        actions_row_two.addWidget(QLabel("Category:"))
        actions_row_two.addWidget(self.category_selector, 1)
        actions_row_two.addWidget(self.apply_category_button)

        trash_actions = QGroupBox("Trash actions")
        trash_actions.setObjectName("trashActionsSection")
        trash_layout = QVBoxLayout(trash_actions)
        trash_layout.addWidget(self.trash_counts_label)
        trash_layout.addWidget(QLabel("Trash destination:"))
        trash_layout.addWidget(self.trash_destination_label)
        trash_layout.addWidget(self.change_trash_folder_button)
        trash_layout.addWidget(self.trash_explanation_label)
        trash_layout.addWidget(self.move_trash_button)
        trash_layout.addWidget(self.restore_trash_button)
        trash_layout.addWidget(self.trash_action_status_label)

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
        details_layout.addWidget(self.category_action_status_label)
        details_layout.addStretch(0)

        details_panel = QWidget()
        details_panel.setLayout(details_layout)
        details_panel.setMinimumWidth(440)

        grid_panel = QWidget()
        grid_layout = QVBoxLayout(grid_panel)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(trash_actions)
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
        root.addWidget(self.view_switch)
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
        if view == "history":
            self._request_missing_history_thumbnails()

    def _select_cleanup_view(self, view: str) -> None:
        current = str(self.view_combo.currentData() or "review")
        self._view_scroll_positions[current] = self.thumbnail_grid.scroll_value()
        index = self.view_combo.findData(view)
        if index < 0 or view == current:
            return
        self.view_combo.blockSignals(True)
        self.view_combo.setCurrentIndex(index)
        self.view_combo.blockSignals(False)
        self._sync_visible_view_switch(view)
        self._trigger_refresh(force=True)
        target = self._view_scroll_positions.get(view, 0)
        self.thumbnail_grid.restore_scroll_value(target)
        QTimer.singleShot(50, lambda value=target: self.thumbnail_grid.restore_scroll_value(value))

    def _on_view_combo_changed(self) -> None:
        view = str(self.view_combo.currentData() or "review")
        self._sync_visible_view_switch(view)
        self._trigger_refresh(force=True)
        if view == "history":
            self._request_missing_history_thumbnails()

    def _request_missing_history_thumbnails(self) -> None:
        missing = []
        for row in self._visible_rows:
            if self._thumbnail_for_photo(row.photo, (140, 140)) is None:
                row.photo.metadata["thumbnail_history_requested"] = True
                missing.append(row.photo)
        if missing:
            self.history_thumbnails_requested.emit(missing)

    def _sync_visible_view_switch(self, view: str) -> None:
        self.view_to_review_button.setChecked(view == "review")
        self.view_history_button.setChecked(view == "history")
        self.view_explanation_label.setText(
            "Photos already moved to Trash. You can review or restore them here."
            if view == "history" else "Photos still requiring cleanup decisions."
        )

    def set_photos(self, photos, imported_root: Optional[str | Path], total_imported_count: Optional[int] = None) -> None:
        self._imported_root = Path(imported_root) if imported_root else None
        if self._imported_root is not None:
            saved = self._trash_settings.value(self._trash_destination_setting_key(), "", type=str)
            chosen = Path(saved) if saved else TrashWorkflowService(self._imported_root).default_destination
            if not self._set_trash_destination(chosen):
                self._set_trash_destination(TrashWorkflowService(self._imported_root).default_destination)
        else:
            self._trash_destination = None
            self._trash_destination_error = "Import a library before moving photos to Trash."
            self._update_trash_actions()
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

    def confirm_selected_for_trash(self) -> None:
        selected = [row for row in self._selected_rows() if row.effective_category == "to_trash"]
        for row in selected:
            row.photo.metadata["trash_workflow_state"] = "confirmed_to_trash"
            row.user_decision = "confirmed_to_trash"
            self._save_photo_user_metadata(row.photo)
        if selected:
            noun = "photo" if len(selected) == 1 else "photos"
            message = f"{len(selected)} {noun} confirmed for Trash."
            self._show_user_saved_indicator(message)
            self._show_trash_status(message, "success")
            self._trigger_refresh(force=True)

    def change_trash_folder(self) -> None:
        start = str(self._trash_destination or (self._imported_root.parent if self._imported_root else Path.home()))
        selected = QFileDialog.getExistingDirectory(self, "Choose Trash folder", start)
        if selected:
            self._set_trash_destination(Path(selected), remember=True)

    def _trash_destination_setting_key(self) -> str:
        root = str(self._imported_root.resolve()) if self._imported_root else "no-library"
        return "trash_destination/" + hashlib.sha256(root.encode("utf-8")).hexdigest()

    def _set_trash_destination(self, destination: Path, *, remember: bool = False) -> bool:
        if self._imported_root is None:
            self._trash_destination = None
            self._trash_destination_error = "Import a library before choosing a Trash destination."
            self._update_trash_actions()
            return False
        try:
            self._trash_destination = TrashWorkflowService(self._imported_root).validate_destination(destination)
            self._trash_destination_error = ""
            if remember:
                self._trash_settings.setValue(self._trash_destination_setting_key(), str(self._trash_destination))
        except ValueError as exc:
            self._trash_destination = None
            self._trash_destination_error = str(exc)
            LOGGER.warning("Invalid Trash destination %s: %s", destination, exc)
        self._update_trash_actions()
        return self._trash_destination is not None

    def _show_trash_status(self, message: str, state: str = "info") -> None:
        colors = {"success": "#137333", "warning": "#8a4b08", "error": "#b42318", "info": "#1f6feb"}
        self.trash_action_status_label.setStyleSheet(f"font-weight: 600; color: {colors.get(state, colors['info'])};")
        self.trash_action_status_label.setText(message)
        self.trash_action_status_label.setVisible(True)

    def _update_trash_actions(self) -> None:
        if not hasattr(self, "trash_counts_label"):
            return
        states = [str((getattr(row.photo, "metadata", {}) or {}).get("trash_workflow_state", "")) for row in self._rows]
        failed = states.count("move_failed")
        active_states = [str(row.photo.metadata.get("trash_workflow_state", "")) for row in self._rows
                         if bool(row.photo.metadata.get("is_active", True))]
        if self.view_combo.currentData() == "history":
            self.trash_counts_label.setText(
                f"Moved to Trash: {states.count('moved_to_trash')} | "
                f"Restored: {states.count('restored')} | Failed moves: {failed}"
            )
        else:
            self.trash_counts_label.setText(
                f"To review: {len(active_states)} | Proposed for Trash: {active_states.count('proposed_to_trash')} | "
                f"Ready to move: {active_states.count('confirmed_to_trash')} | "
                f"Failed moves: {active_states.count('move_failed')}"
            )
        if self._trash_destination is not None:
            self.trash_destination_label.setText(str(self._trash_destination))
            self.trash_destination_label.setToolTip(str(self._trash_destination))
        else:
            self.trash_destination_label.setText(self._trash_destination_error or "No valid Trash destination")
        self.move_trash_button.setEnabled(self._trash_destination is not None and not self._bulk_category_in_progress)
        self.restore_trash_button.setVisible(self.view_combo.currentData() == "history")
        self.move_trash_button.setVisible(self.view_combo.currentData() != "history")
        self.confirm_trash_button.setVisible(self.view_combo.currentData() != "history")

    def _create_trash_confirmation_dialog(self, count: int, destination: Path):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Move photos to Trash")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(f"Move {count} confirmed photo(s) to Trash?")
        dialog.setInformativeText(
            f"Destination:\n{destination}\n\n"
            "The files will be moved, not permanently deleted.\n\n"
            "Other programs may no longer find these files in their current folders."
        )
        cancel_button = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        move_button = dialog.addButton("Move to Trash", QMessageBox.ButtonRole.AcceptRole)
        dialog.setDefaultButton(cancel_button)
        return dialog, move_button

    def restore_selected_photos(self) -> None:
        rows = [row for row in self._selected_rows()
                if row.photo.metadata.get("trash_workflow_state") == "moved_to_trash"]
        if not rows:
            message = "Select one or more moved photos in Trash History to restore."
            self._show_trash_status(message, "warning")
            QMessageBox.information(self, "No moved photos selected", message)
            return
        original_folders = [Path(row.photo.metadata.get("trash_original_path", "")).parent for row in rows]
        alternate_destination = None
        if any(not folder.is_dir() for folder in original_folders):
            selected = QFileDialog.getExistingDirectory(
                self, "Choose restore folder", str(self._imported_root or Path.home())
            )
            if not selected:
                self._show_trash_status("Restore cancelled because an original folder is unavailable.", "warning")
                return
            alternate_destination = Path(selected)
        destinations = {str(folder) for folder in original_folders}
        destination_text = next(iter(destinations)) if len(destinations) == 1 else "their original folders"
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Restore photos")
        dialog.setText(f"Restore {len(rows)} photo(s) to {destination_text}?")
        dialog.setInformativeText("The files will return to the active photo workflow.")
        cancel_button = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        restore_button = dialog.addButton("Restore", QMessageBox.ButtonRole.AcceptRole)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        if dialog.clickedButton() is not restore_button:
            return
        service = TrashWorkflowService(self._imported_root)
        records = []
        for row in rows:
            metadata = row.photo.metadata
            records.append(TrashRecord(
                str(getattr(row.photo, "id", "") or self._photo_key(row.photo)),
                str(metadata.get("trash_original_path", "")), state="moved_to_trash",
                destination_path=str(metadata.get("trash_destination_path", row.photo.path)),
                history=list(metadata.get("trash_history", [])),
            ))
        result = service.restore(records, alternate_destination)
        restored = []
        for row, record in zip(rows, records):
            row.photo.metadata["trash_history"] = record.history
            row.photo.metadata["trash_move_error"] = record.error
            if record.state == "restored":
                row.photo.metadata["trash_workflow_state"] = "restored"
                row.photo.metadata["is_active"] = True
                row.photo.path = Path(record.destination_path)
                restored.append(row.photo)
            self._save_photo_user_metadata(row.photo)
        if result.failed_count:
            message = f"{result.restored_count} of {result.requested_count} photos restored. {result.failed_count} could not be restored."
            state = "warning"
        else:
            noun = "photo" if result.restored_count == 1 else "photos"
            message, state = f"{result.restored_count} {noun} restored to the active workflow.", "success"
        self._show_trash_status(message, state)
        self._trigger_refresh(force=True)
        if restored:
            self.active_state_changed.emit(restored)

    def move_confirmed_to_trash(self) -> None:
        if self._bulk_category_in_progress:
            self._show_trash_status("A Trash operation is already in progress.", "warning")
            return
        rows = [row for row in self._rows
                if row.photo.metadata.get("trash_workflow_state") in {"confirmed_to_trash", "move_failed"}]
        if not rows:
            message = "No photos are confirmed for Trash. Confirm proposed photos before moving them."
            LOGGER.info("Trash move blocked: no confirmed photos")
            self._show_trash_status(message, "warning")
            QMessageBox.information(self, "No confirmed photos", message)
            return
        if self._imported_root is None or self._trash_destination is None:
            message = self._trash_destination_error or "No valid Trash destination is available."
            LOGGER.warning("Trash move blocked: %s", message)
            self._show_trash_status(message, "error")
            QMessageBox.warning(self, "Trash destination unavailable", message)
            return
        service = TrashWorkflowService(self._imported_root)
        destination = self._trash_destination
        dialog, move_button = self._create_trash_confirmation_dialog(len(rows), destination)
        dialog.exec()
        if dialog.clickedButton() is not move_button:
            self._show_trash_status("Trash move cancelled. No files were moved.", "info")
            return
        self._bulk_category_in_progress = True
        try:
            records = [TrashRecord(str(getattr(row.photo, "id", "") or self._photo_key(row.photo)),
                                   str(row.photo.path), state=row.photo.metadata["trash_workflow_state"])
                       for row in rows]
            result = service.move_confirmed(records, destination)
            by_id = {record.photo_id: record for record in records}
            for row in rows:
                key = str(getattr(row.photo, "id", "") or self._photo_key(row.photo))
                record = by_id[key]
                old_path = Path(row.photo.path)
                old_card_key = self._photo_key(row.photo)
                retained_card_thumbnail = self._thumbnail_cache.get(old_card_key)
                row.photo.metadata["trash_workflow_state"] = record.state
                row.photo.metadata["is_active"] = record.state != "moved_to_trash"
                row.photo.metadata.setdefault("trash_original_path", record.source_path)
                row.photo.metadata["trash_destination_path"] = record.destination_path
                row.photo.metadata["trash_move_error"] = record.error
                row.photo.metadata["trash_history"] = record.history
                if record.state == "moved_to_trash" and record.history:
                    row.photo.metadata["trash_moved_at"] = record.history[-1].get("timestamp", "")
                if record.state == "moved_to_trash":
                    row.photo.path = Path(record.destination_path)
                    preserve_thumbnail_for_relocation(
                        str(old_path), int(getattr(row.photo, "modified_time_ns", 0) or 0),
                        int(getattr(row.photo, "file_size", 0) or 0), str(row.photo.path),
                    )
                    moved_cache = get_thumbnail_cache_path(str(row.photo.path))
                    if moved_cache.is_file():
                        row.photo.thumbnail_path = str(moved_cache)
                        row.photo.metadata["thumbnail_path"] = str(moved_cache)
                    if retained_card_thumbnail is not None:
                        self._thumbnail_cache[self._photo_key(row.photo)] = retained_card_thumbnail
                self._save_photo_user_metadata(row.photo)
            if result.moved_count == 0 and result.failed_count:
                message, state = "No photos were moved. Review the error details.", "error"
            elif result.failed_count:
                message = (f"{result.moved_count} of {result.requested_count} photos moved to Trash and were "
                           f"removed from the active workflow. {result.failed_count} could not be moved.")
                state = "warning"
            else:
                noun = "photo" if result.moved_count == 1 else "photos"
                message, state = (f"{result.moved_count} {noun} moved to Trash and removed from the active workflow.",
                                  "success")
            self._show_user_saved_indicator(message)
            self._show_trash_status(message, state)
            self._trigger_refresh(force=True)
            self.active_state_changed.emit([row.photo for row in rows if not row.photo.metadata.get("is_active", True)])
        finally:
            self._bulk_category_in_progress = False
            self._update_trash_actions()

    def _on_grid_selection_changed(self, selected_keys: set[str], selected_key: Optional[str]) -> None:
        started = time.perf_counter()
        measurement = begin_selection_measurement("cleanup")
        if measurement is not None:
            add_selection_count("Selected photos", len(selected_keys))
            add_selection_count("Visible cards", self.thumbnail_grid.rendered_card_count())
        self.selection_count_label.setText(f"Selected: {self.thumbnail_grid.selected_count()}")
        add_selection_time("Selected-count update", (time.perf_counter() - started) * 1000.0)
        if not selected_key:
            self._clear_details()
            finish_selection_measurement(deferred=True)
            return
        row = self._row_for_key(selected_key)
        if row is None:
            self._clear_details()
            finish_selection_measurement(deferred=True)
            return
        details_started = time.perf_counter()
        self._show_details(row)
        add_selection_time("Detail text update", (time.perf_counter() - details_started) * 1000.0)
        add_selection_count("Detail refreshes")
        add_selection_count("Grid rebuilds", 0)
        add_selection_count("Filter operations", 0)
        add_selection_count("Sort operations", 0)
        add_selection_count("Layout activation calls", 0)
        add_selection_time("Total synchronous UI-thread time", (time.perf_counter() - started) * 1000.0)
        finish_selection_measurement(deferred=True)

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

        trash_proposal = (
            metadata.get("trash_proposal_category") == "to_trash"
            and metadata.get("trash_workflow_state") in {"proposed_to_trash", "confirmed_to_trash", "moved_to_trash", "move_failed"}
        )

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
            ("to_trash" if trash_proposal else "")
            or metadata.get("cleanup_effective_category", "")
            or metadata.get("effective_media_category", "")
            or metadata.get("relevance_category", "")
            or getattr(photo, "effective_media_category", "")
            or user_corrected_category
            or automatic_category
            or MediaCategory.Unknown.value
        ).strip().lower()

        # Stable category and workflow state are distinct. Existing manual or
        # reimported To Trash assignments are proposals until explicitly confirmed.
        if (effective_category == "to_trash" and metadata.get("is_active", True)
                and metadata.get("trash_workflow_state") not in {
                    "confirmed_to_trash", "moved_to_trash", "move_failed", "restored",
                }):
            metadata["trash_workflow_state"] = "proposed_to_trash"
            metadata.setdefault("trash_proposal_category", "to_trash")
            photo.metadata = metadata

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
        if self._visible_rows:
            self.results_label.setText(f"Showing {len(self._visible_rows)} photos")
        elif self.view_combo.currentData() == "history":
            self.results_label.setText("No photos have been moved to Trash yet.")
        else:
            self.results_label.setText("No remaining photos in this view.")
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
        history = self.view_combo.currentData() == "history"
        if history:
            rows = [row for row in self._rows
                    if row.photo.metadata.get("trash_workflow_state") == "moved_to_trash"]
        else:
            rows = [row for row in self._rows if bool(row.photo.metadata.get("is_active", True))
                    and row.photo.metadata.get("trash_workflow_state") != "moved_to_trash"]

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
        state = str((getattr(photo, "metadata", {}) or {}).get("trash_workflow_state", ""))
        self.trash_status_value.setText({
            "proposed_to_trash": "Proposed", "confirmed_to_trash": "Confirmed",
            "moved_to_trash": "Moved", "move_failed": "Failed", "restored": "Restored",
        }.get(state, "Not in Trash workflow"))
        self.decision_value.setText(row.user_decision.replace("_", " ").title())
        self.metadata_summary_value.setText(self._metadata_summary(photo))
        metadata = getattr(photo, "metadata", {}) or {}
        self.original_path_value.setText(str(metadata.get("trash_original_path", "") or "-"))
        self.current_trash_path_value.setText(str(metadata.get("trash_destination_path", "") or "-"))
        self.trash_moved_at_value.setText(str(metadata.get("trash_moved_at", "") or "-"))

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
        self.trash_status_value.setText("-")
        self.original_path_value.setText("-")
        self.current_trash_path_value.setText("-")
        self.trash_moved_at_value.setText("-")
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
        if not selected_rows or self._bulk_category_in_progress:
            return

        started = time.perf_counter()
        self._bulk_category_in_progress = True
        self.apply_category_button.setEnabled(False)
        self._category_status_timer.stop()
        busy_noun = "photo" if len(selected_rows) == 1 else "photos"
        self._set_category_action_status(
            f"Applying category to {len(selected_rows)} {busy_noun}...",
            state="busy",
            auto_hide=False,
        )

        affected_keys = [self._photo_key(row.photo) for row in selected_rows]
        preferred_key = self.thumbnail_grid.selected_key() or (affected_keys[0] if affected_keys else None)
        previous_visible_keys = [self._photo_key(row.photo) for row in self._visible_rows]
        previous_scroll = self.thumbnail_grid.scroll_value()

        persistence_started = time.perf_counter()
        successful_rows: list[CleanupReviewRow] = []
        failures = 0
        sidecar_ms = 0.0
        source = "user_bulk" if len(selected_rows) > 1 else "user"
        category_batch = getattr(self._category_learning_engine, "bulk_update", nullcontext)
        preference_batch = getattr(self._preference_learning_engine, "bulk_update", nullcontext)
        try:
            with ExitStack() as stack:
                stack.enter_context(category_batch())
                stack.enter_context(preference_batch())
                for row in selected_rows:
                    previous = row.effective_category
                    old_metadata = dict(getattr(row.photo, "metadata", {}) or {})
                    old_values = (
                        getattr(row.photo, "automatic_media_category", ""),
                        getattr(row.photo, "user_corrected_media_category", ""),
                        getattr(row.photo, "effective_media_category", ""),
                        getattr(row.photo, "media_category", ""),
                    )
                    self._set_photo_category(row, category)
                    sidecar_started = time.perf_counter()
                    try:
                        self._user_metadata_service.save_photo_metadata(row.photo)
                    except Exception:
                        failures += 1
                        row.photo.metadata = old_metadata
                        (row.photo.automatic_media_category,
                         row.photo.user_corrected_media_category,
                         row.photo.effective_media_category,
                         row.photo.media_category) = old_values
                        row.photo.sync_intelligence_from_metadata()
                        continue
                    finally:
                        sidecar_ms += (time.perf_counter() - sidecar_started) * 1000
                    self._category_learning_engine.record_category_correction(
                        row.photo, previous_category=previous,
                        corrected_category=category, source=source,
                    )
                    self._preference_learning_engine.record_category_correction(
                        row.photo, previous_category=previous,
                        corrected_category=category, source=source,
                    )
                    successful_rows.append(row)
        finally:
            persistence_ms = (time.perf_counter() - persistence_started) * 1000
        learning_ms = max(0.0, persistence_ms - sidecar_ms)

        if successful_rows:
            self._category_learning_engine.start_pending_visual_analysis_worker(limit=25)
        successful_keys = [self._photo_key(row.photo) for row in successful_rows]
        successful_key_set = set(successful_keys)
        self._rows = [
            self._build_row(row.photo) if self._photo_key(row.photo) in successful_key_set else row
            for row in self._rows
        ]
        self._refresh_group_options()
        ui_started = time.perf_counter()
        self._refresh_after_category_change(
            affected_keys=successful_keys,
            preferred_key=preferred_key,
            previous_visible_keys=previous_visible_keys,
            previous_scroll=previous_scroll,
        )
        if failures == len(selected_rows):
            self._set_category_action_status(
                "Category could not be applied to the selected photos.",
                state="error",
            )
        elif failures:
            self._set_category_action_status(
                f"Category applied to {len(successful_rows)} of {len(selected_rows)} photos. "
                f"{failures} could not be updated.",
                state="warning",
            )
        else:
            noun = "photo" if len(successful_rows) == 1 else "photos"
            self._set_category_action_status(
                f"Category applied to {len(successful_rows)} {noun}.",
                state="success",
            )
        ui_ms = (time.perf_counter() - ui_started) * 1000
        rebuilds = int([self._photo_key(row.photo) for row in self._visible_rows] != previous_visible_keys)
        total_ms = (time.perf_counter() - started) * 1000
        self.last_bulk_performance = {
            "selected_photos": len(selected_rows), "successful_photos": len(successful_rows),
            "failed_photos": failures, "total_ms": total_ms,
            "metadata_persistence_ms": persistence_ms, "sidecar_persistence_ms": sidecar_ms,
            "database_persistence_ms": 0.0, "learning_event_ms": learning_ms,
            "grid_cards_updated": len(successful_keys) if not rebuilds else 0,
            "full_grid_rebuilds": rebuilds, "thumbnail_reloads": 0,
            "ui_update_requests": len(successful_keys) + 1, "ui_update_ms": ui_ms,
            "responsive_ms": total_ms,
        }
        LOGGER.info(
            "[PERF] Cleanup bulk category assignment: %d photos, %.1f ms; "
            "persistence %.1f ms (sidecar %.1f ms, database 0.0 ms); learning %.1f ms; "
            "UI %.1f ms, cards %d, full grid rebuilds %d, thumbnail reloads 0, "
            "update requests %d, responsive %.1f ms",
            len(selected_rows), total_ms, persistence_ms, sidecar_ms, learning_ms,
            ui_ms, self.last_bulk_performance["grid_cards_updated"], rebuilds,
            self.last_bulk_performance["ui_update_requests"], total_ms,
        )
        self._bulk_category_in_progress = False
        self.apply_category_button.setEnabled(True)

    def _set_photo_category(self, row: CleanupReviewRow, category: str) -> None:
        previous = row.effective_category
        metadata = dict(getattr(row.photo, "metadata", {}) or {})
        automatic = str(metadata.get("automatic_media_category", "") or row.automatic_category
                        or getattr(row.photo, "automatic_media_category", "") or previous).strip().lower()
        metadata.update({
            "automatic_media_category": automatic, "user_corrected_media_category": category,
            "effective_media_category": category, "media_category": category,
            "cleanup_automatic_category": automatic, "cleanup_user_corrected_category": category,
            "cleanup_effective_category": category, "relevance_category": category,
        })
        row.photo.metadata = metadata
        row.photo.automatic_media_category = automatic
        row.photo.user_corrected_media_category = category
        row.photo.effective_media_category = category
        row.photo.media_category = category
        row.photo.sync_intelligence_from_metadata()

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
        selected_keys = set(self.thumbnail_grid.selected_keys())
        return [row for row in self._rows if self._photo_key(row.photo) in selected_keys]

    def _row_for_key(self, key: str) -> Optional[CleanupReviewRow]:
        for row in self._rows:
            if self._photo_key(row.photo) == key:
                return row
        return None

    def _photo_key(self, photo) -> str:
        metadata = getattr(photo, "metadata", {}) or {}
        if metadata.get("trash_workflow_state") and getattr(photo, "id", None):
            return f"photo:{photo.id}"
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
        self._update_trash_actions()
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

    def _set_category_action_status(
        self, text: str, *, state: str, auto_hide: bool = True
    ) -> None:
        styles = {
            "success": ("#176b34", "#edf8f0", "#9dd5ad"),
            "warning": ("#7a4d00", "#fff8e1", "#e8c66a"),
            "error": ("#9b1c1c", "#fff1f0", "#f1aeb5"),
            "busy": ("#1f6feb", "#eef6ff", "#b6d4fe"),
        }
        text = str(text or "").strip()
        if not text:
            return
        if text == self._last_category_status and not self.category_action_status_label.isHidden():
            return
        self._last_category_status = text
        self._category_status_show_count += 1
        foreground, background, border = styles.get(state, styles["busy"])
        self.category_action_status_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {foreground}; "
            f"background: {background}; border: 1px solid {border}; "
            "border-radius: 4px; padding: 5px 8px;"
        )
        self.category_action_status_label.setProperty("statusState", state)
        self.category_action_status_label.setText(text)
        self.category_action_status_label.setVisible(True)
        if auto_hide:
            self._category_status_timer.start()

    def _show_user_saved_indicator(self, text: str) -> None:
        self.user_saved_label.setText(text)
        self.user_saved_label.setVisible(True)
        QTimer.singleShot(2500, lambda: self.user_saved_label.setVisible(False))

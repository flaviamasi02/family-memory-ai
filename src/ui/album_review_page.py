from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QEvent, QTimer, Qt, QSize, Signal
from PySide6.QtGui import QFontMetrics, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QFormLayout,
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

from album.album_scoring_engine import AlbumScoreBreakdown
from core.category_registry import get_category_registry
from core.media_classifier import (
    DecisionHistory,
    MediaCategory,
    MediaClassifier,
    UserDecision,
    media_category_label,
    ordered_media_category_values,
)
from core.image_display_loader import load_display_pixmap, load_display_thumbnail
from core.user_metadata_service import UserMetadataService
from learning.category_learning_engine import get_category_learning_engine
from learning.preference_learning_engine import get_preference_learning_engine
from ui.category_management_dialog import CategoryManagementDialog
from ui.components.workspace_header import WorkspaceHeader
from ui.components.workspace_info_content import WORKSPACE_INFO_CONTENT
from ui.components.workspace_info_panel import WorkspaceInfoPanel
from ui.image_preview_dialog import ImagePreviewDialog
from ui.learning_summary_dialog import LearningSummaryDialog
from ui.help.workspace_help_content import MEMORY_REVIEW_WORKSPACE


@dataclass
class AlbumReviewRow:
    breakdown: AlbumScoreBreakdown
    review_state: str = "pending"
    user_decision: str = UserDecision.Pending.value
    pipeline_state: str = "imported"
    rejection_reason: Optional[str] = None


class AlbumReviewCardWidget(QFrame):
    clicked = Signal(str, int)
    double_clicked = Signal(str)

    def __init__(self, row: AlbumReviewRow, key: str, thumbnail: Optional[QPixmap] = None, parent=None):
        super().__init__(parent)
        self.row = row
        self.key = key
        self._selected = False

        self.setObjectName("albumReviewCard")
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

        self.score_badge = QLabel("")
        self.category_badge = QLabel("")
        self.decision_badge = QLabel("")
        for badge in (self.score_badge, self.category_badge, self.decision_badge):
            badge.setStyleSheet("background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 6px; padding: 2px 6px;")
            badge.setMaximumHeight(22)

        self.category_label = QLabel("")
        self.confidence_label = QLabel("")
        self.decision_label = QLabel("")
        self.pipeline_label = QLabel("")
        self.pipeline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.category_label.setVisible(False)
        self.confidence_label.setVisible(False)
        self.decision_label.setVisible(False)
        self.pipeline_label.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(self.thumbnail_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.filename_label)
        badge_layout = QHBoxLayout()
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setSpacing(4)
        badge_layout.addWidget(self.score_badge)
        badge_layout.addWidget(self.category_badge)
        badge_layout.addWidget(self.decision_badge)
        layout.addLayout(badge_layout)

        self.refresh_from_row(thumbnail=thumbnail)
        self.set_selected(False)

    def refresh_from_row(self, thumbnail: Optional[QPixmap] = None) -> None:
        breakdown = self.row.breakdown
        photo = breakdown.photo

        pixmap = thumbnail if isinstance(thumbnail, QPixmap) else getattr(photo, "thumbnail", None)
        if isinstance(pixmap, QPixmap):
            self.thumbnail_label.setPixmap(pixmap)
            self.thumbnail_label.setText("")
        else:
            self.thumbnail_label.setPixmap(QPixmap())
            self.thumbnail_label.setText("No thumbnail")

        full_name = photo.display_name()
        self.filename_label.setToolTip(full_name)
        metrics = QFontMetrics(self.filename_label.font())
        self.filename_label.setText(metrics.elidedText(full_name, Qt.TextElideMode.ElideRight, self.filename_label.width()))

        confidence = float(getattr(photo, "classification_confidence", 0.0) or 0.0)
        category_value = str(getattr(photo, "effective_media_category", "") or getattr(photo, "media_category", "unknown") or "unknown")
        category_text = media_category_label(category_value)
        decision_text = self.row.user_decision.replace("_", " ").title()
        self.score_badge.setText(f"S {breakdown.total_score:.0f}")
        short_category = category_text if len(category_text) <= 10 else category_text[:9] + ".."
        short_decision = decision_text if len(decision_text) <= 10 else decision_text[:9] + ".."
        self.category_badge.setText(short_category)
        self.decision_badge.setText(short_decision)
        self.category_label.setText(f"Category: {category_text}")
        self.confidence_label.setText(f"Confidence: {max(0, min(100, int(round(confidence * 100))))}%")
        self.decision_label.setText(f"Decision: {decision_text}")

        state_text = self.row.review_state.capitalize()
        pipeline_text = self.row.pipeline_state.capitalize()
        if self.row.rejection_reason:
            self.pipeline_label.setText(
                f"Review: {state_text} | Pipeline: {pipeline_text} ({self.row.rejection_reason})"
            )
        else:
            self.pipeline_label.setText(f"Review: {state_text} | Pipeline: {pipeline_text}")

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        if self._selected:
            self.setStyleSheet(
                "QFrame#albumReviewCard { border: 2px solid #1f6feb; border-radius: 6px; background: #eef6ff; }"
            )
        else:
            self.setStyleSheet(
                "QFrame#albumReviewCard { border: 1px solid #c9c9c9; border-radius: 6px; background: #ffffff; }"
            )

    def mousePressEvent(self, event):
        self.clicked.emit(self.key, int(event.modifiers().value))
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self.key)
        super().mouseDoubleClickEvent(event)


class AlbumReviewPage(QWidget):
    FILTER_ALL = "All"
    FILTER_PENDING = "Pending"
    FILTER_APPROVED = "Approved"
    FILTER_REJECTED = "Rejected"
    CATEGORY_FILTER_ALL = "All categories"

    SORT_HIGHEST = "Highest score"
    SORT_LOWEST = "Lowest score"
    SORT_DATE = "Date"

    review_state_changed = Signal()
    categories_changed = Signal()
    help_requested = Signal(str)

    WORKSPACE_ID = MEMORY_REVIEW_WORKSPACE

    def __init__(self, parent=None):
        super().__init__(parent)

        self._all_rows: List[AlbumReviewRow] = []
        self._visible_rows: List[AlbumReviewRow] = []
        self._cards_by_key = {}
        self._rendered_keys: List[str] = []
        self._selected_key: Optional[str] = None
        self._selected_keys: set[str] = set()
        self._selection_anchor_key: Optional[str] = None
        self._details_key: Optional[str] = None
        self._pending_render_index = 0
        self._initial_render_count = 100
        self._render_batch_size = 60
        self._target_render_count = 0
        self._grid_columns = 4
        self._candidate_count = 0
        self._rejection_reasons_summary: Dict[str, int] = {}
        self._thumbnail_cache: Dict[str, tuple[int, QPixmap]] = {}
        self._thumbnail_source_by_key: Dict[str, str] = {}
        self._scaled_thumbnail_path_cache: Dict[str, tuple[str, QPixmap]] = {}
        self._preview_cache: Dict[str, tuple[int, QPixmap]] = {}
        self._last_view_signature: Optional[tuple[str, str, str]] = None
        self._last_visible_key_order: List[str] = []
        self._grid_rebuild_count = 0
        self._decision_history = DecisionHistory()
        self._decision_selector_syncing = False
        self._category_selector_syncing = False
        self._preview_dialog: Optional[ImagePreviewDialog] = None
        self._user_metadata_service = UserMetadataService()
        self._category_registry = get_category_registry()
        self._category_learning_engine = get_category_learning_engine()
        self._preference_learning_engine = get_preference_learning_engine()
        self._media_classifier = MediaClassifier()

        self.header = WorkspaceHeader("Memory Review")
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

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(
            [
                self.FILTER_ALL,
                self.FILTER_PENDING,
                self.FILTER_APPROVED,
                self.FILTER_REJECTED,
            ]
        )
        self.filter_combo.currentTextChanged.connect(self._trigger_refresh)

        self.category_filter_combo = QComboBox()
        self.category_filter_combo.currentTextChanged.connect(self._trigger_refresh)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems([self.SORT_HIGHEST, self.SORT_LOWEST, self.SORT_DATE])
        self.sort_combo.currentTextChanged.connect(self._trigger_refresh)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search filename...")
        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.setInterval(220)
        self._search_debounce_timer.timeout.connect(self._trigger_refresh)
        self.search_input.textChanged.connect(self._on_search_text_changed)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Decision status:"))
        controls_layout.addWidget(self.filter_combo)
        controls_layout.addWidget(QLabel("Category:"))
        controls_layout.addWidget(self.category_filter_combo)
        controls_layout.addWidget(QLabel("Sort:"))
        controls_layout.addWidget(self.sort_combo)
        controls_layout.addWidget(QLabel("Search:"))
        controls_layout.addWidget(self.search_input, 1)
        self.selection_count_label = QLabel("Selected: 0")
        self.user_saved_label = QLabel("")
        self.user_saved_label.setStyleSheet("font-size: 12px; color: #1f6feb;")
        self.user_saved_label.setVisible(False)
        self.select_all_visible_button = QPushButton("Select all visible")
        self.select_all_visible_button.clicked.connect(self.select_all_visible)
        self.clear_selection_button = QPushButton("Clear selection")
        self.clear_selection_button.clicked.connect(self.clear_selection)
        self.manage_categories_button = QPushButton("Manage Categories")
        self.manage_categories_button.clicked.connect(self._on_manage_categories)
        self.learning_summary_button = QPushButton("Learning Summary")
        self.learning_summary_button.clicked.connect(self._on_learning_summary)
        self.reclassify_unknowns_button = QPushButton("Reclassify Unknowns")
        self.reclassify_unknowns_button.clicked.connect(self.reclassify_unknowns_from_learning)
        controls_layout.addWidget(self.selection_count_label)
        controls_layout.addWidget(self.user_saved_label)
        controls_layout.addWidget(self.manage_categories_button)
        controls_layout.addWidget(self.learning_summary_button)
        controls_layout.addWidget(self.reclassify_unknowns_button)
        controls_layout.addWidget(self.select_all_visible_button)
        controls_layout.addWidget(self.clear_selection_button)

        self.results_label = QLabel("Showing 0 photos")

        self.grid_scroll = QScrollArea(self)
        self.grid_scroll.setWidgetResizable(True)

        self.grid_content = QWidget(self.grid_scroll)
        self.grid_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.grid_layout = QGridLayout(self.grid_content)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(8)
        self.grid_scroll.setWidget(self.grid_content)
        self.grid_scroll.viewport().installEventFilter(self)
        self.grid_scroll.verticalScrollBar().valueChanged.connect(self._on_scroll_value_changed)

        self.preview_label = QLabel("No preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(280, 160)
        self.preview_label.setStyleSheet("border: 1px solid #aaa;")

        self.filename_value = QLabel("-")
        self.score_value = QLabel("-")
        self.pipeline_value = QLabel("-")
        self.rejection_reason_value = QLabel("-")
        self.media_category_value = QLabel("-")
        self.classification_reason_value = QLabel("-")
        self.classification_reason_value.setWordWrap(True)
        self.visual_summary_value = QLabel("-")
        self.visual_summary_value.setWordWrap(True)
        self.confidence_value = QLabel("-")
        self.user_decision_value = QLabel("-")
        self.date_value = QLabel("-")
        self.date_source_value = QLabel("-")

        details_form = QFormLayout()
        details_form.addRow("Filename:", self.filename_value)
        details_form.addRow("Score:", self.score_value)
        details_form.addRow("Media category:", self.media_category_value)
        details_form.addRow("Classification reason:", self.classification_reason_value)
        details_form.addRow("Visual signals:", self.visual_summary_value)
        details_form.addRow("Confidence:", self.confidence_value)
        details_form.addRow("User decision:", self.user_decision_value)
        details_form.addRow("Date:", self.date_value)
        details_form.addRow("Date source:", self.date_source_value)
        details_form.addRow("Pipeline:", self.pipeline_value)
        details_form.addRow("Rejection reason:", self.rejection_reason_value)

        self.explanations_list = QListWidget()
        self.explanations_list.setMinimumHeight(220)
        self.explanations_list.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )

        self.decision_selector = QComboBox()
        for decision in UserDecision:
            self.decision_selector.addItem(decision.value)
        self.decision_selector.currentTextChanged.connect(self._on_decision_selector_changed)

        self.category_selector = QComboBox()
        self.category_selector.currentTextChanged.connect(self._on_category_selector_changed)

        self.apply_decision_button = QPushButton("Apply Decision to Selected")
        self.apply_decision_button.clicked.connect(self._apply_selector_decision)
        self.apply_category_button = QPushButton("Apply Category to Selected")
        self.apply_category_button.clicked.connect(self._apply_selector_category)

        actions_layout = QHBoxLayout()
        actions_layout.addWidget(QLabel("Category:"))
        actions_layout.addWidget(self.category_selector, 1)
        actions_layout.addWidget(self.apply_category_button)
        self.decision_action_label = QLabel("Decision:")
        self.decision_action_label.setVisible(False)
        self.decision_selector.setVisible(False)
        self.apply_decision_button.setVisible(False)

        details_layout = QVBoxLayout()
        details_layout.addWidget(QLabel("Preview"))
        details_layout.addWidget(self.preview_label)
        details_layout.addLayout(details_form)
        details_layout.addWidget(QLabel("Score explanation"))
        details_layout.addWidget(self.explanations_list, 1)
        details_layout.addLayout(actions_layout)

        details_panel = QWidget()
        details_panel.setLayout(details_layout)
        details_panel.setMinimumWidth(420)

        splitter = QSplitter()
        grid_panel = QWidget()
        grid_layout = QVBoxLayout(grid_panel)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self.results_label)
        grid_layout.addWidget(self.grid_scroll, 1)

        splitter.addWidget(grid_panel)
        splitter.addWidget(details_panel)
        splitter.setStretchFactor(0, 8)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([1000, 420])

        root_layout = QVBoxLayout(self)
        root_layout.addWidget(self.header)
        root_layout.addWidget(self.info_panel)
        root_layout.addLayout(controls_layout)
        root_layout.addWidget(splitter, 1)

        self._reload_category_controls()

    def _on_help_clicked(self) -> None:
        self.help_requested.emit(self.WORKSPACE_ID)

    def _reload_category_controls(self) -> None:
        current_filter = self.category_filter_combo.currentText().strip() or self.CATEGORY_FILTER_ALL
        self.category_filter_combo.blockSignals(True)
        self.category_filter_combo.clear()
        self.category_filter_combo.addItem(self.CATEGORY_FILTER_ALL)
        for category_value in ordered_media_category_values():
            self.category_filter_combo.addItem(media_category_label(category_value), category_value)
        filter_index = self.category_filter_combo.findText(current_filter)
        self.category_filter_combo.setCurrentIndex(filter_index if filter_index >= 0 else 0)
        self.category_filter_combo.blockSignals(False)

        current_category_id = str(self.category_selector.currentData() or "").strip()
        self.category_selector.blockSignals(True)
        self.category_selector.clear()
        for category_value in ordered_media_category_values():
            self.category_selector.addItem(media_category_label(category_value), category_value)
        if current_category_id:
            selector_index = self.category_selector.findData(current_category_id)
            if selector_index >= 0:
                self.category_selector.setCurrentIndex(selector_index)
        self.category_selector.blockSignals(False)

    def _on_manage_categories(self) -> None:
        usage = self._category_usage_counts()
        dialog = CategoryManagementDialog(
            registry=self._category_registry,
            usage_counts=usage,
            reassignment_callback=self._reassign_deleted_category,
            parent=self,
        )
        dialog.exec()
        self._reload_category_controls()
        self._trigger_refresh(force=True)
        self.categories_changed.emit()

    def refresh_category_options(self) -> None:
        self._reload_category_controls()
        self._trigger_refresh(force=True)

    def _on_learning_summary(self) -> None:
        dialog = LearningSummaryDialog(
            self._category_learning_engine,
            self,
            preference_engine=self._preference_learning_engine,
        )
        dialog.exec()

    def reclassify_unknowns_from_learning(self) -> int:
        changed_count = 0

        for row in self._all_rows:
            photo = row.breakdown.photo
            metadata = dict(getattr(photo, "metadata", {}) or {})

            user_corrected = str(
                metadata.get("user_corrected_media_category", "")
                or getattr(photo, "user_corrected_media_category", "")
                or ""
            ).strip().lower()

            current_effective = self._effective_category_for_photo(photo)

            if user_corrected or current_effective != MediaCategory.Unknown.value:
                continue

            self._media_classifier.classify_photo(photo)
            new_effective = self._effective_category_for_photo(photo)

            if new_effective == current_effective:
                continue

            row.user_decision = self._initial_user_decision_for_photo(photo)
            row.review_state = self._review_state_from_decision(row.user_decision)

            card = self._cards_by_key.get(self._row_key(row))
            if card is not None:
                card.refresh_from_row(thumbnail=self._get_cached_card_thumbnail(row))

            changed_count += 1

        self._show_user_saved_indicator(f"Reclassified {changed_count} unknown photos")

        if changed_count:
            selected = self._selected_row()
            if selected is not None:
                self._show_details(selected, force=True)
            self._trigger_refresh(force=True)

        return changed_count

    def _category_usage_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self._all_rows:
            category_id = self._effective_category_for_photo(row.breakdown.photo)
            counts[category_id] = counts.get(category_id, 0) + 1
        return counts

    def _reassign_deleted_category(self, old_category_id: str, new_category_id: str) -> None:
        old_id = str(old_category_id or "").strip().lower()
        new_id = str(new_category_id or "").strip().lower()
        if not old_id or not new_id or old_id == new_id:
            return

        for row in self._all_rows:
            photo = row.breakdown.photo
            metadata = dict(getattr(photo, "metadata", {}) or {})

            corrected = str(metadata.get("user_corrected_media_category", "") or getattr(photo, "user_corrected_media_category", "") or "").strip().lower()
            effective = str(metadata.get("effective_media_category", "") or getattr(photo, "effective_media_category", "") or "").strip().lower()
            automatic = str(metadata.get("automatic_media_category", "") or getattr(photo, "automatic_media_category", "") or "").strip().lower()

            changed = False
            if corrected == old_id:
                corrected = new_id
                metadata["user_corrected_media_category"] = new_id
                photo.user_corrected_media_category = new_id
                changed = True
            if effective == old_id:
                metadata["effective_media_category"] = new_id
                metadata["media_category"] = new_id
                photo.effective_media_category = new_id
                photo.media_category = new_id
                changed = True
            if automatic == old_id:
                metadata["automatic_media_category"] = new_id
                photo.automatic_media_category = new_id
                changed = True

            if changed:
                photo.metadata = metadata
                photo.sync_intelligence_from_metadata()

    def set_scored_photos(self, scored_photos: List[AlbumScoreBreakdown]) -> None:
        for item in scored_photos:
            self._ensure_category_fields(item.photo)

        self._all_rows = [
            AlbumReviewRow(
                breakdown=item,
                review_state=self._review_state_from_decision(self._initial_user_decision_for_photo(item.photo)),
                user_decision=self._initial_user_decision_for_photo(item.photo),
                pipeline_state="selected",
                rejection_reason=None,
            )
            for item in scored_photos
        ]
        self._selected_key = None
        self._selected_keys = set()
        self._selection_anchor_key = None
        self.sort_combo.setCurrentText(self.SORT_HIGHEST)
        self.filter_combo.setCurrentText(self.FILTER_ALL)
        self.category_filter_combo.setCurrentText(self.CATEGORY_FILTER_ALL)
        self.search_input.clear()
        self._trigger_refresh(force=True)

    def set_pipeline_data(
        self,
        imported_photos: List,
        candidate_photos: List,
        selected_photos: List,
        rejected_photos: List,
        scored_breakdowns: Dict[str, AlbumScoreBreakdown],
        rejection_reasons: Optional[Dict[str, int]] = None,
    ) -> None:
        self._candidate_count = len(candidate_photos or [])
        self._rejection_reasons_summary = dict(rejection_reasons or {})
        selected_keys = {str(getattr(photo, "path", "")) for photo in selected_photos or []}
        rejected_keys = {str(getattr(photo, "path", "")) for photo in rejected_photos or []}

        rows: List[AlbumReviewRow] = []
        for photo in imported_photos or []:
            self._ensure_category_fields(photo)
            key = str(getattr(photo, "path", ""))
            breakdown = scored_breakdowns.get(key)
            if breakdown is None:
                inferred_total = 0.0
                intelligence = getattr(photo, "intelligence", None)
                if intelligence is not None and intelligence.album_candidate_score is not None:
                    inferred_total = float(intelligence.album_candidate_score)

                breakdown = AlbumScoreBreakdown(
                    photo=photo,
                    total_score=inferred_total,
                    technical_score=0.0,
                    memory_score=0.0,
                    date_score=0.0,
                    explanation=[],
                )

            pipeline_state = "imported"
            rejection_reason = None
            intelligence = getattr(photo, "intelligence", None)

            if key in selected_keys:
                pipeline_state = "selected"
            elif key in rejected_keys:
                pipeline_state = "rejected"
                if intelligence is not None:
                    rejection_reason = getattr(intelligence, "album_rejection_reason", None)

            rows.append(
                AlbumReviewRow(
                    breakdown=breakdown,
                    review_state=self._review_state_from_decision(self._initial_user_decision_for_photo(photo)),
                    user_decision=self._initial_user_decision_for_photo(photo),
                    pipeline_state=pipeline_state,
                    rejection_reason=rejection_reason,
                )
            )

        self._all_rows = rows
        self._selected_key = None
        self._selected_keys = set()
        self._selection_anchor_key = None
        self.sort_combo.setCurrentText(self.SORT_HIGHEST)
        self.filter_combo.setCurrentText(self.FILTER_ALL)
        self.category_filter_combo.setCurrentText(self.CATEGORY_FILTER_ALL)
        self.search_input.clear()
        self._trigger_refresh(force=True)

    def _on_search_text_changed(self) -> None:
        self._search_debounce_timer.start()

    def _trigger_refresh(self, force: bool = False) -> None:
        self.refresh_view(force=force)

    def refresh_view(self, force: bool = False) -> None:
        view_signature = (
            self.filter_combo.currentText(),
            self.category_filter_combo.currentText(),
            self.sort_combo.currentText(),
            self.search_input.text().strip().lower(),
        )
        if not force and view_signature == self._last_view_signature:
            return

        self._last_view_signature = view_signature

        self._visible_rows = self._filtered_sorted_rows()
        self._selected_keys = {
            key for key in self._selected_keys if key in {self._row_key(row) for row in self._visible_rows}
        }
        if self._selected_key not in {self._row_key(row) for row in self._visible_rows}:
            self._selected_key = None

        self._clear_grid()
        self._cards_by_key = {}
        self._rendered_keys = []
        self._pending_render_index = 0
        self._target_render_count = min(self._initial_render_count, len(self._visible_rows))
        self._grid_columns = self._calculate_columns()
        self._grid_rebuild_count += 1

        self.results_label.setText(self._results_label_text())

        self._add_next_batch()

        if self._visible_rows and self._selected_key is None:
            first_key = self._row_key(self._visible_rows[0])
            self._select_key(first_key, additive=False, range_select=False)

        self._update_selection_count()

    def _results_label_text(self) -> str:
        if self._candidate_count or self._rejection_reasons_summary:
            selected = sum(1 for row in self._all_rows if row.pipeline_state == "selected")
            rejected = sum(1 for row in self._all_rows if row.pipeline_state == "rejected")
            reasons = ", ".join(
                f"{reason}:{count}"
                for reason, count in sorted(self._rejection_reasons_summary.items())
            )
            parts = [
                f"Imported: {len(self._all_rows)}",
                f"Candidates: {self._candidate_count}",
                f"Selected: {selected}",
                f"Rejected: {rejected}",
            ]
            if reasons:
                parts.append(f"Reasons: {reasons}")
            parts.append(f"Showing {len(self._visible_rows)}")
            return " | ".join(parts)
        return f"Showing {len(self._visible_rows)} of {len(self._all_rows)} photos"

    def _filtered_sorted_rows(self) -> List[AlbumReviewRow]:
        rows = list(self._all_rows)

        status_filter = self.filter_combo.currentText()
        if status_filter == self.FILTER_PENDING:
            rows = [row for row in rows if row.review_state == "pending"]
        elif status_filter == self.FILTER_APPROVED:
            rows = [row for row in rows if row.review_state == "approved"]
        elif status_filter == self.FILTER_REJECTED:
            rows = [row for row in rows if row.review_state == "rejected"]

        category_filter_data = self.category_filter_combo.currentData()
        category_filter_text = self.category_filter_combo.currentText()
        if category_filter_text != self.CATEGORY_FILTER_ALL and category_filter_data:
            wanted = str(category_filter_data).strip().lower()
            rows = [
                row for row in rows
                if self._effective_category_for_photo(row.breakdown.photo) == wanted
            ]

        search_text = self.search_input.text().strip().lower()
        if search_text:
            rows = [
                row for row in rows
                if search_text in row.breakdown.photo.display_name().lower()
            ]

        sort_mode = self.sort_combo.currentText()
        if sort_mode == self.SORT_LOWEST:
            rows.sort(key=lambda row: (row.breakdown.total_score, self._photo_date_sort_value(row.breakdown.photo)))
        elif sort_mode == self.SORT_DATE:
            rows.sort(key=lambda row: (self._photo_date_sort_value(row.breakdown.photo), row.breakdown.total_score), reverse=True)
        else:
            rows.sort(key=lambda row: (-row.breakdown.total_score, self._photo_date_sort_value(row.breakdown.photo)))

        return rows

    def _calculate_columns(self) -> int:
        width = self.grid_scroll.viewport().width()
        if width <= 0:
            width = self.grid_scroll.width()
        card_width = 172
        return max(1, width // card_width)

    def _clear_grid(self) -> None:
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def review_status_by_path(self) -> dict[str, str]:
        status_by_path = {}
        for row in self._all_rows:
            path = str(getattr(row.breakdown.photo, "path", "") or "")
            if not path:
                continue
            status_by_path[path] = row.review_state
        return status_by_path

    def _add_next_batch(self) -> None:
        if self._pending_render_index >= len(self._visible_rows):
            return

        end_index = min(
            len(self._visible_rows),
            max(self._target_render_count, self._pending_render_index + self._render_batch_size),
        )

        for index in range(self._pending_render_index, end_index):
            row = self._visible_rows[index]
            key = self._row_key(row)
            thumbnail = self._get_cached_card_thumbnail(row)

            card = AlbumReviewCardWidget(row=row, key=key, thumbnail=thumbnail)
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self._on_card_double_clicked)

            grid_index = len(self._rendered_keys)
            row_index = grid_index // self._grid_columns
            column_index = grid_index % self._grid_columns

            self.grid_layout.addWidget(card, row_index, column_index)
            self._cards_by_key[key] = card
            self._rendered_keys.append(key)

            card.set_selected(key in self._selected_keys)

        self._pending_render_index = end_index
        self.grid_content.adjustSize()

    def _on_scroll_value_changed(self, value: int) -> None:
        scrollbar = self.grid_scroll.verticalScrollBar()
        if scrollbar.maximum() <= 0:
            return

        if value >= scrollbar.maximum() - 300:
            self._target_render_count = min(
                len(self._visible_rows),
                self._target_render_count + self._render_batch_size,
            )
            self._add_next_batch()

    def eventFilter(self, watched, event):
        grid_scroll = getattr(self, "grid_scroll", None)
        if grid_scroll is not None and watched is grid_scroll.viewport() and event.type() == QEvent.Type.Resize:
            new_columns = self._calculate_columns()
            if new_columns != self._grid_columns:
                self._relayout_existing_cards(new_columns)
        return super().eventFilter(watched, event)

    def _relayout_existing_cards(self, new_columns: int) -> None:
        self._grid_columns = max(1, new_columns)

        existing_cards = []
        for key in self._rendered_keys:
            card = self._cards_by_key.get(key)
            if card is not None:
                existing_cards.append(card)

        for index, card in enumerate(existing_cards):
            self.grid_layout.removeWidget(card)
            row_index = index // self._grid_columns
            column_index = index % self._grid_columns
            self.grid_layout.addWidget(card, row_index, column_index)

        self.grid_content.adjustSize()

    def _on_card_clicked(self, key: str, modifiers_value: int) -> None:
        modifiers = Qt.KeyboardModifier(modifiers_value)
        additive = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        range_select = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        self._select_key(key, additive=additive, range_select=range_select)

    def _select_key(self, key: str, additive: bool = False, range_select: bool = False) -> None:
        visible_keys = [self._row_key(row) for row in self._visible_rows]
        if key not in visible_keys:
            return

        if range_select and self._selection_anchor_key in visible_keys:
            start = visible_keys.index(self._selection_anchor_key)
            end = visible_keys.index(key)
            if start > end:
                start, end = end, start
            if not additive:
                self._selected_keys.clear()
            self._selected_keys.update(visible_keys[start:end + 1])
        elif additive:
            if key in self._selected_keys:
                self._selected_keys.remove(key)
            else:
                self._selected_keys.add(key)
            self._selection_anchor_key = key
        else:
            self._selected_keys = {key}
            self._selection_anchor_key = key

        self._selected_key = key

        for card_key, card in self._cards_by_key.items():
            card.set_selected(card_key in self._selected_keys)

        row = self._row_for_key(key)
        if row is not None:
            self._show_details(row)

        self._update_selection_count()

    def _on_card_double_clicked(self, key: str) -> None:
        rows = list(self._visible_rows)
        keys = [self._row_key(row) for row in rows]
        if key not in keys:
            return

        start_index = keys.index(key)
        photos = [row.breakdown.photo for row in rows]

        self._preview_dialog = ImagePreviewDialog(self)
        self._preview_dialog.set_items(photos, start_index=start_index)
        self._preview_dialog.show()
        self._preview_dialog.raise_()
        self._preview_dialog.activateWindow()

    def select_all_visible(self) -> None:
        rendered_keys = set(self._rendered_keys)
        self._selected_keys = set(rendered_keys)
        if self._rendered_keys:
            self._selected_key = self._rendered_keys[0]
            self._selection_anchor_key = self._selected_key
            row = self._row_for_key(self._selected_key)
            if row is not None:
                self._show_details(row)

        for key, card in self._cards_by_key.items():
            card.set_selected(key in self._selected_keys)

        self._update_selection_count()

    def clear_selection(self) -> None:
        self._selected_keys.clear()
        self._selected_key = None
        self._selection_anchor_key = None

        for card in self._cards_by_key.values():
            card.set_selected(False)

        self._clear_details()
        self._update_selection_count()

    def _update_selection_count(self) -> None:
        self.selection_count_label.setText(f"Selected: {len(self._selected_keys)}")

    def _selected_rows(self) -> List[AlbumReviewRow]:
        selected = []
        for key in self._selected_keys:
            row = self._row_for_key(key)
            if row is not None:
                selected.append(row)
        return selected

    def _selected_row(self) -> Optional[AlbumReviewRow]:
        if not self._selected_key:
            return None
        return self._row_for_key(self._selected_key)

    def _row_for_key(self, key: str) -> Optional[AlbumReviewRow]:
        for row in self._all_rows:
            if self._row_key(row) == key:
                return row
        return None

    def _row_key(self, row: AlbumReviewRow) -> str:
        return str(getattr(row.breakdown.photo, "path", ""))

    def _show_details(self, row: AlbumReviewRow, force: bool = False) -> None:
        key = self._row_key(row)
        if not force and self._details_key == key:
            return

        self._details_key = key
        photo = row.breakdown.photo
        breakdown = row.breakdown

        self.filename_value.setText(photo.display_name())
        self.score_value.setText(
            f"Total {breakdown.total_score:.2f} | "
            f"Technical {breakdown.technical_score:.2f} | "
            f"Memory {breakdown.memory_score:.2f} | "
            f"Date {breakdown.date_score:.2f}"
        )

        category_value = self._effective_category_for_photo(photo)
        self.media_category_value.setText(media_category_label(category_value))
        self.classification_reason_value.setText(str(getattr(photo, "classification_reason", "") or "-"))
        visual_parts = [
            str(photo.metadata.get("visual_signals_summary", "") or "").strip(),
            str(photo.metadata.get("visual_evidence", "") or "").strip(),
        ]
        self.visual_summary_value.setText(" | ".join(part for part in visual_parts if part) or "-")

        confidence = float(getattr(photo, "classification_confidence", 0.0) or 0.0)
        self.confidence_value.setText(f"{max(0, min(100, int(round(confidence * 100))))}%")
        self.user_decision_value.setText(row.user_decision.replace("_", " ").title())

        intelligence = getattr(photo, "intelligence", None)
        date_value = "-"
        date_source = "-"
        if intelligence is not None:
            if getattr(intelligence, "date_taken", None):
                date_value = str(intelligence.date_taken)
            if getattr(intelligence, "date_source", None):
                date_source = str(intelligence.date_source)
            elif getattr(intelligence, "source_of_date", None):
                date_source = str(intelligence.source_of_date)

        self.date_value.setText(date_value)
        self.date_source_value.setText(date_source)

        self.pipeline_value.setText(row.pipeline_state.title())
        self.rejection_reason_value.setText(row.rejection_reason or "-")

        self.explanations_list.clear()
        for explanation in breakdown.explanation or []:
            self.explanations_list.addItem(str(explanation))

        if not breakdown.explanation:
            self.explanations_list.addItem("No score explanation available.")

        preview = self._get_cached_preview(photo)
        if isinstance(preview, QPixmap) and not preview.isNull():
            self.preview_label.setPixmap(preview)
            self.preview_label.setText("")
        else:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("Preview unavailable")

        self._sync_selectors_to_row(row)

    def _clear_details(self) -> None:
        self._details_key = None
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("No preview")
        self.filename_value.setText("-")
        self.score_value.setText("-")
        self.media_category_value.setText("-")
        self.classification_reason_value.setText("-")
        self.visual_summary_value.setText("-")
        self.confidence_value.setText("-")
        self.user_decision_value.setText("-")
        self.date_value.setText("-")
        self.date_source_value.setText("-")
        self.pipeline_value.setText("-")
        self.rejection_reason_value.setText("-")
        self.explanations_list.clear()

    def _sync_selectors_to_row(self, row: AlbumReviewRow) -> None:
        self._decision_selector_syncing = True
        decision_index = self.decision_selector.findText(row.user_decision)
        self.decision_selector.setCurrentIndex(decision_index if decision_index >= 0 else 0)
        self._decision_selector_syncing = False

        category_value = self._effective_category_for_photo(row.breakdown.photo)
        self._category_selector_syncing = True
        category_index = self.category_selector.findData(category_value)
        self.category_selector.setCurrentIndex(category_index if category_index >= 0 else 0)
        self._category_selector_syncing = False

    def _on_decision_selector_changed(self, value: str) -> None:
        _ = value
        if self._decision_selector_syncing:
            return
        # Memory Review no longer exposes decision editing; hidden selector changes
        # must not write decisions implicitly.
        return

    def _on_category_selector_changed(self, _value: str) -> None:
        if self._category_selector_syncing:
            return
        # Do not apply immediately. User must press Apply Category to Selected.
        return

    def _apply_selector_decision(self) -> None:
        decision = self.decision_selector.currentText()
        rows = self._selected_rows()
        if not rows:
            return

        if not self._confirm_bulk_if_needed(len(rows), f"apply decision {decision}"):
            return

        self._apply_decision_to_rows(rows, decision, source="user_bulk")

    def _apply_selector_category(self) -> None:
        category = str(self.category_selector.currentData() or self.category_selector.currentText()).strip().lower()
        rows = self._selected_rows()
        if not rows or not category:
            return

        if not self._confirm_bulk_if_needed(len(rows), f"apply category {media_category_label(category)}"):
            return

        self._apply_category_to_rows(rows, category, source="user_bulk" if len(rows) > 1 else "user")

    def _confirm_bulk_if_needed(self, count: int, action_text: str) -> bool:
        if count <= 20:
            return True

        response = QMessageBox.question(
            self,
            "Confirm bulk change",
            f"You selected {count} photos.\n\nDo you want to {action_text}?",
        )
        return response == QMessageBox.StandardButton.Yes

    def _apply_decision_to_rows(self, rows: List[AlbumReviewRow], decision: str, source: str) -> None:
        for row in rows:
            previous = row.user_decision
            row.user_decision = str(decision)
            row.review_state = self._review_state_from_decision(row.user_decision)

            photo = row.breakdown.photo
            photo.user_decision = row.user_decision
            metadata = dict(getattr(photo, "metadata", {}) or {})
            metadata["user_decision"] = row.user_decision
            photo.metadata = metadata

            self._decision_history.record_decision_change(
                photo,
                previous_value=previous,
                new_value=row.user_decision,
                source=source,
            )
            self._preference_learning_engine.record_decision(
                photo,
                previous_decision=previous,
                new_decision=row.user_decision,
                source=source,
            )
            self._save_photo_user_metadata(photo)

            card = self._cards_by_key.get(self._row_key(row))
            if card is not None:
                card.refresh_from_row(thumbnail=self._get_cached_card_thumbnail(row))

        selected = self._selected_row()
        if selected is not None:
            self._show_details(selected, force=True)

        self._show_user_saved_indicator("User decision saved")
        self.review_state_changed.emit()
        self._trigger_refresh(force=True)

    def _apply_category_to_rows(self, rows: List[AlbumReviewRow], category: str, source: str) -> None:
        category = str(category or "").strip().lower()
        if not category:
            return

        affected_keys = [self._row_key(row) for row in rows]
        preferred_key = self._selected_key or (affected_keys[0] if affected_keys else None)
        previous_visible_keys = [self._row_key(row) for row in self._visible_rows]
        previous_scroll = self.grid_scroll.verticalScrollBar().value()
        previous_render_count = max(len(self._rendered_keys), self._initial_render_count)

        for row in rows:
            photo = row.breakdown.photo
            previous = self._effective_category_for_photo(photo)

            metadata = dict(getattr(photo, "metadata", {}) or {})
            automatic = str(metadata.get("automatic_media_category", "") or getattr(photo, "automatic_media_category", "") or previous).strip().lower()

            metadata["automatic_media_category"] = automatic
            metadata["user_corrected_media_category"] = category
            metadata["effective_media_category"] = category
            metadata["media_category"] = category
            metadata["classification_reason"] = metadata.get("classification_reason", "") or "User corrected category."
            photo.metadata = metadata

            photo.automatic_media_category = automatic
            photo.user_corrected_media_category = category
            photo.effective_media_category = category
            photo.media_category = category
            photo.classification_reason = str(metadata.get("classification_reason", "") or "")
            photo.sync_intelligence_from_metadata()

            self._decision_history.record_category_correction(
                photo,
                previous_value=previous,
                new_value=category,
                source=source,
            )
            self._category_learning_engine.record_category_correction(
                photo,
                previous_category=previous,
                corrected_category=category,
                source=source,
            )
            self._preference_learning_engine.record_category_correction(
                photo,
                previous_category=previous,
                corrected_category=category,
                source=source,
            )
            self._save_photo_user_metadata(photo)

            card = self._cards_by_key.get(self._row_key(row))
            if card is not None:
                card.refresh_from_row(thumbnail=self._get_cached_card_thumbnail(row))

        self._show_user_saved_indicator("User category saved")
        self.review_state_changed.emit()
        self._refresh_after_category_change(
            affected_keys=affected_keys,
            preferred_key=preferred_key,
            previous_visible_keys=previous_visible_keys,
            previous_scroll=previous_scroll,
            previous_render_count=previous_render_count,
        )

    def _refresh_after_category_change(
        self,
        affected_keys: list[str],
        preferred_key: Optional[str],
        previous_visible_keys: list[str],
        previous_scroll: int,
        previous_render_count: int,
    ) -> None:
        new_visible_rows = self._filtered_sorted_rows()
        new_visible_keys = [self._row_key(row) for row in new_visible_rows]

        if new_visible_keys == previous_visible_keys:
            self._visible_rows = new_visible_rows
            for key in affected_keys:
                row = self._row_for_key(key)
                card = self._cards_by_key.get(key)
                if row is not None and card is not None:
                    card.refresh_from_row(thumbnail=self._get_cached_card_thumbnail(row))
                    card.set_selected(key in self._selected_keys)
            selected = self._selected_row()
            if selected is not None:
                self._show_details(selected, force=True)
            self._restore_scroll_position(previous_scroll)
            self._update_selection_count()
            return

        selected_key = self._choose_selection_after_filter_change(
            preferred_key=preferred_key,
            previous_visible_keys=previous_visible_keys,
            new_visible_keys=new_visible_keys,
        )

        visible_key_set = set(new_visible_keys)
        self._selected_keys = {key for key in self._selected_keys if key in visible_key_set}
        if selected_key:
            self._selected_key = selected_key
            self._selected_keys = {selected_key}
            self._selection_anchor_key = selected_key
        else:
            self._selected_key = None
            self._selection_anchor_key = None

        self._visible_rows = new_visible_rows
        self._rebuild_grid_preserving_scroll(previous_scroll, previous_render_count)

        if selected_key:
            row = self._row_for_key(selected_key)
            if row is not None:
                self._show_details(row, force=True)
        else:
            self._clear_details()
        self._restore_scroll_position(previous_scroll)
        self._update_selection_count()

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

    def _rebuild_grid_preserving_scroll(self, scroll_value: int, render_count: int) -> None:
        self._clear_grid()
        self._cards_by_key = {}
        self._rendered_keys = []
        self._pending_render_index = 0
        self._target_render_count = min(max(self._initial_render_count, int(render_count or 0)), len(self._visible_rows))
        self._grid_columns = self._calculate_columns()
        self._grid_rebuild_count += 1
        self.results_label.setText(self._results_label_text())
        self._add_next_batch()
        self._restore_scroll_position(scroll_value)

    def _restore_scroll_position(self, value: int) -> None:
        scrollbar = self.grid_scroll.verticalScrollBar()
        target = max(0, int(value or 0))

        def apply_restore() -> None:
            self.grid_content.adjustSize()
            scrollbar.setValue(min(target, scrollbar.maximum()))

        apply_restore()
        QTimer.singleShot(0, apply_restore)
        QTimer.singleShot(50, apply_restore)
        QTimer.singleShot(100, apply_restore)

    def _show_user_saved_indicator(self, text: str) -> None:
        self.user_saved_label.setText(text)
        self.user_saved_label.setVisible(True)
        QTimer.singleShot(2500, lambda: self.user_saved_label.setVisible(False))

    def _save_photo_user_metadata(self, photo) -> None:
        try:
            self._user_metadata_service.save_photo_metadata(photo)
        except Exception:
            # Metadata persistence must not break review flow.
            pass

    def _ensure_category_fields(self, photo) -> None:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        automatic = str(
            metadata.get("automatic_media_category", "")
            or getattr(photo, "automatic_media_category", "")
            or metadata.get("media_category", "")
            or getattr(photo, "media_category", "")
            or MediaCategory.Unknown.value
        ).strip().lower()

        user_corrected = str(
            metadata.get("user_corrected_media_category", "")
            or getattr(photo, "user_corrected_media_category", "")
            or ""
        ).strip().lower()

        effective = user_corrected or automatic or MediaCategory.Unknown.value

        metadata["automatic_media_category"] = automatic
        metadata["user_corrected_media_category"] = user_corrected
        metadata["effective_media_category"] = effective
        metadata["media_category"] = effective

        photo.metadata = metadata
        photo.automatic_media_category = automatic
        photo.user_corrected_media_category = user_corrected
        photo.effective_media_category = effective
        photo.media_category = effective

        if not getattr(photo, "classification_reason", None):
            photo.classification_reason = str(metadata.get("classification_reason", "") or "")
        if not getattr(photo, "classification_confidence", None):
            photo.classification_confidence = float(metadata.get("classification_confidence", 0.0) or 0.0)

    def _effective_category_for_photo(self, photo) -> str:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        return str(
            metadata.get("effective_media_category", "")
            or getattr(photo, "effective_media_category", "")
            or metadata.get("user_corrected_media_category", "")
            or getattr(photo, "user_corrected_media_category", "")
            or metadata.get("automatic_media_category", "")
            or getattr(photo, "automatic_media_category", "")
            or metadata.get("media_category", "")
            or getattr(photo, "media_category", "")
            or MediaCategory.Unknown.value
        ).strip().lower()

    def _initial_user_decision_for_photo(self, photo) -> str:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        value = str(
            metadata.get("user_decision", "")
            or getattr(photo, "user_decision", "")
            or UserDecision.Pending.value
        ).strip()
        return value or UserDecision.Pending.value

    def _review_state_from_decision(self, decision: str) -> str:
        normalized = str(decision or "").strip().lower()
        if normalized == UserDecision.ApproveForAlbum.value:
            return "approved"
        if normalized in {
            UserDecision.Reject.value,
            UserDecision.IrrelevantMedia.value,
            UserDecision.Duplicate.value,
            UserDecision.Document.value,
            UserDecision.Screenshot.value,
            UserDecision.Advertisement.value,
            UserDecision.Meme.value,
        }:
            return "rejected"
        return "pending"

    def _photo_date_sort_value(self, photo) -> datetime:
        intelligence = getattr(photo, "intelligence", None)
        date_value = getattr(intelligence, "date_taken", None) if intelligence is not None else None
        if isinstance(date_value, datetime):
            return date_value

        if date_value:
            try:
                return datetime.fromisoformat(str(date_value).replace("Z", "+00:00"))
            except Exception:
                pass
            try:
                return datetime.strptime(str(date_value), "%Y:%m:%d %H:%M:%S")
            except Exception:
                pass

        return datetime.min

    def _get_cached_card_thumbnail(self, row: AlbumReviewRow) -> Optional[QPixmap]:
        photo = row.breakdown.photo
        file_path = str(getattr(photo, "path", "") or "")
        if not file_path:
            return None

        cache_key = self._thumbnail_cache_key(file_path, QSize(140, 140))
        cached = self._thumbnail_cache.get(cache_key)
        if cached is not None:
            return cached[1]

        pixmap = getattr(photo, "thumbnail", None)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self._thumbnail_source_by_key[file_path] = "photo_thumbnail"
        else:
            pixmap = None

        thumbnail_path = str(getattr(photo, "thumbnail_path", "") or "")
        if pixmap is None and thumbnail_path and Path(thumbnail_path).exists():
            pixmap = load_display_thumbnail(thumbnail_path, QSize(140, 140))
            if pixmap is not None and not pixmap.isNull():
                self._thumbnail_source_by_key[file_path] = "thumbnail_path"

        if pixmap is None and file_path and Path(file_path).exists():
            pixmap = load_display_thumbnail(file_path, QSize(140, 140))
            if pixmap is not None and not pixmap.isNull():
                self._thumbnail_source_by_key[file_path] = "original_scaled"

        if pixmap is not None and not pixmap.isNull():
            self._thumbnail_cache[cache_key] = (self._file_mtime(file_path), pixmap)
            return pixmap

        return None

    def update_thumbnail(self, photo, pixmap) -> None:
        key = str(getattr(photo, "path", "") or "")
        if not key:
            return

        self._thumbnail_cache = {
            cache_key: value for cache_key, value in self._thumbnail_cache.items() if not cache_key.startswith(f"{key}|")
        }

        for row in self._all_rows:
            if str(getattr(row.breakdown.photo, "path", "") or "") != key:
                continue
            if isinstance(pixmap, QPixmap) and not pixmap.isNull():
                row.breakdown.photo.thumbnail = pixmap
            card = self._cards_by_key.get(self._row_key(row))
            if card is not None:
                card.refresh_from_row(thumbnail=pixmap if isinstance(pixmap, QPixmap) and not pixmap.isNull() else None)
                card.update()
                card.repaint()
            if self._details_key == key:
                self._show_details(row, force=True)
            break

    def _get_cached_preview(self, photo) -> Optional[QPixmap]:
        file_path = str(getattr(photo, "path", "") or "")
        if not file_path:
            return None

        cache_key = self._thumbnail_cache_key(file_path, QSize(280, 160))
        cached = self._preview_cache.get(cache_key)
        if cached is not None:
            return cached[1]

        pixmap = load_display_thumbnail(file_path, QSize(280, 160))
        if pixmap is not None and not pixmap.isNull():
            self._preview_cache[cache_key] = (self._file_mtime(file_path), pixmap)
            return pixmap

        return None

    def _thumbnail_cache_key(self, file_path: str, size: QSize) -> str:
        return f"{file_path}|{size.width()}x{size.height()}|{self._file_mtime(file_path)}"

    def _file_mtime(self, file_path: str) -> int:
        try:
            return int(Path(file_path).stat().st_mtime)
        except Exception:
            return 0

    def visible_filenames(self) -> List[str]:
        return [row.breakdown.photo.display_name() for row in self._visible_rows]

    def select_photo_by_filename(self, filename: str) -> bool:
        for row in self._visible_rows:
            if row.breakdown.photo.display_name() == filename:
                self._select_key(self._row_key(row), additive=False, range_select=False)
                return True
        return False

    def selected_count(self) -> int:
        return len(self._selected_keys)

    def selected_file_paths(self) -> list[str]:
        return sorted(self._selected_keys)

    def grid_column_count(self) -> int:
        return int(self._grid_columns)

    def compact_card_size(self) -> tuple[int, int]:
        if not self._cards_by_key:
            return 0, 0
        card = next(iter(self._cards_by_key.values()))
        return card.width(), card.height()

    def card_summary_for_filename(self, filename: str) -> Optional[dict[str, str]]:
        for row in self._visible_rows:
            if row.breakdown.photo.display_name() != filename:
                continue
            card = self._cards_by_key.get(self._row_key(row))
            if card is None:
                return None
            self._get_cached_card_thumbnail(row)
            return {
                "score": card.score_badge.text(),
                "category": card.category_label.text(),
                "confidence": card.confidence_label.text(),
                "decision": card.decision_label.text(),
            }
        return None

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

    def thumbnail_source_for_filename(self, filename: str) -> str:
        for row in self._all_rows:
            photo = row.breakdown.photo
            if photo.display_name() == filename:
                return self._thumbnail_source_by_key.get(str(getattr(photo, "path", "") or ""), "")
        return ""

    def set_selected_decision(self, decision: str) -> None:
        selected = self._selected_row()
        if selected is None:
            return
        self._apply_decision_to_rows([selected], decision, source="user")

    def approve_selected(self) -> None:
        self.set_selected_decision(UserDecision.ApproveForAlbum.value)

    def reject_selected(self) -> None:
        self.set_selected_decision(UserDecision.Reject.value)

    def reset_selected(self) -> None:
        self.set_selected_decision(UserDecision.Pending.value)

    def decision_for_filename(self, filename: str) -> str:
        for row in self._all_rows:
            if row.breakdown.photo.display_name() == filename:
                return row.user_decision
        return ""

    def review_state_for_filename(self, filename: str) -> str:
        for row in self._all_rows:
            if row.breakdown.photo.display_name() == filename:
                return row.review_state
        return ""

    def decision_history_entries(self):
        return list(self._decision_history.entries)

    def learning_events(self):
        return self.decision_history_entries()

    def rendered_card_count(self) -> int:
        return len(self._cards_by_key)

    def grid_rebuild_count(self) -> int:
        return int(self._grid_rebuild_count)

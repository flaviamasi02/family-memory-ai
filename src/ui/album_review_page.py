from __future__ import annotations

import os
import time
from html import escape
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QEvent, QTimer, Qt, QSize, Signal
from PySide6.QtGui import QFontMetrics, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QFormLayout,
    QGridLayout,
    QGroupBox,
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
from core.category_suggestion_service import CategorySuggestionService
from core.media_classifier import (
    DecisionHistory,
    MediaCategory,
    MediaClassifier,
    UserDecision,
    media_category_label,
    ordered_media_category_values,
)
from core.image_display_loader import load_display_pixmap, load_display_thumbnail
from core.memory_review_perf import (
    increment_memory_review_counter,
    measure_memory_review,
    record_memory_review,
)
from core.selection_update import changed_selection_keys
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
from vision.managed_mobileclip_provider import ManagedMobileCLIPEmbeddingProvider


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

    def __init__(
        self,
        row: AlbumReviewRow,
        key: str,
        thumbnail: Optional[QPixmap] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.row = row
        self.key = key
        self._selected: Optional[bool] = None

        self.setObjectName("albumReviewCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedWidth(164)
        self.setFixedHeight(228)

        self.thumbnail_label = QLabel("No thumbnail")
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setFixedSize(140, 140)
        self.thumbnail_label.setStyleSheet(
            "border: 1px solid #bbb; background: #f6f6f6;"
        )

        self.filename_label = QLabel("")
        self.filename_label.setWordWrap(False)
        self.filename_label.setStyleSheet("font-weight: 600;")
        self.filename_label.setFixedWidth(148)
        self.filename_label.setMaximumHeight(20)

        self.score_badge = QLabel("")
        self.category_badge = QLabel("")
        self.decision_badge = QLabel("")
        for badge in (self.score_badge, self.category_badge, self.decision_badge):
            badge.setStyleSheet(
                "background: palette(alternate-base); border: 1px solid palette(mid); "
                "border-radius: 6px; padding: 2px 5px;"
            )
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

        pixmap = (
            thumbnail
            if isinstance(thumbnail, QPixmap)
            else getattr(photo, "thumbnail", None)
        )
        if isinstance(pixmap, QPixmap):
            self.thumbnail_label.setPixmap(pixmap)
            self.thumbnail_label.setText("")
        else:
            self.thumbnail_label.setPixmap(QPixmap())
            self.thumbnail_label.setText("No thumbnail")

        full_name = photo.display_name()
        self.filename_label.setToolTip(full_name)
        metrics = QFontMetrics(self.filename_label.font())
        self.filename_label.setText(
            metrics.elidedText(
                full_name, Qt.TextElideMode.ElideRight, self.filename_label.width()
            )
        )

        confidence = float(getattr(photo, "classification_confidence", 0.0) or 0.0)
        category_value = str(
            getattr(photo, "effective_media_category", "")
            or getattr(photo, "media_category", "unknown")
            or "unknown"
        )
        category_text = media_category_label(category_value)
        decision_text = self.row.user_decision.replace("_", " ").title()
        self.score_badge.setText(f"S {breakdown.total_score:.0f}")
        short_category = (
            category_text if len(category_text) <= 10 else category_text[:9] + ".."
        )
        short_decision = (
            decision_text if len(decision_text) <= 10 else decision_text[:9] + ".."
        )
        self.category_badge.setText(short_category)
        self.decision_badge.setText(short_decision)
        self.category_label.setText(f"Category: {category_text}")
        self.confidence_label.setText(
            f"Confidence: {max(0, min(100, int(round(confidence * 100))))}%"
        )
        self.decision_label.setText(f"Decision: {decision_text}")

        state_text = self.row.review_state.capitalize()
        pipeline_text = self.row.pipeline_state.capitalize()
        if self.row.rejection_reason:
            self.pipeline_label.setText(
                f"Review: {state_text} | Pipeline: {pipeline_text} ({self.row.rejection_reason})"
            )
        else:
            self.pipeline_label.setText(
                f"Review: {state_text} | Pipeline: {pipeline_text}"
            )

    def set_selected(self, selected: bool) -> None:
        selected = bool(selected)
        if self._selected == selected:
            return
        self._selected = selected
        if self._selected:
            self.setStyleSheet(
                "QFrame#albumReviewCard { border: 3px solid palette(highlight); "
                "border-radius: 6px; background: palette(alternate-base); }"
            )
        else:
            self.setStyleSheet(
                "QFrame#albumReviewCard { border: 1px solid palette(mid); "
                "border-radius: 6px; background: palette(base); }"
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
        self._retained_thumbnail_by_key: Dict[str, QPixmap] = {}
        self._thumbnail_source_by_key: Dict[str, str] = {}
        self._preview_cache: Dict[str, tuple[int, QPixmap]] = {}
        self._empty_reason_text: str = ""
        self._last_view_signature: Optional[tuple[str, str, str]] = None
        self._last_visible_key_order: List[str] = []
        self._visible_index_by_key: Dict[str, int] = {}
        self._rows_by_key: Dict[str, AlbumReviewRow] = {}
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
        self._category_suggestion_service = CategorySuggestionService(
            category_registry=self._category_registry,
            media_classifier=self._media_classifier,
        )
        self._suggestion_request_id = 0
        self._current_suggestion = None
        self._selection_generation = 0
        self._pending_details_key: Optional[str] = None
        self._details_timer = QTimer(self)
        self._details_timer.setSingleShot(True)
        self._details_timer.timeout.connect(self._complete_deferred_selection)
        self._suggestion_timer = QTimer(self)
        self._suggestion_timer.setSingleShot(True)
        self._suggestion_timer.setInterval(120)
        self._suggestion_timer.timeout.connect(self._compute_pending_suggestion)
        self._pending_suggestion_row: Optional[AlbumReviewRow] = None
        self._suggestion_metadata = ManagedMobileCLIPEmbeddingProvider().metadata

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
        # Review benefits from vertical working space; guidance remains one click away.
        self.info_panel.set_expanded(False)

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

        self.selection_count_label = QLabel("Selected: 0")
        self.selection_count_label.setStyleSheet("font-weight: 600;")
        self.user_saved_label = QLabel("")
        self.user_saved_label.setStyleSheet(
            "font-size: 12px; color: palette(highlight);"
        )
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
        self.reclassify_unknowns_button.clicked.connect(
            self.reclassify_unknowns_from_learning
        )

        filters_group = QGroupBox("Filters")
        filters_layout = QHBoxLayout(filters_group)
        filters_layout.setContentsMargins(6, 2, 6, 4)
        filters_layout.setSpacing(6)
        filters_layout.addWidget(QLabel("Decision:"))
        filters_layout.addWidget(self.filter_combo)
        filters_layout.addWidget(QLabel("Category:"))
        filters_layout.addWidget(self.category_filter_combo)
        filters_layout.addWidget(QLabel("Sort:"))
        filters_layout.addWidget(self.sort_combo)
        filters_layout.addWidget(QLabel("Search:"))
        filters_layout.addWidget(self.search_input, 1)

        tools_group = QGroupBox("Selection and tools")
        tools_layout = QHBoxLayout(tools_group)
        tools_layout.setContentsMargins(6, 2, 6, 4)
        tools_layout.setSpacing(6)
        tools_layout.addWidget(self.selection_count_label)
        tools_layout.addWidget(self.user_saved_label)
        tools_layout.addStretch(1)
        tools_layout.addWidget(self.manage_categories_button)
        tools_layout.addWidget(self.learning_summary_button)
        tools_layout.addWidget(self.reclassify_unknowns_button)
        tools_layout.addWidget(self.select_all_visible_button)
        tools_layout.addWidget(self.clear_selection_button)

        toolbar_layout = QVBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(2)
        toolbar_layout.addWidget(filters_group)
        toolbar_layout.addWidget(tools_group)

        self.results_label = QLabel("Showing 0 photos")

        self.grid_scroll = QScrollArea(self)
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.grid_content = QWidget(self.grid_scroll)
        self.grid_content.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.grid_layout = QGridLayout(self.grid_content)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(10)
        self.grid_scroll.setWidget(self.grid_content)
        self.grid_scroll.viewport().installEventFilter(self)
        self.grid_scroll.verticalScrollBar().valueChanged.connect(
            self._on_scroll_value_changed
        )

        self.preview_label = QLabel("No preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumWidth(300)
        self.preview_label.setMinimumHeight(165)
        self.preview_label.setMaximumHeight(190)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.preview_label.setStyleSheet("background: palette(window);")

        self.filename_value = QLabel("-")
        self.score_value = QLabel("-")
        self.score_value.setWordWrap(True)
        self.pipeline_value = QLabel("-")
        self.rejection_reason_value = QLabel("-")
        self.media_category_value = QLabel("-")
        self.media_category_value.setStyleSheet("font-weight: 700;")
        self.category_source_value = QLabel("-")
        self.classification_reason_value = QLabel("-")
        self.classification_reason_value.setWordWrap(True)
        self.visual_summary_value = QLabel("-")
        self.visual_summary_value.setWordWrap(True)
        self.confidence_value = QLabel("-")
        self.user_decision_value = QLabel("-")
        self.date_value = QLabel("-")
        self.date_source_value = QLabel("-")
        self.classification_summary_value = QLabel(
            "Select a photo to see why its current category is shown."
        )
        self.classification_summary_value.setWordWrap(True)

        self.ai_suggestion_value = QLabel(
            "Select one photo to check for an advisory suggestion."
        )
        self.ai_suggestion_value.setWordWrap(True)
        self.ai_suggestion_reasons = QLabel("")
        self.ai_suggestion_reasons.setWordWrap(True)
        self.ai_suggestion_reasons.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.ai_suggestion_reasons.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ai_suggestion_reasons.setVisible(False)
        self.apply_suggestion_button = QPushButton("Apply suggestion")
        self.apply_suggestion_button.clicked.connect(self._apply_current_suggestion)
        self.reject_suggestion_button = QPushButton("Reject / Not useful")
        self.reject_suggestion_button.clicked.connect(self._reject_current_suggestion)
        self.apply_suggestion_button.setEnabled(False)
        self.reject_suggestion_button.setEnabled(False)

        self.decision_selector = QComboBox()
        for decision in UserDecision:
            self.decision_selector.addItem(decision.value)
        self.decision_selector.currentTextChanged.connect(
            self._on_decision_selector_changed
        )
        self.category_selector = QComboBox()
        self.category_selector.currentTextChanged.connect(
            self._on_category_selector_changed
        )
        self.apply_decision_button = QPushButton("Apply Decision to Selected")
        self.apply_decision_button.clicked.connect(self._apply_selector_decision)
        self.apply_category_button = QPushButton("Apply Category to Selected")
        self.apply_category_button.setDefault(True)
        self.apply_category_button.clicked.connect(self._apply_selector_category)
        self.action_scope_label = QLabel(
            "Select one or more photos to apply a category."
        )
        self.action_scope_label.setWordWrap(True)
        self.decision_action_label = QLabel("Decision:")
        self.decision_action_label.setVisible(False)
        self.decision_selector.setVisible(False)
        self.apply_decision_button.setVisible(False)

        self.preview_section = QGroupBox("Preview")
        preview_layout = QVBoxLayout(self.preview_section)
        preview_layout.setContentsMargins(2, 2, 2, 2)
        preview_layout.addWidget(self.preview_label)

        self.current_status_section = QGroupBox("Current Status")
        status_layout = QVBoxLayout(self.current_status_section)
        status_layout.setContentsMargins(6, 4, 6, 4)
        status_layout.setSpacing(1)
        self.current_category_label = QLabel("Category")
        self.category_source_label = QLabel("Source")
        self.user_decision_label = QLabel("Decision")
        for label in (
            self.current_category_label,
            self.category_source_label,
            self.user_decision_label,
        ):
            label.setStyleSheet("font-size: 11px;")
        self.media_category_value.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.category_source_value.setStyleSheet("font-weight: 600;")
        self.user_decision_value.setStyleSheet("font-weight: 600;")
        status_layout.addWidget(self.current_category_label)
        status_layout.addWidget(self.media_category_value)
        status_layout.addSpacing(3)
        status_layout.addWidget(self.category_source_label)
        status_layout.addWidget(self.category_source_value)
        status_layout.addSpacing(3)
        status_layout.addWidget(self.user_decision_label)
        status_layout.addWidget(self.user_decision_value)
        status_layout.addStretch(1)

        self.preview_status_row = QWidget()
        preview_status_layout = QHBoxLayout(self.preview_status_row)
        preview_status_layout.setContentsMargins(0, 0, 0, 0)
        preview_status_layout.setSpacing(4)
        preview_status_layout.addWidget(self.preview_section, 3)
        preview_status_layout.addWidget(
            self.current_status_section, 2, Qt.AlignmentFlag.AlignTop
        )

        self.ai_suggestion_section = QGroupBox("AI Suggestion")
        suggestion_layout = QVBoxLayout(self.ai_suggestion_section)
        suggestion_layout.setContentsMargins(5, 3, 5, 4)
        suggestion_layout.setSpacing(2)
        suggestion_layout.addWidget(self.ai_suggestion_value)
        suggestion_layout.addWidget(self.ai_suggestion_reasons)
        suggestion_actions = QHBoxLayout()
        suggestion_actions.addWidget(self.apply_suggestion_button)
        suggestion_actions.addWidget(self.reject_suggestion_button)
        suggestion_actions.addStretch(1)
        suggestion_layout.addLayout(suggestion_actions)

        self.classification_summary_section = QGroupBox("Classification Summary")
        summary_layout = QVBoxLayout(self.classification_summary_section)
        summary_layout.setContentsMargins(5, 3, 5, 4)
        summary_layout.addWidget(self.classification_summary_value)

        self.photo_information_section = QGroupBox("Photo Information")
        information_form = QFormLayout(self.photo_information_section)
        information_form.setContentsMargins(5, 3, 5, 4)
        information_form.addRow("Filename:", self.filename_value)
        information_form.addRow("Date:", self.date_value)
        information_form.addRow("Date source:", self.date_source_value)
        information_form.addRow("Scores:", self.score_value)
        self.photo_information_section.setCheckable(True)
        self.photo_information_section.setChecked(False)
        self.photo_information_section.toggled.connect(
            lambda checked: self.photo_information_section.setMaximumHeight(
                16777215 if checked else 28
            )
        )
        self.photo_information_section.setMaximumHeight(28)

        self.explanations_list = QListWidget()
        self.explanations_list.setMinimumHeight(90)
        self.diagnostics_section = QGroupBox("Technical details")
        self.diagnostics_section.setCheckable(True)
        self.diagnostics_section.setChecked(False)
        diagnostics_form = QFormLayout(self.diagnostics_section)
        diagnostics_form.addRow("Import reason:", self.classification_reason_value)
        diagnostics_form.addRow("Visual signals:", self.visual_summary_value)
        diagnostics_form.addRow("Confidence:", self.confidence_value)
        diagnostics_form.addRow("Pipeline:", self.pipeline_value)
        diagnostics_form.addRow("Rejection reason:", self.rejection_reason_value)
        diagnostics_form.addRow("Score explanation:", self.explanations_list)
        self.diagnostics_section.toggled.connect(
            lambda checked: self.diagnostics_section.setMaximumHeight(
                16777215 if checked else 28
            )
        )
        self.diagnostics_section.setMaximumHeight(28)

        self.actions_section = QGroupBox("Actions")
        actions_layout = QVBoxLayout(self.actions_section)
        actions_layout.setContentsMargins(5, 3, 5, 4)
        actions_layout.setSpacing(2)
        actions_layout.addWidget(self.action_scope_label)
        category_actions = QHBoxLayout()
        category_actions.setSpacing(4)
        category_action_label = QLabel("Category")
        category_action_label.setStyleSheet("font-size: 11px;")
        category_actions.addWidget(category_action_label)
        self.category_selector.setMinimumWidth(180)
        category_actions.addWidget(self.category_selector, 1)
        category_actions.addWidget(self.apply_category_button)
        actions_layout.addLayout(category_actions)

        details_content = QWidget()
        self.details_layout = QVBoxLayout(details_content)
        self.details_layout.setContentsMargins(2, 2, 2, 2)
        self.details_layout.setSpacing(3)
        self.details_layout.addWidget(self.preview_status_row)
        self.details_layout.addWidget(self.ai_suggestion_section)
        self.details_layout.addWidget(self.classification_summary_section)
        self.details_layout.addWidget(self.actions_section)
        self.details_layout.addWidget(self.photo_information_section)
        self.details_layout.addWidget(self.diagnostics_section)
        self.details_layout.addStretch(1)

        for section in (
            self.current_status_section,
            self.ai_suggestion_section,
            self.classification_summary_section,
            self.actions_section,
        ):
            section.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
            )

        self.details_scroll = QScrollArea()
        self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.details_scroll.setWidget(details_content)
        self.details_scroll.setMinimumWidth(430)
        self.details_scroll.viewport().installEventFilter(self)

        grid_panel = QWidget()
        grid_panel.setMinimumWidth(430)
        grid_layout = QVBoxLayout(grid_panel)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(4)
        grid_layout.addWidget(self.results_label)
        grid_layout.addWidget(self.grid_scroll, 1)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(grid_panel)
        self.main_splitter.addWidget(self.details_scroll)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([700, 700])

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 3, 6, 5)
        root_layout.setSpacing(2)
        root_layout.addWidget(self.header)
        root_layout.addWidget(self.info_panel)
        root_layout.addLayout(toolbar_layout)
        root_layout.addWidget(self.main_splitter, 1)

        self._reload_category_controls()

    def _on_help_clicked(self) -> None:
        self.help_requested.emit(self.WORKSPACE_ID)

    def _reload_category_controls(self) -> None:
        current_filter = (
            self.category_filter_combo.currentText().strip() or self.CATEGORY_FILTER_ALL
        )
        self.category_filter_combo.blockSignals(True)
        self.category_filter_combo.clear()
        self.category_filter_combo.addItem(self.CATEGORY_FILTER_ALL)
        for category_value in ordered_media_category_values():
            self.category_filter_combo.addItem(
                media_category_label(category_value), category_value
            )
        filter_index = self.category_filter_combo.findText(current_filter)
        self.category_filter_combo.setCurrentIndex(
            filter_index if filter_index >= 0 else 0
        )
        self.category_filter_combo.blockSignals(False)

        current_category_id = str(self.category_selector.currentData() or "").strip()
        self.category_selector.blockSignals(True)
        self.category_selector.clear()
        for category_value in ordered_media_category_values():
            self.category_selector.addItem(
                media_category_label(category_value), category_value
            )
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

            user_corrected = (
                str(
                    metadata.get("user_corrected_media_category", "")
                    or getattr(photo, "user_corrected_media_category", "")
                    or ""
                )
                .strip()
                .lower()
            )

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

    def _reassign_deleted_category(
        self, old_category_id: str, new_category_id: str
    ) -> None:
        old_id = str(old_category_id or "").strip().lower()
        new_id = str(new_category_id or "").strip().lower()
        if not old_id or not new_id or old_id == new_id:
            return

        for row in self._all_rows:
            photo = row.breakdown.photo
            metadata = dict(getattr(photo, "metadata", {}) or {})

            corrected = (
                str(
                    metadata.get("user_corrected_media_category", "")
                    or getattr(photo, "user_corrected_media_category", "")
                    or ""
                )
                .strip()
                .lower()
            )
            effective = (
                str(
                    metadata.get("effective_media_category", "")
                    or getattr(photo, "effective_media_category", "")
                    or ""
                )
                .strip()
                .lower()
            )
            automatic = (
                str(
                    metadata.get("automatic_media_category", "")
                    or getattr(photo, "automatic_media_category", "")
                    or ""
                )
                .strip()
                .lower()
            )

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
        self._empty_reason_text = ""
        for item in scored_photos:
            self._ensure_category_fields(item.photo)

        self._all_rows = [
            AlbumReviewRow(
                breakdown=item,
                review_state=self._review_state_from_decision(
                    self._initial_user_decision_for_photo(item.photo)
                ),
                user_decision=self._initial_user_decision_for_photo(item.photo),
                pipeline_state="selected",
                rejection_reason=None,
            )
            for item in scored_photos
        ]
        self._rows_by_key = {self._row_key(row): row for row in self._all_rows}
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
        self._empty_reason_text = ""
        self._candidate_count = len(candidate_photos or [])
        self._rejection_reasons_summary = dict(rejection_reasons or {})
        selected_keys = {
            str(getattr(photo, "path", "")) for photo in selected_photos or []
        }
        rejected_keys = {
            str(getattr(photo, "path", "")) for photo in rejected_photos or []
        }

        rows: List[AlbumReviewRow] = []
        for photo in imported_photos or []:
            self._ensure_category_fields(photo)
            key = str(getattr(photo, "path", ""))
            breakdown = scored_breakdowns.get(key)
            if breakdown is None:
                inferred_total = 0.0
                intelligence = getattr(photo, "intelligence", None)
                if (
                    intelligence is not None
                    and intelligence.album_candidate_score is not None
                ):
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
                    rejection_reason = getattr(
                        intelligence, "album_rejection_reason", None
                    )

            rows.append(
                AlbumReviewRow(
                    breakdown=breakdown,
                    review_state=self._review_state_from_decision(
                        self._initial_user_decision_for_photo(photo)
                    ),
                    user_decision=self._initial_user_decision_for_photo(photo),
                    pipeline_state=pipeline_state,
                    rejection_reason=rejection_reason,
                )
            )

        had_rows = bool(self._all_rows)
        self._all_rows = rows
        self._rows_by_key = {self._row_key(row): row for row in rows}
        if not had_rows:
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

        previous_signature = self._last_view_signature
        self._last_view_signature = view_signature
        previous_scroll = self.grid_scroll.verticalScrollBar().value()
        previous_keys = [self._row_key(row) for row in self._visible_rows]

        operation = "Sort update" if previous_signature and previous_signature[:2] == view_signature[:2] and previous_signature[3] == view_signature[3] else "Filter update"
        with measure_memory_review(operation, items=len(self._all_rows)):
            self._visible_rows = self._filtered_sorted_rows()
        self._index_visible_rows()

        self._selected_keys = {
            key
            for key in self._selected_keys
            if key in {self._row_key(row) for row in self._visible_rows}
        }
        if self._selected_key not in {self._row_key(row) for row in self._visible_rows}:
            self._selected_key = None

        new_keys = [self._row_key(row) for row in self._visible_rows]
        # Sorting does not invalidate cards or thumbnails: only move the already
        # rendered widgets. This is the common expensive rebuild found by PERF-003.
        if set(new_keys) == set(previous_keys) and self._cards_by_key:
            self._rendered_keys = [key for key in new_keys if key in self._cards_by_key]
            with measure_memory_review("Grid creation", items=len(self._rendered_keys)):
                self._relayout_existing_cards(self._calculate_columns())
            increment_memory_review_counter("grid_rebuilds_avoided")
            self.results_label.setText(self._results_label_text())
            self._restore_scroll_position(previous_scroll)
            self._update_selection_count()
            return

        self._clear_grid()
        self._cards_by_key = {}
        self._rendered_keys = []
        self._pending_render_index = 0
        self._target_render_count = min(
            self._initial_render_count, len(self._visible_rows)
        )
        self._grid_columns = self._calculate_columns()
        self._grid_rebuild_count += 1

        self.results_label.setText(self._results_label_text())

        with measure_memory_review("Grid creation", items=self._target_render_count):
            self._add_next_batch()
        increment_memory_review_counter("grid_rebuilds")
        self._restore_scroll_position(previous_scroll)

        if self._visible_rows and self._selected_key is None:
            first_key = self._row_key(self._visible_rows[0])
            self._select_key(first_key, additive=False, range_select=False)

        self._update_selection_count()

    def _index_visible_rows(self) -> None:
        self._last_visible_key_order = [
            self._row_key(row) for row in self._visible_rows
        ]
        self._visible_index_by_key = {
            key: index for index, key in enumerate(self._last_visible_key_order)
        }

    def _results_label_text(self) -> str:
        if not self._all_rows and self._empty_reason_text:
            return self._empty_reason_text

        if self._candidate_count or self._rejection_reasons_summary:
            selected = sum(
                1 for row in self._all_rows if row.pipeline_state == "selected"
            )
            rejected = sum(
                1 for row in self._all_rows if row.pipeline_state == "rejected"
            )
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
                row
                for row in rows
                if self._effective_category_for_photo(row.breakdown.photo) == wanted
            ]

        search_text = self.search_input.text().strip().lower()
        if search_text:
            rows = [
                row
                for row in rows
                if search_text in row.breakdown.photo.display_name().lower()
            ]

        sort_mode = self.sort_combo.currentText()
        if sort_mode == self.SORT_LOWEST:
            rows.sort(
                key=lambda row: (
                    row.breakdown.total_score,
                    self._photo_date_sort_value(row.breakdown.photo),
                )
            )
        elif sort_mode == self.SORT_DATE:
            rows.sort(
                key=lambda row: (
                    self._photo_date_sort_value(row.breakdown.photo),
                    row.breakdown.total_score,
                ),
                reverse=True,
            )
        else:
            rows.sort(
                key=lambda row: (
                    -row.breakdown.total_score,
                    self._photo_date_sort_value(row.breakdown.photo),
                )
            )

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
            max(
                self._target_render_count,
                self._pending_render_index + self._render_batch_size,
            ),
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
        if (
            grid_scroll is not None
            and watched is grid_scroll.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            new_columns = self._calculate_columns()
            if new_columns != self._grid_columns:
                self._relayout_existing_cards(new_columns)

        details_scroll = getattr(self, "details_scroll", None)
        if (
            details_scroll is not None
            and watched is details_scroll.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self._refresh_selected_preview()
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

    def _select_key(
        self, key: str, additive: bool = False, range_select: bool = False
    ) -> None:
        started = time.perf_counter()
        visible_keys = self._last_visible_key_order
        if key not in self._visible_index_by_key:
            return

        previous_keys = set(self._selected_keys)
        operation = "Single selection"

        if range_select and self._selection_anchor_key in self._visible_index_by_key:
            operation = "Shift range selection"
            start = self._visible_index_by_key[self._selection_anchor_key]
            end = self._visible_index_by_key[key]
            if start > end:
                start, end = end, start
            if not additive:
                self._selected_keys.clear()
            self._selected_keys.update(visible_keys[start : end + 1])
        elif additive:
            if key in self._selected_keys:
                operation = "Deselection"
                self._selected_keys.remove(key)
            else:
                operation = "Ctrl-click selection"
                self._selected_keys.add(key)
            self._selection_anchor_key = key
        else:
            self._selected_keys = {key}
            self._selection_anchor_key = key

        self._selected_key = key
        self._apply_selection_ui(previous_keys, active_key=key)
        elapsed = (time.perf_counter() - started) * 1000.0
        record_memory_review(operation, elapsed, items=len(self._selected_keys))
        record_memory_review("Selection update", elapsed, items=len(self._selected_keys))
        increment_memory_review_counter("selection_updates")
        increment_memory_review_counter("selection_signal_emissions")

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
        started = time.perf_counter()
        previous_keys = set(self._selected_keys)
        rendered_keys = set(self._rendered_keys)
        self._selected_keys = rendered_keys
        if self._rendered_keys:
            self._selected_key = self._rendered_keys[0]
            self._selection_anchor_key = self._selected_key
        self._apply_selection_ui(previous_keys, active_key=self._selected_key)
        record_memory_review(
            "Select all visible", (time.perf_counter() - started) * 1000.0,
            items=len(self._selected_keys),
        )
        increment_memory_review_counter("selection_signal_emissions")

    def clear_selection(self) -> None:
        started = time.perf_counter()
        previous_keys = set(self._selected_keys)
        self._selected_keys.clear()
        self._selected_key = None
        self._selection_anchor_key = None

        self._apply_selection_ui(previous_keys, active_key=None)
        record_memory_review(
            "Clear selection", (time.perf_counter() - started) * 1000.0,
            items=len(previous_keys),
        )
        increment_memory_review_counter("selection_signal_emissions")

    def _apply_selection_ui(
        self, previous_keys: set[str], *, active_key: Optional[str]
    ) -> None:
        """Apply one selection transaction and touch changed cards only."""
        changed_keys = changed_selection_keys(previous_keys, self._selected_keys)
        highlight_started = time.perf_counter()
        for changed_key in changed_keys:
            card = self._cards_by_key.get(changed_key)
            if card is not None:
                card.set_selected(changed_key in self._selected_keys)
        record_memory_review(
            "Selection highlight update",
            (time.perf_counter() - highlight_started) * 1000.0,
            items=len(changed_keys),
        )
        increment_memory_review_counter("selection_cards_updated", len(changed_keys))
        increment_memory_review_counter("selection_rows_scanned", 0)
        increment_memory_review_counter("selection_viewport_updates", len(changed_keys))
        increment_memory_review_counter("selection_layout_activations", 0)

        count_started = time.perf_counter()
        self._update_selection_count()
        record_memory_review(
            "Selected-count label update",
            (time.perf_counter() - count_started) * 1000.0,
            items=len(self._selected_keys),
        )
        increment_memory_review_counter("selected_count_updates")

        # Match the responsive grid architecture: return after the minimal
        # selection transaction so Qt can paint highlights. One replaceable
        # zero-delay callback owns all secondary details for the final key.
        self._selection_generation += 1
        self._pending_details_key = active_key
        self._details_timer.setProperty("generation", self._selection_generation)
        self._details_timer.start(0)
        record_memory_review(
            "Selection highlight visible",
            (time.perf_counter() - highlight_started) * 1000.0,
            items=len(changed_keys),
        )

    def _complete_deferred_selection(self) -> None:
        started = time.perf_counter()
        generation = int(self._details_timer.property("generation") or 0)
        key = self._pending_details_key
        self._pending_details_key = None
        if generation != self._selection_generation:
            increment_memory_review_counter("stale_detail_refreshes_ignored")
            return
        if key is None:
            self._suggestion_request_id += 1
            self._suggestion_timer.stop()
            self._pending_suggestion_row = None
            self._clear_details()
        elif key == self._selected_key:
            row = self._row_for_key(key)
            if row is not None:
                self._show_details(row)
        increment_memory_review_counter("selection_details_refreshes")
        record_memory_review(
            "Selection deferred completion",
            (time.perf_counter() - started) * 1000.0,
            items=1 if key else 0,
        )

    def _update_selection_count(self) -> None:
        count = len(self._selected_keys)
        self.selection_count_label.setText(f"Selected: {count}")
        if count == 0:
            scope = "Select one or more photos to apply a category."
        elif count == 1:
            scope = "The category action affects 1 selected photo."
        else:
            scope = f"The category action affects {count} selected photos."
        self.action_scope_label.setText(scope)

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
        return self._rows_by_key.get(key)

    def _row_key(self, row: AlbumReviewRow) -> str:
        return self._photo_key(row.breakdown.photo)

    def _normalize_photo_key_from_path(self, file_path: str) -> str:
        raw = str(file_path or "").strip()
        if not raw:
            return ""

        normalized = os.path.normpath(raw)
        return normalized

    def _photo_key(self, photo) -> str:
        return self._normalize_photo_key_from_path(
            str(getattr(photo, "path", "") or "")
        )

    def _show_details(self, row: AlbumReviewRow, force: bool = False) -> None:
        key = self._row_key(row)
        if not force and self._details_key == key:
            return

        self._details_key = key
        detail_started = time.perf_counter()
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
        metadata = dict(getattr(photo, "metadata", {}) or {})
        user_category = str(
            metadata.get("user_corrected_media_category", "") or ""
        ).strip()
        if user_category:
            source = str(metadata.get("category_confirmation_source", "") or "")
            if (
                metadata.get("category_suggestion_state") == "accepted"
                or source == "ai_suggestion_accepted"
            ):
                self.category_source_value.setText("Accepted AI suggestion")
            else:
                self.category_source_value.setText("Manual correction")
        elif category_value == MediaCategory.Unknown.value:
            self.category_source_value.setText("Unconfirmed")
        else:
            self.category_source_value.setText("Deterministic classification")
        self.classification_reason_value.setText(
            str(getattr(photo, "classification_reason", "") or "-")
        )
        if user_category:
            support_count = int(
                metadata.get("category_suggestion_support_count", 0) or 0
            )
            if self.category_source_value.text() == "Accepted AI suggestion":
                evidence = (
                    f" because it is visually similar to {support_count} confirmed "
                    f"{media_category_label(category_value)} photos"
                    if support_count
                    else " from an advisory AI suggestion"
                )
                summary = f"This photo was accepted as {media_category_label(category_value)}{evidence}."
            else:
                summary = "This category was selected manually."
        elif category_value == MediaCategory.Unknown.value:
            summary = (
                "No category has been confirmed yet. The app is waiting for stronger "
                "semantic evidence or a manual decision."
            )
        else:
            summary = (
                f"The current {media_category_label(category_value)} category comes from "
                "reliable import-time classification rules."
            )
        self.classification_summary_value.setText(summary)
        visual_parts = [
            str(photo.metadata.get("visual_signals_summary", "") or "").strip(),
            str(photo.metadata.get("visual_evidence", "") or "").strip(),
        ]
        self.visual_summary_value.setText(
            " | ".join(part for part in visual_parts if part) or "-"
        )

        confidence = float(getattr(photo, "classification_confidence", 0.0) or 0.0)
        self.confidence_value.setText(
            f"{max(0, min(100, int(round(confidence * 100))))}%"
        )
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
        self._current_suggestion = None
        self.ai_suggestion_value.setText(
            "Select one photo to check for an advisory suggestion."
        )
        self.ai_suggestion_reasons.setText("")
        self.ai_suggestion_reasons.setVisible(False)
        self.apply_suggestion_button.setEnabled(False)
        self.reject_suggestion_button.setEnabled(False)
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
        self._request_category_suggestion(row)
        increment_memory_review_counter("detail_refreshes")
        record_memory_review(
            "Preview refresh", (time.perf_counter() - detail_started) * 1000.0, items=1
        )

    def _clear_details(self) -> None:
        self._details_key = None
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("No preview")
        self.filename_value.setText("-")
        self.score_value.setText("-")
        self.media_category_value.setText("-")
        self.category_source_value.setText("-")
        self.classification_reason_value.setText("-")
        self.classification_summary_value.setText(
            "Select a photo to see why its current category is shown."
        )
        self.visual_summary_value.setText("-")
        self.confidence_value.setText("-")
        self.user_decision_value.setText("-")
        self.date_value.setText("-")
        self.date_source_value.setText("-")
        self.pipeline_value.setText("-")
        self.rejection_reason_value.setText("-")
        self.explanations_list.clear()
        self._current_suggestion = None
        self.ai_suggestion_value.setText(
            "Select one photo to check for an advisory suggestion."
        )
        self.ai_suggestion_reasons.setText("")
        self.ai_suggestion_reasons.setVisible(False)
        self.apply_suggestion_button.setEnabled(False)
        self.reject_suggestion_button.setEnabled(False)

    def on_embedding_index_updated(self) -> None:
        """Refresh advisory suggestions after background embeddings are committed."""
        self._category_suggestion_service.invalidate_cache()
        self._suggestion_request_id += 1
        row = self._selected_row()
        if row is not None and self._details_key == self._row_key(row):
            self._request_category_suggestion(row)

    def _request_category_suggestion(self, row: AlbumReviewRow) -> None:
        self._suggestion_request_id += 1
        request_id = self._suggestion_request_id
        self._current_suggestion = None
        self.ai_suggestion_value.setText("Checking stored visual evidence…")
        self.ai_suggestion_reasons.setText("")
        self.ai_suggestion_reasons.setVisible(False)
        self.apply_suggestion_button.setEnabled(False)
        self.reject_suggestion_button.setEnabled(False)

        self._pending_suggestion_row = row
        self._suggestion_timer.setProperty("request_id", request_id)
        self._suggestion_timer.start()
        increment_memory_review_counter("suggestion_refreshes_deferred")

    def _compute_pending_suggestion(self) -> None:
        row = self._pending_suggestion_row
        request_id = int(self._suggestion_timer.property("request_id") or 0)
        self._pending_suggestion_row = None
        if row is None or request_id != self._suggestion_request_id:
            increment_memory_review_counter("stale_suggestions_ignored")
            return
        with measure_memory_review("Suggestion refresh", items=len(self._all_rows)):
            result = self._category_suggestion_service.suggest(
                row.breakdown.photo,
                [r.breakdown.photo for r in self._all_rows],
                self._suggestion_metadata,
            )
        if (
            request_id != self._suggestion_request_id
            or self._details_key != self._row_key(row)
        ):
            increment_memory_review_counter("stale_suggestions_ignored")
            return
        self._render_category_suggestion(result)

    def _render_category_suggestion(self, result) -> None:
        self._current_suggestion = result if result.status == "suggested" else None
        self.ai_suggestion_reasons.setText("")
        self.ai_suggestion_reasons.setVisible(
            bool(result.reasons) and result.status == "suggested"
        )
        if result.status == "suggested":
            support_count = result.evidence_counts.get(result.suggested_category_id, 0)
            self.ai_suggestion_value.setText(
                "<span style='font-size: 11px'>Suggested category</span><br>"
                f"<span style='font-size: 16px; font-weight: 700'>{escape(result.suggested_category_name)}</span><br>"
                "<span style='font-size: 11px'>Confidence</span> "
                f"<b>{int(round(result.confidence * 100))}%</b>&nbsp;&nbsp;"
                "<span style='font-size: 11px'>Supporting evidence</span> "
                f"<b>{support_count} confirmed similar photos</b>"
            )
            explanation = "<br>".join(
                escape(str(reason).strip())
                for reason in result.reasons
                if str(reason).strip()
            )
            self.ai_suggestion_reasons.setText(
                "<span style='font-size: 11px'>Explanation</span><br>" + explanation
            )
            self.apply_suggestion_button.setEnabled(True)
            self.reject_suggestion_button.setEnabled(True)
        elif result.status == "already_accepted":
            support_count = result.evidence_counts.get(result.suggested_category_id, 0)
            support_text = (
                f"\nSupporting evidence: {support_count} confirmed similar photos"
                if support_count
                else ""
            )
            self.ai_suggestion_value.setText(
                "✓ Suggestion already accepted\n"
                f"Category: {result.suggested_category_name}\n"
                f"This suggestion has already been applied.{support_text}"
            )
            self.apply_suggestion_button.setEnabled(False)
            self.reject_suggestion_button.setEnabled(False)
        else:
            label = result.status.replace("_", " ").title()
            detail = (
                result.reasons[0]
                if result.reasons
                else "No safe advisory suggestion is available."
            )
            self.ai_suggestion_value.setText(f"No suggestion ({label}). {detail}")
            self.apply_suggestion_button.setEnabled(False)
            self.reject_suggestion_button.setEnabled(
                result.status not in {"no_embedding", "error"}
            )

    def _apply_current_suggestion(self) -> None:
        result = self._current_suggestion
        row = self._selected_row()
        if result is None or row is None or result.status != "suggested":
            return
        self._suggestion_request_id += 1
        applied_at = datetime.now(timezone.utc).isoformat()
        evidence_counts = getattr(result, "evidence_counts", {}) or {}
        applied = self._apply_category_to_rows(
            [row],
            result.suggested_category_id,
            source="ai_suggestion_accepted",
            acceptance_metadata={
                "category_suggestion_state": "accepted",
                "category_suggestion_model_key": result.model_key,
                "category_suggestion_applied_category": result.suggested_category_id,
                "category_suggestion_support_count": evidence_counts.get(
                    result.suggested_category_id, 0
                ),
                "category_suggestion_confidence": float(
                    getattr(result, "confidence", 0.0) or 0.0
                ),
                "category_suggestion_accepted_at": applied_at,
                "category_suggestion_applied_at": applied_at,
            },
        )
        if not applied:
            self.ai_suggestion_value.setText(
                "Could not save the suggested category. No acceptance was recorded; "
                "the suggestion is still available."
            )
            self.apply_suggestion_button.setEnabled(True)
            self.reject_suggestion_button.setEnabled(True)
            return
        self._current_suggestion = None
        self.apply_suggestion_button.setEnabled(False)
        self.reject_suggestion_button.setEnabled(False)
        self.ai_suggestion_value.setText(
            "Suggestion applied through the category correction workflow."
        )
        self.ai_suggestion_reasons.setText("")
        self._category_suggestion_service.invalidate_cache()

    def _reject_current_suggestion(self) -> None:
        self._suggestion_request_id += 1
        result = self._current_suggestion
        row = self._selected_row()
        if result is not None:
            self._category_suggestion_service.record_rejection(
                result,
                source="user",
                photo=row.breakdown.photo if row is not None else None,
            )
        self._current_suggestion = None
        self.apply_suggestion_button.setEnabled(False)
        self.reject_suggestion_button.setEnabled(False)
        self.ai_suggestion_value.setText(
            "Suggestion marked not useful. Category was not changed."
        )

    def _sync_selectors_to_row(self, row: AlbumReviewRow) -> None:
        self._decision_selector_syncing = True
        decision_index = self.decision_selector.findText(row.user_decision)
        self.decision_selector.setCurrentIndex(
            decision_index if decision_index >= 0 else 0
        )
        self._decision_selector_syncing = False

        category_value = self._effective_category_for_photo(row.breakdown.photo)
        self._category_selector_syncing = True
        category_index = self.category_selector.findData(category_value)
        self.category_selector.setCurrentIndex(
            category_index if category_index >= 0 else 0
        )
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

    def _normalize_category_id(self, value) -> str:
        return self._category_registry.normalize_category_id(value)

    def _apply_selector_category(self) -> None:
        category = self._normalize_category_id(
            self.category_selector.currentData() or self.category_selector.currentText()
        )
        rows = self._selected_rows()
        if not rows or not category:
            return

        if not self._confirm_bulk_if_needed(
            len(rows), f"apply category {media_category_label(category)}"
        ):
            return

        self._apply_category_to_rows(
            rows, category, source="user_bulk" if len(rows) > 1 else "user"
        )

    def _confirm_bulk_if_needed(self, count: int, action_text: str) -> bool:
        if count <= 20:
            return True

        response = QMessageBox.question(
            self,
            "Confirm bulk change",
            f"You selected {count} photos.\n\nDo you want to {action_text}?",
        )
        return response == QMessageBox.StandardButton.Yes

    def _apply_decision_to_rows(
        self, rows: List[AlbumReviewRow], decision: str, source: str
    ) -> None:
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

    def _apply_category_to_rows(
        self,
        rows: List[AlbumReviewRow],
        category: str,
        source: str,
        acceptance_metadata: Optional[dict] = None,
    ) -> bool:
        category = self._normalize_category_id(category)
        if not category:
            return False

        affected_keys = [self._row_key(row) for row in rows]
        preferred_key = self._selected_key or (
            affected_keys[0] if affected_keys else None
        )
        previous_visible_keys = [self._row_key(row) for row in self._visible_rows]
        previous_scroll = self.grid_scroll.verticalScrollBar().value()
        previous_render_count = max(
            len(self._rendered_keys), self._initial_render_count
        )

        for row in rows:
            photo = row.breakdown.photo
            previous = self._effective_category_for_photo(photo)

            metadata = dict(getattr(photo, "metadata", {}) or {})
            previous_metadata = dict(metadata)
            previous_decision = row.user_decision
            previous_review_state = row.review_state
            previous_photo_decision = getattr(photo, "user_decision", "")
            previous_category_fields = {
                name: getattr(photo, name, "")
                for name in (
                    "automatic_media_category",
                    "user_corrected_media_category",
                    "effective_media_category",
                    "media_category",
                    "classification_reason",
                )
            }
            decision_changed = False
            automatic = (
                str(
                    metadata.get("automatic_media_category", "")
                    or getattr(photo, "automatic_media_category", "")
                    or previous
                )
                .strip()
                .lower()
            )

            metadata["automatic_media_category"] = automatic
            metadata["user_corrected_media_category"] = category
            metadata["effective_media_category"] = category
            metadata["media_category"] = category
            metadata["category_confirmation_state"] = "manual_confirmed"
            metadata["category_confirmation_source"] = source
            metadata["category_confirmation_category"] = category
            metadata["category_confirmation_at"] = datetime.now(
                timezone.utc
            ).isoformat()
            if acceptance_metadata:
                metadata.update(acceptance_metadata)
            if row.user_decision == UserDecision.Pending.value:
                row.user_decision = UserDecision.Keep.value
                row.review_state = self._review_state_from_decision(row.user_decision)
                photo.user_decision = row.user_decision
                metadata["user_decision"] = row.user_decision
                decision_changed = True
            metadata["classification_reason"] = (
                metadata.get("classification_reason", "") or "User corrected category."
            )
            photo.metadata = metadata

            photo.automatic_media_category = automatic
            photo.user_corrected_media_category = category
            photo.effective_media_category = category
            photo.media_category = category
            photo.classification_reason = str(
                metadata.get("classification_reason", "") or ""
            )
            photo.sync_intelligence_from_metadata()

            if not self._save_photo_user_metadata(photo):
                photo.metadata = previous_metadata
                row.user_decision = previous_decision
                row.review_state = previous_review_state
                photo.user_decision = previous_photo_decision
                for name, value in previous_category_fields.items():
                    setattr(photo, name, value)
                photo.sync_intelligence_from_metadata()
                self._show_user_saved_indicator(
                    "Category save failed — no change applied"
                )
                return False

            if decision_changed:
                self._decision_history.record_decision_change(
                    photo,
                    previous_value=previous_decision,
                    new_value=row.user_decision,
                    source=source,
                )
                self._preference_learning_engine.record_decision(
                    photo,
                    previous_decision=previous_decision,
                    new_decision=row.user_decision,
                    source=source,
                )

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
            self._category_learning_engine.start_pending_visual_analysis_worker(
                limit=25
            )
            self._preference_learning_engine.record_category_correction(
                photo,
                previous_category=previous,
                corrected_category=category,
                source=source,
            )
            card = self._cards_by_key.get(self._row_key(row))
            if card is not None:
                card.refresh_from_row(thumbnail=self._get_cached_card_thumbnail(row))

        self._category_learning_engine.start_pending_visual_analysis_worker(limit=25)
        self._category_suggestion_service.invalidate_cache()
        self._show_user_saved_indicator("User category saved")
        self.review_state_changed.emit()
        self._refresh_after_category_change(
            affected_keys=affected_keys,
            preferred_key=preferred_key,
            previous_visible_keys=previous_visible_keys,
            previous_scroll=previous_scroll,
            previous_render_count=previous_render_count,
        )
        return True

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
            self._index_visible_rows()
            for key in affected_keys:
                row = self._row_for_key(key)
                card = self._cards_by_key.get(key)
                if row is not None and card is not None:
                    card.refresh_from_row(
                        thumbnail=self._get_cached_card_thumbnail(row)
                    )
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
        self._selected_keys = {
            key for key in self._selected_keys if key in visible_key_set
        }
        if selected_key:
            self._selected_key = selected_key
            self._selected_keys = {selected_key}
            self._selection_anchor_key = selected_key
        else:
            self._selected_key = None
            self._selection_anchor_key = None

        self._visible_rows = new_visible_rows
        self._index_visible_rows()
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

    def _rebuild_grid_preserving_scroll(
        self, scroll_value: int, render_count: int
    ) -> None:
        self._clear_grid()
        self._cards_by_key = {}
        self._rendered_keys = []
        self._pending_render_index = 0
        self._target_render_count = min(
            max(self._initial_render_count, int(render_count or 0)),
            len(self._visible_rows),
        )
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

    def _save_photo_user_metadata(self, photo) -> bool:
        try:
            saved_path = self._user_metadata_service.save_photo_metadata(photo)
        except (OSError, ValueError, TypeError):
            return False
        return saved_path is not None

    def _ensure_category_fields(self, photo) -> None:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        automatic = (
            str(
                metadata.get("automatic_media_category", "")
                or getattr(photo, "automatic_media_category", "")
                or metadata.get("media_category", "")
                or getattr(photo, "media_category", "")
                or MediaCategory.Unknown.value
            )
            .strip()
            .lower()
        )

        user_corrected = (
            str(
                metadata.get("user_corrected_media_category", "")
                or getattr(photo, "user_corrected_media_category", "")
                or ""
            )
            .strip()
            .lower()
        )

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
            photo.classification_reason = str(
                metadata.get("classification_reason", "") or ""
            )
        if not getattr(photo, "classification_confidence", None):
            photo.classification_confidence = float(
                metadata.get("classification_confidence", 0.0) or 0.0
            )

    def _effective_category_for_photo(self, photo) -> str:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        return (
            str(
                metadata.get("effective_media_category", "")
                or getattr(photo, "effective_media_category", "")
                or metadata.get("user_corrected_media_category", "")
                or getattr(photo, "user_corrected_media_category", "")
                or metadata.get("automatic_media_category", "")
                or getattr(photo, "automatic_media_category", "")
                or metadata.get("media_category", "")
                or getattr(photo, "media_category", "")
                or MediaCategory.Unknown.value
            )
            .strip()
            .lower()
        )

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
        date_value = (
            getattr(intelligence, "date_taken", None)
            if intelligence is not None
            else None
        )
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
        photo_key = self._photo_key(photo)
        if not file_path:
            return None

        cache_key = self._thumbnail_cache_key(photo_key, QSize(140, 140))
        cached = self._thumbnail_cache.get(cache_key)
        if cached is not None:
            return cached[1]

        retained = self._retained_thumbnail_by_key.get(photo_key)
        if isinstance(retained, QPixmap) and not retained.isNull():
            self._thumbnail_source_by_key[photo_key] = "retained"
            self._thumbnail_cache[cache_key] = (0, retained)
            return retained

        pixmap = getattr(photo, "thumbnail", None)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self._thumbnail_source_by_key[photo_key] = "photo_thumbnail"
            self._retained_thumbnail_by_key[photo_key] = pixmap
        else:
            pixmap = None

        thumbnail_path = str(getattr(photo, "thumbnail_path", "") or "")
        if pixmap is None and thumbnail_path and Path(thumbnail_path).exists():
            pixmap = load_display_thumbnail(thumbnail_path, QSize(140, 140))
            if pixmap is not None and not pixmap.isNull():
                self._thumbnail_source_by_key[photo_key] = "thumbnail_path"
                self._retained_thumbnail_by_key[photo_key] = pixmap

        if pixmap is not None and not pixmap.isNull():
            self._thumbnail_cache[cache_key] = (0, pixmap)
            return pixmap

        return None

    def update_thumbnail(self, photo, pixmap) -> None:
        started = time.perf_counter()
        key = self._photo_key(photo)
        if not key:
            return

        if not isinstance(pixmap, QPixmap) or pixmap.isNull():
            return

        self._retained_thumbnail_by_key[key] = pixmap
        self._thumbnail_source_by_key[key] = "retained"

        self._thumbnail_cache = {
            cache_key: value
            for cache_key, value in self._thumbnail_cache.items()
            if not cache_key.startswith(f"{key}|")
        }

        self._preview_cache = {
            cache_key: value
            for cache_key, value in self._preview_cache.items()
            if not cache_key.startswith(f"{key}|")
        }

        for row in self._all_rows:
            if self._row_key(row) != key:
                continue
            row.breakdown.photo.thumbnail = pixmap
            card = self._cards_by_key.get(self._row_key(row))
            if card is not None:
                card.refresh_from_row(thumbnail=pixmap)
            if self._details_key == key:
                self._show_details(row, force=True)
            record_memory_review(
                "Thumbnail refresh", (time.perf_counter() - started) * 1000.0, items=1
            )
            increment_memory_review_counter("thumbnail_updates")
            break

    def _refresh_selected_preview(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        preview = self._get_cached_preview(row.breakdown.photo)
        if isinstance(preview, QPixmap) and not preview.isNull():
            self.preview_label.setPixmap(preview)
            self.preview_label.setText("")

    def _preview_target_size(self) -> QSize:
        available_width = max(300, self.preview_label.width() - 10)
        # Quantizing avoids filling the cache with a new pixmap for every resize pixel.
        target_width = max(300, (available_width // 40) * 40)
        target_height = max(110, self.preview_label.height() - 8)
        return QSize(target_width, target_height)

    def _get_cached_preview(self, photo) -> Optional[QPixmap]:
        photo_key = self._photo_key(photo)
        if not photo_key:
            return None

        target_size = self._preview_target_size()
        cache_key = self._thumbnail_cache_key(photo_key, target_size)
        cached = self._preview_cache.get(cache_key)
        if cached is not None:
            return cached[1]

        retained = self._retained_thumbnail_by_key.get(photo_key)
        if isinstance(retained, QPixmap) and not retained.isNull():
            scaled = retained.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview_cache[cache_key] = (0, scaled)
            return scaled

        photo_thumbnail = getattr(photo, "thumbnail", None)
        if isinstance(photo_thumbnail, QPixmap) and not photo_thumbnail.isNull():
            scaled = photo_thumbnail.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview_cache[cache_key] = (0, scaled)
            return scaled

        thumbnail_path = str(getattr(photo, "thumbnail_path", "") or "")
        pixmap = None
        if thumbnail_path and Path(thumbnail_path).exists():
            pixmap = load_display_thumbnail(thumbnail_path, target_size)
        if pixmap is not None and not pixmap.isNull():
            self._preview_cache[cache_key] = (0, pixmap)
            return pixmap

        return None

    def _thumbnail_cache_key(self, photo_key: str, size: QSize) -> str:
        return f"{photo_key}|{size.width()}x{size.height()}"

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
                return self._thumbnail_source_by_key.get(self._photo_key(photo), "")
        return ""

    def set_selected_decision(self, decision: str) -> None:
        selected = self._selected_row()
        if selected is None:
            return
        self._apply_decision_to_rows([selected], decision, source="user")

    def set_empty_reason(self, message: str) -> None:
        self._empty_reason_text = str(message or "").strip()
        self.results_label.setText(self._results_label_text())

    def all_row_count(self) -> int:
        return len(self._all_rows)

    def visible_row_count(self) -> int:
        return len(self._visible_rows)

    def rendered_card_count(self) -> int:
        return len(self._cards_by_key)

    def retained_thumbnail_count(self) -> int:
        return len(self._retained_thumbnail_by_key)

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

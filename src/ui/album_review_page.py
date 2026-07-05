from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QPixmap
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
from core.media_classifier import (
    DecisionHistory,
    MediaCategory,
    UserDecision,
    media_category_label,
    ordered_media_category_values,
)


@dataclass
class AlbumReviewRow:
    breakdown: AlbumScoreBreakdown
    review_state: str = "pending"
    user_decision: str = UserDecision.Pending.value
    pipeline_state: str = "imported"
    rejection_reason: Optional[str] = None


class AlbumReviewCardWidget(QFrame):
    clicked = Signal(str, int)

    def __init__(self, row: AlbumReviewRow, key: str, thumbnail: Optional[QPixmap] = None, parent=None):
        super().__init__(parent)
        self.row = row
        self.key = key
        self._selected = False

        self.setObjectName("albumReviewCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(220)

        self.thumbnail_label = QLabel("No thumbnail")
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setFixedHeight(130)
        self.thumbnail_label.setStyleSheet("border: 1px solid #bbb; background: #f6f6f6;")

        self.filename_label = QLabel("")
        self.filename_label.setWordWrap(True)
        self.filename_label.setStyleSheet("font-weight: 600;")

        self.scores_label = QLabel("")
        self.scores_label.setWordWrap(True)

        self.category_label = QLabel("")
        self.confidence_label = QLabel("")
        self.decision_label = QLabel("")
        self.pipeline_label = QLabel("")
        self.pipeline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.thumbnail_label)
        layout.addWidget(self.filename_label)
        layout.addWidget(self.scores_label)
        layout.addWidget(self.category_label)
        layout.addWidget(self.confidence_label)
        layout.addWidget(self.decision_label)
        layout.addWidget(self.pipeline_label)

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

        self.filename_label.setText(photo.display_name())
        self.scores_label.setText(
            (
                f"Total: {breakdown.total_score:.2f}\n"
                f"Technical: {breakdown.technical_score:.2f}  "
                f"Memory: {breakdown.memory_score:.2f}  "
                f"Date: {breakdown.date_score:.2f}"
            )
        )

        confidence = float(getattr(photo, "classification_confidence", 0.0) or 0.0)
        category_value = str(getattr(photo, "effective_media_category", "") or getattr(photo, "media_category", "unknown") or "unknown")
        category_text = media_category_label(category_value)
        decision_text = self.row.user_decision.replace("_", " ").title()
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


class AlbumReviewPage(QWidget):
    # PERF-001 bottleneck notes:
    # - Creating thousands of card widgets blocks the UI thread.
    # - Rebuilding the whole grid for each keypress is expensive.
    # - Re-scaling thumbnails on every refresh wastes CPU.
    # - Repainting details/preview for same selection is unnecessary work.
    # - Rendering should be lazy and driven by viewport demand.
    FILTER_ALL = "All"
    FILTER_PENDING = "Pending"
    FILTER_APPROVED = "Approved"
    FILTER_REJECTED = "Rejected"
    CATEGORY_FILTER_ALL = "All categories"

    SORT_HIGHEST = "Highest score"
    SORT_LOWEST = "Lowest score"
    SORT_DATE = "Date"

    review_state_changed = Signal()

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
        self._preview_cache: Dict[str, tuple[int, QPixmap]] = {}
        self._last_view_signature: Optional[tuple[str, str, str]] = None
        self._last_visible_key_order: List[str] = []
        self._grid_rebuild_count = 0
        self._decision_history = DecisionHistory()
        self._decision_selector_syncing = False
        self._category_selector_syncing = False

        self.memory_review_label = QLabel("Memory Review")
        self.memory_review_label.setStyleSheet("font-size: 18px; font-weight: 600;")

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
        self.category_filter_combo.addItem(self.CATEGORY_FILTER_ALL)
        for category_value in ordered_media_category_values():
            self.category_filter_combo.addItem(media_category_label(category_value))
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
        self.select_all_visible_button = QPushButton("Select all visible")
        self.select_all_visible_button.clicked.connect(self.select_all_visible)
        self.clear_selection_button = QPushButton("Clear selection")
        self.clear_selection_button.clicked.connect(self.clear_selection)
        controls_layout.addWidget(self.selection_count_label)
        controls_layout.addWidget(self.select_all_visible_button)
        controls_layout.addWidget(self.clear_selection_button)

        self.results_label = QLabel("Showing 0 photos")

        self.grid_scroll = QScrollArea(self)
        self.grid_scroll.setWidgetResizable(True)

        self.grid_content = QWidget(self.grid_scroll)
        self.grid_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.grid_layout = QGridLayout(self.grid_content)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(10)
        self.grid_scroll.setWidget(self.grid_content)
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
        self.confidence_value = QLabel("-")
        self.user_decision_value = QLabel("-")
        self.date_value = QLabel("-")
        self.date_source_value = QLabel("-")

        details_form = QFormLayout()
        details_form.addRow("Filename:", self.filename_value)
        details_form.addRow("Score:", self.score_value)
        details_form.addRow("Media category:", self.media_category_value)
        details_form.addRow("Classification reason:", self.classification_reason_value)
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
        for category_value in ordered_media_category_values():
            self.category_selector.addItem(media_category_label(category_value), category_value)
        self.category_selector.currentTextChanged.connect(self._on_category_selector_changed)

        self.apply_decision_button = QPushButton("Apply Decision to Selected")
        self.apply_decision_button.clicked.connect(self._apply_selector_decision)
        self.apply_category_button = QPushButton("Apply Category to Selected")
        self.apply_category_button.clicked.connect(self._apply_selector_category)

        actions_layout = QHBoxLayout()
        actions_layout.addWidget(QLabel("Category:"))
        actions_layout.addWidget(self.category_selector, 1)
        actions_layout.addWidget(self.apply_category_button)
        actions_layout.addWidget(QLabel("Decision:"))
        actions_layout.addWidget(self.decision_selector, 1)
        actions_layout.addWidget(self.apply_decision_button)

        details_layout = QVBoxLayout()
        details_layout.addWidget(QLabel("Preview"))
        details_layout.addWidget(self.preview_label)
        details_layout.addLayout(details_form)
        details_layout.addWidget(QLabel("Score explanation"))
        details_layout.addWidget(self.explanations_list, 1)
        details_layout.addLayout(actions_layout)

        details_panel = QWidget()
        details_panel.setLayout(details_layout)
        details_panel.setMinimumWidth(520)

        splitter = QSplitter()
        grid_panel = QWidget()
        grid_layout = QVBoxLayout(grid_panel)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self.results_label)
        grid_layout.addWidget(self.grid_scroll, 1)

        splitter.addWidget(grid_panel)
        splitter.addWidget(details_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 3)

        root_layout = QVBoxLayout(self)
        root_layout.addWidget(self.memory_review_label)
        root_layout.addLayout(controls_layout)
        root_layout.addWidget(splitter, 1)

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
        filtered = [
            row
            for row in self._all_rows
            if self._matches_filter(row) and self._matches_category_filter(row) and self._matches_search(row)
        ]

        sort_option = self.sort_combo.currentText()
        if sort_option == self.SORT_LOWEST:
            filtered.sort(key=lambda row: row.breakdown.total_score)
        elif sort_option == self.SORT_DATE:
            filtered.sort(key=self._sort_date_key, reverse=True)
        else:
            filtered.sort(key=lambda row: row.breakdown.total_score, reverse=True)

        self._visible_rows = filtered
        next_visible_order = [self._row_key(row) for row in self._visible_rows]
        imported_count = len(self._all_rows)
        selected_count = sum(1 for row in self._all_rows if row.pipeline_state == "selected")
        rejected_count = sum(1 for row in self._all_rows if row.pipeline_state == "rejected")
        reasons_text = "none"
        if self._rejection_reasons_summary:
            reasons_text = ", ".join(
                f"{reason}:{count}"
                for reason, count in sorted(self._rejection_reasons_summary.items())
            )
        self.results_label.setText(
            (
                f"Showing {len(self._visible_rows)} of {len(self._all_rows)} photos | "
                f"Imported: {imported_count} | Candidates: {self._candidate_count} | "
                f"Selected: {selected_count} | Rejected: {rejected_count} | "
                f"Reasons: {reasons_text}"
            )
        )
        self._refresh_selection_count_label()

        if not force and next_visible_order == self._last_visible_key_order:
            self._refresh_card_selection()
            selected = self._selected_row()
            if selected is not None:
                self._show_details(selected)
            return

        self._last_visible_key_order = next_visible_order
        self._rebuild_grid()

    def approve_selected(self) -> None:
        self.set_selected_decision(UserDecision.ApproveForAlbum.value)

    def reject_selected(self) -> None:
        self.set_selected_decision(UserDecision.Reject.value)

    def reset_selected(self) -> None:
        self.set_selected_decision(UserDecision.Pending.value)

    def _set_state_for_selected(self, state: str) -> None:
        decision = UserDecision.Pending.value
        if state == "approved":
            decision = UserDecision.ApproveForAlbum.value
        elif state == "rejected":
            decision = UserDecision.Reject.value
        self.set_selected_decision(decision)

    def set_selected_decision(self, decision: str) -> None:
        selected = self._selected_row()
        if selected is None:
            return

        normalized = self._normalize_decision(decision)
        previous_decision = selected.user_decision
        if previous_decision == normalized:
            return

        selected.user_decision = normalized
        selected.review_state = self._review_state_from_decision(normalized)
        photo = selected.breakdown.photo
        setattr(photo, "user_decision", normalized)
        metadata = dict(getattr(photo, "metadata", {}) or {})
        metadata["user_decision"] = normalized
        photo.metadata = metadata
        photo.sync_intelligence_from_metadata()
        self._decision_history.record_decision_change(photo, previous_decision, normalized)

        self.review_state_changed.emit()
        current_filter = self.filter_combo.currentText()
        if current_filter == self.FILTER_ALL:
            card = self._cards_by_key.get(self._row_key(selected))
            if card is not None:
                card.refresh_from_row(thumbnail=self._get_cached_card_thumbnail(selected))
            self._set_selector_value(normalized)
            self._show_details(selected)
            return

        self._trigger_refresh(force=True)

    def _on_decision_selector_changed(self, _value: str) -> None:
        if self._decision_selector_syncing:
            return

    def _apply_selector_decision(self) -> None:
        selected_rows = self._selected_rows()
        if not selected_rows:
            return
        event_source = "user_bulk" if len(selected_rows) > 1 else "user"

        normalized = self._normalize_decision(self.decision_selector.currentText())
        if len(selected_rows) > 20 and not self._confirm_bulk_change(
            action_label="decision",
            selected_count=len(selected_rows),
            target_value=normalized,
        ):
            return

        changed = False
        for row in selected_rows:
            previous_decision = row.user_decision
            if previous_decision == normalized:
                continue

            row.user_decision = normalized
            row.review_state = self._review_state_from_decision(normalized)
            photo = row.breakdown.photo
            setattr(photo, "user_decision", normalized)
            metadata = dict(getattr(photo, "metadata", {}) or {})
            metadata["user_decision"] = normalized
            photo.metadata = metadata
            photo.sync_intelligence_from_metadata()
            self._decision_history.record_decision_change(
                photo,
                previous_decision,
                normalized,
                source=event_source,
            )

            card = self._cards_by_key.get(self._row_key(row))
            if card is not None:
                card.refresh_from_row(thumbnail=self._get_cached_card_thumbnail(row))
            changed = True

        if not changed:
            return

        self.review_state_changed.emit()
        selected = self._selected_row()
        if selected is not None:
            self._set_selector_value(normalized)
            self._show_details(selected, force=True)
        self._trigger_refresh(force=True)

    def _on_category_selector_changed(self, _value: str) -> None:
        if self._category_selector_syncing:
            return

    def _apply_selector_category(self) -> None:
        selected_rows = self._selected_rows()
        if not selected_rows:
            return
        event_source = "user_bulk" if len(selected_rows) > 1 else "user"

        new_category = str(self.category_selector.currentData() or "").strip().lower()
        if not new_category:
            return

        if len(selected_rows) > 20 and not self._confirm_bulk_change(
            action_label="category",
            selected_count=len(selected_rows),
            target_value=media_category_label(new_category),
        ):
            return

        changed = False
        for row in selected_rows:
            photo = row.breakdown.photo
            previous_effective = self._effective_category_for_photo(photo)
            if previous_effective == new_category:
                continue

            metadata = dict(getattr(photo, "metadata", {}) or {})
            metadata["user_corrected_media_category"] = new_category
            metadata["effective_media_category"] = new_category
            metadata["media_category"] = new_category
            photo.metadata = metadata
            photo.user_corrected_media_category = new_category
            photo.effective_media_category = new_category
            photo.media_category = new_category
            photo.sync_intelligence_from_metadata()
            self._decision_history.record_category_correction(
                photo,
                previous_effective,
                new_category,
                source=event_source,
            )

            card = self._cards_by_key.get(self._row_key(row))
            if card is not None:
                card.refresh_from_row(thumbnail=self._get_cached_card_thumbnail(row))
            changed = True

        if not changed:
            return

        selected = self._selected_row()
        if selected is not None:
            self._show_details(selected, force=True)
        self._trigger_refresh(force=True)

    def _matches_filter(self, row: AlbumReviewRow) -> bool:
        option = self.filter_combo.currentText()
        if option == self.FILTER_PENDING:
            return row.review_state == "pending"
        if option == self.FILTER_APPROVED:
            return row.review_state == "approved"
        if option == self.FILTER_REJECTED:
            return row.review_state == "rejected"
        return True

    def _matches_category_filter(self, row: AlbumReviewRow) -> bool:
        selected_label = self.category_filter_combo.currentText().strip()
        if not selected_label or selected_label == self.CATEGORY_FILTER_ALL:
            return True

        effective_value = self._effective_category_for_photo(row.breakdown.photo)
        return media_category_label(effective_value) == selected_label

    def _matches_search(self, row: AlbumReviewRow) -> bool:
        needle = self.search_input.text().strip().lower()
        if not needle:
            return True

        filename = row.breakdown.photo.display_name().lower()
        return needle in filename

    def _rebuild_grid(self) -> None:
        for card in self._cards_by_key.values():
            self.grid_layout.removeWidget(card)
            card.deleteLater()

        self._cards_by_key = {}
        self._rendered_keys = []
        self._pending_render_index = 0
        self._target_render_count = 0
        self._grid_columns = self._calculate_grid_columns()
        self._grid_rebuild_count += 1

        if not self._visible_rows:
            self._selected_key = None
            self._details_key = None
            self._clear_details()
            return

        visible_keys = {self._row_key(row) for row in self._visible_rows}
        if self._selected_key not in visible_keys:
            self._selected_key = self._row_key(self._visible_rows[0])
        if not self._selected_keys:
            self._selected_keys = {self._selected_key}
        if self._selection_anchor_key is None:
            self._selection_anchor_key = self._selected_key

        self._target_render_count = min(self._initial_render_count, len(self._visible_rows))
        self._schedule_render_batch()

    def _schedule_render_batch(self) -> None:
        QTimer.singleShot(0, self._add_next_batch)

    def _add_next_batch(self) -> None:
        render_limit = min(self._target_render_count, len(self._visible_rows))
        if self._pending_render_index >= render_limit:
            self._refresh_card_selection()
            selected = self._selected_row()
            if selected is not None:
                self._show_details(selected)
            return

        batch_end = min(self._pending_render_index + self._render_batch_size, render_limit)
        for index in range(self._pending_render_index, batch_end):
            row = self._visible_rows[index]
            key = self._row_key(row)
            card = AlbumReviewCardWidget(
                row=row,
                key=key,
                thumbnail=self._get_cached_card_thumbnail(row),
            )
            card.clicked.connect(self._on_card_clicked)
            self._cards_by_key[key] = card
            self._rendered_keys.append(key)

            card_index = len(self._rendered_keys) - 1
            grid_row = card_index // self._grid_columns
            grid_column = card_index % self._grid_columns
            self.grid_layout.addWidget(card, grid_row, grid_column)

        self._pending_render_index = batch_end
        self._refresh_card_selection()

        if self._pending_render_index >= render_limit:
            selected = self._selected_row()
            if selected is not None:
                self._show_details(selected)

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
        self._refresh_selection_count_label()

        selected = self._selected_row()
        if selected is None:
            self._clear_details()
            return

        self._show_details(selected)

    def _refresh_card_selection(self) -> None:
        for key, card in self._cards_by_key.items():
            card.set_selected(key in self._selected_keys)

    def _on_scroll_value_changed(self, value: int) -> None:
        scrollbar = self.grid_scroll.verticalScrollBar()
        if scrollbar.maximum() <= 0:
            return

        near_bottom_threshold = 180
        if value < scrollbar.maximum() - near_bottom_threshold:
            return

        if self._target_render_count >= len(self._visible_rows):
            return

        self._target_render_count = min(
            self._target_render_count + self._render_batch_size,
            len(self._visible_rows),
        )
        self._schedule_render_batch()

    def _selected_row(self) -> Optional[AlbumReviewRow]:
        if not self._selected_key:
            return None

        for row in self._all_rows:
            if self._row_key(row) == self._selected_key:
                return row

        return None

    def _selected_rows(self) -> List[AlbumReviewRow]:
        selected_lookup = set(self._selected_keys)
        if not selected_lookup and self._selected_key:
            selected_lookup.add(self._selected_key)

        rows: List[AlbumReviewRow] = []
        for row in self._all_rows:
            if self._row_key(row) in selected_lookup:
                rows.append(row)
        return rows

    def _range_keys_between(self, start_key: str, end_key: str) -> List[str]:
        visible_keys = [self._row_key(row) for row in self._visible_rows]
        if start_key not in visible_keys or end_key not in visible_keys:
            return [end_key]

        start_index = visible_keys.index(start_key)
        end_index = visible_keys.index(end_key)
        if start_index <= end_index:
            return visible_keys[start_index:end_index + 1]
        return visible_keys[end_index:start_index + 1]

    def _row_key(self, row: AlbumReviewRow) -> str:
        photo = row.breakdown.photo
        return str(getattr(photo, "path", photo.display_name()))

    def _calculate_grid_columns(self) -> int:
        width = max(240, self.grid_scroll.viewport().width())
        return max(1, width // 240)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_columns = self._calculate_grid_columns()
        if new_columns == self._grid_columns:
            return

        self._grid_columns = new_columns
        self._relayout_cards()

    def _relayout_cards(self) -> None:
        for index, key in enumerate(self._rendered_keys):
            card = self._cards_by_key.get(key)
            if card is None:
                continue

            self.grid_layout.removeWidget(card)
            grid_row = index // self._grid_columns
            grid_column = index % self._grid_columns
            self.grid_layout.addWidget(card, grid_row, grid_column)

    def _show_details(self, row: AlbumReviewRow, force: bool = False) -> None:
        breakdown = row.breakdown
        photo = breakdown.photo
        row_key = self._row_key(row)

        if self._details_key == row_key and not force:
            return

        self._details_key = row_key

        pixmap = getattr(photo, "thumbnail", None)
        cached_preview = self._get_cached_preview(row_key, pixmap)
        if isinstance(cached_preview, QPixmap):
            self.preview_label.setPixmap(cached_preview)
            self.preview_label.setText("")
        else:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("No preview")

        self.filename_value.setText(photo.display_name())
        self.score_value.setText(
            (
                f"Total {breakdown.total_score:.2f} | "
                f"Technical {breakdown.technical_score:.2f} | "
                f"Memory {breakdown.memory_score:.2f} | "
                f"Date {breakdown.date_score:.2f}"
            )
        )
        self.pipeline_value.setText(row.pipeline_state.capitalize())
        self.rejection_reason_value.setText(row.rejection_reason or "-")
        self.user_decision_value.setText(row.user_decision)
        self._set_selector_value(row.user_decision)

        category_value = self._effective_category_for_photo(photo)
        self.media_category_value.setText(media_category_label(category_value))
        self._set_category_selector_value(category_value)
        self.classification_reason_value.setText(str(getattr(photo, "classification_reason", "") or "-"))
        confidence = float(getattr(photo, "classification_confidence", 0.0) or 0.0)
        self.confidence_value.setText(f"{max(0, min(100, int(round(confidence * 100))))}%")

        intelligence = getattr(photo, "intelligence", None)
        date_text = "-"
        date_source_text = "Unknown"
        if intelligence is not None and intelligence.date_taken is not None:
            date_text = str(intelligence.date_taken)
            date_source_text = str(getattr(intelligence, "date_source", "Unknown") or "Unknown")
        self.date_value.setText(date_text)
        self.date_source_value.setText(date_source_text)

        self.explanations_list.clear()
        for line in breakdown.explanation:
            self.explanations_list.addItem(str(line))

    def _clear_details(self) -> None:
        self._details_key = None
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("No preview")
        self.filename_value.setText("-")
        self.score_value.setText("-")
        self.pipeline_value.setText("-")
        self.rejection_reason_value.setText("-")
        self.media_category_value.setText("-")
        self.classification_reason_value.setText("-")
        self.confidence_value.setText("-")
        self.user_decision_value.setText("-")
        self.date_value.setText("-")
        self.date_source_value.setText("-")
        self.explanations_list.clear()

    def visible_filenames(self) -> List[str]:
        return [row.breakdown.photo.display_name() for row in self._visible_rows]

    def card_summary_for_filename(self, filename: str) -> Optional[Dict[str, str]]:
        target = (filename or "").strip()
        if not target:
            return None

        for row in self._visible_rows:
            if row.breakdown.photo.display_name() != target:
                continue
            card = self._cards_by_key.get(self._row_key(row))
            if card is None:
                return None
            return {
                "category": card.category_label.text(),
                "confidence": card.confidence_label.text(),
                "decision": card.decision_label.text(),
            }

        return None

    def select_photo_by_filename(self, filename: str) -> bool:
        target = (filename or "").strip()
        if not target:
            return False

        for row in self._visible_rows:
            if row.breakdown.photo.display_name() == target:
                self._selected_key = self._row_key(row)
                self._selected_keys = {self._selected_key}
                self._selection_anchor_key = self._selected_key
                self._refresh_card_selection()
                self._refresh_selection_count_label()
                self._show_details(row)
                return True

        return False

    def review_state_for_filename(self, filename: str) -> Optional[str]:
        target = (filename or "").strip()
        for row in self._all_rows:
            if row.breakdown.photo.display_name() == target:
                return row.review_state
        return None

    def review_status_by_path(self) -> Dict[str, str]:
        return {self._row_key(row): row.review_state for row in self._all_rows}

    def decision_for_filename(self, filename: str) -> Optional[str]:
        target = (filename or "").strip()
        for row in self._all_rows:
            if row.breakdown.photo.display_name() == target:
                return row.user_decision
        return None

    def decision_history_entries(self) -> List:
        return list(self._decision_history.entries)

    def learning_events(self) -> List:
        return list(self._decision_history.entries)

    def selected_count(self) -> int:
        return len(self._selected_keys)

    def selected_file_paths(self) -> List[str]:
        return sorted(self._selected_keys)

    def clear_selection(self) -> None:
        self._selected_keys.clear()
        self._selected_key = None
        self._selection_anchor_key = None
        self._refresh_card_selection()
        self._refresh_selection_count_label()
        self._clear_details()

    def select_all_visible(self) -> None:
        self._selected_keys = {self._row_key(row) for row in self._visible_rows}
        if self._visible_rows:
            self._selected_key = self._row_key(self._visible_rows[0])
            self._selection_anchor_key = self._selected_key
            self._show_details(self._visible_rows[0], force=True)
        self._refresh_card_selection()
        self._refresh_selection_count_label()

    def _refresh_selection_count_label(self) -> None:
        self.selection_count_label.setText(f"Selected: {len(self._selected_keys)}")

    def _confirm_bulk_change(self, action_label: str, selected_count: int, target_value: str) -> bool:
        if selected_count <= 20:
            return True

        response = QMessageBox.question(
            self,
            "Confirm bulk change",
            (
                f"Apply {action_label} change to {selected_count} selected photos?\n"
                f"Target: {target_value}"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return response == QMessageBox.StandardButton.Yes

    def _set_selector_value(self, decision: str) -> None:
        normalized = self._normalize_decision(decision)
        self._decision_selector_syncing = True
        self.decision_selector.setCurrentText(normalized)
        self._decision_selector_syncing = False

    def _set_category_selector_value(self, category_value: str) -> None:
        normalized = self._normalize_category(category_value)
        target_label = media_category_label(normalized)
        self._category_selector_syncing = True
        self.category_selector.setCurrentText(target_label)
        self._category_selector_syncing = False

    def _initial_user_decision_for_photo(self, photo) -> str:
        user_decision = str(getattr(photo, "user_decision", "") or "")
        if not user_decision:
            metadata = getattr(photo, "metadata", {}) or {}
            user_decision = str(metadata.get("user_decision", "") or "")
        normalized = self._normalize_decision(user_decision)
        setattr(photo, "user_decision", normalized)
        metadata = dict(getattr(photo, "metadata", {}) or {})
        metadata["user_decision"] = normalized
        photo.metadata = metadata
        photo.sync_intelligence_from_metadata()
        return normalized

    def _effective_category_for_photo(self, photo) -> str:
        self._ensure_category_fields(photo)
        return str(getattr(photo, "effective_media_category", MediaCategory.Unknown.value) or MediaCategory.Unknown.value)

    def _ensure_category_fields(self, photo) -> None:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        automatic = self._normalize_category(
            str(getattr(photo, "automatic_media_category", "") or metadata.get("automatic_media_category") or getattr(photo, "media_category", "") or metadata.get("media_category") or MediaCategory.Unknown.value)
        )
        corrected = self._normalize_category(str(getattr(photo, "user_corrected_media_category", "") or metadata.get("user_corrected_media_category", "")), allow_empty=True)
        effective = corrected if corrected else automatic

        metadata["automatic_media_category"] = automatic
        metadata["user_corrected_media_category"] = corrected
        metadata["effective_media_category"] = effective
        metadata["media_category"] = effective

        photo.metadata = metadata
        photo.automatic_media_category = automatic
        photo.user_corrected_media_category = corrected
        photo.effective_media_category = effective
        photo.media_category = effective
        photo.sync_intelligence_from_metadata()

    def _normalize_category(self, category_value: str, allow_empty: bool = False) -> str:
        value = str(category_value or "").strip().lower()
        known = set(ordered_media_category_values())
        if value in known:
            return value
        if allow_empty and not value:
            return ""
        return MediaCategory.Unknown.value

    def _review_state_from_decision(self, decision: str) -> str:
        normalized = self._normalize_decision(decision)
        if normalized == UserDecision.ApproveForAlbum.value:
            return "approved"
        if normalized == UserDecision.Reject.value:
            return "rejected"
        return "pending"

    def _normalize_decision(self, decision: str) -> str:
        value = str(decision or "").strip().lower()
        known = {item.value for item in UserDecision}
        if value in known:
            return value
        return UserDecision.Unknown.value if value else UserDecision.Pending.value

    def _sort_date_key(self, row: AlbumReviewRow):
        photo = row.breakdown.photo
        intelligence = getattr(photo, "intelligence", None)
        date_value = getattr(intelligence, "date_taken", None) if intelligence is not None else None

        if isinstance(date_value, datetime):
            return date_value

        if isinstance(date_value, str):
            parsed = self._parse_date_text(date_value)
            if parsed is not None:
                return parsed

        metadata = getattr(photo, "metadata", {}) or {}
        metadata_date = metadata.get("date_taken")
        if isinstance(metadata_date, datetime):
            return metadata_date
        if isinstance(metadata_date, str):
            parsed = self._parse_date_text(metadata_date)
            if parsed is not None:
                return parsed

        return datetime.min

    def _parse_date_text(self, value: str) -> Optional[datetime]:
        text = (value or "").strip()
        if not text:
            return None

        known_formats = [
            "%Y:%m:%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y:%m:%d",
            "%Y-%m-%d",
            "%Y/%m/%d",
        ]
        for date_format in known_formats:
            try:
                return datetime.strptime(text, date_format)
            except ValueError:
                continue

        return None

    def _get_cached_card_thumbnail(self, row: AlbumReviewRow) -> Optional[QPixmap]:
        key = self._row_key(row)
        photo = row.breakdown.photo
        pixmap = getattr(photo, "thumbnail", None)
        if not isinstance(pixmap, QPixmap):
            return None

        source_key = int(pixmap.cacheKey())
        cached = self._thumbnail_cache.get(key)
        if cached is not None and cached[0] == source_key:
            return cached[1]

        scaled = pixmap.scaled(
            200,
            120,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumbnail_cache[key] = (source_key, scaled)
        return scaled

    def _get_cached_preview(self, row_key: str, pixmap: Optional[QPixmap]) -> Optional[QPixmap]:
        if not isinstance(pixmap, QPixmap):
            return None

        source_key = int(pixmap.cacheKey())
        cached = self._preview_cache.get(row_key)
        if cached is not None and cached[0] == source_key:
            return cached[1]

        scaled = pixmap.scaled(
            320,
            220,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_cache[row_key] = (source_key, scaled)
        return scaled
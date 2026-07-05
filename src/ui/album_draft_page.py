from __future__ import annotations

from statistics import mean
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from album.album_draft_builder import AlbumDraftBuildResult, AlbumDraftPage as DraftPageModel
from ui.photo_grid_widget import PhotoGridWidget


class AlbumDraftPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._draft_result: Optional[AlbumDraftBuildResult] = None
        self._selected_page: Optional[DraftPageModel] = None

        self.year_value = QLabel("-")
        self.total_pages_value = QLabel("0")
        self.total_included_value = QLabel("0")
        self.source_photos_value = QLabel("0")
        self.excluded_photos_value = QLabel("0")

        summary_layout = QHBoxLayout()
        summary_layout.addWidget(self._create_summary_block("Album year", self.year_value))
        summary_layout.addWidget(self._create_summary_block("Total pages", self.total_pages_value))
        summary_layout.addWidget(self._create_summary_block("Total included photos", self.total_included_value))
        summary_layout.addWidget(self._create_summary_block("Source photos", self.source_photos_value))
        summary_layout.addWidget(self._create_summary_block("Excluded photos", self.excluded_photos_value))

        self.largest_month_value = QLabel("-")
        self.smallest_month_value = QLabel("-")
        self.average_per_page_value = QLabel("0.0")

        stats_layout = QFormLayout()
        stats_layout.addRow("Largest month:", self.largest_month_value)
        stats_layout.addRow("Smallest month:", self.smallest_month_value)
        stats_layout.addRow("Average photos per page:", self.average_per_page_value)

        self.page_list = QListWidget()
        self.page_list.currentRowChanged.connect(self._on_page_changed)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Draft Pages"))
        left_layout.addWidget(self.page_list, 1)
        left_panel.setMinimumWidth(240)

        self.photo_grid = PhotoGridWidget()
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.addWidget(QLabel("Page Photos"))
        center_layout.addWidget(self.photo_grid, 1)

        self.page_title_value = QLabel("-")
        self.page_photo_count_value = QLabel("0")
        self.page_type_value = QLabel("-")
        self.page_explanations_list = QListWidget()

        details_form = QFormLayout()
        details_form.addRow("Page title:", self.page_title_value)
        details_form.addRow("Number of photos:", self.page_photo_count_value)
        details_form.addRow("Page type:", self.page_type_value)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Page Details"))
        right_layout.addLayout(details_form)
        right_layout.addWidget(QLabel("Explanation"))
        right_layout.addWidget(self.page_explanations_list, 1)
        right_panel.setMinimumWidth(320)

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 3)

        self.empty_state_label = QLabel(
            "No album draft is available yet. Import photos and create an album draft first."
        )
        self.empty_state_label.setWordWrap(True)
        self.empty_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state_label.setStyleSheet("font-size: 16px; color: #444; padding: 36px;")

        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(splitter, 1)

        self.stack_layout = QStackedLayout()
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.addStretch(1)
        empty_layout.addWidget(self.empty_state_label)
        empty_layout.addStretch(1)
        self.stack_layout.addWidget(self.empty_widget)
        self.stack_layout.addWidget(self.content_widget)

        root_layout = QVBoxLayout(self)
        root_layout.addLayout(summary_layout)
        root_layout.addLayout(stats_layout)

        stack_host = QWidget()
        stack_host.setLayout(self.stack_layout)
        root_layout.addWidget(stack_host, 1)

        self.set_draft_result(None)

    def _create_summary_block(self, title: str, value_label: QLabel) -> QWidget:
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 12px; color: #666;")
        value_label.setStyleSheet("font-size: 20px; font-weight: 700;")

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        widget.setStyleSheet("background: #f7f7f7; border: 1px solid #dddddd; border-radius: 6px;")
        return widget

    def set_draft_result(self, result: Optional[AlbumDraftBuildResult]) -> None:
        self._draft_result = result
        self._selected_page = None
        self.page_list.clear()
        self.photo_grid.set_photos([])
        self._clear_page_details()

        if result is None:
            self.year_value.setText("-")
            self.total_pages_value.setText("0")
            self.total_included_value.setText("0")
            self.source_photos_value.setText("0")
            self.excluded_photos_value.setText("0")
            self.largest_month_value.setText("-")
            self.smallest_month_value.setText("-")
            self.average_per_page_value.setText("0.0")
            self.stack_layout.setCurrentWidget(self.empty_widget)
            return

        draft = result.draft
        pages = list(draft.pages or [])

        self.year_value.setText(str(draft.year))
        self.total_pages_value.setText(str(len(pages)))
        self.total_included_value.setText(str(result.included_photo_count))
        self.source_photos_value.setText(str(result.source_photo_count))
        self.excluded_photos_value.setText(str(result.excluded_photo_count))
        self._update_statistics(pages)

        for page in pages:
            item = QListWidgetItem(f"{page.title} ({len(page.photos)})")
            item.setData(Qt.ItemDataRole.UserRole, page.title)
            self.page_list.addItem(item)

        self.stack_layout.setCurrentWidget(self.content_widget)
        if pages:
            self.page_list.setCurrentRow(0)

    def _update_statistics(self, pages: list[DraftPageModel]) -> None:
        if not pages:
            self.largest_month_value.setText("-")
            self.smallest_month_value.setText("-")
            self.average_per_page_value.setText("0.0")
            return

        largest = max(pages, key=lambda page: (len(page.photos), page.title))
        smallest = min(pages, key=lambda page: (len(page.photos), page.title))
        self.largest_month_value.setText(f"{largest.title} ({len(largest.photos)})")
        self.smallest_month_value.setText(f"{smallest.title} ({len(smallest.photos)})")
        self.average_per_page_value.setText(f"{mean(len(page.photos) for page in pages):.1f}")

    def _on_page_changed(self, index: int) -> None:
        pages = list(getattr(getattr(self._draft_result, "draft", None), "pages", []) or [])
        if index < 0 or index >= len(pages):
            self._selected_page = None
            self.photo_grid.set_photos([])
            self._clear_page_details()
            return

        page = pages[index]
        self._selected_page = page
        self.photo_grid.set_photos(page.photos)
        self.page_title_value.setText(page.title)
        self.page_photo_count_value.setText(str(len(page.photos)))
        self.page_type_value.setText(page.page_type)
        self.page_explanations_list.clear()
        for line in page.explanation:
            self.page_explanations_list.addItem(str(line))

    def _clear_page_details(self) -> None:
        self.page_title_value.setText("-")
        self.page_photo_count_value.setText("0")
        self.page_type_value.setText("-")
        self.page_explanations_list.clear()

    def update_thumbnail(self, photo, pixmap) -> None:
        if photo is None or pixmap is None:
            return

        photo.thumbnail = pixmap
        visible_keys = {str(getattr(item, "path", "")) for item in getattr(self._selected_page, "photos", [])}
        if str(getattr(photo, "path", "")) in visible_keys:
            self.photo_grid.update_thumbnail(photo, pixmap)

    def page_titles(self) -> list[str]:
        return [self.page_list.item(index).text() for index in range(self.page_list.count())]

    def current_page_title(self) -> str:
        return self.page_title_value.text()

    def visible_photo_filenames(self) -> list[str]:
        return [photo.display_name() for photo in getattr(self.photo_grid, "_photos", [])]

    def select_page_by_title(self, title: str) -> bool:
        target = (title or "").strip()
        if not target:
            return False

        for index in range(self.page_list.count()):
            item = self.page_list.item(index)
            item_title = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if item_title == target or item.text() == target:
                self.page_list.setCurrentRow(index)
                return True

        return False

    def is_empty_state_visible(self) -> bool:
        return self.stack_layout.currentWidget() is self.empty_widget
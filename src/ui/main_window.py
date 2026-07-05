from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from album.album_builder import AlbumBuilder
from album.album_draft_builder import AlbumDraftBuilder
from album.annual_album import AnnualAlbum
from album.album_scoring_engine import AlbumScoringEngine
from album.candidate_selection_engine import CandidateSelectionEngine
from core.photo_scanner import find_photos
from core.safe_file_move_service import CLEANUP_REVIEW_FOLDER_NAME
from models.photo_model import PhotoModel
from ui.album_draft_page import AlbumDraftPage
from ui.album_review_page import AlbumReviewPage
from ui.irrelevant_media_page import IrrelevantMediaPage
from ui.photo_details_panel import PhotoDetailsPanel
from ui.photo_grid_widget import PhotoGridWidget
from workers.thumbnail_worker import ThumbnailWorker


class MainWindow(QMainWindow):
    BROWSER_FILTER_ALL = "All"
    BROWSER_FILTER_FAMILY = "Family photo candidates"
    BROWSER_FILTER_DOCUMENTS = "Documents/scans"
    BROWSER_FILTER_ADVERTISEMENTS = "Advertisements"
    BROWSER_FILTER_SCREENSHOTS = "Screenshots"
    BROWSER_FILTER_MEMES = "Memes/graphics"
    BROWSER_FILTER_VIDEOS = "Videos"
    BROWSER_FILTER_DUPLICATES = "Duplicates"
    BROWSER_FILTER_LOW_QUALITY = "Low quality"
    BROWSER_FILTER_UNKNOWN = "Unknown"

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Family Memory AI")
        self._configure_window_size()

        self.thumbnail_thread = None
        self.thumbnail_worker = None
        self.selected_photo = None
        self._review_cache_signature = None
        self._review_cache_payload = None
        self._current_review_year = None
        self._current_scored_photos = []
        self._all_photos = []
        self._imported_folder = None

        title = QLabel("Family Memory AI")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        import_button = QPushButton("Import Photos")
        import_button.setMinimumHeight(45)
        import_button.setStyleSheet("font-size: 18px;")
        import_button.clicked.connect(self.import_photos)

        self.status_label = QLabel("Choose a folder to import photos.")
        self.status_label.setStyleSheet("font-size: 15px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.photo_model = PhotoModel()
        self.photo_view = PhotoGridWidget()
        self.photo_view.photo_selected.connect(self._handle_photo_selection)
        self.browser_filter_combo = QComboBox()
        self.browser_filter_combo.addItems(
            [
                self.BROWSER_FILTER_ALL,
                self.BROWSER_FILTER_FAMILY,
                self.BROWSER_FILTER_DOCUMENTS,
                self.BROWSER_FILTER_ADVERTISEMENTS,
                self.BROWSER_FILTER_SCREENSHOTS,
                self.BROWSER_FILTER_MEMES,
                self.BROWSER_FILTER_VIDEOS,
                self.BROWSER_FILTER_DUPLICATES,
                self.BROWSER_FILTER_LOW_QUALITY,
                self.BROWSER_FILTER_UNKNOWN,
            ]
        )
        self.browser_filter_combo.currentTextChanged.connect(self._apply_browser_filter)

        self.details_panel = PhotoDetailsPanel()
        self.review_page = AlbumReviewPage()
        self.review_page.review_state_changed.connect(self._refresh_album_draft)
        self.review_page.categories_changed.connect(self._sync_review_category_options)
        self.draft_page = AlbumDraftPage()
        self.irrelevant_media_page = IrrelevantMediaPage()
        self.irrelevant_media_page.categories_changed.connect(self._sync_cleanup_category_options)
        self.irrelevant_media_page.moved_photos.connect(self._handle_irrelevant_media_moved)
        self.irrelevant_media_page.faces_analyzed.connect(self._handle_faces_analyzed)

        browser_page = QWidget()
        browser_layout = QVBoxLayout(browser_page)
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Relevance:"))
        filter_layout.addWidget(self.browser_filter_combo)
        filter_layout.addStretch(1)
        browser_layout.addLayout(filter_layout)
        content_layout = QHBoxLayout()
        content_layout.addWidget(self.photo_view, 1)
        content_layout.addWidget(self.details_panel, 0)
        browser_layout.addLayout(content_layout, 1)

        self.tabs = QTabWidget()
        self.tabs.addTab(browser_page, "Photo Browser")
        self.tabs.addTab(self.review_page, "Album Review")
        self.tabs.addTab(self.irrelevant_media_page, "Cleanup Review")
        self.tabs.addTab(self.draft_page, "Album Draft")

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(import_button)
        layout.addWidget(self.status_label)
        layout.addWidget(self.tabs, 1)

        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)

    def _configure_window_size(self):
        min_width = 1280
        min_height = 820
        preferred_width = 1600
        preferred_height = 1000

        self.setMinimumSize(min_width, min_height)

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(preferred_width, preferred_height)
            return

        available = screen.availableGeometry()
        width = min(preferred_width, max(min_width, available.width() - 80))
        height = min(preferred_height, max(min_height, available.height() - 80))
        self.resize(width, height)

    def import_photos(self):
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select photo folder",
        )

        if not folder_path:
            self.status_label.setText("No folder selected.")
            return

        self._imported_folder = folder_path
        photos = find_photos(folder_path)

        self.status_label.setText(
            f"Found {len(photos)} files. Loading thumbnails progressively in background..."
        )

        self.load_photos(photos)
        self.start_thumbnail_loading(photos)

    def load_photos(self, photos):
        self._all_photos = list(photos or [])
        self.photo_model.set_photos(photos)
        self._apply_browser_filter()
        self._load_irrelevant_media_data(self._all_photos)
        relevant_photos = [photo for photo in self._all_photos if self._is_album_relevant(photo)]
        self._load_album_review_data(relevant_photos)

    def _load_irrelevant_media_data(self, photos):
        irrelevant = [photo for photo in photos or [] if not self._is_album_relevant(photo)]
        self.irrelevant_media_page.set_photos(
            irrelevant,
            self._imported_folder,
            total_imported_count=len(photos or []),
        )

    def _is_album_relevant(self, photo) -> bool:
        intelligence = getattr(photo, "intelligence", None)
        if intelligence is not None:
            return bool(getattr(intelligence, "is_album_relevant_candidate", True))
        return bool(getattr(photo, "is_album_relevant_candidate", True))

    def _apply_browser_filter(self):
        filter_name = self.browser_filter_combo.currentText()
        filtered = [photo for photo in self._all_photos if self._matches_browser_filter(photo, filter_name)]
        self.photo_view.set_photos(filtered)

        if self.selected_photo is not None and all(
            str(getattr(photo, "path", "")) != str(getattr(self.selected_photo, "path", ""))
            for photo in filtered
        ):
            self.selected_photo = None
            self.details_panel.set_photo(None)

    def _matches_browser_filter(self, photo, filter_name: str) -> bool:
        category = self._browser_category(photo)
        if filter_name == self.BROWSER_FILTER_FAMILY:
            return category == "family_photo_candidate"
        if filter_name == self.BROWSER_FILTER_DOCUMENTS:
            return category == "document_or_scan"
        if filter_name == self.BROWSER_FILTER_ADVERTISEMENTS:
            return category == "advertisement"
        if filter_name == self.BROWSER_FILTER_SCREENSHOTS:
            return category == "screenshot"
        if filter_name == self.BROWSER_FILTER_MEMES:
            return category == "meme_or_graphic"
        if filter_name == self.BROWSER_FILTER_VIDEOS:
            return category == "video"
        if filter_name == self.BROWSER_FILTER_DUPLICATES:
            return category == "duplicate_candidate"
        if filter_name == self.BROWSER_FILTER_LOW_QUALITY:
            return category == "low_quality_photo"
        if filter_name == self.BROWSER_FILTER_UNKNOWN:
            return category == "unknown"
        return True

    def _browser_category(self, photo) -> str:
        intelligence = getattr(photo, "intelligence", None)
        if intelligence is not None:
            return str(getattr(intelligence, "relevance_category", "unknown") or "unknown")
        return str(getattr(photo, "relevance_category", "unknown") or "unknown")

    def _load_album_review_data(self, photos):
        self._review_cache_signature = None if not photos else self._review_cache_signature
        signature = self._build_review_signature(photos)
        if signature == self._review_cache_signature and self._review_cache_payload is not None:
            payload = self._review_cache_payload
            self.review_page.set_pipeline_data(
                imported_photos=payload["imported_photos"],
                candidate_photos=payload["candidate_photos"],
                selected_photos=payload["selected_photos"],
                rejected_photos=payload["rejected_photos"],
                scored_breakdowns=payload["scored_breakdowns"],
                rejection_reasons=payload["rejection_reasons"],
            )
            self._current_review_year = payload["chosen_year"]
            self._current_scored_photos = list(payload["scored_photos"])
            self._refresh_album_draft()
            self.status_label.setText(payload["status_text"])
            return

        builder = AlbumBuilder()
        by_year = builder.group_photos_by_year(photos)

        if not by_year:
            self.review_page.set_scored_photos([])
            self._current_review_year = None
            self._current_scored_photos = []
            self.draft_page.set_draft_result(None)
            self.status_label.setText(
                "Files loaded. Album Review needs relevant family photos with usable dates to build a scored list."
            )
            return

        # Pick the largest year bucket as default review scope.
        chosen_year = max(sorted(by_year.keys()), key=lambda year: len(by_year[year]))
        album = AnnualAlbum(
            year=chosen_year,
            photos=list(photos),
            candidate_photos=list(photos),
            selected_photos=[],
            rejected_photos=[],
            status="candidate_selection",
        )

        selection_result = CandidateSelectionEngine().evaluate(album)
        scoring_result = AlbumScoringEngine().score(album)

        scored_by_key = {
            str(getattr(item.photo, "path", "")): item for item in scoring_result.scored_photos
        }
        self.review_page.set_pipeline_data(
            imported_photos=photos,
            candidate_photos=album.candidate_photos,
            selected_photos=album.selected_photos,
            rejected_photos=album.rejected_photos,
            scored_breakdowns=scored_by_key,
            rejection_reasons=selection_result.rejection_reasons,
        )
        self._current_review_year = chosen_year
        self._current_scored_photos = list(scoring_result.scored_photos)
        self._refresh_album_draft()

        rejected_reasons_summary = ", ".join(
            f"{reason}: {count}"
            for reason, count in sorted(selection_result.rejection_reasons.items())
        )
        rejected_reasons_text = (
            f" Rejections: {rejected_reasons_summary}." if rejected_reasons_summary else ""
        )

        self.status_label.setText(
            (
                f"Found {len(photos)} photos. Review loaded with "
                f"{scoring_result.scored_count} scored selected candidates for year {chosen_year}; "
                f"selected={len(album.selected_photos)}, rejected={len(album.rejected_photos)}."
                f"{rejected_reasons_text}"
            )
        )

        self._review_cache_signature = signature
        self._review_cache_payload = {
            "imported_photos": photos,
            "candidate_photos": album.candidate_photos,
            "selected_photos": album.selected_photos,
            "rejected_photos": album.rejected_photos,
            "scored_breakdowns": scored_by_key,
            "scored_photos": list(scoring_result.scored_photos),
            "rejection_reasons": selection_result.rejection_reasons,
            "chosen_year": chosen_year,
            "status_text": self.status_label.text(),
        }

    def _handle_irrelevant_media_moved(self, moved_photos):
        moved_paths = {str(getattr(photo, "path", "")) for photo in moved_photos or []}
        if not moved_paths:
            return

        self._all_photos = [
            photo for photo in self._all_photos
            if str(getattr(photo, "path", "")) not in moved_paths
        ]
        self._review_cache_signature = None
        self._review_cache_payload = None
        self.load_photos(self._all_photos)
        self.status_label.setText(
            f"Cleanup files moved to {Path(self._imported_folder) / CLEANUP_REVIEW_FOLDER_NAME}. Library updated in memory."
        )

    def _handle_faces_analyzed(self, analyzed_photos):
        updated_photos = list(analyzed_photos or [])
        if not updated_photos:
            return

        for photo in updated_photos:
            self.photo_model.refresh_photo_metadata(photo)

        if self.selected_photo is not None:
            selected_path = str(getattr(self.selected_photo, "path", ""))
            for photo in updated_photos:
                if str(getattr(photo, "path", "")) == selected_path:
                    self.details_panel.set_photo(self.selected_photo)
                    break

    def _refresh_album_draft(self):
        if self._current_review_year is None or not self._current_scored_photos:
            self.draft_page.set_draft_result(None)
            return

        draft_result = AlbumDraftBuilder().build(
            year=self._current_review_year,
            scored_photos=list(self._current_scored_photos),
            review_status_by_path=self.review_page.review_status_by_path(),
        )
        self.draft_page.set_draft_result(draft_result)

    def _sync_review_category_options(self):
        self.irrelevant_media_page.refresh_category_options()

    def _sync_cleanup_category_options(self):
        self.review_page.refresh_category_options()

    def _build_review_signature(self, photos):
        return tuple(
            (
                str(getattr(photo, "path", "")),
                getattr(photo, "file_size", 0),
                str(getattr(getattr(photo, "intelligence", None), "date_taken", "")),
            )
            for photo in photos or []
        )

    def start_thumbnail_loading(self, photos):
        print("thumbnail worker started")
        self.thumbnail_thread = QThread()
        self.thumbnail_worker = ThumbnailWorker(photos, batch_size=12, delay_ms=10)

        self.thumbnail_worker.moveToThread(self.thumbnail_thread)

        self.thumbnail_thread.started.connect(self.thumbnail_worker.run)
        self.thumbnail_worker.thumbnail_ready.connect(self.update_thumbnail)
        print("thumbnail_ready connected")
        self.thumbnail_worker.finished.connect(self.thumbnail_thread.quit)
        self.thumbnail_worker.finished.connect(self.thumbnail_worker.deleteLater)
        self.thumbnail_thread.finished.connect(self.thumbnail_thread.deleteLater)

        self.thumbnail_thread.start()

    def update_thumbnail(self, photo, image_or_pixmap):
        print(f"thumbnail signal received: {getattr(photo, 'path', None)}")
        print("Thumbnail received", getattr(photo, "path", None))
        if isinstance(image_or_pixmap, QImage):
            print(f"thumbnail received image null={image_or_pixmap.isNull()}")
        elif isinstance(image_or_pixmap, QPixmap):
            print(f"thumbnail received pixmap null={image_or_pixmap.isNull()}")
        else:
            print(f"thumbnail received type={type(image_or_pixmap).__name__}")

        if isinstance(image_or_pixmap, QImage):
            pixmap = QPixmap.fromImage(image_or_pixmap)
        else:
            pixmap = image_or_pixmap

        if pixmap is None:
            return

        self.photo_model.update_thumbnail(photo, pixmap)
        self.photo_view.update_thumbnail(photo, pixmap)
        self.review_page.update_thumbnail(photo, pixmap)
        self.irrelevant_media_page.update_thumbnail(photo, pixmap)
        self.draft_page.update_thumbnail(photo, pixmap)

        if (
            self.selected_photo is not None
            and str(getattr(self.selected_photo, "path", "")) == str(getattr(photo, "path", ""))
        ):
            self.details_panel.set_photo(self.selected_photo)

    def _handle_photo_selection(self, photo):
        if photo is not None:
            print(f"MainWindow received selected photo: {photo.display_name()}")
        else:
            print("MainWindow received selected photo: None")
        self.selected_photo = photo
        self.details_panel.set_photo(photo)

import logging
import sys
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, QThread, QTimer, Slot
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
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
from ai_runtime.manager import create_default_runtime_manager
from core.application_services import ApplicationServices, build_application_services
from core.perf_stats import (begin_import_performance_session,
                             finish_import_performance_session, get_session_stats)
from core.memory_review_perf import measure_memory_review, record_memory_review
from core.safe_file_move_service import CLEANUP_REVIEW_FOLDER_NAME
from models.photo_model import PhotoModel
from models.photo import Photo
from ui.album_draft_page import AlbumDraftPage
from ui.album_review_page import AlbumReviewPage
from ui.components.workspace_header import WorkspaceHeader
from ui.components.workspace_info_content import WORKSPACE_INFO_CONTENT
from ui.components.workspace_info_panel import WorkspaceInfoPanel
from ui.components.workspace_help_panel import WorkspaceHelpPanel
from ui.help.workspace_help_content import PHOTO_BROWSER_WORKSPACE
from ui.help.workspace_help_registry import WorkspaceHelpRegistry
from ui.irrelevant_media_page import IrrelevantMediaPage
from ui.photo_details_panel import PhotoDetailsPanel
from ui.photo_grid_widget import PhotoGridWidget
from ui.settings_page import SettingsPage
from ui.people_review_page import PeopleReviewPage
from workers.embedding_worker import EmbeddingWorker
from storage.photo_repository import PhotoRepository
from core.trash_workflow_service import TrashRecord
from cache.thumbnail_cache import get_thumbnail_cache_path_for_identity
from vision.batch_embedding_service import embedding_failure_diagnostic_lines
from vision.batch_embedding_service import BatchEmbeddingService
from vision.managed_mobileclip_provider import ManagedMobileCLIPEmbeddingProvider
from workers.scan_worker import ScanCompletion, ScanWorker
from workers.thumbnail_worker import ThumbnailWorker
from workers.face_processing_worker import FaceProcessingWorker
from faces.processing import LocalFaceEmbeddingProvider, LocalOpenCVFaceDetector

logger = logging.getLogger(__name__)


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

    def __init__(self, application_services: ApplicationServices | None = None):
        super().__init__()
        self.application_services = application_services or build_application_services()
        # One composition-owned manager is shared by Settings and import
        # indexing.  Providers may still receive explicit managers in tests.
        self.ai_runtime_manager = create_default_runtime_manager()

        self.setWindowTitle("Family Memory AI")
        self._configure_window_size()

        self.thumbnail_thread = None
        self.thumbnail_worker = None
        self._thumbnail_run_id = 0
        self._active_thumbnail_run_id = 0
        self._pending_thumbnail_photos = None
        self._thumbnail_import_started_at: dict[int, float] = {}
        self.scan_thread = None
        self.scan_worker = None
        self._scan_run_id = 0
        self._active_scan_run_id = 0
        self.embedding_thread = None
        self.embedding_worker = None
        self._embedding_run_id = 0
        self._active_embedding_run_id = 0
        self._pending_embedding_photos = None
        self._embedding_run_lifecycle: dict[int, dict[str, bool]] = {}
        self._pending_import_folder_path = None
        self.face_processing_thread = None
        self.face_processing_worker = None
        self._import_phase = "Idle"
        self._import_generation = 0
        self._current_import_photos = []
        self._embedding_close_requested = False
        self.selected_photo = None
        self._review_cache_signature = None
        self._review_cache_payload = None
        self._current_review_year = None
        self._current_scored_photos = []
        self._all_photos = []
        self._imported_folder = None
        self._import_wall_t0: float = 0.0
        self._first_thumbnail_logged: bool = False
        self._workspace_help_registry = WorkspaceHelpRegistry()
        self._tab_workspace_ids: list[str] = []

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
        self.ai_status_label = QLabel("AI embeddings: not indexed yet")
        self.ai_status_label.setStyleSheet("font-size: 13px; color: #5f6368;")
        self.ai_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        self.review_page.help_requested.connect(self._on_workspace_help_requested)
        self.review_page.review_state_changed.connect(self._refresh_album_draft)
        self.review_page.categories_changed.connect(self._sync_review_category_options)
        self.draft_page = AlbumDraftPage()
        self.draft_page.help_requested.connect(self._on_workspace_help_requested)
        self.irrelevant_media_page = IrrelevantMediaPage()
        self.irrelevant_media_page.help_requested.connect(self._on_workspace_help_requested)
        self.irrelevant_media_page.categories_changed.connect(self._sync_cleanup_category_options)
        self.irrelevant_media_page.moved_photos.connect(self._handle_irrelevant_media_moved)
        self.irrelevant_media_page.active_state_changed.connect(self._handle_trash_active_state_changed)
        self.irrelevant_media_page.history_thumbnails_requested.connect(self.start_thumbnail_loading)
        self.irrelevant_media_page.faces_analyzed.connect(self._handle_faces_analyzed)
        self.settings_page = SettingsPage(
            runtime_manager=self.ai_runtime_manager,
            application_services=self.application_services,
        )
        self.settings_page.help_requested.connect(self._on_workspace_help_requested)
        self.settings_page.set_evaluation_context_providers(
            self._mobileclip_library_photos,
            self._mobileclip_selected_photos,
        )
        self.settings_page.mobileclip_evaluation_requested.connect(self._handle_mobileclip_evaluation_requested)
        self.settings_page.runtime_operation_finished.connect(self._on_runtime_operation_finished)
        self.people_review_page = PeopleReviewPage()
        self.people_review_page.help_requested.connect(self._on_workspace_help_requested)
        self.people_review_page.scan_requested.connect(self._start_face_processing)
        self.people_review_page.pause_requested.connect(self._pause_face_processing)
        self.people_review_page.resume_requested.connect(self._resume_face_processing)
        self.people_review_page.cancel_requested.connect(self._cancel_face_processing)
        self.people_review_page.runtime_settings_requested.connect(self._open_face_runtime_settings)
        self.settings_page.face_runtime_ready_changed.connect(self.people_review_page.set_runtime_ready)
        self.people_review_page.set_runtime_ready(self.settings_page.face_runtime_manager.status().ready)

        browser_page = QWidget()
        browser_layout = QVBoxLayout(browser_page)
        browser_header = WorkspaceHeader("Photo Browser")
        browser_header.help_clicked.connect(lambda: self._on_workspace_help_requested(PHOTO_BROWSER_WORKSPACE))
        browser_info = WORKSPACE_INFO_CONTENT[PHOTO_BROWSER_WORKSPACE]
        self.browser_info_panel = WorkspaceInfoPanel(
            workspace_id=PHOTO_BROWSER_WORKSPACE,
            title=browser_info.title,
            purpose=browser_info.purpose,
            purpose_details=browser_info.purpose_details,
            typical_actions=browser_info.typical_actions,
            tip=browser_info.tip,
            collapsed_label=browser_info.collapsed_label,
        )
        browser_layout.addWidget(browser_header)
        browser_layout.addWidget(self.browser_info_panel)
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
        self.tabs.addTab(self.irrelevant_media_page, "Cleanup Review")
        self.tabs.addTab(self.people_review_page, "People Review")
        self.tabs.addTab(self.review_page, "Memory Review")
        self.tabs.addTab(self.draft_page, "Album Draft")
        self.tabs.addTab(self.settings_page, "Settings")
        self._tab_workspace_ids = [
            PHOTO_BROWSER_WORKSPACE,
            self.irrelevant_media_page.WORKSPACE_ID,
            self.people_review_page.WORKSPACE_ID,
            self.review_page.WORKSPACE_ID,
            self.draft_page.WORKSPACE_ID,
            self.settings_page.WORKSPACE_ID,
        ]
        self.tabs.currentChanged.connect(self._on_tab_changed)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(import_button)
        layout.addWidget(self.status_label)
        layout.addWidget(self.ai_status_label)
        layout.addWidget(self.tabs, 1)

        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)

        self._build_workspace_help_dock()
        self._on_tab_changed(self.tabs.currentIndex())
        self._mobileclip_startup_recovery_scheduled = False
        # Application composition owns the one explicit startup decision; the
        # shared manager remains authoritative for persisted transitions and
        # Settings owns only the worker presentation.
        QTimer.singleShot(0, self._recover_mobileclip_runtime_on_startup)

    def _recover_mobileclip_runtime_on_startup(self) -> None:
        """Schedule at most one verification for recoverable persisted state."""
        if self._mobileclip_startup_recovery_scheduled:
            return
        if not self.ai_runtime_manager.needs_verification_recovery("mobileclip"):
            return
        if not self.ai_runtime_manager.prepare_verification_recovery("mobileclip"):
            return
        self._mobileclip_startup_recovery_scheduled = True
        self.settings_page.start_mobileclip_verification_recovery()

    def closeEvent(self, event):
        self._embedding_close_requested = True
        self._cancel_face_processing()
        self._request_embedding_worker_cancel()
        if self.thumbnail_worker is not None:
            self.thumbnail_worker.cancel()
        app = QCoreApplication.instance()
        while self.embedding_thread is not None and self.embedding_thread.isRunning():
            self.embedding_thread.wait(250)
            if app is not None:
                app.processEvents()
        while self._thumbnail_thread_is_running():
            self.thumbnail_thread.wait(250)
            if app is not None:
                app.processEvents()
        while True:
            face_thread = getattr(self, "face_processing_thread", None)
            if face_thread is None or not face_thread.isRunning():
                break
            face_thread.wait(250)
            if app is not None:
                app.processEvents()
        while True:
            runtime_thread = getattr(getattr(self, "settings_page", None), "_face_runtime_thread", None)
            if runtime_thread is None or not runtime_thread.isRunning():
                break
            runtime_thread.wait(250)
            if app is not None:
                app.processEvents()
        if app is not None:
            app.processEvents()
        super().closeEvent(event)

    def _start_face_processing(self, photos) -> None:
        if self.face_processing_thread is not None:
            return
        self.people_review_page.progress_label.setText(
            f"Preparing local face scan for {len(photos)} eligible photos…"
        )
        thread = QThread(self)
        runtime_status = self.settings_page.face_runtime_manager.status()
        detector = LocalOpenCVFaceDetector(runtime_status.interpreter_path)
        embedder = LocalFaceEmbeddingProvider(interpreter_path=runtime_status.interpreter_path)
        worker = FaceProcessingWorker(photos, self.people_review_page.repository,
                                      detector=detector, embedder=embedder)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.people_review_page.show_scan_progress)
        worker.completed.connect(self.people_review_page.show_scan_completed)
        worker.unavailable.connect(self.people_review_page.show_scan_unavailable)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_face_processing_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self.face_processing_thread, self.face_processing_worker = thread, worker
        thread.start()

    def _open_face_runtime_settings(self) -> None:
        settings_index = self.tabs.indexOf(self.settings_page)
        if settings_index >= 0:
            self.tabs.setCurrentIndex(settings_index)
            QTimer.singleShot(0, self.settings_page.open_face_runtime_section)

    def _pause_face_processing(self) -> None:
        if self.face_processing_worker is not None:
            self.face_processing_worker.pause()
            self.people_review_page.set_scan_state("paused")
            self.people_review_page.progress_label.setText("Local face scan paused safely between photos.")

    def _resume_face_processing(self) -> None:
        if self.face_processing_worker is not None:
            self.face_processing_worker.resume()
            self.people_review_page.set_scan_state("running")
            self.people_review_page.progress_label.setText("Resuming local face scan…")

    def _cancel_face_processing(self) -> None:
        worker = getattr(self, "face_processing_worker", None)
        if worker is not None:
            worker.cancel()
            page = getattr(self, "people_review_page", None)
            if page is not None:
                page.progress_label.setText("Cancelling local face scan safely…")

    def _on_face_processing_thread_finished(self) -> None:
        self.face_processing_worker = None
        self.face_processing_thread = None
        if hasattr(self, "people_review_page"):
            self.people_review_page.set_scan_state("idle")

    def _mobileclip_library_photos(self) -> list:
        return list(self._all_photos or [])

    def _mobileclip_selected_photos(self) -> list:
        current_index = self.tabs.currentIndex() if hasattr(self, "tabs") else -1
        current_label = self.tabs.tabText(current_index) if current_index >= 0 else ""
        if current_label == "Cleanup Review":
            return list(self.irrelevant_media_page.selected_photos())
        if current_label == "Photo Browser" and self.selected_photo is not None:
            return [self.selected_photo]
        cleanup_selected = self.irrelevant_media_page.selected_photos()
        if cleanup_selected:
            return list(cleanup_selected)
        return [self.selected_photo] if self.selected_photo is not None else []

    def _handle_mobileclip_evaluation_requested(self, source_result) -> None:
        self.status_label.setText(
            f"MobileCLIP evaluation ready: {source_result.sample_count} image(s) from {source_result.source_label}."
        )

    def _build_workspace_help_dock(self) -> None:
        self.workspace_help_panel = WorkspaceHelpPanel(self)
        self.workspace_help_panel.close_requested.connect(self._close_workspace_help)

        self.workspace_help_dock = QDockWidget("Workspace Help", self)
        self.workspace_help_dock.setObjectName("workspaceHelpDock")
        self.workspace_help_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.workspace_help_dock.setWidget(self.workspace_help_panel)
        self.workspace_help_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.workspace_help_dock)
        self.workspace_help_dock.hide()

    def _on_tab_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._tab_workspace_ids):
            return
        workspace_id = self._tab_workspace_ids[index]
        if hasattr(self, "settings_page"):
            self.settings_page._refresh_source_summary()
        definition = self._workspace_help_registry.get(workspace_id)
        self.workspace_help_panel.set_help_definition(definition)

    def _on_workspace_help_requested(self, workspace_id: str) -> None:
        definition = self._workspace_help_registry.get(workspace_id)
        self.workspace_help_panel.set_help_definition(definition)
        self.workspace_help_dock.show()
        self.workspace_help_dock.raise_()

    def _close_workspace_help(self) -> None:
        self.workspace_help_dock.hide()

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
        selection_started = time.perf_counter()
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select photo folder",
        )

        if not folder_path:
            self.status_label.setText("No folder selected.")
            return

        # Reset per-session stats and start the wall-clock timer.
        session = begin_import_performance_session(folder_path)
        session.record("Folder selection", (time.perf_counter() - selection_started) * 1000,
                       1, "UI thread")
        self._import_wall_t0 = time.perf_counter()
        self._first_thumbnail_logged = False

        self._imported_folder = folder_path
        self.status_label.setText("Scanning folder…")

        self._queue_or_start_scan(folder_path)

    def _queue_or_start_scan(self, folder_path: str) -> None:
        """Enter the single import state machine or replace its queued request."""
        active = (
            (self.scan_thread is not None and self._scan_thread_is_running(self.scan_thread))
            or self._thumbnail_thread_is_running()
            or self._embedding_thread_is_running()
        )
        if active:
            self._pending_import_folder_path = folder_path
            self._pending_embedding_photos = None
            self._request_embedding_worker_cancel()
            if self.thumbnail_worker is not None:
                self.thumbnail_worker.cancel()
            self._set_embedding_status("Waiting for the current import worker to finish before starting the queued import…")
            self.status_label.setText("Queued new import; finishing the current worker…")
            return
        self._begin_import_scan(folder_path)

    def _begin_import_scan(self, folder_path: str) -> None:
        self._pending_import_folder_path = None
        self._import_generation += 1
        self._import_phase = "Preparing"
        logger.info("Import lifecycle generation=%s phase=Scanning", self._import_generation)
        self._set_embedding_status("Scanning changes…")
        self.status_label.setText("Scanning changes…")
        self._start_scan(folder_path)

    def _start_scan(self, folder_path: str) -> None:
        """Launch folder scanning on a background thread via ScanWorker."""
        # Stop any in-progress scan before starting a new one.
        if self.scan_thread is not None and self._scan_thread_is_running(self.scan_thread):
            self.scan_thread.quit()
            self.scan_thread.wait(2000)

        self._scan_run_id += 1
        run_id = self._scan_run_id
        self._active_scan_run_id = run_id

        thread = QThread()
        thread._family_memory_run_id = run_id
        worker = ScanWorker(folder_path, self.application_services, run_id)
        self.scan_thread = thread
        self.scan_worker = worker
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.scan_complete.connect(self._on_scan_complete)
        worker.scan_error.connect(self._on_scan_error)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        thread.finished.connect(self._on_active_scan_thread_finished, Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(thread.deleteLater)

        thread.start()

    @Slot()
    def _on_active_scan_thread_finished(self) -> None:
        try:
            thread = self.sender()
        except RuntimeError:
            thread = None
        thread = thread or self.scan_thread
        self._on_scan_thread_finished(
            int(getattr(thread, "_family_memory_run_id", 0)), thread
        )

    def _scan_thread_is_running(self, thread) -> bool:
        try:
            return bool(thread.isRunning())
        except RuntimeError:
            if self.scan_thread is thread:
                # A deleted Qt wrapper is still evidence that its run identity
                # was issued.  Preserve that high-water mark before clearing
                # the active references so the next worker cannot reuse it.
                self._scan_run_id = max(
                    self._scan_run_id, self._active_scan_run_id
                )
                self.scan_thread = None
                self.scan_worker = None
                self._active_scan_run_id = 0
            return False

    def _on_scan_thread_finished(self, run_id: int, finished_thread) -> None:
        if run_id != self._active_scan_run_id or self.scan_thread is not finished_thread:
            return
        self.scan_thread = None
        self.scan_worker = None
        self._active_scan_run_id = 0
        if self._pending_import_folder_path is not None:
            folder = self._pending_import_folder_path
            self._begin_import_scan(folder)

    def _on_scan_complete(self, completion) -> None:
        photos = self._apply_scan_completion(completion)
        if photos is None:
            return

        # A newer folder request owns the next transition.  Let this scan's
        # thread-finished cleanup start it; do not create workers for stale data.
        if self._pending_import_folder_path is not None:
            return
        photos = self._reconcile_incremental_photos(photos)
        stats = get_session_stats()
        n = len(photos or [])

        # ── Phase 1 (synchronous, UI thread) ─────────────────────────────────
        # Populate the Photo Browser with placeholder cards.  set_photos() only
        # creates card widgets — no image decoding occurs here — so this is fast
        # regardless of library size.
        t0 = time.perf_counter()
        self._all_photos = list(photos or [])
        people_review_page = getattr(self, "people_review_page", None)
        if people_review_page is not None:
            people_review_page.set_photos(self._all_photos)
        active_photos = [photo for photo in self._all_photos if self._is_active_photo(photo)]
        self.photo_model.set_photos(active_photos)
        self._apply_browser_filter()
        stats.record("UI refresh", (time.perf_counter() - t0) * 1000, n, "UI thread")
        import_result = getattr(self, "_last_import_result", None)
        if import_result is not None:
            stats.inc("reused_photos", int(getattr(import_result, "reused", 0)))

        self.status_label.setText(
            f"Scan complete — showing {n} photos. Loading thumbnails…"
        )

        self._current_import_photos = [
            photo for photo in active_photos
            if getattr(photo, "sync_state", "added") in {"added", "updated"}
        ]
        self._import_phase = "Thumbnail generation"
        logger.info(
            "Import lifecycle generation=%s phase=ScanCompleted submitted=%s next=ThumbnailGeneration",
            self._import_generation, len(self._current_import_photos),
        )
        added = sum(getattr(photo, "sync_state", "added") == "added" for photo in photos or [])
        renamed = sum(getattr(photo, "sync_state", "added") == "renamed" for photo in photos or [])
        self._set_embedding_status(
            f"Reusing existing metadata… Found {added} new photos and {renamed} renamed photos."
        )
        self.start_thumbnail_loading(active_photos)

        # ── Phase 2 & 3 (deferred) ────────────────────────────────────────────
        # Let Qt process the browser repaint first, then set up the secondary
        # views.  Each phase defers the next one the same way so the event loop
        # remains responsive throughout.
        QTimer.singleShot(0, self._deferred_setup_cleanup_review)

    def _apply_scan_completion(self, completion):
        """Publish a matching worker result on the UI thread exactly once."""
        if isinstance(completion, ScanCompletion):
            # Compare with the latest issued run rather than only the active
            # QThread reference: Qt may deliver thread.finished before the
            # queued completion payload. A genuinely newer run increments
            # _scan_run_id and still rejects the stale payload deterministically.
            if (completion.run_id != self._scan_run_id
                    or self._pending_import_folder_path is not None):
                if completion.library is not None:
                    self.application_services.discard_prepared_library(completion.library)
                return None
            if completion.library is not None:
                self.application_services.publish_active_library(completion.library)
                self._refresh_performance_diagnostics_if_available()
            self._last_import_result = completion.import_result
            return completion.photos
        # Direct domain-list calls remain supported by load/lifecycle tests.
        return completion

    def _reconcile_incremental_photos(self, photos: list) -> list:
        """Reuse rich domain objects for unchanged files in the active session."""
        previous_by_id = {
            getattr(photo, "id", None): photo for photo in getattr(self, "_all_photos", [])
            if getattr(photo, "id", None)
        }
        reconciled = []
        for incoming in photos or []:
            state = getattr(incoming, "sync_state", "added")
            existing = previous_by_id.get(getattr(incoming, "id", None))
            if existing is None or state in {"added", "updated"}:
                reconciled.append(incoming)
                continue
            for attribute in (
                "path", "filename", "extension", "file_size", "created_at",
                "modified_at", "modified_time_ns", "sync_state", "previous_path",
            ):
                setattr(existing, attribute, getattr(incoming, attribute))
            reconciled.append(existing)
        return reconciled

    def _start_embedding_indexing(self, photos: list) -> None:
        """Launch import/index embedding generation without blocking the UI."""
        requested_photos = list(photos or [])
        settings_page = getattr(self, "settings_page", None)
        if requested_photos and getattr(settings_page, "_active_runtime_thread", None) is not None:
            # Incremental scans can finish before startup verification. Keep the
            # same shared-manager lifecycle as before and resume only after the
            # authoritative runtime operation reaches a terminal state.
            self._pending_embedding_photos = requested_photos
            self._set_embedding_status("Waiting for MobileCLIP verification to finish…")
            return
        if self._embedding_thread_is_running():
            self._pending_embedding_photos = requested_photos
            self._request_embedding_worker_cancel()
            return

        self._launch_embedding_worker(requested_photos)

    @Slot(str)
    def _on_runtime_operation_finished(self, _operation: str) -> None:
        pending = self._pending_embedding_photos
        if pending is None or self._embedding_thread_is_running():
            return
        self._pending_embedding_photos = None
        self._launch_embedding_worker(pending)

    def _embedding_thread_is_running(self) -> bool:
        """Return thread state while discarding a deleted Qt wrapper safely."""
        thread = self.embedding_thread
        if thread is None:
            return False
        try:
            return bool(thread.isRunning())
        except RuntimeError:
            self._embedding_run_lifecycle.pop(self._active_embedding_run_id, None)
            self.embedding_thread = None
            self.embedding_worker = None
            self._active_embedding_run_id = 0
            return False

    def _launch_embedding_worker(self, photos: list) -> None:
        queue_started = time.perf_counter()
        self._embedding_run_id += 1
        run_id = self._embedding_run_id
        self._active_embedding_run_id = run_id

        thread = QThread()
        thread._family_memory_run_id = run_id
        worker = EmbeddingWorker(
            photos,
            service_factory=lambda: BatchEmbeddingService(
                provider=ManagedMobileCLIPEmbeddingProvider(
                    runtime_manager=self.ai_runtime_manager
                )
            ),
            run_id=run_id,
        )
        self.embedding_thread = thread
        self.embedding_worker = worker
        get_session_stats().record("Embedding queue creation",
                                   (time.perf_counter() - queue_started) * 1000,
                                   len(photos), "UI thread")
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        # Use QObject-bound queued slots rather than context-free lambdas.  The
        # latter may execute Python UI work on the worker thread on some PySide6
        # builds, which made a cache-fast second import especially crash-prone.
        self._embedding_run_lifecycle[run_id] = {"thread_finished": False, "terminal_state": None}
        worker.progress.connect(self._on_embedding_progress_for_run, Qt.ConnectionType.QueuedConnection)
        worker.complete.connect(self._on_embedding_complete_for_run, Qt.ConnectionType.QueuedConnection)
        worker.error.connect(self._on_embedding_error_for_run, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        thread.finished.connect(self._on_active_embedding_thread_finished, Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(thread.deleteLater)

        thread.start()

    @Slot(int, object)
    def _on_embedding_progress_for_run(self, run_id: int, progress) -> None:
        if run_id in self._embedding_run_lifecycle:
            self._on_embedding_progress(run_id, progress)

    @Slot(int, object)
    def _on_embedding_complete_for_run(self, run_id: int, result) -> None:
        lifecycle = self._embedding_run_lifecycle.get(run_id)
        if lifecycle is None or lifecycle["terminal_state"] is not None:
            return
        try:
            self._on_embedding_complete(run_id, result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Embedding terminal callback failed run_id=%s", run_id)
            self._set_embedding_status(f"Embedding completion failed: {exc}", severity="error")
            lifecycle["terminal_state"] = "Failed"
        else:
            processed = int(getattr(result, "processed_successfully", 0) or 0)
            cached = int(getattr(result, "skipped_cached", 0) or 0)
            failed = int(getattr(result, "failed", 0) or 0)
            cancelled = int(getattr(result, "cancelled", 0) or 0)
            lifecycle["terminal_state"] = (
                "Cancelled" if cancelled
                else "Failed" if failed and not (processed or cached)
                else "Completed"
            )
        finally:
            self._finalize_embedding_run(run_id)

    @Slot(int, str)
    def _on_embedding_error_for_run(self, run_id: int, message: str) -> None:
        lifecycle = self._embedding_run_lifecycle.get(run_id)
        if lifecycle is None or lifecycle["terminal_state"] is not None:
            return
        try:
            self._on_embedding_error(run_id, message)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Embedding error callback failed run_id=%s", run_id)
            self._set_embedding_status(f"Embedding failure reporting failed: {exc}", severity="error")
            lifecycle["terminal_state"] = "Failed"
        finally:
            lifecycle["terminal_state"] = "Failed"
            self._finalize_embedding_run(run_id)

    @Slot()
    def _on_active_embedding_thread_finished(self) -> None:
        try:
            thread = self.sender()
        except RuntimeError:
            thread = None
        thread = thread or self.embedding_thread
        self._on_embedding_thread_finished(int(getattr(thread, "_family_memory_run_id", 0)))

    def _request_embedding_worker_cancel(self) -> None:
        """Cooperatively request cancellation without destroying a running QThread."""
        if self.embedding_worker is not None:
            self.embedding_worker.cancel()

    def _on_embedding_thread_finished(self, run_id: int) -> None:
        lifecycle = self._embedding_run_lifecycle.get(run_id)
        if lifecycle is None:
            return
        lifecycle["thread_finished"] = True
        self._finalize_embedding_run(run_id)

    def _finalize_embedding_run(self, run_id: int) -> None:
        """Clean up only after both terminal result and thread exit arrived."""
        lifecycle = self._embedding_run_lifecycle.get(run_id)
        if lifecycle is None or not lifecycle["thread_finished"] or lifecycle["terminal_state"] is None:
            return
        self._embedding_run_lifecycle.pop(run_id, None)
        if run_id != self._active_embedding_run_id:
            return
        self.embedding_thread = None
        self.embedding_worker = None
        self._active_embedding_run_id = 0
        logger.info("Import lifecycle generation=%s embedding_run=%s cleanup=complete", self._import_generation, run_id)

        if self._embedding_close_requested:
            return

        pending_folder = self._pending_import_folder_path
        if pending_folder is not None:
            self._begin_import_scan(pending_folder)
            return

        pending_photos = self._pending_embedding_photos
        self._pending_embedding_photos = None
        if pending_photos is not None:
            self._launch_embedding_worker(pending_photos)
            return
        self._import_phase = str(lifecycle["terminal_state"])
        logger.info("Import lifecycle generation=%s phase=%s", self._import_generation, self._import_phase)
        session = finish_import_performance_session()
        session.print_summary()
        self._refresh_performance_diagnostics_if_available()

    def _refresh_performance_diagnostics_if_available(self) -> None:
        """Refresh optional diagnostics without making it a lifecycle dependency.

        Lightweight lifecycle harnesses and shutdown paths may not own Settings.
        A refresh failure is reported, but cannot invalidate an otherwise
        completed import or recreate any UI/storage objects.
        """
        settings_page = getattr(self, "settings_page", None)
        refresh = getattr(settings_page, "refresh_developer_diagnostics", None)
        if not callable(refresh):
            return
        try:
            refresh()
        except Exception:  # noqa: BLE001
            logger.exception("Optional performance diagnostics refresh failed")

    def _on_embedding_progress(self, run_id: int, progress) -> None:
        if run_id != self._active_embedding_run_id:
            return
        self._set_embedding_status(
            f"Indexing semantic embeddings {progress.current_index}/{progress.total_count} "
            f"(new={progress.processed_count}, reused={progress.cached_count}, failed={progress.failed_count})…"
        )

    def _on_embedding_complete(self, run_id: int, result) -> None:
        if run_id != self._active_embedding_run_id:
            return
        print(
            "[EmbeddingIndex] "
            f"processed={getattr(result, 'processed_successfully', 0)} "
            f"cached={getattr(result, 'skipped_cached', 0)} "
            f"failed={getattr(result, 'failed', 0)} "
            f"cancelled={getattr(result, 'cancelled', 0)} "
            f"elapsed={getattr(result, 'elapsed_seconds', 0.0):.3f}s",
            file=sys.stderr,
            flush=True,
        )
        for line in embedding_failure_diagnostic_lines(result, limit=3):
            print(line, file=sys.stderr, flush=True)

        processed = int(getattr(result, "processed_successfully", 0) or 0)
        cached = int(getattr(result, "skipped_cached", 0) or 0)
        failed = int(getattr(result, "failed", 0) or 0)
        cancelled = int(getattr(result, "cancelled", 0) or 0)
        received = int(getattr(result, "total_images_received", 0) or 0)
        get_session_stats().inc("embedded_photos", processed)
        get_session_stats().inc("embedding_cache_hits", cached)
        ready = processed + cached
        total = ready + failed + cancelled
        self._import_phase = "Cache reuse" if cached else "Embedding indexing"
        if received <= 0:
            self._set_embedding_status(
                "AI embeddings: no eligible photos to index.",
                severity="success",
            )
        elif cancelled:
            self._set_embedding_status(
                "⚠ Semantic embedding indexing cancelled. "
                f"{processed} new · {cached} reused · {failed} failed",
                severity="warning",
            )
        elif failed and not processed and not cached:
            self._set_embedding_status(
                "✕ Semantic embedding indexing failed. "
                f"0 ready · {failed} failed",
                severity="error",
            )
        elif failed:
            self._set_embedding_status(
                f"⚠ AI embeddings ready: {ready}/{total}. "
                f"{processed} new · {cached} reused · {failed} failed",
                severity="warning",
            )
        elif processed and not cached:
            self._set_embedding_status(
                f"✓ Semantic embedding indexing completed. {processed} new embeddings "
                f"created · 0 reused · 0 failed",
                severity="success",
            )
        else:
            self._set_embedding_status(
                f"✓ Semantic embeddings ready: {ready}/{total}. "
                f"{processed} new · {cached} reused from cache · 0 failed",
                severity="success",
            )
        if ready and not cancelled:
            self._on_embedding_index_updated(result)

    def _set_embedding_status(self, message: str, severity: str = "progress") -> None:
        """Update the dedicated persistent AI status (or test-compatible fallback)."""
        label = getattr(self, "ai_status_label", self.status_label)
        label.setText(message)
        colors = {
            "success": "#137333",
            "warning": "#b06000",
            "error": "#b3261e",
            "progress": "#5f6368",
        }
        if hasattr(label, "setStyleSheet"):
            label.setStyleSheet(f"font-size: 13px; color: {colors[severity]};")

    def _on_embedding_index_updated(self, result) -> None:
        _ = result
        review_page = getattr(self, "review_page", None)
        if review_page is not None and hasattr(
            review_page, "on_embedding_index_updated"
        ):
            review_page.on_embedding_index_updated()

    def _on_embedding_error(self, run_id: int, error_message: str) -> None:
        if run_id != self._active_embedding_run_id:
            return
        print(f"[EmbeddingIndex] error: {error_message}", file=sys.stderr, flush=True)
        self._set_embedding_status(
            f"✕ Semantic embedding indexing failed. {error_message}",
            severity="error",
        )

    def _deferred_setup_cleanup_review(self) -> None:
        """Populate Cleanup Review — deferred from _on_scan_complete."""
        self.status_label.setText("Preparing Cleanup Review in background…")
        t0 = time.perf_counter()
        try:
            self._load_irrelevant_media_data(self._all_photos)
        except Exception as exc:  # noqa: BLE001
            print(f"[MainWindow] Cleanup Review setup error: {exc}", file=sys.stderr, flush=True)
        finally:
            get_session_stats().record(
                "Cleanup Review preparation", (time.perf_counter() - t0) * 1000,
                len(self._all_photos), "UI thread"
            )
        QTimer.singleShot(0, self._deferred_setup_memory_review)

    def _deferred_setup_memory_review(self) -> None:
        """Populate Memory Review and Album Draft — deferred from _deferred_setup_cleanup_review."""
        self.status_label.setText("Preparing Memory Review…")
        active = [p for p in self._all_photos if self._is_active_photo(p)]
        relevant = [p for p in active if self._is_album_relevant(p)]
        t0 = time.perf_counter()
        try:
            self._load_album_review_data(relevant_photos=relevant, imported_photos=active)
        except Exception as exc:  # noqa: BLE001
            print(f"[MainWindow] Memory Review setup error: {exc}", file=sys.stderr, flush=True)
            self.status_label.setText("Memory Review preparation encountered an error.")
        finally:
            get_session_stats().record(
                "Memory Review preparation", (time.perf_counter() - t0) * 1000,
                len(relevant), "UI thread"
            )
            get_session_stats().record("Album Draft preparation",
                                       (time.perf_counter() - t0) * 1000,
                                       len(relevant), "UI thread")

    def _on_scan_error(self, error_message: str) -> None:
        self._import_phase = "Completed"
        self.status_label.setText(f"Scan error: {error_message}")
        self._set_embedding_status(f"Import scan failed: {error_message}", severity="error")

    def load_photos(self, photos):
        self._all_photos = list(photos or [])
        people_review_page = getattr(self, "people_review_page", None)
        if people_review_page is not None:
            people_review_page.set_photos(self._all_photos)
        active = [photo for photo in self._all_photos if self._is_active_photo(photo)]
        self.photo_model.set_photos(active)
        self._apply_browser_filter()
        self._start_embedding_indexing(active)
        self._load_irrelevant_media_data(self._all_photos)
        relevant_photos = [photo for photo in active if self._is_album_relevant(photo)]
        self._load_album_review_data(relevant_photos=relevant_photos, imported_photos=active)

    def _load_irrelevant_media_data(self, photos):
        irrelevant = [photo for photo in photos or []
                      if (not self._is_album_relevant(photo)
                          or bool((getattr(photo, "metadata", {}) or {}).get("trash_workflow_state"))
                          or (getattr(photo, "metadata", {}) or {}).get("effective_media_category") == "to_trash")]
        known_ids = {str(getattr(photo, "id", "")) for photo in irrelevant}
        store = self.application_services.metadata_store
        if store.library_id:
            for item in PhotoRepository(store).list_trash_history():
                if str(item["photo_id"]) in known_ids:
                    continue
                path = Path(str(item.get("destination_path") or ""))
                if not path.is_file():
                    continue
                photo = Photo.from_path(path)
                photo.id = str(item["photo_id"])
                photo.metadata.update(item)
                photo.metadata["trash_original_path"] = str(item.get("source_path") or "")
                photo.metadata["trash_destination_path"] = str(item.get("destination_path") or "")
                photo.metadata["trash_moved_at"] = str(item.get("created_at") or "")
                photo.metadata["trash_move_error"] = str(item.get("error") or "")
                cached = get_thumbnail_cache_path_for_identity(
                    str(item.get("source_path") or ""), int(item.get("modified_time_ns") or 0),
                    int(item.get("file_size") or 0),
                )
                if cached.is_file():
                    photo.thumbnail_path = str(cached)
                    photo.metadata["thumbnail_path"] = str(cached)
                irrelevant.append(photo)
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

    @staticmethod
    def _is_active_photo(photo) -> bool:
        metadata = getattr(photo, "metadata", {}) or {}
        return bool(metadata.get("is_active", True)) and metadata.get("trash_workflow_state") != "moved_to_trash"

    def _apply_browser_filter(self):
        filter_name = self.browser_filter_combo.currentText()
        filtered = [photo for photo in self._all_photos
                    if self._is_active_photo(photo) and self._matches_browser_filter(photo, filter_name)]
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

    def _load_album_review_data(self, relevant_photos, imported_photos=None):
        load_started = time.perf_counter()
        imported = list(imported_photos or relevant_photos or [])
        relevant = list(relevant_photos or [])
        imported_count = len(imported)
        relevant_count = len(relevant)

        # If classification marks every item as non-relevant, keep Memory Review usable
        # by falling back to the imported set and reporting this in diagnostics.
        review_input = relevant if relevant else list(imported)
        fallback_to_imported = bool(imported_count and not relevant_count)

        self._review_cache_signature = None if not review_input else self._review_cache_signature
        signature = self._build_review_signature(review_input)
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
            self._log_memory_review_diagnostics(
                imported=imported_count,
                relevant=relevant_count,
                year_buckets=len(payload.get("by_year", {})),
                chosen_year=payload.get("chosen_year"),
                candidates=len(payload["candidate_photos"]),
                selected=len(payload["selected_photos"]),
                scored=len(payload["scored_photos"]),
                fallback_to_imported=fallback_to_imported,
            )
            return

        builder = AlbumBuilder()
        with measure_memory_review("Database reads", items=0):
            # Memory Review consumes the already-rehydrated projection. Keeping
            # this explicit zero-read span guards against accidental UI SQL.
            pass
        by_year = builder.group_photos_by_year(review_input)

        if not by_year:
            self.review_page.set_scored_photos([])
            missing_date_count = 0
            for photo in review_input:
                intelligence = getattr(photo, "intelligence", None)
                has_year = isinstance(getattr(intelligence, "year", None), int)
                if not has_year:
                    missing_date_count += 1

            empty_reason = (
                "Memory Review is empty: no photos with usable dates "
                f"(imported={imported_count}, relevant={relevant_count}, missing_year={missing_date_count})."
            )
            self.review_page.set_empty_reason(empty_reason)
            self._current_review_year = None
            self._current_scored_photos = []
            self.draft_page.set_draft_result(None)
            self.status_label.setText(empty_reason)
            self._log_memory_review_diagnostics(
                imported=imported_count,
                relevant=relevant_count,
                year_buckets=0,
                chosen_year=None,
                candidates=0,
                selected=0,
                scored=0,
                fallback_to_imported=fallback_to_imported,
            )
            return

        # Pick the largest year bucket as default review scope.
        chosen_year = max(sorted(by_year.keys()), key=lambda year: len(by_year[year]))
        album = AnnualAlbum(
            year=chosen_year,
            photos=list(review_input),
            candidate_photos=list(review_input),
            selected_photos=[],
            rejected_photos=[],
            status="candidate_selection",
        )

        selection_result = CandidateSelectionEngine().evaluate(album)
        with measure_memory_review("Score retrieval", items=len(review_input)):
            scoring_result = AlbumScoringEngine().score(album)

        scored_by_key = {
            str(getattr(item.photo, "path", "")): item for item in scoring_result.scored_photos
        }
        self.review_page.set_pipeline_data(
            imported_photos=review_input,
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
                f"Found {len(review_input)} review input photos "
                f"(imported={imported_count}, relevant={relevant_count}, "
                f"fallback_to_imported={fallback_to_imported}). "
                f"Review loaded with "
                f"{scoring_result.scored_count} scored selected candidates for year {chosen_year}; "
                f"selected={len(album.selected_photos)}, rejected={len(album.rejected_photos)}."
                f"{rejected_reasons_text}"
            )
        )

        self._log_memory_review_diagnostics(
            imported=imported_count,
            relevant=relevant_count,
            year_buckets=len(by_year),
            chosen_year=chosen_year,
            candidates=len(album.candidate_photos),
            selected=len(album.selected_photos),
            scored=scoring_result.scored_count,
            fallback_to_imported=fallback_to_imported,
        )

        self._review_cache_signature = signature
        self._review_cache_payload = {
            "imported_photos": review_input,
            "candidate_photos": album.candidate_photos,
            "selected_photos": album.selected_photos,
            "rejected_photos": album.rejected_photos,
            "scored_breakdowns": scored_by_key,
            "scored_photos": list(scoring_result.scored_photos),
            "rejection_reasons": selection_result.rejection_reasons,
            "chosen_year": chosen_year,
            "by_year": by_year,
            "status_text": self.status_label.text(),
        }
        record_memory_review(
            "Memory Review load", (time.perf_counter() - load_started) * 1000.0,
            items=len(review_input),
        )

    def _log_memory_review_diagnostics(
        self,
        *,
        imported: int,
        relevant: int,
        year_buckets: int,
        chosen_year,
        candidates: int,
        selected: int,
        scored: int,
        fallback_to_imported: bool,
    ) -> None:
        diagnostics = (
            "[MemoryReview Diagnostics]\n"
            f"imported={int(imported)}\n"
            f"relevant={int(relevant)}\n"
            f"year_buckets={int(year_buckets)}\n"
            f"chosen_year={chosen_year if chosen_year is not None else '-'}\n"
            f"candidates={int(candidates)}\n"
            f"selected={int(selected)}\n"
            f"scored={int(scored)}\n"
            f"all_rows={self.review_page.all_row_count()}\n"
            f"visible_rows={self.review_page.visible_row_count()}\n"
            f"rendered_cards={self.review_page.rendered_card_count()}\n"
            f"thumbnail_cache={self.review_page.retained_thumbnail_count()}\n"
            f"fallback_to_imported={str(bool(fallback_to_imported)).lower()}"
        )
        print(diagnostics, file=sys.stderr, flush=True)

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

    def _handle_trash_active_state_changed(self, _photos):
        """Refresh active consumers once; Cleanup Review retains its history rows."""
        changed = list(_photos or [])
        store = self.application_services.metadata_store
        if store.library_id:
            records = []
            for photo in changed:
                metadata = getattr(photo, "metadata", {}) or {}
                if getattr(photo, "id", None):
                    records.append(TrashRecord(
                        str(photo.id), str(metadata.get("trash_original_path", photo.path)),
                        state=str(metadata.get("trash_workflow_state", "restored")),
                        destination_path=str(metadata.get("trash_destination_path", photo.path)),
                        error=str(metadata.get("trash_move_error", "")),
                        history=list(metadata.get("trash_history", [])),
                    ))
            if records:
                PhotoRepository(store).apply_trash_results(records)
        active = [photo for photo in self._all_photos if self._is_active_photo(photo)]
        self.photo_model.set_photos(active)
        self._apply_browser_filter()
        self._review_cache_signature = None
        self._review_cache_payload = None
        relevant = [photo for photo in active if self._is_album_relevant(photo)]
        self._load_album_review_data(relevant_photos=relevant, imported_photos=active)

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
        """Serialize thumbnail jobs so a repeated import cannot orphan a QThread."""
        requested_photos = list(photos or [])
        if self._thumbnail_thread_is_running():
            self._pending_thumbnail_photos = requested_photos
            self.thumbnail_worker.cancel()
            return

        self._launch_thumbnail_worker(requested_photos)

    def _thumbnail_thread_is_running(self) -> bool:
        thread = self.thumbnail_thread
        if thread is None:
            return False
        try:
            return bool(thread.isRunning())
        except RuntimeError:
            self.thumbnail_thread = None
            self.thumbnail_worker = None
            self._active_thumbnail_run_id = 0
            return False

    def _launch_thumbnail_worker(self, photos) -> None:
        self._thumbnail_run_id += 1
        run_id = self._thumbnail_run_id
        self._active_thumbnail_run_id = run_id
        # Capture the import timer owned by this run.  A superseded thumbnail
        # worker may finish after the user has started another import; it must
        # not consume or reset the newer import's wall-clock measurement.
        self._thumbnail_import_started_at[run_id] = self._import_wall_t0
        thread = QThread()
        thread._family_memory_run_id = run_id
        worker = ThumbnailWorker(photos, batch_size=20, delay_ms=0)
        self.thumbnail_thread = thread
        self.thumbnail_worker = worker

        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.thumbnail_ready.connect(self.update_thumbnail)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        thread.finished.connect(self._on_active_thumbnail_thread_finished, Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(thread.deleteLater)

        thread.start()

    @Slot()
    def _on_active_thumbnail_thread_finished(self) -> None:
        try:
            thread = self.sender()
        except RuntimeError:
            thread = None
        thread = thread or self.thumbnail_thread
        self._on_thumbnail_thread_finished(
            int(getattr(thread, "_family_memory_run_id", 0)), thread
        )

    def _on_thumbnail_thread_finished(self, run_id: int, finished_thread) -> None:
        if run_id != self._active_thumbnail_run_id or self.thumbnail_thread is not finished_thread:
            self._thumbnail_import_started_at.pop(run_id, None)
            return
        self._on_thumbnail_worker_finished(run_id)
        self.thumbnail_thread = None
        self.thumbnail_worker = None
        self._active_thumbnail_run_id = 0
        if self._embedding_close_requested:
            self._pending_thumbnail_photos = None
            return
        if self._pending_import_folder_path is not None:
            folder = self._pending_import_folder_path
            self._pending_thumbnail_photos = None
            self._begin_import_scan(folder)
            return
        pending = self._pending_thumbnail_photos
        self._pending_thumbnail_photos = None
        if pending is not None:
            self._launch_thumbnail_worker(pending)
            return
        photos = self._current_import_photos
        self._import_phase = "Embedding indexing"
        logger.info(
            "Import lifecycle generation=%s phase=Indexing submitted=%s",
            self._import_generation, len(photos),
        )
        self._set_embedding_status("Indexing semantic embeddings: starting…")
        self._start_embedding_indexing(photos)

    def _on_thumbnail_worker_finished(self, run_id: int) -> None:
        """Record timing only for the import that owns this finished run."""
        started_at = self._thumbnail_import_started_at.pop(run_id, 0.0)
        if started_at > 0 and started_at == self._import_wall_t0:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            get_session_stats().record("total_import_wall_clock [UI]", elapsed_ms)
            self._import_wall_t0 = 0.0
            get_session_stats().print_summary()

    def update_thumbnail(self, photo, image_or_pixmap):
        # Record the first thumbnail arrival time once per session.
        if not self._first_thumbnail_logged and self._import_wall_t0 > 0:
            elapsed_ms = (time.perf_counter() - self._import_wall_t0) * 1000
            get_session_stats().record("time_to_first_thumbnail [UI]", elapsed_ms)
            self._first_thumbnail_logged = True

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
        self.selected_photo = photo
        self.details_panel.set_photo(photo)
        if hasattr(self, "settings_page"):
            self.settings_page._refresh_source_summary()

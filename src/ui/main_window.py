from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.photo_scanner import find_photos
from models.photo_model import PhotoModel
from ui.photo_details_panel import PhotoDetailsPanel
from ui.photo_grid_widget import PhotoGridWidget
from workers.thumbnail_worker import ThumbnailWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Family Memory AI")
        self.setMinimumSize(1000, 700)

        self.thumbnail_thread = None
        self.thumbnail_worker = None

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

        self.details_panel = PhotoDetailsPanel()

        content_layout = QHBoxLayout()
        content_layout.addWidget(self.photo_view, 1)
        content_layout.addWidget(self.details_panel, 0)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(import_button)
        layout.addWidget(self.status_label)
        layout.addLayout(content_layout)

        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)

    def import_photos(self):
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select photo folder",
        )

        if not folder_path:
            self.status_label.setText("No folder selected.")
            return

        photos = find_photos(folder_path)

        self.status_label.setText(
            f"Found {len(photos)} photos. Loading thumbnails progressively in background..."
        )

        self.load_photos(photos)
        self.start_thumbnail_loading(photos)

    def load_photos(self, photos):
        self.photo_model.set_photos(photos)
        self.photo_view.set_photos(photos)

    def start_thumbnail_loading(self, photos):
        self.thumbnail_thread = QThread()
        self.thumbnail_worker = ThumbnailWorker(photos, batch_size=12, delay_ms=10)

        self.thumbnail_worker.moveToThread(self.thumbnail_thread)

        self.thumbnail_thread.started.connect(self.thumbnail_worker.run)
        self.thumbnail_worker.thumbnail_ready.connect(self.update_thumbnail)
        self.thumbnail_worker.finished.connect(self.thumbnail_thread.quit)
        self.thumbnail_worker.finished.connect(self.thumbnail_worker.deleteLater)
        self.thumbnail_thread.finished.connect(self.thumbnail_thread.deleteLater)

        self.thumbnail_thread.start()

    def update_thumbnail(self, photo, pixmap):
        self.photo_model.update_thumbnail(photo, pixmap)
        self.photo_view.update_thumbnail(photo, pixmap)
        self.details_panel.set_photo(photo)

    def _handle_photo_selection(self, photo):
        if photo is not None:
            print(f"MainWindow received selected photo: {photo.display_name()}")
        else:
            print("MainWindow received selected photo: None")
        self.details_panel.set_photo(photo)

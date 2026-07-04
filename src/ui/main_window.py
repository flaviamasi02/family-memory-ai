from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QGridLayout,
    QWidget,
)


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class ThumbnailWorker(QObject):
    thumbnail_ready = Signal(str, QPixmap)
    finished = Signal()

    def __init__(self, photos, thumbnail_size=160):
        super().__init__()
        self.photos = photos
        self.thumbnail_size = thumbnail_size

    def run(self):
        for photo_path in self.photos:
            pixmap = QPixmap(str(photo_path))
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    self.thumbnail_size,
                    self.thumbnail_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.thumbnail_ready.emit(str(photo_path), pixmap)

        self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Family Memory AI")
        self.setMinimumSize(1000, 700)

        self.thumbnail_labels = []
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

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(12)
        self.grid_widget.setLayout(self.grid_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.grid_widget)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(import_button)
        layout.addWidget(self.status_label)
        layout.addWidget(scroll_area)

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

        photos = self.find_photos(folder_path)
        photos_to_show = photos[:300]

        self.status_label.setText(
            f"Found {len(photos)} photos. Loading first {len(photos_to_show)} thumbnails..."
        )

        self.show_loading_grid(photos_to_show)
        self.start_thumbnail_loading(photos_to_show)

    def find_photos(self, folder_path):
        folder = Path(folder_path)

        return [
            file
            for file in folder.rglob("*")
            if file.suffix.lower() in SUPPORTED_EXTENSIONS
        ]

    def show_loading_grid(self, photos):
        self.clear_grid()

        columns = 5
        thumbnail_size = 160
        self.thumbnail_labels = []

        for index, photo_path in enumerate(photos):
            row = index // columns
            column = index % columns

            label = QLabel("Loading...")
            label.setFixedSize(thumbnail_size, thumbnail_size)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("border: 1px solid #cccccc; color: #777777;")

            self.thumbnail_labels.append(label)
            self.grid_layout.addWidget(label, row, column)

    def start_thumbnail_loading(self, photos):
        self.thumbnail_thread = QThread()
        self.thumbnail_worker = ThumbnailWorker(photos)

        self.thumbnail_worker.moveToThread(self.thumbnail_thread)

        self.thumbnail_thread.started.connect(self.thumbnail_worker.run)
        self.thumbnail_worker.thumbnail_ready.connect(self.update_thumbnail)
        self.thumbnail_worker.finished.connect(self.thumbnail_thread.quit)
        self.thumbnail_worker.finished.connect(self.thumbnail_worker.deleteLater)
        self.thumbnail_thread.finished.connect(self.thumbnail_thread.deleteLater)

        self.thumbnail_thread.start()

    def update_thumbnail(self, photo_path, pixmap):
        index = None

        for i, label in enumerate(self.thumbnail_labels):
            if i < len(self.thumbnail_labels):
                index = i
                break

        # Find the first label still showing "Loading..."
        for label in self.thumbnail_labels:
            if label.text() == "Loading...":
                label.setPixmap(pixmap)
                label.setText("")
                break

    def clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
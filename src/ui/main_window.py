from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Family Memory AI")
        self.setMinimumSize(800, 600)

        label = QLabel("Welcome to Family Memory AI")
        label.setStyleSheet("font-size: 24px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.setCentralWidget(label)
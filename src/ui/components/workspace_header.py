from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class WorkspaceHeader(QWidget):
    """Reusable workspace title row with a right-aligned help action."""

    help_clicked = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(parent)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 600;")

        self.help_button = QPushButton("? Help")
        self.help_button.setToolTip("Open workspace guide")
        self.help_button.clicked.connect(self.help_clicked.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.title_label)
        layout.addStretch(1)
        layout.addWidget(self.help_button)

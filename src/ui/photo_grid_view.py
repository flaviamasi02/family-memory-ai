from PySide6.QtCore import QSize
from PySide6.QtWidgets import QListView


class PhotoGridView(QListView):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setSpacing(12)
        self.setWordWrap(True)
        self.setGridSize(QSize(180, 210))
        self.setIconSize(QSize(160, 160))
        self.setUniformItemSizes(True)
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)

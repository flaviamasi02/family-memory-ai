from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import QListView


class PhotoGridView(QListView):
    selected_photo_changed = Signal(object)

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

        self.clicked.connect(self.handle_click)

    def handle_click(self, index):
        if not index.isValid():
            return

        model = self.model()
        if model is None:
            return

        if hasattr(model, "get_photo_at_row"):
            photo = model.get_photo_at_row(index.row())
        elif hasattr(model, "get_photo"):
            photo = model.get_photo(index)
        else:
            photo = None

        if photo is not None:
            self.selected_photo_changed.emit(photo)

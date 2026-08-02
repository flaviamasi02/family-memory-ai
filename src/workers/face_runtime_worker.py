from PySide6.QtCore import QObject, Signal


class FaceRuntimeWorker(QObject):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, manager, operation):
        super().__init__(); self.manager, self.operation = manager, operation

    def run(self):
        try:
            result = getattr(self.manager, self.operation)(lambda value, text: self.progress.emit(value, text))
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()

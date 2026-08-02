from threading import Event
from PySide6.QtCore import QObject, Signal


class FaceRuntimeWorker(QObject):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, manager, operation):
        super().__init__(); self.manager, self.operation = manager, operation; self.cancel_event = Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            result = getattr(self.manager, self.operation)(lambda value, text: self.progress.emit(value, text), self.cancel_event)
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()

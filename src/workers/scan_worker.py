"""
Background worker that runs folder scanning and metadata extraction
off the UI thread so the main window stays responsive during import.

Emits:
  scan_complete(list)  — when find_photos() finishes; payload is list[Photo].
  scan_error(str)      — when an unhandled exception occurs during scanning.
  finished()           — always emitted last, regardless of outcome.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from core.photo_scanner import find_photos


class ScanWorker(QObject):
    scan_complete = Signal(list)
    scan_error = Signal(str)
    finished = Signal()

    def __init__(self, folder_path: str) -> None:
        super().__init__()
        self._folder_path = folder_path

    def run(self) -> None:
        try:
            photos = find_photos(self._folder_path)
            self.scan_complete.emit(photos)
        except Exception as exc:  # noqa: BLE001
            self.scan_error.emit(str(exc))
        finally:
            self.finished.emit()

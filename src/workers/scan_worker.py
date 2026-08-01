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

from core.application_services import ApplicationServices
from core.perf_stats import get_session_stats
from core.photo_scanner import find_photos
from storage.import_registration import ImportRegistrationService


class ScanWorker(QObject):
    scan_complete = Signal(list)
    scan_error = Signal(str)
    finished = Signal()

    def __init__(self, folder_path: str, application_services: ApplicationServices | None = None) -> None:
        super().__init__()
        self._folder_path = folder_path
        self._application_services = application_services

    def run(self) -> None:
        registration = None
        try:
            if self._application_services is not None:
                store = self._application_services.metadata_store
                self._application_services.open_or_register_library(self._folder_path)
                registration = ImportRegistrationService(store, self._folder_path)
            photos = find_photos(self._folder_path)
            if registration is not None:
                registration.register(
                    photos,
                    skipped=get_session_stats().get_counter("unsupported_files_skipped"),
                )
            self.scan_complete.emit(photos)
        except Exception as exc:  # noqa: BLE001
            if registration is not None:
                try:
                    registration.fail(str(exc))
                except Exception:  # noqa: BLE001
                    pass
            self.scan_error.emit(str(exc))
        finally:
            self.finished.emit()

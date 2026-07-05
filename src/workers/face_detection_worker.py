from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from core.face_detection_service import FaceDetectionService
from core.media_classifier import MediaClassifier
from core.user_metadata_service import UserMetadataService


@dataclass
class FaceDetectionBatchSummary:
    analyzed_count: int
    faces_detected_count: int
    reclassified_count: int
    photos: list[object]


class FaceDetectionWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)

    def __init__(self, photos, enabled: bool = True):
        super().__init__()
        self._photos = list(photos or [])
        self._face_service = FaceDetectionService(enabled=enabled)
        self._classifier = MediaClassifier()
        self._user_metadata_service = UserMetadataService()

    def run(self) -> None:
        analyzed: list[object] = []
        faces_detected_count = 0
        reclassified_count = 0
        total = len(self._photos)

        for index, photo in enumerate(self._photos, start=1):
            self.progress.emit(index, total, getattr(photo, "display_name", lambda: str(photo))())

            previous_effective = str(
                getattr(photo, "effective_media_category", "")
                or getattr(photo, "media_category", "unknown")
                or "unknown"
            ).strip().lower()

            result = self._face_service.analyze_photo(photo)
            if result.has_faces:
                faces_detected_count += 1

            if result.has_faces:
                self._classifier.classify_photo(photo)

            current_effective = str(
                getattr(photo, "effective_media_category", "")
                or getattr(photo, "media_category", "unknown")
                or "unknown"
            ).strip().lower()
            if current_effective != previous_effective:
                reclassified_count += 1

            try:
                self._user_metadata_service.save_photo_metadata(photo)
            except Exception:
                pass

            analyzed.append(photo)

        summary = FaceDetectionBatchSummary(
            analyzed_count=len(analyzed),
            faces_detected_count=faces_detected_count,
            reclassified_count=reclassified_count,
            photos=analyzed,
        )
        self.finished.emit(summary)
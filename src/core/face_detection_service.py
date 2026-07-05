from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from core.feature_flags import ENABLE_FACE_DETECTION
from core.image_display_loader import load_display_thumbnail_image

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    cv2 = None

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    np = None


@dataclass(frozen=True)
class FaceDetectionResult:
    face_count: int
    has_faces: bool
    confidence: float
    detector: str
    explanation: list[str]


class FaceDetectionService:
    def __init__(self, enabled: Optional[bool] = None, max_dimension: int = 800):
        self._enabled = ENABLE_FACE_DETECTION if enabled is None else bool(enabled)
        self._max_dimension = max(128, int(max_dimension))
        self._cascade = self._load_cascade() if self._enabled else None

    def detect(self, file_path: str | Path) -> FaceDetectionResult:
        if not self._enabled:
            return FaceDetectionResult(
                face_count=0,
                has_faces=False,
                confidence=0.0,
                detector="disabled",
                explanation=["Face detection disabled"],
            )

        if cv2 is None or np is None or self._cascade is None:
            return self._fallback_result()

        path = Path(file_path)
        image = load_display_thumbnail_image(path, QSize(self._max_dimension, self._max_dimension))
        if image is None or image.isNull():
            return self._fallback_result()

        gray = self._qimage_to_grayscale_array(image)
        if gray is None:
            return self._fallback_result()

        try:
            faces = self._cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(24, 24),
            )
        except Exception:
            return self._fallback_result()

        face_count = int(len(faces) if faces is not None else 0)
        if face_count <= 0:
            return FaceDetectionResult(
                face_count=0,
                has_faces=False,
                confidence=0.0,
                detector="opencv-haar",
                explanation=["No faces detected"],
            )

        confidence = self._confidence_from_faces(faces, image.width(), image.height())
        explanation = [
            "Faces detected using OpenCV Haar cascade",
            f"Detected {face_count} face(s)",
            f"Analyzed resized image at {image.width()}x{image.height()}",
        ]
        return FaceDetectionResult(
            face_count=face_count,
            has_faces=True,
            confidence=confidence,
            detector="opencv-haar",
            explanation=explanation,
        )

    def apply_result_to_photo(self, photo, result: FaceDetectionResult) -> None:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        metadata["face_count"] = int(result.face_count)
        metadata["faces_count"] = int(result.face_count)
        metadata["has_faces"] = bool(result.has_faces)
        metadata["face_detection_confidence"] = float(result.confidence)
        metadata["face_detection_detector"] = str(result.detector)
        metadata["face_detection_explanation"] = list(result.explanation)
        photo.metadata = metadata
        photo.sync_intelligence_from_metadata()

    def analyze_photo(self, photo) -> FaceDetectionResult:
        result = self.detect(getattr(photo, "path", ""))
        self.apply_result_to_photo(photo, result)
        return result

    def _load_cascade(self):
        if cv2 is None:
            return None

        cascade_path = getattr(cv2.data, "haarcascades", "") + "haarcascade_frontalface_default.xml"
        if not cascade_path:
            return None

        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            return None
        return cascade

    def _fallback_result(self) -> FaceDetectionResult:
        return FaceDetectionResult(
            face_count=0,
            has_faces=False,
            confidence=0.0,
            detector="unavailable",
            explanation=["Face detection unavailable"],
        )

    def _qimage_to_grayscale_array(self, image):
        if cv2 is None or np is None:
            return None

        gray_image = image.convertToFormat(QImage.Format.Format_Grayscale8)
        width = gray_image.width()
        height = gray_image.height()
        if width <= 0 or height <= 0:
            return None

        try:
            buffer = gray_image.bits()
            byte_count = gray_image.sizeInBytes()
            array = np.frombuffer(buffer, dtype=np.uint8, count=byte_count)
            array = array.reshape((height, gray_image.bytesPerLine()))
            return array[:, :width]
        except Exception:
            return None

    def _confidence_from_faces(self, faces, width: int, height: int) -> float:
        if width <= 0 or height <= 0:
            return 0.6

        area = float(width * height)
        if area <= 0:
            return 0.6

        face_count = len(faces) if faces is not None else 0
        coverage = 0.0
        for face in faces or []:
            try:
                _, _, face_width, face_height = face
                coverage += (float(face_width) * float(face_height)) / area
            except Exception:
                continue

        base = 0.58 + min(0.18, 0.05 * max(0, face_count - 1))
        coverage_boost = min(0.18, coverage * 1.5)
        return round(min(0.95, base + coverage_boost), 3)
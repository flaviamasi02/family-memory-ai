"""Local FACE-001 detection, crop, embedding, and conservative clustering."""

from __future__ import annotations

import hashlib
import importlib
import math
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Sequence

from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QImageReader

from core.application_data import get_app_data_service
from faces.models import BoundingBox, Face, FaceCluster, FaceEmbedding
from faces.services import FaceDetectionCandidate

cv2 = np = None  # resolved lazily so optional native dependencies cannot break startup


def _load_runtime():
    global cv2, np
    if cv2 is None or np is None:
        try:
            cv2 = importlib.import_module("cv2")
            np = importlib.import_module("numpy")
        except Exception as exc:
            cv2 = np = None
            raise FaceModelUnavailable("Local face runtime is not installed or cannot be loaded.") from exc
    return cv2, np


class FaceModelUnavailable(RuntimeError):
    pass


class LocalOpenCVFaceDetector:
    """Lazy, local OpenCV detector. Coordinates use the EXIF-oriented image."""

    provider_id = "opencv-haar-frontal"
    model_revision = "1"

    def __init__(self):
        self._cascade = None
        self.load_count = 0

    @property
    def available(self) -> bool:
        try:
            _load_runtime()
            return True
        except FaceModelUnavailable:
            return False

    def _model(self):
        if self._cascade is None:
            if not self.available:
                raise FaceModelUnavailable("Local face detector is not installed.")
            path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            model = cv2.CascadeClassifier(str(path))
            if model.empty():
                raise FaceModelUnavailable("Local face detector model is unavailable.")
            self._cascade, self.load_count = model, self.load_count + 1
        return self._cascade

    def detect(self, image_path: Path, cancel_event: Event | None = None) -> Sequence[FaceDetectionCandidate]:
        if cancel_event and cancel_event.is_set():
            return ()
        cv, numpy = _load_runtime()
        reader = QImageReader(str(image_path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            raise ValueError("Image could not be decoded.")
        rgb = image.convertToFormat(image.Format.Format_RGB888)
        array = numpy.frombuffer(rgb.bits(), dtype=numpy.uint8, count=rgb.sizeInBytes()).reshape(rgb.height(), rgb.bytesPerLine())
        gray = cv.cvtColor(array[:, : rgb.width() * 3].reshape(rgb.height(), rgb.width(), 3), cv.COLOR_RGB2GRAY)
        boxes = self._model().detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
        return tuple(FaceDetectionCandidate(BoundingBox(float(x), float(y), float(w), float(h)), 0.8) for x, y, w, h in boxes)


class FaceCropCache:
    def __init__(self, root: Path | None = None, size: int = 224, padding: float = .2):
        self.root = Path(root or (get_app_data_service().root / "cache" / "faces"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.size, self.padding = size, padding

    def cache_key(self, face: Face) -> str:
        raw = f"{face.id}|{face.detector_key}|{face.source_fingerprint}|crop-v1"
        return hashlib.sha256(raw.encode()).hexdigest()

    def path_for(self, face: Face) -> Path:
        return self.root / f"{self.cache_key(face)}.jpg"

    def create(self, source: Path, face: Face) -> Path:
        target = self.path_for(face)
        if target.is_file():
            return target
        reader = QImageReader(str(source)); reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            raise ValueError("Face crop source could not be decoded.")
        box = face.bounding_box
        px, py = box.width * self.padding, box.height * self.padding
        left, top = max(0, int(box.x - px)), max(0, int(box.y - py))
        right, bottom = min(image.width(), math.ceil(box.x + box.width + px)), min(image.height(), math.ceil(box.y + box.height + py))
        crop = image.copy(QRect(left, top, max(1, right-left), max(1, bottom-top))).scaled(
            QSize(self.size, self.size), aspectMode=1, mode=1)
        if not crop.save(str(target), "JPEG", 88):
            raise OSError("Face thumbnail could not be written.")
        face.crop_cache_key, face.crop_cache_path = self.cache_key(face), str(target)
        return target

    def clear(self) -> None:
        for path in self.root.glob("*.jpg"):
            path.unlink(missing_ok=True)


class LocalFaceEmbeddingProvider:
    """Bounded local face-crop descriptor, isolated from MobileCLIP."""
    provider_id = "local-face-descriptor"
    model_id = "face-crop-dct"
    model_revision = "1"
    embedding_dimension = 128

    def __init__(self, crop_cache: FaceCropCache | None = None):
        self.crop_cache = crop_cache or FaceCropCache()

    def embed(self, image_path: Path, faces: Sequence[Face], cancel_event: Event | None = None) -> Sequence[FaceEmbedding]:
        cv, numpy = _load_runtime()
        output = []
        for face in faces:
            if cancel_event and cancel_event.is_set(): break
            crop = cv.imread(str(self.crop_cache.create(image_path, face)), cv.IMREAD_GRAYSCALE)
            if crop is None: continue
            descriptor = cv.dct(cv.resize(crop, (32, 32)).astype(numpy.float32) / 255.0).flatten()[:128]
            norm = float(numpy.linalg.norm(descriptor))
            if not math.isfinite(norm) or norm == 0: continue
            vector = tuple(float(x) for x in descriptor / norm)
            output.append(FaceEmbedding(face.id, self.provider_id, self.model_id, self.model_revision,
                                        len(vector), vector, face.source_fingerprint))
        return tuple(output)


class ConservativeFaceClusterer:
    """Deterministic complete-link-like grouping; clusters are advisory only."""
    algorithm_key = "cosine-conservative-v1"

    def __init__(self, threshold: float = .88): self.threshold = threshold

    @staticmethod
    def similarity(a, b): return sum(x*y for x, y in zip(a, b))

    def cluster(self, embeddings: Sequence[FaceEmbedding], existing: Sequence[FaceCluster] = ()) -> Sequence[FaceCluster]:
        by_face = {item.face_id: item for item in embeddings if item.status == "ok"}
        groups: list[list[str]] = []
        for face_id in sorted(by_face):
            vector = by_face[face_id].vector
            group = next((g for g in groups if all(self.similarity(vector, by_face[x].vector) >= self.threshold for x in g)), None)
            (group if group is not None else groups.append([face_id]))
        old = {tuple(sorted(getattr(c, "face_ids", ()) or ())): c for c in existing}
        result = []
        for group in groups:
            cluster = old.get(tuple(group), FaceCluster(algorithm_key=self.algorithm_key))
            cluster.face_ids = tuple(group)
            pairs = [self.similarity(by_face[a].vector, by_face[b].vector) for i,a in enumerate(group) for b in group[i+1:]]
            cluster.confidence = min(pairs) if pairs else 1.0
            result.append(cluster)
        return tuple(result)

"""Bounded background orchestration for the FACE-001 local pipeline."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from threading import Condition, Event

from PySide6.QtCore import QObject, Signal

from faces.models import Face
from faces.processing import (ConservativeFaceClusterer, FaceCropCache,
                              FaceModelUnavailable, LocalFaceEmbeddingProvider,
                              LocalOpenCVFaceDetector)


@dataclass(frozen=True)
class FaceScanProgress:
    eligible: int
    processed: int = 0
    current: str = ""
    faces_found: int = 0
    no_faces: int = 0
    failures: int = 0
    remaining: int = 0
    cancelled: bool = False


class FaceProcessingWorker(QObject):
    progress = Signal(object)
    completed = Signal(object)
    unavailable = Signal(str)
    finished = Signal()

    def __init__(self, photos, repository, detector=None, embedder=None, clusterer=None, crop_cache=None):
        super().__init__()
        self.photos = list(photos or [])
        self.repository = repository
        self.detector = detector or LocalOpenCVFaceDetector()
        self.crop_cache = crop_cache or FaceCropCache()
        self.embedder = embedder or LocalFaceEmbeddingProvider(self.crop_cache)
        self.clusterer = clusterer or ConservativeFaceClusterer()
        self._cancel = Event()
        self._pause = Condition()
        self._paused = False

    def pause(self):
        with self._pause:
            self._paused = True

    def resume(self):
        with self._pause:
            self._paused = False
            self._pause.notify_all()

    def cancel(self):
        self._cancel.set()
        self.resume()

    def run(self):
        total = len(self.photos)
        progress = FaceScanProgress(total, remaining=total)
        self.progress.emit(progress)
        try:
            if hasattr(self.detector, "available") and not self.detector.available:
                raise FaceModelUnavailable("Local face processing is unavailable. Install the optional face runtime from Settings, then try again.")
            processed = faces_found = no_faces = failures = 0
            for photo in self.photos:
                with self._pause:
                    while self._paused and not self._cancel.is_set():
                        self._pause.wait()
                if self._cancel.is_set():
                    break
                current = str(getattr(photo, "filename", "") or getattr(photo, "path", ""))
                try:
                    self._process_photo(photo)
                    metadata = dict(getattr(photo, "metadata", {}) or {})
                    metadata.pop("face_processing_failure", None); photo.metadata = metadata
                    count = len(self.repository.faces_for_image(self._image_id(photo)))
                    faces_found += count
                    no_faces += int(count == 0)
                except FaceModelUnavailable:
                    raise
                except Exception as exc:
                    failures += 1
                    metadata = dict(getattr(photo, "metadata", {}) or {})
                    metadata["face_processing_failure"] = {
                        "code": str(getattr(exc, "code", "image_processing_failed")),
                        "message": str(exc),
                    }
                    photo.metadata = metadata
                processed += 1
                progress = FaceScanProgress(total, processed, current, faces_found, no_faces,
                                            failures, total - processed, self._cancel.is_set())
                self.progress.emit(progress)
            if not self._cancel.is_set():
                self._rebuild_clusters()
            progress = FaceScanProgress(total, processed, "", faces_found, no_faces, failures,
                                        total - processed, self._cancel.is_set())
            self.completed.emit(progress)
        except FaceModelUnavailable as exc:
            self.unavailable.emit(str(exc))
        except Exception:
            self.unavailable.emit("Local face scan could not finish. Completed results were kept; please try again.")
        finally:
            self.finished.emit()

    def _image_id(self, photo) -> str:
        return str(getattr(photo, "id", "") or Path(getattr(photo, "path", "")).resolve())

    def _fingerprint(self, photo) -> str:
        path = Path(getattr(photo, "path", ""))
        stat = path.stat()
        return hashlib.sha256(f"{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()

    def _process_photo(self, photo):
        path, image_id = Path(photo.path), self._image_id(photo)
        fingerprint = self._fingerprint(photo)
        detector_key = f"{self.detector.provider_id}|{self.detector.model_revision}"
        existing = self.repository.faces_for_image(image_id)
        if existing and all(f.source_fingerprint == fingerprint and f.detector_key == detector_key for f in existing):
            return
        self.repository.delete_faces_for_image(image_id)
        candidates = self.detector.detect(path, self._cancel)
        faces = []
        for candidate in candidates:
            stable = hashlib.sha256(f"{image_id}|{fingerprint}|{candidate.bounding_box.to_dict()}|{detector_key}".encode()).hexdigest()
            face = Face(image_id=image_id, id=stable, source_fingerprint=fingerprint,
                        bounding_box=candidate.bounding_box, detection_confidence=candidate.confidence,
                        detector_key=detector_key, landmarks=candidate.landmarks,
                        quality_metrics=candidate.quality_metrics or {})
            self.crop_cache.create(path, face)
            self.repository.save_face(face)
            faces.append(face)
        if faces:
            model_key = (f"{self.embedder.provider_id}|{self.embedder.model_id}|"
                         f"{self.embedder.model_revision}|dim={self.embedder.embedding_dimension}")
            missing = [face for face in faces if self.repository.get_embedding(face.id, model_key) is None]
            for embedding in self.embedder.embed(path, missing, self._cancel):
                self.repository.save_embedding(embedding)

    def _rebuild_clusters(self):
        model_key = (f"{self.embedder.provider_id}|{self.embedder.model_id}|"
                     f"{self.embedder.model_revision}|dim={self.embedder.embedding_dimension}")
        clusters = self.clusterer.cluster(self.repository.embeddings_for_model(model_key), self.repository.list_clusters())
        for cluster in clusters:
            self.repository.save_cluster(cluster)
            for face_id in cluster.face_ids:
                face = self.repository.get_face(face_id)
                if face is not None:
                    face.cluster_id = cluster.id
                    self.repository.save_face(face)

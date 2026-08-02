"""Bounded background orchestration for the FACE-001 local pipeline."""

from __future__ import annotations

import hashlib
import json
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Condition, Event

from PySide6.QtCore import QObject, Signal

from faces.models import Face
from faces.processing import (ConservativeFaceClusterer, FaceCropCache,
                              FaceImageProcessingError, FaceModelUnavailable, LocalFaceEmbeddingProvider,
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
    images_per_second: float = 0.0
    estimated_remaining_seconds: float = 0.0
    failure_reasons: tuple[tuple[str, int], ...] = ()
    cache_hits: int = 0
    worker_startup_ms: float = 0.0
    average_processing_ms: float = 0.0
    median_processing_ms: float = 0.0
    slowest_processing_ms: float = 0.0
    photos_decoded: int = 0
    photos_with_faces: int = 0
    crop_failures: int = 0
    embedding_failures: int = 0
    persistence_failures: int = 0


@dataclass(frozen=True)
class PhotoProcessingOutcome:
    face_count: int = 0
    reused: bool = False
    crop_failures: int = 0
    embedding_failures: int = 0
    persistence_failures: int = 0


class FaceProcessingWorker(QObject):
    progress = Signal(object)
    stage_changed = Signal(object)
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
        self._skip = Event()
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
        self._close_runtime()

    def skip_current(self):
        self._skip.set()
        self._close_runtime()

    def run(self):
        total = len(self.photos)
        progress = FaceScanProgress(total, remaining=total)
        self.progress.emit(progress)
        try:
            if hasattr(self.detector, "available") and not self.detector.available:
                raise FaceModelUnavailable("Local face processing is unavailable. Install the optional face runtime from Settings, then try again.")
            processed = faces_found = no_faces = failures = cache_hits = 0
            decoded = photos_with_faces = crop_failures = embedding_failures = persistence_failures = 0
            failure_reasons = {}; run_started = time.perf_counter()
            for photo in self.photos:
                self._skip.clear()
                with self._pause:
                    while self._paused and not self._cancel.is_set():
                        self._pause.wait()
                if self._cancel.is_set():
                    break
                current = str(getattr(photo, "filename", "") or getattr(photo, "path", ""))
                try:
                    outcome = self._process_photo(photo)
                    cache_hits += int(outcome.reused)
                    decoded += 1
                    crop_failures += outcome.crop_failures
                    embedding_failures += outcome.embedding_failures
                    persistence_failures += outcome.persistence_failures
                    metadata = dict(getattr(photo, "metadata", {}) or {})
                    metadata.pop("face_processing_failure", None); photo.metadata = metadata
                    count = outcome.face_count
                    faces_found += count
                    photos_with_faces += int(count > 0)
                    no_faces += int(count == 0)
                except FaceModelUnavailable:
                    if self._cancel.is_set():
                        break
                    raise
                except Exception as exc:
                    failures += 1
                    code = str(getattr(exc, "code", "image_processing_failed"))
                    failure_reasons[code] = failure_reasons.get(code, 0) + 1
                    metadata = dict(getattr(photo, "metadata", {}) or {})
                    metadata["face_processing_failure"] = {
                        "code": str(getattr(exc, "code", "image_processing_failed")),
                        "message": str(exc),
                    }
                    photo.metadata = metadata
                processed += 1
                elapsed = max(time.perf_counter() - run_started, .001); rate = processed / elapsed
                progress = FaceScanProgress(total, processed, current, faces_found, no_faces,
                                            failures, total - processed, self._cancel.is_set(), rate,
                                            (total - processed) / rate if rate else 0,
                                            tuple(sorted(failure_reasons.items(), key=lambda item: (-item[1], item[0]))), cache_hits,
                                            *self._runtime_timings(), decoded, photos_with_faces,
                                            crop_failures, embedding_failures, persistence_failures)
                self.progress.emit(progress)
            if not self._cancel.is_set():
                self._rebuild_clusters()
            progress = FaceScanProgress(total, processed, "", faces_found, no_faces, failures,
                                        total - processed, self._cancel.is_set(),
                                        processed / max(time.perf_counter()-run_started,.001), 0,
                                        tuple(sorted(failure_reasons.items(), key=lambda item: (-item[1], item[0]))), cache_hits,
                                        *self._runtime_timings(), decoded, photos_with_faces,
                                        crop_failures, embedding_failures, persistence_failures)
            self.completed.emit(progress)
        except FaceModelUnavailable as exc:
            self.unavailable.emit(str(exc))
        except Exception:
            self.unavailable.emit("Local face scan could not finish. Completed results were kept; please try again.")
        finally:
            self._close_runtime()
            self.finished.emit()

    def _image_id(self, photo) -> str:
        return str(getattr(photo, "id", "") or Path(getattr(photo, "path", "")).resolve())

    def _fingerprint(self, photo) -> str:
        path = Path(getattr(photo, "path", ""))
        stat = path.stat()
        return hashlib.sha256(f"{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()

    def _process_photo(self, photo):
        path, image_id = Path(photo.path), self._image_id(photo)
        image_started = time.perf_counter(); timings = {}
        self._stage(photo, "checking cached results", image_started)
        fingerprint = self._fingerprint(photo)
        detector_key = f"{self.detector.provider_id}|{self.detector.model_revision}"
        existing = self.repository.faces_for_image(image_id)
        result = self.repository.get_processing_result(image_id)
        if (result and result["status"] == "success" and result["source_fingerprint"] == fingerprint
                and result["detector_key"] == detector_key
                and result["processing_version"] == "face-worker-v1"):
            return PhotoProcessingOutcome(int(result["face_count"]), reused=True)
        if existing and all(f.source_fingerprint == fingerprint and f.detector_key == detector_key for f in existing):
            self.repository.save_processing_result(image_id, fingerprint, detector_key, "success", len(existing))
            return PhotoProcessingOutcome(len(existing), reused=True)
        self.repository.delete_faces_for_image(image_id)
        self._stage(photo, "decoding and detecting faces", image_started)
        started = time.perf_counter()
        try:
            candidates = self.detector.detect(path, self._cancel)
        except FaceModelUnavailable as exc:
            if self._skip.is_set():
                raise FaceImageProcessingError("skipped", "This slow photo was skipped.") from exc
            raise
        timings["detection_ms"] = (time.perf_counter()-started)*1000
        detection_stats = dict(getattr(self.detector, "last_detection_stats", {}) or {})
        timings["decode_ms"] = detection_stats.get("decode_ms", 0)
        timings["managed_detection_ms"] = detection_stats.get("detection_ms", timings["detection_ms"])
        self._stage(photo, "persisting detections", image_started, len(candidates), detection_stats)
        faces = []; crop_failures = persistence_failures = 0
        started = time.perf_counter()
        for candidate in candidates:
            stable = hashlib.sha256(f"{image_id}|{fingerprint}|{candidate.bounding_box.to_dict()}|{detector_key}".encode()).hexdigest()
            face = Face(image_id=image_id, id=stable, source_fingerprint=fingerprint,
                        bounding_box=candidate.bounding_box, detection_confidence=candidate.confidence,
                        detector_key=detector_key, landmarks=candidate.landmarks,
                        quality_metrics=candidate.quality_metrics or {})
            # Detection evidence is useful independently of crops/embeddings.
            # Persist it first so a downstream optional step cannot erase it.
            try:
                self.repository.save_face(face)
            except Exception as exc:
                persistence_failures += 1
                self._log_stage(photo, "persist", "persistence_failed", exc)
                continue
            faces.append(face)
        if candidates and not faces:
            raise FaceImageProcessingError(
                "persistence_failed", "Detected faces could not be saved for this image.")
        timings["detection_persistence_ms"] = (time.perf_counter()-started)*1000
        if faces:
            self._stage(photo, "creating face thumbnails", image_started, len(faces), detection_stats)
            started = time.perf_counter()
            try:
                create_many = getattr(self.crop_cache, "create_many", None)
                if create_many is not None:
                    create_many(path, faces)
                else:
                    for face in faces: self.crop_cache.create(path, face)
                for face in faces: self.repository.save_face(face)
            except Exception as exc:
                crop_failures += len(faces)
                self._log_stage(photo, "crop", "crop_failed", exc)
                for face in faces:
                    face.processing_error = "crop_failed"
                    try: self.repository.save_face(face)
                    except Exception: persistence_failures += 1
            timings["crop_ms"] = (time.perf_counter()-started)*1000
        if faces:
            model_key = (f"{self.embedder.provider_id}|{self.embedder.model_id}|"
                         f"{self.embedder.model_revision}|dim={self.embedder.embedding_dimension}")
            cached_embedding_ids = self.repository.embedding_face_ids(model_key, (face.id for face in faces))
            missing = [face for face in faces if face.crop_cache_path and face.id not in cached_embedding_ids]
            embedding_failures = 0
            self._stage(photo, "embedding faces", image_started, len(faces), detection_stats)
            started = time.perf_counter()
            for face in missing:
                if self._skip.is_set():
                    embedding_failures += 1
                    face.processing_error = "embedding_skipped"
                    continue
                try:
                    embeddings = self.embedder.embed(path, (face,), self._cancel)
                    for embedding in embeddings: self.repository.save_embedding(embedding)
                    if not embeddings: raise ValueError("No descriptor was produced.")
                except Exception as exc:
                    embedding_failures += 1
                    face.processing_error = "embedding_failed"
                    self._log_stage(photo, "embed", "embedding_failed", exc)
                    try: self.repository.save_face(face)
                    except Exception: persistence_failures += 1
            timings["embedding_ms"] = (time.perf_counter()-started)*1000
        self._stage(photo, "saving processing result", image_started, len(faces), detection_stats)
        started = time.perf_counter()
        try:
            self.repository.save_processing_result(image_id, fingerprint, detector_key, "success", len(faces))
        except Exception as exc:
            persistence_failures += 1
            self._log_stage(photo, "persist", "persistence_failed", exc)
        timings["result_persistence_ms"] = (time.perf_counter()-started)*1000
        timings["total_ms"] = (time.perf_counter()-image_started)*1000
        self._log_timings(photo, timings, detection_stats, len(faces))
        return PhotoProcessingOutcome(len(faces), False, crop_failures,
                                      embedding_failures if faces else 0, persistence_failures)

    def _log_stage(self, photo, stage: str, code: str, exc: Exception) -> None:
        """Record downstream diagnostics without exposing a personal path."""
        client = getattr(self.detector, "runtime_client", None)
        log_path = getattr(client, "log_path", None)
        if log_path is None: return
        path = Path(getattr(photo, "path", ""))
        record = {"time": datetime.now(timezone.utc).isoformat(), "operation": "scan",
                  "processing_stage": stage, "error_code": code,
                  "image_suffix": path.suffix.casefold(),
                  "image_size": path.stat().st_size if path.is_file() else 0,
                  "technical_detail": f"{type(exc).__name__}: {exc}"}
        with Path(log_path).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _log_timings(self, photo, timings, detection_stats, accepted_count):
        client = getattr(self.detector, "runtime_client", None)
        log_path = getattr(client, "log_path", None)
        if log_path is None: return
        path = Path(getattr(photo, "path", ""))
        record = {"time": datetime.now(timezone.utc).isoformat(), "operation": "image_summary",
                  "image_suffix": path.suffix.casefold(), "image_size": path.stat().st_size if path.is_file() else 0,
                  "raw_detections": detection_stats.get("raw", accepted_count),
                  "accepted_detections": accepted_count,
                  "rejected_detections": detection_stats.get("rejected", 0), **timings}
        with Path(log_path).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _stage(self, photo, stage, image_started, faces=0, detection_stats=None):
        self.stage_changed.emit({"stage": stage, "current": str(getattr(photo, "filename", "")),
                                 "elapsed_seconds": time.perf_counter()-image_started,
                                 "faces": int(faces), "detection_stats": detection_stats or {}})

    def _close_runtime(self):
        clients = {getattr(self.detector, "runtime_client", None), getattr(self.embedder, "runtime_client", None)}
        for client in clients:
            if client is not None: client.close()

    def _runtime_timings(self):
        client = getattr(self.detector, "runtime_client", None)
        values = list(getattr(client, "processing_times_ms", ()) or ())
        if not values: return (float(getattr(client, "startup_ms", 0) or 0), 0.0, 0.0, 0.0)
        return (float(client.startup_ms), sum(values)/len(values), statistics.median(values), max(values))

    def _rebuild_clusters(self):
        self.stage_changed.emit({"stage": "building face groups", "current": "", "elapsed_seconds": 0, "faces": 0})
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

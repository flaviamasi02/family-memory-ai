from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Protocol, Sequence, runtime_checkable

from faces.models import BoundingBox, Face, FaceCluster, FaceEmbedding, FaceLandmark, Person
from faces.repositories import FaceRepository, PersonRepository


@dataclass(frozen=True)
class FaceDetectionCandidate:
    bounding_box: BoundingBox
    confidence: float | None = None
    landmarks: tuple[FaceLandmark, ...] = ()
    quality_metrics: dict[str, float] | None = None


@runtime_checkable
class FaceDetectionProvider(Protocol):
    provider_id: str
    def detect(self, image_path: Path, cancel_event: Event | None = None) -> Sequence[FaceDetectionCandidate]: ...


@runtime_checkable
class FaceEmbeddingProvider(Protocol):
    provider_id: str
    model_id: str
    model_revision: str
    embedding_dimension: int
    def embed(self, image_path: Path, faces: Sequence[Face], cancel_event: Event | None = None) -> Sequence[FaceEmbedding]: ...


@runtime_checkable
class FaceClusteringService(Protocol):
    def cluster(self, embeddings: Sequence[FaceEmbedding], existing: Sequence[FaceCluster] = ()) -> Sequence[FaceCluster]: ...


@runtime_checkable
class PersonManagementService(Protocol):
    def create_person(self, name: str = "") -> Person: ...
    def rename_person(self, person_id: str, name: str) -> Person: ...
    def assign_face(self, face_id: str, person_id: str | None) -> Face: ...


class NoOpFaceDetectionProvider:
    """Foundation placeholder. It intentionally never examines the image."""

    provider_id = "model-004a-no-op"

    def detect(self, image_path: Path, cancel_event: Event | None = None) -> Sequence[FaceDetectionCandidate]:
        return ()


class UnavailableFaceEmbeddingProvider:
    """Explicit placeholder preventing accidental fake embeddings."""

    provider_id = "unavailable"
    model_id = "unavailable"
    model_revision = "0"
    embedding_dimension = 0

    def embed(self, image_path: Path, faces: Sequence[Face], cancel_event: Event | None = None) -> Sequence[FaceEmbedding]:
        if not faces:
            return ()
        raise RuntimeError("Face embedding generation is not available in MODEL-004A.")


class NoOpFaceClusteringService:
    def cluster(self, embeddings: Sequence[FaceEmbedding], existing: Sequence[FaceCluster] = ()) -> Sequence[FaceCluster]:
        return tuple(existing)


class RepositoryPersonManagementService:
    def __init__(self, faces: FaceRepository, persons: PersonRepository):
        self._faces = faces
        self._persons = persons

    def create_person(self, name: str = "") -> Person:
        return self._persons.save_person(Person(name=name))

    def rename_person(self, person_id: str, name: str) -> Person:
        person = self._require_person(person_id)
        person.name = name.strip()
        person.revision += 1
        return self._persons.save_person(person)

    def assign_face(self, face_id: str, person_id: str | None) -> Face:
        face = self._faces.get_face(face_id)
        if face is None:
            raise KeyError(f"Unknown face: {face_id}")
        if person_id is not None:
            self._require_person(person_id)
        face.person_id = person_id
        face.revision += 1
        return self._faces.save_face(face)

    def _require_person(self, person_id: str) -> Person:
        person = self._persons.get_person(person_id)
        if person is None:
            raise KeyError(f"Unknown person: {person_id}")
        return person

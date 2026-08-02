from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
import math
from uuid import uuid4


def new_id() -> str:
    """Return a portable, stable identifier without a storage dependency."""
    return str(uuid4())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _confidence(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1.")
    return value


@dataclass(frozen=True)
class BoundingBox:
    """Pixel-space rectangle within the source image."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("Bounding boxes require non-negative origins and positive size.")

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> BoundingBox:
        return cls(*(float(value[key]) for key in ("x", "y", "width", "height")))


@dataclass(frozen=True)
class FaceLandmark:
    kind: str
    x: float
    y: float
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValueError("Landmark kind cannot be empty.")
        object.__setattr__(self, "confidence", _confidence(self.confidence, "landmark confidence"))

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "x": self.x, "y": self.y, "confidence": self.confidence}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FaceLandmark:
        return cls(str(value["kind"]), float(value["x"]), float(value["y"]), value.get("confidence"))


@dataclass
class Face:
    """One detected face region, independent of any detector or UI toolkit."""

    image_id: str
    bounding_box: BoundingBox
    id: str = field(default_factory=new_id)
    source_fingerprint: str = ""
    detection_confidence: float | None = None
    detector_key: str = ""
    landmarks: tuple[FaceLandmark, ...] = ()
    quality_metrics: dict[str, float] = field(default_factory=dict)
    person_id: str | None = None
    cluster_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    revision: int = 1
    crop_cache_key: str = ""
    crop_cache_path: str = ""
    detection_status: str = "detected"
    false_positive: bool = False
    assignment_source: str = ""
    assignment_confidence: float | None = None
    assignment_confirmed: bool = False
    processing_error: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.image_id:
            raise ValueError("Face and image IDs cannot be empty.")
        self.detection_confidence = _confidence(self.detection_confidence, "detection confidence")
        self.assignment_confidence = _confidence(self.assignment_confidence, "assignment confidence")
        self.landmarks = tuple(self.landmarks)
        self.quality_metrics = {str(key): float(value) for key, value in self.quality_metrics.items()}
        if self.revision < 1:
            raise ValueError("Face revision must be positive.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "image_id": self.image_id,
            "source_fingerprint": self.source_fingerprint,
            "bounding_box": self.bounding_box.to_dict(),
            "detection_confidence": self.detection_confidence,
            "detector_key": self.detector_key,
            "landmarks": [item.to_dict() for item in self.landmarks],
            "quality_metrics": dict(self.quality_metrics),
            "person_id": self.person_id,
            "cluster_id": self.cluster_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "revision": self.revision,
            "crop_cache_key": self.crop_cache_key,
            "crop_cache_path": self.crop_cache_path,
            "detection_status": self.detection_status,
            "false_positive": self.false_positive,
            "assignment_source": self.assignment_source,
            "assignment_confidence": self.assignment_confidence,
            "assignment_confirmed": self.assignment_confirmed,
            "processing_error": self.processing_error,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Face:
        data = dict(value)
        data["bounding_box"] = BoundingBox.from_dict(data["bounding_box"])
        data["landmarks"] = tuple(FaceLandmark.from_dict(item) for item in data.get("landmarks", ()))
        return cls(**data)


@dataclass
class Person:
    """A user-manageable identity learned from zero or more faces."""

    name: str = ""
    id: str = field(default_factory=new_id)
    aliases: tuple[str, ...] = ()
    profile_face_id: str | None = None
    notes: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    revision: int = 1
    relationship_label: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Person ID cannot be empty.")
        self.name = self.name.strip()
        self.aliases = tuple(str(alias).strip() for alias in self.aliases if str(alias).strip())
        if self.revision < 1:
            raise ValueError("Person revision must be positive.")

    def to_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in (
            "id", "name", "aliases", "profile_face_id", "notes", "created_at", "updated_at", "revision", "relationship_label"
        )} | {"aliases": list(self.aliases)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Person:
        return cls(**dict(value))


@dataclass
class FaceCluster:
    """A stable automatic grouping that may later be linked to a person."""

    id: str = field(default_factory=new_id)
    label: str = ""
    person_id: str | None = None
    algorithm_key: str = ""
    confidence: float | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    revision: int = 1
    face_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Cluster ID cannot be empty.")
        self.confidence = _confidence(self.confidence, "cluster confidence")
        if self.revision < 1:
            raise ValueError("Cluster revision must be positive.")
        self.face_ids = tuple(self.face_ids)

    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FaceCluster:
        return cls(**dict(value))


@dataclass
class FaceEmbedding:
    """Versioned cache record; vectors are never part of the Face identity."""

    face_id: str
    provider_id: str
    model_id: str
    model_revision: str
    dimension: int
    vector: tuple[float, ...]
    source_fingerprint: str = ""
    generated_at: str = field(default_factory=utc_now)
    status: str = "ok"
    error: str = ""

    def __post_init__(self) -> None:
        self.vector = tuple(float(item) for item in self.vector)
        if not self.face_id or not self.provider_id or not self.model_id or not self.model_revision:
            raise ValueError("Embedding identity fields cannot be empty.")
        if self.dimension < 0 or (self.status == "ok" and self.dimension != len(self.vector)):
            raise ValueError("Embedding dimension must match a successful vector.")
        if self.status == "ok" and not all(math.isfinite(item) for item in self.vector):
            raise ValueError("Embedding vectors must contain only finite values.")

    @property
    def model_key(self) -> str:
        return f"{self.provider_id}|{self.model_id}|{self.model_revision}|dim={self.dimension}"

    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self)) | {"vector": list(self.vector)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FaceEmbedding:
        return cls(**dict(value))

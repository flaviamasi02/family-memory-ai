"""Platform-neutral face intelligence foundation.

MODEL-004A deliberately contains no face-recognition implementation.  The
types and contracts exported here are safe for desktop and future mobile
clients to share.
"""

from faces.models import (
    BoundingBox,
    Face,
    FaceCluster,
    FaceEmbedding,
    FaceLandmark,
    Person,
)
from faces.persistence import SQLiteFaceRepository

__all__ = [
    "BoundingBox",
    "Face",
    "FaceCluster",
    "FaceEmbedding",
    "FaceLandmark",
    "Person",
    "SQLiteFaceRepository",
]

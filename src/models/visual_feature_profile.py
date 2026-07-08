from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class VisualFeatureProfile:
    has_faces: bool = False
    face_count: int = 0
    face_confidence: float = 0.0
    has_text_like_regions: bool = False
    looks_like_document: bool = False
    looks_like_screenshot: bool = False
    looks_like_graphic_or_meme: bool = False
    dominant_orientation: str = "unknown"
    visual_tags: list[str] = field(default_factory=list)
    evidence_summary: list[str] = field(default_factory=list)
    confidence_by_feature: dict[str, float] = field(default_factory=dict)
    extraction_status: str = "missing"
    extractor_version: str = "visual-feature-extractor-v1"

    @classmethod
    def empty(cls, status: str = "missing", reason: str | None = None) -> "VisualFeatureProfile":
        summary = [reason] if reason else []
        return cls(extraction_status=status, evidence_summary=summary)

    @classmethod
    def from_dict(cls, data: Any) -> "VisualFeatureProfile":
        if not isinstance(data, dict):
            return cls.empty()
        try:
            return cls(
                has_faces=bool(data.get("has_faces", False)),
                face_count=max(0, int(data.get("face_count", 0) or 0)),
                face_confidence=max(0.0, min(1.0, float(data.get("face_confidence", 0.0) or 0.0))),
                has_text_like_regions=bool(data.get("has_text_like_regions", False)),
                looks_like_document=bool(data.get("looks_like_document", False)),
                looks_like_screenshot=bool(data.get("looks_like_screenshot", False)),
                looks_like_graphic_or_meme=bool(data.get("looks_like_graphic_or_meme", False)),
                dominant_orientation=str(data.get("dominant_orientation", "unknown") or "unknown"),
                visual_tags=[str(item) for item in data.get("visual_tags", []) if str(item).strip()],
                evidence_summary=[str(item) for item in data.get("evidence_summary", []) if str(item).strip()],
                confidence_by_feature={str(k): max(0.0, min(1.0, float(v or 0.0))) for k, v in dict(data.get("confidence_by_feature", {}) or {}).items()},
                extraction_status=str(data.get("extraction_status", "loaded") or "loaded"),
                extractor_version=str(data.get("extractor_version", "visual-feature-extractor-v1") or "visual-feature-extractor-v1"),
            )
        except Exception:
            return cls.empty(status="corrupted", reason="Stored visual feature profile could not be read safely.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def has_content_evidence(self) -> bool:
        return bool(
            self.has_faces
            or self.has_text_like_regions
            or self.looks_like_document
            or self.looks_like_screenshot
            or self.looks_like_graphic_or_meme
            or self.visual_tags
        )

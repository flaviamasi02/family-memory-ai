from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
SUPPORTED_LIBRARY_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


@dataclass(frozen=True)
class MediaRelevanceResult:
    relevance_category: str
    relevance_reason: str
    is_album_relevant_candidate: bool


class MediaRelevanceClassifier:
    def classify(
        self,
        file_path: str | Path,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> MediaRelevanceResult:
        path = Path(file_path)
        extension = path.suffix.lower()
        stem_lower = path.stem.lower()
        filename_lower = path.name.lower()
        metadata = dict(metadata or {})

        if extension in VIDEO_EXTENSIONS:
            return MediaRelevanceResult(
                relevance_category="video",
                relevance_reason=f"Video extension detected: {extension}",
                is_album_relevant_candidate=False,
            )

        if extension and extension not in SUPPORTED_LIBRARY_EXTENSIONS:
            return MediaRelevanceResult(
                relevance_category="unsupported_file",
                relevance_reason=f"Unsupported extension detected: {extension}",
                is_album_relevant_candidate=False,
            )

        if filename_lower.startswith("screenshot") or "screenshot" in filename_lower:
            return MediaRelevanceResult(
                relevance_category="screenshot",
                relevance_reason="Filename indicates a screenshot.",
                is_album_relevant_candidate=False,
            )

        if "receipt" in stem_lower or "invoice" in stem_lower:
            return MediaRelevanceResult(
                relevance_category="receipt_or_scan",
                relevance_reason="Filename indicates receipt or invoice content.",
                is_album_relevant_candidate=False,
            )

        if "scan" in stem_lower or "document" in stem_lower:
            return MediaRelevanceResult(
                relevance_category="document_image",
                relevance_reason="Filename indicates a scanned or document image.",
                is_album_relevant_candidate=False,
            )

        width = metadata.get("width")
        height = metadata.get("height")
        if (
            ("wa" in path.name.upper() or "whatsapp" in filename_lower)
            and isinstance(width, int)
            and isinstance(height, int)
            and max(width, height) <= 512
        ):
            return MediaRelevanceResult(
                relevance_category="meme_or_graphic",
                relevance_reason="WhatsApp-style filename with very small image dimensions.",
                is_album_relevant_candidate=False,
            )

        if extension in IMAGE_EXTENSIONS:
            return MediaRelevanceResult(
                relevance_category="family_photo_candidate",
                relevance_reason="Supported image file treated as family photo candidate by default.",
                is_album_relevant_candidate=True,
            )

        return MediaRelevanceResult(
            relevance_category="unknown",
            relevance_reason="File could not be classified deterministically.",
            is_album_relevant_candidate=False,
        )
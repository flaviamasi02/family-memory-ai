from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from core.category_registry import get_category_registry
from models.photo import Photo


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
LOW_QUALITY_MIN_DIMENSION = 480
LOW_QUALITY_MIN_AREA = 640 * 480
LOW_QUALITY_MISSING_DIMENSION_MIN_FILE_SIZE = 32 * 1024
DUPLICATE_HASH_MIN_FILE_SIZE = 1024


@dataclass
class PhotoCleanupClassification:
    photo: Photo
    category: str
    confidence: float
    reasons: list[str] = field(default_factory=list)
    recommended_action: str = "review"


@dataclass
class PhotoCleanupResult:
    classifications: list[PhotoCleanupClassification] = field(default_factory=list)
    total_count: int = 0
    category_counts: dict[str, int] = field(default_factory=dict)


class PhotoCleanupEngine:
    def classify_photos(self, photos: list[Photo]) -> PhotoCleanupResult:
        classifications = [self._classify_single_photo(photo) for photo in photos or []]
        self._mark_exact_duplicates(classifications)

        category_counts: dict[str, int] = {}
        for classification in classifications:
            self._apply_classification_to_photo(classification)
            category = classification.category
            category_counts[category] = category_counts.get(category, 0) + 1

        return PhotoCleanupResult(
            classifications=classifications,
            total_count=len(classifications),
            category_counts=category_counts,
        )

    def _classify_single_photo(self, photo: Photo) -> PhotoCleanupClassification:
        registry = get_category_registry()
        path = Path(getattr(photo, "path", ""))
        extension = path.suffix.lower()
        filename_lower = path.name.lower()
        metadata = getattr(photo, "metadata", {}) or {}
        reasons: list[str] = []

        if extension in VIDEO_EXTENSIONS:
            category = "video"
            return PhotoCleanupClassification(
                photo,
                category,
                1.0,
                [f"Video extension detected: {extension}"],
                self._default_recommended_action(category, registry),
            )

        if self._contains_screenshot_keyword(filename_lower):
            category = "screenshot"
            return PhotoCleanupClassification(
                photo,
                category,
                0.98,
                ["Filename indicates a screenshot."],
                self._default_recommended_action(category, registry),
            )

        if self._contains_document_keyword(filename_lower):
            category = "document_or_scan"
            return PhotoCleanupClassification(
                photo,
                category,
                0.98,
                ["Filename indicates document or scan content."],
                self._default_recommended_action(category, registry),
            )

        if self._contains_advertisement_keyword(filename_lower):
            category = "advertisement"
            return PhotoCleanupClassification(
                photo,
                category,
                0.96,
                ["Filename indicates promotional or advertisement content."],
                self._default_recommended_action(category, registry),
            )

        if self._is_meme_or_graphic(filename_lower, metadata):
            category = "meme_or_graphic"
            return PhotoCleanupClassification(
                photo,
                category,
                0.95,
                ["Filename or very small WhatsApp-style dimensions indicate meme/graphic content."],
                self._default_recommended_action(category, registry),
            )

        if self._is_low_quality(photo, metadata, reasons):
            category = "low_quality_photo"
            return PhotoCleanupClassification(
                photo,
                category,
                0.85,
                reasons,
                self._default_recommended_action(category, registry, fallback="review"),
            )

        if extension in IMAGE_EXTENSIONS:
            category = "family_photo_candidate"
            return PhotoCleanupClassification(
                photo,
                category,
                0.90,
                ["Normal image file kept as family photo candidate by default."],
                self._default_recommended_action(category, registry),
            )

        return PhotoCleanupClassification(photo, "unknown", 0.40, [f"No deterministic cleanup rule matched for extension {extension or 'none'}."], "review")

    def _contains_screenshot_keyword(self, filename_lower: str) -> bool:
        return filename_lower.startswith("screenshot") or "screenshot" in filename_lower

    def _contains_document_keyword(self, filename_lower: str) -> bool:
        keywords = ("scan", "document", "receipt", "invoice", "fattura", "pdf", "contratto")
        return any(keyword in filename_lower for keyword in keywords)

    def _contains_advertisement_keyword(self, filename_lower: str) -> bool:
        keywords = ("promo", "banner", "pubblicita", "offerta", "sale")
        if any(keyword in filename_lower for keyword in keywords):
            return True

        tokens = filename_lower.replace("-", "_").replace(".", "_").split("_")
        return any(token in {"ad", "ads"} for token in tokens)

    def _is_meme_or_graphic(self, filename_lower: str, metadata: dict) -> bool:
        if any(keyword in filename_lower for keyword in ("meme", "gif", "sticker")):
            return True

        width = metadata.get("width")
        height = metadata.get("height")
        return (
            "wa" in filename_lower
            and isinstance(width, int)
            and isinstance(height, int)
            and max(width, height) <= 512
        )

    def _is_low_quality(self, photo: Photo, metadata: dict, reasons: list[str]) -> bool:
        intelligence = getattr(photo, "intelligence", None)
        if intelligence is not None and bool(getattr(intelligence, "is_blurry", False)):
            reasons.append("Photo is marked as blurry.")

        width = metadata.get("width")
        height = metadata.get("height")

        if isinstance(width, int) and isinstance(height, int):
            if min(width, height) < LOW_QUALITY_MIN_DIMENSION or (width * height) < LOW_QUALITY_MIN_AREA:
                reasons.append(f"Image resolution is very small ({width}x{height}).")
        elif photo.extension.lower() in {".jpg", ".jpeg", ".png", ".webp"} and photo.file_size >= LOW_QUALITY_MISSING_DIMENSION_MIN_FILE_SIZE:
            reasons.append("Usable image dimensions are missing.")

        return bool(reasons)

    def _mark_exact_duplicates(self, classifications: list[PhotoCleanupClassification]) -> None:
        hash_groups: dict[str, list[PhotoCleanupClassification]] = {}
        for classification in classifications:
            photo = classification.photo
            if not isinstance(photo, Photo):
                continue
            if photo.file_size < DUPLICATE_HASH_MIN_FILE_SIZE:
                continue

            file_hash = self._file_hash(photo.path)
            if not file_hash:
                continue
            hash_groups.setdefault(file_hash, []).append(classification)

        for group in hash_groups.values():
            if len(group) < 2:
                continue

            keeper = self._choose_duplicate_keeper(group)
            for classification in group:
                if classification is keeper:
                    if "Exact duplicate group keeper selected." not in classification.reasons:
                        classification.reasons.append("Exact duplicate group keeper selected.")
                    continue

                classification.category = "duplicate_candidate"
                classification.confidence = max(classification.confidence, 0.99)
                classification.recommended_action = "move_to_cleanup_review"
                classification.reasons = [
                    f"Exact file duplicate detected; keeping {keeper.photo.display_name()} as the preferred copy."
                ]

    def _choose_duplicate_keeper(
        self,
        group: list[PhotoCleanupClassification],
    ) -> PhotoCleanupClassification:
        return max(
            group,
            key=lambda classification: (
                self._technical_quality_score(classification.photo),
                classification.photo.file_size,
                -len(classification.photo.display_name()),
                str(classification.photo.path),
            ),
        )

    def _technical_quality_score(self, photo: Photo) -> int:
        metadata = getattr(photo, "metadata", {}) or {}
        width = metadata.get("width")
        height = metadata.get("height")
        if isinstance(width, int) and isinstance(height, int):
            return width * height
        return 0

    def _file_hash(self, file_path: Path) -> str | None:
        try:
            digest = hashlib.sha256()
            with Path(file_path).open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except OSError:
            return None

    def _apply_classification_to_photo(self, classification: PhotoCleanupClassification) -> None:
        registry = get_category_registry()
        photo = classification.photo
        metadata = getattr(photo, "metadata", {})
        metadata["relevance_category"] = classification.category
        metadata["relevance_reason"] = "; ".join(classification.reasons)
        metadata["cleanup_reasons"] = list(classification.reasons)
        metadata["cleanup_confidence"] = classification.confidence
        metadata["cleanup_recommended_action"] = classification.recommended_action
        metadata["is_album_relevant_candidate"] = registry.is_album_candidate_category(classification.category)
        photo.metadata = metadata
        photo.sync_intelligence_from_metadata()

    def _default_recommended_action(self, category_id: str, registry, fallback: str = "review") -> str:
        if registry.is_album_candidate_category(category_id):
            return "keep"
        if registry.is_cleanup_category(category_id):
            return "move_to_cleanup_review"
        return fallback
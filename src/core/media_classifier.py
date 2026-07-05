from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional


class MediaCategory(str, Enum):
    FamilyPhoto = "family_photo"
    Screenshot = "screenshot"
    Document = "document"
    Receipt = "receipt"
    Invoice = "invoice"
    Advertisement = "advertisement"
    Meme = "meme"
    Graphic = "graphic"
    Video = "video"
    DuplicateCandidate = "duplicate_candidate"
    LowQuality = "low_quality"
    Unknown = "unknown"


class UserDecision(str, Enum):
    Pending = "pending"
    ApproveForAlbum = "approve_for_album"
    Keep = "keep"
    IrrelevantMedia = "irrelevant_media"
    Duplicate = "duplicate"
    Document = "document"
    Screenshot = "screenshot"
    Advertisement = "advertisement"
    Meme = "meme"
    Reject = "reject"
    Unknown = "unknown"


@dataclass(frozen=True)
class MediaClassification:
    media_category: MediaCategory
    classification_reason: str
    classification_confidence: float


@dataclass(frozen=True)
class LearningEvent:
    file_path: str
    event_type: str
    previous_value: str
    new_value: str
    source: str = "user"

    @property
    def photo_path(self) -> str:
        return self.file_path

    @property
    def user_decision(self) -> str:
        return self.new_value


@dataclass
class DecisionHistory:
    entries: list[LearningEvent] = field(default_factory=list)

    def record_event(
        self,
        file_path: str,
        event_type: str,
        previous_value: str,
        new_value: str,
        source: str = "user",
    ) -> LearningEvent:
        entry = LearningEvent(
            file_path=str(file_path),
            event_type=str(event_type),
            previous_value=str(previous_value),
            new_value=str(new_value),
            source=str(source),
        )
        self.entries.append(entry)
        return entry

    def record_decision_change(
        self,
        photo,
        previous_value: str,
        new_value: str,
        source: str = "user",
    ) -> LearningEvent:
        return self.record_event(
            file_path=str(getattr(photo, "path", "")),
            event_type="decision_change",
            previous_value=str(previous_value),
            new_value=str(new_value),
            source=source,
        )

    def record_category_correction(
        self,
        photo,
        previous_value: str,
        new_value: str,
        source: str = "user",
    ) -> LearningEvent:
        return self.record_event(
            file_path=str(getattr(photo, "path", "")),
            event_type="category_correction",
            previous_value=str(previous_value),
            new_value=str(new_value),
            source=source,
        )

    def latest_for_photo(self, photo_path: str) -> Optional[LearningEvent]:
        target = str(photo_path)
        for entry in reversed(self.entries):
            if entry.file_path == target:
                return entry
        return None


def media_category_label(category_value: str) -> str:
    labels = {
        MediaCategory.FamilyPhoto.value: "Family Photo",
        MediaCategory.Screenshot.value: "Screenshot",
        MediaCategory.Document.value: "Document",
        MediaCategory.Receipt.value: "Receipt",
        MediaCategory.Invoice.value: "Invoice",
        MediaCategory.Advertisement.value: "Advertisement",
        MediaCategory.Meme.value: "Meme",
        MediaCategory.Graphic.value: "Graphic",
        MediaCategory.Video.value: "Video",
        MediaCategory.DuplicateCandidate.value: "Duplicate Candidate",
        MediaCategory.LowQuality.value: "Low Quality",
        MediaCategory.Unknown.value: "Unknown",
    }
    normalized = str(category_value or "").strip().lower()
    return labels.get(normalized, "Unknown")


def ordered_media_category_values() -> list[str]:
    return [
        MediaCategory.FamilyPhoto.value,
        MediaCategory.Screenshot.value,
        MediaCategory.Document.value,
        MediaCategory.Receipt.value,
        MediaCategory.Invoice.value,
        MediaCategory.Advertisement.value,
        MediaCategory.Meme.value,
        MediaCategory.Graphic.value,
        MediaCategory.Video.value,
        MediaCategory.DuplicateCandidate.value,
        MediaCategory.LowQuality.value,
        MediaCategory.Unknown.value,
    ]


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
MEME_FILENAME_INDICATORS = {
    "meme",
    "sticker",
    "gif",
    "funny",
    "lol",
    "joke",
    "quote",
    "imgflip",
    "tenor",
    "giphy",
    "whatsapp image",
    "forwarded",
    "shared",
    "download",
    "facebook",
    "instagram",
    "tiktok",
}
DOCUMENT_FILENAME_INDICATORS = {
    "document",
    "scan",
    "pdf",
    "contract",
    "contratto",
    "statement",
    "bill",
}
ADVERTISEMENT_FILENAME_INDICATORS = {
    "promo",
    "banner",
    "offerta",
    "sale",
    "advert",
    "coupon",
    "sponsor",
    "ad_",
}


class MediaClassifier:
    def classify(self, file_path: str | Path, metadata: Optional[Mapping[str, Any]] = None) -> MediaClassification:
        path = Path(file_path)
        extension = path.suffix.lower()
        filename_lower = path.name.lower()
        metadata_dict = dict(metadata or {})

        width, height = self._read_dimensions(metadata_dict)
        area = width * height if isinstance(width, int) and isinstance(height, int) else None
        ratio = (width / height) if isinstance(width, int) and isinstance(height, int) and height > 0 else None
        has_camera_metadata = self._has_camera_metadata(metadata_dict)
        has_exif_date = self._has_exif_date(metadata_dict)
        has_gps = bool(metadata_dict.get("has_gps", False))
        looks_downloaded = self._looks_downloaded_or_shared(filename_lower)
        meme_indicators = self._matched_meme_indicators(filename_lower)

        if extension in VIDEO_EXTENSIONS:
            return MediaClassification(
                media_category=MediaCategory.Video,
                classification_reason=f"Video extension detected: {extension}",
                classification_confidence=1.0,
            )

        if extension and extension not in IMAGE_EXTENSIONS:
            return MediaClassification(
                media_category=MediaCategory.Unknown,
                classification_reason=f"Unsupported non-video extension {extension} classified as unknown media.",
                classification_confidence=0.70,
            )

        screenshot_by_filename = self._is_screenshot(filename_lower, metadata_dict)
        screenshot_by_dimensions = self._is_tall_phone_screenshot(width, height, ratio)
        if screenshot_by_filename or screenshot_by_dimensions:
            reason_parts = []
            if screenshot_by_filename:
                reason_parts.append("filename/metadata indicates screenshot")
            if screenshot_by_dimensions:
                reason_parts.append(f"dimensions look like tall phone screenshot ({width}x{height})")
            return MediaClassification(
                MediaCategory.Screenshot,
                f"Classified as screenshot because {' and '.join(reason_parts)}.",
                0.98,
            )

        if "invoice" in filename_lower:
            return MediaClassification(MediaCategory.Invoice, "Filename indicates invoice content.", 0.99)

        if "receipt" in filename_lower:
            return MediaClassification(MediaCategory.Receipt, "Filename indicates receipt content.", 0.99)

        if self._is_document(filename_lower):
            return MediaClassification(
                MediaCategory.Document,
                "Classified as document because filename indicates scan/document content.",
                0.97,
            )

        if self._is_advertisement(filename_lower) or self._is_banner_like(ratio, width, height):
            reason_parts = []
            if self._is_advertisement(filename_lower):
                reason_parts.append("filename has advertisement/promotional indicators")
            if self._is_banner_like(ratio, width, height):
                reason_parts.append(f"dimensions are banner-like ({width}x{height})")
            return MediaClassification(
                MediaCategory.Advertisement,
                f"Classified as advertisement because {' and '.join(reason_parts)}.",
                0.95,
            )

        if self._is_duplicate_candidate(filename_lower, metadata_dict):
            return MediaClassification(MediaCategory.DuplicateCandidate, "Filename or metadata indicates duplicate candidate.", 0.95)

        if self._is_meme(filename_lower):
            detail = ", ".join(meme_indicators[:3]) if meme_indicators else "meme indicators"
            if area is not None and area <= 512 * 512:
                return MediaClassification(
                    MediaCategory.Graphic,
                    f"Classified as graphic because filename contains {detail} and image has low resolution ({width}x{height}).",
                    0.95,
                )
            return MediaClassification(
                MediaCategory.Meme,
                f"Classified as meme because filename contains {detail}.",
                0.94,
            )

        if self._is_small_square_without_camera_metadata(width, height, has_camera_metadata, has_exif_date):
            return MediaClassification(
                MediaCategory.Graphic,
                f"Classified as graphic because image is small square ({width}x{height}) and lacks camera/exif metadata.",
                0.90,
            )

        if self._is_low_quality(width, height):
            return MediaClassification(
                MediaCategory.LowQuality,
                f"Classified as low quality because dimensions are very small ({width}x{height}).",
                0.88,
            )

        if self._is_graphic(filename_lower, width, height):
            return MediaClassification(
                MediaCategory.Graphic,
                "Classified as graphic because filename or dimensions indicate non-photo graphic content.",
                0.90,
            )

        if extension in IMAGE_EXTENSIONS:
            confidence = 0.70
            reason_notes = ["supported image extension"]

            if has_camera_metadata:
                confidence += 0.14
                reason_notes.append("camera metadata present")
            if has_exif_date:
                confidence += 0.12
                reason_notes.append("EXIF date present")
            if has_gps:
                confidence += 0.04
                reason_notes.append("GPS metadata present")

            weak_metadata_profile = not has_camera_metadata and not has_exif_date and not has_gps
            if looks_downloaded and weak_metadata_profile:
                confidence -= 0.32
                reason_notes.append("filename looks downloaded/shared/WhatsApp with no camera metadata")

            if area is not None and area < 800 * 800:
                confidence -= 0.08
                reason_notes.append("limited resolution")

            confidence = max(0.20, min(0.96, confidence))

            if confidence < 0.58:
                return MediaClassification(
                    MediaCategory.Unknown,
                    f"Classified as unknown because family-photo evidence is weak ({'; '.join(reason_notes)}).",
                    confidence,
                )

            return MediaClassification(
                MediaCategory.FamilyPhoto,
                f"Classified as family photo because {'; '.join(reason_notes)}.",
                confidence,
            )

        return MediaClassification(
            media_category=MediaCategory.Unknown,
            classification_reason=f"No deterministic rule matched for extension {extension or 'none'}.",
            classification_confidence=0.40,
        )

    def classify_photo(self, photo) -> MediaClassification:
        classification = self.classify(getattr(photo, "path", ""), getattr(photo, "metadata", {}))
        self.apply_classification_to_photo(photo, classification)
        return classification

    def classify_photos(self, photos: list) -> list[MediaClassification]:
        classifications: list[MediaClassification] = []
        for photo in photos or []:
            classifications.append(self.classify_photo(photo))
        return classifications

    def apply_classification_to_photo(self, photo, classification: MediaClassification) -> None:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        metadata["media_category"] = classification.media_category.value
        metadata["automatic_media_category"] = classification.media_category.value
        metadata["user_corrected_media_category"] = metadata.get("user_corrected_media_category", "")
        if isinstance(metadata.get("user_corrected_media_category"), str) and metadata.get("user_corrected_media_category").strip():
            metadata["effective_media_category"] = str(metadata.get("user_corrected_media_category")).strip().lower()
        else:
            metadata["effective_media_category"] = classification.media_category.value
        metadata["classification_reason"] = classification.classification_reason
        metadata["classification_confidence"] = classification.classification_confidence

        legacy_category = self._legacy_relevance_category(classification.media_category)
        metadata["relevance_category"] = legacy_category
        metadata["relevance_reason"] = classification.classification_reason
        metadata["is_album_relevant_candidate"] = classification.media_category == MediaCategory.FamilyPhoto

        photo.metadata = metadata
        photo.automatic_media_category = classification.media_category.value
        photo.user_corrected_media_category = str(metadata.get("user_corrected_media_category", "") or "")
        photo.effective_media_category = str(metadata.get("effective_media_category", classification.media_category.value) or classification.media_category.value)
        photo.media_category = photo.effective_media_category
        photo.classification_reason = classification.classification_reason
        photo.classification_confidence = classification.classification_confidence
        if not getattr(photo, "user_decision", None):
            photo.user_decision = UserDecision.Pending.value
        photo.sync_intelligence_from_metadata()

    def _is_screenshot(self, filename_lower: str, metadata: Mapping[str, Any]) -> bool:
        if filename_lower.startswith("screenshot") or "screenshot" in filename_lower:
            return True
        software = str(metadata.get("software", "") or "").lower()
        return "screenshot" in software

    def _is_document(self, filename_lower: str) -> bool:
        if any(keyword in filename_lower for keyword in DOCUMENT_FILENAME_INDICATORS):
            return True
        return any(keyword in filename_lower for keyword in ("doc_", "receipt", "invoice"))

    def _is_advertisement(self, filename_lower: str) -> bool:
        if any(keyword in filename_lower for keyword in ADVERTISEMENT_FILENAME_INDICATORS):
            return True

        tokens = filename_lower.replace("-", "_").replace(".", "_").split("_")
        return any(token in {"ad", "ads"} for token in tokens)

    def _is_duplicate_candidate(self, filename_lower: str, metadata: Mapping[str, Any]) -> bool:
        if bool(metadata.get("is_duplicate_candidate", False)):
            return True
        duplicate_group = metadata.get("duplicate_group_id")
        if isinstance(duplicate_group, str) and duplicate_group.strip():
            return True
        duplicate_markers = (" copy", "(copy)", "_copy", "duplicate")
        return any(marker in filename_lower for marker in duplicate_markers)

    def _is_meme(self, filename_lower: str) -> bool:
        return bool(self._matched_meme_indicators(filename_lower))

    def _matched_meme_indicators(self, filename_lower: str) -> list[str]:
        return [indicator for indicator in sorted(MEME_FILENAME_INDICATORS) if indicator in filename_lower]

    def _is_graphic(self, filename_lower: str, width: Optional[int], height: Optional[int]) -> bool:
        if any(keyword in filename_lower for keyword in ("graphic", "logo", "icon", "poster", "flyer")):
            return True

        if isinstance(width, int) and isinstance(height, int):
            return width <= 512 and height <= 512 and width * height <= 512 * 512
        return False

    def _is_low_quality(self, width: Optional[int], height: Optional[int]) -> bool:
        if not isinstance(width, int) or not isinstance(height, int):
            return False
        return min(width, height) < 480 or (width * height) < (640 * 480)

    def _is_tall_phone_screenshot(
        self,
        width: Optional[int],
        height: Optional[int],
        ratio: Optional[float],
    ) -> bool:
        if not isinstance(width, int) or not isinstance(height, int) or not isinstance(ratio, float):
            return False
        return height >= 1300 and ratio <= 0.58

    def _is_banner_like(
        self,
        ratio: Optional[float],
        width: Optional[int],
        height: Optional[int],
    ) -> bool:
        if not isinstance(ratio, float) or not isinstance(width, int) or not isinstance(height, int):
            return False
        return width >= 1000 and height >= 120 and ratio >= 2.6

    def _is_small_square_without_camera_metadata(
        self,
        width: Optional[int],
        height: Optional[int],
        has_camera_metadata: bool,
        has_exif_date: bool,
    ) -> bool:
        if not isinstance(width, int) or not isinstance(height, int):
            return False
        if width != height:
            return False
        if width > 800:
            return False
        return not has_camera_metadata and not has_exif_date

    def _has_camera_metadata(self, metadata: Mapping[str, Any]) -> bool:
        make = str(metadata.get("camera_make", "") or "").strip()
        model = str(metadata.get("camera_model", "") or "").strip()
        return bool(make or model)

    def _has_exif_date(self, metadata: Mapping[str, Any]) -> bool:
        date_value = metadata.get("date_taken")
        return bool(str(date_value).strip()) if date_value is not None else False

    def _looks_downloaded_or_shared(self, filename_lower: str) -> bool:
        indicators = {
            "whatsapp",
            "forwarded",
            "shared",
            "download",
            "facebook",
            "instagram",
            "tiktok",
            "imgflip",
            "giphy",
            "tenor",
        }
        return any(indicator in filename_lower for indicator in indicators)

    def _read_dimensions(self, metadata: Mapping[str, Any]) -> tuple[Optional[int], Optional[int]]:
        width = metadata.get("width")
        height = metadata.get("height")
        if isinstance(width, int) and isinstance(height, int):
            return width, height
        return None, None

    def _legacy_relevance_category(self, category: MediaCategory) -> str:
        mapping = {
            MediaCategory.FamilyPhoto: "family_photo_candidate",
            MediaCategory.Screenshot: "screenshot",
            MediaCategory.Document: "document_or_scan",
            MediaCategory.Receipt: "document_or_scan",
            MediaCategory.Invoice: "document_or_scan",
            MediaCategory.Advertisement: "advertisement",
            MediaCategory.Meme: "meme_or_graphic",
            MediaCategory.Graphic: "meme_or_graphic",
            MediaCategory.Video: "video",
            MediaCategory.DuplicateCandidate: "duplicate_candidate",
            MediaCategory.LowQuality: "low_quality_photo",
            MediaCategory.Unknown: "unknown",
        }
        return mapping.get(category, "unknown")
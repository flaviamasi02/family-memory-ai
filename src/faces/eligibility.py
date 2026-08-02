"""Authoritative FACE-001 processing eligibility policy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.category_registry import normalize_category_id
from core.supported_media import is_supported_image_path


EXCLUDED_CATEGORY_IDS = frozenset({
    "screenshot", "document", "document_or_scan", "receipt", "invoice",
    "advertisement", "meme", "graphic", "meme_or_graphic", "video", "to_trash",
    "not_family_photo",
})
ELIGIBLE_CATEGORY_IDS = frozenset({"family_photo", "personal_photo", "unknown", ""})


@dataclass(frozen=True)
class FaceEligibility:
    eligible: bool
    reason: str
    reason_code: str


def face_processing_eligibility(photo, *, require_file: bool = True) -> FaceEligibility:
    """Return one explainable decision shared by queues, scans, and diagnostics."""
    metadata = dict(getattr(photo, "metadata", {}) or {})
    if metadata.get("face_analysis_excluded") is True:
        return FaceEligibility(False, "Manually excluded from face analysis.", "manual_exclusion")
    if not bool(metadata.get("is_active", True)) or metadata.get("trash_workflow_state") == "moved_to_trash":
        return FaceEligibility(False, "Photo is inactive or in Trash History.", "inactive_trash")
    path = Path(getattr(photo, "path", ""))
    if not is_supported_image_path(path):
        return FaceEligibility(False, "Only supported still images can be scanned.", "unsupported_media")
    if path.suffix.casefold() in {".heic", ".heif"}:
        return FaceEligibility(False, "HEIC/HEIF face decoding is not available in this runtime.", "managed_decoder_unsupported")
    category = normalize_category_id(
        getattr(photo, "user_corrected_media_category", "")
        or getattr(photo, "effective_media_category", "")
        or metadata.get("effective_media_category")
        or getattr(photo, "media_category", "")
    )
    if category in EXCLUDED_CATEGORY_IDS:
        return FaceEligibility(False, f"Category '{category}' is excluded from face analysis.", "excluded_category")
    if category not in ELIGIBLE_CATEGORY_IDS:
        return FaceEligibility(False, "This category is not a family-photo candidate.", "not_family_candidate")
    if require_file and (not path.is_file()):
        return FaceEligibility(False, "The source file is missing.", "missing_file")
    return FaceEligibility(True, "Active supported family-photo candidate.", "eligible")


def set_face_analysis_excluded(photo, excluded: bool) -> None:
    metadata = dict(getattr(photo, "metadata", {}) or {})
    metadata["face_analysis_excluded"] = bool(excluded)
    photo.metadata = metadata

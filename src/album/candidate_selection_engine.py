from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from album.annual_album import AnnualAlbum
from models.photo import Photo
from models.photo_intelligence import PhotoIntelligence


@dataclass
class CandidateSelectionResult:
    selected_count: int = 0
    rejected_count: int = 0
    rejection_reasons: Dict[str, int] = field(default_factory=dict)


class CandidateSelectionEngine:
    def evaluate(self, album: AnnualAlbum) -> CandidateSelectionResult:
        album.selected_photos = []
        album.rejected_photos = []

        result = CandidateSelectionResult()

        for candidate in album.candidate_photos or []:
            reason = self._rejection_reason(candidate, album.year)
            if reason is None:
                self._mark_selected(candidate)
                album.selected_photos.append(candidate)
                continue

            result.rejection_reasons[reason] = result.rejection_reasons.get(reason, 0) + 1
            if isinstance(candidate, Photo):
                self._mark_rejected(candidate, reason)
                album.rejected_photos.append(candidate)

        result.selected_count = len(album.selected_photos)
        result.rejected_count = len(album.rejected_photos)
        album.status = "candidates_evaluated"
        return result

    def _rejection_reason(self, photo, expected_year: int) -> Optional[str]:
        if not isinstance(photo, Photo):
            return "invalid_photo_object"

        if getattr(photo, "path", None) is None:
            return "missing_file_path"

        photo_year = self._extract_year(photo)
        if photo_year is None:
            return "missing_year"

        if photo_year != expected_year:
            return "year_mismatch"

        return None

    def _extract_year(self, photo: Photo) -> Optional[int]:
        intelligence = getattr(photo, "intelligence", None)
        if intelligence is not None and isinstance(getattr(intelligence, "year", None), int):
            return intelligence.year

        metadata = getattr(photo, "metadata", {}) or {}

        year = metadata.get("year")
        if isinstance(year, int):
            return year

        date_taken = metadata.get("date_taken")
        if isinstance(date_taken, datetime):
            return date_taken.year

        if isinstance(date_taken, str):
            text = date_taken.strip()
            if len(text) >= 4 and text[:4].isdigit():
                return int(text[:4])

        return None

    def _mark_selected(self, photo: Photo) -> None:
        if photo.intelligence is None:
            photo.intelligence = PhotoIntelligence()

        photo.intelligence.album_selected = True
        photo.intelligence.album_rejection_reason = None

    def _mark_rejected(self, photo: Photo, reason: str) -> None:
        if photo.intelligence is None:
            photo.intelligence = PhotoIntelligence()

        photo.intelligence.album_selected = False
        photo.intelligence.album_rejection_reason = reason

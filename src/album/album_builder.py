from datetime import datetime
from typing import Dict, List, Optional

from album.annual_album import AnnualAlbum
from models.photo import Photo


class AlbumBuilder:
    def group_photos_by_year(self, photos: List[Photo]) -> Dict[int, List[Photo]]:
        grouped: Dict[int, List[Photo]] = {}
        for photo in photos or []:
            year = self._extract_year(photo)
            if year is None:
                continue
            grouped.setdefault(year, []).append(photo)
        return grouped

    def create_annual_album(self, photos: List[Photo], year: int) -> AnnualAlbum:
        matching = [photo for photo in photos or [] if self._extract_year(photo) == year]
        return AnnualAlbum(
            year=year,
            photos=list(matching),
            candidate_photos=list(matching),
            selected_photos=[],
            rejected_photos=[],
            status="candidate_selection",
        )

    def _extract_year(self, photo: Photo) -> Optional[int]:
        intelligence = getattr(photo, "intelligence", None)
        if intelligence is not None and isinstance(getattr(intelligence, "year", None), int):
            return intelligence.year

        metadata = getattr(photo, "metadata", {}) or {}
        date_taken = metadata.get("date_taken")

        if isinstance(date_taken, datetime):
            return date_taken.year

        if isinstance(date_taken, str):
            year = self._year_from_string(date_taken)
            if year is not None:
                return year

        return None

    def _year_from_string(self, value: str) -> Optional[int]:
        text = (value or "").strip()
        if len(text) < 4:
            return None

        head = text[:4]
        if head.isdigit():
            return int(head)

        return None

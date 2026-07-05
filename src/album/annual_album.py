from dataclasses import dataclass, field
from typing import List

from models.photo import Photo


@dataclass
class AnnualAlbum:
    year: int
    photos: List[Photo] = field(default_factory=list)
    candidate_photos: List[Photo] = field(default_factory=list)
    selected_photos: List[Photo] = field(default_factory=list)
    rejected_photos: List[Photo] = field(default_factory=list)
    status: str = "draft"

    def __post_init__(self) -> None:
        if self.year < 0:
            raise ValueError("year must be a positive integer")

        if not self.photos and self.candidate_photos:
            self.photos = list(self.candidate_photos)

        if not self.candidate_photos and self.photos:
            self.candidate_photos = list(self.photos)

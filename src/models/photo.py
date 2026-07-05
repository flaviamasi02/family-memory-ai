from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtGui import QPixmap

from models.photo_intelligence import PhotoIntelligence


@dataclass
class Photo:
    path: Path
    filename: str
    extension: str
    file_size: int
    created_at: Optional[datetime]
    modified_at: Optional[datetime]
    thumbnail: Optional[QPixmap] = None
    status: str = "pending"
    id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    technical_score: Optional[float] = None
    memory_score: Optional[float] = None
    rarity_score: Optional[float] = None
    people: List[str] = field(default_factory=list)
    ai_tags: List[str] = field(default_factory=list)
    intelligence: Optional[PhotoIntelligence] = None

    def __post_init__(self) -> None:
        if self.intelligence is None:
            self.intelligence = PhotoIntelligence()

        self.sync_intelligence_from_metadata()

    @classmethod
    def from_path(cls, path: Path) -> "Photo":
        path = Path(path)
        stat = path.stat()

        return cls(
            path=path,
            filename=path.name,
            extension=path.suffix.lower(),
            file_size=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            thumbnail=None,
            status="pending",
            id=None,
            metadata={},
            technical_score=None,
            memory_score=None,
            rarity_score=None,
            people=[],
            ai_tags=[],
            intelligence=PhotoIntelligence(),
        )

    def display_name(self) -> str:
        return self.filename or str(self.path)

    def set_status(self, status: str) -> None:
        self.status = status

    def has_thumbnail(self) -> bool:
        return self.thumbnail is not None

    def is_analyzed(self) -> bool:
        return bool(self.ai_tags or self.people or self.metadata)

    def is_scored(self) -> bool:
        return any(
            score is not None
            for score in (self.technical_score, self.memory_score, self.rarity_score)
        )

    def sync_intelligence_from_metadata(self) -> None:
        if self.intelligence is None:
            self.intelligence = PhotoIntelligence()

        metadata = self.metadata or {}
        self.intelligence.has_metadata = bool(metadata)

        if not metadata:
            return

        date_taken = metadata.get("date_taken")
        if date_taken is not None:
            self.intelligence.date_taken = date_taken

        year = metadata.get("year")
        month = metadata.get("month")

        if isinstance(year, int):
            self.intelligence.year = year
        if isinstance(month, int):
            self.intelligence.month = month

        if self.intelligence.year is None or self.intelligence.month is None:
            derived_year, derived_month = self._derive_year_month_from_date(date_taken)
            if self.intelligence.year is None:
                self.intelligence.year = derived_year
            if self.intelligence.month is None:
                self.intelligence.month = derived_month

    def _derive_year_month_from_date(self, date_value) -> tuple[Optional[int], Optional[int]]:
        if isinstance(date_value, datetime):
            return date_value.year, date_value.month

        if isinstance(date_value, str):
            text = date_value.strip()
            if len(text) >= 7 and text[:4].isdigit():
                year = int(text[:4])
                month = None

                if text[4:5] in {":", "-", "/"} and text[5:7].isdigit():
                    month = int(text[5:7])

                return year, month

        return None, None

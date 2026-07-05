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
    relevance_category: str = "unknown"
    relevance_reason: str = ""
    is_album_relevant_candidate: bool = True
    media_category: str = "unknown"
    automatic_media_category: str = "unknown"
    user_corrected_media_category: str = ""
    effective_media_category: str = "unknown"
    user_decision: str = "pending"
    classification_reason: str = ""
    classification_confidence: float = 0.0

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
        day = metadata.get("day")
        date_source = metadata.get("date_source")
        relevance_category = metadata.get("relevance_category")
        relevance_reason = metadata.get("relevance_reason")
        is_relevant_candidate = metadata.get("is_album_relevant_candidate")
        media_category = metadata.get("media_category")
        automatic_media_category = metadata.get("automatic_media_category")
        user_corrected_media_category = metadata.get("user_corrected_media_category")
        effective_media_category = metadata.get("effective_media_category")
        user_decision = metadata.get("user_decision")
        classification_reason = metadata.get("classification_reason")
        classification_confidence = metadata.get("classification_confidence")

        if isinstance(year, int):
            self.intelligence.year = year
        if isinstance(month, int):
            self.intelligence.month = month
        if isinstance(day, int):
            self.intelligence.day = day
        if isinstance(date_source, str) and date_source.strip():
            normalized_source = date_source.strip()
            self.intelligence.date_source = normalized_source
            self.intelligence.source_of_date = normalized_source

        if isinstance(relevance_category, str) and relevance_category.strip():
            self.relevance_category = relevance_category.strip()
            self.intelligence.relevance_category = self.relevance_category

        if isinstance(relevance_reason, str):
            self.relevance_reason = relevance_reason
            self.intelligence.relevance_reason = relevance_reason

        if isinstance(is_relevant_candidate, bool):
            self.is_album_relevant_candidate = is_relevant_candidate
            self.intelligence.is_album_relevant_candidate = is_relevant_candidate

        if isinstance(media_category, str) and media_category.strip():
            self.media_category = media_category.strip()
            self.intelligence.media_category = self.media_category

        if isinstance(automatic_media_category, str) and automatic_media_category.strip():
            self.automatic_media_category = automatic_media_category.strip()
            self.intelligence.automatic_media_category = self.automatic_media_category

        if isinstance(user_corrected_media_category, str):
            self.user_corrected_media_category = user_corrected_media_category.strip()
            self.intelligence.user_corrected_media_category = self.user_corrected_media_category

        if isinstance(effective_media_category, str) and effective_media_category.strip():
            self.effective_media_category = effective_media_category.strip()
            self.intelligence.effective_media_category = self.effective_media_category

        if self.user_corrected_media_category:
            self.effective_media_category = self.user_corrected_media_category
        elif self.automatic_media_category:
            self.effective_media_category = self.automatic_media_category
        elif self.media_category:
            self.effective_media_category = self.media_category

        self.media_category = self.effective_media_category or self.media_category
        self.intelligence.media_category = self.media_category
        self.intelligence.automatic_media_category = self.automatic_media_category
        self.intelligence.user_corrected_media_category = self.user_corrected_media_category
        self.intelligence.effective_media_category = self.effective_media_category

        if isinstance(user_decision, str) and user_decision.strip():
            self.user_decision = user_decision.strip()
            self.intelligence.user_decision = self.user_decision

        if isinstance(classification_reason, str):
            self.classification_reason = classification_reason
            self.intelligence.classification_reason = classification_reason

        if isinstance(classification_confidence, (int, float)):
            self.classification_confidence = float(classification_confidence)
            self.intelligence.classification_confidence = float(classification_confidence)

        if (
            self.intelligence.year is None
            or self.intelligence.month is None
            or self.intelligence.day is None
        ):
            derived_year, derived_month, derived_day = self._derive_year_month_day_from_date(date_taken)
            if self.intelligence.year is None:
                self.intelligence.year = derived_year
            if self.intelligence.month is None:
                self.intelligence.month = derived_month
            if self.intelligence.day is None:
                self.intelligence.day = derived_day

        if not getattr(self.intelligence, "date_source", None):
            self.intelligence.date_source = "Unknown"
        if not getattr(self.intelligence, "source_of_date", None):
            self.intelligence.source_of_date = self.intelligence.date_source
        if not getattr(self.intelligence, "relevance_category", None):
            self.intelligence.relevance_category = self.relevance_category
        if getattr(self.intelligence, "relevance_reason", None) is None:
            self.intelligence.relevance_reason = self.relevance_reason
        if not getattr(self.intelligence, "media_category", None):
            self.intelligence.media_category = self.media_category
        if not getattr(self.intelligence, "automatic_media_category", None):
            self.intelligence.automatic_media_category = self.automatic_media_category
        if getattr(self.intelligence, "user_corrected_media_category", None) is None:
            self.intelligence.user_corrected_media_category = self.user_corrected_media_category
        if not getattr(self.intelligence, "effective_media_category", None):
            self.intelligence.effective_media_category = self.effective_media_category
        if not getattr(self.intelligence, "user_decision", None):
            self.intelligence.user_decision = self.user_decision
        if getattr(self.intelligence, "classification_reason", None) is None:
            self.intelligence.classification_reason = self.classification_reason
        if not isinstance(getattr(self.intelligence, "classification_confidence", None), (int, float)):
            self.intelligence.classification_confidence = self.classification_confidence
        self.intelligence.is_album_relevant_candidate = self.is_album_relevant_candidate

    def _derive_year_month_day_from_date(
        self,
        date_value,
    ) -> tuple[Optional[int], Optional[int], Optional[int]]:
        if isinstance(date_value, datetime):
            return date_value.year, date_value.month, date_value.day

        if isinstance(date_value, str):
            text = date_value.strip()
            if len(text) >= 10 and text[:4].isdigit():
                year = int(text[:4])
                month = None
                day = None

                if text[4:5] in {":", "-", "/"} and text[5:7].isdigit():
                    month = int(text[5:7])
                if text[7:8] in {":", "-", "/"} and text[8:10].isdigit():
                    day = int(text[8:10])

                return year, month, day

        return None, None, None

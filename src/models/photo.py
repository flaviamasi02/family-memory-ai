from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtGui import QPixmap


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
        )

    def display_name(self) -> str:
        return self.filename or str(self.path)

    def has_thumbnail(self) -> bool:
        return self.thumbnail is not None

    def is_analyzed(self) -> bool:
        return bool(self.ai_tags or self.people or self.metadata)

    def is_scored(self) -> bool:
        return any(
            score is not None
            for score in (self.technical_score, self.memory_score, self.rarity_score)
        )

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class PhotoIntelligence:
    # Basic
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    date_taken: Optional[datetime | str] = None
    date_source: str = "Unknown"
    source_of_date: str = "Unknown"
    has_metadata: bool = False
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

    # Quality placeholders
    quality_score: Optional[float] = None
    blur_score: Optional[float] = None
    exposure_score: Optional[float] = None
    is_blurry: bool = False

    # People placeholders
    faces_count: int = 0
    people_names: List[str] = field(default_factory=list)

    # Duplicate placeholders
    duplicate_group_id: Optional[str] = None
    is_duplicate_candidate: bool = False

    # Album placeholders
    album_candidate_score: Optional[float] = None
    album_selected: bool = False
    album_rejection_reason: Optional[str] = None

    # AI placeholders
    ai_score: Optional[float] = None
    ai_tags: List[str] = field(default_factory=list)
    ai_explanation: Optional[str] = None
from dataclasses import dataclass, field

from album.annual_album import AnnualAlbum
from models.photo import Photo
from models.photo_intelligence import PhotoIntelligence


@dataclass
class AlbumScoreBreakdown:
    photo: Photo
    total_score: float
    technical_score: float
    memory_score: float
    date_score: float
    explanation: list[str] = field(default_factory=list)


@dataclass
class AlbumScoringResult:
    scored_photos: list[AlbumScoreBreakdown] = field(default_factory=list)
    scored_count: int = 0


class AlbumScoringEngine:
    def score(self, album: AnnualAlbum) -> AlbumScoringResult:
        scored: list[AlbumScoreBreakdown] = []

        for photo in album.selected_photos or []:
            if photo.intelligence is None:
                photo.intelligence = PhotoIntelligence()

            # Keep intelligence in sync so date/year fields can be derived from metadata.
            photo.sync_intelligence_from_metadata()

            technical_score, technical_explanations = self._technical_score(photo)
            memory_score, memory_explanations = self._memory_score(photo)
            date_score, date_explanations = self._date_score(photo, album.year)

            total_score = round(
                (technical_score * 0.4) + (memory_score * 0.4) + (date_score * 0.2),
                2,
            )

            photo.intelligence.album_candidate_score = total_score

            scored.append(
                AlbumScoreBreakdown(
                    photo=photo,
                    total_score=total_score,
                    technical_score=technical_score,
                    memory_score=memory_score,
                    date_score=date_score,
                    explanation=[
                        *technical_explanations,
                        *memory_explanations,
                        *date_explanations,
                        f"Total score calculated with weights 40/40/20 = {total_score}",
                    ],
                )
            )

        scored.sort(key=lambda item: item.total_score, reverse=True)
        return AlbumScoringResult(scored_photos=scored, scored_count=len(scored))

    def _technical_score(self, photo: Photo) -> tuple[float, list[str]]:
        score = 50.0
        explanation = ["Technical base score: 50"]

        if photo.has_thumbnail():
            score += 10
            explanation.append("+10 technical: thumbnail available")

        if photo.file_size > 0:
            score += 10
            explanation.append("+10 technical: file size is greater than zero")

        metadata = photo.metadata or {}
        if metadata.get("width") is not None and metadata.get("height") is not None:
            score += 10
            explanation.append("+10 technical: metadata contains width and height")

        if photo.intelligence is not None and photo.intelligence.is_blurry is True:
            score -= 30
            explanation.append("-30 technical: photo marked as blurry")

        clamped = self._clamp(score)
        if clamped != score:
            explanation.append(f"Technical score clamped to {clamped}")

        return clamped, explanation

    def _memory_score(self, photo: Photo) -> tuple[float, list[str]]:
        score = 50.0
        explanation = ["Memory base score: 50"]

        if photo.people:
            score += 15
            explanation.append("+15 memory: photo.people is not empty")

        intelligence = photo.intelligence
        if intelligence is not None and intelligence.people_names:
            score += 15
            explanation.append("+15 memory: intelligence.people_names is not empty")

        metadata = photo.metadata or {}
        if any(metadata.get(key) for key in ("event", "location", "description")):
            score += 10
            explanation.append("+10 memory: metadata contains event, location, or description")

        clamped = self._clamp(score)
        if clamped != score:
            explanation.append(f"Memory score clamped to {clamped}")

        return clamped, explanation

    def _date_score(self, photo: Photo, album_year: int) -> tuple[float, list[str]]:
        score = 50.0
        explanation = ["Date base score: 50"]

        intelligence = photo.intelligence
        if intelligence is None:
            clamped = self._clamp(score)
            return clamped, explanation

        if intelligence.date_taken is not None:
            score += 20
            explanation.append("+20 date: intelligence.date_taken exists")

        if intelligence.month is not None:
            score += 10
            explanation.append("+10 date: intelligence.month exists")

        if intelligence.year == album_year:
            score += 20
            explanation.append(f"+20 date: intelligence.year matches album year {album_year}")

        clamped = self._clamp(score)
        if clamped != score:
            explanation.append(f"Date score clamped to {clamped}")

        return clamped, explanation

    def _clamp(self, score: float) -> float:
        return max(0.0, min(100.0, float(score)))

from __future__ import annotations

from calendar import month_name
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from album.album_scoring_engine import AlbumScoreBreakdown
from models.photo import Photo


@dataclass
class AlbumDraftPage:
    title: str
    photos: list[Photo] = field(default_factory=list)
    page_type: str = "month"
    explanation: list[str] = field(default_factory=list)


@dataclass
class AlbumDraft:
    year: int
    pages: list[AlbumDraftPage] = field(default_factory=list)
    total_photos: int = 0
    explanation: list[str] = field(default_factory=list)


@dataclass
class AlbumDraftBuildResult:
    draft: AlbumDraft
    source_photo_count: int = 0
    included_photo_count: int = 0
    excluded_photo_count: int = 0
    exclusion_reasons: dict[str, int] = field(default_factory=dict)


class AlbumDraftBuilder:
    def build(
        self,
        year: int,
        scored_photos: list[AlbumScoreBreakdown],
        review_status_by_path: dict[str, str] | None = None,
    ) -> AlbumDraftBuildResult:
        status_map = {str(key): str(value).strip().lower() for key, value in (review_status_by_path or {}).items()}
        exclusion_reasons: dict[str, int] = {}

        approved_candidates: list[AlbumScoreBreakdown] = []
        pending_candidates: list[AlbumScoreBreakdown] = []

        for breakdown in scored_photos or []:
            photo = getattr(breakdown, "photo", None)
            if photo is None:
                self._inc(exclusion_reasons, "missing_photo")
                continue

            path = getattr(photo, "path", None)
            if not path:
                self._inc(exclusion_reasons, "missing_file_path")
                continue

            status = status_map.get(str(path), "pending")
            if status == "rejected":
                self._inc(exclusion_reasons, "rejected_by_user")
                continue

            if status == "approved":
                approved_candidates.append(breakdown)
            else:
                pending_candidates.append(breakdown)

        draft_explanation: list[str] = [
            "Rejected photos were excluded.",
            "Photos were grouped by month.",
            "Draft limited to 120 photos.",
        ]

        max_draft_size = 120

        if approved_candidates:
            draft_explanation.insert(0, "Approved photos were prioritized.")
            selected_pool = sorted(approved_candidates, key=self._rank_for_chronological_selection)
            for _item in pending_candidates:
                self._inc(exclusion_reasons, "below_selection_cutoff")
        else:
            draft_explanation.insert(0, "No approved photos found; top-scoring pending photos were used.")
            pending_ranked = sorted(
                pending_candidates,
                key=self._rank_for_pending_cutoff,
            )
            selected_pool = pending_ranked

        included_breakdowns = selected_pool[:max_draft_size]
        for _item in selected_pool[max_draft_size:]:
            self._inc(exclusion_reasons, "below_selection_cutoff")

        included_breakdowns = sorted(included_breakdowns, key=self._rank_for_chronological_selection)

        pages = self._group_into_pages(included_breakdowns)

        draft = AlbumDraft(
            year=year,
            pages=pages,
            total_photos=len(included_breakdowns),
            explanation=draft_explanation,
        )

        source_count = len(scored_photos or [])
        included_count = len(included_breakdowns)
        excluded_count = source_count - included_count

        return AlbumDraftBuildResult(
            draft=draft,
            source_photo_count=source_count,
            included_photo_count=included_count,
            excluded_photo_count=excluded_count,
            exclusion_reasons=exclusion_reasons,
        )

    def _group_into_pages(self, included_breakdowns: list[AlbumScoreBreakdown]) -> list[AlbumDraftPage]:
        monthly_buckets: dict[tuple[int, int], list[Photo]] = {}
        undated_bucket: list[Photo] = []

        for breakdown in included_breakdowns:
            photo = breakdown.photo
            date_parts = self._extract_date_parts(photo)
            year = date_parts[0]
            month = date_parts[1]

            if year is None or month is None or month < 1 or month > 12:
                undated_bucket.append(photo)
                continue

            monthly_buckets.setdefault((year, month), []).append(photo)

        pages: list[AlbumDraftPage] = []
        for year_month in sorted(monthly_buckets.keys()):
            y, m = year_month
            photos = monthly_buckets[year_month]
            title = f"{month_name[m]} {y}"
            pages.append(
                AlbumDraftPage(
                    title=title,
                    photos=photos,
                    page_type="month",
                    explanation=[f"{len(photos)} photos included for {title}."],
                )
            )

        if undated_bucket:
            pages.append(
                AlbumDraftPage(
                    title="Undated Memories",
                    photos=undated_bucket,
                    page_type="undated",
                    explanation=[f"{len(undated_bucket)} photos included without date metadata."],
                )
            )

        return pages

    def _rank_for_chronological_selection(self, breakdown: AlbumScoreBreakdown):
        date_tuple = self._normalized_date_tuple(breakdown.photo)
        key = str(getattr(breakdown.photo, "path", ""))
        return (date_tuple[0], date_tuple[1], -float(breakdown.total_score), key)

    def _rank_for_pending_cutoff(self, breakdown: AlbumScoreBreakdown):
        date_tuple = self._normalized_date_tuple(breakdown.photo)
        key = str(getattr(breakdown.photo, "path", ""))
        return (-float(breakdown.total_score), date_tuple[0], date_tuple[1], key)

    def _normalized_date_tuple(self, photo: Photo) -> tuple[int, tuple[int, int, int]]:
        year, month, day = self._extract_date_parts(photo)
        if year is None or month is None or day is None:
            return (1, (9999, 12, 31))
        return (0, (year, month, day))

    def _extract_date_parts(self, photo: Photo) -> tuple[Optional[int], Optional[int], Optional[int]]:
        intelligence = getattr(photo, "intelligence", None)
        if intelligence is not None:
            year = getattr(intelligence, "year", None)
            month = getattr(intelligence, "month", None)
            day = getattr(intelligence, "day", None)
            if isinstance(year, int) and isinstance(month, int) and isinstance(day, int):
                return year, month, day

            date_taken = getattr(intelligence, "date_taken", None)
            parsed = self._parse_date(date_taken)
            if parsed is not None:
                return parsed.year, parsed.month, parsed.day

        metadata = getattr(photo, "metadata", {}) or {}
        year = metadata.get("year")
        month = metadata.get("month")
        day = metadata.get("day")
        if isinstance(year, int) and isinstance(month, int) and isinstance(day, int):
            return year, month, day

        parsed = self._parse_date(metadata.get("date_taken"))
        if parsed is not None:
            return parsed.year, parsed.month, parsed.day

        return None, None, None

    def _parse_date(self, value) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            text = value.strip()
            formats = [
                "%Y:%m:%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
                "%Y:%m:%d",
                "%Y-%m-%d",
                "%Y/%m/%d",
            ]
            for date_format in formats:
                try:
                    return datetime.strptime(text, date_format)
                except ValueError:
                    continue

        return None

    def _inc(self, reasons: dict[str, int], key: str) -> None:
        reasons[key] = reasons.get(key, 0) + 1

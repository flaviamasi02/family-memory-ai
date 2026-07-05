from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class DateSource:
    EXIF = "EXIF"
    FILENAME = "Filename"
    FILESYSTEM = "Filesystem"
    UNKNOWN = "Unknown"


@dataclass
class DateExtractionResult:
    date_taken: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    date_source: str = DateSource.UNKNOWN


class DateExtractionService:
    EXIF_DATE_TIME_ORIGINAL = 36867
    EXIF_CREATE_DATE = 36868

    # Additional commonly useful EXIF date tags.
    OTHER_EXIF_DATE_TAGS = [
        306,    # DateTime
        36868,  # DateTimeDigitized / CreateDate
        37520,  # SubSecTime
        37521,  # SubSecTimeOriginal
        37522,  # SubSecTimeDigitized
    ]

    def extract_date(self, file_path: Path | str, exif: Any = None) -> DateExtractionResult:
        path = Path(file_path)

        exif_result = self._extract_from_exif(exif)
        if exif_result is not None:
            return exif_result

        filename_result = self._extract_from_filename(path.name)
        if filename_result is not None:
            return filename_result

        filesystem_result = self._extract_from_filesystem(path)
        if filesystem_result is not None:
            return filesystem_result

        return DateExtractionResult(date_source=DateSource.UNKNOWN)

    def _extract_from_exif(self, exif: Any) -> Optional[DateExtractionResult]:
        if not exif:
            return None

        primary = exif.get(self.EXIF_DATE_TIME_ORIGINAL)
        if primary:
            return self._build_result(str(primary), DateSource.EXIF)

        create_date = exif.get(self.EXIF_CREATE_DATE)
        if create_date:
            return self._build_result(str(create_date), DateSource.EXIF)

        for tag in self.OTHER_EXIF_DATE_TAGS:
            value = exif.get(tag)
            if value:
                result = self._build_result(str(value), DateSource.EXIF)
                if result is not None:
                    return result

        for tag, value in exif.items():
            if not value:
                continue
            if tag in {self.EXIF_DATE_TIME_ORIGINAL, self.EXIF_CREATE_DATE}:
                continue
            result = self._build_result(str(value), DateSource.EXIF)
            if result is not None:
                return result

        return None

    def _extract_from_filename(self, filename: str) -> Optional[DateExtractionResult]:
        text = (filename or "").strip()
        if not text:
            return None

        patterns = [
            r"(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})[_-](?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})",
            r"(?:^|[_-])(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})(?:[_-]|\.)",
            r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue

            year = int(match.group("year"))
            month = int(match.group("month"))
            day = int(match.group("day"))
            hour = int(match.groupdict().get("hour") or 0)
            minute = int(match.groupdict().get("minute") or 0)
            second = int(match.groupdict().get("second") or 0)

            try:
                date_obj = datetime(year, month, day, hour, minute, second)
            except ValueError:
                continue

            return DateExtractionResult(
                date_taken=date_obj.strftime("%Y:%m:%d %H:%M:%S"),
                year=year,
                month=month,
                day=day,
                date_source=DateSource.FILENAME,
            )

        return None

    def _extract_from_filesystem(self, file_path: Path) -> Optional[DateExtractionResult]:
        try:
            stat = file_path.stat()
        except OSError:
            return None

        timestamps = []
        if getattr(stat, "st_ctime", None):
            timestamps.append(stat.st_ctime)
        if getattr(stat, "st_mtime", None):
            timestamps.append(stat.st_mtime)

        if not timestamps:
            return None

        date_obj = datetime.fromtimestamp(min(timestamps))
        return DateExtractionResult(
            date_taken=date_obj.strftime("%Y:%m:%d %H:%M:%S"),
            year=date_obj.year,
            month=date_obj.month,
            day=date_obj.day,
            date_source=DateSource.FILESYSTEM,
        )

    def _build_result(self, value: str, source: str) -> Optional[DateExtractionResult]:
        parsed = self._parse_date_text(value)
        if parsed is None:
            return None

        return DateExtractionResult(
            date_taken=parsed.strftime("%Y:%m:%d %H:%M:%S"),
            year=parsed.year,
            month=parsed.month,
            day=parsed.day,
            date_source=source,
        )

    def _parse_date_text(self, value: str) -> Optional[datetime]:
        text = (value or "").strip()
        if not text:
            return None

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

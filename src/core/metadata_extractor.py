from pathlib import Path
from typing import Any, Dict, Optional

from core.date_extraction_service import DateExtractionService


try:
    from PIL import Image
except ImportError:  # pragma: no cover - depends on runtime environment
    Image = None


EXIF_TAGS = {
    "camera_make": 271,
    "camera_model": 272,
    "orientation": 274,
}

IMAGE_METADATA_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


_date_extraction_service = DateExtractionService()


def extract_basic_metadata(path: Optional[Path | str] = None) -> Dict[str, Any]:
    if not path:
        return {}

    file_path = Path(path)
    if not file_path.exists():
        return {}

    metadata: Dict[str, Any] = {
        "width": None,
        "height": None,
        "date_taken": None,
        "year": None,
        "month": None,
        "day": None,
        "camera_make": None,
        "camera_model": None,
        "orientation": None,
        "has_gps": False,
        "date_source": None,
    }

    exif = None
    if Image is not None and file_path.suffix.lower() in IMAGE_METADATA_EXTENSIONS:
        try:
            with Image.open(file_path) as image:
                metadata["width"] = image.width
                metadata["height"] = image.height

                exif = image.getexif()
                if exif:
                    make = exif.get(EXIF_TAGS["camera_make"])
                    if make:
                        metadata["camera_make"] = str(make)

                    model = exif.get(EXIF_TAGS["camera_model"])
                    if model:
                        metadata["camera_model"] = str(model)

                    orientation = exif.get(EXIF_TAGS["orientation"])
                    if orientation is not None:
                        metadata["orientation"] = int(orientation)

                    gps_info = exif.get(34853)
                    metadata["has_gps"] = bool(gps_info)
        except Exception as exc:
            print(f"Metadata extraction warning for {file_path}: {exc}")

    date_result = _date_extraction_service.extract_date(file_path=file_path, exif=exif)
    metadata["date_taken"] = date_result.date_taken
    metadata["year"] = date_result.year
    metadata["month"] = date_result.month
    metadata["day"] = date_result.day
    metadata["date_source"] = date_result.date_source

    return metadata


def _extract_filename_date(filename: str) -> Optional[str]:
    result = _date_extraction_service._extract_from_filename(filename)
    return result.date_taken if result is not None else None

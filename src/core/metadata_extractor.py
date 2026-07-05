from pathlib import Path
from typing import Any, Dict, Optional


try:
    from PIL import Image
except ImportError:  # pragma: no cover - depends on runtime environment
    Image = None


EXIF_TAGS = {
    "date_taken": 36867,
    "camera_make": 271,
    "camera_model": 272,
    "orientation": 274,
}


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
        "camera_make": None,
        "camera_model": None,
        "orientation": None,
        "has_gps": False,
    }

    if Image is None:
        return metadata

    try:
        with Image.open(file_path) as image:
            metadata["width"] = image.width
            metadata["height"] = image.height

            exif = image.getexif()
            if exif:
                date_taken = exif.get(EXIF_TAGS["date_taken"])
                if date_taken:
                    metadata["date_taken"] = str(date_taken)
                    year, month = _derive_year_month(metadata["date_taken"])
                    metadata["year"] = year
                    metadata["month"] = month

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
        return metadata

    return metadata


def _derive_year_month(date_value: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    if not date_value:
        return None, None

    text = str(date_value).strip()
    if len(text) < 4 or not text[:4].isdigit():
        return None, None

    year = int(text[:4])
    month = None
    if len(text) >= 7 and text[4:5] in {":", "-", "/"} and text[5:7].isdigit():
        month = int(text[5:7])

    return year, month

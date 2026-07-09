import hashlib
from pathlib import Path

from core.image_display_loader import DISPLAY_THUMBNAIL_VERSION


def get_thumbnail_cache_path(photo_path: str) -> Path:
    cache_dir = Path("cache") / "thumbnails"
    cache_dir.mkdir(parents=True, exist_ok=True)

    file = Path(photo_path)
    try:
        stat = file.stat()
        cache_key = f"{DISPLAY_THUMBNAIL_VERSION}_{file.resolve()}_{stat.st_mtime_ns}_{stat.st_size}"
    except OSError:
        cache_key = f"{DISPLAY_THUMBNAIL_VERSION}_{file.resolve()}_0_0"
    filename = hashlib.md5(cache_key.encode("utf-8")).hexdigest() + ".jpg"

    return cache_dir / filename
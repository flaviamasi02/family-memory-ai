import hashlib
from pathlib import Path

from core.display_constants import DISPLAY_THUMBNAIL_VERSION


def get_thumbnail_cache_path(photo_path: str) -> Path:
    cache_dir = Path("cache") / "thumbnails"
    cache_dir.mkdir(parents=True, exist_ok=True)

    file = Path(photo_path)
    try:
        stat = file.stat()
        cache_key = f"{DISPLAY_THUMBNAIL_VERSION}_{file.resolve()}_{stat.st_mtime_ns}_{stat.st_size}"
    except OSError:
        # Fall back to a path-only key so missing/unreadable files still get a
        # stable (though less precise) entry rather than silently colliding.
        resolved = str(file.resolve())
        cache_key = f"{DISPLAY_THUMBNAIL_VERSION}_{resolved}_unavailable"
    filename = hashlib.md5(cache_key.encode("utf-8")).hexdigest() + ".jpg"

    return cache_dir / filename


def get_thumbnail_cache_path_for_identity(photo_path: str, modified_time_ns: int,
                                          file_size: int) -> Path:
    """Resolve a cache key from persisted evidence when the old file moved."""
    cache_dir = Path("cache") / "thumbnails"
    cache_dir.mkdir(parents=True, exist_ok=True)
    resolved = str(Path(photo_path).resolve(strict=False))
    key = f"{DISPLAY_THUMBNAIL_VERSION}_{resolved}_{modified_time_ns}_{file_size}"
    return cache_dir / (hashlib.md5(key.encode("utf-8")).hexdigest() + ".jpg")


def preserve_thumbnail_for_relocation(old_path: str, old_modified_time_ns: int,
                                      old_file_size: int, new_path: str) -> bool:
    old_cache = get_thumbnail_cache_path_for_identity(
        old_path, old_modified_time_ns, old_file_size)
    if not old_cache.is_file():
        return False
    new_cache = get_thumbnail_cache_path(new_path)
    if not new_cache.exists():
        new_cache.write_bytes(old_cache.read_bytes())
    return True

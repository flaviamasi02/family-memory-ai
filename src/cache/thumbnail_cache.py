from __future__ import annotations

import hashlib
from pathlib import Path


_THUMBNAILS_SUBDIR = Path(".familymemory") / "thumbnails"


def get_thumbnail_cache_path(photo_path: str) -> Path:
    """Return the on-disk cache path for a thumbnail derived from *photo_path*.

    Thumbnails are stored in a ``.familymemory/thumbnails/`` directory that
    is created inside the photo's parent directory.  A SHA-256 digest of the
    resolved absolute path is used as the filename so each source image maps
    to a unique, stable cache entry regardless of filename collisions.

    The cache directory is created automatically if it does not yet exist.
    """
    path = Path(photo_path).resolve()
    digest = hashlib.sha256(str(path).encode()).hexdigest()
    cache_dir = path.parent / _THUMBNAILS_SUBDIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{digest}.jpg"

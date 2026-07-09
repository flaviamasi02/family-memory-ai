from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader, QPixmap


_full_pixmap_cache: dict[str, QPixmap] = {}
_thumbnail_pixmap_cache: dict[str, QPixmap] = {}
_thumbnail_image_cache: dict[str, QImage] = {}


# Bump this when display-orientation behavior changes so stale on-disk thumbs are bypassed.
DISPLAY_THUMBNAIL_VERSION = "display-v2"


def load_display_pixmap(file_path: str | Path) -> Optional[QPixmap]:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return None

    signature = _file_signature(path)
    cache_key = f"full:{DISPLAY_THUMBNAIL_VERSION}:{path}:{signature}"
    cached = _full_pixmap_cache.get(cache_key)
    if isinstance(cached, QPixmap) and not cached.isNull():
        return cached

    pixmap = _read_pixmap(path, scaled_size=None)
    if not isinstance(pixmap, QPixmap) or pixmap.isNull():
        return None

    _full_pixmap_cache[cache_key] = pixmap
    return pixmap


def load_display_thumbnail(file_path: str | Path, target_size) -> Optional[QPixmap]:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return None

    size = _normalize_size(target_size)
    if size.width() <= 0 or size.height() <= 0:
        return None

    signature = _file_signature(path)
    cache_key = f"thumb:{DISPLAY_THUMBNAIL_VERSION}:{path}:{signature}:{size.width()}x{size.height()}"
    cached = _thumbnail_pixmap_cache.get(cache_key)
    if isinstance(cached, QPixmap) and not cached.isNull():
        return cached

    pixmap = _read_pixmap(path, scaled_size=size)
    if not isinstance(pixmap, QPixmap) or pixmap.isNull():
        fallback = QPixmap(str(path))
        if isinstance(fallback, QPixmap) and not fallback.isNull():
            pixmap = fallback.scaled(
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            return None

    if pixmap.width() > size.width() or pixmap.height() > size.height():
        pixmap = pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    _thumbnail_pixmap_cache[cache_key] = pixmap
    return pixmap


def load_display_thumbnail_image(file_path: str | Path, target_size) -> Optional[QImage]:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return None

    size = _normalize_size(target_size)
    if size.width() <= 0 or size.height() <= 0:
        return None

    signature = _file_signature(path)
    cache_key = f"thumb_image:{DISPLAY_THUMBNAIL_VERSION}:{path}:{signature}:{size.width()}x{size.height()}"
    cached = _thumbnail_image_cache.get(cache_key)
    if isinstance(cached, QImage) and not cached.isNull():
        return cached

    image = _read_image(path, scaled_size=size)
    if not isinstance(image, QImage) or image.isNull():
        fallback = QImage(str(path))
        if isinstance(fallback, QImage) and not fallback.isNull():
            image = fallback.scaled(
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            return None

    if image.width() > size.width() or image.height() > size.height():
        image = image.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    _thumbnail_image_cache[cache_key] = image
    return image


def _read_pixmap(path: Path, scaled_size: Optional[QSize]) -> Optional[QPixmap]:
    image = _read_image(path, scaled_size=scaled_size)
    if image is None or image.isNull():
        return None

    pixmap = QPixmap.fromImage(image)
    if pixmap.isNull():
        return None

    return pixmap


def _read_image(path: Path, scaled_size: Optional[QSize]) -> Optional[QImage]:
    reader = QImageReader(str(path))
    # Qt auto-transform applies EXIF orientation when available.
    reader.setAutoTransform(True)
    if isinstance(scaled_size, QSize):
        reader.setScaledSize(scaled_size)

    try:
        image = reader.read()
    except Exception:
        return None

    if image.isNull():
        return None

    return image


def _normalize_size(target_size) -> QSize:
    if isinstance(target_size, QSize):
        return QSize(max(1, target_size.width()), max(1, target_size.height()))

    if isinstance(target_size, int):
        edge = max(1, int(target_size))
        return QSize(edge, edge)

    if isinstance(target_size, tuple) and len(target_size) == 2:
        width = max(1, int(target_size[0]))
        height = max(1, int(target_size[1]))
        return QSize(width, height)

    return QSize(1, 1)


def _file_signature(path: Path) -> str:
    try:
        stat = path.stat()
        return f"{int(stat.st_mtime_ns)}:{int(stat.st_size)}"
    except Exception:
        return "0:0"

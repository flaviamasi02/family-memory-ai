"""Single authoritative supported-media boundary for library imports."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TypeVar

SUPPORTED_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"})
SUPPORTED_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".avi", ".mkv"})
SUPPORTED_MEDIA_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS


def is_supported_media_path(value: str | Path) -> bool:
    """Return whether *value* has an explicitly supported media extension."""
    return Path(value).suffix.casefold() in SUPPORTED_MEDIA_EXTENSIONS


def is_supported_image_path(value: str | Path) -> bool:
    return Path(value).suffix.casefold() in SUPPORTED_IMAGE_EXTENSIONS


T = TypeVar("T")


def supported_media_items(items: Iterable[T]) -> list[T]:
    """Defensively filter objects carrying a ``path`` before downstream work."""
    return [item for item in items if is_supported_media_path(getattr(item, "path", ""))]


def supported_image_items(items: Iterable[T]) -> list[T]:
    """Return only image objects eligible for thumbnail decoding."""
    return [item for item in items if is_supported_image_path(getattr(item, "path", ""))]

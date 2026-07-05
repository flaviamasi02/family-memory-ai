from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtGui import QPixmap

from core.image_display_loader import load_display_pixmap, load_display_thumbnail


def load_pixmap_with_orientation(file_path: str | Path) -> Optional[QPixmap]:
    return load_display_pixmap(file_path)


def load_thumbnail_with_orientation(file_path: str | Path, target_size) -> Optional[QPixmap]:
    return load_display_thumbnail(file_path, target_size)

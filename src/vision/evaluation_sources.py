from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

EXCLUDED_IMPORT_FOLDERS = {"_family_memory_deleted_review", "_family_memory_cleanup_review"}
SIDECAR_SUFFIX = ".familymemory.json"

EVALUATION_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


@dataclass(frozen=True)
class EvaluationSourceResult:
    source_id: str
    source_label: str
    paths: tuple[Path, ...] = ()
    available_count: int = 0
    sample_count: int = 0
    available: bool = True
    message: str = ""
    folder: Path | None = None


def stable_photo_path(photo) -> Path | None:
    raw = getattr(photo, "path", photo)
    if raw is None:
        return None
    return Path(raw)


def unique_stable_paths(items: Iterable) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for item in items or []:
        path = stable_photo_path(item)
        if path is None:
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def cap_paths(paths: Iterable, max_images: int) -> list[Path]:
    limit = max(1, min(300, int(max_images)))
    return unique_stable_paths(paths)[:limit]


def current_library_source(photos: Iterable, max_images: int) -> EvaluationSourceResult:
    paths = unique_stable_paths(photos)
    if not paths:
        return EvaluationSourceResult(
            "library",
            "Current imported library",
            available=False,
            message="Import a photo library first.",
        )
    capped = tuple(paths[: max(1, min(300, int(max_images)))])
    return EvaluationSourceResult("library", "Current imported library", capped, len(paths), len(capped))


def selected_photos_source(photos: Iterable, max_images: int) -> EvaluationSourceResult:
    paths = unique_stable_paths(photos)
    if not paths:
        return EvaluationSourceResult(
            "selected",
            "Selected photos",
            available=False,
            message="Select one or more photos first.",
        )
    capped = tuple(paths[: max(1, min(300, int(max_images)))])
    return EvaluationSourceResult("selected", "Selected photos", capped, len(paths), len(capped))


def folder_image_paths(folder: Path, max_images: int) -> list[Path]:
    limit = max(1, min(300, int(max_images)))
    paths: list[Path] = []
    for file in Path(folder).rglob("*"):
        if len(paths) >= limit:
            break
        if not file.is_file():
            continue
        if file.name.lower().endswith(SIDECAR_SUFFIX):
            continue
        if any(excluded_folder in file.parts for excluded_folder in EXCLUDED_IMPORT_FOLDERS):
            continue
        if file.suffix.lower() not in EVALUATION_IMAGE_EXTENSIONS:
            continue
        paths.append(file)
    return paths


def another_folder_source(folder: Path | None, max_images: int) -> EvaluationSourceResult:
    if folder is None:
        return EvaluationSourceResult(
            "folder",
            "Another folder",
            available=False,
            message="Choose a folder before running evaluation.",
        )
    paths = folder_image_paths(folder, max_images)
    return EvaluationSourceResult(
        "folder",
        "Another folder",
        tuple(paths),
        len(paths),
        len(paths),
        available=bool(paths),
        message="" if paths else "No eligible images were found in the selected folder.",
        folder=Path(folder),
    )

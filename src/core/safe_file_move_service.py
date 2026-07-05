from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path


CLEANUP_REVIEW_FOLDER_NAME = "_family_memory_cleanup_review"


@dataclass
class SafeFileMoveResult:
    destination_folder: Path
    moved_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    moved_files: list[Path] = field(default_factory=list)
    skipped_files: dict[str, str] = field(default_factory=dict)
    failed_files: dict[str, str] = field(default_factory=dict)


def move_files_to_cleanup_review(file_paths: list[str | Path], source_folder: str | Path) -> SafeFileMoveResult:
    destination_folder = Path(source_folder) / CLEANUP_REVIEW_FOLDER_NAME
    destination_folder.mkdir(parents=True, exist_ok=True)

    result = SafeFileMoveResult(destination_folder=destination_folder)
    for file_path in file_paths or []:
        source = Path(file_path)
        if not source.exists():
            result.skipped_count += 1
            result.skipped_files[str(source)] = "source_missing"
            continue

        destination = _build_unique_destination(destination_folder, source.name)
        try:
            shutil.move(str(source), str(destination))
        except Exception as exc:
            result.failed_count += 1
            result.failed_files[str(source)] = str(exc)
            continue

        result.moved_count += 1
        result.moved_files.append(destination)

    return result


def _build_unique_destination(destination_folder: Path, filename: str) -> Path:
    candidate = destination_folder / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while True:
        next_candidate = destination_folder / f"{stem}_{counter}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        counter += 1
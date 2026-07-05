from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path


QUARANTINE_FOLDER_NAME = "_family_memory_deleted_review"


@dataclass
class SafeBulkDeleteResult:
    destination_folder: Path
    moved_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    moved_files: list[Path] = field(default_factory=list)
    failed_files: dict[str, str] = field(default_factory=dict)
    skipped_files: dict[str, str] = field(default_factory=dict)


def move_files_to_quarantine(file_paths: list[str | Path], imported_root: str | Path) -> SafeBulkDeleteResult:
    destination_folder = Path(imported_root) / QUARANTINE_FOLDER_NAME
    destination_folder.mkdir(parents=True, exist_ok=True)

    result = SafeBulkDeleteResult(destination_folder=destination_folder)

    for original in file_paths or []:
        source = Path(original)
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
    target = destination_folder / filename
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    counter = 1
    while True:
        candidate = destination_folder / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
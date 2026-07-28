from __future__ import annotations

import json
import logging
import ntpath
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from core.application_data import ApplicationDataPathService, atomic_write_json
from storage.errors import (
    DuplicateLibraryError,
    InvalidLibraryRootError,
    LibraryNotFoundError,
    RegistryCorruptionError,
)

logger = logging.getLogger(__name__)
REGISTRY_VERSION = 1
VALID_STATUSES = {"active", "root_missing", "disconnected", "archived"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalise_source_root(value: str | Path, *, windows: bool | None = None) -> str:
    """Build a deterministic comparison key without requiring the root to exist."""
    raw = os.path.expandvars(os.path.expanduser(str(value).strip()))
    if not raw:
        raise InvalidLibraryRootError("A photo library root is required")
    is_windows = os.name == "nt" if windows is None else windows
    if is_windows:
        raw = raw.replace("/", "\\")
        if not ntpath.isabs(raw):
            raw = ntpath.abspath(raw)
        return ntpath.normcase(ntpath.normpath(raw))
    # Path.resolve also collapses accessible symlinks, while strict=False keeps
    # disconnected/removable roots representable without an I/O requirement.
    return os.path.normpath(str(Path(raw).resolve(strict=False)))


@dataclass(frozen=True)
class LibraryRecord:
    library_id: str
    display_name: str
    source_root: str
    normalised_source_root: str
    created_at: str
    last_opened_at: str | None
    status: str
    schema_version: int
    database_path: str
    last_known_available_at: str | None = None


class LibraryRegistry:
    """Atomic application-level JSON registry containing no photo metadata."""

    def __init__(self, paths: ApplicationDataPathService, *, windows_paths: bool | None = None):
        self.paths = paths
        self.windows_paths = windows_paths
        self._lock = threading.RLock()
        self.paths.initialise()
        self._load()
        logger.info("Library registry initialised")

    def _load(self) -> list[LibraryRecord]:
        if not self.paths.registry_path.exists():
            return []
        try:
            payload = json.loads(self.paths.registry_path.read_text(encoding="utf-8"))
            if payload.get("registry_version") != REGISTRY_VERSION or not isinstance(payload.get("libraries"), list):
                raise ValueError("unsupported registry structure")
            return [LibraryRecord(**item) for item in payload["libraries"]]
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise RegistryCorruptionError("The library registry is invalid and was not replaced") from exc

    def _save(self, records: list[LibraryRecord]) -> None:
        atomic_write_json(self.paths.registry_path, {
            "registry_version": REGISTRY_VERSION,
            "updated_at": _now(),
            "libraries": [asdict(record) for record in records],
        })

    def list_libraries(self) -> list[LibraryRecord]:
        with self._lock:
            return self._load()

    def find_by_id(self, library_id: str) -> LibraryRecord | None:
        return next((item for item in self.list_libraries() if item.library_id == library_id), None)

    def find_by_source_root(self, source_root: str | Path) -> LibraryRecord | None:
        key = normalise_source_root(source_root, windows=self.windows_paths)
        return next((item for item in self.list_libraries() if item.normalised_source_root == key), None)

    def register(self, source_root: str | Path, display_name: str | None = None) -> LibraryRecord:
        source = Path(source_root).expanduser()
        if not source.exists() or not source.is_dir():
            raise InvalidLibraryRootError("The photo library root is unavailable or is not a directory")
        key = normalise_source_root(source, windows=self.windows_paths)
        with self._lock:
            records = self._load()
            existing = next((item for item in records if item.normalised_source_root == key), None)
            if existing:
                logger.info("Existing library reused: %s", existing.library_id)
                return existing
            library_id = str(uuid.uuid4())
            directory = self.paths.library_dir(library_id)
            directory.mkdir(parents=True, exist_ok=True)
            now = _now()
            record = LibraryRecord(
                library_id, display_name or source.name or "Photo Library", str(source), key,
                now, None, "active", 0,
                str(self.paths.library_database_path(library_id).relative_to(self.paths.root)), now,
            )
            records.append(record)
            self._save(records)
            logger.info("Library registered: %s", library_id)
            return record

    def create(self, source_root: str | Path, display_name: str | None = None) -> LibraryRecord:
        if self.find_by_source_root(source_root):
            raise DuplicateLibraryError("That physical root is already registered")
        return self.register(source_root, display_name)

    def _replace(self, library_id: str, **changes: object) -> LibraryRecord:
        with self._lock:
            records = self._load()
            for index, item in enumerate(records):
                if item.library_id == library_id:
                    data = asdict(item)
                    data.update(changes)
                    updated = LibraryRecord(**data)
                    records[index] = updated
                    self._save(records)
                    return updated
        raise LibraryNotFoundError(f"Unknown LibraryID: {library_id}")

    def update_display_name(self, library_id: str, display_name: str) -> LibraryRecord:
        if not display_name.strip():
            raise ValueError("Display name cannot be empty")
        return self._replace(library_id, display_name=display_name.strip())

    def update_source_root(self, library_id: str, source_root: str | Path) -> LibraryRecord:
        source = Path(source_root).expanduser()
        if not source.exists() or not source.is_dir():
            raise InvalidLibraryRootError("The relocated photo library root is unavailable")
        key = normalise_source_root(source, windows=self.windows_paths)
        duplicate = self.find_by_source_root(source)
        if duplicate and duplicate.library_id != library_id:
            raise DuplicateLibraryError("That physical root belongs to another library")
        return self._replace(library_id, source_root=str(source), normalised_source_root=key,
                             status="active", last_known_available_at=_now())

    def mark_last_opened(self, library_id: str, schema_version: int) -> LibraryRecord:
        now = _now()
        return self._replace(library_id, last_opened_at=now, last_known_available_at=now,
                             status="active", schema_version=schema_version)

    def mark_unavailable(self, library_id: str, status: str = "root_missing") -> LibraryRecord:
        if status not in {"root_missing", "disconnected"}:
            raise ValueError("Unavailable status must be root_missing or disconnected")
        return self._replace(library_id, status=status)

    def remove(self, library_id: str) -> None:
        """Remove only the locator record; source, database and caches are untouched."""
        with self._lock:
            records = self._load()
            retained = [item for item in records if item.library_id != library_id]
            if len(retained) == len(records):
                raise LibraryNotFoundError(f"Unknown LibraryID: {library_id}")
            self._save(retained)

"""Transactional registration of an existing import scan in central metadata."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from storage.metadata_store import MetadataStore
from storage.photo_repository import PhotoRepository, normalise_relative_path, utc_now
from storage.schema import SCHEMA_VERSION

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from models.photo import Photo


@dataclass(frozen=True)
class ImportRunResult:
    import_run_id: str
    library_id: str
    status: str
    discovered: int
    created: int
    reused: int
    skipped: int
    failed: int
    elapsed_time_ms: float


class ImportRegistrationService:
    """Own ImportRun lifecycle while reusing the scanner's already-built list."""

    def __init__(self, store: MetadataStore, source_root: str | Path):
        self.store = store
        self.source_root = Path(source_root).resolve(strict=False)
        self.repository = PhotoRepository(store)
        self.import_run_id = str(uuid4())
        self.started_at = utc_now()
        self.started_perf = time.perf_counter()
        with self.store.work_unit() as connection:
            connection.execute(
                "INSERT INTO import_runs(import_run_id,library_id,source_root,started_at,status,"
                "schema_version) VALUES (?,?,?,?,?,?)",
                (self.import_run_id, store.library_id, str(self.source_root), self.started_at,
                 "running", SCHEMA_VERSION),
            )

    def register(self, photos: list[Photo], *, skipped: int = 0) -> ImportRunResult:
        created = reused = changed = failed = 0
        discovered = len(photos) + skipped
        elapsed_ms = 0.0
        try:
            with self.store.work_unit() as connection:
                for photo in photos:
                    relative = str(photo.path.resolve(strict=False).relative_to(self.source_root))
                    key = normalise_relative_path(relative)
                    location = self.repository.get_location(key, connection=connection)
                    event = "reused"
                    if location is None:
                        record = self.repository.create_photo(
                            media_type="video" if photo.extension.lower() in {".mp4", ".mov", ".avi", ".mkv"} else "image",
                            width=_positive_int(photo.metadata.get("width")),
                            height=_positive_int(photo.metadata.get("height")),
                            captured_at=_text(photo.metadata.get("date_taken")),
                            connection=connection,
                        )
                        location = self.repository.create_location(
                            record.photo_id, source_path=str(photo.path), relative_path=relative,
                            filename=photo.filename, file_size=photo.file_size,
                            modified_time_ns=photo.modified_time_ns,
                            import_run_id=self.import_run_id, connection=connection,
                        )
                        created += 1
                        event = "created"
                    else:
                        if (location.file_size != photo.file_size or
                                location.modified_time_ns != photo.modified_time_ns):
                            changed += 1
                            event = "changed"
                        else:
                            reused += 1
                        self.repository.refresh_location(
                            location.location_id, source_path=str(photo.path), filename=photo.filename,
                            file_size=photo.file_size, modified_time_ns=photo.modified_time_ns,
                            import_run_id=self.import_run_id, connection=connection,
                        )
                    photo.id = location.photo_id
                    connection.execute(
                        "INSERT INTO import_run_items(import_run_item_id,import_run_id,photo_id,"
                        "location_id,normalised_path_key,event) VALUES (?,?,?,?,?,?)",
                        (str(uuid4()), self.import_run_id, location.photo_id,
                         location.location_id, key, event),
                    )
                elapsed_ms = (time.perf_counter() - self.started_perf) * 1000
                connection.execute(
                    "UPDATE import_runs SET completed_at=?,status='completed',discovered_count=?,"
                    "created_count=?,reused_count=?,changed_count=?,skipped_count=?,failed_count=?,"
                    "elapsed_time_ms=? WHERE import_run_id=?",
                    (utc_now(), discovered, created, reused, changed, skipped, failed,
                     elapsed_ms, self.import_run_id),
                )
        except Exception as exc:
            self.fail(str(exc), discovered=discovered, skipped=skipped)
            raise
        logger.info(
            "Import registered: library=%s run=%s discovered=%s created=%s reused=%s changed=%s skipped=%s",
            self.store.library_id, self.import_run_id, discovered, created, reused, changed, skipped,
        )
        return ImportRunResult(self.import_run_id, str(self.store.library_id), "completed",
                               discovered, created, reused, skipped, failed, elapsed_ms)

    def fail(self, error: str, *, discovered: int = 0, skipped: int = 0) -> None:
        elapsed_ms = (time.perf_counter() - self.started_perf) * 1000
        with self.store.work_unit() as connection:
            connection.execute(
                "UPDATE import_runs SET completed_at=?,status='failed',discovered_count=?,"
                "skipped_count=?,failed_count=1,error_summary=?,elapsed_time_ms=? "
                "WHERE import_run_id=? AND status='running'",
                (utc_now(), discovered, skipped, error[:1000], elapsed_ms, self.import_run_id),
            )


def _positive_int(value) -> int | None:
    return value if isinstance(value, int) and value > 0 else None


def _text(value) -> str | None:
    return str(value) if value is not None else None

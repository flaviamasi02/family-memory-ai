"""Change planning and transactional synchronization for folder imports."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from storage.metadata_store import MetadataStore
from storage.photo_repository import (
    PhotoLocationRecord, PhotoRepository, normalise_relative_path, utc_now,
)
from storage.schema import SCHEMA_VERSION

if TYPE_CHECKING:
    from models.photo import Photo

logger = logging.getLogger(__name__)
FINGERPRINT_BYTES = 1024 * 1024


def partial_fingerprint(path: Path, file_size: int) -> str:
    digest = hashlib.sha256()
    digest.update(str(file_size).encode("ascii"))
    with path.open("rb") as source:
        digest.update(source.read(FINGERPRINT_BYTES))
    return digest.hexdigest()


@dataclass(frozen=True)
class FileObservation:
    path: Path
    relative_path: str
    normalised_path_key: str
    filename: str
    file_size: int
    modified_time_ns: int


@dataclass(frozen=True)
class SyncItem:
    observation: FileObservation
    state: str
    photo_id: str | None = None
    previous_location: PhotoLocationRecord | None = None
    fingerprint: str | None = None


@dataclass(frozen=True)
class SyncPlan:
    items: tuple[SyncItem, ...]
    removed: tuple[PhotoLocationRecord, ...]

    def item_for(self, path: Path) -> SyncItem:
        resolved = path.resolve(strict=False)
        return next(item for item in self.items if item.observation.path == resolved)


@dataclass(frozen=True)
class ImportRunResult:
    import_run_id: str
    library_id: str
    status: str
    discovered: int
    added: int
    unchanged: int
    removed: int
    moved: int
    renamed: int
    updated: int
    skipped: int
    failed: int
    elapsed_time_ms: float

    @property
    def created(self) -> int:
        return self.added

    @property
    def reused(self) -> int:
        return self.unchanged + self.moved + self.renamed


class ImportRegistrationService:
    """Plan filesystem deltas once and commit their metadata as one batch."""

    def __init__(self, store: MetadataStore, source_root: str | Path):
        self.store = store
        self.source_root = Path(source_root).resolve(strict=False)
        self.repository = PhotoRepository(store)
        self.import_run_id = str(uuid4())
        self.started_at = utc_now()
        self.started_perf = time.perf_counter()
        self.plan: SyncPlan | None = None
        with self.store.work_unit() as connection:
            connection.execute(
                "INSERT INTO import_runs(import_run_id,library_id,source_root,started_at,status,"
                "schema_version) VALUES (?,?,?,?,?,?)",
                (self.import_run_id, store.library_id, str(self.source_root), self.started_at,
                 "running", SCHEMA_VERSION),
            )

    def plan_changes(self, observations: list[FileObservation]) -> SyncPlan:
        locations = self.repository.list_locations()
        by_key = {location.normalised_path_key: location for location in locations}
        observed_keys = {item.normalised_path_key for item in observations}
        unmatched = [location for location in locations
                     if location.normalised_path_key not in observed_keys]
        fingerprint_candidates: dict[tuple[str, int], list[PhotoLocationRecord]] = {}
        for location in unmatched:
            if location.partial_fingerprint:
                fingerprint_candidates.setdefault(
                    (location.partial_fingerprint, location.file_size), []).append(location)

        planned: list[SyncItem] = []
        matched_location_ids: set[str] = set()
        for observation in observations:
            existing = by_key.get(observation.normalised_path_key)
            if existing is not None:
                unchanged = (existing.file_size == observation.file_size and
                             existing.modified_time_ns == observation.modified_time_ns and
                             existing.availability == "available")
                fingerprint = existing.partial_fingerprint
                # Upgrade DATA-001C locations once. Later unchanged runs perform
                # no content read and no database UPDATE.
                if not fingerprint:
                    fingerprint = partial_fingerprint(observation.path, observation.file_size)
                planned.append(SyncItem(observation, "unchanged" if unchanged else "updated",
                                        existing.photo_id, existing, fingerprint))
                matched_location_ids.add(existing.location_id)
                continue

            fingerprint = partial_fingerprint(observation.path, observation.file_size)
            candidates = fingerprint_candidates.get((fingerprint, observation.file_size), [])
            candidates = [candidate for candidate in candidates
                          if candidate.location_id not in matched_location_ids]
            if len(candidates) == 1:
                previous = candidates[0]
                old_relative = Path(previous.root_relative_path)
                new_relative = Path(observation.relative_path)
                parent_changed = old_relative.parent != new_relative.parent
                name_changed = old_relative.name != new_relative.name
                state = "moved" if parent_changed else "renamed" if name_changed else "moved"
                planned.append(SyncItem(observation, state, previous.photo_id,
                                        previous, fingerprint))
                matched_location_ids.add(previous.location_id)
            else:
                planned.append(SyncItem(observation, "added", fingerprint=fingerprint))

        removed = tuple(location for location in unmatched
                        if location.location_id not in matched_location_ids
                        and location.availability == "available")
        self.plan = SyncPlan(tuple(planned), removed)
        return self.plan

    def register(self, photos: list[Photo], *, skipped: int = 0,
                 plan: SyncPlan | None = None) -> ImportRunResult:
        plan = plan or self.plan
        if plan is None:
            observations = [_observation(self.source_root, photo) for photo in photos]
            plan = self.plan_changes(observations)
        photos_by_key = {
            normalise_relative_path(str(photo.path.resolve(strict=False).relative_to(self.source_root))): photo
            for photo in photos
        }
        counts = {name: 0 for name in ("added", "unchanged", "removed", "moved", "renamed", "updated")}
        discovered = len(plan.items) + skipped
        try:
            with self.store.work_unit() as connection:
                for item in plan.items:
                    photo = photos_by_key[item.observation.normalised_path_key]
                    location = item.previous_location
                    if item.state == "added":
                        record = self.repository.create_photo(
                            media_type="video" if photo.extension.lower() in {".mp4", ".mov", ".avi", ".mkv"} else "image",
                            width=_positive_int(photo.metadata.get("width")),
                            height=_positive_int(photo.metadata.get("height")),
                            captured_at=_text(photo.metadata.get("date_taken")), connection=connection)
                        location = self.repository.create_location(
                            record.photo_id, source_path=str(photo.path),
                            relative_path=item.observation.relative_path, filename=photo.filename,
                            file_size=photo.file_size, modified_time_ns=photo.modified_time_ns,
                            import_run_id=self.import_run_id,
                            partial_fingerprint=item.fingerprint,
                            fingerprint_algorithm="sha256-first-1mib-size",
                            fingerprint_version=1, connection=connection)
                    elif item.state in {"moved", "renamed"}:
                        self.repository.mark_location_missing(
                            location.location_id, self.import_run_id, connection=connection)
                        location = self.repository.create_location(
                            item.photo_id, source_path=str(photo.path),
                            relative_path=item.observation.relative_path, filename=photo.filename,
                            file_size=photo.file_size, modified_time_ns=photo.modified_time_ns,
                            import_run_id=self.import_run_id,
                            partial_fingerprint=item.fingerprint,
                            fingerprint_algorithm="sha256-first-1mib-size",
                            fingerprint_version=1, connection=connection)
                        connection.execute("UPDATE photos SET status='active',updated_at=? WHERE photo_id=?",
                                           (utc_now(), item.photo_id))
                    elif item.state == "updated":
                        self.repository.refresh_location(
                            location.location_id, source_path=str(photo.path), filename=photo.filename,
                            file_size=photo.file_size, modified_time_ns=photo.modified_time_ns,
                            import_run_id=self.import_run_id, connection=connection)
                        self.repository.set_location_fingerprint(
                            location.location_id, item.fingerprint, connection=connection)
                    elif not location.partial_fingerprint:
                        self.repository.set_location_fingerprint(
                            location.location_id, item.fingerprint, connection=connection)

                    photo.id = item.photo_id or location.photo_id
                    counts[item.state] += 1
                    connection.execute(
                        "INSERT INTO import_run_items(import_run_item_id,import_run_id,photo_id,"
                        "location_id,normalised_path_key,event,fingerprint_evidence) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (str(uuid4()), self.import_run_id, photo.id, location.location_id,
                         item.observation.normalised_path_key, _legacy_event(item.state),
                         item.fingerprint),)

                for location in plan.removed:
                    self.repository.mark_location_missing(
                        location.location_id, self.import_run_id, connection=connection)
                    counts["removed"] += 1
                    connection.execute(
                        "INSERT INTO import_run_items(import_run_item_id,import_run_id,photo_id,"
                        "location_id,normalised_path_key,event) VALUES (?,?,?,?,?,'missing')",
                        (str(uuid4()), self.import_run_id, location.photo_id,
                         location.location_id, location.normalised_path_key))

                elapsed_ms = (time.perf_counter() - self.started_perf) * 1000
                connection.execute(
                    "UPDATE import_runs SET completed_at=?,status='completed',discovered_count=?,"
                    "created_count=?,reused_count=?,changed_count=?,missing_count=?,skipped_count=?,"
                    "unchanged_count=?,added_count=?,removed_count=?,moved_count=?,renamed_count=?,"
                    "updated_count=?,elapsed_time_ms=? WHERE import_run_id=?",
                    (utc_now(), discovered, counts["added"], counts["unchanged"] + counts["moved"] + counts["renamed"],
                     counts["updated"], counts["removed"], skipped, counts["unchanged"],
                     counts["added"], counts["removed"], counts["moved"], counts["renamed"],
                     counts["updated"], elapsed_ms, self.import_run_id))
        except Exception as exc:
            self.fail(str(exc), discovered=discovered, skipped=skipped)
            raise
        logger.info("Incremental import registered: library=%s run=%s counts=%s",
                    self.store.library_id, self.import_run_id, counts)
        return ImportRunResult(self.import_run_id, str(self.store.library_id), "completed",
            discovered, counts["added"], counts["unchanged"], counts["removed"],
            counts["moved"], counts["renamed"], counts["updated"], skipped, 0, elapsed_ms)

    def fail(self, error: str, *, discovered: int = 0, skipped: int = 0) -> None:
        elapsed_ms = (time.perf_counter() - self.started_perf) * 1000
        with self.store.work_unit() as connection:
            connection.execute(
                "UPDATE import_runs SET completed_at=?,status='failed',discovered_count=?,"
                "skipped_count=?,failed_count=1,error_summary=?,elapsed_time_ms=? "
                "WHERE import_run_id=? AND status='running'",
                (utc_now(), discovered, skipped, error[:1000], elapsed_ms, self.import_run_id))


def _observation(root: Path, photo) -> FileObservation:
    relative = str(photo.path.resolve(strict=False).relative_to(root))
    return FileObservation(photo.path.resolve(strict=False), relative,
        normalise_relative_path(relative), photo.filename, photo.file_size, photo.modified_time_ns)


def _legacy_event(state: str) -> str:
    return {"added": "created", "unchanged": "reused", "updated": "changed",
            "moved": "changed", "renamed": "changed"}[state]


def _positive_int(value) -> int | None:
    return value if isinstance(value, int) and value > 0 else None


def _text(value) -> str | None:
    return str(value) if value is not None else None

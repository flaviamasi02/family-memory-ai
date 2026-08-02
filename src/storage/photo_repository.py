"""Repository boundary for stable photos and their observed file locations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from storage.metadata_store import MetadataStore


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalise_relative_path(value: str | Path) -> str:
    """Return a portable, case-aware key for a path relative to a library."""
    key = os.path.normpath(str(value)).replace("\\", "/")
    return key.casefold() if os.name == "nt" else key


@dataclass(frozen=True)
class PhotoRecord:
    photo_id: str
    library_id: str
    media_type: str
    width: int | None
    height: int | None
    captured_at: str | None
    content_hash: str | None
    hash_algorithm: str | None
    hash_version: int | None
    status: str
    metadata_revision: int
    automatic_media_category: str | None
    effective_media_category: str | None
    relevance_category: str | None
    is_album_relevant_candidate: int | None
    classification_confidence: float | None
    classification_reason: str | None
    trash_workflow_state: str | None
    trash_proposal_confidence: float | None
    trash_proposal_source: str | None
    trash_proposal_explanation: str | None
    is_active: int


@dataclass(frozen=True)
class PhotoLocationRecord:
    location_id: str
    photo_id: str
    library_id: str
    source_path: str
    root_relative_path: str
    normalised_path_key: str
    filename: str
    file_size: int
    modified_time_ns: int
    partial_fingerprint: str | None
    fingerprint_algorithm: str | None
    fingerprint_version: int | None
    availability: str


class PhotoRepository:
    """CRUD/query operations using MetadataStore-owned work units.

    A caller performing a bulk import can pass its transaction connection to
    every method, avoiding one transaction and connection per photo.
    """

    def __init__(self, store: MetadataStore):
        self.store = store

    @staticmethod
    def _photo(row: Any | None) -> PhotoRecord | None:
        return PhotoRecord(*row) if row else None

    @staticmethod
    def _location(row: Any | None) -> PhotoLocationRecord | None:
        return PhotoLocationRecord(*row) if row else None

    @staticmethod
    def _photo_columns() -> str:
        return ("photo_id,library_id,media_type,width,height,captured_at,content_hash,"
                "hash_algorithm,hash_version,status,metadata_revision,automatic_media_category,"
                "effective_media_category,relevance_category,is_album_relevant_candidate,"
                "classification_confidence,classification_reason,trash_workflow_state,"
                "trash_proposal_confidence,trash_proposal_source,trash_proposal_explanation,is_active")

    @staticmethod
    def _location_columns() -> str:
        return ("location_id,photo_id,library_id,source_path,root_relative_path,"
                "normalised_path_key,filename,file_size,modified_time_ns,partial_fingerprint,"
                "fingerprint_algorithm,fingerprint_version,availability")

    def create_photo(self, *, media_type: str = "image", width: int | None = None,
                     height: int | None = None, captured_at: str | None = None,
                     content_hash: str | None = None, hash_algorithm: str | None = None,
                     hash_version: int | None = None,
                     automatic_media_category: str | None = None,
                     effective_media_category: str | None = None,
                     relevance_category: str | None = None,
                     is_album_relevant_candidate: bool | None = None,
                     classification_confidence: float | None = None,
                     classification_reason: str | None = None,
                     connection=None) -> PhotoRecord:
        if connection is None:
            with self.store.work_unit() as transaction:
                return self.create_photo(media_type=media_type, width=width, height=height,
                    captured_at=captured_at, content_hash=content_hash,
                    hash_algorithm=hash_algorithm, hash_version=hash_version,
                    automatic_media_category=automatic_media_category,
                    effective_media_category=effective_media_category,
                    relevance_category=relevance_category,
                    is_album_relevant_candidate=is_album_relevant_candidate,
                    classification_confidence=classification_confidence,
                    classification_reason=classification_reason,
                    connection=transaction)
        photo_id = str(uuid4())
        connection.execute(
            "INSERT INTO photos(photo_id,library_id,media_type,width,height,captured_at,"
            "content_hash,hash_algorithm,hash_version,automatic_media_category,"
            "effective_media_category,relevance_category,is_album_relevant_candidate,"
            "classification_confidence,classification_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (photo_id, self.store.library_id, media_type, width, height, captured_at,
             content_hash, hash_algorithm, hash_version, automatic_media_category,
             effective_media_category, relevance_category,
             None if is_album_relevant_candidate is None else int(is_album_relevant_candidate),
             classification_confidence, classification_reason),
        )
        return PhotoRecord(
            photo_id, str(self.store.library_id), media_type, width, height, captured_at,
            content_hash, hash_algorithm, hash_version, "active", 1,
            automatic_media_category, effective_media_category, relevance_category,
            None if is_album_relevant_candidate is None else int(is_album_relevant_candidate),
            classification_confidence, classification_reason,
            None, None, None, None, 1,
        )

    def update_photo(self, photo_id: str, *, connection=None, **changes) -> PhotoRecord:
        allowed = {"media_type", "width", "height", "captured_at", "camera_make",
                   "camera_model", "content_hash", "hash_algorithm", "hash_version", "status"}
        allowed.update({"automatic_media_category", "effective_media_category",
                        "relevance_category", "is_album_relevant_candidate",
                        "classification_confidence", "classification_reason"})
        allowed.update({"trash_workflow_state", "trash_proposal_confidence", "trash_proposal_source",
                        "trash_proposal_explanation", "is_active"})
        invalid = set(changes) - allowed
        if invalid:
            raise ValueError(f"Unsupported photo fields: {', '.join(sorted(invalid))}")
        if not changes:
            record = self.get_by_id(photo_id, connection=connection)
            if record is None:
                raise KeyError(photo_id)
            return record
        if connection is None:
            with self.store.work_unit() as transaction:
                return self.update_photo(photo_id, connection=transaction, **changes)
        assignments = ",".join(f"{name}=?" for name in changes)
        cursor = connection.execute(
            f"UPDATE photos SET {assignments},metadata_revision=metadata_revision+1,updated_at=? "
            "WHERE photo_id=? AND library_id=?",
            (*changes.values(), utc_now(), photo_id, self.store.library_id),
        )
        if not cursor.rowcount:
            raise KeyError(photo_id)
        return self.get_by_id(photo_id, connection=connection)

    def get_by_id(self, photo_id: str, *, connection=None) -> PhotoRecord | None:
        if connection is None:
            with self.store.read_connection() as reader:
                return self.get_by_id(photo_id, connection=reader)
        row = connection.execute(
            f"SELECT {self._photo_columns()} FROM photos WHERE photo_id=? AND library_id=?",
            (photo_id, self.store.library_id),
        ).fetchone()
        return self._photo(row)

    def get_by_relative_path(self, relative_path: str | Path, *, connection=None) -> PhotoRecord | None:
        key = normalise_relative_path(relative_path)
        if connection is None:
            with self.store.read_connection() as reader:
                return self.get_by_relative_path(key, connection=reader)
        row = connection.execute(
            f"SELECT {','.join('p.' + c for c in self._photo_columns().split(','))} "
            "FROM photos p JOIN photo_locations l ON l.photo_id=p.photo_id "
            "WHERE l.library_id=? AND l.normalised_path_key=? AND l.availability!='deleted'",
            (self.store.library_id, key),
        ).fetchone()
        return self._photo(row)

    def get_by_fingerprint(self, fingerprint: str, *, file_size: int | None = None,
                           connection=None) -> list[PhotoRecord]:
        if connection is None:
            with self.store.read_connection() as reader:
                return self.get_by_fingerprint(fingerprint, file_size=file_size, connection=reader)
        size_sql, parameters = (" AND l.file_size=?", [self.store.library_id, fingerprint, file_size]) \
            if file_size is not None else ("", [self.store.library_id, fingerprint])
        rows = connection.execute(
            f"SELECT DISTINCT {','.join('p.' + c for c in self._photo_columns().split(','))} "
            "FROM photos p JOIN photo_locations l ON l.photo_id=p.photo_id "
            "WHERE l.library_id=? AND (l.partial_fingerprint=? OR p.content_hash=?)" + size_sql,
            ([parameters[0], fingerprint, fingerprint] + parameters[2:]),
        ).fetchall()
        return [self._photo(row) for row in rows]

    def list_library_photos(self, *, connection=None) -> list[PhotoRecord]:
        if connection is None:
            with self.store.read_connection() as reader:
                return self.list_library_photos(connection=reader)
        rows = connection.execute(
            f"SELECT {self._photo_columns()} FROM photos WHERE library_id=? ORDER BY created_at,photo_id",
            (self.store.library_id,),
        ).fetchall()
        return [self._photo(row) for row in rows]

    def list_active_photos(self, *, connection=None) -> list[PhotoRecord]:
        if connection is None:
            with self.store.read_connection() as reader:
                return self.list_active_photos(connection=reader)
        rows = connection.execute(
            f"SELECT {self._photo_columns()} FROM photos WHERE library_id=? AND is_active=1 ORDER BY created_at,photo_id",
            (self.store.library_id,),
        ).fetchall()
        return [self._photo(row) for row in rows]

    def apply_trash_results(self, results, *, connection=None) -> None:
        """Persist a batch of service records and immutable audit rows."""
        if connection is None:
            with self.store.work_unit() as transaction:
                self.apply_trash_results(results, connection=transaction)
                return
        for record in results:
            active = int(record.state not in {"moved_to_trash"})
            connection.execute(
                "UPDATE photos SET trash_workflow_state=?,is_active=?,updated_at=? WHERE photo_id=? AND library_id=?",
                (record.state, active, utc_now(), record.photo_id, self.store.library_id),
            )
            event = record.history[-1] if record.history else {"action": record.state}
            connection.execute(
                "INSERT INTO trash_history(trash_history_id,photo_id,library_id,action,source_path,destination_path,error,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (str(uuid4()), record.photo_id, self.store.library_id, event.get("action", record.state),
                 event.get("source", record.source_path), event.get("destination", record.destination_path),
                 event.get("error", record.error), event.get("timestamp", utc_now())),
            )

    def list_trash_history(self, *, connection=None) -> list[dict[str, object]]:
        """Return one bounded projection per photo for the explicit history view."""
        if connection is None:
            with self.store.read_connection() as reader:
                return self.list_trash_history(connection=reader)
        rows = connection.execute(
            "SELECT p.photo_id,p.trash_workflow_state,p.is_active,p.trash_proposal_confidence,"
            "p.trash_proposal_source,p.trash_proposal_explanation,h.source_path,h.destination_path,"
            "h.error,h.created_at FROM photos p JOIN trash_history h ON h.trash_history_id=("
            "SELECT h2.trash_history_id FROM trash_history h2 WHERE h2.photo_id=p.photo_id "
            "ORDER BY h2.created_at DESC,h2.trash_history_id DESC LIMIT 1) "
            "WHERE p.library_id=? AND p.trash_workflow_state IS NOT NULL ORDER BY h.created_at DESC",
            (self.store.library_id,),
        ).fetchall()
        keys = ("photo_id", "trash_workflow_state", "is_active", "trash_proposal_confidence",
                "trash_proposal_source", "trash_proposal_explanation", "source_path",
                "destination_path", "error", "created_at")
        return [dict(zip(keys, row)) for row in rows]
    def get_location(self, relative_path: str | Path, *, connection=None) -> PhotoLocationRecord | None:
        key = normalise_relative_path(relative_path)
        if connection is None:
            with self.store.read_connection() as reader:
                return self.get_location(key, connection=reader)
        return self._location(connection.execute(
            f"SELECT {self._location_columns()} FROM photo_locations "
            "WHERE library_id=? AND normalised_path_key=?",
            (self.store.library_id, key),
        ).fetchone())

    def list_locations(self, *, connection=None) -> list[PhotoLocationRecord]:
        if connection is None:
            with self.store.read_connection() as reader:
                return self.list_locations(connection=reader)
        rows = connection.execute(
            f"SELECT {self._location_columns()} FROM photo_locations "
            "WHERE library_id=? AND availability!='deleted' ORDER BY normalised_path_key",
            (self.store.library_id,),
        ).fetchall()
        return [self._location(row) for row in rows]

    def list_sync_state(self, *, connection=None) -> list[tuple[PhotoLocationRecord, PhotoRecord]]:
        """Load the import planner projection with one indexed database query."""
        if connection is None:
            with self.store.read_connection() as reader:
                return self.list_sync_state(connection=reader)
        location_columns = ",".join(f"l.{column}" for column in self._location_columns().split(","))
        photo_columns = ",".join(f"p.{column}" for column in self._photo_columns().split(","))
        rows = connection.execute(
            f"SELECT {location_columns},{photo_columns} FROM photo_locations l "
            "JOIN photos p ON p.photo_id=l.photo_id "
            "WHERE l.library_id=? AND l.availability!='deleted' "
            "ORDER BY l.normalised_path_key",
            (self.store.library_id,),
        ).fetchall()
        location_count = len(self._location_columns().split(","))
        return [
            (self._location(row[:location_count]), self._photo(row[location_count:]))
            for row in rows
        ]

    def create_location(self, photo_id: str, *, source_path: str, relative_path: str,
                        filename: str, file_size: int, modified_time_ns: int,
                        import_run_id: str, partial_fingerprint: str | None = None,
                        fingerprint_algorithm: str | None = None,
                        fingerprint_version: int | None = None, connection=None) -> PhotoLocationRecord:
        if connection is None:
            with self.store.work_unit() as transaction:
                return self.create_location(photo_id, source_path=source_path,
                    relative_path=relative_path, filename=filename, file_size=file_size,
                    modified_time_ns=modified_time_ns, import_run_id=import_run_id,
                    partial_fingerprint=partial_fingerprint,
                    fingerprint_algorithm=fingerprint_algorithm,
                    fingerprint_version=fingerprint_version, connection=transaction)
        location_id, now = str(uuid4()), utc_now()
        key = normalise_relative_path(relative_path)
        connection.execute(
            "INSERT INTO photo_locations(location_id,photo_id,library_id,source_path,"
            "root_relative_path,normalised_path_key,filename,extension,file_size,modified_time_ns,"
            "partial_fingerprint,fingerprint_algorithm,fingerprint_version,first_seen_run_id,"
            "last_seen_run_id,first_seen_at,last_seen_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (location_id, photo_id, self.store.library_id, source_path, relative_path, key,
             filename, Path(filename).suffix.lower(), file_size, modified_time_ns,
             partial_fingerprint, fingerprint_algorithm, fingerprint_version,
             import_run_id, import_run_id, now, now),
        )
        connection.execute("UPDATE photos SET preferred_location_id=? WHERE photo_id=?",
                           (location_id, photo_id))
        return PhotoLocationRecord(
            location_id, photo_id, str(self.store.library_id), source_path, relative_path,
            key, filename, file_size, modified_time_ns, partial_fingerprint,
            fingerprint_algorithm, fingerprint_version, "available",
        )

    def refresh_location(self, location_id: str, *, source_path: str, filename: str,
                         file_size: int, modified_time_ns: int, import_run_id: str,
                         connection) -> None:
        connection.execute(
            "UPDATE photo_locations SET source_path=?,filename=?,extension=?,file_size=?,"
            "modified_time_ns=?,availability='available',last_seen_run_id=?,last_seen_at=?,"
            "removed_at=NULL,updated_at=? WHERE location_id=? AND library_id=?",
            (source_path, filename, Path(filename).suffix.lower(), file_size, modified_time_ns,
             import_run_id, utc_now(), utc_now(), location_id, self.store.library_id),
        )
        connection.execute(
            "UPDATE photos SET status='active',deleted_at=NULL,updated_at=? WHERE photo_id="
            "(SELECT photo_id FROM photo_locations WHERE location_id=?) AND status!='active'",
            (utc_now(), location_id),
        )

    def set_location_fingerprint(self, location_id: str, fingerprint: str, *, connection) -> None:
        connection.execute(
            "UPDATE photo_locations SET partial_fingerprint=?,fingerprint_algorithm=?,"
            "fingerprint_version=?,updated_at=? WHERE location_id=? AND library_id=?",
            (fingerprint, "sha256-first-1mib-size", 1, utc_now(), location_id,
             self.store.library_id),
        )

    def mark_location_missing(self, location_id: str, import_run_id: str, *, connection) -> None:
        now = utc_now()
        connection.execute(
            "UPDATE photo_locations SET availability='missing',last_seen_run_id=?,removed_at=?,"
            "updated_at=? WHERE location_id=? AND library_id=? AND availability='available'",
            (import_run_id, now, now, location_id, self.store.library_id),
        )
        connection.execute(
            "UPDATE photos SET status='missing',updated_at=? WHERE photo_id=(SELECT photo_id "
            "FROM photo_locations WHERE location_id=?) AND NOT EXISTS (SELECT 1 FROM photo_locations "
            "WHERE photo_id=(SELECT photo_id FROM photo_locations WHERE location_id=?) "
            "AND availability='available')",
            (now, location_id, location_id),
        )

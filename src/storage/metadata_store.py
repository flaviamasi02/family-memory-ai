from __future__ import annotations

import contextlib
import logging
import os
import shutil
import sqlite3
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from core.application_data import ApplicationDataPathService
from storage.errors import (
    BackupDestinationConflictError, BackupError, ChecksumMismatchError,
    DatabaseHealthCheckError, DatabaseInitialisationError, InvalidBackupError,
    LibraryNotFoundError, RestoreError, SchemaMigrationError,
    UnavailableLibraryError, UnsupportedSchemaVersionError,
)
from storage.library_registry import LibraryRecord, LibraryRegistry
from storage.schema import MIGRATIONS, REQUIRED_TABLES, SCHEMA_VERSION

# Kept as a compatibility injection seam for the DATA-001A rollback test.  The
# persisted migration remains the immutable definition in ``storage.schema``.
MIGRATION_STATEMENTS = MIGRATIONS[0].statements

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackupResult:
    source_path: str
    destination_path: str
    schema_version: int
    integrity: str


@dataclass(frozen=True)
class RestoreResult:
    backup_path: str
    database_path: str
    safety_copy_path: str
    schema_version: int
    healthy: bool


class MetadataStore:
    """Lifecycle and connection-per-work-unit boundary for one library database."""

    def __init__(self, paths: ApplicationDataPathService, registry: LibraryRegistry):
        self.paths, self.registry = paths, registry
        self._record: LibraryRecord | None = None
        self._operation_lock = threading.RLock()
        self._restoring = False

    @property
    def library_id(self) -> str | None:
        return self._record.library_id if self._record else None

    @property
    def database_path(self) -> Path | None:
        return self.paths.library_database_path(self._record.library_id) if self._record else None

    def open_library(self, library_id: str) -> None:
        with self._operation_lock:
            if self._record and self._record.library_id == library_id:
                return
            if self._record:
                raise DatabaseInitialisationError("Close the current library before opening another")
            record = self.registry.find_by_id(library_id)
            if not record:
                raise LibraryNotFoundError(f"Unknown LibraryID: {library_id}")
            if not Path(record.source_root).is_dir():
                self.registry.mark_unavailable(library_id)
                raise UnavailableLibraryError("The library source root is unavailable")
            self._record = record
            try:
                self.initialise_schema()
                report = self.health_check()
                if not report["healthy"]:
                    raise DatabaseHealthCheckError("The library database failed its health check")
                self.registry.mark_last_opened(library_id, self.get_schema_version())
            except Exception:
                self._record = None
                raise

    def close_library(self) -> None:
        with self._operation_lock:
            if self._record:
                logger.info("Metadata store closed: %s", self._record.library_id)
            self._record = None

    close = close_library

    def _require_path(self) -> Path:
        if not self._record or not self.database_path:
            raise LibraryNotFoundError("No library is open")
        return self.database_path

    @staticmethod
    def _configure(connection: sqlite3.Connection, *, wal: bool = True) -> sqlite3.Connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        if wal:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _connect(self) -> sqlite3.Connection:
        return self._configure(sqlite3.connect(self._require_path(), timeout=5.0))

    @contextlib.contextmanager
    def work_unit(self) -> Iterator[sqlite3.Connection]:
        """Yield a fresh transaction-owned connection; never share it across threads."""
        with self._operation_lock:
            if self._restoring:
                raise RestoreError("Database restore is in progress")
            connection = self._connect()
            try:
                connection.execute("BEGIN")
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            finally:
                connection.close()

    transaction = work_unit

    def get_schema_version(self) -> int:
        path = self._require_path()
        if not path.exists():
            return 0
        try:
            with contextlib.closing(self._connect()) as connection:
                row = connection.execute("SELECT max(version) FROM schema_migrations").fetchone()
                return int(row[0] or 0)
        except sqlite3.OperationalError:
            return 0

    def _verify_history(self, connection: sqlite3.Connection) -> None:
        try:
            rows = connection.execute("SELECT version,name,checksum FROM schema_migrations ORDER BY version").fetchall()
        except sqlite3.OperationalError:
            return
        known = {migration.version: migration for migration in MIGRATIONS}
        for version, name, checksum in rows:
            if version not in known:
                if version > SCHEMA_VERSION:
                    raise UnsupportedSchemaVersionError(
                        f"Database schema {version} is newer than supported schema {SCHEMA_VERSION}"
                    )
                raise ChecksumMismatchError(f"Unknown migration version {version}")
            migration = known[version]
            if name != migration.name or checksum != migration.checksum:
                raise ChecksumMismatchError(f"Migration history mismatch at version {version}")

    def initialise_schema(self) -> None:
        with self._operation_lock:
            path = self._require_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                current = self.get_schema_version()
                if current > SCHEMA_VERSION:
                    raise UnsupportedSchemaVersionError(
                        f"Database schema {current} is newer than supported schema {SCHEMA_VERSION}"
                    )
                if path.exists() and current:
                    with contextlib.closing(self._connect()) as connection:
                        self._verify_history(connection)
                for migration in MIGRATIONS:
                    if migration.version <= current:
                        continue
                    connection = self._connect()
                    try:
                        connection.execute("BEGIN IMMEDIATE")
                        statements = MIGRATION_STATEMENTS if migration.version == 1 else migration.statements
                        for statement in statements:
                            connection.execute(statement)
                        if migration.version == 1:
                            record = self._record
                            connection.execute(
                                "INSERT INTO libraries VALUES (?,?,?,?,?,?,?,?)",
                                (record.library_id, record.display_name, record.source_root,
                                 record.normalised_source_root, record.created_at, record.last_opened_at,
                                 migration.version, record.status),
                            )
                        else:
                            connection.execute("UPDATE libraries SET schema_version=?", (migration.version,))
                        connection.execute(
                            "INSERT INTO schema_migrations(version,name,checksum) VALUES (?,?,?)",
                            (migration.version, migration.name, migration.checksum),
                        )
                        connection.commit()
                    except BaseException:
                        connection.rollback()
                        raise
                    finally:
                        connection.close()
                    current = migration.version
                    logger.info("Schema migration applied: library=%s version=%s migration=%s",
                                self.library_id, migration.version, migration.name)
            except (UnsupportedSchemaVersionError, ChecksumMismatchError):
                raise
            except Exception as exc:
                raise SchemaMigrationError("Could not apply the library schema migration") from exc

    @staticmethod
    def _inspect_database(path: Path) -> tuple[int, str, list[tuple], set[str]]:
        if not path.is_file():
            raise InvalidBackupError("Database file does not exist")
        try:
            uri = f"file:{path.resolve().as_posix()}?mode=ro"
            with contextlib.closing(sqlite3.connect(uri, uri=True)) as connection:
                integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
                foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
                tables = {r[0] for r in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                if "schema_migrations" not in tables:
                    raise InvalidBackupError("Database has no migration history")
                version = int(connection.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0])
            return version, integrity, foreign_keys, tables
        except InvalidBackupError:
            raise
        except sqlite3.Error as exc:
            raise InvalidBackupError("Database could not be validated") from exc

    def health_check(self) -> dict[str, object]:
        path = self._require_path()
        result: dict[str, object] = {
            "database_path": str(path), "library_id": self.library_id,
            "schema_version": 0, "expected_schema_version": SCHEMA_VERSION,
            "integrity_check": "unavailable", "foreign_key_check": "unavailable",
            "migration_history_consistent": False, "missing_required_tables": [],
            "unsupported_newer_schema": False, "read_available": False,
            "write_available": False, "healthy": False,
        }
        try:
            version, integrity, fk_rows, tables = self._inspect_database(path)
            result.update(schema_version=version, integrity_check=integrity,
                          foreign_key_check="ok" if not fk_rows else f"{len(fk_rows)} violation(s)",
                          missing_required_tables=sorted(REQUIRED_TABLES - tables),
                          unsupported_newer_schema=version > SCHEMA_VERSION, read_available=True)
            with contextlib.closing(self._connect()) as connection:
                self._verify_history(connection)
                result["migration_history_consistent"] = True
                connection.execute("BEGIN")
                connection.execute("CREATE TEMP TABLE IF NOT EXISTS metadata_health_probe(value INTEGER)")
                connection.rollback()
                result["write_available"] = True
            result["healthy"] = all((integrity == "ok", not fk_rows, not result["missing_required_tables"],
                                     not result["unsupported_newer_schema"], result["migration_history_consistent"],
                                     result["read_available"], result["write_available"]))
            return result
        except UnsupportedSchemaVersionError:
            result["unsupported_newer_schema"] = True
            return result
        except (InvalidBackupError, ChecksumMismatchError, sqlite3.Error):
            return result

    def schema_summary(self) -> dict[str, object]:
        """Return the supported schema contract without exposing SQL to callers."""
        version = self.get_schema_version() if self.library_id else 0
        missing: list[str] = []
        if self.library_id:
            missing = list(self.health_check()["missing_required_tables"])
        return {
            "schema_version": version,
            "expected_schema_version": SCHEMA_VERSION,
            "required_table_count": len(REQUIRED_TABLES),
            "missing_required_tables": missing,
            "migrations": [
                {"version": migration.version, "name": migration.name}
                for migration in MIGRATIONS
            ],
        }

    def backup(self, destination_path: str | Path, *, overwrite: bool = False) -> BackupResult:
        with self._operation_lock:
            source, destination = self._require_path().resolve(), Path(destination_path).resolve()
            if destination == source:
                raise BackupError("Backup destination must differ from the live database")
            if destination.exists() and not overwrite:
                raise BackupDestinationConflictError("Backup destination already exists")
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.partial")
            try:
                with contextlib.closing(self._connect()) as source_connection, \
                     contextlib.closing(sqlite3.connect(temporary)) as destination_connection:
                    source_connection.backup(destination_connection)
                version, integrity, foreign_keys, tables = self._inspect_database(temporary)
                if integrity != "ok" or foreign_keys or REQUIRED_TABLES - tables or version > SCHEMA_VERSION:
                    raise InvalidBackupError("Created backup failed validation")
                self._verify_backup_history(temporary)
                os.replace(temporary, destination)
                return BackupResult(str(source), str(destination), version, integrity)
            except (BackupDestinationConflictError, InvalidBackupError):
                temporary.unlink(missing_ok=True)
                raise
            except (OSError, sqlite3.Error) as exc:
                temporary.unlink(missing_ok=True)
                raise BackupError("Database backup failed") from exc

    def validate_backup(self, destination_path: str | Path) -> BackupResult:
        path = Path(destination_path).resolve()
        version, integrity, foreign_keys, tables = self._inspect_database(path)
        if version > SCHEMA_VERSION:
            raise UnsupportedSchemaVersionError(
                f"Backup schema {version} is newer than supported schema {SCHEMA_VERSION}")
        if integrity != "ok" or foreign_keys or REQUIRED_TABLES - tables or version != SCHEMA_VERSION:
            raise InvalidBackupError("Backup failed schema or integrity validation")
        self._verify_backup_history(path)
        return BackupResult(str(self._require_path()), str(path), version, integrity)

    @staticmethod
    def _verify_backup_history(path: Path) -> None:
        try:
            with contextlib.closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as connection:
                rows = connection.execute(
                    "SELECT version,name,checksum FROM schema_migrations ORDER BY version"
                ).fetchall()
            expected = [(m.version, m.name, m.checksum) for m in MIGRATIONS]
            if rows != expected:
                raise InvalidBackupError("Backup migration history is inconsistent")
        except sqlite3.Error as exc:
            raise InvalidBackupError("Backup migration history could not be validated") from exc

    def restore(self, backup_path: str | Path) -> RestoreResult:
        """Validate, safety-copy, atomically replace, then re-open/health-check."""
        with self._operation_lock:
            candidate = Path(backup_path).resolve()
            validated = self.validate_backup(candidate)
            live = self._require_path().resolve()
            safety = live.with_name(f"{live.name}.pre-restore-{uuid4().hex}.bak")
            replacement = live.with_name(f".{live.name}.{uuid4().hex}.restore")
            self._restoring = True
            try:
                # The live database may have committed pages in WAL; use the
                # online API for the recovery copy rather than copying only the
                # main file.
                self.backup(safety)
                shutil.copy2(candidate, replacement)
                os.replace(replacement, live)
                for suffix in ("-wal", "-shm"):
                    Path(f"{live}{suffix}").unlink(missing_ok=True)
                report = self.health_check()
                if not report["healthy"]:
                    raise RestoreError("Restored database failed its health check")
                return RestoreResult(str(candidate), str(live), str(safety), validated.schema_version, True)
            except Exception as exc:
                replacement.unlink(missing_ok=True)
                if safety.exists():
                    shutil.copy2(safety, live)
                if isinstance(exc, (InvalidBackupError, UnsupportedSchemaVersionError, RestoreError)):
                    raise
                raise RestoreError("Database restore failed; the safety copy was retained") from exc
            finally:
                self._restoring = False

from __future__ import annotations

import contextlib
import hashlib
import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from core.application_data import ApplicationDataPathService
from storage.errors import (DatabaseHealthCheckError, DatabaseInitialisationError,
                            LibraryNotFoundError, UnavailableLibraryError,
                            UnsupportedSchemaVersionError)
from storage.library_registry import LibraryRecord, LibraryRegistry

logger = logging.getLogger(__name__)
SCHEMA_VERSION = 1
MIGRATION_NAME = "data_001a_foundation"
MIGRATION_STATEMENTS = ("""
CREATE TABLE schema_migrations (
 version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, checksum TEXT NOT NULL,
 applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
)
""", """CREATE TABLE libraries (
 library_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, root_path TEXT NOT NULL,
 normalised_root_key TEXT NOT NULL, created_at TEXT NOT NULL, last_opened_at TEXT,
 schema_version INTEGER NOT NULL, status TEXT NOT NULL
)
""")
MIGRATION_SQL = "\n".join(MIGRATION_STATEMENTS)


class MetadataStore:
    """Lifecycle and connection-per-work-unit boundary for one library database."""

    def __init__(self, paths: ApplicationDataPathService, registry: LibraryRegistry):
        self.paths, self.registry = paths, registry
        self._record: LibraryRecord | None = None

    @property
    def library_id(self) -> str | None:
        return self._record.library_id if self._record else None

    @property
    def database_path(self) -> Path | None:
        return self.paths.library_database_path(self._record.library_id) if self._record else None

    def open_library(self, library_id: str) -> None:
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
            self.health_check()
            self.registry.mark_last_opened(library_id, self.get_schema_version())
        except Exception:
            self._record = None
            raise

    def close_library(self) -> None:
        if self._record:
            logger.info("Metadata store closed: %s", self._record.library_id)
        self._record = None

    def close(self) -> None:
        self.close_library()

    def _require_path(self) -> Path:
        if not self._record or not self.database_path:
            raise LibraryNotFoundError("No library is open")
        return self.database_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._require_path(), timeout=5.0)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    @contextlib.contextmanager
    def work_unit(self) -> Iterator[sqlite3.Connection]:
        """Yield a new transaction-owned connection and always close it."""
        connection = self._connect()
        try:
            with connection:
                connection.execute("BEGIN")
                yield connection
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

    def initialise_schema(self) -> None:
        path = self._require_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            current = self.get_schema_version()
            if current > SCHEMA_VERSION:
                raise UnsupportedSchemaVersionError(
                    f"Database schema {current} is newer than supported schema {SCHEMA_VERSION}"
                )
            if current == SCHEMA_VERSION:
                return
            checksum = hashlib.sha256(MIGRATION_SQL.encode()).hexdigest()
            with self.work_unit() as connection:
                for statement in MIGRATION_STATEMENTS:
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO libraries VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (self._record.library_id, self._record.display_name, self._record.source_root,
                     self._record.normalised_source_root, self._record.created_at,
                     self._record.last_opened_at, SCHEMA_VERSION, self._record.status),
                )
                connection.execute(
                    "INSERT INTO schema_migrations(version,name,checksum) VALUES (?,?,?)",
                    (SCHEMA_VERSION, MIGRATION_NAME, checksum),
                )
            logger.info("Schema migration applied: library=%s version=%s", self.library_id, SCHEMA_VERSION)
        except UnsupportedSchemaVersionError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseInitialisationError("Could not initialise the library database") from exc

    def health_check(self) -> dict[str, object]:
        try:
            with contextlib.closing(self._connect()) as connection:
                integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
                foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
            if integrity != "ok" or foreign_keys:
                raise DatabaseHealthCheckError("The library database failed its integrity check")
            result = {"healthy": True, "integrity": integrity, "schema_version": self.get_schema_version()}
            logger.info("Database health check passed: library=%s", self.library_id)
            return result
        except DatabaseHealthCheckError:
            raise
        except sqlite3.Error as exc:
            raise DatabaseHealthCheckError("The library database health check failed") from exc

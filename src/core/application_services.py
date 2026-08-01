from __future__ import annotations

from dataclasses import dataclass

from core.application_data import ApplicationDataPathService, get_app_data_service
from storage.library_registry import LibraryRecord, LibraryRegistry
from storage.metadata_store import MetadataStore
from core.perf_stats import get_session_stats


@dataclass(frozen=True)
class PreparedLibraryContext:
    """Worker-ready library that is not active until explicitly published."""

    record: LibraryRecord
    store: MetadataStore


@dataclass
class ApplicationServices:
    paths: ApplicationDataPathService
    library_registry: LibraryRegistry
    metadata_store: MetadataStore

    def open_or_register_library(self, source_root):
        """Idempotently select a library without dropping a healthy active one."""
        prepared = self.prepare_import_library(source_root)
        self.publish_active_library(prepared)
        return prepared.record

    def prepare_import_library(self, source_root) -> PreparedLibraryContext:
        """Open a worker-ready context without changing the published active library."""
        stats = get_session_stats()
        stats.start("Library registration", thread_kind="Background thread")
        record = self.library_registry.register(source_root)
        stats.stop("Library registration", 1)
        if self.metadata_store.library_id == record.library_id:
            return PreparedLibraryContext(record, self.metadata_store)
        store = MetadataStore(self.paths, self.library_registry)
        store.open_library(record.library_id)
        return PreparedLibraryContext(record, store)

    def publish_active_library(self, prepared: PreparedLibraryContext) -> None:
        """Publish a completed import's library as the one authoritative context."""
        if prepared.store.library_id != prepared.record.library_id:
            raise ValueError("Prepared library identity does not match its MetadataStore")
        current = self.metadata_store
        if current is prepared.store:
            return
        self.metadata_store = prepared.store
        current.close_library()

    def discard_prepared_library(self, prepared: PreparedLibraryContext) -> None:
        if prepared.store is not self.metadata_store:
            prepared.store.close_library()

    def close(self) -> None:
        self.metadata_store.close()

    def diagnostics(self) -> dict[str, object]:
        return {
            "application_data_root": str(self.paths.root),
            "registered_library_count": len(self.library_registry.list_libraries()),
            "active_library_id": self.metadata_store.library_id,
            "database_path": str(self.metadata_store.database_path) if self.metadata_store.database_path else None,
            "schema_version": self.metadata_store.get_schema_version() if self.metadata_store.library_id else None,
            "database_health": self.metadata_store.health_check()["healthy"] if self.metadata_store.library_id else None,
        }


def build_application_services(app_data_root=None) -> ApplicationServices:
    paths = get_app_data_service(app_data_root, migrate_legacy=False)
    registry = LibraryRegistry(paths)
    return ApplicationServices(paths, registry, MetadataStore(paths, registry))

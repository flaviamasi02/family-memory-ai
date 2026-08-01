from __future__ import annotations

from dataclasses import dataclass

from core.application_data import ApplicationDataPathService, get_app_data_service
from storage.library_registry import LibraryRegistry
from storage.metadata_store import MetadataStore


@dataclass
class ApplicationServices:
    paths: ApplicationDataPathService
    library_registry: LibraryRegistry
    metadata_store: MetadataStore

    def open_or_register_library(self, source_root):
        """Idempotently select the managed library for an imported root."""
        record = self.library_registry.register(source_root)
        if self.metadata_store.library_id != record.library_id:
            self.metadata_store.close_library()
            self.metadata_store.open_library(record.library_id)
        return record

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

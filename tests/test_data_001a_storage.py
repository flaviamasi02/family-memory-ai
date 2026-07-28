from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import pytest
import storage.metadata_store as metadata_store_module

from core.application_data import ApplicationDataError, ApplicationDataPathService
from core.application_services import build_application_services
from storage.errors import (DuplicateLibraryError, LibraryNotFoundError,
                            RegistryCorruptionError, UnavailableLibraryError,
                            UnsupportedSchemaVersionError)
from storage.library_registry import LibraryRegistry, normalise_source_root
from storage.metadata_store import MetadataStore, SCHEMA_VERSION


@pytest.fixture
def setup(tmp_path):
    source = tmp_path / "photos"
    source.mkdir()
    paths = ApplicationDataPathService(tmp_path / "app-data")
    registry = LibraryRegistry(paths)
    return source, paths, registry


def test_application_paths_and_idempotent_initialisation(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    from core.application_data import default_app_data_root
    assert default_app_data_root(platform_name="nt") == tmp_path / "Local" / "FamilyMemoryAI"
    paths = ApplicationDataPathService(tmp_path / "override")
    paths.initialise(); paths.initialise()
    assert paths.libraries_dir.is_dir()
    assert paths.thumbnails_dir.is_dir()
    assert paths.models_dir.is_dir()
    assert paths.logs_dir.is_dir()


def test_application_path_creation_failure(tmp_path):
    root = tmp_path / "file"
    root.write_text("not a directory")
    with pytest.raises(ApplicationDataError):
        ApplicationDataPathService(root).initialise()


def test_registration_lookup_persistence_and_source_untouched(setup):
    source, paths, registry = setup
    before = list(source.iterdir())
    record = registry.create(source, "Family")
    assert registry.register(source).library_id == record.library_id
    assert registry.find_by_id(record.library_id) == record
    assert registry.find_by_source_root(source / ".") == record
    assert len(LibraryRegistry(paths).list_libraries()) == 1
    assert list(source.iterdir()) == before
    assert paths.library_database_path(record.library_id).parent.is_dir()


def test_duplicate_update_relocation_status_and_non_destructive_remove(setup, tmp_path):
    source, paths, registry = setup
    record = registry.create(source)
    with pytest.raises(DuplicateLibraryError):
        registry.create(source / ".")
    db = paths.library_database_path(record.library_id)
    db.write_text("keep")
    renamed = registry.update_display_name(record.library_id, "Renamed")
    assert renamed.display_name == "Renamed" and Path(paths.root / renamed.database_path) == db
    relocated = tmp_path / "relocated"; relocated.mkdir()
    moved = registry.update_source_root(record.library_id, relocated)
    assert moved.library_id == record.library_id and Path(paths.root / moved.database_path) == db
    opened = registry.mark_last_opened(record.library_id, 1)
    assert opened.last_opened_at and opened.status == "active"
    assert registry.mark_unavailable(record.library_id).status == "root_missing"
    registry.remove(record.library_id)
    assert relocated.exists() and db.read_text() == "keep"


def test_windows_normalisation_variants():
    expected = normalise_source_root(r"C:\Users\Family\Photos", windows=True)
    assert normalise_source_root("c:/users/family/photos/", windows=True) == expected
    assert normalise_source_root(r"C:\Users\Family\.\Photos\\", windows=True) == expected


def test_invalid_library_id_cannot_escape(setup):
    _, paths, _ = setup
    with pytest.raises(ApplicationDataError):
        paths.library_database_path("../../escape")


def test_registry_corruption_is_not_replaced(tmp_path):
    paths = ApplicationDataPathService(tmp_path / "app")
    paths.initialise()
    paths.registry_path.write_text("not-json")
    with pytest.raises(RegistryCorruptionError):
        LibraryRegistry(paths)
    assert paths.registry_path.read_text() == "not-json"


def test_metadata_store_schema_pragmas_health_and_lifecycle(setup):
    source, paths, registry = setup
    record = registry.create(source)
    store = MetadataStore(paths, registry)
    store.open_library(record.library_id)
    assert store.library_id == record.library_id
    assert store.database_path == paths.library_database_path(record.library_id)
    assert store.get_schema_version() == SCHEMA_VERSION
    assert store.health_check()["healthy"] is True
    with store.work_unit() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        row = connection.execute("SELECT version,name,checksum FROM schema_migrations").fetchone()
        assert row[0] == 1 and row[1] and len(row[2]) == 64
        library = connection.execute("SELECT library_id FROM libraries").fetchone()
        assert library[0] == record.library_id
    store.open_library(record.library_id)
    store.close_library(); store.close_library()
    store.open_library(record.library_id); store.close()


def test_work_units_use_distinct_thread_owned_connections(setup):
    source, paths, registry = setup
    record = registry.create(source)
    store = MetadataStore(paths, registry); store.open_library(record.library_id)
    ids = []
    def use_connection():
        with store.work_unit() as connection:
            ids.append(id(connection)); connection.execute("SELECT 1").fetchone()
    threads = [threading.Thread(target=use_connection) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert len(ids) == 2


def test_unsupported_newer_schema_is_rejected(setup):
    source, paths, registry = setup
    record = registry.create(source)
    store = MetadataStore(paths, registry); store.open_library(record.library_id); store.close()
    with sqlite3.connect(paths.library_database_path(record.library_id)) as connection:
        connection.execute("INSERT INTO schema_migrations(version,name,checksum) VALUES (99,'future','x')")
    with pytest.raises(UnsupportedSchemaVersionError):
        store.open_library(record.library_id)


def test_failed_migration_rolls_back_atomically(setup, monkeypatch):
    source, paths, registry = setup
    record = registry.create(source)
    original = metadata_store_module.MIGRATION_STATEMENTS
    monkeypatch.setattr(metadata_store_module, "MIGRATION_STATEMENTS",
                        original + ("CREATE TABLE broken (",))
    store = MetadataStore(paths, registry)
    with pytest.raises(metadata_store_module.DatabaseInitialisationError):
        store.open_library(record.library_id)
    with sqlite3.connect(paths.library_database_path(record.library_id)) as connection:
        names = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "schema_migrations" not in names and "libraries" not in names


def test_invalid_and_unavailable_library(setup):
    source, paths, registry = setup
    store = MetadataStore(paths, registry)
    with pytest.raises(LibraryNotFoundError): store.open_library("missing")
    record = registry.create(source); source.rmdir()
    with pytest.raises(UnavailableLibraryError): store.open_library(record.library_id)
    assert registry.find_by_id(record.library_id).status == "root_missing"


def test_composition_and_diagnostics_use_override(tmp_path):
    services = build_application_services(tmp_path / "app")
    diagnostic = services.diagnostics()
    assert diagnostic["application_data_root"] == str(tmp_path / "app")
    assert diagnostic["registered_library_count"] == 0
    services.close()

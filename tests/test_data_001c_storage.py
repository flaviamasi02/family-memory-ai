from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.application_data import ApplicationDataPathService
from core.application_services import ApplicationServices
from storage.import_registration import ImportRegistrationService
from storage.library_registry import LibraryRegistry
from storage.metadata_store import MetadataStore
from storage.photo_repository import PhotoRepository


@pytest.fixture
def library(tmp_path):
    root = tmp_path / "photos"
    root.mkdir()
    paths = ApplicationDataPathService(tmp_path / "app")
    registry = LibraryRegistry(paths)
    record = registry.register(root)
    store = MetadataStore(paths, registry)
    store.open_library(record.library_id)
    yield root, paths, registry, record, store
    store.close()


def make_photo(root: Path, name: str, content: bytes = b"image"):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != content:
        path.write_bytes(content)
    stat = path.stat()
    return SimpleNamespace(path=path, filename=path.name, extension=path.suffix.lower(),
                           file_size=stat.st_size, modified_time_ns=stat.st_mtime_ns,
                           metadata={}, id=None)


def test_photo_repository_crud_path_hash_and_listing(library):
    root, _, _, record, store = library
    repository = PhotoRepository(store)
    with store.work_unit() as connection:
        photo = repository.create_photo(width=100, height=50, content_hash="full-hash",
                                        hash_algorithm="sha256", hash_version=1,
                                        connection=connection)
        location = repository.create_location(
            photo.photo_id, source_path=str(root / "A.jpg"), relative_path="A.jpg",
            filename="A.jpg", file_size=5, modified_time_ns=10, import_run_id=None,
            partial_fingerprint="partial-hash", fingerprint_algorithm="sha256-first-1mib-size",
            fingerprint_version=1, connection=connection,
        )
    assert photo.library_id == record.library_id
    assert repository.get_by_id(photo.photo_id) == photo
    assert repository.get_by_relative_path("A.jpg").photo_id == photo.photo_id
    assert repository.get_by_fingerprint("partial-hash", file_size=5)[0].photo_id == photo.photo_id
    assert repository.get_by_fingerprint("full-hash")[0].photo_id == photo.photo_id
    assert repository.list_library_photos() == [photo]
    updated = repository.update_photo(photo.photo_id, width=200, status="missing")
    assert updated.width == 200 and updated.status == "missing" and updated.metadata_revision == 2
    assert location.photo_id == photo.photo_id


def test_repeated_import_stable_ids_locations_runs_and_restart(library):
    root, paths, registry, record, store = library
    first_photos = [make_photo(root, "one.jpg"), make_photo(root, "nested/two.png")]
    first = ImportRegistrationService(store, root).register(first_photos, skipped=3)
    ids = [photo.id for photo in first_photos]
    second_photos = [make_photo(root, str(photo.path.relative_to(root)), photo.path.read_bytes())
                     for photo in first_photos]
    second = ImportRegistrationService(store, root).register(second_photos)

    assert first.discovered == 5 and first.created == 2 and first.reused == 0 and first.skipped == 3
    assert second.created == 0 and second.reused == 2
    assert [photo.id for photo in second_photos] == ids
    with store.read_connection() as connection:
        runs = connection.execute(
            "SELECT status,discovered_count,created_count,reused_count,skipped_count,"
            "completed_at,elapsed_time_ms FROM import_runs ORDER BY started_at"
        ).fetchall()
        assert connection.execute("SELECT count(*) FROM photos").fetchone()[0] == 2
        assert connection.execute("SELECT count(*) FROM photo_locations").fetchone()[0] == 2
    assert runs[0][:5] == ("completed", 5, 2, 0, 3)
    assert runs[1][:5] == ("completed", 2, 0, 2, 0)
    assert all(row[5] and row[6] >= 0 for row in runs)

    store.close()
    restarted = MetadataStore(paths, LibraryRegistry(paths))
    restarted.open_library(record.library_id)
    assert {p.photo_id for p in PhotoRepository(restarted).list_library_photos()} == set(ids)
    restarted.close()


def test_changed_file_reuses_logical_photo_and_updates_location(library):
    root, _, _, _, store = library
    original = make_photo(root, "one.jpg", b"old")
    ImportRegistrationService(store, root).register([original])
    original_id = original.id
    changed = make_photo(root, "one.jpg", b"larger replacement")
    result = ImportRegistrationService(store, root).register([changed])
    assert changed.id == original_id and result.created == 0
    with store.read_connection() as connection:
        assert connection.execute("SELECT changed_count FROM import_runs WHERE import_run_id=?",
                                  (result.import_run_id,)).fetchone()[0] == 1
        assert connection.execute("SELECT file_size FROM photo_locations").fetchone()[0] == len(b"larger replacement")


def test_bulk_registration_rolls_back_and_marks_run_failed(library, monkeypatch):
    root, _, _, _, store = library
    photos = [make_photo(root, "one.jpg"), make_photo(root, "two.jpg")]
    registration = ImportRegistrationService(store, root)
    original = registration.repository.create_location
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(registration.repository, "create_location", fail_second)
    with pytest.raises(RuntimeError, match="injected failure"):
        registration.register(photos)
    with store.read_connection() as connection:
        assert connection.execute("SELECT count(*) FROM photos").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM photo_locations").fetchone()[0] == 0
        assert connection.execute("SELECT status,failed_count FROM import_runs").fetchone() == ("failed", 1)


def test_bulk_import_uses_constant_transactions(library, monkeypatch):
    root, _, _, _, store = library
    photos = [make_photo(root, f"{number}.jpg") for number in range(25)]
    original = store.work_unit
    calls = 0

    @contextmanager
    def counted():
        nonlocal calls
        calls += 1
        with original() as connection:
            yield connection

    monkeypatch.setattr(store, "work_unit", counted)
    ImportRegistrationService(store, root).register(photos)
    assert calls == 2  # one durable run start plus one transactional batch


def test_automatic_registration_reuses_library_and_worker_has_one_scan(tmp_path):
    root = tmp_path / "photos"
    root.mkdir()
    paths = ApplicationDataPathService(tmp_path / "app")
    registry = LibraryRegistry(paths)
    store = MetadataStore(paths, registry)
    services = ApplicationServices(paths, registry, store)
    first = services.open_or_register_library(root)
    second = services.open_or_register_library(root / ".")
    assert first.library_id == second.library_id and len(registry.list_libraries()) == 1
    source = (Path(__file__).parents[1] / "src/workers/scan_worker.py").read_text()
    assert source.count("find_photos(self._folder_path, registration)") == 1
    assert "open_or_register_library(self._folder_path)" in source

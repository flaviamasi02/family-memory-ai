from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.application_data import ApplicationDataPathService
from core.perf_stats import begin_import_performance_session
from storage.import_registration import FileObservation, ImportRegistrationService
from storage.library_registry import LibraryRegistry
from storage.metadata_store import MetadataStore
from storage.photo_repository import normalise_relative_path


@pytest.fixture
def opened_store(tmp_path):
    root = tmp_path / "photos"
    root.mkdir()
    (root / "one.jpg").write_bytes(b"image")
    paths = ApplicationDataPathService(tmp_path / "app")
    registry = LibraryRegistry(paths)
    record = registry.register(root)
    store = MetadataStore(paths, registry)
    store.open_library(record.library_id)
    yield root, store
    store.close()


def _photo(path):
    stat = path.stat()
    return SimpleNamespace(
        path=path, filename=path.name, extension=path.suffix,
        file_size=stat.st_size, modified_time_ns=stat.st_mtime_ns, metadata={}, id=None,
        automatic_media_category="photo", effective_media_category="photo",
        relevance_category="relevant", is_album_relevant_candidate=True,
        classification_confidence=1.0, classification_reason="test",
    )


def _observation(root, photo):
    relative = str(photo.path.relative_to(root))
    return FileObservation(
        photo.path.resolve(), relative, normalise_relative_path(relative), photo.filename,
        photo.file_size, photo.modified_time_ns,
    )


def test_planner_uses_one_joined_sqlite_read(opened_store):
    root, store = opened_store
    item = _photo(root / "one.jpg")
    service = ImportRegistrationService(store, root)
    service.register([item], plan=service.plan_changes([_observation(root, item)]))

    statements = []
    with store.read_connection() as connection:
        connection.set_trace_callback(statements.append)
        rows = service.repository.list_sync_state(connection=connection)

    selects = [statement for statement in statements if statement.lstrip().upper().startswith("SELECT")]
    assert len(rows) == 1
    assert len(selects) == 1
    assert "JOIN photos" in selects[0]


def test_added_registration_avoids_readback_queries(opened_store):
    root, store = opened_store
    item = _photo(root / "one.jpg")
    service = ImportRegistrationService(store, root)
    plan = service.plan_changes([_observation(root, item)])
    statements = []
    begin_import_performance_session(root)
    # Trace the actual work unit by temporarily instrumenting the store factory.
    original = store._connect

    def traced_connect(*args, **kwargs):
        connection = original(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    store._connect = traced_connect
    try:
        result = service.register([item], plan=plan)
    finally:
        store._connect = original

    assert result.added == 1
    assert not [statement for statement in statements if statement.lstrip().upper().startswith("SELECT")]

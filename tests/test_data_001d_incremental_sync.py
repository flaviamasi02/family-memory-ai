from __future__ import annotations

import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

import storage.import_registration as registration_module
from cache.thumbnail_cache import (
    get_thumbnail_cache_path_for_identity, preserve_thumbnail_for_relocation,
)
from core.application_data import ApplicationDataPathService
from storage.import_registration import FileObservation, ImportRegistrationService
from storage.library_registry import LibraryRegistry
from storage.metadata_store import MetadataStore
from storage.photo_repository import PhotoRepository, normalise_relative_path
from vision.embedding_provider import EmbeddingRecord, EmbeddingStore, FakeEmbeddingProvider, now_iso


@pytest.fixture
def opened(tmp_path):
    root = tmp_path / "photos"; root.mkdir()
    paths = ApplicationDataPathService(tmp_path / "app")
    registry = LibraryRegistry(paths); record = registry.register(root)
    store = MetadataStore(paths, registry); store.open_library(record.library_id)
    yield root, store, record
    store.close()


def photo(root: Path, relative: str, content: bytes = b"image"):
    path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != content:
        path.write_bytes(content)
    stat = path.stat()
    return SimpleNamespace(path=path, filename=path.name, extension=path.suffix,
        file_size=stat.st_size, modified_time_ns=stat.st_mtime_ns, metadata={}, id=None,
        sync_state="added", previous_path=None)


def observation(root: Path, item) -> FileObservation:
    relative = str(item.path.relative_to(root))
    return FileObservation(item.path.resolve(), relative, normalise_relative_path(relative),
                           item.filename, item.file_size, item.modified_time_ns)


def synchronize(store, root, photos):
    service = ImportRegistrationService(store, root)
    plan = service.plan_changes([observation(root, item) for item in photos])
    for item in photos:
        planned = plan.item_for(item.path)
        item.sync_state = planned.state; item.id = planned.photo_id
        item.previous_path = Path(planned.previous_location.source_path) \
            if planned.previous_location and planned.state in {"moved", "renamed"} else None
    return service.register(photos, plan=plan), plan


def test_unchanged_sync_reuses_identity_without_hash_or_location_update(opened, monkeypatch):
    root, store, _ = opened
    first_photo = photo(root, "one.jpg")
    first, _ = synchronize(store, root, [first_photo])
    repository = PhotoRepository(store)
    before = repository.get_location("one.jpg")
    calls = 0

    def unexpected_hash(*_args):
        nonlocal calls
        calls += 1
        raise AssertionError("unchanged import must reuse the stored fingerprint")

    monkeypatch.setattr(registration_module, "partial_fingerprint", unexpected_hash)
    repeated_photo = photo(root, "one.jpg")
    repeated, _ = synchronize(store, root, [repeated_photo])
    after = repository.get_location("one.jpg")
    assert first.added == 1
    assert repeated.unchanged == 1 and repeated.added == repeated.updated == 0
    assert repeated_photo.id == first_photo.id and calls == 0
    assert after == before


def test_unchanged_plan_rehydrates_durable_capture_date_for_review(opened):
    root, store, _ = opened
    original = photo(root, "dated.jpg")
    original.metadata = {"date_taken": "2024-05-06T12:00:00"}
    synchronize(store, root, [original])
    repeated = photo(root, "dated.jpg")
    service = ImportRegistrationService(store, root)
    plan = service.plan_changes([observation(root, repeated)])
    assert plan.item_for(repeated.path).state == "unchanged"
    assert plan.item_for(repeated.path).captured_at == "2024-05-06T12:00:00"


def test_repeated_import_rehydrates_cleanup_classification(opened):
    root, store, _ = opened
    original = photo(root, "document.jpg")
    original.automatic_media_category = "document"
    original.effective_media_category = "document"
    original.relevance_category = "document_or_scan"
    original.is_album_relevant_candidate = False
    original.classification_confidence = 0.91
    original.classification_reason = "document evidence"
    synchronize(store, root, [original])

    repeated = photo(root, "document.jpg")
    service = ImportRegistrationService(store, root)
    planned = service.plan_changes([observation(root, repeated)]).item_for(repeated.path)

    assert planned.state == "unchanged"
    assert planned.classification == (
        "document", "document", "document_or_scan", 0, 0.91, "document evidence")


def test_pre_snapshot_rows_are_marked_for_one_time_classification(opened):
    root, store, _ = opened
    legacy = photo(root, "legacy.jpg")
    synchronize(store, root, [legacy])
    with store.work_unit() as connection:
        connection.execute(
            "UPDATE photos SET automatic_media_category=NULL,effective_media_category=NULL,"
            "relevance_category=NULL,is_album_relevant_candidate=NULL,"
            "classification_confidence=NULL,classification_reason=NULL")

    repeated = photo(root, "legacy.jpg")
    service = ImportRegistrationService(store, root)
    planned = service.plan_changes([observation(root, repeated)]).item_for(repeated.path)
    assert planned.state == "unchanged"
    assert planned.classification is None


def test_added_updated_removed_statistics_and_restart_persistence(opened):
    root, store, record = opened
    original = photo(root, "original.jpg", b"old")
    synchronize(store, root, [original])
    original.path.write_bytes(b"updated bytes")
    updated = photo(root, "original.jpg", b"updated bytes")
    added = photo(root, "added.jpg", b"new")
    result, _ = synchronize(store, root, [updated, added])
    assert result.added == 1 and result.updated == 1 and result.unchanged == 0
    assert updated.id == original.id and added.id != original.id

    updated.path.unlink(); added.path.unlink()
    removed, _ = synchronize(store, root, [])
    assert removed.removed == 2
    summary = store.incremental_sync_summary()
    assert summary["total_photos"] == 2 and summary["active_photos"] == 0
    assert summary["removed_photos"] == 2 and "removed=2" in summary["last_import_summary"]
    store.close(); store.open_library(record.library_id)
    assert {p.status for p in PhotoRepository(store).list_library_photos()} == {"missing"}


@pytest.mark.parametrize("old_name,new_name,expected", [
    ("old.jpg", "new.jpg", "renamed"),
    ("folder/photo.jpg", "elsewhere/photo.jpg", "moved"),
])
def test_relocation_preserves_photo_embedding_and_user_decision(opened, old_name, new_name, expected):
    root, store, _ = opened
    original = photo(root, old_name, b"same logical bytes")
    synchronize(store, root, [original])
    with store.work_unit() as connection:
        connection.execute(
            "INSERT INTO embeddings(embedding_id,photo_id,provider,model_name,model_key,dimension,vector) "
            "VALUES ('embedding',?,'test','test','test',1,?)",
            (original.id, struct.pack("<f", 1.0)))
        connection.execute(
            "INSERT INTO reviews(review_id,photo_id,review_type,decision,source,created_at) "
            "VALUES ('review',?,'memory','keep','user','now')", (original.id,))

    new_path = root / new_name; new_path.parent.mkdir(parents=True, exist_ok=True)
    original.path.rename(new_path)
    relocated = photo(root, new_name, b"same logical bytes")
    result, plan = synchronize(store, root, [relocated])
    assert getattr(result, expected) == 1 and relocated.id == original.id
    assert plan.item_for(new_path).previous_location.root_relative_path == old_name
    with store.read_connection() as connection:
        assert connection.execute("SELECT photo_id FROM embeddings").fetchone()[0] == original.id
        assert connection.execute("SELECT photo_id,decision FROM reviews").fetchone() == (original.id, "keep")
        locations = connection.execute(
            "SELECT root_relative_path,availability FROM photo_locations ORDER BY created_at").fetchall()
    assert (old_name, "missing") in locations and (new_name, "available") in locations


def test_thumbnail_and_legacy_embedding_cache_are_rekeyed_without_regeneration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    old = tmp_path / "old.jpg"; old.write_bytes(b"same")
    stat = old.stat()
    old_cache = get_thumbnail_cache_path_for_identity(str(old), stat.st_mtime_ns, stat.st_size)
    old_cache.parent.mkdir(parents=True, exist_ok=True); old_cache.write_bytes(b"cached thumbnail")

    embedding_store = EmbeddingStore(tmp_path / "embeddings.db")
    provider = FakeEmbeddingProvider(dimension=2)
    key, mtime, size, fingerprint = str(old.resolve()), stat.st_mtime_ns, stat.st_size, "legacy"
    embedding_store.put(EmbeddingRecord(key, fingerprint, mtime, size,
        provider.metadata.provider_id, provider.metadata.checkpoint_id,
        provider.metadata.revision, 2, [1.0, 0.0], now_iso()))
    new = tmp_path / "new.jpg"; old.rename(new)
    assert preserve_thumbnail_for_relocation(str(old), stat.st_mtime_ns, stat.st_size, str(new))
    assert embedding_store.preserve_for_relocation(old, new) == 1
    assert embedding_store.get_valid(new, provider.metadata) is not None
    assert embedding_store.count() == 1


def test_no_duplicate_rows_and_import_statistics_are_durable(opened):
    root, store, _ = opened
    items = [photo(root, f"{index}.jpg", str(index).encode()) for index in range(20)]
    synchronize(store, root, items)
    result, _ = synchronize(store, root, [photo(root, item.filename, item.path.read_bytes()) for item in items])
    assert result.unchanged == 20 and result.elapsed_time_ms >= 0
    with store.read_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM photos").fetchone()[0] == 20
        assert connection.execute("SELECT COUNT(*) FROM photo_locations").fetchone()[0] == 20
        row = connection.execute(
            "SELECT unchanged_count,added_count,removed_count,moved_count,renamed_count,updated_count "
            "FROM import_runs WHERE import_run_id=?", (result.import_run_id,)).fetchone()
    assert row == (20, 0, 0, 0, 0, 0)
    assert result.counts_consistent
    assert result.observed_count == 20


def test_pipeline_keeps_one_walk_and_submits_only_changed_photos_to_embeddings():
    scanner = Path("src/core/photo_scanner.py").read_text(encoding="utf-8")
    worker = Path("src/workers/scan_worker.py").read_text(encoding="utf-8")
    window = Path("src/ui/main_window.py").read_text(encoding="utf-8")
    thumbnails = Path("src/workers/thumbnail_worker.py").read_text(encoding="utf-8")
    assert scanner.count('folder.rglob("*")') == 1
    assert worker.count("find_photos(self._folder_path, registration)") == 1
    assert 'in {"added", "updated"}' in window
    assert 'sync_state", "added") not in {"added", "updated"}' in thumbnails

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from core.supported_media import (
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_MEDIA_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
    is_supported_media_path,
    supported_image_items,
    supported_media_items,
)


@pytest.mark.parametrize("name", [
    "photo.jpg", "photo.JPEG", "photo.PNG", "photo.webp", "photo.HEIC",
    "photo.heif", "clip.mp4", "clip.MOV", "clip.avi", "clip.MKV",
    "family.trip.v2.final.JPG", ".hidden-photo.png",
])
def test_supported_media_extensions_are_case_insensitive(name):
    assert is_supported_media_path(name)


@pytest.mark.parametrize("name", [
    "family_memory.db", "family_memory.db-wal", "family_memory.db-shm",
    "photo.familymemory.json", "photo.family.extra.json", "ordinary.json",
    "README.md", "requirements.txt", "pytest.ini", ".gitignore",
    ".hidden", "extensionless", "archive.tar.gz",
])
def test_project_database_sidecar_and_non_media_files_are_excluded(name):
    assert not is_supported_media_path(name)


def test_authoritative_sets_cover_current_images_and_videos():
    assert {".jpg", ".jpeg", ".png", ".heic", ".heif"} <= SUPPORTED_IMAGE_EXTENSIONS
    assert {".mp4", ".mov", ".avi", ".mkv"} <= SUPPORTED_VIDEO_EXTENSIONS
    assert SUPPORTED_MEDIA_EXTENSIONS == SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS


def test_downstream_and_thumbnail_filters_reject_unsupported_before_work():
    items = [SimpleNamespace(path=Path(name)) for name in (
        "one.jpg", "two.mp4", "family_memory.db", "README.md", "x.json"
    )]
    assert [item.path.name for item in supported_media_items(items)] == ["one.jpg", "two.mp4"]
    assert [item.path.name for item in supported_image_items(items)] == ["one.jpg"]


def test_directories_are_not_import_candidates(tmp_path):
    directory = tmp_path / "looks-like.jpg"
    directory.mkdir()
    # Extension support alone does not turn a directory into a scanner file.
    assert directory.is_dir()


def test_mixed_folder_scan_filters_before_photo_and_metadata_work(tmp_path, monkeypatch):
    pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    import core.photo_scanner as scanner
    from core.perf_stats import get_session_stats, reset_session_stats

    supported = ["a.jpg", "b.JPEG", "c.png", "d.heic", "e.mp4"]
    unsupported = [
        "family_memory.db", "family_memory.db-wal", "family_memory.db-shm",
        "a.familymemory.json", "ordinary.json", "README.md", "requirements.txt",
        "pytest.ini", ".gitignore", "extensionless",
    ]
    for name in supported + unsupported:
        (tmp_path / name).write_bytes(b"not decoded in this test")
    (tmp_path / "directory.jpg").mkdir()

    constructed: list[Path] = []
    metadata_paths: list[Path] = []

    class FakePhoto:
        def __init__(self, path):
            self.path = Path(path); self.metadata = {}; self.extension = self.path.suffix.lower()
        @classmethod
        def from_path(cls, path):
            constructed.append(Path(path)); return cls(path)
        def sync_intelligence_from_metadata(self): pass

    monkeypatch.setattr(scanner, "Photo", FakePhoto)
    monkeypatch.setattr(scanner, "extract_basic_metadata", lambda path: metadata_paths.append(Path(path)) or {})
    monkeypatch.setattr(scanner._media_classifier, "classify_photos", lambda photos: None)
    monkeypatch.setattr(scanner._user_metadata_service, "apply_for_photo", lambda photo: None)
    reset_session_stats()
    photos = scanner.find_photos(tmp_path)

    assert {photo.path.name for photo in photos} == set(supported)
    assert set(constructed) == set(metadata_paths)
    assert {path.name for path in constructed} == set(supported)
    stats = get_session_stats()
    assert stats.get_counter("filesystem_entries_discovered") == len(supported) + len(unsupported) + 1
    assert stats.get_counter("files_discovered") == len(supported) + len(unsupported)
    assert stats.get_counter("supported_media_candidates") == len(supported)
    assert stats.get_counter("unsupported_files_skipped") == len(unsupported)
    assert stats.get_counter("files_scanned") == len(supported)


def test_thumbnail_worker_constructs_jobs_for_images_only():
    pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    from workers.thumbnail_worker import ThumbnailWorker
    photos = [SimpleNamespace(path=Path(name)) for name in ("a.jpg", "b.mp4", "README.md", "family_memory.db")]
    worker = ThumbnailWorker(photos)
    assert [photo.path.name for photo in worker.photos] == ["a.jpg"]


def test_normal_import_code_has_no_metadata_store_operations():
    source = Path("src/ui/main_window.py").read_text(encoding="utf-8")
    import_pipeline = source[source.index("def _begin_import_scan"):source.index("def _on_scan_error")]
    for forbidden in ("metadata_store", "health_check", "schema_summary", ".backup(", "register("):
        assert forbidden not in import_pipeline
    assert import_pipeline.count("ScanWorker(") == 1

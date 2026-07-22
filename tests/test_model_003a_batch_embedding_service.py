from __future__ import annotations

import math
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from vision.batch_embedding_service import BatchEmbeddingService, embedding_failure_diagnostic_lines
from vision.embedding_provider import EmbeddingRecord, EmbeddingStore, FakeEmbeddingProvider, ModelMetadata, now_iso, source_identity
from vision.evaluation_sources import folder_image_paths


JPEG_BYTES = bytes.fromhex("ffd8ffe000104a46494600010101006000600000ffdb0043000302020302020303030304030304050805050404050a070706080c0a0c0c0b0a0b0b0d0e12100d0e110e0b0b1016101113141515150c0f171816141812141514ffdb00430103040405040509050509140d0b0d141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414ffc00011080001000103012200021101031101ffc4001400010000000000000000000000000000000000000008ffc40014100100000000000000000000000000000000000000ffda000c03010002110311003f00b2c001ffd9")
PNG_BYTES = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c4944415408d763f8ffff3f0005fe02fea73581e80000000049454e44ae426082")

def image(path: Path, color=(10, 20, 30)) -> Path:
    payload = JPEG_BYTES if path.suffix.lower() in {".jpg", ".jpeg"} else PNG_BYTES
    path.write_bytes(payload + bytes(color))
    return path


class BadProvider(FakeEmbeddingProvider):
    def __init__(self, values):
        super().__init__(dimension=512)
        self.values = values

    def embed_images(self, paths, cancel_event=None):
        self.load(cancel_event)
        key, mt, sz, fp = source_identity(Path(paths[0]))
        return [EmbeddingRecord(key, fp, mt, sz, self.metadata.provider_id, self.metadata.checkpoint_id, self.metadata.revision, len(self.values), list(self.values), now_iso())]


def test_new_image_gets_valid_persistent_512_embedding_and_reload_lookup(tmp_path):
    p = image(tmp_path / "a.jpg")
    db = tmp_path / "emb.sqlite3"
    provider = FakeEmbeddingProvider()
    result = BatchEmbeddingService(provider, EmbeddingStore(db)).embed_images([p])
    assert result.processed_successfully == 1
    assert result.outcomes[0].embedding_dimension == 512
    cached = EmbeddingStore(db).get_valid(p, provider.metadata)
    assert cached is not None
    assert len(cached.embedding) == 512
    assert all(math.isfinite(v) for v in cached.embedding)


def test_unchanged_cached_image_is_skipped_and_provider_not_recalled(tmp_path):
    p = image(tmp_path / "a.png")
    db = tmp_path / "emb.sqlite3"
    provider = FakeEmbeddingProvider()
    service = BatchEmbeddingService(provider, EmbeddingStore(db))
    assert service.embed_images([p]).processed_successfully == 1
    calls = provider.embed_call_count
    result = service.embed_images([p])
    assert result.skipped_cached == 1
    assert provider.embed_call_count == calls


def test_changed_source_file_and_changed_model_key_regenerate(tmp_path):
    p = image(tmp_path / "a.jpg", (1, 2, 3))
    db = tmp_path / "emb.sqlite3"
    provider = FakeEmbeddingProvider()
    service = BatchEmbeddingService(provider, EmbeddingStore(db))
    service.embed_images([p])
    first_calls = provider.embed_call_count
    time.sleep(0.01)
    image(p, (9, 8, 7))
    assert service.embed_images([p]).processed_successfully == 1
    assert provider.embed_call_count == first_calls + 1
    provider.metadata = ModelMetadata(**{**provider.metadata.__dict__, "revision": "v2"})
    assert service.embed_images([p]).processed_successfully == 1
    assert provider.embed_call_count == first_calls + 2


@pytest.mark.parametrize("values", [[0.1] * 511, [float("nan")] * 512, [float("inf")] * 512])
def test_invalid_embedding_dimension_or_non_finite_rejected(tmp_path, values):
    p = image(tmp_path / "bad.jpg")
    result = BatchEmbeddingService(BadProvider(values), EmbeddingStore(tmp_path / "e.sqlite3")).embed_images([p])
    assert result.failed == 1
    assert "Expected" in result.outcomes[0].error or "NaN" in result.outcomes[0].error


def test_embedding_failure_diagnostics_include_path_type_and_message(tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_text("not a supported image")

    result = BatchEmbeddingService(FakeEmbeddingProvider(), EmbeddingStore(tmp_path / "e.sqlite3")).embed_images([bad])
    lines = embedding_failure_diagnostic_lines(result)

    assert result.failed == 1
    assert str(bad) in lines[0]
    assert "ValueError" in lines[0]
    assert "Unsupported image extension" in lines[0]


def test_repeated_embedding_failure_diagnostics_are_grouped_and_limited(tmp_path):
    paths = []
    for index in range(4):
        path = tmp_path / f"bad{index}.txt"
        path.write_text("not a supported image")
        paths.append(path)

    result = BatchEmbeddingService(FakeEmbeddingProvider(), EmbeddingStore(tmp_path / "e.sqlite3")).embed_images(paths)
    lines = embedding_failure_diagnostic_lines(result, limit=3)

    assert len(lines) == 1
    assert "x4" in lines[0]
    assert "Unsupported image extension" in lines[0]


def test_successful_embedding_run_has_no_failure_diagnostics(tmp_path):
    p = image(tmp_path / "ok.jpg")
    result = BatchEmbeddingService(FakeEmbeddingProvider(), EmbeddingStore(tmp_path / "e.sqlite3")).embed_images([p])

    assert result.failed == 0
    assert embedding_failure_diagnostic_lines(result) == []


def test_corrupt_image_does_not_stop_batch_and_progress_counts(tmp_path):
    good1 = image(tmp_path / "good1.jpg")
    bad = tmp_path / "bad.jpg"; bad.write_text("not an image")
    good2 = image(tmp_path / "good2.png")
    progress = []
    result = BatchEmbeddingService(FakeEmbeddingProvider(), EmbeddingStore(tmp_path / "e.sqlite3")).embed_images([good1, bad, good2], progress.append)
    assert result.processed_successfully == 2
    assert result.failed == 1
    assert len(progress) == 3
    assert progress[-1].processed_count == 2
    assert progress[-1].failed_count == 1


def test_cancellation_stops_between_images_and_loads_once(tmp_path):
    paths = [image(tmp_path / f"{i}.jpg", (i, i, i)) for i in range(3)]
    event = threading.Event()
    seen = []
    def progress(p):
        seen.append(p)
        event.set()
    provider = FakeEmbeddingProvider()
    result = BatchEmbeddingService(provider, EmbeddingStore(tmp_path / "e.sqlite3")).embed_images(paths, progress, event)
    assert result.processed_successfully == 1
    assert result.cancelled == 2
    assert provider.load_count == 1


def test_migration_from_previous_schema_and_identity_model_index(tmp_path):
    db = tmp_path / "legacy.sqlite3"
    p = image(tmp_path / "a.jpg")
    provider = FakeEmbeddingProvider()
    rec = provider.embed_images([p])[0]
    import json
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE embeddings (photo_key TEXT, source_fingerprint TEXT, source_mtime_ns INTEGER, source_size INTEGER, provider_id TEXT, checkpoint_id TEXT, model_revision TEXT, embedding_dimension INTEGER, embedding_json TEXT, generated_at TEXT, status TEXT, error TEXT, PRIMARY KEY(photo_key, provider_id, checkpoint_id, model_revision))")
        con.execute("INSERT INTO embeddings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (rec.photo_key, rec.source_fingerprint, rec.source_mtime_ns, rec.source_size, rec.provider_id, rec.checkpoint_id, rec.model_revision, rec.embedding_dimension, json.dumps(rec.embedding), rec.generated_at, "ok", ""))
    store = EmbeddingStore(db)
    assert store.get_valid(p, provider.metadata) is not None
    with sqlite3.connect(db) as con:
        indexes = [row[1] for row in con.execute("PRAGMA index_list(embeddings)")]
    assert "idx_embeddings_identity_model" in indexes


def test_diagnostic_folder_uses_existing_supported_image_extensions(tmp_path):
    image(tmp_path / "a.jpg")
    image(tmp_path / "b.png")
    (tmp_path / "note.txt").write_text("x")
    paths = folder_image_paths(tmp_path, 20)
    assert {p.suffix for p in paths} == {".jpg", ".png"}


def test_image_verification_tries_qt_after_pillow_decode_failure(tmp_path, monkeypatch):
    from types import ModuleType
    import sys
    from vision import batch_embedding_service as service_module

    p = tmp_path / "fallback.heic"
    p.write_bytes(b"not decoded by pillow but accepted by fake qt")

    class FakePillowImage:
        @staticmethod
        def open(path):
            raise ValueError("pillow cannot decode heic")

    class FakeImageOps:
        @staticmethod
        def exif_transpose(image):
            return image

    class FakeQtImage:
        def isNull(self):
            return False

    class FakeQImageReader:
        def __init__(self, path):
            self.path = path
            self.auto_transform = False

        def setAutoTransform(self, enabled):
            self.auto_transform = enabled

        def read(self):
            assert self.auto_transform is True
            return FakeQtImage()

        def errorString(self):
            return "qt should not report an error"

    pil = ModuleType("PIL")
    pyside = sys.modules.get("PySide6") or ModuleType("PySide6")
    qtgui = ModuleType("PySide6.QtGui")
    pil.Image = FakePillowImage
    pil.ImageOps = FakeImageOps
    qtgui.QImageReader = FakeQImageReader
    pyside.QtGui = qtgui
    monkeypatch.setitem(sys.modules, "PIL", pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", FakePillowImage)
    monkeypatch.setitem(sys.modules, "PIL.ImageOps", FakeImageOps)
    monkeypatch.setitem(sys.modules, "PySide6", pyside)
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)

    service_module._verify_loadable_image(p)


def test_image_verification_reports_pillow_and_qt_errors_after_all_decoders_fail(tmp_path, monkeypatch):
    from types import ModuleType
    import sys
    from vision import batch_embedding_service as service_module

    p = tmp_path / "bad.heic"
    p.write_bytes(b"not an image")

    class FakePillowImage:
        @staticmethod
        def open(path):
            raise ValueError("pillow failure kept")

    class FakeImageOps:
        @staticmethod
        def exif_transpose(image):
            return image

    class FakeQtImage:
        def isNull(self):
            return True

    class FakeQImageReader:
        def __init__(self, path):
            pass

        def setAutoTransform(self, enabled):
            pass

        def read(self):
            return FakeQtImage()

        def errorString(self):
            return "qt failure kept"

    pil = ModuleType("PIL")
    pyside = sys.modules.get("PySide6") or ModuleType("PySide6")
    qtgui = ModuleType("PySide6.QtGui")
    pil.Image = FakePillowImage
    pil.ImageOps = FakeImageOps
    qtgui.QImageReader = FakeQImageReader
    pyside.QtGui = qtgui
    monkeypatch.setitem(sys.modules, "PIL", pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", FakePillowImage)
    monkeypatch.setitem(sys.modules, "PIL.ImageOps", FakeImageOps)
    monkeypatch.setitem(sys.modules, "PySide6", pyside)
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)

    with pytest.raises(ValueError) as exc_info:
        service_module._verify_loadable_image(p)

    message = str(exc_info.value)
    assert "pillow failure kept" in message
    assert "qt failure kept" in message

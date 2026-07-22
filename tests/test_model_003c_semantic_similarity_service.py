from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from vision.embedding_provider import EmbeddingRecord, EmbeddingStore, FakeEmbeddingProvider, ModelMetadata, now_iso, source_identity
from vision.semantic_similarity_service import SemanticSimilarityService

JPEG_BYTES = bytes.fromhex("ffd8ffe000104a46494600010101006000600000ffdb0043000302020302020303030304030304050805050404050a070706080c0a0c0c0b0a0b0b0d0e12100d0e110e0b0b1016101113141515150c0f171816141812141514ffdb00430103040405040509050509140d0b0d141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414ffc00011080001000103012200021101031101ffc4001400010000000000000000000000000000000000000008ffc40014100100000000000000000000000000000000000000ffda000c03010002110311003f00b2c001ffd9")


def image(path: Path, marker: bytes) -> Path:
    path.write_bytes(JPEG_BYTES + marker)
    return path


def put(store: EmbeddingStore, path: Path, metadata: ModelMetadata, values: list[float]) -> None:
    key, mt, sz, fp = source_identity(path)
    store.put(EmbeddingRecord(key, fp, mt, sz, metadata.provider_id, metadata.checkpoint_id, metadata.revision, len(values), values, now_iso()))


def test_cosine_similarity_reference_values(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    meta = FakeEmbeddingProvider(dimension=2).metadata
    source = image(tmp_path / "source.jpg", b"s")
    same = image(tmp_path / "same.jpg", b"a")
    orthogonal = image(tmp_path / "orthogonal.jpg", b"b")
    opposite = image(tmp_path / "opposite.jpg", b"c")
    put(store, source, meta, [1, 0])
    put(store, same, meta, [2, 0])
    put(store, orthogonal, meta, [0, 3])
    put(store, opposite, meta, [-4, 0])

    results = {Path(r.photo_key).name: r.similarity for r in SemanticSimilarityService(store).most_similar(source, meta, limit=10)}

    assert results["same.jpg"] == pytest.approx(1.0)
    assert results["orthogonal.jpg"] == pytest.approx(0.0)
    assert results["opposite.jpg"] == pytest.approx(-1.0)


def test_top_n_ordering_exclusion_threshold_and_equal_score_tiebreak(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    meta = FakeEmbeddingProvider(dimension=2).metadata
    source = image(tmp_path / "source.jpg", b"s")
    low = image(tmp_path / "low.jpg", b"l")
    high_b = image(tmp_path / "b_high.jpg", b"b")
    high_a = image(tmp_path / "a_high.jpg", b"a")
    put(store, source, meta, [1, 0])
    put(store, low, meta, [0.5, 0.8660254])
    put(store, high_b, meta, [1, 0])
    put(store, high_a, meta, [1, 0])

    results = SemanticSimilarityService(store).most_similar(source, meta, limit=2, minimum_similarity=0.9)

    assert [Path(r.photo_key).name for r in results] == ["a_high.jpg", "b_high.jpg"]
    assert all(Path(r.photo_key).name != "source.jpg" for r in results)


def test_source_can_be_included(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    meta = FakeEmbeddingProvider(dimension=2).metadata
    source = image(tmp_path / "source.jpg", b"s")
    put(store, source, meta, [1, 0])

    results = SemanticSimilarityService(store).most_similar(source, meta, exclude_source=False)

    assert [Path(r.photo_key).name for r in results] == ["source.jpg"]


def test_missing_source_missing_candidate_and_empty_library_are_safe(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    meta = FakeEmbeddingProvider(dimension=2).metadata
    source = image(tmp_path / "source.jpg", b"s")
    missing_candidate = image(tmp_path / "missing.jpg", b"m")

    assert SemanticSimilarityService(store).most_similar(source, meta) == []
    put(store, source, meta, [1, 0])
    assert SemanticSimilarityService(store).most_similar(source, meta, candidates=[missing_candidate]) == []


def test_incompatible_model_keys_are_never_compared(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    meta = FakeEmbeddingProvider(dimension=2).metadata
    other = ModelMetadata("other", meta.checkpoint_id, meta.revision, "", "", "", "", "", 2)
    source = image(tmp_path / "source.jpg", b"s")
    candidate = image(tmp_path / "candidate.jpg", b"c")
    put(store, source, meta, [1, 0])
    put(store, candidate, other, [1, 0])

    assert SemanticSimilarityService(store).most_similar(source, meta) == []


def test_incompatible_dimensions_rejected(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    meta = FakeEmbeddingProvider(dimension=2).metadata
    source = image(tmp_path / "source.jpg", b"s")
    candidate = image(tmp_path / "candidate.jpg", b"c")
    put(store, source, meta, [1, 0])
    put(store, candidate, meta, [1, 0])
    with sqlite3.connect(store.db_path) as con:
        con.execute("UPDATE embeddings SET embedding_dimension=3 WHERE photo_key=?", (str(candidate.resolve()),))

    with pytest.raises(ValueError, match="dimension"):
        SemanticSimilarityService(store).most_similar(source, meta)


def test_no_embedding_recomputation(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    provider = FakeEmbeddingProvider(dimension=2)
    source = image(tmp_path / "source.jpg", b"s")
    candidate = image(tmp_path / "candidate.jpg", b"c")
    put(store, source, provider.metadata, [1, 0])
    put(store, candidate, provider.metadata, [1, 0])

    SemanticSimilarityService(store).most_similar(source, provider.metadata)

    assert provider.load_count == 0
    assert provider.embed_call_count == 0

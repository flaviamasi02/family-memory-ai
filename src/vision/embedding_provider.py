from __future__ import annotations

import hashlib
import math
import sqlite3
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock
from typing import Iterable, Protocol

from core.application_data import get_app_data_service


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ProviderStatus:
    state: str
    message: str = ""
    missing_dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelMetadata:
    provider_id: str
    checkpoint_id: str
    revision: str
    license: str
    source_url: str
    parameters: str
    download_size: str
    disk_usage: str
    embedding_dimension: int

    @property
    def model_key(self) -> str:
        return f"{self.provider_id}|{self.checkpoint_id}|{self.revision}|dim={self.embedding_dimension}"


@dataclass
class EmbeddingRecord:
    photo_key: str
    source_fingerprint: str
    source_mtime_ns: int
    source_size: int
    provider_id: str
    checkpoint_id: str
    model_revision: str
    embedding_dimension: int
    embedding: list[float]
    generated_at: str
    status: str = "ok"
    error: str = ""

    @property
    def model_key(self) -> str:
        return f"{self.provider_id}|{self.checkpoint_id}|{self.model_revision}|dim={self.embedding_dimension}"


class VisionEmbeddingProvider(Protocol):
    metadata: ModelMetadata

    def availability(self) -> ProviderStatus: ...
    def load(self, cancel_event: Event | None = None) -> None: ...
    def embed_images(self, paths: list[Path], cancel_event: Event | None = None) -> list[EmbeddingRecord]: ...
    def embed_texts(self, prompts: list[str], cancel_event: Event | None = None) -> list[list[float]]: ...
    def release(self) -> None: ...


def normalize(vec: Iterable[float]) -> list[float]:
    vals = [float(v) for v in vec]
    norm = math.sqrt(sum(v * v for v in vals))
    if norm <= 0:
        return vals
    return [v / norm for v in vals]


def cosine(a: list[float], b: list[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


def source_identity(path: Path) -> tuple[str, int, int, str]:
    st = path.stat()
    resolved = str(path.resolve())
    h = hashlib.sha256()
    h.update(resolved.encode("utf-8"))
    h.update(str(st.st_size).encode("ascii"))
    h.update(str(st.st_mtime_ns).encode("ascii"))
    with path.open("rb") as f:
        h.update(f.read(1024 * 1024))
    return resolved, int(st.st_mtime_ns), int(st.st_size), h.hexdigest()


def _embedding_to_blob(values: Iterable[float]) -> bytes:
    vals = [float(v) for v in values]
    return struct.pack(f"<{len(vals)}f", *vals)


def _blob_to_embedding(blob: bytes, dimension: int) -> list[float]:
    if len(blob) != dimension * 4:
        raise ValueError(f"Embedding blob length {len(blob)} does not match dimension {dimension}.")
    return list(struct.unpack(f"<{dimension}f", blob))


class EmbeddingStore:
    SCHEMA_VERSION = 2

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = get_app_data_service().cache_dir("embeddings") / "semantic_embeddings.sqlite3"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init()

    def _init(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS embeddings (
                    photo_key TEXT NOT NULL,
                    source_fingerprint TEXT NOT NULL,
                    source_mtime_ns INTEGER NOT NULL,
                    source_size INTEGER NOT NULL,
                    provider_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    model_revision TEXT NOT NULL,
                    model_key TEXT NOT NULL DEFAULT '',
                    embedding_dimension INTEGER NOT NULL,
                    embedding_blob BLOB,
                    embedding_json TEXT,
                    generated_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    error TEXT NOT NULL,
                    schema_version INTEGER NOT NULL DEFAULT 2,
                    PRIMARY KEY(photo_key, provider_id, checkpoint_id, model_revision)
                )
                """
            )
            columns = {row[1] for row in con.execute("PRAGMA table_info(embeddings)")}
            for name, ddl in {
                "model_key": "ALTER TABLE embeddings ADD COLUMN model_key TEXT NOT NULL DEFAULT ''",
                "embedding_blob": "ALTER TABLE embeddings ADD COLUMN embedding_blob BLOB",
                "updated_at": "ALTER TABLE embeddings ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''",
                "schema_version": "ALTER TABLE embeddings ADD COLUMN schema_version INTEGER NOT NULL DEFAULT 1",
            }.items():
                if name not in columns:
                    con.execute(ddl)
            con.execute("UPDATE embeddings SET model_key = provider_id || '|' || checkpoint_id || '|' || model_revision || '|dim=' || embedding_dimension WHERE model_key = ''")
            con.execute("UPDATE embeddings SET updated_at = generated_at WHERE updated_at = ''")
            con.execute("UPDATE embeddings SET schema_version = ? WHERE schema_version < ?", (self.SCHEMA_VERSION, self.SCHEMA_VERSION))
            con.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_source ON embeddings(source_fingerprint)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_identity_model ON embeddings(photo_key, model_key)")

    def get_valid(self, path: Path, metadata: ModelMetadata) -> EmbeddingRecord | None:
        try:
            key, mt, sz, fp = source_identity(path)
        except Exception:
            return None
        return self.get_valid_by_identity(key, fp, mt, sz, metadata)

    def get_valid_by_identity(self, photo_key: str, source_fingerprint: str, source_mtime_ns: int, source_size: int, metadata: ModelMetadata) -> EmbeddingRecord | None:
        with self._lock, sqlite3.connect(self.db_path) as con:
            row = con.execute(
                """
                SELECT embedding_dimension, embedding_blob, embedding_json, generated_at, status, error
                FROM embeddings
                WHERE photo_key=? AND model_key=? AND source_fingerprint=? AND source_mtime_ns=? AND source_size=? AND status='ok'
                """,
                (photo_key, metadata.model_key, source_fingerprint, source_mtime_ns, source_size),
            ).fetchone()
        if not row:
            return None
        dimension = int(row[0])
        if row[1] is not None:
            embedding = _blob_to_embedding(row[1], dimension)
        else:
            import json
            embedding = [float(v) for v in json.loads(row[2])]
        return EmbeddingRecord(photo_key, source_fingerprint, source_mtime_ns, source_size, metadata.provider_id, metadata.checkpoint_id, metadata.revision, dimension, embedding, row[3], row[4], row[5])

    def iter_valid_for_model(self, metadata: ModelMetadata) -> Iterable[EmbeddingRecord]:
        """Yield current valid embeddings for one exact provider/checkpoint/revision/dimension.

        Persisted rows are returned only when the source file still exists and
        its current identity matches the stored size, mtime, and fingerprint.
        """
        with self._lock, sqlite3.connect(self.db_path) as con:
            rows = con.execute(
                """
                SELECT photo_key, source_fingerprint, source_mtime_ns, source_size, embedding_dimension,
                       embedding_blob, embedding_json, generated_at, status, error
                FROM embeddings
                WHERE model_key=? AND status='ok'
                ORDER BY photo_key
                """,
                (metadata.model_key,),
            ).fetchall()
        for row in rows:
            photo_key = str(row[0])
            source_fingerprint = str(row[1])
            source_mtime_ns = int(row[2])
            source_size = int(row[3])
            try:
                path = Path(photo_key)
                st = path.stat()
                if int(st.st_size) != source_size or int(st.st_mtime_ns) != source_mtime_ns:
                    continue
                current_key, current_mtime_ns, current_size, current_fingerprint = source_identity(path)
                if (
                    current_key != photo_key
                    or current_fingerprint != source_fingerprint
                    or current_mtime_ns != source_mtime_ns
                    or current_size != source_size
                ):
                    continue
            except Exception:
                continue
            dimension = int(row[4])
            if row[5] is not None:
                embedding = _blob_to_embedding(row[5], dimension)
            else:
                import json
                embedding = [float(v) for v in json.loads(row[6])]
            yield EmbeddingRecord(photo_key, source_fingerprint, source_mtime_ns, source_size, metadata.provider_id, metadata.checkpoint_id, metadata.revision, dimension, embedding, str(row[7]), str(row[8]), str(row[9]))

    def put(self, rec: EmbeddingRecord) -> None:
        updated_at = now_iso()
        blob = _embedding_to_blob(rec.embedding) if rec.embedding else None
        with self._lock, sqlite3.connect(self.db_path) as con:
            con.execute(
                """
                REPLACE INTO embeddings
                (photo_key, source_fingerprint, source_mtime_ns, source_size, provider_id, checkpoint_id,
                 model_revision, model_key, embedding_dimension, embedding_blob, embedding_json, generated_at,
                 updated_at, status, error, schema_version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (rec.photo_key, rec.source_fingerprint, rec.source_mtime_ns, rec.source_size, rec.provider_id,
                 rec.checkpoint_id, rec.model_revision, rec.model_key, rec.embedding_dimension, blob, None,
                 rec.generated_at, updated_at, rec.status, rec.error, self.SCHEMA_VERSION),
            )

    def put_failure(self, path: Path, metadata: ModelMetadata, error: str) -> None:
        try:
            key, mt, sz, fp = source_identity(path)
        except Exception:
            key, mt, sz, fp = str(path), 0, 0, ""
        self.put(EmbeddingRecord(key, fp, mt, sz, metadata.provider_id, metadata.checkpoint_id, metadata.revision, metadata.embedding_dimension, [], now_iso(), "failed", error))

    def invalidate_embedding(self, path: Path, metadata: ModelMetadata | None = None) -> int:
        key = str(Path(path).resolve())
        with self._lock, sqlite3.connect(self.db_path) as con:
            if metadata is None:
                cur = con.execute("UPDATE embeddings SET status='invalidated', updated_at=? WHERE photo_key=?", (now_iso(), key))
            else:
                cur = con.execute("UPDATE embeddings SET status='invalidated', updated_at=? WHERE photo_key=? AND model_key=?", (now_iso(), key, metadata.model_key))
            return int(cur.rowcount)

    def invalidate_model_embeddings(self, model_key: str) -> int:
        with self._lock, sqlite3.connect(self.db_path) as con:
            cur = con.execute("UPDATE embeddings SET status='invalidated', updated_at=? WHERE model_key=?", (now_iso(), model_key))
            return int(cur.rowcount)

    def count(self) -> int:
        with sqlite3.connect(self.db_path) as con:
            return int(con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0])


class FakeEmbeddingProvider:
    def __init__(self, dimension: int = 512, batch_size: int = 4, available: bool = True):
        self.metadata = ModelMetadata("fake", "fake-v1", "test", "test", "local", "0", "0", "0", dimension)
        self.batch_size = batch_size
        self.loaded = False
        self.load_count = 0
        self.embed_call_count = 0
        self.available = available
        self.max_seen_batch = 0

    def availability(self):
        return ProviderStatus("Ready" if self.available else "Not installed", "" if self.available else "fake unavailable", () if self.available else ("fake",))

    def load(self, cancel_event=None):
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("cancelled")
        if not self.loaded:
            self.loaded = True
            self.load_count += 1

    def embed_images(self, paths, cancel_event=None):
        if not self.loaded:
            self.load(cancel_event)
        self.embed_call_count += 1
        self.max_seen_batch = max(self.max_seen_batch, len(paths))
        out = []
        for p in paths:
            if cancel_event and cancel_event.is_set():
                break
            try:
                key, mt, sz, fp = source_identity(Path(p))
                seed = int(hashlib.sha1(fp.encode()).hexdigest()[:8], 16)
            except Exception as e:
                out.append(EmbeddingRecord(str(p), "", 0, 0, self.metadata.provider_id, self.metadata.checkpoint_id, self.metadata.revision, self.metadata.embedding_dimension, [], now_iso(), "failed", str(e)))
                continue
            vals = normalize([((seed >> (i % 24)) & 255) + 1 for i in range(self.metadata.embedding_dimension)])
            out.append(EmbeddingRecord(key, fp, mt, sz, self.metadata.provider_id, self.metadata.checkpoint_id, self.metadata.revision, self.metadata.embedding_dimension, vals, now_iso()))
        return out

    def embed_texts(self, prompts, cancel_event=None):
        if not self.loaded:
            self.load(cancel_event)
        return [normalize([((int(hashlib.sha1(t.encode()).hexdigest()[:8], 16) >> (i % 24)) & 255) + 1 for i in range(self.metadata.embedding_dimension)]) for t in prompts]

    def release(self):
        self.loaded = False

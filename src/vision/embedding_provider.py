from __future__ import annotations

import hashlib, math, os, sqlite3, statistics, time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock
from typing import Any, Iterable, Protocol

from core.application_data import get_app_data_service, atomic_write_json


def now_iso() -> str: return datetime.now(timezone.utc).isoformat()

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

class VisionEmbeddingProvider(Protocol):
    metadata: ModelMetadata
    def availability(self) -> ProviderStatus: ...
    def load(self, cancel_event: Event | None = None) -> None: ...
    def embed_images(self, paths: list[Path], cancel_event: Event | None = None) -> list[EmbeddingRecord]: ...
    def embed_texts(self, prompts: list[str], cancel_event: Event | None = None) -> list[list[float]]: ...
    def release(self) -> None: ...


def normalize(vec: Iterable[float]) -> list[float]:
    vals = [float(v) for v in vec]
    norm = math.sqrt(sum(v*v for v in vals))
    if norm <= 0: return vals
    return [v/norm for v in vals]

def cosine(a: list[float], b: list[float]) -> float:
    return float(sum(x*y for x,y in zip(a,b)))

def source_identity(path: Path) -> tuple[str, int, int, str]:
    st = path.stat()
    h = hashlib.sha256()
    h.update(str(path.resolve()).encode())
    h.update(str(st.st_size).encode()); h.update(str(st.st_mtime_ns).encode())
    with path.open('rb') as f: h.update(f.read(1024*1024))
    return str(path.resolve()), int(st.st_mtime_ns), int(st.st_size), h.hexdigest()

class EmbeddingStore:
    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = get_app_data_service().cache_dir('embeddings') / 'semantic_embeddings.sqlite3'
        self.db_path = Path(db_path); self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock(); self._init()
    def _init(self):
        with sqlite3.connect(self.db_path) as con:
            con.execute('''CREATE TABLE IF NOT EXISTS embeddings (photo_key TEXT, source_fingerprint TEXT, source_mtime_ns INTEGER, source_size INTEGER, provider_id TEXT, checkpoint_id TEXT, model_revision TEXT, embedding_dimension INTEGER, embedding_json TEXT, generated_at TEXT, status TEXT, error TEXT, PRIMARY KEY(photo_key, provider_id, checkpoint_id, model_revision))''')
            con.execute('CREATE INDEX IF NOT EXISTS idx_embeddings_source ON embeddings(source_fingerprint)')
    def get_valid(self, path: Path, metadata: ModelMetadata) -> EmbeddingRecord | None:
        try: key, mt, sz, fp = source_identity(path)
        except Exception: return None
        with self._lock, sqlite3.connect(self.db_path) as con:
            row = con.execute('SELECT embedding_dimension, embedding_json, generated_at, status, error FROM embeddings WHERE photo_key=? AND provider_id=? AND checkpoint_id=? AND model_revision=? AND source_fingerprint=? AND source_mtime_ns=? AND source_size=?', (key, metadata.provider_id, metadata.checkpoint_id, metadata.revision, fp, mt, sz)).fetchone()
        if not row: return None
        import json
        return EmbeddingRecord(key, fp, mt, sz, metadata.provider_id, metadata.checkpoint_id, metadata.revision, int(row[0]), list(json.loads(row[1])), row[2], row[3], row[4])
    def put(self, rec: EmbeddingRecord) -> None:
        import json
        with self._lock, sqlite3.connect(self.db_path) as con:
            con.execute('REPLACE INTO embeddings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (rec.photo_key, rec.source_fingerprint, rec.source_mtime_ns, rec.source_size, rec.provider_id, rec.checkpoint_id, rec.model_revision, rec.embedding_dimension, json.dumps(rec.embedding), rec.generated_at, rec.status, rec.error))
    def count(self) -> int:
        with sqlite3.connect(self.db_path) as con: return int(con.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0])

class FakeEmbeddingProvider:
    def __init__(self, dimension:int=8, batch_size:int=4, available:bool=True):
        self.metadata=ModelMetadata('fake','fake-v1','test','test','local','0', '0', '0', dimension); self.batch_size=batch_size; self.loaded=False; self.load_count=0; self.available=available; self.max_seen_batch=0
    def availability(self): return ProviderStatus('Ready' if self.available else 'Not installed', '' if self.available else 'fake unavailable', () if self.available else ('fake',))
    def load(self, cancel_event=None):
        if cancel_event and cancel_event.is_set(): raise RuntimeError('cancelled')
        self.loaded=True; self.load_count+=1
    def embed_images(self, paths, cancel_event=None):
        if not self.loaded: self.load(cancel_event)
        self.max_seen_batch=max(self.max_seen_batch, len(paths)); out=[]
        for p in paths:
            if cancel_event and cancel_event.is_set(): break
            try: key,mt,sz,fp=source_identity(Path(p)); seed=int(hashlib.sha1(fp.encode()).hexdigest()[:8],16)
            except Exception as e: out.append(EmbeddingRecord(str(p),'',0,0,self.metadata.provider_id,self.metadata.checkpoint_id,self.metadata.revision,self.metadata.embedding_dimension,[],now_iso(),'failed',str(e))); continue
            vals=normalize([((seed >> (i%24)) & 255)+1 for i in range(self.metadata.embedding_dimension)])
            out.append(EmbeddingRecord(key,fp,mt,sz,self.metadata.provider_id,self.metadata.checkpoint_id,self.metadata.revision,self.metadata.embedding_dimension,vals,now_iso()))
        return out
    def embed_texts(self, prompts, cancel_event=None):
        if not self.loaded: self.load(cancel_event)
        return [normalize([((int(hashlib.sha1(t.encode()).hexdigest()[:8],16)>>(i%24))&255)+1 for i in range(self.metadata.embedding_dimension)]) for t in prompts]
    def release(self): self.loaded=False

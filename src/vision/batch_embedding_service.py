from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Callable, Iterable


from vision.evaluation_sources import EVALUATION_IMAGE_EXTENSIONS as IMAGE_EXTENSIONS
from vision.embedding_provider import EmbeddingRecord, EmbeddingStore, VisionEmbeddingProvider, now_iso, source_identity
from vision.mobileclip_provider import MobileCLIPEmbeddingProvider

EMBEDDING_STATUS_PROCESSED = "processed"
EMBEDDING_STATUS_CACHED = "cached"
EMBEDDING_STATUS_FAILED = "failed"
EMBEDDING_STATUS_CANCELLED = "cancelled"


@dataclass(frozen=True)
class BatchEmbeddingProgress:
    current_index: int
    total_count: int
    current_image: str
    processed_count: int
    cached_count: int
    failed_count: int


@dataclass(frozen=True)
class BatchImageEmbeddingOutcome:
    image: str
    status: str
    error: str = ""
    embedding_dimension: int = 0


@dataclass
class BatchEmbeddingResult:
    total_images_received: int
    processed_successfully: int = 0
    skipped_cached: int = 0
    failed: int = 0
    cancelled: int = 0
    elapsed_seconds: float = 0.0
    outcomes: list[BatchImageEmbeddingOutcome] = field(default_factory=list)


ProgressCallback = Callable[[BatchEmbeddingProgress], None]


class BatchEmbeddingService:
    def __init__(self, provider: VisionEmbeddingProvider | None = None, store: EmbeddingStore | None = None):
        self.provider = provider or MobileCLIPEmbeddingProvider()
        self.store = store or EmbeddingStore()

    @property
    def model_key(self) -> str:
        return self.provider.metadata.model_key

    def get_cached_embedding(self, image) -> EmbeddingRecord | None:
        return self.store.get_valid(_path_for(image), self.provider.metadata)

    def needs_embedding(self, image) -> bool:
        path = _path_for(image)
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            return False
        return self.get_cached_embedding(path) is None

    def invalidate_embedding(self, image) -> int:
        return self.store.invalidate_embedding(_path_for(image), self.provider.metadata)

    def invalidate_model_embeddings(self, model_key: str | None = None) -> int:
        return self.store.invalidate_model_embeddings(model_key or self.model_key)

    def embed_images(self, images: Iterable, progress_callback: ProgressCallback | None = None, cancellation_token: Event | None = None) -> BatchEmbeddingResult:
        paths = [_path_for(image) for image in images]
        result = BatchEmbeddingResult(total_images_received=len(paths))
        start = time.perf_counter()
        loaded = False
        for idx, path in enumerate(paths, start=1):
            if cancellation_token and cancellation_token.is_set():
                result.cancelled = len(paths) - idx + 1
                result.outcomes.append(BatchImageEmbeddingOutcome(str(path), EMBEDDING_STATUS_CANCELLED, "Cancelled before processing image."))
                break
            try:
                if path.suffix.lower() not in IMAGE_EXTENSIONS:
                    raise ValueError(f"Unsupported image extension: {path.suffix.lower()}")
                cached = self.store.get_valid(path, self.provider.metadata)
                if cached is not None:
                    result.skipped_cached += 1
                    result.outcomes.append(BatchImageEmbeddingOutcome(str(path), EMBEDDING_STATUS_CACHED, embedding_dimension=cached.embedding_dimension))
                else:
                    if _provider_requires_image_decode_validation(self.provider):
                        _verify_loadable_image(path)
                    else:
                        _verify_supported_image_signature(path)
                    if not loaded:
                        self.provider.load(cancellation_token)
                        loaded = True
                    records = self.provider.embed_images([path], cancellation_token)
                    if not records:
                        if cancellation_token and cancellation_token.is_set():
                            result.cancelled = len(paths) - idx + 1
                            result.outcomes.append(BatchImageEmbeddingOutcome(str(path), EMBEDDING_STATUS_CANCELLED, "Cancelled during provider embedding."))
                            break
                        raise RuntimeError("Embedding provider returned no image embedding.")
                    record = records[0]
                    self._validate_record(record)
                    self.store.put(record)
                    result.processed_successfully += 1
                    result.outcomes.append(BatchImageEmbeddingOutcome(str(path), EMBEDDING_STATUS_PROCESSED, embedding_dimension=record.embedding_dimension))
            except Exception as exc:
                result.failed += 1
                error = str(exc)
                self.store.put_failure(path, self.provider.metadata, error)
                result.outcomes.append(BatchImageEmbeddingOutcome(str(path), EMBEDDING_STATUS_FAILED, error=error, embedding_dimension=self.provider.metadata.embedding_dimension))
            finally:
                result.elapsed_seconds = time.perf_counter() - start
                if progress_callback:
                    progress_callback(BatchEmbeddingProgress(idx, len(paths), str(path), result.processed_successfully, result.skipped_cached, result.failed))
        result.elapsed_seconds = time.perf_counter() - start
        return result

    def _validate_record(self, record: EmbeddingRecord) -> None:
        expected = self.provider.metadata.embedding_dimension
        if record.status != "ok":
            raise RuntimeError(record.error or "Embedding provider failed for image.")
        if record.embedding_dimension != expected or len(record.embedding) != expected:
            raise ValueError(f"Expected {expected}-dimensional embedding, got {record.embedding_dimension}/{len(record.embedding)}.")
        if not all(math.isfinite(float(v)) for v in record.embedding):
            raise ValueError("Embedding contains NaN or infinite values.")


def _path_for(image) -> Path:
    return Path(getattr(image, "path", image))


def _provider_requires_image_decode_validation(provider: VisionEmbeddingProvider) -> bool:
    return bool(getattr(provider, "requires_image_decode_validation", isinstance(provider, MobileCLIPEmbeddingProvider)))


def _verify_loadable_image(path: Path) -> None:
    decode_errors: list[str] = []

    try:
        from PIL import Image, ImageOps
    except ImportError:
        Image = None
        ImageOps = None

    if Image is not None and ImageOps is not None:
        try:
            with Image.open(path) as image:
                ImageOps.exif_transpose(image).convert("RGB").load()
            return
        except Exception as exc:
            decode_errors.append(str(exc))

    try:
        from PySide6.QtGui import QImageReader
    except ImportError:
        QImageReader = None

    if QImageReader is not None:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        if not image.isNull():
            return
        decode_errors.append(reader.errorString() or "Image could not be decoded by Qt.")

    if not decode_errors:
        header = path.read_bytes()[:12]
        if header.startswith(b"\x89PNG\r\n\x1a\n") or header.startswith(b"\xff\xd8\xff") or header.startswith(b"RIFF"):
            return
        decode_errors.append("No image decoder is available in this environment.")

    raise ValueError("; ".join(error for error in decode_errors if error))


def _verify_supported_image_signature(path: Path) -> None:
    header = path.read_bytes()[:32]
    if (
        header.startswith(b"\xff\xd8\xff")
        or header.startswith(b"\x89PNG\r\n\x1a\n")
        or header.startswith(b"RIFF")
        or b"ftyp" in header[:16]
    ):
        return
    raise ValueError("Image file signature is not recognized.")

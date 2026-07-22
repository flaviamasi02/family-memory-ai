from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from vision.embedding_provider import EmbeddingRecord, EmbeddingStore, ModelMetadata


@dataclass(frozen=True)
class SemanticSimilarityResult:
    """Similarity score for one stored image embedding."""

    photo_key: str
    similarity: float
    model_key: str


class SemanticSimilarityService:
    """Compare existing persisted image embeddings without recomputing them.

    The current implementation performs an exact linear scan over candidate
    vectors for the requested model metadata: O(n * d) time and O(n) result
    memory for n valid candidates and d embedding dimensions. This keeps the
    boundary correct and simple for a ~50k-photo library while leaving room for
    a future ANN/vector index behind the same service API.
    """

    def __init__(self, store: EmbeddingStore | None = None):
        self.store = store or EmbeddingStore()

    def most_similar(
        self,
        source_image,
        metadata: ModelMetadata,
        *,
        candidates: Iterable | None = None,
        limit: int = 10,
        exclude_source: bool = True,
        minimum_similarity: float | None = None,
    ) -> list[SemanticSimilarityResult]:
        """Return top matches ordered highest-to-lowest by cosine similarity.

        Missing source/candidate embeddings are skipped safely. All compared
        rows must match the complete model key (provider, checkpoint, revision,
        and dimension) and have vector lengths equal to the model dimension.
        """

        if limit <= 0:
            return []
        source = self.store.get_valid(_path_for(source_image), metadata)
        if source is None:
            return []
        self._validate_record(source, metadata)

        if candidates is None:
            candidate_records = self.store.iter_valid_for_model(metadata)
        else:
            candidate_records = (
                rec for item in candidates if (rec := self.store.get_valid(_path_for(item), metadata)) is not None
            )

        results: list[SemanticSimilarityResult] = []
        for candidate in candidate_records:
            self._validate_record(candidate, metadata)
            if exclude_source and candidate.photo_key == source.photo_key:
                continue
            score = _cosine_similarity(source.embedding, candidate.embedding)
            if minimum_similarity is not None and score < minimum_similarity:
                continue
            results.append(SemanticSimilarityResult(candidate.photo_key, score, candidate.model_key))

        results.sort(key=lambda r: (-r.similarity, r.photo_key))
        return results[:limit]

    def _validate_record(self, record: EmbeddingRecord, metadata: ModelMetadata) -> None:
        if record.model_key != metadata.model_key:
            raise ValueError(f"Embedding model key {record.model_key!r} is incompatible with {metadata.model_key!r}.")
        if record.embedding_dimension != metadata.embedding_dimension or len(record.embedding) != metadata.embedding_dimension:
            raise ValueError(
                f"Embedding dimension {record.embedding_dimension}/{len(record.embedding)} is incompatible with "
                f"model dimension {metadata.embedding_dimension}."
            )
        if not all(math.isfinite(float(v)) for v in record.embedding):
            raise ValueError("Embedding contains NaN or infinite values.")


def _path_for(image) -> Path:
    return Path(getattr(image, "path", image))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a <= 0 or norm_b <= 0:
        raise ValueError("Cannot compare zero-length embedding vector.")
    return float(dot / (norm_a * norm_b))

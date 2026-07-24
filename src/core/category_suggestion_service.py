from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from core.category_registry import CategoryRegistry, get_category_registry
from vision.embedding_provider import EmbeddingStore, ModelMetadata
from vision.semantic_similarity_service import SemanticSimilarityService


@dataclass(frozen=True)
class CategorySuggestionEvidence:
    photo_key: str
    category_id: str
    category_name: str
    similarity: float
    trust_level: str
    trust_weight: float


@dataclass(frozen=True)
class CategorySuggestionResult:
    source_photo_key: str
    status: str
    suggested_category_id: str = ""
    suggested_category_name: str = ""
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)
    evidence_counts: dict[str, int] = field(default_factory=dict)
    supporting_photos: list[CategorySuggestionEvidence] = field(default_factory=list)
    model_key: str = ""
    provenance: str = "stored_vectors+trusted_labels+deterministic_rules"


@dataclass(frozen=True)
class CategorySuggestionConfig:
    minimum_similarity: float = 0.72
    similar_limit: int = 40
    minimum_support_count: int = 2
    minimum_winning_margin: float = 0.22
    conflict_margin: float = 0.12
    minimum_confidence: float = 0.52


class CategorySuggestionService:
    """UI-independent explainable category suggestion service.

    Confidence is a deterministic 0.0-1.0 heuristic from trusted similar-photo
    support, average/strongest similarity, category agreement, deterministic
    classifier agreement, and conflicts. It is not a probability.
    """

    TRUST_WEIGHTS = {
        "manual_confirmed": 1.0,
        "user_correction": 1.0,
        "accepted_suggestion": 0.85,
        "deterministic_classification": 0.55,
        "machine_unreviewed": 0.0,
    }

    def __init__(
        self,
        *,
        similarity_service: SemanticSimilarityService | None = None,
        embedding_store: EmbeddingStore | None = None,
        category_registry: CategoryRegistry | None = None,
        media_classifier=None,
        config: CategorySuggestionConfig | None = None,
    ):
        self.embedding_store = embedding_store or EmbeddingStore()
        self.similarity_service = similarity_service or SemanticSimilarityService(
            self.embedding_store
        )
        self.category_registry = category_registry or get_category_registry()
        if media_classifier is None:
            from core.media_classifier import MediaClassifier

            media_classifier = MediaClassifier(enable_visual_content_analysis=False)
        self.media_classifier = media_classifier
        self.config = config or CategorySuggestionConfig()
        self._cache: dict[tuple[str, str, int], CategorySuggestionResult] = {}
        self._feedback: list[dict[str, str]] = []

    def suggest(
        self, source_photo, all_photos: Iterable, metadata: ModelMetadata
    ) -> CategorySuggestionResult:
        source_key = str(Path(getattr(source_photo, "path", source_photo)).resolve())
        try:
            if (
                self.embedding_store.get_valid(
                    Path(getattr(source_photo, "path", source_photo)), metadata
                )
                is None
            ):
                return self._result(
                    source_key,
                    "no_embedding",
                    model_key=metadata.model_key,
                    reasons=[
                        "No current stored embedding is available for this photo."
                    ],
                )
            eligible = self._eligible_category_ids()
            if not eligible:
                return self._result(
                    source_key,
                    "no_eligible_categories",
                    model_key=metadata.model_key,
                    reasons=["No content categories are eligible for AI suggestions."],
                )
            by_key = {str(Path(getattr(p, "path", p)).resolve()): p for p in all_photos}
            signature = self._evidence_signature(by_key.values())
            cache_key = (source_key, metadata.model_key, signature)
            if cache_key in self._cache:
                return self._cache[cache_key]
            sims = self.similarity_service.most_similar(
                source_photo,
                metadata,
                candidates=by_key.values(),
                limit=self.config.similar_limit,
                exclude_source=True,
                minimum_similarity=self.config.minimum_similarity,
            )
            evidence: list[CategorySuggestionEvidence] = []
            scores: dict[str, float] = {}
            counts: dict[str, int] = {}
            for sim in sims:
                photo = by_key.get(str(Path(sim.photo_key).resolve()))
                if photo is None:
                    continue
                cat, trust = self._trusted_category(photo)
                if not cat or cat not in eligible:
                    continue
                weight = self.TRUST_WEIGHTS[trust]
                if weight <= 0:
                    continue
                ev = CategorySuggestionEvidence(
                    sim.photo_key,
                    cat,
                    self.category_registry.label_for(cat),
                    sim.similarity,
                    trust,
                    weight,
                )
                evidence.append(ev)
                scores[cat] = scores.get(cat, 0.0) + sim.similarity * weight
                counts[cat] = counts.get(cat, 0) + 1
            if not evidence:
                result = self._result(
                    source_key,
                    "insufficient_evidence",
                    model_key=metadata.model_key,
                    reasons=[
                        "No similar photos have trustworthy confirmed category evidence."
                    ],
                )
                self._cache[cache_key] = result
                return result
            ranked = sorted(
                scores.items(),
                key=lambda x: (-x[1], self.category_registry.label_for(x[0]), x[0]),
            )
            winner, win_score = ranked[0]
            runner_score = ranked[1][1] if len(ranked) > 1 else 0.0
            if counts.get(winner, 0) < self.config.minimum_support_count:
                result = self._result(
                    source_key,
                    "insufficient_evidence",
                    model_key=metadata.model_key,
                    evidence_counts=counts,
                    reasons=[
                        "Not enough trusted similar photos support one category yet."
                    ],
                )
                self._cache[cache_key] = result
                return result
            margin = (win_score - runner_score) / max(win_score, 0.0001)
            if runner_score and margin < self.config.conflict_margin:
                result = self._result(
                    source_key,
                    "conflicting_evidence",
                    model_key=metadata.model_key,
                    evidence_counts=counts,
                    reasons=[
                        "Trusted similar photos support multiple categories too evenly."
                    ],
                )
                self._cache[cache_key] = result
                return result
            winning_evidence = [e for e in evidence if e.category_id == winner]
            avg_sim = sum(e.similarity for e in winning_evidence) / len(
                winning_evidence
            )
            strongest = max(e.similarity for e in winning_evidence)
            support_factor = min(1.0, len(winning_evidence) / 6.0)
            agreement = win_score / max(sum(scores.values()), 0.0001)
            trust_avg = sum(e.trust_weight for e in winning_evidence) / len(
                winning_evidence
            )
            confidence = (
                0.18
                + 0.26 * support_factor
                + 0.22 * avg_sim
                + 0.12 * strongest
                + 0.16 * agreement
                + 0.06 * trust_avg
            )
            deterministic = self.media_classifier.classify(
                getattr(source_photo, "path", source_photo),
                getattr(source_photo, "metadata", {}) or {},
                allow_visual_analysis=False,
            )
            det_cat = getattr(
                deterministic.media_category, "value", str(deterministic.media_category)
            )
            if det_cat == winner and deterministic.classification_confidence >= 0.55:
                confidence += 0.08
                det_reason = "Existing deterministic signals agree."
            elif det_cat != "unknown" and det_cat in eligible:
                confidence -= 0.10
                det_reason = "Existing deterministic signals point to another category, so confidence is reduced."
            else:
                det_reason = "Existing deterministic signals are inconclusive."
            confidence = max(0.0, min(1.0, round(confidence, 4)))
            if confidence < self.config.minimum_confidence or (
                runner_score and margin < self.config.minimum_winning_margin
            ):
                status = (
                    "conflicting_evidence" if runner_score else "insufficient_evidence"
                )
                result = self._result(
                    source_key,
                    status,
                    model_key=metadata.model_key,
                    evidence_counts=counts,
                    reasons=[
                        "Evidence is not strong enough for a clear advisory suggestion.",
                        det_reason,
                    ],
                )
                self._cache[cache_key] = result
                return result
            reasons = [
                f"Similar to {len(winning_evidence)} photos previously confirmed as {self.category_registry.label_for(winner)}.",
                "Visual similarity supports this category.",
                det_reason,
            ]
            result = self._result(
                source_key,
                "suggested",
                winner,
                self.category_registry.label_for(winner),
                confidence,
                reasons,
                counts,
                sorted(winning_evidence, key=lambda e: (-e.similarity, e.photo_key))[
                    :8
                ],
                metadata.model_key,
            )
            self._cache[cache_key] = result
            return result
        except Exception as exc:
            return self._result(
                source_key,
                "error",
                model_key=metadata.model_key,
                reasons=[f"Suggestion failed safely: {exc}"],
            )

    def record_rejection(
        self, result: CategorySuggestionResult, source: str = "user"
    ) -> None:
        self._feedback.append(
            {
                "photo_key": result.source_photo_key,
                "category_id": result.suggested_category_id,
                "source": source,
                "action": "rejected",
            }
        )

    @property
    def feedback_events(self) -> list[dict[str, str]]:
        return list(self._feedback)

    def invalidate_cache(self) -> None:
        self._cache.clear()

    def _eligible_category_ids(self) -> set[str]:
        return {
            c.id
            for c in self.category_registry.all_categories()
            if c.is_album_candidate and c.id != "unknown"
        }

    def _trusted_category(self, photo) -> tuple[str, str]:
        md = dict(getattr(photo, "metadata", {}) or {})
        user = (
            str(
                md.get("user_corrected_media_category")
                or getattr(photo, "user_corrected_media_category", "")
                or ""
            )
            .strip()
            .lower()
        )
        if user:
            return user, "user_correction"
        if str(md.get("category_confirmation_state", "")).lower() in {
            "confirmed",
            "manual_confirmed",
        }:
            return (
                str(
                    md.get("effective_media_category")
                    or getattr(photo, "effective_media_category", "")
                    or ""
                )
                .strip()
                .lower(),
                "manual_confirmed",
            )
        if str(md.get("category_suggestion_state", "")).lower() == "accepted":
            return (
                str(
                    md.get("effective_media_category")
                    or getattr(photo, "effective_media_category", "")
                    or ""
                )
                .strip()
                .lower(),
                "accepted_suggestion",
            )
        if bool(md.get("deterministic_category_trusted", False)):
            return (
                str(
                    md.get("automatic_media_category")
                    or getattr(photo, "automatic_media_category", "")
                    or ""
                )
                .strip()
                .lower(),
                "deterministic_classification",
            )
        return "", "machine_unreviewed"

    def _evidence_signature(self, photos: Iterable) -> int:
        return hash(
            tuple(
                sorted(
                    (
                        str(Path(getattr(p, "path", p)).resolve()),
                        self._trusted_category(p),
                    )
                    for p in photos
                )
            )
        )

    def _result(
        self,
        source_key: str,
        status: str,
        suggested_category_id: str = "",
        suggested_category_name: str = "",
        confidence: float = 0.0,
        reasons: Optional[list[str]] = None,
        evidence_counts: Optional[dict[str, int]] = None,
        supporting_photos: Optional[list[CategorySuggestionEvidence]] = None,
        model_key: str = "",
    ) -> CategorySuggestionResult:
        return CategorySuggestionResult(
            source_key,
            status,
            suggested_category_id,
            suggested_category_name,
            confidence,
            reasons or [],
            evidence_counts or {},
            supporting_photos or [],
            model_key,
        )

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core.application_data import get_app_data_service, atomic_write_json
from core.category_registry import get_category_registry


@dataclass
class PreferenceLearningEvent:
    file_path: str
    event_type: str
    target: str
    decision: str
    previous_value: str
    new_value: str
    source_action: str
    timestamp: str
    context: dict[str, str | int | float | bool] = field(default_factory=dict)


@dataclass
class PreferenceSignal:
    id: str
    signal_type: str
    target: str
    decision: str
    support_count: int
    strength: float
    explanation: str
    source_action: str
    first_learned_at: str = ""
    last_learned_at: str = ""


@dataclass
class PreferenceLearningProfile:
    signals: list[PreferenceSignal] = field(default_factory=list)
    total_events: int = 0
    signal_counts: dict[str, int] = field(default_factory=dict)
    last_updated_at: str = ""


POSITIVE_DECISIONS = {"approve_for_album", "approved", "keep"}
CLEANUP_DECISIONS = {
    "reject",
    "rejected",
    "irrelevant_media",
    "duplicate",
    "document",
    "screenshot",
    "advertisement",
    "meme",
    "move_to_cleanup_folder",
    "move_to_cleanup_review",
}


class PreferenceLearningEngine:
    def __init__(self, storage_root: Optional[str | Path] = None):
        service = get_app_data_service(storage_root or os.environ.get("FAMILY_MEMORY_LEARNING_ROOT"), legacy_root=Path.cwd())
        self.migration_diagnostics = service.diagnostics
        self._storage_path = service.profile_path("preference_learning_profile.json")
        self._event_summaries: list[dict[str, Any]] = []
        self.profile = PreferenceLearningProfile()
        self._load_profile()

    @property
    def storage_path(self) -> Path:
        return self._storage_path

    def record_category_correction(
        self,
        photo,
        previous_category: str,
        corrected_category: str,
        source: str,
    ) -> PreferenceLearningEvent:
        corrected = _normalize(corrected_category) or "unknown"
        previous = _normalize(previous_category) or "unknown"
        event = PreferenceLearningEvent(
            file_path=str(getattr(photo, "path", "")),
            event_type="category_correction",
            target=corrected,
            decision=f"corrected_to_{corrected}",
            previous_value=previous,
            new_value=corrected,
            source_action=_source(source),
            timestamp=_now_iso(),
            context=_photo_context(photo),
        )
        self.record_event(event)
        return event

    def record_decision(
        self,
        photo,
        previous_decision: str,
        new_decision: str,
        source: str,
    ) -> PreferenceLearningEvent:
        decision = _normalize(new_decision) or "unknown"
        previous = _normalize(previous_decision) or "pending"
        target = _event_target_for_photo(photo, fallback=decision)
        event_type = "cleanup_decision" if _is_cleanup_decision(decision, target) else "decision"
        event = PreferenceLearningEvent(
            file_path=str(getattr(photo, "path", "")),
            event_type=event_type,
            target=target,
            decision=decision,
            previous_value=previous,
            new_value=decision,
            source_action=_source(source),
            timestamp=_now_iso(),
            context=_photo_context(photo),
        )
        self.record_event(event)
        return event

    def record_cleanup_decision(
        self,
        photo,
        previous_decision: str,
        new_decision: str,
        source: str,
    ) -> PreferenceLearningEvent:
        event = self.record_decision(photo, previous_decision, new_decision, source)
        event.event_type = "cleanup_decision"
        if self._event_summaries:
            self._event_summaries[-1]["event_type"] = "cleanup_decision"
            self._recompute_profile()
            self._save_profile()
        return event

    def record_event(self, event: PreferenceLearningEvent) -> None:
        summary = {
            "file_path": event.file_path,
            "event_type": _normalize(event.event_type) or "event",
            "target": _normalize(event.target) or "unknown",
            "decision": _normalize(event.decision) or "unknown",
            "previous_value": _normalize(event.previous_value),
            "new_value": _normalize(event.new_value),
            "source_action": _source(event.source_action),
            "timestamp": event.timestamp or _now_iso(),
            "context": dict(event.context or {}),
        }
        self._event_summaries.append(summary)
        self._recompute_profile()
        self._save_profile()

    def learning_summary(self) -> dict[str, Any]:
        strongest = sorted(
            self.profile.signals,
            key=lambda signal: (signal.strength, signal.support_count, signal.signal_type, signal.target),
            reverse=True,
        )
        return {
            "total_events": int(self.profile.total_events),
            "signal_counts": dict(self.profile.signal_counts),
            "preference_signals": [asdict(signal) for signal in strongest],
            "strongest_preference_signals": [asdict(signal) for signal in strongest[:5]],
            "last_updated_at": self.profile.last_updated_at,
            "event_summaries": list(self._event_summaries),
        }

    def _recompute_profile(self) -> None:
        grouped: dict[tuple[str, str, str, str], int] = {}
        grouped_timestamps: dict[tuple[str, str, str, str], list[str]] = {}

        for event in self._event_summaries:
            for signal_type, target, decision in _signal_specs_for_event(event):
                source_action = _source(event.get("source_action", "user"))
                key = (signal_type, target, decision, source_action)
                grouped[key] = grouped.get(key, 0) + 1
                timestamp = str(event.get("timestamp", "") or "").strip()
                if timestamp:
                    grouped_timestamps.setdefault(key, []).append(timestamp)

        signals: list[PreferenceSignal] = []
        signal_counts: dict[str, int] = {}

        for (signal_type, target, decision, source_action), support_count in grouped.items():
            signal_counts[signal_type] = signal_counts.get(signal_type, 0) + support_count
            strength = min(0.99, round(0.35 + min(0.60, support_count * 0.10), 3))
            signals.append(
                PreferenceSignal(
                    id=_signal_id(signal_type, target, decision, source_action),
                    signal_type=signal_type,
                    target=target,
                    decision=decision,
                    support_count=int(support_count),
                    strength=float(strength),
                    explanation=_signal_explanation(signal_type, target, decision, support_count, source_action),
                    source_action=source_action,
                    first_learned_at=_first_timestamp(grouped_timestamps.get((signal_type, target, decision, source_action), [])),
                    last_learned_at=_latest_timestamp_values(grouped_timestamps.get((signal_type, target, decision, source_action), [])),
                )
            )

        signals.sort(
            key=lambda item: (item.support_count, item.strength, item.signal_type, item.target),
            reverse=True,
        )
        self.profile = PreferenceLearningProfile(
            signals=signals,
            total_events=len(self._event_summaries),
            signal_counts=signal_counts,
            last_updated_at=_latest_timestamp(self._event_summaries),
        )

    def _save_profile(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "total_events": self.profile.total_events,
            "signal_counts": self.profile.signal_counts,
            "signals": [asdict(signal) for signal in self.profile.signals],
            "event_summaries": self._event_summaries,
            "last_updated_at": self.profile.last_updated_at or _now_iso(),
        }
        payload["schema_version"] = 1
        atomic_write_json(self._storage_path, payload)

    def _load_profile(self) -> None:
        if not self._storage_path.exists():
            return

        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except Exception:
            self._event_summaries = []
            self.profile = PreferenceLearningProfile()
            return

        if not isinstance(payload, dict):
            return

        raw_summaries = payload.get("event_summaries", [])
        if isinstance(raw_summaries, list):
            for raw in raw_summaries:
                if not isinstance(raw, dict):
                    continue
                target = _normalize(raw.get("target", ""))
                decision = _normalize(raw.get("decision", ""))
                event_type = _normalize(raw.get("event_type", ""))
                if not target or not decision or not event_type:
                    continue
                self._event_summaries.append(
                    {
                        "file_path": str(raw.get("file_path", "") or ""),
                        "event_type": event_type,
                        "target": target,
                        "decision": decision,
                        "previous_value": _normalize(raw.get("previous_value", "")),
                        "new_value": _normalize(raw.get("new_value", "")),
                        "source_action": _source(raw.get("source_action", "user")),
                        "timestamp": str(raw.get("timestamp", "") or ""),
                        "context": dict(raw.get("context", {}) or {}),
                    }
                )

        self._recompute_profile()


def _signal_specs_for_event(event: dict[str, Any]) -> list[tuple[str, str, str]]:
    event_type = _normalize(event.get("event_type", ""))
    target = _normalize(event.get("target", "")) or "unknown"
    decision = _normalize(event.get("decision", "")) or _normalize(event.get("new_value", "")) or "unknown"
    context = dict(event.get("context", {}) or {})
    category = _normalize(context.get("effective_media_category", "")) or target

    if event_type == "category_correction":
        return [
            ("category_preference", target, decision),
            ("category_target_preference", target, "user_corrected_category"),
        ]

    specs = [("decision_preference", decision, decision)]

    if decision in POSITIVE_DECISIONS:
        specs.append(("positive_memory_preference", category, decision))

    if event_type == "cleanup_decision" or _is_cleanup_decision(decision, category):
        specs.append(("cleanup_preference", category, decision))

    return specs


def _photo_context(photo) -> dict[str, str | int | float | bool]:
    metadata = dict(getattr(photo, "metadata", {}) or {})
    effective = _normalize(
        metadata.get("effective_media_category", "")
        or getattr(photo, "effective_media_category", "")
        or getattr(photo, "media_category", "")
        or "unknown"
    )
    automatic = _normalize(
        metadata.get("automatic_media_category", "")
        or getattr(photo, "automatic_media_category", "")
        or "unknown"
    )
    user_corrected = _normalize(
        metadata.get("user_corrected_media_category", "")
        or getattr(photo, "user_corrected_media_category", "")
        or ""
    )
    return {
        "effective_media_category": effective or "unknown",
        "automatic_media_category": automatic or "unknown",
        "user_corrected_media_category": user_corrected,
        "classification_confidence": _to_float(metadata.get("classification_confidence", getattr(photo, "classification_confidence", 0.0))),
        "is_cleanup_category": bool(get_category_registry().is_cleanup_category(effective)),
        "is_album_candidate_category": bool(get_category_registry().is_album_candidate_category(effective)),
    }


def _event_target_for_photo(photo, fallback: str) -> str:
    context = _photo_context(photo)
    return _normalize(context.get("effective_media_category", "")) or _normalize(fallback) or "unknown"


def _is_cleanup_decision(decision: str, category: str) -> bool:
    normalized_decision = _normalize(decision)
    normalized_category = _normalize(category)
    if normalized_decision in CLEANUP_DECISIONS:
        return True
    return bool(normalized_category and get_category_registry().is_cleanup_category(normalized_category))


def _signal_explanation(
    signal_type: str,
    target: str,
    decision: str,
    support_count: int,
    source_action: str,
) -> str:
    target_label = get_category_registry().label_for(target)
    decision_text = decision.replace("_", " ")
    source_text = source_action.replace("_", " ")

    if signal_type == "category_preference":
        return f"User corrected media to {target_label} {support_count} time(s) from {source_text} actions."
    if signal_type == "category_target_preference":
        return f"User category corrections repeatedly selected {target_label} as the authoritative category."
    if signal_type == "positive_memory_preference":
        return f"User made {support_count} positive memory decision(s) for {target_label} using {decision_text}."
    if signal_type == "cleanup_preference":
        return f"User made {support_count} cleanup-oriented decision(s) for {target_label} using {decision_text}."
    return f"User made {support_count} decision(s) of {decision_text} from {source_text} actions."


def _signal_id(signal_type: str, target: str, decision: str, source_action: str) -> str:
    signature = f"{signal_type}|{target}|{decision}|{source_action}"
    digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:12]
    return f"pref_{digest}"


def _latest_timestamp(events: list[dict[str, Any]]) -> str:
    timestamps = [str(event.get("timestamp", "") or "") for event in events if event.get("timestamp")]
    return max(timestamps) if timestamps else ""


def _first_timestamp(timestamps: list[str]) -> str:
    values = [str(item or "").strip() for item in timestamps if str(item or "").strip()]
    return min(values) if values else ""


def _latest_timestamp_values(timestamps: list[str]) -> str:
    values = [str(item or "").strip() for item in timestamps if str(item or "").strip()]
    return max(values) if values else ""


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _source(value: Any) -> str:
    return _normalize(value) or "user"


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_default_engine: Optional[PreferenceLearningEngine] = None


def get_preference_learning_engine(
    storage_root: Optional[str | Path] = None,
    force_reload: bool = False,
) -> PreferenceLearningEngine:
    global _default_engine
    if force_reload or _default_engine is None:
        _default_engine = PreferenceLearningEngine(storage_root=storage_root)
    return _default_engine


def reset_preference_learning_engine() -> None:
    global _default_engine
    _default_engine = None

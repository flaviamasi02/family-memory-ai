from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core.category_registry import get_category_registry
from models.visual_feature_profile import VisualFeatureProfile


@dataclass
class CategoryLearningEvent:
    file_path: str
    previous_category: str
    corrected_category: str
    source: str
    timestamp: str
    extracted_signals: dict[str, str | int | float | bool]


@dataclass
class CategoryLearningRule:
    id: str
    target_category: str
    conditions: dict[str, str | int | float | bool]
    confidence_boost: float
    support_count: int
    explanation: str
    first_learned_at: str = ""
    last_learned_at: str = ""


@dataclass
class CategoryLearningProfile:
    rules: list[CategoryLearningRule] = field(default_factory=list)
    total_events: int = 0
    category_event_counts: dict[str, int] = field(default_factory=dict)


_BOOL_SIGNAL_KEYS = [
    "contains_whatsapp",
    "contains_screenshot",
    "contains_download",
    "contains_forwarded",
    "contains_giphy",
    "contains_tenor",
    "contains_meme",
    "contains_buongiorno",
    "contains_auguri",
    "is_small_image",
    "is_square",
    "is_very_wide",
    "is_very_tall",
    "has_camera_metadata",
    "has_exif_date",
    "has_gps",
]

_STRING_SIGNAL_KEYS = [
    "extension",
    "file_size_bucket",
    "date_source",
]


class CategoryLearningEngine:
    def __init__(self, storage_root: Optional[str | Path] = None):
        root = Path(storage_root or os.environ.get("FAMILY_MEMORY_LEARNING_ROOT") or Path.cwd())
        self._storage_path = root / ".familymemory" / "category_learning_profile.json"
        self._events: list[CategoryLearningEvent] = []
        self._event_summaries: list[dict[str, Any]] = []
        self.profile = CategoryLearningProfile()
        self._load_profile()

    @property
    def storage_path(self) -> Path:
        return self._storage_path

    def extract_signals(
        self,
        file_path: str | Path,
        metadata: Optional[dict[str, Any]] = None,
        visual_profile: Optional[VisualFeatureProfile | dict[str, Any]] = None,
    ) -> dict[str, str | int | float | bool]:
        path = Path(file_path)
        metadata_dict = dict(metadata or {})
        filename_lower = path.name.lower()

        width = _to_int(metadata_dict.get("width"))
        height = _to_int(metadata_dict.get("height"))
        area = (width * height) if isinstance(width, int) and isinstance(height, int) else 0
        aspect_ratio = (
            float(width / height)
            if isinstance(width, int) and isinstance(height, int) and height > 0
            else 0.0
        )

        has_camera = bool(
            str(metadata_dict.get("camera_make", "") or "").strip()
            or str(metadata_dict.get("camera_model", "") or "").strip()
        )
        date_taken = str(metadata_dict.get("date_taken", "") or "").strip()
        has_exif_date = bool(date_taken)
        has_gps = bool(metadata_dict.get("has_gps", False))
        date_source = (
            str(
                metadata_dict.get("date_source", "")
                or metadata_dict.get("source_of_date", "")
                or "unknown"
            )
            .strip()
            or "unknown"
        )

        file_size = _to_int(metadata_dict.get("file_size"))
        if file_size is None and path.exists() and path.is_file():
            try:
                file_size = int(path.stat().st_size)
            except Exception:
                file_size = 0

        profile = _visual_profile_from_inputs(metadata_dict, visual_profile)

        signals: dict[str, str | int | float | bool] = {
            "contains_whatsapp": "whatsapp" in filename_lower or "-wa" in filename_lower,
            "contains_screenshot": "screenshot" in filename_lower or "schermata" in filename_lower,
            "contains_download": "download" in filename_lower,
            "contains_forwarded": "forwarded" in filename_lower,
            "contains_giphy": "giphy" in filename_lower,
            "contains_tenor": "tenor" in filename_lower,
            "contains_meme": "meme" in filename_lower,
            "contains_buongiorno": "buongiorno" in filename_lower,
            "contains_auguri": "auguri" in filename_lower,
            "width": int(width or 0),
            "height": int(height or 0),
            "aspect_ratio": round(float(aspect_ratio), 4),
            "is_small_image": bool(area > 0 and area <= 800 * 800),
            "is_square": bool(isinstance(width, int) and isinstance(height, int) and abs(width - height) <= 20),
            "is_very_wide": bool(
                isinstance(width, int)
                and isinstance(height, int)
                and height > 0
                and (width / height) >= 2.5
            ),
            "is_very_tall": bool(
                isinstance(width, int)
                and isinstance(height, int)
                and width > 0
                and (height / width) >= 2.5
            ),
            "has_camera_metadata": has_camera,
            "has_exif_date": has_exif_date,
            "has_gps": has_gps,
            "date_source": date_source.lower(),
            "extension": path.suffix.lower(),
            "file_size_bucket": _size_bucket(int(file_size or 0)),
        }
        signals.update(_visual_profile_signals(profile))
        return signals

    def record_category_correction(
        self,
        photo,
        previous_category: str,
        corrected_category: str,
        source: str,
    ) -> CategoryLearningEvent:
        metadata = dict(getattr(photo, "metadata", {}) or {})
        if "file_size" not in metadata:
            metadata["file_size"] = int(getattr(photo, "file_size", 0) or 0)

        signals = self.extract_signals(getattr(photo, "path", ""), metadata, getattr(photo, "visual_features", None))
        event = CategoryLearningEvent(
            file_path=str(getattr(photo, "path", "")),
            previous_category=str(previous_category or "").strip().lower(),
            corrected_category=str(corrected_category or "").strip().lower(),
            source=str(source or "user").strip() or "user",
            timestamp=_now_iso(),
            extracted_signals=signals,
        )

        self._events.append(event)
        self._event_summaries.append(
            {
                "corrected_category": event.corrected_category,
                "source": event.source,
                "timestamp": event.timestamp,
                "signals": dict(event.extracted_signals),
            }
        )

        self._recompute_profile()
        self._save_profile()
        return event

    def apply_learning(
        self,
        file_path: str | Path,
        metadata: Optional[dict[str, Any]],
        base_category: str,
        base_confidence: float,
        base_reason: str,
    ) -> tuple[str, float, str, Optional[CategoryLearningRule]]:
        if not self.profile.rules:
            return base_category, base_confidence, base_reason, None

        signals = self.extract_signals(file_path, metadata)
        matches: list[tuple[float, CategoryLearningRule]] = []

        for rule in self.profile.rules:
            if _matches_rule(rule, signals):
                # Prefer rules with stronger support and more specific conditions.
                score = (
                    float(rule.confidence_boost)
                    + min(0.50, float(rule.support_count) / 100.0)
                    + min(0.10, len(rule.conditions) * 0.01)
                )
                matches.append((score, rule))

        if not matches:
            return base_category, base_confidence, base_reason, None

        matches.sort(key=lambda item: item[0], reverse=True)
        best_rule = matches[0][1]

        learned_category = best_rule.target_category
        learned_conf = max(
            float(base_confidence),
            min(0.99, float(base_confidence) + float(best_rule.confidence_boost)),
        )
        category_label = get_category_registry().label_for(learned_category)
        learned_reason = (
            f"Classified as {category_label} because this matches a learned user rule: "
            f"{best_rule.explanation}"
        )

        if str(learned_category).strip().lower() == str(base_category).strip().lower():
            learned_reason = f"{base_reason} Learned user rule reinforcement: {best_rule.explanation}"

        return learned_category, learned_conf, learned_reason, best_rule

    def learning_summary(self) -> dict[str, Any]:
        return {
            "total_events": int(self.profile.total_events),
            "category_event_counts": dict(self.profile.category_event_counts),
            "rules": [asdict(rule) for rule in self.profile.rules],
            "event_summaries": list(self._event_summaries),
        }

    def _recompute_profile(self) -> None:
        counts: dict[str, int] = {}
        grouped_signatures: dict[tuple[str, tuple[tuple[str, Any], ...]], int] = {}
        grouped_timestamps: dict[tuple[str, tuple[tuple[str, Any], ...]], list[str]] = {}

        for summary in self._event_summaries:
            category = str(summary.get("corrected_category", "") or "").strip().lower()
            if not category:
                continue

            counts[category] = counts.get(category, 0) + 1
            signals = dict(summary.get("signals", {}) or {})
            timestamp = str(summary.get("timestamp", "") or "").strip()

            # Important improvement:
            # Previously the engine created rules only when many images shared
            # the exact same large condition set. That was too rigid.
            # Now we generate several smaller, explainable candidate rule sets.
            # This lets the app learn practical patterns like:
            # "WhatsApp + small image + no camera metadata => Meme"
            # even when the images have different sizes or filenames.
            for conditions in _candidate_rule_condition_sets(signals):
                if len(conditions) < 1:
                    continue
                signature = (category, tuple(sorted(conditions.items())))
                grouped_signatures[signature] = grouped_signatures.get(signature, 0) + 1
                if timestamp:
                    grouped_timestamps.setdefault(signature, []).append(timestamp)

        rules: list[CategoryLearningRule] = []
        registry = get_category_registry()

        for (target_category, condition_items), support_count in grouped_signatures.items():
            category_def = registry.get(target_category)
            min_support = 3 if category_def is not None and category_def.type == "user" else 5

            if support_count < min_support:
                continue

            conditions = dict(condition_items)
            specificity_bonus = min(0.10, len(conditions) * 0.015)
            confidence_boost = min(
                0.50,
                0.22 + specificity_bonus + max(0, support_count - min_support) * 0.02,
            )

            rule = CategoryLearningRule(
                id=_rule_id(target_category, conditions),
                target_category=target_category,
                conditions=conditions,
                confidence_boost=round(float(confidence_boost), 3),
                support_count=int(support_count),
                explanation=_rule_explanation(target_category, conditions),
                first_learned_at=_first_timestamp(grouped_timestamps.get((target_category, condition_items), [])),
                last_learned_at=_latest_timestamp(grouped_timestamps.get((target_category, condition_items), [])),
            )
            rules.append(rule)

        # Remove duplicate rule IDs, keeping the strongest rule.
        deduped: dict[str, CategoryLearningRule] = {}
        for rule in rules:
            existing = deduped.get(rule.id)
            if existing is None:
                deduped[rule.id] = rule
                continue
            if (rule.support_count, rule.confidence_boost, len(rule.conditions)) > (
                existing.support_count,
                existing.confidence_boost,
                len(existing.conditions),
            ):
                deduped[rule.id] = rule

        final_rules = list(deduped.values())
        final_rules.sort(
            key=lambda item: (item.support_count, item.confidence_boost, len(item.conditions)),
            reverse=True,
        )

        self.profile = CategoryLearningProfile(
            rules=final_rules,
            total_events=len(self._event_summaries),
            category_event_counts=counts,
        )

    def _save_profile(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "total_events": self.profile.total_events,
            "category_event_counts": self.profile.category_event_counts,
            "rules": [asdict(rule) for rule in self.profile.rules],
            "event_summaries": self._event_summaries,
            "updated_at": _now_iso(),
        }
        self._storage_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    def _load_profile(self) -> None:
        if not self._storage_path.exists():
            return

        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except Exception:
            return

        raw_summaries = payload.get("event_summaries", []) if isinstance(payload, dict) else []
        if isinstance(raw_summaries, list):
            for raw in raw_summaries:
                if not isinstance(raw, dict):
                    continue

                category = str(raw.get("corrected_category", "") or "").strip().lower()
                signals = dict(raw.get("signals", {}) or {})
                source = str(raw.get("source", "user") or "user")
                timestamp = str(raw.get("timestamp", "") or "")

                if not category or not signals:
                    continue

                self._event_summaries.append(
                    {
                        "corrected_category": category,
                        "source": source,
                        "timestamp": timestamp,
                        "signals": signals,
                    }
                )

        self._recompute_profile()


def _candidate_rule_condition_sets(signals: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def add(condition: dict[str, Any]) -> None:
        cleaned = {k: v for k, v in condition.items() if v not in (None, "", False)}
        if len(cleaned) >= 1 and cleaned not in candidates:
            candidates.append(cleaned)

    visual_bool_keys = [
        "visual_has_faces",
        "visual_has_text_like_regions",
        "visual_looks_like_document",
        "visual_looks_like_screenshot",
        "visual_looks_like_graphic_or_meme",
    ]
    active = [key for key in visual_bool_keys if signals.get(key) is True]
    for key in active:
        add({key: True})

    tags = str(signals.get("visual_tags", "") or "")
    for tag in [item.strip() for item in tags.split(",") if item.strip()]:
        add({"visual_tag": tag})

    orientation = str(signals.get("visual_orientation", "") or "").strip()
    for key in active:
        if orientation and orientation != "unknown":
            add({key: True, "visual_orientation": orientation})

    if len(active) >= 2:
        add({key: True for key in active[:3]})

    return candidates


def _visual_profile_from_inputs(metadata: dict[str, Any], visual_profile: Optional[VisualFeatureProfile | dict[str, Any]]) -> VisualFeatureProfile:
    if isinstance(visual_profile, VisualFeatureProfile):
        return visual_profile
    if isinstance(visual_profile, dict):
        return VisualFeatureProfile.from_dict(visual_profile)
    return VisualFeatureProfile.from_dict(metadata.get("visual_feature_profile"))


def _visual_profile_signals(profile: VisualFeatureProfile) -> dict[str, str | int | float | bool]:
    if profile.extraction_status in {"missing", "corrupted", "unavailable", "failed", "timeout"} and not profile.has_content_evidence():
        return {"visual_features_available": False}
    return {
        "visual_features_available": True,
        "visual_has_faces": bool(profile.has_faces),
        "visual_face_count": int(profile.face_count),
        "visual_has_text_like_regions": bool(profile.has_text_like_regions),
        "visual_looks_like_document": bool(profile.looks_like_document),
        "visual_looks_like_screenshot": bool(profile.looks_like_screenshot),
        "visual_looks_like_graphic_or_meme": bool(profile.looks_like_graphic_or_meme),
        "visual_orientation": str(profile.dominant_orientation or "unknown"),
        "visual_tags": ",".join(sorted(set(profile.visual_tags))),
    }

def _matches_rule(rule: CategoryLearningRule, signals: dict[str, Any]) -> bool:
    for key, value in (rule.conditions or {}).items():
        if signals.get(key) != value:
            return False
    return True


def _build_rule_conditions(signals: dict[str, Any]) -> dict[str, Any]:
    conditions: dict[str, Any] = {}

    for key in _BOOL_SIGNAL_KEYS:
        if key not in signals:
            continue

        value = bool(signals.get(key))

        # Negative metadata evidence is important and explainable.
        if key in {"has_camera_metadata", "has_exif_date", "has_gps"}:
            conditions[key] = value
        elif value:
            conditions[key] = True

    for key in _STRING_SIGNAL_KEYS:
        value = str(signals.get(key, "") or "").strip().lower()
        if value:
            conditions[key] = value

    return conditions


def _rule_id(target_category: str, conditions: dict[str, Any]) -> str:
    signature = "|".join(f"{key}={conditions[key]}" for key in sorted(conditions.keys()))
    compact = str(abs(hash((target_category, signature))))
    return f"rule_{target_category}_{compact[:12]}"


def _rule_explanation(target_category: str, conditions: dict[str, Any]) -> str:
    phrases: list[str] = []

    if conditions.get("visual_has_faces") is True:
        phrases.append("detected faces")
    if conditions.get("visual_has_text_like_regions") is True:
        phrases.append("text-like visual regions")
    if conditions.get("visual_looks_like_document") is True:
        phrases.append("document-like visual evidence")
    if conditions.get("visual_looks_like_screenshot") is True:
        phrases.append("screenshot-like visual evidence")
    if conditions.get("visual_looks_like_graphic_or_meme") is True:
        phrases.append("graphic/meme-like visual evidence")
    if conditions.get("visual_tag"):
        phrases.append(f"visual tag: {conditions.get('visual_tag')}")
    if conditions.get("contains_whatsapp") is True:
        phrases.append("WhatsApp-like filename")
    if conditions.get("contains_screenshot") is True:
        phrases.append("screenshot-like filename")
    if conditions.get("contains_download") is True:
        phrases.append("download/shared filename")
    if conditions.get("contains_forwarded") is True:
        phrases.append("forwarded filename")
    if conditions.get("contains_giphy") is True or conditions.get("contains_tenor") is True:
        phrases.append("GIF platform marker")
    if conditions.get("contains_meme") is True:
        phrases.append("meme keyword")
    if conditions.get("contains_buongiorno") is True:
        phrases.append("buongiorno keyword")
    if conditions.get("contains_auguri") is True:
        phrases.append("auguri keyword")
    if conditions.get("is_small_image") is True:
        phrases.append("small image")
    if conditions.get("is_square") is True:
        phrases.append("square geometry")
    if conditions.get("is_very_wide") is True:
        phrases.append("very wide geometry")
    if conditions.get("is_very_tall") is True:
        phrases.append("very tall geometry")

    if conditions.get("has_camera_metadata") is False:
        phrases.append("without camera metadata")
    elif conditions.get("has_camera_metadata") is True:
        phrases.append("with camera metadata")

    if conditions.get("has_exif_date") is False:
        phrases.append("without EXIF date")
    elif conditions.get("has_exif_date") is True:
        phrases.append("with EXIF date")

    date_source = conditions.get("date_source")
    if date_source:
        phrases.append(f"date source {date_source}")

    extension = conditions.get("extension")
    if extension:
        phrases.append(f"extension {extension}")

    bucket = conditions.get("file_size_bucket")
    if bucket:
        phrases.append(f"{bucket} file size")

    if not phrases:
        phrases = ["repeated user-corrected pattern"]

    category_label = get_category_registry().label_for(target_category)
    return f"User often marks media with {'; '.join(phrases)} as {category_label}."


def _size_bucket(file_size: int) -> str:
    size = int(file_size or 0)
    if size <= 0:
        return "unknown"
    if size < 200 * 1024:
        return "tiny"
    if size < 1024 * 1024:
        return "small"
    if size < 5 * 1024 * 1024:
        return "medium"
    return "large"


def _to_int(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)

    try:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except Exception:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _first_timestamp(timestamps: list[str]) -> str:
    values = [str(item or "").strip() for item in timestamps if str(item or "").strip()]
    return min(values) if values else ""


def _latest_timestamp(timestamps: list[str]) -> str:
    values = [str(item or "").strip() for item in timestamps if str(item or "").strip()]
    return max(values) if values else ""


_default_engine: Optional[CategoryLearningEngine] = None


def get_category_learning_engine(
    storage_root: Optional[str | Path] = None,
    force_reload: bool = False,
) -> CategoryLearningEngine:
    global _default_engine
    if force_reload or _default_engine is None:
        _default_engine = CategoryLearningEngine(storage_root=storage_root)
    return _default_engine


def reset_category_learning_engine() -> None:
    global _default_engine
    _default_engine = None

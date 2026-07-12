from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core.category_registry import get_category_registry
from core.user_metadata_service import UserMetadataService
from models.visual_feature_profile import VisualFeatureProfile

SCHEMA_VERSION = 2
MIN_VISUAL_SUPPORT = 3
MIN_SIGNAL_CONFIDENCE = 0.60
MIN_RECOMMENDATION_CONFIDENCE = 0.62
CONTENT_CATEGORY_IDS = {
    "family_photo", "personal_photo", "screenshot", "document", "receipt", "invoice",
    "advertisement", "meme", "graphic", "family_photo_candidate", "document_or_scan", "meme_or_graphic",
}
WORKFLOW_CATEGORY_IDS = {"duplicate_candidate", "low_quality", "low_quality_photo", "unknown", "video"}


@dataclass
class CategoryLearningEvent:
    file_path: str
    previous_category: str
    corrected_category: str
    source: str
    timestamp: str
    extracted_signals: dict[str, str | int | float | bool]
    event_id: str = ""
    visual_status: str = "missing"


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
    rule_type: str = "visual_content"


@dataclass
class CategoryVisualProfile:
    category_id: str
    corrected_examples: int = 0
    visual_examples: int = 0
    aggregate_features: dict[str, float] = field(default_factory=dict)
    feature_support_counts: dict[str, int] = field(default_factory=dict)
    confidence: float = 0.0
    strength: float = 0.0
    first_learned_at: str = ""
    last_updated_at: str = ""
    explanation_summaries: list[str] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION


@dataclass
class CategoryLearningProfile:
    rules: list[CategoryLearningRule] = field(default_factory=list)
    total_events: int = 0
    category_event_counts: dict[str, int] = field(default_factory=dict)
    visual_profiles: dict[str, CategoryVisualProfile] = field(default_factory=dict)
    pending_visual_analyses: dict[str, dict[str, Any]] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


class CategoryLearningEngine:
    def __init__(self, storage_root: Optional[str | Path] = None):
        root = Path(storage_root or os.environ.get("FAMILY_MEMORY_LEARNING_ROOT") or Path.cwd())
        self._storage_root = root
        self._storage_path = root / ".familymemory" / "category_learning_profile.json"
        self._event_summaries: list[dict[str, Any]] = []
        self._learned_event_ids: set[str] = set()
        self.profile = CategoryLearningProfile()
        self.diagnostics = {"corrections_received": 0, "visual_profiles_reused": 0, "visual_profiles_queued": 0, "visual_profiles_completed": 0, "category_profiles_updated": 0, "recommendations_with_visual_match": 0, "recommendations_unknown": 0, "visual_analysis_workers_started": 0, "visual_analysis_workers_finished": 0}
        self._visual_analysis_thread: threading.Thread | None = None
        self._visual_analysis_lock = threading.Lock()
        self._load_profile()

    @property
    def storage_path(self) -> Path: return self._storage_path

    def extract_signals(self, file_path: str | Path, metadata: Optional[dict[str, Any]] = None, visual_profile: Optional[VisualFeatureProfile | dict[str, Any]] = None) -> dict[str, str | int | float | bool]:
        path = Path(file_path); metadata_dict = dict(metadata or {}); filename_lower = path.name.lower()
        width = _to_int(metadata_dict.get("width")); height = _to_int(metadata_dict.get("height"))
        area = (width * height) if isinstance(width, int) and isinstance(height, int) else 0
        aspect_ratio = float(width / height) if isinstance(width, int) and isinstance(height, int) and height > 0 else 0.0
        has_camera = bool(str(metadata_dict.get("camera_make", "") or "").strip() or str(metadata_dict.get("camera_model", "") or "").strip())
        file_size = _to_int(metadata_dict.get("file_size")) or 0
        profile = _visual_profile_from_inputs(metadata_dict, visual_profile)
        signals: dict[str, str | int | float | bool] = {
            "contains_whatsapp": "whatsapp" in filename_lower or "-wa" in filename_lower,
            "contains_screenshot": "screenshot" in filename_lower or "schermata" in filename_lower,
            "contains_download": "download" in filename_lower,
            "contains_forwarded": "forwarded" in filename_lower,
            "contains_giphy": "giphy" in filename_lower,
            "contains_tenor": "tenor" in filename_lower,
            "contains_meme": "meme" in filename_lower,
            "width": int(width or 0), "height": int(height or 0), "aspect_ratio": round(aspect_ratio, 4),
            "is_small_image": bool(area > 0 and area <= 800 * 800),
            "is_square": bool(isinstance(width, int) and isinstance(height, int) and abs(width - height) <= 20),
            "has_camera_metadata": has_camera,
            "extension": path.suffix.lower(), "file_size_bucket": _size_bucket(file_size),
        }
        signals.update(_visual_profile_signals(profile)); return signals

    def record_category_correction(self, photo, previous_category: str, corrected_category: str, source: str) -> CategoryLearningEvent:
        self.diagnostics["corrections_received"] += 1
        category = _normalize(corrected_category) or "unknown"; previous = _normalize(previous_category) or "unknown"
        metadata = dict(getattr(photo, "metadata", {}) or {})
        visual = _visual_profile_from_inputs(metadata, getattr(photo, "visual_features", None))
        event_id = _event_id(str(getattr(photo, "path", "")), previous, category, source)
        signals = self.extract_signals(getattr(photo, "path", ""), metadata, visual)
        event = CategoryLearningEvent(str(getattr(photo, "path", "")), previous, category, str(source or "user"), _now_iso(), signals, event_id, visual.extraction_status)
        if event_id in self._learned_event_ids:
            return event
        self._learned_event_ids.add(event_id)
        summary = {"event_id": event_id, "file_path": event.file_path, "corrected_category": category, "previous_category": previous, "source": event.source, "timestamp": event.timestamp, "signals": signals, "visual_status": visual.extraction_status}
        self._event_summaries.append(summary)
        if _is_content_category(category) and visual.has_content_evidence() and signals.get("visual_features_available") is True:
            self.diagnostics["visual_profiles_reused"] += 1
        elif _is_content_category(category):
            self.profile.pending_visual_analyses[event_id] = {"event_id": event_id, "file_path": event.file_path, "category_id": category, "previous_category": previous, "source": event.source, "timestamp": event.timestamp}
            self.diagnostics["visual_profiles_queued"] += 1
        self._recompute_profile(); self._save_profile(); return event

    def record_completed_visual_analysis(self, event_id: str, visual_profile: VisualFeatureProfile | dict[str, Any]) -> bool:
        pending = self.profile.pending_visual_analyses.pop(str(event_id), None)
        if not pending: return False
        profile = VisualFeatureProfile.from_dict(visual_profile) if isinstance(visual_profile, dict) else visual_profile
        if not profile.has_content_evidence():
            self._save_profile(); return False
        signals = self.extract_signals(pending.get("file_path", ""), {}, profile)
        self._event_summaries.append({"event_id": f"{event_id}:visual", "file_path": pending.get("file_path", ""), "corrected_category": pending.get("category_id", ""), "previous_category": pending.get("previous_category", ""), "source": "visual_analysis_completed", "timestamp": _now_iso(), "signals": signals, "visual_status": profile.extraction_status})
        self.diagnostics["visual_profiles_completed"] += 1
        self._recompute_profile(); self._save_profile(); return True

    def process_pending_visual_analyses(self, limit: int = 10, extractor: Any | None = None) -> int:
        if extractor is None:
            from core.visual_feature_extraction_service import VisualFeatureExtractionService
            service = VisualFeatureExtractionService()
        else:
            service = extractor
        done = 0
        for event_id, pending in list(self.profile.pending_visual_analyses.items())[: max(0, int(limit))]:
            path = pending.get("file_path", "")
            profile = service.extract(path)
            if profile.extraction_status == "extracted":
                try:
                    from models.photo import Photo
                    photo = Photo.from_path(Path(path)); service.apply_profile_to_photo(photo, profile); UserMetadataService().save_for_photo(photo)
                except Exception: pass
            if self.record_completed_visual_analysis(event_id, profile): done += 1
        return done

    def start_pending_visual_analysis_worker(self, limit: int = 10, extractor: Any | None = None) -> bool:
        """Start one bounded background pass over queued visual analyses.

        Returns True when this call started a worker and False when there was
        nothing to process or another worker is already active.
        """
        if not self.profile.pending_visual_analyses:
            return False
        with self._visual_analysis_lock:
            if self._visual_analysis_thread is not None and self._visual_analysis_thread.is_alive():
                return False

            def _run() -> None:
                try:
                    while self.profile.pending_visual_analyses:
                        pending_before = len(self.profile.pending_visual_analyses)
                        processed = self.process_pending_visual_analyses(limit=limit, extractor=extractor)
                        pending_after = len(self.profile.pending_visual_analyses)
                        if processed <= 0 and pending_after >= pending_before:
                            break
                finally:
                    self.diagnostics["visual_analysis_workers_finished"] += 1
                    with self._visual_analysis_lock:
                        self._visual_analysis_thread = None

            self.diagnostics["visual_analysis_workers_started"] += 1
            self._visual_analysis_thread = threading.Thread(target=_run, name="ContentLearningVisualAnalysis", daemon=True)
            self._visual_analysis_thread.start()
            return True

    def wait_for_pending_visual_analysis(self, timeout: float | None = None) -> bool:
        thread = self._visual_analysis_thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    def apply_learning(self, file_path: str | Path, metadata: Optional[dict[str, Any]], base_category: str, base_confidence: float, base_reason: str, visual_profile: Optional[VisualFeatureProfile | dict[str, Any]] = None) -> tuple[str, float, str, Optional[CategoryLearningRule]]:
        signals = self.extract_signals(file_path, metadata, visual_profile)
        best: tuple[float, CategoryLearningRule, list[str]] | None = None
        for rule in self.profile.rules:
            matched = _matched_visual_conditions(rule, signals)
            if matched and rule.support_count >= MIN_VISUAL_SUPPORT:
                score = rule.confidence_boost + min(.25, rule.support_count / 80.0)
                if best is None or score > best[0]: best = (score, rule, matched)
        if best is None:
            if _normalize(base_category) == "unknown": self.diagnostics["recommendations_unknown"] += 1
            return base_category, base_confidence, base_reason, None
        _, rule, matched = best; label = get_category_registry().label_for(rule.target_category)
        conf = min(.88, max(float(base_confidence), .50) + float(rule.confidence_boost))
        if conf < MIN_RECOMMENDATION_CONFIDENCE: return base_category, base_confidence, base_reason, None
        self.diagnostics["recommendations_with_visual_match"] += 1
        reason = f"{base_reason} Learned visual content also supports {label}: matched {', '.join(matched)} from {rule.support_count} corrected examples."
        return rule.target_category, conf, reason, rule

    def learning_summary(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "total_events": self.profile.total_events, "category_event_counts": dict(self.profile.category_event_counts), "rules": [asdict(r) for r in self.profile.rules], "visual_profiles": {k: asdict(v) for k, v in self.profile.visual_profiles.items()}, "pending_visual_analyses": len(self.profile.pending_visual_analyses), "event_summaries": list(self._event_summaries), "diagnostics": dict(self.diagnostics)}

    def _recompute_profile(self) -> None:
        counts: dict[str, int] = {}; visual_events: dict[str, list[dict[str, Any]]] = {}; first: dict[str, str] = {}; last: dict[str, str] = {}
        for e in self._event_summaries:
            cat = _normalize(e.get("corrected_category", ""));
            if not cat: continue
            counts[cat] = counts.get(cat, 0) + 1; ts = str(e.get("timestamp", "") or "")
            if ts: first[cat] = min(first.get(cat, ts), ts); last[cat] = max(last.get(cat, ts), ts)
            if _is_content_category(cat) and dict(e.get("signals", {})).get("visual_features_available") is True:
                visual_events.setdefault(cat, []).append(e)
        profiles: dict[str, CategoryVisualProfile] = {}
        rules: list[CategoryLearningRule] = []
        for cat, events in visual_events.items():
            support: dict[str, int] = {}; totals: dict[str, float] = {}
            for e in events:
                for key, label in _visual_signal_labels(dict(e.get("signals", {}))).items():
                    support[label] = support.get(label, 0) + 1; totals[label] = totals.get(label, 0.0) + 1.0
            strong = [label for label, n in sorted(support.items(), key=lambda x: (-x[1], x[0])) if n >= MIN_VISUAL_SUPPORT and n / max(1, len(events)) >= MIN_SIGNAL_CONFIDENCE]
            confidence = round(min(.95, (len(events) / max(MIN_VISUAL_SUPPORT, counts.get(cat, 1))) * (len(strong) / max(1, len(support))) if support else 0.0), 3)
            profiles[cat] = CategoryVisualProfile(cat, counts.get(cat, 0), len(events), {k: round(v / max(1, len(events)), 3) for k, v in totals.items()}, support, confidence, confidence, first.get(cat, ""), last.get(cat, ""), strong[:8])
            for label in strong:
                condition = _condition_for_label(label)
                if condition:
                    rules.append(CategoryLearningRule(_rule_id(cat, condition), cat, condition, round(min(.30, .12 + support[label] * .025), 3), support[label], f"User corrections taught a visual-content rule: {label}.", first.get(cat, ""), last.get(cat, "")))
        self.profile = CategoryLearningProfile(rules, len(self._event_summaries), counts, profiles, dict(self.profile.pending_visual_analyses), SCHEMA_VERSION)
        self.diagnostics["category_profiles_updated"] = len(profiles)

    def _save_profile(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.learning_summary()
        payload["pending_visual_analyses"] = dict(self.profile.pending_visual_analyses)
        payload["learned_event_ids"] = sorted(self._learned_event_ids)
        payload["updated_at"] = _now_iso()
        fd, tmp = tempfile.mkstemp(prefix=self._storage_path.name, dir=str(self._storage_path.parent)); os.close(fd)
        Path(tmp).write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8"); os.replace(tmp, self._storage_path)

    def _load_profile(self) -> None:
        if not self._storage_path.exists(): return
        try: payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except Exception: return
        if not isinstance(payload, dict): return
        self._learned_event_ids = {str(x) for x in payload.get("learned_event_ids", []) if str(x)}
        pending = payload.get("pending_visual_analyses", {})
        if isinstance(pending, dict):
            self.profile.pending_visual_analyses = {str(k): dict(v) for k, v in pending.items() if isinstance(v, dict)}
        raw = payload.get("event_summaries", [])
        if isinstance(raw, list):
            for e in raw:
                if isinstance(e, dict) and _normalize(e.get("corrected_category", "")):
                    self._event_summaries.append(e); eid = str(e.get("event_id", "") or "")
                    if eid and not eid.endswith(":visual"): self._learned_event_ids.add(eid)
        self._recompute_profile()


def _visual_signal_labels(signals: dict[str, Any]) -> dict[str, str]:
    out = {}
    mapping = {"visual_has_faces":"face presence", "visual_has_text_like_regions":"high text density", "visual_looks_like_document":"document-like page structure", "visual_looks_like_screenshot":"screenshot-like flat layout", "visual_looks_like_graphic_or_meme":"flat graphic structure"}
    for k, label in mapping.items():
        if signals.get(k) is True: out[k] = label
    orient = str(signals.get("visual_orientation", "") or "")
    if orient and orient != "unknown": out["visual_orientation"] = f"{orient} layout tendency"
    return out

def _condition_for_label(label: str) -> dict[str, Any]:
    reverse = {"face presence": {"visual_has_faces": True}, "high text density": {"visual_has_text_like_regions": True}, "document-like page structure": {"visual_looks_like_document": True}, "screenshot-like flat layout": {"visual_looks_like_screenshot": True}, "flat graphic structure": {"visual_looks_like_graphic_or_meme": True}}
    if label.endswith(" layout tendency"): return {"visual_orientation": label.split()[0]}
    return reverse.get(label, {})

def _matched_visual_conditions(rule: CategoryLearningRule, signals: dict[str, Any]) -> list[str]:
    labels = _visual_signal_labels(signals); matched=[]
    for k, v in rule.conditions.items():
        if signals.get(k) != v: return []
        matched.append(labels.get(k, str(k)))
    return matched

def _visual_profile_from_inputs(metadata: dict[str, Any], visual_profile: Optional[VisualFeatureProfile | dict[str, Any]]) -> VisualFeatureProfile:
    if isinstance(visual_profile, VisualFeatureProfile): return visual_profile
    if isinstance(visual_profile, dict): return VisualFeatureProfile.from_dict(visual_profile)
    return VisualFeatureProfile.from_dict(metadata.get("visual_feature_profile"))

def _visual_profile_signals(profile: VisualFeatureProfile) -> dict[str, str | int | float | bool]:
    if profile.extraction_status in {"missing", "corrupted", "unavailable", "failed", "timeout"} and not profile.has_content_evidence(): return {"visual_features_available": False}
    return {"visual_features_available": True, "visual_has_faces": bool(profile.has_faces), "visual_face_count": int(profile.face_count), "visual_has_text_like_regions": bool(profile.has_text_like_regions), "visual_looks_like_document": bool(profile.looks_like_document), "visual_looks_like_screenshot": bool(profile.looks_like_screenshot), "visual_looks_like_graphic_or_meme": bool(profile.looks_like_graphic_or_meme), "visual_orientation": str(profile.dominant_orientation or "unknown"), "visual_tags": ",".join(sorted(set(profile.visual_tags)))}

def _is_content_category(category_id: str) -> bool:
    cid = _normalize(category_id)
    if cid in WORKFLOW_CATEGORY_IDS: return False
    item = get_category_registry().get(cid)
    return bool(cid in CONTENT_CATEGORY_IDS or (item is not None and not cid.startswith("duplicate") and cid != "unknown"))

def _event_id(path: str, previous: str, category: str, source: str) -> str:
    return hashlib.sha256(f"{Path(path).as_posix()}|{previous}|{category}|{source}".encode()).hexdigest()[:24]

def _rule_id(target_category: str, conditions: dict[str, Any]) -> str:
    return "rule_" + hashlib.sha1((target_category + json.dumps(conditions, sort_keys=True)).encode()).hexdigest()[:16]

def _normalize(v: Any) -> str: return str(v or "").strip().lower()
def _now_iso() -> str: return datetime.now(timezone.utc).isoformat()
def _to_int(v: Any) -> int | None:
    try: return int(v)
    except Exception: return None
def _size_bucket(file_size: int) -> str:
    if file_size <= 0: return "unknown"
    if file_size < 200*1024: return "tiny"
    if file_size < 1024*1024: return "small"
    if file_size < 5*1024*1024: return "medium"
    return "large"

_default_engine: Optional[CategoryLearningEngine] = None
def get_category_learning_engine(storage_root: Optional[str | Path] = None, force_reload: bool = False) -> CategoryLearningEngine:
    global _default_engine
    if storage_root is not None:
        return CategoryLearningEngine(storage_root=storage_root)
    if force_reload or _default_engine is None:
        _default_engine = CategoryLearningEngine()
    return _default_engine

def reset_category_learning_engine() -> None:
    global _default_engine
    _default_engine = None

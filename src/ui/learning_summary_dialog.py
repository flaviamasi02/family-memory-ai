from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QListWidget, QVBoxLayout

from learning.category_learning_engine import CategoryLearningEngine
from learning.preference_learning_engine import PreferenceLearningEngine


class LearningSummaryDialog(QDialog):
    def __init__(self, engine: CategoryLearningEngine, parent=None, preference_engine: Optional[PreferenceLearningEngine] = None):
        super().__init__(parent)
        self.setWindowTitle("Learning Summary")
        self.resize(860, 720)
        summary = engine.learning_summary()
        preference_summary = preference_engine.learning_summary() if preference_engine is not None else {}

        visual_profiles = dict(summary.get("visual_profiles") or {})
        visual_examples = sum(int(p.get("visual_examples", 0) or 0) for p in visual_profiles.values())
        pending = int(summary.get("pending_visual_analyses", 0) or 0)

        self.total_label = QLabel(
            f"Overview: {int(summary.get('total_events', 0))} correction activity records | "
            f"{visual_examples} visual examples analyzed | {len(visual_profiles)} categories with visual profiles | "
            f"{pending} pending visual analyses"
        )
        self.total_label.setStyleSheet("font-weight: 600;")

        self.visual_label = QLabel("Category Visual Learning (content evidence from corrected images)")
        self.visual_list = QListWidget()
        if not visual_profiles:
            self.visual_list.addItem("No category visual profiles yet. Corrected images will be analyzed locally in the background when needed.")
        else:
            for category, profile in sorted(visual_profiles.items()):
                signals = list(profile.get("explanation_summaries") or [])
                signal_text = "; ".join(signals) if signals else "No strong visual signal yet."
                self.visual_list.addItem(
                    f"{category} | examples={int(profile.get('corrected_examples', 0))} | "
                    f"visual={int(profile.get('visual_examples', 0))} | confidence={float(profile.get('confidence', 0.0)):.2f} | "
                    f"updated={_format_local_timestamp(str(profile.get('last_updated_at', '') or ''))} | {signal_text}"
                )

        self.activity_label = QLabel("Activity (counts of user corrections, not visual learning by itself)")
        self.activity_list = QListWidget()
        for category, count in sorted((summary.get("category_event_counts") or {}).items()):
            self.activity_list.addItem(f"{category}: {count} correction records")
        if self.activity_list.count() == 0:
            self.activity_list.addItem("No category correction activity yet.")

        self.rules_label = QLabel("Learned Rules (visual-content rules are separate from metadata-only support)")
        self.rules_list = QListWidget()
        rules = list(summary.get("rules") or [])
        if not rules:
            self.rules_list.addItem("No learned visual-content rules yet. Unknown remains the conservative result when evidence is weak.")
        else:
            for rule in rules[:100]:
                self.rules_list.addItem(
                    f"{rule.get('rule_type', 'visual_content')} -> {rule.get('target_category', 'unknown')} | "
                    f"support={int(rule.get('support_count', 0))} | confidence boost={float(rule.get('confidence_boost', 0.0)):.2f} | "
                    f"{_learned_timestamp_text(rule)} | {rule.get('explanation', '')}"
                )

        self.preference_label = QLabel("Preference Signals (user behavior patterns, not visual-content learning)")
        self.preference_list = QListWidget()
        preference_signals = list(preference_summary.get("preference_signals") or preference_summary.get("strongest_preference_signals") or [])
        if not preference_signals:
            self.preference_list.addItem("No learned preference signals yet.")
        else:
            for signal in preference_signals[:50]:
                self.preference_list.addItem(
                    f"{signal.get('signal_type', 'preference')} -> {signal.get('target', 'unknown')} | "
                    f"support={int(signal.get('support_count', 0) or 0)} | strength={float(signal.get('strength', 0.0) or 0.0):.2f} | "
                    f"{_learned_timestamp_text(signal)} | {signal.get('explanation', '')}"
                )

        self.events_label = QLabel("Recent Learning Activity")
        self.events_list = QListWidget()
        events = list(summary.get("event_summaries") or [])[-50:]
        if not events:
            self.events_list.addItem("No category learning events yet.")
        else:
            for event in reversed(events):
                timestamp = _format_local_timestamp(str(event.get("timestamp", "") or ""))
                self.events_list.addItem(f"{timestamp} | category={event.get('corrected_category', 'unknown')} | source={event.get('source', 'user')} | visual={event.get('visual_status', 'unknown')}")

        root = QVBoxLayout(self)
        for widget, stretch in [(self.total_label,0),(self.visual_label,0),(self.visual_list,2),(self.activity_label,0),(self.activity_list,1),(self.rules_label,0),(self.rules_list,2),(self.preference_label,0),(self.preference_list,2),(self.events_label,0),(self.events_list,1)]:
            root.addWidget(widget, stretch)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)


def _learned_timestamp_text(item: dict) -> str:
    first = _format_local_timestamp(str(item.get("first_learned_at", "") or "")); last = _format_local_timestamp(str(item.get("last_learned_at", item.get("last_updated_at", "")) or ""))
    return f"learned {first}" if first == last else f"learned {first}; updated {last}"


def _format_local_timestamp(value: str) -> str:
    text = str(value or "").strip()
    if not text: return "date/time not recorded"
    try: parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception: return text
    if parsed.tzinfo is not None: parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d %H:%M")

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QListWidget, QVBoxLayout

from learning.category_learning_engine import CategoryLearningEngine
from learning.preference_learning_engine import PreferenceLearningEngine


class LearningSummaryDialog(QDialog):
    def __init__(
        self,
        engine: CategoryLearningEngine,
        parent=None,
        preference_engine: Optional[PreferenceLearningEngine] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Learning Summary")
        self.resize(760, 620)

        summary = engine.learning_summary()
        preference_summary = preference_engine.learning_summary() if preference_engine is not None else {}

        self.total_label = QLabel(f"Total corrections learned: {int(summary.get('total_events', 0))}")
        self.total_label.setStyleSheet("font-weight: 600;")

        self.counts_label = QLabel("Category correction counts")
        self.counts_list = QListWidget()
        for category, count in sorted((summary.get("category_event_counts") or {}).items()):
            self.counts_list.addItem(f"{category}: {count}")

        self.rules_label = QLabel("Learned rules")
        self.rules_list = QListWidget()
        rules = list(summary.get("rules") or [])
        if not rules:
            self.rules_list.addItem("No learned rules yet.")
        else:
            for rule in rules:
                target = str(rule.get("target_category", "unknown"))
                support = int(rule.get("support_count", 0))
                boost = float(rule.get("confidence_boost", 0.0))
                explanation = str(rule.get("explanation", "") or "")
                learned = _learned_timestamp_text(rule)
                self.rules_list.addItem(
                    f"{target} | support={support} | boost={boost:.2f} | {learned} | {explanation}"
                )

        self.events_label = QLabel("Recent category learning events")
        self.events_list = QListWidget()
        events = list(summary.get("event_summaries") or [])[-20:]
        if not events:
            self.events_list.addItem("No category learning events yet.")
        else:
            for event in reversed(events):
                timestamp = _format_local_timestamp(str(event.get("timestamp", "") or ""))
                category = str(event.get("corrected_category", "unknown") or "unknown")
                source = str(event.get("source", "user") or "user")
                self.events_list.addItem(f"{timestamp} | category={category} | source={source}")

        self.preference_label = QLabel("Learned preference signals")
        self.preference_list = QListWidget()
        preference_signals = list(
            preference_summary.get("preference_signals")
            or preference_summary.get("strongest_preference_signals")
            or []
        )
        if not preference_signals:
            self.preference_list.addItem("No learned preference signals yet.")
        else:
            for signal in preference_signals[:20]:
                signal_type = str(signal.get("signal_type", "preference") or "preference")
                target = str(signal.get("target", "unknown") or "unknown")
                support = int(signal.get("support_count", 0) or 0)
                strength = float(signal.get("strength", 0.0) or 0.0)
                explanation = str(signal.get("explanation", "") or "")
                learned = _learned_timestamp_text(signal)
                self.preference_list.addItem(
                    f"{signal_type} -> {target} | support={support} | strength={strength:.2f} | {learned} | {explanation}"
                )

        root = QVBoxLayout(self)
        root.addWidget(self.total_label)
        root.addWidget(self.counts_label)
        root.addWidget(self.counts_list, 1)
        root.addWidget(self.rules_label)
        root.addWidget(self.rules_list, 2)
        root.addWidget(self.events_label)
        root.addWidget(self.events_list, 1)
        root.addWidget(self.preference_label)
        root.addWidget(self.preference_list, 2)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)


def _learned_timestamp_text(item: dict) -> str:
    first = _format_local_timestamp(str(item.get("first_learned_at", "") or ""))
    last = _format_local_timestamp(str(item.get("last_learned_at", "") or ""))
    if first == last:
        return f"learned {first}"
    return f"learned {first}; updated {last}"


def _format_local_timestamp(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "date/time not recorded"

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return text

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d %H:%M")

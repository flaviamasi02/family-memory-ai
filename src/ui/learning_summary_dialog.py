from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QListWidget, QVBoxLayout

from learning.category_learning_engine import CategoryLearningEngine


class LearningSummaryDialog(QDialog):
    def __init__(self, engine: CategoryLearningEngine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Learning Summary")
        self.resize(620, 420)

        summary = engine.learning_summary()

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
                self.rules_list.addItem(f"{target} | support={support} | boost={boost:.2f} | {explanation}")

        root = QVBoxLayout(self)
        root.addWidget(self.total_label)
        root.addWidget(self.counts_label)
        root.addWidget(self.counts_list, 1)
        root.addWidget(self.rules_label)
        root.addWidget(self.rules_list, 2)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

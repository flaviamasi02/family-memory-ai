from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ui.help.workspace_help_models import (
    WorkspaceAIStatusMetric,
    WorkspaceHelpDefinition,
    WorkspaceHelpTip,
)


class WorkspaceHelpPanel(QWidget):
    """Reusable right-side panel that renders contextual workspace help sections."""

    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._definition: WorkspaceHelpDefinition | None = None
        self._renderers: dict[str, Callable[[QVBoxLayout, object], None]] = {
            "purpose": self._render_purpose,
            "workflow": self._render_workflow,
            "bullet_list": self._render_bullet_list,
            "tips": self._render_tips,
            "ai_status": self._render_ai_status,
            "text": self._render_text,
        }

        self.workspace_title_label = QLabel("Workspace Help")
        self.workspace_title_label.setStyleSheet("font-size: 17px; font-weight: 700;")

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close_requested.emit)

        header = QHBoxLayout()
        header.addWidget(self.workspace_title_label)
        header.addStretch(1)
        header.addWidget(self.close_button)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.scroll_content = QWidget()
        self.sections_layout = QVBoxLayout(self.scroll_content)
        self.sections_layout.setContentsMargins(0, 0, 0, 0)
        self.sections_layout.setSpacing(12)
        self.scroll_area.setWidget(self.scroll_content)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)
        root.addLayout(header)
        root.addWidget(self.scroll_area, 1)

    def set_help_definition(self, definition: WorkspaceHelpDefinition) -> None:
        self._definition = definition
        self.workspace_title_label.setText(f"{definition.title} Guide")
        self._rebuild_sections()

    def _rebuild_sections(self) -> None:
        while self.sections_layout.count():
            item = self.sections_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if self._definition is None:
            self.sections_layout.addStretch(1)
            return

        for section in self._definition.sections:
            self.sections_layout.addWidget(self._create_section_card(section.title, section.kind, section.payload, section.icon))

        self.sections_layout.addStretch(1)

    def _create_section_card(self, title: str, kind: str, payload: object, icon_name: str) -> QWidget:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #d9dce1; border-radius: 8px; }")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        section_title_row = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setFixedWidth(18)
        icon = self._icon_for_name(icon_name)
        if icon is not None:
            icon_label.setPixmap(icon.pixmap(16, 16))
        section_title = QLabel(title)
        section_title.setStyleSheet("font-size: 14px; font-weight: 600;")
        section_title_row.addWidget(icon_label)
        section_title_row.addWidget(section_title)
        section_title_row.addStretch(1)

        layout.addLayout(section_title_row)

        renderer = self._renderers.get(kind, self._render_unknown)
        renderer(layout, payload)
        return card

    def _render_purpose(self, layout: QVBoxLayout, payload: object) -> None:
        content = payload if isinstance(payload, dict) else {}
        mapping = [
            ("Why this workspace exists", "why_this_workspace_exists"),
            ("Problem it solves", "problem_it_solves"),
            ("AI automation", "ai_automation"),
            ("Your interaction", "user_interaction"),
            ("Expected outcome", "expected_outcome"),
        ]
        for label, key in mapping:
            value = str(content.get(key, "")).strip()
            if not value:
                continue
            heading = QLabel(label)
            heading.setStyleSheet("font-weight: 600; color: #2d3748;")
            body = QLabel(value)
            body.setWordWrap(True)
            body.setStyleSheet("color: #364152;")
            layout.addWidget(heading)
            layout.addWidget(body)

    def _render_workflow(self, layout: QVBoxLayout, payload: object) -> None:
        steps = [str(step).strip() for step in (payload if isinstance(payload, list) else []) if str(step).strip()]
        if not steps:
            layout.addWidget(QLabel("No workflow steps available."))
            return

        for index, step in enumerate(steps):
            step_label = QLabel(step)
            step_label.setWordWrap(True)
            step_label.setStyleSheet(
                "background: #f3f6fb; border: 1px solid #d3dce8; border-radius: 6px; padding: 6px 8px;"
            )
            layout.addWidget(step_label)
            if index < len(steps) - 1:
                arrow = QLabel("v")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                arrow.setStyleSheet("color: #5f6b7a; font-size: 13px;")
                layout.addWidget(arrow)

    def _render_bullet_list(self, layout: QVBoxLayout, payload: object) -> None:
        items = [str(item).strip() for item in (payload if isinstance(payload, list) else []) if str(item).strip()]
        if not items:
            layout.addWidget(QLabel("No guidance available."))
            return

        for item in items:
            label = QLabel(f"- {item}")
            label.setWordWrap(True)
            label.setStyleSheet("color: #364152;")
            layout.addWidget(label)

    def _render_tips(self, layout: QVBoxLayout, payload: object) -> None:
        tips = payload if isinstance(payload, list) else []
        if not tips:
            layout.addWidget(QLabel("No tips available."))
            return

        for tip in tips:
            if not isinstance(tip, WorkspaceHelpTip):
                continue
            frame = QFrame()
            frame.setStyleSheet("QFrame { background: #f6fbf6; border: 1px solid #cfe6cf; border-radius: 6px; }")
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(8, 8, 8, 8)
            frame_layout.setSpacing(4)

            title = QLabel(tip.title)
            title.setStyleSheet("font-weight: 600; color: #1f5130;")
            body = QLabel(tip.body)
            body.setWordWrap(True)
            body.setStyleSheet("color: #2a4a33;")
            frame_layout.addWidget(title)
            frame_layout.addWidget(body)
            layout.addWidget(frame)

    def _render_ai_status(self, layout: QVBoxLayout, payload: object) -> None:
        metrics = payload if isinstance(payload, list) else []
        if not metrics:
            layout.addWidget(QLabel("No AI status metrics available."))
            return

        for metric in metrics:
            if not isinstance(metric, WorkspaceAIStatusMetric):
                continue

            row = QWidget()
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)

            title_row = QHBoxLayout()
            label = QLabel(metric.label)
            value = QLabel(f"{metric.normalized_progress()}%")
            value.setStyleSheet("font-weight: 600;")
            title_row.addWidget(label)
            title_row.addStretch(1)
            title_row.addWidget(value)

            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(metric.normalized_progress())
            progress.setTextVisible(False)
            progress.setFixedHeight(9)

            row_layout.addLayout(title_row)
            row_layout.addWidget(progress)

            description = str(metric.description or "").strip()
            if description:
                desc_label = QLabel(description)
                desc_label.setWordWrap(True)
                desc_label.setStyleSheet("font-size: 11px; color: #4b5563;")
                row_layout.addWidget(desc_label)

            layout.addWidget(row)

    def _render_text(self, layout: QVBoxLayout, payload: object) -> None:
        paragraphs = payload if isinstance(payload, list) else [str(payload)]
        for paragraph in paragraphs:
            text = str(paragraph).strip()
            if not text:
                continue
            label = QLabel(text)
            label.setWordWrap(True)
            label.setStyleSheet("color: #364152;")
            layout.addWidget(label)

    def _render_unknown(self, layout: QVBoxLayout, payload: object) -> None:
        label = QLabel(str(payload))
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(label)

    def _icon_for_name(self, icon_name: str):
        icon_name = str(icon_name or "").strip().lower()
        style = self.style()
        mapping = {
            "info": QStyle.StandardPixmap.SP_MessageBoxInformation,
            "flow": QStyle.StandardPixmap.SP_ArrowForward,
            "check": QStyle.StandardPixmap.SP_DialogApplyButton,
            "tip": QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "ai": QStyle.StandardPixmap.SP_ComputerIcon,
        }
        pixmap_id = mapping.get(icon_name)
        if pixmap_id is None:
            return None
        return style.standardIcon(pixmap_id)

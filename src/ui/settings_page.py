from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.components.workspace_header import WorkspaceHeader
from ui.components.workspace_info_content import WORKSPACE_INFO_CONTENT
from ui.components.workspace_info_panel import WorkspaceInfoPanel
from ui.help.workspace_help_content import SETTINGS_WORKSPACE


class SettingsPage(QWidget):
    """Settings workspace shell for current and future application preferences."""

    help_requested = Signal(str)

    WORKSPACE_ID = SETTINGS_WORKSPACE

    def __init__(self, parent=None):
        super().__init__(parent)

        self.header = WorkspaceHeader("Settings")
        self.header.help_clicked.connect(self._on_help_clicked)
        info_content = WORKSPACE_INFO_CONTENT[self.WORKSPACE_ID]
        self.info_panel = WorkspaceInfoPanel(
            workspace_id=self.WORKSPACE_ID,
            title=info_content.title,
            purpose=info_content.purpose,
            purpose_details=info_content.purpose_details,
            typical_actions=info_content.typical_actions,
            tip=info_content.tip,
            collapsed_label=info_content.collapsed_label,
        )

        self.description_label = QLabel(
            "Settings will centralize workflow preferences, safety defaults, and AI behavior controls. "
            "Use this workspace to keep application behavior predictable across review sessions."
        )
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.description_label.setStyleSheet(
            "font-size: 14px; color: #3f4752; border: 1px solid #d4d9df; border-radius: 8px; padding: 12px;"
        )

        root = QVBoxLayout(self)
        root.addWidget(self.header)
        root.addWidget(self.info_panel)
        root.addWidget(self.description_label)
        root.addStretch(1)

    def _on_help_clicked(self) -> None:
        self.help_requested.emit(self.WORKSPACE_ID)

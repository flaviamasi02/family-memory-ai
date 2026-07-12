from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QLabel, QToolButton, QVBoxLayout, QWidget


class WorkspaceInfoPanel(QWidget):
    """Compact reusable workspace introduction panel with collapsible content."""

    _SETTINGS_KEY_PREFIX = "ui/workspace_info_panel"

    def __init__(
        self,
        workspace_id: str,
        title: str,
        purpose: str,
        purpose_details: str,
        typical_actions: list[str] | tuple[str, ...],
        tip: str,
        collapsed_label: str = "Workspace overview",
        settings: QSettings | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.workspace_id = str(workspace_id or "").strip()
        self._title = str(title or "").strip()
        self._collapsed_label = str(collapsed_label or "Workspace overview").strip()
        self._settings = settings or QSettings(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            "FamilyMemoryAI",
            "FamilyMemoryAI",
        )

        self.toggle_button = QToolButton()
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toggle_button.setAutoRaise(True)
        self.toggle_button.setStyleSheet(
            "QToolButton {"
            " border: none; text-align: left; padding: 0;"
            " font-size: 14px; font-weight: 600; color: #2f3b4a;"
            "}"
            "QToolButton:focus { outline: 1px solid #8aa1bf; }"
        )
        self.toggle_button.toggled.connect(self._on_toggled)

        self.details_container = QWidget()
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(0, 8, 0, 0)
        details_layout.setSpacing(6)

        self.workspace_title_label = QLabel(self._title)
        self.workspace_title_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #1f2937;")

        purpose_heading = QLabel("Purpose")
        purpose_heading.setStyleSheet("font-size: 12px; font-weight: 700; color: #475569;")
        self.purpose_label = QLabel(str(purpose or "").strip())
        self.purpose_label.setWordWrap(True)
        self.purpose_label.setStyleSheet("font-size: 13px; color: #334155;")
        self.purpose_details_label = QLabel(str(purpose_details or "").strip())
        self.purpose_details_label.setWordWrap(True)
        self.purpose_details_label.setStyleSheet("font-size: 13px; color: #334155;")

        actions_heading = QLabel("Typical actions")
        actions_heading.setStyleSheet("font-size: 12px; font-weight: 700; color: #475569;")
        self.actions_label = QLabel(self._build_actions_text(typical_actions))
        self.actions_label.setWordWrap(True)
        self.actions_label.setStyleSheet("font-size: 13px; color: #334155;")

        tip_heading = QLabel("Tip")
        tip_heading.setStyleSheet("font-size: 12px; font-weight: 700; color: #475569;")
        self.tip_label = QLabel(str(tip or "").strip())
        self.tip_label.setWordWrap(True)
        self.tip_label.setStyleSheet("font-size: 13px; color: #334155;")

        details_layout.addWidget(self.workspace_title_label)
        details_layout.addWidget(purpose_heading)
        details_layout.addWidget(self.purpose_label)
        details_layout.addWidget(self.purpose_details_label)
        details_layout.addWidget(actions_heading)
        details_layout.addWidget(self.actions_label)
        details_layout.addWidget(tip_heading)
        details_layout.addWidget(self.tip_label)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(0)
        root.addWidget(self.toggle_button)
        root.addWidget(self.details_container)

        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())
        self.setStyleSheet(
            "WorkspaceInfoPanel {"
            " background: #f8fafc; border: 1px solid #d8dee6; border-radius: 8px;"
            "}"
        )

        initial_expanded = self._load_expanded_state()
        self.toggle_button.setChecked(initial_expanded)
        self._apply_state(initial_expanded)

    def is_expanded(self) -> bool:
        return self.toggle_button.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self.toggle_button.setChecked(bool(expanded))

    def _build_actions_text(self, actions: list[str] | tuple[str, ...]) -> str:
        cleaned = [str(action).strip() for action in list(actions or []) if str(action).strip()]
        return "\n".join(f"- {action}" for action in cleaned)

    def _settings_key(self) -> str:
        workspace = self.workspace_id or "default"
        return f"{self._SETTINGS_KEY_PREFIX}/{workspace}/expanded"

    def _load_expanded_state(self) -> bool:
        return bool(self._settings.value(self._settings_key(), True, type=bool))

    def _save_expanded_state(self, expanded: bool) -> None:
        self._settings.setValue(self._settings_key(), bool(expanded))
        self._settings.sync()

    def _toggle_label_text(self, expanded: bool) -> str:
        arrow = "▼" if expanded else "▶"
        return f"{arrow} {self._title} - {self._collapsed_label}"

    def _apply_state(self, expanded: bool) -> None:
        self.details_container.setHidden(not expanded)
        self.toggle_button.setText(self._toggle_label_text(expanded))
        self.toggle_button.setToolTip("Collapse workspace information" if expanded else "Expand workspace information")

    def _on_toggled(self, checked: bool) -> None:
        expanded = bool(checked)
        self._apply_state(expanded)
        self._save_expanded_state(expanded)

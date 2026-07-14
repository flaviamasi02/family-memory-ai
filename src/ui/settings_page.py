from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QPushButton, QSpinBox, QFileDialog, QTextEdit, QHBoxLayout
from vision.mobileclip_provider import MobileCLIPEmbeddingProvider

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

        self.mobileclip_status = QLabel("MobileCLIP: checking optional local provider…")
        self.mobileclip_status.setWordWrap(True)
        self.sample_limit = QSpinBox(); self.sample_limit.setRange(1, 300); self.sample_limit.setValue(100)
        self.select_folder_button = QPushButton("Select MobileCLIP evaluation folder…")
        self.cancel_note = QLabel("Evaluation runs outside the UI thread in the evaluation service; no model is downloaded automatically.")
        self.cancel_note.setWordWrap(True)
        self.report_box = QTextEdit(); self.report_box.setReadOnly(True); self.report_box.setMaximumHeight(120)
        controls = QHBoxLayout(); controls.addWidget(QLabel("Max sample size (default 100, cap 300):")); controls.addWidget(self.sample_limit); controls.addStretch(1)
        root.addWidget(QLabel("MobileCLIP Local Evaluation (evaluation-only)"))
        root.addWidget(self.mobileclip_status)
        root.addLayout(controls)
        root.addWidget(self.select_folder_button)
        root.addWidget(self.cancel_note)
        root.addWidget(self.report_box)
        self.select_folder_button.clicked.connect(self._select_mobileclip_folder)
        self._refresh_mobileclip_status()
        root.addStretch(1)

    def _on_help_clicked(self) -> None:
        self.help_requested.emit(self.WORKSPACE_ID)


    def _refresh_mobileclip_status(self) -> None:
        provider = MobileCLIPEmbeddingProvider()
        status = provider.availability()
        meta = provider.metadata
        self.mobileclip_status.setText(
            f"Status: {status.state}. Selected checkpoint: {meta.checkpoint_id} ({meta.download_size}, {meta.embedding_dimension}D). "
            f"Source: {meta.source_url}. Missing dependencies: {', '.join(status.missing_dependencies) or 'none'}. "
            "Use explicit setup/download steps before running; startup and imports do not download models."
        )

    def _select_mobileclip_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select a folder for bounded MobileCLIP evaluation")
        if not folder:
            return
        self.report_box.setPlainText(
            f"Selected {folder}. Run the documented evaluation command or developer workflow with max_images={self.sample_limit.value()}. "
            "The workflow is capped at 300 images and writes reports under stable application data."
        )

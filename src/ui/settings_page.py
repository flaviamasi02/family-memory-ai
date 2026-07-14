from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from vision.evaluation_sources import (
    EvaluationSourceResult,
    another_folder_source,
    current_library_source,
    selected_photos_source,
)
from vision.mobileclip_provider import MobileCLIPEmbeddingProvider

from ui.components.workspace_header import WorkspaceHeader
from ui.components.workspace_info_content import WORKSPACE_INFO_CONTENT
from ui.components.workspace_info_panel import WorkspaceInfoPanel
from ui.help.workspace_help_content import SETTINGS_WORKSPACE


class SettingsPage(QWidget):
    """Settings workspace shell for current and future application preferences."""

    help_requested = Signal(str)
    mobileclip_evaluation_requested = Signal(object)

    WORKSPACE_ID = SETTINGS_WORKSPACE

    def __init__(self, parent=None):
        super().__init__(parent)
        self._library_provider: Callable[[], list] = lambda: []
        self._selection_provider: Callable[[], list] = lambda: []
        self._selected_folder: Path | None = None
        self._last_source_result: EvaluationSourceResult | None = None

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
        self.library_radio = QRadioButton("Current imported library")
        self.selected_radio = QRadioButton("Selected photos")
        self.folder_radio = QRadioButton("Another folder")
        self.source_group = QButtonGroup(self)
        for button in (self.library_radio, self.selected_radio, self.folder_radio):
            self.source_group.addButton(button)
            button.toggled.connect(self._refresh_source_summary)
        self.library_radio.setChecked(True)
        self.select_folder_button = QPushButton("Choose another folder…")
        self.run_button = QPushButton("Run MobileCLIP evaluation")
        self.cancel_note = QLabel("Evaluation runs outside the UI thread in the evaluation service; no model is downloaded automatically.")
        self.cancel_note.setWordWrap(True)
        self.source_summary = QLabel("")
        self.source_summary.setWordWrap(True)
        self.report_box = QTextEdit(); self.report_box.setReadOnly(True); self.report_box.setMaximumHeight(120)
        controls = QHBoxLayout(); controls.addWidget(QLabel("Max sample size (default 100, cap 300):")); controls.addWidget(self.sample_limit); controls.addStretch(1)
        source_layout = QVBoxLayout(); source_layout.addWidget(QLabel("Evaluation source:")); source_layout.addWidget(self.library_radio); source_layout.addWidget(self.selected_radio); source_layout.addWidget(self.folder_radio)
        root.addWidget(QLabel("MobileCLIP Local Evaluation (evaluation-only)"))
        root.addWidget(self.mobileclip_status)
        root.addLayout(controls)
        root.addLayout(source_layout)
        root.addWidget(self.select_folder_button)
        root.addWidget(self.source_summary)
        root.addWidget(self.run_button)
        root.addWidget(self.cancel_note)
        root.addWidget(self.report_box)
        self.select_folder_button.clicked.connect(self._select_mobileclip_folder)
        self.run_button.clicked.connect(self._run_mobileclip_evaluation)
        self.sample_limit.valueChanged.connect(self._refresh_source_summary)
        self._refresh_mobileclip_status()
        self._refresh_source_summary()
        root.addStretch(1)

    def set_evaluation_context_providers(self, library_provider: Callable[[], list], selection_provider: Callable[[], list]) -> None:
        self._library_provider = library_provider
        self._selection_provider = selection_provider
        self._refresh_source_summary()

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

    def _active_source_result(self) -> EvaluationSourceResult:
        limit = self.sample_limit.value()
        if self.selected_radio.isChecked():
            return selected_photos_source(self._selection_provider(), limit)
        if self.folder_radio.isChecked():
            return another_folder_source(self._selected_folder, limit)
        return current_library_source(self._library_provider(), limit)

    def _refresh_source_summary(self) -> None:
        result = self._active_source_result()
        self._last_source_result = result
        self.run_button.setEnabled(result.available and result.sample_count > 0)
        self.select_folder_button.setEnabled(self.folder_radio.isChecked())
        self.source_summary.setText(self._format_source_summary(result))

    def _format_source_summary(self, result: EvaluationSourceResult) -> str:
        limit = self.sample_limit.value()
        if not result.available:
            return f"Source: {result.source_label}\n{result.message}\nMaximum sample: {limit}"
        if result.source_id == "selected":
            return f"Source: Selected photos\nSelected: {result.available_count}\nMaximum sample: {limit}\nImages to evaluate: {result.sample_count}"
        if result.source_id == "folder":
            return f"Source: Another folder\nFolder: {result.folder}\nEligible images: {result.available_count}\nMaximum sample: {limit}\nImages to evaluate: {result.sample_count}"
        return f"Source: Current imported library\nAvailable images: {result.available_count}\nMaximum sample: {limit}\nImages to evaluate: {result.sample_count}"

    def _select_mobileclip_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select a folder for bounded MobileCLIP evaluation")
        if not folder:
            return
        self._selected_folder = Path(folder)
        self.folder_radio.setChecked(True)
        self._refresh_source_summary()

    def _run_mobileclip_evaluation(self) -> None:
        result = self._active_source_result()
        self._last_source_result = result
        if not result.available or not result.paths:
            self.report_box.setPlainText(result.message or "No images are available for evaluation.")
            self._refresh_source_summary()
            return
        self.report_box.setPlainText(
            f"Queued MobileCLIP evaluation for {result.sample_count} image(s) from {result.source_label}. "
            "The evaluation service performs model inference outside the UI thread and does not modify originals or categories."
        )
        self.mobileclip_evaluation_requested.emit(result)

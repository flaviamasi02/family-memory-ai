from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from vision.evaluation_sources import (
    EvaluationSourceResult,
    another_folder_source,
    current_library_source,
    selected_photos_source,
)
from ai_runtime.manager import create_default_runtime_manager

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
        self.ai_runtime_manager = create_default_runtime_manager()

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

        self.ai_models_title = QLabel("AI Models")
        self.ai_models_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.ai_models_card = QFrame()
        self.ai_models_card.setFrameShape(QFrame.Shape.StyledPanel)
        self.ai_models_card.setStyleSheet("QFrame { border: 1px solid #d4d9df; border-radius: 8px; padding: 8px; background: #fbfcfe; }")
        self.ai_model_name = QLabel("MobileCLIP")
        self.ai_model_name.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.ai_detail_labels: dict[str, QLabel] = {}
        for key in (
            "Status",
            "Checkpoint",
            "Capabilities",
            "Device",
            "Python environment",
            "Download size",
            "Disk usage",
            "Code license",
            "Model license",
            "Last installed",
            "Last updated",
            "Last benchmark",
            "Last error",
        ):
            label = QLabel("checking…")
            label.setWordWrap(True)
            self.ai_detail_labels[key] = label
        self.ai_actions_label = QLabel("Actions: View details, verify, test, update, remove, open model folder, and view logs are surfaced according to runtime state. Install requires an explicitly confirmed plan.")
        self.ai_actions_label.setWordWrap(True)
        self.mobileclip_status = QLabel("MobileCLIP: checking optional local provider…")
        self.mobileclip_status.setWordWrap(True)
        self.ai_env_input = QLineEdit()
        self.ai_env_input.setPlaceholderText("Python interpreter for selected AI runtime (current app environment by default)")
        self.inspect_env_button = QPushButton("Inspect Python environment")
        self.plan_button = QPushButton("View installation plan")
        self.ai_plan_box = QTextEdit(); self.ai_plan_box.setReadOnly(True); self.ai_plan_box.setMaximumHeight(170)
        self.sample_limit = QSpinBox(); self.sample_limit.setRange(1, 300); self.sample_limit.setValue(100)
        self.library_radio = QRadioButton("Current imported library")
        self.selected_radio = QRadioButton("Selected photos")
        self.folder_radio = QRadioButton("Another folder")
        self.source_group = QButtonGroup(self)
        self.select_folder_button = QPushButton("Choose another folder…")
        self.run_button = QPushButton("Run MobileCLIP evaluation")
        self.cancel_note = QLabel("Evaluation runs outside the UI thread in the evaluation service; no model is downloaded automatically.")
        self.cancel_note.setWordWrap(True)
        self.source_summary = QLabel("")
        self.source_summary.setWordWrap(True)
        self.report_box = QTextEdit(); self.report_box.setReadOnly(True); self.report_box.setMaximumHeight(120)
        for button in (self.library_radio, self.selected_radio, self.folder_radio):
            self.source_group.addButton(button)
            button.toggled.connect(self._refresh_source_summary)
        self.library_radio.setChecked(True)
        controls = QHBoxLayout(); controls.addWidget(QLabel("Max sample size (default 100, cap 300):")); controls.addWidget(self.sample_limit); controls.addStretch(1)
        source_layout = QVBoxLayout(); source_layout.addWidget(QLabel("Evaluation source:")); source_layout.addWidget(self.library_radio); source_layout.addWidget(self.selected_radio); source_layout.addWidget(self.folder_radio)
        root.addWidget(self.ai_models_title)
        card_layout = QVBoxLayout(self.ai_models_card)
        card_layout.addWidget(self.ai_model_name)
        details_layout = QGridLayout()
        for row, (key, value_label) in enumerate(self.ai_detail_labels.items()):
            key_label = QLabel(f"{key}:")
            key_label.setStyleSheet("font-weight: 600;")
            key_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            details_layout.addWidget(key_label, row, 0)
            details_layout.addWidget(value_label, row, 1)
        card_layout.addLayout(details_layout)
        card_layout.addWidget(self.ai_actions_label)
        root.addWidget(self.ai_models_card)
        root.addWidget(self.mobileclip_status)
        env_layout = QHBoxLayout(); env_layout.addWidget(QLabel("Python environment:")); env_layout.addWidget(self.ai_env_input); env_layout.addWidget(self.inspect_env_button); env_layout.addWidget(self.plan_button)
        root.addLayout(env_layout)
        root.addWidget(self.ai_plan_box)
        root.addWidget(QLabel("MobileCLIP Local Evaluation (evaluation-only)"))
        root.addLayout(controls)
        root.addLayout(source_layout)
        root.addWidget(self.select_folder_button)
        root.addWidget(self.source_summary)
        root.addWidget(self.run_button)
        root.addWidget(self.cancel_note)
        root.addWidget(self.report_box)
        self.inspect_env_button.clicked.connect(self._inspect_ai_environment)
        self.plan_button.clicked.connect(self._show_ai_installation_plan)
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
        descriptor = self.ai_runtime_manager.registry.require("mobileclip")
        status = self.ai_runtime_manager.status("mobileclip")
        record = self.ai_runtime_manager.installation_record("mobileclip")
        last_benchmark = next((b.date for b in reversed(self.ai_runtime_manager.storage.benchmarks()) if b.provider_id == "mobileclip"), "never")
        details = {
            "Status": status.state,
            "Checkpoint": f"{descriptor.checkpoint_id} ({descriptor.revision})",
            "Capabilities": ", ".join(c.value.replace("_", " ") for c in descriptor.capabilities),
            "Device": "CPU",
            "Python environment": record.interpreter_path or "current application environment",
            "Download size": descriptor.expected_download_size,
            "Disk usage": f"{record.installed_disk_usage_bytes} bytes",
            "Code license": descriptor.code_license,
            "Model license": descriptor.model_license,
            "Last installed": record.install_date or "never",
            "Last updated": record.update_date or "never",
            "Last benchmark": last_benchmark,
            "Last error": status.last_error or "none",
        }
        for key, value in details.items():
            self.ai_detail_labels[key].setText(value)
        self.mobileclip_status.setText(
            "MobileCLIP remains local-only and evaluation-only. "
            "Only valid actions are enabled by runtime state; no package or model is downloaded automatically."
        )

    def _inspect_ai_environment(self) -> None:
        interpreter = self.ai_env_input.text().strip() or None
        env = self.ai_runtime_manager.save_environment_selection("mobileclip", interpreter or __import__('sys').executable)
        self.ai_plan_box.setPlainText(
            f"Python environment:\n{env.interpreter_path}\nVersion: {env.python_version or 'unknown'}\nArchitecture: {env.architecture or 'unknown'}\nEnvironment: {env.environment_type} at {env.environment_path or 'unknown'}\nPip available: {env.pip_available}\nWritable: {env.writable}\nValid: {env.valid}\n{env.message}"
        )
        self._refresh_mobileclip_status()

    def _show_ai_installation_plan(self) -> None:
        interpreter = self.ai_env_input.text().strip() or None
        plan = self.ai_runtime_manager.build_installation_plan("mobileclip", interpreter)
        actions = "\n".join(f"- {a.action_type.value}: {a.label}" for a in plan.actions)
        warnings = "\n".join(f"- {w}" for w in plan.warnings)
        self.ai_plan_box.setPlainText(
            f"Installation plan for {plan.provider_name}\n"
            f"Checkpoint: {plan.checkpoint_id}\n"
            f"Python environment:\n{plan.python_environment.interpreter_path}\n"
            f"Packages: {', '.join(plan.packages_to_install) or 'none'}\n"
            f"Model files: {', '.join(plan.model_files_to_download) or 'none'}\n"
            f"Download size: {plan.expected_download_size}\nDestination: {plan.destination_path}\n"
            f"Licenses: code={plan.licenses['code']}; model={plan.licenses['model']}\n"
            f"Device: {plan.device}\nAdmin rights expected: {plan.administrator_rights_expected}\nRestart may be required: {plan.restart_may_be_required}\n"
            f"Warnings:\n{warnings}\nTyped actions (not executed until explicit confirmation):\n{actions}"
        )
        QMessageBox.information(self, "AI Models installation plan", "Plan generated only. Nothing was installed or downloaded.")

    def _active_source_result(self) -> EvaluationSourceResult:
        limit = self.sample_limit.value()
        if self.selected_radio.isChecked():
            return selected_photos_source(self._selection_provider(), limit)
        if self.folder_radio.isChecked():
            return another_folder_source(self._selected_folder, limit)
        return current_library_source(self._library_provider(), limit)

    def _refresh_source_summary(self) -> None:
        required_widgets = ("run_button", "select_folder_button", "source_summary")
        if not all(hasattr(self, name) for name in required_widgets):
            return
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

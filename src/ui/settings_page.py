from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from threading import Event
from typing import Callable

from PySide6.QtCore import Qt, Signal, QThread, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QFrame,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QLayout,
    QScrollArea,
)
from vision.evaluation_sources import (
    EvaluationSourceResult,
    another_folder_source,
    current_library_source,
    selected_photos_source,
)
from ai_runtime.manager import create_default_runtime_manager
from ai_runtime.models import AIRuntimeInstallationPlan
from workers.ai_runtime_worker import AIRuntimeOperationWorker

from ui.components.workspace_header import WorkspaceHeader
from ui.components.workspace_info_content import WORKSPACE_INFO_CONTENT
from ui.components.workspace_info_panel import WorkspaceInfoPanel
from ui.help.workspace_help_content import SETTINGS_WORKSPACE


logger = logging.getLogger(__name__)


class SettingsPage(QWidget):
    """Settings workspace shell for current and future application preferences."""

    help_requested = Signal(str)
    mobileclip_evaluation_requested = Signal(object)

    WORKSPACE_ID = SETTINGS_WORKSPACE

    def __init__(self, parent=None):
        t0 = time.perf_counter()
        super().__init__(parent)
        self._library_provider: Callable[[], list] = lambda: []
        self._selection_provider: Callable[[], list] = lambda: []
        self._selected_folder: Path | None = None
        self._last_source_result: EvaluationSourceResult | None = None
        self.ai_runtime_manager = create_default_runtime_manager()
        self._last_installation_plan: AIRuntimeInstallationPlan | None = None
        self._active_runtime_thread: QThread | None = None
        self._active_runtime_worker: AIRuntimeOperationWorker | None = None
        self._active_cancel_event: Event | None = None

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

        page_layout = QVBoxLayout(self)
        page_layout.addWidget(self.header)

        self.settings_scroll_area = QScrollArea()
        self.settings_scroll_area.setObjectName("settingsScrollArea")
        self.settings_scroll_area.setWidgetResizable(True)
        self.settings_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.settings_scroll_content = QWidget()
        self.settings_scroll_content.setObjectName("settingsScrollContent")
        root = QVBoxLayout(self.settings_scroll_content)
        root.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        root.addWidget(self.info_panel)
        root.addWidget(self.description_label)
        page_layout.addWidget(self.settings_scroll_area, 1)
        self.settings_scroll_area.setWidget(self.settings_scroll_content)

        self.ai_models_title = QLabel("AI Models")
        self.ai_models_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.ai_models_card = QFrame()
        self.ai_models_card.setObjectName("aiModelsCard")
        self.ai_models_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.ai_models_card.setFrameShape(QFrame.Shape.StyledPanel)
        self.ai_models_card.setStyleSheet("#aiModelsCard { border: 1px solid #d4d9df; border-radius: 8px; padding: 8px; background: #fbfcfe; }")
        self.ai_model_name = QLabel("MobileCLIP")
        self.ai_model_name.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.ai_detail_labels: dict[str, QLabel] = {}
        self.ai_detail_key_labels: dict[str, QLabel] = {}
        self._ai_details_grid_rows_inserted = 0
        for key in (
            "Provider",
            "Status",
            "Checkpoint",
            "Capabilities",
            "Device",
            "Python environment",
            "Python version",
            "Provider revision",
            "Model path",
            "Download size",
            "Disk usage",
            "Code license",
            "Model license",
            "Last installed",
            "Last updated",
            "Current step",
            "Installed packages",
            "Checkpoint status",
            "Last verification",
            "Last benchmark",
            "Last error",
        ):
            label = QLabel("checking…")
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            self.ai_detail_labels[key] = label
        self.ai_actions_label = QLabel("Actions: View details, verify, Test Image, update, remove, open model folder, and view logs are surfaced according to runtime state. Install requires an explicitly confirmed plan.")
        self.ai_actions_label.setWordWrap(True)
        self.mobileclip_status = QLabel("MobileCLIP: checking optional local provider…")
        self.mobileclip_status.setWordWrap(True)
        self.ai_env_input = QLineEdit()
        self.ai_env_input.setPlaceholderText("Python interpreter for selected AI runtime (current app environment by default)")
        self.inspect_env_button = QPushButton("Inspect Python environment")
        self.plan_button = QPushButton("View installation plan")
        self.install_button = QPushButton("Install")
        self.cancel_install_button = QPushButton("Cancel")
        self.verify_button = QPushButton("Verify")
        self.test_button = QPushButton("Test Image")
        self.test_button.setToolTip("Select one image file and run a MobileCLIP embedding test; folders are not selected here.")
        self.open_model_folder_button = QPushButton("Open model folder")
        self.view_logs_button = QPushButton("View logs")
        self.remove_model_files_button = QPushButton("Remove model files")
        self.ai_plan_box = QTextEdit(); self.ai_plan_box.setReadOnly(True); self.ai_plan_box.setMaximumHeight(170)
        self.dump_ai_metadata_button = QPushButton("Dump AI metadata diagnostics")
        self.runtime_step_label = QLabel("Current step: idle")
        self.runtime_progress_bar = QProgressBar(); self.runtime_progress_bar.setRange(0, 1); self.runtime_progress_bar.setValue(0)
        self.sample_limit = QSpinBox(); self.sample_limit.setRange(1, 300); self.sample_limit.setValue(100)
        self.library_radio = QRadioButton("Current imported library")
        self.selected_radio = QRadioButton("Selected photos")
        self.folder_radio = QRadioButton("Another folder")
        self.source_group = QButtonGroup(self)
        self.select_folder_button = QPushButton("Choose another folder…")
        self.run_button = QPushButton("Run MobileCLIP evaluation")
        self.cancel_note = QLabel("Evaluation and AI runtime operations run outside the UI thread; no model is downloaded automatically.")
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
        env_layout = QHBoxLayout(); env_layout.addWidget(QLabel("Python environment:")); env_layout.addWidget(self.ai_env_input); env_layout.addWidget(self.inspect_env_button); env_layout.addWidget(self.plan_button)
        action_layout = QHBoxLayout()
        for action_button in (self.install_button, self.cancel_install_button, self.verify_button, self.test_button, self.open_model_folder_button, self.view_logs_button, self.remove_model_files_button):
            action_layout.addWidget(action_button)
        root.addWidget(self.ai_models_title)
        card_layout = QVBoxLayout(self.ai_models_card)
        card_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        card_layout.addWidget(self.ai_model_name)
        self.ai_details_widget = QWidget(self.ai_models_card)
        self.ai_details_widget.setObjectName("ai_details_widget")
        self.ai_details_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        details_layout = QGridLayout(self.ai_details_widget)
        details_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        details_layout.setColumnStretch(0, 0)
        details_layout.setColumnStretch(1, 1)
        for row, (key, value_label) in enumerate(self.ai_detail_labels.items()):
            key_label = QLabel(f"{key}:")
            key_label.setStyleSheet("font-weight: 600;")
            key_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            key_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            self.ai_detail_key_labels[key] = key_label
            row_height = max(key_label.sizeHint().height(), value_label.sizeHint().height())
            details_layout.setRowMinimumHeight(row, row_height)
            details_layout.setRowStretch(row, 0)
            details_layout.addWidget(key_label, row, 0)
            details_layout.addWidget(value_label, row, 1)
        self._ai_details_grid_rows_inserted = details_layout.rowCount()
        card_layout.addWidget(self.ai_details_widget)
        card_layout.addWidget(self.mobileclip_status)
        card_layout.addWidget(self.ai_actions_label)
        card_layout.addLayout(action_layout)
        card_layout.addWidget(self.dump_ai_metadata_button)
        card_layout.addLayout(env_layout)
        card_layout.addWidget(self.ai_plan_box)
        card_layout.addWidget(self.runtime_step_label)
        card_layout.addWidget(self.runtime_progress_bar)
        root.addWidget(self.ai_models_card, 0)
        self.mobileclip_evaluation_title = QLabel("MobileCLIP Local Evaluation (evaluation-only)")
        root.addWidget(self.mobileclip_evaluation_title)
        root.addLayout(controls)
        root.addLayout(source_layout)
        root.addWidget(self.select_folder_button)
        root.addWidget(self.source_summary)
        root.addWidget(self.run_button)
        root.addWidget(self.cancel_note)
        root.addWidget(self.report_box)
        self.inspect_env_button.clicked.connect(self._inspect_ai_environment)
        self.plan_button.clicked.connect(self._show_ai_installation_plan)
        self.dump_ai_metadata_button.clicked.connect(self._dump_ai_metadata_diagnostics)
        self.install_button.clicked.connect(self._confirm_and_install_mobileclip)
        self.cancel_install_button.clicked.connect(self._cancel_ai_runtime_operation)
        self.verify_button.clicked.connect(self._verify_mobileclip_runtime)
        self.test_button.clicked.connect(self._test_mobileclip_one_image)
        self.open_model_folder_button.clicked.connect(lambda: self.ai_plan_box.setPlainText(f"Model folder: {self.ai_runtime_manager.installation_record('mobileclip').local_model_cache_path}"))
        self.view_logs_button.clicked.connect(self._show_ai_runtime_logs)
        self.remove_model_files_button.clicked.connect(self._show_mobileclip_removal_plan)
        self.select_folder_button.clicked.connect(self._select_mobileclip_folder)
        self.run_button.clicked.connect(self._run_mobileclip_evaluation)
        self.sample_limit.valueChanged.connect(self._refresh_source_summary)
        self._restore_ai_environment_selection()
        self._refresh_mobileclip_status()
        self._refresh_source_summary()
        logger.info("SettingsPage construction %.1f ms", (time.perf_counter() - t0) * 1000)
        root.addStretch(1)

    def set_evaluation_context_providers(self, library_provider: Callable[[], list], selection_provider: Callable[[], list]) -> None:
        self._library_provider = library_provider
        self._selection_provider = selection_provider
        self._refresh_source_summary()

    def _on_help_clicked(self) -> None:
        self.help_requested.emit(self.WORKSPACE_ID)

    def _restore_ai_environment_selection(self) -> None:
        record = self.ai_runtime_manager.installation_record("mobileclip")
        if record.interpreter_path and not self.ai_env_input.text().strip():
            self.ai_env_input.setText(record.interpreter_path)

    def _show_ai_runtime_logs(self) -> None:
        self.ai_plan_box.setPlainText(self.ai_runtime_manager.storage.recent_log_text())

    def _refresh_mobileclip_status(self) -> None:
        refresh_t0 = time.perf_counter()
        logger.info("Refreshing AI Models cached metadata status")
        descriptor = self.ai_runtime_manager.registry.require("mobileclip")
        status = self.ai_runtime_manager.status("mobileclip", deep=False)
        record = self.ai_runtime_manager.installation_record("mobileclip")
        last_benchmark = next((b.date for b in reversed(self.ai_runtime_manager.storage.benchmarks()) if b.provider_id == "mobileclip"), "never")
        details = {
            "Provider": descriptor.display_name,
            "Status": status.state,
            "Checkpoint": f"{descriptor.checkpoint_id} ({descriptor.revision})",
            "Capabilities": ", ".join(c.value.replace("_", " ") for c in descriptor.capabilities),
            "Device": "CPU",
            "Python environment": record.interpreter_path or "current application environment",
            "Python version": record.python_version or descriptor.python_version_spec or "unknown",
            "Provider revision": descriptor.revision,
            "Model path": record.local_model_cache_path or "not selected",
            "Download size": descriptor.expected_download_size,
            "Disk usage": f"{record.installed_disk_usage_bytes} bytes",
            "Code license": descriptor.code_license,
            "Model license": descriptor.model_license,
            "Last installed": record.install_date or "never",
            "Last updated": record.update_date or "never",
            "Current step": status.state,
            "Installed packages": "available" if status.dependencies_available else f"missing: {', '.join(status.missing_dependencies)}",
            "Checkpoint status": "present" if status.model_files_available else f"missing: {', '.join(status.missing_model_files)}",
            "Last verification": record.last_validation_result or "never",
            "Last benchmark": last_benchmark,
            "Last error": status.last_error or "none",
        }
        logger.info("AI Models metadata details keys: %s", list(details))
        for key, value in details.items():
            self.ai_detail_labels[key].setText(value)
        self._refresh_ai_details_geometry()
        logger.info("AI Models cached status refresh %.1f ms; rows=%s child_widgets=%s card_geometry=%s details_geometry=%s", (time.perf_counter() - refresh_t0) * 1000, self._ai_details_grid_rows_inserted, len(self.ai_details_widget.findChildren(QWidget)), self.ai_models_card.geometry().getRect(), self.ai_details_widget.geometry().getRect())
        self.mobileclip_status.setText(
            "MobileCLIP remains local-only and evaluation-only. "
            "Only valid actions are enabled by runtime state; no package or model is downloaded automatically."
        )


    def _refresh_ai_details_geometry(self) -> None:
        details_layout = self.ai_details_widget.layout()
        if isinstance(details_layout, QGridLayout):
            for row, key in enumerate(self.ai_detail_labels):
                key_label = self.ai_detail_key_labels[key]
                value_label = self.ai_detail_labels[key]
                row_height = max(key_label.sizeHint().height(), value_label.sizeHint().height())
                details_layout.setRowMinimumHeight(row, row_height)
            details_layout.activate()
        self.ai_details_widget.updateGeometry()
        card_layout = self.ai_models_card.layout()
        if card_layout is not None:
            card_layout.activate()
        self.ai_models_card.updateGeometry()


    def _dump_ai_metadata_diagnostics(self) -> None:
        report = self._build_ai_metadata_diagnostics_report()
        logger.info("AI metadata diagnostics report:\n%s", report)
        self.ai_plan_box.setPlainText(report)

    def _build_ai_metadata_diagnostics_report(self) -> str:
        details_layout = self.ai_details_widget.layout()
        lines = [
            "AI metadata diagnostics",
            f"Card object name: {self.ai_models_card.objectName()}",
            f"Row count: {self._ai_details_grid_rows_inserted}",
            f"Widget count: {len(self.ai_details_widget.findChildren(QWidget))}",
            f"Card geometry: {self.ai_models_card.geometry().getRect()}",
            f"Details geometry: {self.ai_details_widget.geometry().getRect()}",
            f"Details sizeHint: {self.ai_details_widget.sizeHint().width()}x{self.ai_details_widget.sizeHint().height()}",
            f"Details minimumSizeHint: {self.ai_details_widget.minimumSizeHint().width()}x{self.ai_details_widget.minimumSizeHint().height()}",
            "Rows:",
        ]
        for row, key in enumerate(self.ai_detail_labels):
            key_label = self.ai_detail_key_labels[key]
            value_label = self.ai_detail_labels[key]
            key_item = details_layout.itemAtPosition(row, 0).widget() if isinstance(details_layout, QGridLayout) and details_layout.itemAtPosition(row, 0) else None
            value_item = details_layout.itemAtPosition(row, 1).widget() if isinstance(details_layout, QGridLayout) and details_layout.itemAtPosition(row, 1) else None
            lines.append(
                f"- {row}: {key} | key_visible={key_label.isVisible()} key_geometry={key_label.geometry().getRect()} "
                f"key_is_grid_item={key_item is key_label} | value_visible={value_label.isVisible()} "
                f"value_geometry={value_label.geometry().getRect()} value_is_grid_item={value_item is value_label} "
                f"value={value_label.text()}"
            )
        lines.extend(["Visible widgets:", *self._visible_widget_lines(self.ai_models_card)])
        lines.extend(["Widget tree:", *self._widget_tree_lines(self.ai_models_card)])
        lines.extend(["Parent hierarchy:", *self._widget_parent_hierarchy(self.ai_details_widget)])
        return "\n".join(lines)

    def _visible_widget_lines(self, root: QWidget) -> list[str]:
        lines: list[str] = []
        for widget in root.findChildren(QWidget):
            if widget.isVisible():
                lines.append(f"- {widget.__class__.__name__} name={widget.objectName() or '<unnamed>'} geometry={widget.geometry().getRect()}")
        return lines or ["- none"]

    def _widget_tree_lines(self, root: QWidget, depth: int = 0) -> list[str]:
        indent = "  " * depth
        lines = [f"{indent}- {root.__class__.__name__} name={root.objectName() or '<unnamed>'} geometry={root.geometry().getRect()} visible={root.isVisible()}"]
        for child in root.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
            lines.extend(self._widget_tree_lines(child, depth + 1))
        return lines

    def _widget_parent_hierarchy(self, widget: QWidget) -> list[str]:
        lines: list[str] = []
        current: QWidget | None = widget
        while current is not None:
            lines.append(f"- {current.__class__.__name__} name={current.objectName() or '<unnamed>'} geometry={current.geometry().getRect()}")
            parent = current.parentWidget()
            current = parent if isinstance(parent, QWidget) else None
        return lines

    def _inspect_ai_environment(self) -> None:
        interpreter = self.ai_env_input.text().strip() or None
        env = self.ai_runtime_manager.save_environment_selection("mobileclip", interpreter or __import__('sys').executable)
        self.ai_plan_box.setPlainText(
            f"Python environment:\n{env.interpreter_path}\nVersion: {env.python_version or 'unknown'}\nArchitecture: {env.architecture or 'unknown'}\nEnvironment: {env.environment_type} at {env.environment_path or 'unknown'}\nPip available: {env.pip_available}\nWritable: {env.writable}\nValid: {env.valid}\n{env.message}"
        )
        self._refresh_mobileclip_status()

    def _format_ai_installation_plan(self, plan: AIRuntimeInstallationPlan) -> str:
        actions = "\n".join(f"- {a.action_type.value}: {a.label}" for a in plan.actions)
        warnings = "\n".join(f"- {w}" for w in plan.warnings)
        return (
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

    def _show_ai_installation_plan(self) -> None:
        interpreter = self.ai_env_input.text().strip() or None
        self._last_installation_plan = None
        self.plan_button.setStyleSheet("")
        self.ai_plan_box.setPlainText("Inspecting MobileCLIP environment and building installation plan...")
        self.runtime_step_label.setText("Current step: building installation plan")
        self._start_ai_runtime_operation("build_plan", interpreter=interpreter)


    def _set_runtime_buttons_enabled(self, enabled: bool) -> None:
        for button in (self.inspect_env_button, self.plan_button, self.install_button, self.verify_button, self.test_button, self.open_model_folder_button, self.view_logs_button, self.remove_model_files_button):
            button.setEnabled(enabled)
        self.cancel_install_button.setEnabled(not enabled)

    def _start_ai_runtime_operation(self, operation: str, *, plan: AIRuntimeInstallationPlan | None = None, image_path: Path | None = None, interpreter: str | None = None) -> None:
        if self._active_runtime_thread is not None:
            self.ai_plan_box.setPlainText("Another AI runtime operation is already running.")
            return
        self._active_cancel_event = Event()
        thread = QThread(self)
        worker = AIRuntimeOperationWorker(self.ai_runtime_manager, operation, plan=plan, image_path=image_path, interpreter=interpreter, cancel_event=self._active_cancel_event)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_ai_runtime_progress, Qt.ConnectionType.QueuedConnection)
        worker.current_step.connect(self._on_ai_runtime_current_step, Qt.ConnectionType.QueuedConnection)
        worker.completed.connect(self._on_ai_runtime_completed, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(self._on_ai_runtime_failed, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(worker.deleteLater, Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(thread.deleteLater, Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(self._clear_ai_runtime_worker, Qt.ConnectionType.QueuedConnection)
        self._active_runtime_thread = thread
        self._active_runtime_worker = worker
        self._set_runtime_buttons_enabled(False)
        self.runtime_progress_bar.setRange(0, 0)
        thread.start()

    def _clear_ai_runtime_worker(self) -> None:
        self._active_runtime_thread = None
        self._active_runtime_worker = None
        self._active_cancel_event = None
        self._set_runtime_buttons_enabled(True)
        self.runtime_progress_bar.setRange(0, 1); self.runtime_progress_bar.setValue(1)
        self._refresh_mobileclip_status()

    @Slot(str)
    def _on_ai_runtime_current_step(self, step: str) -> None:
        self.runtime_step_label.setText(f"Current step: {step}")

    @Slot(str, str)
    def _on_ai_runtime_progress(self, step: str, message: str) -> None:
        self.ai_plan_box.append(f"[{step}] {message}")
        if step == "download" and "/" in message:
            done_text, total_text = message.split("/", 1)
            total_text = total_text.split()[0]
            if done_text.isdigit() and total_text.isdigit() and int(total_text) > 0:
                self.runtime_progress_bar.setRange(0, int(total_text)); self.runtime_progress_bar.setValue(int(done_text))

    @Slot(str, object)
    def _on_ai_runtime_completed(self, operation: str, result: object) -> None:
        self.runtime_step_label.setText(f"Current step: {operation} completed")
        if operation == "build_plan" and isinstance(result, AIRuntimeInstallationPlan):
            self._last_installation_plan = result
            self.ai_plan_box.setPlainText(self._format_ai_installation_plan(result))
            QMessageBox.information(self, "AI Models installation plan", "Plan generated only. Nothing was installed or downloaded.")
            return
        self.ai_plan_box.append(f"{operation.title()} completed.")
        if hasattr(result, "stdout") or hasattr(result, "stderr"):
            out = getattr(result, "stdout", "") or ""
            err = getattr(result, "stderr", "") or ""
            code = getattr(result, "returncode", "")
            self.ai_plan_box.append(f"Final result: exit_code={code}\n{out}\n{err}".strip())
        if operation == "test" and hasattr(result, "stdout"):
            try:
                payload = json.loads(result.stdout.strip())
                self.report_box.setPlainText(
                    f"MobileCLIP one-image test succeeded.\nElapsed seconds: {payload.get('elapsed_seconds'):.3f}\nEmbedding dimension: {payload.get('embedding_dimension')}\nFinite numeric output: {payload.get('finite')}\nNo classification, upload, or photo modification was performed."
                )
            except Exception:
                self.report_box.setPlainText(f"MobileCLIP one-image test completed.\n{getattr(result, 'stdout', '')}\n{getattr(result, 'stderr', '')}")
        self._refresh_mobileclip_status()

    @Slot(str)
    def _on_ai_runtime_failed(self, error: str) -> None:
        self.runtime_step_label.setText("Current step: failed")
        self.ai_plan_box.append(f"AI runtime operation failed: {error}")
        self._refresh_mobileclip_status()

    def _cancel_ai_runtime_operation(self) -> None:
        if self._active_cancel_event is not None:
            self._active_cancel_event.set()
            self.ai_plan_box.append("Cancellation requested. The running step will stop as soon as it is safe.")
        else:
            self.ai_plan_box.setPlainText("No AI runtime operation is running; nothing changed.")

    def _confirmation_text_for_plan(self, plan: AIRuntimeInstallationPlan) -> str:
        warnings = "\n".join(f"- {w}" for w in plan.warnings)
        return (
            f"Interpreter:\n{plan.python_environment.interpreter_path}\n\n"
            f"Packages:\n{chr(10).join(plan.packages_to_install) or 'none'}\n\n"
            f"Checkpoint: {plan.checkpoint_id}\nDestination: {plan.destination_path}\n\n"
            f"Licenses:\nCode: {plan.licenses['code']}\nModel: {plan.licenses['model']}\n\n"
            f"Disk estimate: {plan.estimated_disk_requirement}\n\nWarnings:\n{warnings}"
        )

    def _confirm_and_install_mobileclip(self) -> None:
        if self._last_installation_plan is None:
            self.ai_plan_box.setPlainText("Generate an installation plan first by clicking ‘View installation plan’.")
            self.plan_button.setFocus(Qt.FocusReason.OtherFocusReason)
            self.plan_button.setStyleSheet("font-weight: 700; border: 2px solid #2f80ed;")
            return
        interpreter = self.ai_env_input.text().strip() or self._last_installation_plan.python_environment.interpreter_path
        if not interpreter:
            self.ai_plan_box.setPlainText("Select and inspect a MobileCLIP Python interpreter before installing.")
            return
        env = self.ai_runtime_manager.save_environment_selection("mobileclip", interpreter)
        if not env.valid:
            self.ai_plan_box.setPlainText(f"Selected interpreter is invalid; installation was not started.\n{env.message}")
            self._refresh_mobileclip_status()
            return
        plan = self.ai_runtime_manager.build_installation_plan("mobileclip", interpreter)
        self._last_installation_plan = plan
        if QMessageBox.question(self, "Confirm MobileCLIP installation", self._confirmation_text_for_plan(plan)) != QMessageBox.StandardButton.Yes:
            self.ai_plan_box.setPlainText("Installation cancelled before execution; no packages or model files were changed.")
            return
        plan.confirmed = True
        self.ai_plan_box.setPlainText("Starting confirmed MobileCLIP installation…")
        self._start_ai_runtime_operation("install", plan=plan)

    def _verify_mobileclip_runtime(self) -> None:
        interpreter = self.ai_env_input.text().strip() or self.ai_runtime_manager.installation_record("mobileclip").interpreter_path
        if interpreter:
            env = self.ai_runtime_manager.save_environment_selection("mobileclip", interpreter)
            if not env.valid:
                self.ai_plan_box.setPlainText(f"Selected interpreter is invalid; verification was not started.\n{env.message}")
                return
        self.ai_plan_box.setPlainText("Starting MobileCLIP verification…")
        self._start_ai_runtime_operation("verify")

    def _test_mobileclip_one_image(self) -> None:
        result = self._active_source_result()
        image_path = result.paths[0] if result.available and result.paths else None
        if image_path is None:
            selected, _ = QFileDialog.getOpenFileName(self, "Select an image to test MobileCLIP", "", "One image file (*.jpg *.jpeg *.png *.bmp *.webp);;All supported images (*.jpg *.jpeg *.png *.bmp *.webp)")
            image_path = Path(selected) if selected else None
        if image_path is None:
            self.report_box.setPlainText("No image selected; MobileCLIP Test Image was not started.")
            return
        interpreter = self.ai_env_input.text().strip() or self.ai_runtime_manager.installation_record("mobileclip").interpreter_path
        if interpreter:
            env = self.ai_runtime_manager.save_environment_selection("mobileclip", interpreter)
            if not env.valid:
                self.report_box.setPlainText(f"Selected interpreter is invalid; test was not started.\n{env.message}")
                return
        self.report_box.setPlainText(f"Starting MobileCLIP Test Image embedding check for {image_path}…")
        self._start_ai_runtime_operation("test", image_path=Path(image_path))

    def _show_mobileclip_removal_plan(self) -> None:
        plan = self.ai_runtime_manager.removal_plan("mobileclip")
        warnings = "\n".join(f"- {w}" for w in plan.warnings)
        self.ai_plan_box.setPlainText(f"Removal plan for {plan.provider_name}\nDestination: {plan.destination_path}\nWarnings:\n{warnings}\nNo photos, thumbnails, categories, learning profiles, or originals are removed.")
        if QMessageBox.question(self, "Confirm MobileCLIP model-file removal", "Remove only manager-owned MobileCLIP checkpoint/cache files?\n\nPhotos, thumbnails, categories, profiles, and source images will be preserved.") != QMessageBox.StandardButton.Yes:
            self.ai_plan_box.append("Removal cancelled before execution; nothing changed.")
            return
        plan.confirmed = True
        self._start_ai_runtime_operation("remove", plan=plan)

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

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from threading import Event
from typing import Callable

from PySide6.QtCore import QUrl, Qt, Signal, QThread, Slot
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog,
    QButtonGroup,
    QCheckBox,
    QComboBox,
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
from ai_runtime.manager import AIRuntimeManager, create_default_runtime_manager
from ai_runtime.models import AIRuntimeInstallationPlan
from workers.ai_runtime_worker import AIRuntimeOperationWorker
from core.application_services import ApplicationServices, build_application_services
from core.perf_stats import (
    export_performance_report,
    performance_history,
)
from core.memory_review_perf import memory_review_performance_snapshot
from core.selection_diagnostics import (
    arm_selection_measurement,
    selection_diagnostic_report,
    set_selection_bypass,
)
from storage.errors import StorageError
from storage.schema import SCHEMA_VERSION

from ui.components.workspace_header import WorkspaceHeader
from ui.components.workspace_info_content import WORKSPACE_INFO_CONTENT
from ui.components.workspace_info_panel import WorkspaceInfoPanel
from ui.help.workspace_help_content import SETTINGS_WORKSPACE
from faces.runtime import FaceRuntimeManager
from workers.face_runtime_worker import FaceRuntimeWorker


logger = logging.getLogger(__name__)


class SettingsPage(QWidget):
    """Settings workspace shell for current and future application preferences."""

    help_requested = Signal(str)
    mobileclip_evaluation_requested = Signal(object)
    runtime_operation_finished = Signal(str)
    face_runtime_ready_changed = Signal(bool)

    WORKSPACE_ID = SETTINGS_WORKSPACE

    def __init__(
        self,
        parent=None,
        runtime_manager: AIRuntimeManager | None = None,
        application_services: ApplicationServices | None = None,
        face_runtime_manager: FaceRuntimeManager | None = None,
    ):
        t0 = time.perf_counter()
        super().__init__(parent)
        self._library_provider: Callable[[], list] = lambda: []
        self._selection_provider: Callable[[], list] = lambda: []
        self._selected_folder: Path | None = None
        self._last_source_result: EvaluationSourceResult | None = None
        self.ai_runtime_manager = runtime_manager or create_default_runtime_manager()
        self.application_services = application_services or build_application_services()
        self.face_runtime_manager = face_runtime_manager or FaceRuntimeManager()
        self._face_runtime_thread = None
        self._face_runtime_worker = None
        self._last_installation_plan: AIRuntimeInstallationPlan | None = None
        self._active_runtime_thread: QThread | None = None
        self._active_runtime_worker: AIRuntimeOperationWorker | None = None
        self._active_cancel_event: Event | None = None
        self._active_runtime_operation: str | None = None

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
        self.delete_face_analysis_button = QPushButton("Delete all face analysis data…")
        self.delete_face_analysis_button.clicked.connect(self._delete_face_analysis)
        root.addWidget(self.delete_face_analysis_button)
        self._build_face_runtime_section(root)
        self._build_developer_diagnostics(root)
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

    def _build_face_runtime_section(self, root: QVBoxLayout) -> None:
        self.face_runtime_title = QLabel("Face Recognition Runtime")
        self.face_runtime_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.face_runtime_card = QFrame(); self.face_runtime_card.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self.face_runtime_card)
        self.face_runtime_labels = {}
        grid = QGridLayout()
        for row, key in enumerate(("Runtime status", "Installed version", "Detector backend", "Model version",
                                   "Install location", "Last verification", "Last error")):
            grid.addWidget(QLabel(f"{key}:"), row, 0)
            value = QLabel("checking…"); value.setWordWrap(True); grid.addWidget(value, row, 1)
            self.face_runtime_labels[key] = value
        layout.addLayout(grid)
        actions = QHBoxLayout()
        self.face_runtime_install_button = QPushButton("Install")
        self.face_runtime_verify_button = QPushButton("Verify")
        self.face_runtime_repair_button = QPushButton("Repair")
        self.face_runtime_remove_button = QPushButton("Remove")
        self.face_runtime_logs_button = QPushButton("View Logs")
        self.face_runtime_folder_button = QPushButton("Open Runtime Folder")
        for button in (self.face_runtime_install_button, self.face_runtime_verify_button,
                       self.face_runtime_repair_button, self.face_runtime_remove_button,
                       self.face_runtime_logs_button, self.face_runtime_folder_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.face_runtime_progress = QProgressBar(); self.face_runtime_progress.setRange(0, 100)
        self.face_runtime_message = QLabel("Face recognition is optional and is never installed automatically.")
        self.face_runtime_message.setWordWrap(True)
        self.face_runtime_technical_details = QTextEdit(); self.face_runtime_technical_details.setReadOnly(True)
        self.face_runtime_technical_details.setMaximumHeight(100); self.face_runtime_technical_details.hide()
        layout.addWidget(self.face_runtime_progress); layout.addWidget(self.face_runtime_message)
        layout.addWidget(self.face_runtime_technical_details)
        root.addWidget(self.face_runtime_title); root.addWidget(self.face_runtime_card)
        self.face_runtime_install_button.clicked.connect(lambda: self._confirm_face_runtime_operation("install"))
        self.face_runtime_verify_button.clicked.connect(lambda: self._start_face_runtime_operation("verify"))
        self.face_runtime_repair_button.clicked.connect(lambda: self._confirm_face_runtime_operation("repair"))
        self.face_runtime_remove_button.clicked.connect(lambda: self._confirm_face_runtime_operation("remove"))
        self.face_runtime_logs_button.clicked.connect(self._show_face_runtime_logs)
        self.face_runtime_folder_button.clicked.connect(lambda: self._open_folder(self.face_runtime_manager.root))
        self.refresh_face_runtime_status()

    def refresh_face_runtime_status(self) -> None:
        status = self.face_runtime_manager.status()
        values = {"Runtime status": status.state, "Installed version": status.installed_version,
                  "Detector backend": status.detector_backend, "Model version": status.model_version,
                  "Install location": status.install_location, "Last verification": status.last_verification,
                  "Last error": status.last_error}
        for key, value in values.items(): self.face_runtime_labels[key].setText(value)
        busy = self._face_runtime_thread is not None
        self.face_runtime_install_button.setEnabled(not busy and not status.ready)
        self.face_runtime_verify_button.setEnabled(not busy and status.state != "Not installed")
        self.face_runtime_repair_button.setEnabled(not busy)
        self.face_runtime_remove_button.setEnabled(not busy and status.state != "Not installed")
        self.face_runtime_ready_changed.emit(status.ready)

    def _confirm_face_runtime_operation(self, operation: str) -> None:
        descriptions = {
            "install": "Install the local face recognition runtime into the application Python environment? No photos are uploaded.",
            "repair": "Repair the local face recognition runtime by reinstalling its managed packages?",
            "remove": "Remove the managed face detector runtime? Existing face-analysis data is preserved until separately deleted.",
        }
        if QMessageBox.question(self, f"{operation.title()} Face Runtime", descriptions[operation]) != QMessageBox.StandardButton.Yes:
            return
        self._start_face_runtime_operation(operation)

    def _start_face_runtime_operation(self, operation: str) -> None:
        if self._face_runtime_thread is not None: return
        thread = QThread(self); worker = FaceRuntimeWorker(self.face_runtime_manager, operation)
        worker.moveToThread(thread); thread.started.connect(worker.run)
        worker.progress.connect(self._on_face_runtime_progress)
        worker.completed.connect(self._on_face_runtime_completed)
        worker.failed.connect(self._on_face_runtime_failed)
        worker.finished.connect(thread.quit); worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater); thread.finished.connect(self._clear_face_runtime_operation)
        self._face_runtime_thread, self._face_runtime_worker = thread, worker
        self.face_runtime_message.setText(f"{operation.title()} in progress…")
        self.face_runtime_progress.setValue(0); self.refresh_face_runtime_status(); thread.start()

    def _on_face_runtime_progress(self, value: int, message: str) -> None:
        self.face_runtime_progress.setValue(value); self.face_runtime_message.setText(message)

    def _on_face_runtime_completed(self, status) -> None:
        self.face_runtime_progress.setValue(100); self.face_runtime_message.setText(
            "Face recognition runtime is ready." if status.ready else "Face recognition runtime was removed."
        )
        self.refresh_face_runtime_status()

    def _on_face_runtime_failed(self, message: str) -> None:
        self.face_runtime_message.setText(f"Operation failed. Recommended action: check your connection, then choose Repair. Reason: {message}")
        self.face_runtime_technical_details.setPlainText(message); self.face_runtime_technical_details.show()
        self.refresh_face_runtime_status()

    def _clear_face_runtime_operation(self) -> None:
        self._face_runtime_thread = self._face_runtime_worker = None
        self.refresh_face_runtime_status()

    def _show_face_runtime_logs(self) -> None:
        text = self.face_runtime_manager.log_path.read_text(encoding="utf-8", errors="replace") if self.face_runtime_manager.log_path.exists() else "No Face Runtime logs yet."
        self.face_runtime_technical_details.setPlainText(text[-12000:]); self.face_runtime_technical_details.show()

    def open_face_runtime_section(self) -> None:
        self.settings_scroll_area.ensureWidgetVisible(self.face_runtime_card)
        self.face_runtime_card.setFocus()

    def _build_developer_diagnostics(self, root: QVBoxLayout) -> None:
        self.developer_diagnostics_toggle = QPushButton("Developer Diagnostics")
        self.developer_diagnostics_toggle.setCheckable(True)
        self.developer_diagnostics_toggle.setChecked(False)
        self.developer_diagnostics_toggle.setStyleSheet("font-size: 16px; font-weight: 700; text-align: left;")
        root.addWidget(self.developer_diagnostics_toggle)

        self.developer_diagnostics_panel = QFrame()
        self.developer_diagnostics_panel.setObjectName("developerDiagnosticsPanel")
        self.developer_diagnostics_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.developer_diagnostics_panel.setStyleSheet(
            "#developerDiagnosticsPanel { border: 1px solid #d4d9df; border-radius: 8px; padding: 8px; background: #fbfcfe; }"
        )
        panel = QVBoxLayout(self.developer_diagnostics_panel)
        explanation = QLabel(
            "Safely inspect application-managed metadata storage. Libraries are registered only when you choose a folder; photos are never scanned here."
        )
        explanation.setWordWrap(True)
        panel.addWidget(explanation)
        self.diagnostics_library_selector = QComboBox()
        panel.addWidget(self.diagnostics_library_selector)
        self.diagnostics_labels: dict[str, QLabel] = {}
        grid = QGridLayout()
        fields = (
            "Application data root", "Registered library count", "Active LibraryID",
            "Active database path", "Schema version", "Expected schema version",
            "Database health status", "Integrity-check status", "Foreign-key-check status",
            "Migration-history status", "Missing required tables", "Read availability",
            "Write availability",
            "Total registered photos", "Active photos", "Removed photos",
            "Last incremental sync", "Last import summary",
        )
        for row, field in enumerate(fields):
            key = QLabel(f"{field}:"); key.setStyleSheet("font-weight: 600;")
            value = QLabel("Not available"); value.setWordWrap(True)
            self.diagnostics_labels[field] = value
            grid.addWidget(key, row, 0); grid.addWidget(value, row, 1)
        grid.setColumnStretch(1, 1)
        panel.addLayout(grid)
        self.diagnostics_status_label = QLabel("Ready")
        self.diagnostics_status_label.setWordWrap(True)
        panel.addWidget(self.diagnostics_status_label)
        self.diagnostics_report = QTextEdit()
        self.diagnostics_report.setReadOnly(True)
        self.diagnostics_report.setMaximumHeight(160)
        panel.addWidget(self.diagnostics_report)

        self.import_efficiency_title = QLabel("⚡ Import Efficiency")
        efficiency_font = QFont(self.import_efficiency_title.font())
        efficiency_font.setPointSizeF(max(14, efficiency_font.pointSizeF() + 3))
        efficiency_font.setWeight(QFont.Weight.Bold)
        self.import_efficiency_title.setFont(efficiency_font)
        panel.addWidget(self.import_efficiency_title)

        self.import_efficiency_status_banner = QLabel("— No completed import")
        self.import_efficiency_status_banner.setObjectName("importEfficiencyStatus")
        self.import_efficiency_status_banner.setStyleSheet(
            "#importEfficiencyStatus { background: #eef1f4; border-radius: 7px; "
            "padding: 9px; font-size: 14px; font-weight: 700; }"
        )
        panel.addWidget(self.import_efficiency_status_banner)

        self.import_efficiency_completion = QLabel("Complete an import to see how much work was reused.")
        self.import_efficiency_completion.setWordWrap(True)
        panel.addWidget(self.import_efficiency_completion)

        self.import_efficiency_values: dict[str, QLabel] = {}
        efficiency_grid = QGridLayout()
        efficiency_cards = (
            ("Photos processed", "📁", "Photos included in the completed import."),
            ("Already known photos", "✓", "Photos already stored in the library."),
            ("New photos", "+", "Photos that were not already known to the library."),
            ("Embeddings reused", "✨", "The previous AI analysis was reused."),
            ("Thumbnails reused", "✓", "Existing thumbnails were reused."),
            ("Database work avoided", "🗃", "Database queries avoided by reusing information already available."),
        )
        for index, (label, icon, help_text) in enumerate(efficiency_cards):
            card = QFrame(); card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setObjectName("importEfficiencyCard")
            card.setStyleSheet(
                "#importEfficiencyCard { background: white; border: 1px solid #dfe4e8; "
                "border-radius: 6px; padding: 5px; }"
            )
            card.setToolTip(help_text)
            card_layout = QVBoxLayout(card)
            heading = QLabel(f"{icon}  {label}"); heading.setStyleSheet("font-weight: 600; border: none;")
            heading.setToolTip(help_text)
            value = QLabel("0"); value.setStyleSheet("font-size: 24px; font-weight: 700; color: #243447; border: none;")
            value.setToolTip(help_text)
            card_layout.addWidget(heading); card_layout.addWidget(value)
            self.import_efficiency_values[label] = value
            efficiency_grid.addWidget(card, index // 3, index % 3)
        panel.addLayout(efficiency_grid)

        self.import_efficiency_result = QLabel("☆☆☆☆☆  No completed import")
        self.import_efficiency_result.setStyleSheet("font-size: 16px; font-weight: 700; color: #39734d;")
        panel.addWidget(self.import_efficiency_result)

        self.import_performance_title = QLabel("⚡ Import Performance")
        # A pixel-sized QSS font has pointSizeF() == -1. Qt's stylesheet/font
        # resolution later copies that font through setPointSize(), producing
        # ``QFont::setPointSize: Point size <= 0 (-1)`` when this diagnostics
        # heading is initialized. Use an equivalent positive point
        # size so the rendered height stays the same without an invalid inherited
        # point-size sentinel.
        title_font = QFont(self.import_performance_title.font())
        logical_dpi = max(1, self.import_performance_title.logicalDpiY())
        title_font.setPointSizeF(15 * 72 / logical_dpi)
        title_font.setWeight(QFont.Weight.Bold)
        self.import_performance_title.setFont(title_font)
        panel.addWidget(self.import_performance_title)
        self.performance_history_selector = QComboBox()
        self.performance_history_selector.currentIndexChanged.connect(self._show_performance_session)
        panel.addWidget(self.performance_history_selector)
        self.import_performance_summary = QLabel("Import completed in\n—\n\nSlowest activity\n—")
        self.import_performance_summary.setWordWrap(True)
        self.import_performance_summary.setStyleSheet("font-size: 15px; padding: 6px;")
        panel.addWidget(self.import_performance_summary)
        self.technical_details_toggle = QPushButton("▸ Technical Details")
        self.technical_details_toggle.setCheckable(True)
        self.technical_details_toggle.setChecked(False)
        self.technical_details_toggle.setToolTip(
            "Show all timings, stages, thread names, per-item measurements, and developer counters."
        )
        panel.addWidget(self.technical_details_toggle)
        self.import_performance_report = QTextEdit()
        self.import_performance_report.setReadOnly(True)
        self.import_performance_report.setMaximumHeight(240)
        self.import_performance_report.setToolTip(
            "Photos processed: Photos included in this import.\n"
            "Already known photos: Photos already stored in the library.\n"
            "New photos: Photos not previously stored in the library.\n"
            "Thumbnails reused: Existing thumbnail files were reused.\n"
            "Embeddings reused: The previous AI analysis was reused.\n"
            "File checks avoided: The application avoided checking the same files multiple times.\n"
            "Path processing avoided: The application avoided processing the same paths multiple times.\n"
            "Database queries avoided: The application reused information instead of reading it again.\n"
            "Timing averages: Average elapsed milliseconds for each processed item.\n"
            "Per-stage timings: Elapsed time, item count, per-item average, and thread for each activity.\n"
            "Developer counters: Original internal measurements retained for diagnosis."
        )
        panel.addWidget(self.import_performance_report)
        self.import_performance_report.setVisible(False)
        self.technical_details_toggle.toggled.connect(self._toggle_performance_details)
        self.export_performance_button = QPushButton("Export Performance Report")
        self.export_performance_button.clicked.connect(self._export_performance_report)
        panel.addWidget(self.export_performance_button)

        self.memory_review_performance_title = QLabel("Memory Review Performance")
        self.memory_review_performance_title.setStyleSheet("font-weight: 700; margin-top: 8px;")
        panel.addWidget(self.memory_review_performance_title)
        self.memory_review_performance_report = QTextEdit()
        self.memory_review_performance_report.setReadOnly(True)
        self.memory_review_performance_report.setMaximumHeight(180)
        self.memory_review_performance_report.setToolTip(
            "Aggregate Memory Review UI timings. Values are process-local and contain no per-photo logs."
        )
        panel.addWidget(self.memory_review_performance_report)
        self.measure_memory_review_selection_button = QPushButton(
            "Measure Memory Review selection"
        )
        self.measure_memory_review_selection_button.clicked.connect(
            lambda _checked=False: self._arm_selection_measurement("memory")
        )
        panel.addWidget(self.measure_memory_review_selection_button)
        self.measure_cleanup_review_selection_button = QPushButton(
            "Measure Cleanup Review selection"
        )
        self.measure_cleanup_review_selection_button.clicked.connect(
            lambda _checked=False: self._arm_selection_measurement("cleanup")
        )
        panel.addWidget(self.measure_cleanup_review_selection_button)
        self.memory_review_measurement_instructions = QLabel(
            "Open Memory Review, then select several photos. Return here to view the measured result."
        )
        self.memory_review_measurement_instructions.setWordWrap(True)
        panel.addWidget(self.memory_review_measurement_instructions)
        self.selection_diagnostic_warning = QLabel(
            "Temporary diagnostic controls: displayed information may be incomplete while a bypass is enabled."
        )
        self.selection_diagnostic_warning.setWordWrap(True)
        panel.addWidget(self.selection_diagnostic_warning)
        self.selection_diagnostic_bypasses = {}
        for key, label in (
            ("preview", "Memory Review diagnostic: skip preview loading"),
            ("details", "Memory Review diagnostic: skip detail-panel refresh"),
            ("suggestions", "Memory Review diagnostic: skip AI suggestions"),
            ("styling", "Memory Review diagnostic: skip selection styling"),
        ):
            set_selection_bypass(key, False)
            checkbox = QCheckBox(label)
            checkbox.setChecked(False)
            checkbox.toggled.connect(
                lambda checked, bypass_key=key: set_selection_bypass(bypass_key, checked)
            )
            self.selection_diagnostic_bypasses[key] = checkbox
            panel.addWidget(checkbox)

        actions = QGridLayout()
        action_specs = (
            ("diagnostics_refresh_button", "Refresh", self.refresh_developer_diagnostics),
            ("open_application_data_button", "Open Application Data Folder", self._open_application_data_folder),
            ("register_test_library_button", "Register Test Library", self._choose_test_library),
            ("open_selected_library_button", "Open Selected Library", self._open_selected_library),
            ("run_health_check_button", "Run Health Check", self._run_health_check),
            ("show_schema_summary_button", "Show Schema Summary", self._show_schema_summary),
            ("create_backup_button", "Create Backup", self._choose_backup_destination),
            ("validate_backup_button", "Validate Backup", self._choose_backup_to_validate),
            ("open_database_folder_button", "Open Database Folder", self._open_database_folder),
            ("copy_diagnostic_report_button", "Copy Diagnostic Report", self._copy_diagnostic_report),
        )
        for index, (attribute, text, callback) in enumerate(action_specs):
            button = QPushButton(text); setattr(self, attribute, button)
            button.clicked.connect(callback); actions.addWidget(button, index // 2, index % 2)
        panel.addLayout(actions)
        root.addWidget(self.developer_diagnostics_panel)
        self.developer_diagnostics_toggle.toggled.connect(self.developer_diagnostics_panel.setVisible)
        self.developer_diagnostics_panel.setVisible(False)
        self.refresh_developer_diagnostics()

    def _set_diagnostics_status(self, text: str) -> None:
        self.diagnostics_status_label.setText(text)

    def _arm_selection_measurement(self, workspace: str = "memory") -> None:
        arm_selection_measurement(workspace)
        self._set_diagnostics_status(
            f"{workspace.title()} Review selection measurement armed. Select photos, then Refresh."
        )

    def refresh_developer_diagnostics(self) -> None:
        services = self.application_services
        records = services.library_registry.list_libraries()
        selected_id = self.diagnostics_library_selector.currentData()
        self.diagnostics_library_selector.blockSignals(True)
        self.diagnostics_library_selector.clear()
        for record in records:
            self.diagnostics_library_selector.addItem(f"{record.display_name} — {record.library_id}", record.library_id)
        if selected_id:
            index = self.diagnostics_library_selector.findData(selected_id)
            if index >= 0:
                self.diagnostics_library_selector.setCurrentIndex(index)
        self.diagnostics_library_selector.blockSignals(False)
        snapshot = memory_review_performance_snapshot()
        timings = snapshot["timings"]
        counters = snapshot["counters"]
        readable_order = (
            "Memory Review load", "Score retrieval", "Database reads",
            "Grid creation", "Filter update", "Sort update", "Selection update",
            "Ctrl-click selection", "Deselection", "Shift range selection",
            "Select all visible", "Clear selection", "Selection highlight update",
            "Selection highlight visible", "Selected-count label update",
            "Preview refresh", "Suggestion refresh", "Thumbnail refresh",
        )
        memory_lines = [selection_diagnostic_report(), "", "Recent aggregate timings (last / average / maximum)"]
        for name in readable_order:
            values = timings.get(name)
            if values is None:
                memory_lines.append(f"{name}: —")
            else:
                memory_lines.append(
                    f"{name}: {values['last_ms']:.1f} / {values['average_ms']:.1f} / "
                    f"{values['max_ms']:.1f} ms ({values['count']} samples)"
                )
        if counters:
            memory_lines.extend(("", "Update counters"))
            memory_lines.extend(f"{key}: {value}" for key, value in sorted(counters.items()))
        self.memory_review_performance_report.setPlainText("\n".join(memory_lines))
        store = services.metadata_store
        health = store.health_check() if store.library_id else None
        sync = store.incremental_sync_summary() if store.library_id else None
        values = {
            "Application data root": str(services.paths.root),
            "Registered library count": str(len(records)),
            "Active LibraryID": store.library_id or "No active library",
            "Active database path": str(store.database_path) if store.database_path else "No active database",
            "Schema version": str(health["schema_version"]) if health else "Not available",
            "Expected schema version": str(SCHEMA_VERSION),
            "Database health status": "Healthy" if health and health["healthy"] else ("Unhealthy" if health else "Not available"),
            "Integrity-check status": str(health["integrity_check"]) if health else "Not available",
            "Foreign-key-check status": str(health["foreign_key_check"]) if health else "Not available",
            "Migration-history status": ("Consistent" if health and health["migration_history_consistent"] else ("Inconsistent" if health else "Not available")),
            "Missing required tables": ", ".join(health["missing_required_tables"]) if health and health["missing_required_tables"] else "None",
            "Read availability": self._availability_text(health, "read_available"),
            "Write availability": self._availability_text(health, "write_available"),
            "Total registered photos": str(sync["total_photos"]) if sync else "Not available",
            "Active photos": str(sync["active_photos"]) if sync else "Not available",
            "Removed photos": str(sync["removed_photos"]) if sync else "Not available",
            "Last incremental sync": str(sync["last_incremental_sync"] or "Never") if sync else "Not available",
            "Last import summary": str(sync["last_import_summary"]) if sync else "Not available",
        }
        for key, value in values.items():
            self.diagnostics_labels[key].setText(value)
        active = bool(store.library_id)
        for button in (self.run_health_check_button, self.show_schema_summary_button,
                       self.create_backup_button, self.validate_backup_button,
                       self.open_database_folder_button):
            button.setEnabled(active)
        self.open_selected_library_button.setEnabled(bool(records))
        self._refresh_performance_history()

    def _refresh_performance_history(self) -> None:
        sessions = performance_history()
        current_id = self.performance_history_selector.currentData()
        self.performance_history_selector.blockSignals(True)
        self.performance_history_selector.clear()
        for session in reversed(sessions):
            self.performance_history_selector.addItem(
                f"{session.created_at} — {session.total_ms:.1f} ms", session.session_id)
        if current_id:
            index = self.performance_history_selector.findData(current_id)
            if index >= 0:
                self.performance_history_selector.setCurrentIndex(index)
        self.performance_history_selector.blockSignals(False)
        self._show_performance_session()

    def _selected_performance_session(self):
        session_id = self.performance_history_selector.currentData()
        return next((item for item in performance_history() if item.session_id == session_id), None)

    def _toggle_performance_details(self, expanded: bool) -> None:
        self.technical_details_toggle.setText(
            "▾ Technical Details" if expanded else "▸ Technical Details")
        self.import_performance_report.setVisible(expanded)

    @staticmethod
    def _reuse_status(counters: dict[str, int] | None) -> tuple[str, int]:
        """Translate existing counters into a Product Owner-facing reuse result."""
        if counters is None:
            return "No completed import", 0
        processed = max(0, int(counters.get("processed_photos", 0)))
        reused = min(processed, max(0, int(counters.get("reused_photos", 0))))
        if processed and reused == processed:
            return "Excellent reuse", 5
        if processed and reused * 4 >= processed * 3:
            return "Good reuse", 4
        if reused:
            return "Partial reuse", 3
        return "Full processing required", 1

    def _show_performance_session(self, _index: int = -1) -> None:
        session = self._selected_performance_session()
        if session is None:
            self.import_efficiency_status_banner.setText("— No completed import")
            self.import_efficiency_completion.setText("Complete an import to see how much work was reused.")
            for value in self.import_efficiency_values.values():
                value.setText("0")
            self.import_efficiency_result.setText("☆☆☆☆☆  No completed import")
            self.import_performance_summary.setText("Import completed in\n—\n\nSlowest activity\n—")
            self.import_performance_report.setPlainText("No technical details are available until an import completes.")
            self.export_performance_button.setEnabled(False)
            return
        counters = session.counters
        def average(stage_name: str) -> float:
            values = [stage.average_ms_per_item for stage in session.stages
                      if stage.name == stage_name and stage.average_ms_per_item is not None]
            return sum(values) / len(values) if values else 0.0
        processed = max(0, counters.get("processed_photos", 0))
        reused = min(processed, max(0, counters.get("reused_photos", 0)))
        status, stars = self._reuse_status(counters)
        dashboard_values = {
            "Photos processed": processed,
            "Already known photos": reused,
            "New photos": max(0, processed - reused),
            "Embeddings reused": counters.get("embedding_cache_hits", 0),
            "Thumbnails reused": counters.get("thumbnail_cache_hits", 0),
            "Database work avoided": counters.get("sqlite_queries_avoided", 0),
        }
        for label, value in dashboard_values.items():
            self.import_efficiency_values[label].setText(f"{value:,}")
        self.import_efficiency_status_banner.setText(f"✓  {status}")
        self.import_efficiency_completion.setText("Import completed successfully")
        self.import_efficiency_result.setText(f"{'★' * stars}{'☆' * (5 - stars)}  {status}")
        self.import_performance_summary.setText(
            f"Import completed in\n{session.total_ms / 1000:.2f} seconds\n\n"
            f"Slowest activity\n{session.identify_bottleneck() or 'Not available'}"
        )
        lines = [
            "All timings and developer counters",
            f"Photos processed: {processed}",
            f"Already known photos: {reused}",
            f"New photos: {max(0, processed - reused)}",
            f"Thumbnails reused: {counters.get('thumbnail_cache_hits', 0)}",
            f"Embeddings reused: {counters.get('embedding_cache_hits', 0)}",
            f"File checks avoided: {counters.get('filesystem_stat_calls_avoided', 0)}",
            f"Path processing avoided: {counters.get('path_resolutions_avoided', 0)}",
            f"Database queries avoided: {counters.get('sqlite_queries_avoided', 0)}",
            "",
            "Developer counters:",
        ]
        friendly_counter_keys = {
            "filesystem_stat_calls_avoided", "path_resolutions_avoided", "sqlite_queries_avoided"
        }
        lines.extend(
            f"{key}: {value}" for key, value in sorted(counters.items())
            if key not in friendly_counter_keys
        )
        lines.extend([
            "",
            "Timing averages",
            f"Photos newly embedded: {counters.get('embedded_photos', 0)}",
            f"Thumbnails generated: {counters.get('thumbnails_generated', 0)}",
            f"Average embedding time: {average('Embedding execution'):.2f} ms/item",
            f"Average thumbnail time: {average('Thumbnail generation'):.2f} ms/item",
            f"Average DB write: {average('SQLite writes'):.2f} ms/item",
            f"Average DB read: {average('SQLite reads'):.2f} ms/item",
            "", "Per-stage timings:",
        ])
        lines.extend(
            f"{stage.name}: {stage.elapsed_ms:.1f} ms "
            f"({stage.elapsed_ms * 100 / session.total_ms if session.total_ms else 0:.1f}%) · "
            f"items={stage.item_count} · avg={stage.average_ms_per_item or 0:.2f} ms/item · {stage.thread_kind}"
            for stage in session.stages
        )
        self.import_performance_report.setPlainText("\n".join(lines))
        self.export_performance_button.setEnabled(True)

    def _export_performance_report(self) -> None:
        session = self._selected_performance_session()
        if session is None:
            return
        selected, _ = QFileDialog.getSaveFileName(
            self, "Export Performance Report", "import-performance-report.json", "JSON (*.json)")
        if selected:
            library_size = session.get_counter("processed_photos")
            export_performance_report(selected, session, library_size)
            self._set_diagnostics_status(f"Performance report exported to {selected}")

    @staticmethod
    def _availability_text(health: dict[str, object] | None, key: str) -> str:
        return "Available" if health and health[key] else ("Unavailable" if health else "Not available")

    def register_test_library(self, source_root: str | Path) -> str | None:
        """Register/open an explicitly chosen root without scanning or touching it."""
        try:
            record = self.application_services.library_registry.register(source_root)
            store = self.application_services.metadata_store
            if store.library_id and store.library_id != record.library_id:
                store.close_library()
            store.open_library(record.library_id)
            self._set_diagnostics_status(f"Test library ready. Schema version {store.get_schema_version()}.")
            self.refresh_developer_diagnostics()
            return record.library_id
        except (StorageError, OSError, ValueError) as exc:
            self._set_diagnostics_status(f"The test library could not be registered: {exc}")
            self.refresh_developer_diagnostics()
            return None

    def _choose_test_library(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select an empty test library folder")
        if selected:
            self.register_test_library(selected)

    def _open_selected_library(self) -> None:
        library_id = self.diagnostics_library_selector.currentData()
        if not library_id:
            self._set_diagnostics_status("Select a registered library first."); return
        try:
            store = self.application_services.metadata_store
            if store.library_id and store.library_id != library_id:
                store.close_library()
            store.open_library(library_id)
            self._set_diagnostics_status("Selected library opened successfully.")
        except StorageError as exc:
            self._set_diagnostics_status(f"The selected library could not be opened: {exc}")
        self.refresh_developer_diagnostics()

    def _run_health_check(self) -> None:
        try:
            health = self.application_services.metadata_store.health_check()
            lines = ["Database health: " + ("Healthy" if health["healthy"] else "Unhealthy")]
            lines += [f"Integrity check: {health['integrity_check']}", f"Foreign-key check: {health['foreign_key_check']}",
                      f"Migration history: {'Consistent' if health['migration_history_consistent'] else 'Inconsistent'}"]
            self.diagnostics_report.setPlainText("\n".join(lines))
            self._set_diagnostics_status(lines[0])
        except StorageError as exc:
            self._set_diagnostics_status(f"Health check could not run: {exc}")
        self.refresh_developer_diagnostics()

    def _show_schema_summary(self) -> None:
        summary = self.application_services.metadata_store.schema_summary()
        migrations = ", ".join(f"{item['version']}: {item['name']}" for item in summary["migrations"])
        missing = ", ".join(summary["missing_required_tables"]) or "None"
        self.diagnostics_report.setPlainText(
            f"Schema version: {summary['schema_version']}\nExpected schema version: {summary['expected_schema_version']}\n"
            f"Required tables: {summary['required_table_count']}\nMissing tables: {missing}\nMigrations: {migrations}"
        )
        self._set_diagnostics_status("Schema summary displayed.")

    def create_backup(self, destination: str | Path) -> bool:
        try:
            result = self.application_services.metadata_store.backup(destination)
            self._set_diagnostics_status(f"Backup created successfully. Schema version {result.schema_version}.")
            return True
        except StorageError as exc:
            self._set_diagnostics_status(f"Backup was not created: {exc}")
            return False

    def _choose_backup_destination(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(self, "Create metadata backup", "family_memory-backup.db", "SQLite database (*.db)")
        if selected:
            self.create_backup(selected)

    def validate_backup(self, candidate: str | Path) -> bool:
        try:
            result = self.application_services.metadata_store.validate_backup(candidate)
            self._set_diagnostics_status(f"Backup is valid. Schema version {result.schema_version}; integrity {result.integrity}.")
            return True
        except StorageError as exc:
            self._set_diagnostics_status(f"Backup is invalid: {exc}")
            return False

    def _choose_backup_to_validate(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "Validate metadata backup", "", "SQLite database (*.db);;All files (*)")
        if selected:
            self.validate_backup(selected)

    @staticmethod
    def _open_folder(path: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _open_application_data_folder(self) -> None:
        self._open_folder(self.application_services.paths.root)

    def _open_database_folder(self) -> None:
        path = self.application_services.metadata_store.database_path
        if path:
            self._open_folder(path.parent)

    def diagnostic_report_text(self) -> str:
        return "\n".join(f"{key}: {label.text()}" for key, label in self.diagnostics_labels.items())

    def _copy_diagnostic_report(self) -> None:
        QGuiApplication.clipboard().setText(self.diagnostic_report_text())
        self._set_diagnostics_status("Diagnostic report copied to the clipboard.")

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

    def start_mobileclip_verification_recovery(self) -> None:
        """Display and run recovery already authorized by app composition."""
        self.runtime_step_label.setText("Current step: starting verification recovery")
        self.ai_plan_box.append(
            "The previous session did not leave a usable verified runtime. "
            "Verifying the configured runtime again."
        )
        self._refresh_mobileclip_status()
        self._start_ai_runtime_operation("verify")

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
        self._active_runtime_operation = operation
        self._set_runtime_buttons_enabled(False)
        self.runtime_progress_bar.setRange(0, 0)
        thread.start()

    def _clear_ai_runtime_worker(self) -> None:
        completed_operation = self._active_runtime_operation or ""
        self._active_runtime_thread = None
        self._active_runtime_worker = None
        self._active_cancel_event = None
        self._active_runtime_operation = None
        self._set_runtime_buttons_enabled(True)
        self.runtime_progress_bar.setRange(0, 1); self.runtime_progress_bar.setValue(1)
        self._refresh_mobileclip_status()
        self.runtime_operation_finished.emit(completed_operation)

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

    def _delete_face_analysis(self) -> None:
        message = ("This removes face detections, crops, embeddings, clusters, suggestions, and "
                   "confirmed person assignments. Original photos, categories, cleanup history, "
                   "and album decisions remain untouched.")
        if QMessageBox.warning(self, "Delete all face analysis data?", message,
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                               QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return
        from faces.persistence import SQLiteFaceRepository
        from faces.processing import FaceCropCache
        SQLiteFaceRepository().clear_face_analysis()
        FaceCropCache().clear()
        QMessageBox.information(self, "Face analysis deleted", "Face analysis data was deleted. Original photos were not changed.")

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

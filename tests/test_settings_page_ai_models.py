from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_settings_page_source_refresh_widgets_exist_before_default_radio_checked():
    source = Path("src/ui/settings_page.py").read_text(encoding="utf-8")
    run_button_pos = source.index('self.run_button = QPushButton("Run MobileCLIP evaluation")')
    select_folder_pos = source.index('self.select_folder_button = QPushButton("Choose another folder…")')
    source_summary_pos = source.index('self.source_summary = QLabel("")')
    checked_pos = source.index('self.library_radio.setChecked(True)')
    assert run_button_pos < checked_pos
    assert select_folder_pos < checked_pos
    assert source_summary_pos < checked_pos


def test_settings_page_can_be_constructed_without_attribute_error(monkeypatch, tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from ui.settings_page import SettingsPage
    except ImportError as exc:
        pytest.skip(f"PySide6 unavailable in this environment: {exc}")

    monkeypatch.setenv("FAMILY_MEMORY_APP_DATA_ROOT", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    page = SettingsPage()

    assert hasattr(page, "run_button")
    assert hasattr(page, "select_folder_button")
    assert hasattr(page, "source_summary")
    assert page.ai_detail_labels["Status"].text()
    assert page.ai_detail_labels["Checkpoint"].text()
    page.deleteLater()


def test_ai_models_metadata_source_includes_required_visible_rows():
    source = Path("src/ui/settings_page.py").read_text(encoding="utf-8")
    for label in (
        "Provider",
        "Status",
        "Python environment",
        "Python version",
        "Provider revision",
        "Model path",
        "Checkpoint",
        "Capabilities",
        "Device",
        "Installed packages",
        "Checkpoint status",
        "Last verification",
        "Last error",
    ):
        assert f'"{label}"' in source


def test_ai_models_metadata_rows_receive_positive_layout_height(monkeypatch, tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication, QGridLayout
    except ImportError as exc:
        pytest.skip(f"PySide6 unavailable in this environment: {exc}")
    from ui.settings_page import SettingsPage

    monkeypatch.setenv("FAMILY_MEMORY_APP_DATA_ROOT", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    page = SettingsPage()
    page.resize(900, 900)
    page.show()
    app.processEvents()

    details_layout = page.ai_details_widget.layout()
    assert isinstance(details_layout, QGridLayout)
    assert page.ai_details_widget.height() > 0
    assert page.ai_details_widget.height() >= page.ai_details_widget.minimumSizeHint().height()
    assert page.ai_details_widget.height() >= page.ai_details_widget.sizeHint().height() * 0.75
    assert page.ai_details_widget.height() > 120
    assert page.ai_models_card.height() > 75

    last_metadata_bottom = 0
    for row, key in enumerate(page.ai_detail_labels):
        key_label = page.ai_detail_key_labels[key]
        value_label = page.ai_detail_labels[key]
        assert key_label.height() > 0, f"{key} key label collapsed to zero height"
        assert value_label.height() > 0, f"{key} value label collapsed to zero height"
        assert details_layout.itemAtPosition(row, 0).widget() is key_label
        assert details_layout.itemAtPosition(row, 1).widget() is value_label
        last_metadata_bottom = max(
            last_metadata_bottom,
            key_label.mapTo(page.ai_models_card, key_label.rect().bottomLeft()).y(),
            value_label.mapTo(page.ai_models_card, value_label.rect().bottomLeft()).y(),
        )

    actions_top = page.ai_actions_label.mapTo(page.ai_models_card, page.ai_actions_label.rect().topLeft()).y()
    assert actions_top > last_metadata_bottom
    page.close()
    page.deleteLater()


def test_ai_models_card_uses_targeted_stylesheet_and_diagnostics_source_is_present():
    source = Path("src/ui/settings_page.py").read_text(encoding="utf-8")
    assert 'setObjectName("aiModelsCard")' in source
    assert 'setStyleSheet("#aiModelsCard {' in source
    assert 'setStyleSheet("QFrame {' not in source
    assert 'dump_ai_metadata_button = QPushButton("Dump AI metadata diagnostics")' in source
    assert "def _build_ai_metadata_diagnostics_report" in source
    assert "logger.info" in source


def test_ai_models_diagnostics_report_is_generated(monkeypatch, tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    QApplication = widgets.QApplication
    from ui.settings_page import SettingsPage

    monkeypatch.setenv("FAMILY_MEMORY_APP_DATA_ROOT", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    page = SettingsPage()
    page.show()
    app.processEvents()

    report = page._build_ai_metadata_diagnostics_report()
    assert "AI metadata diagnostics" in report
    assert "Row count:" in report
    assert "Widget count:" in report
    assert "Provider" in report
    assert "key_is_grid_item=True" in report
    assert "value_is_grid_item=True" in report
    page.dump_ai_metadata_button.click()
    assert "AI metadata diagnostics" in page.ai_plan_box.toPlainText()
    page.close()
    page.deleteLater()


def test_ai_models_source_orders_section_controls_before_evaluation():
    source = Path("src/ui/settings_page.py").read_text(encoding="utf-8")
    metadata_pos = source.index("card_layout.addWidget(self.ai_details_widget)")
    description_pos = source.index("card_layout.addWidget(self.mobileclip_status)")
    actions_text_pos = source.index("card_layout.addWidget(self.ai_actions_label)")
    buttons_pos = source.index("card_layout.addLayout(action_layout)")
    diagnostics_pos = source.index("card_layout.addWidget(self.dump_ai_metadata_button)")
    environment_pos = source.index("card_layout.addLayout(env_layout)")
    plan_pos = source.index("card_layout.addWidget(self.ai_plan_box)")
    evaluation_pos = source.index('self.mobileclip_evaluation_title = QLabel("MobileCLIP Local Evaluation (evaluation-only)")')
    assert metadata_pos < description_pos < actions_text_pos < buttons_pos < diagnostics_pos < environment_pos < plan_pos < evaluation_pos
    assert "QScrollArea" in source
    assert "setWidgetResizable(True)" in source
    assert 'self.settings_scroll_area.setWidget(self.settings_scroll_content)' in source


def test_ai_models_widget_order_has_no_overlap(monkeypatch, tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    QApplication = widgets.QApplication
    from ui.settings_page import SettingsPage

    monkeypatch.setenv("FAMILY_MEMORY_APP_DATA_ROOT", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    page = SettingsPage()
    page.resize(640, 420)
    page.show()
    app.processEvents()

    widgets = [
        page.ai_details_widget,
        page.mobileclip_status,
        page.ai_actions_label,
        page.install_button,
        page.dump_ai_metadata_button,
        page.ai_env_input,
        page.ai_plan_box,
    ]
    bottoms = []
    for widget in widgets:
        assert widget.height() > 0
        top = widget.mapTo(page.settings_scroll_content, widget.rect().topLeft()).y()
        bottom = widget.mapTo(page.settings_scroll_content, widget.rect().bottomLeft()).y()
        assert bottom >= top
        bottoms.append((top, bottom))

    for (_, previous_bottom), (next_top, _) in zip(bottoms, bottoms[1:]):
        assert next_top > previous_bottom

    card_bottom = page.ai_models_card.mapTo(page.settings_scroll_content, page.ai_models_card.rect().bottomLeft()).y()
    evaluation_top = page.mobileclip_evaluation_title.mapTo(page.settings_scroll_content, page.mobileclip_evaluation_title.rect().topLeft()).y()
    assert evaluation_top > card_bottom
    page.close()
    page.deleteLater()



def test_view_installation_plan_starts_worker_instead_of_building_on_ui_thread():
    source = Path("src/ui/settings_page.py").read_text(encoding="utf-8")
    show_body = source[source.index("def _show_ai_installation_plan"):source.index("def _set_runtime_buttons_enabled")]

    assert "Inspecting MobileCLIP environment and building installation plan" in show_body
    assert "build_installation_plan" not in show_body
    assert '_start_ai_runtime_operation("build_plan", interpreter=interpreter)' in show_body


def test_worker_completion_displays_final_installation_plan():
    source = Path("src/ui/settings_page.py").read_text(encoding="utf-8")
    completed_body = source[source.index("def _on_ai_runtime_completed"):source.index("def _on_ai_runtime_failed")]
    formatter_body = source[source.index("def _format_ai_installation_plan"):source.index("def _show_ai_installation_plan")]

    assert 'operation == "build_plan" and isinstance(result, AIRuntimeInstallationPlan)' in completed_body
    assert "self._last_installation_plan = result" in completed_body
    assert "self.ai_plan_box.setPlainText(self._format_ai_installation_plan(result))" in completed_body
    assert "Packages: {', '.join(plan.packages_to_install) or 'none'}" in formatter_body
    assert "Model files: {', '.join(plan.model_files_to_download) or 'none'}" in formatter_body
    assert "Warnings:" in formatter_body


def test_failure_path_restores_ui_state():
    source = Path("src/ui/settings_page.py").read_text(encoding="utf-8")
    failed_body = source[source.index("def _on_ai_runtime_failed"):source.index("def _cancel_ai_runtime_operation")]
    cleanup_body = source[source.index("def _clear_ai_runtime_worker"):source.index("def _on_ai_runtime_progress")]
    start_body = source[source.index("def _start_ai_runtime_operation"):source.index("def _clear_ai_runtime_worker")]

    assert "self.ai_plan_box.append(f\"AI runtime operation failed: {error}\")" in failed_body
    assert "worker.finished.connect(thread.quit, Qt.ConnectionType.QueuedConnection)" in start_body
    assert "thread.finished.connect(self._clear_ai_runtime_worker, Qt.ConnectionType.QueuedConnection)" in start_body
    assert "self._active_runtime_thread = None" in cleanup_body
    assert "self._active_runtime_worker = None" in cleanup_body
    assert "self._set_runtime_buttons_enabled(True)" in cleanup_body

def test_installation_plan_source_uses_existing_worker_thread_pattern():
    source = Path("src/ui/settings_page.py").read_text(encoding="utf-8")
    worker_source = Path("src/workers/ai_runtime_worker.py").read_text(encoding="utf-8")
    show_body = source[source.index("def _show_ai_installation_plan"):source.index("def _set_runtime_buttons_enabled")]

    assert "Inspecting MobileCLIP environment and building installation plan" in show_body
    assert "build_installation_plan" not in show_body
    assert '_start_ai_runtime_operation("build_plan"' in show_body
    assert 'if self.operation == "build_plan"' in worker_source
    assert "manager.build_installation_plan(self.provider_id, self.interpreter)" in worker_source
    assert "completed = Signal(str, object)" in worker_source
    assert "self.completed.emit(self.operation, result)" in worker_source


def test_ai_runtime_worker_signals_are_queued_to_prevent_windows_qtextdocument_thread_error():
    source = Path("src/ui/settings_page.py").read_text(encoding="utf-8")
    start_body = source[source.index("def _start_ai_runtime_operation"):source.index("def _clear_ai_runtime_worker")]

    assert "QObject: Cannot create children for a parent that is in a different thread."
    assert "worker.progress.connect(self._on_ai_runtime_progress, Qt.ConnectionType.QueuedConnection)" in start_body
    assert "worker.current_step.connect(self._on_ai_runtime_current_step, Qt.ConnectionType.QueuedConnection)" in start_body
    assert "worker.completed.connect(self._on_ai_runtime_completed, Qt.ConnectionType.QueuedConnection)" in start_body
    assert "worker.failed.connect(self._on_ai_runtime_failed, Qt.ConnectionType.QueuedConnection)" in start_body
    assert "lambda step: self.runtime_step_label.setText" not in start_body
    assert "lambda result" not in start_body

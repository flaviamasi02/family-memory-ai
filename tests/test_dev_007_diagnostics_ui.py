from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.application_data import ApplicationDataPathService
from core.application_services import ApplicationServices
from storage.library_registry import LibraryRegistry
from storage.metadata_store import MetadataStore
from storage.schema import SCHEMA_VERSION


@pytest.fixture
def page(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    QApplication = widgets.QApplication
    from ui.settings_page import SettingsPage
    from core.perf_stats import clear_performance_history

    monkeypatch.setenv("FAMILY_MEMORY_APP_DATA_ROOT", str(tmp_path / "runtime"))
    clear_performance_history()
    paths = ApplicationDataPathService(tmp_path / "app")
    registry = LibraryRegistry(paths)
    services = ApplicationServices(paths, registry, MetadataStore(paths, registry))
    app = QApplication.instance() or QApplication([])
    result = SettingsPage(application_services=services)
    yield result, services, app, tmp_path
    result.close()
    services.close()
    result.deleteLater()
    clear_performance_history()


def test_section_present_collapsed_and_safe_without_active_library(page):
    widget, _, _, _ = page
    assert widget.developer_diagnostics_toggle.text() == "Developer Diagnostics"
    assert not widget.developer_diagnostics_panel.isVisible()
    assert widget.diagnostics_labels["Active LibraryID"].text() == "No active library"
    assert widget.diagnostics_labels["Active database path"].text() == "No active database"
    assert not widget.run_health_check_button.isEnabled()
    diagnostics_actions = [button.text() for button in widget.developer_diagnostics_panel.findChildren(type(widget.diagnostics_refresh_button))]
    assert "Restore" not in diagnostics_actions
    assert "Delete" not in diagnostics_actions


def test_import_performance_title_has_valid_point_size(page):
    widget, _, _, _ = page
    font = widget.import_performance_title.font()
    assert font.pointSizeF() > 0
    assert font.bold()
    # Pixel-sized QSS fonts report pointSizeF() == -1 and caused Qt's warning
    # when its stylesheet-resolved title font was copied internally.
    assert "font-size" not in widget.import_performance_title.styleSheet()


def test_memory_review_selection_measurement_controls_default_off(page):
    widget, _, _, _ = page
    assert widget.measure_memory_review_selection_button.text() == "Measure Memory Review selection"
    assert "Open Memory Review" in widget.memory_review_measurement_instructions.text()
    assert all(not checkbox.isChecked() for checkbox in widget.selection_diagnostic_bypasses.values())
    widget.measure_memory_review_selection_button.click()
    assert "measurement armed" in widget.diagnostics_status_label.text().lower()
    widget.refresh_developer_diagnostics()
    assert "Waiting for Memory Review selection..." in widget.memory_review_performance_report.toPlainText()


def test_import_performance_summary_does_not_show_raw_html(page):
    widget, _, _, _ = page
    assert "<b>" not in widget.import_performance_summary.text()


def test_import_efficiency_no_session_is_clear_and_explained(page):
    widget, _, _, _ = page
    report = widget.import_performance_report.toPlainText()
    assert widget.import_efficiency_title.text().endswith("Import Efficiency")
    assert "No completed import" in widget.import_efficiency_status_banner.text()
    assert "No technical details" in report
    assert not widget.import_performance_report.isVisible()
    tooltip = widget.import_performance_report.toolTip()
    for label in (
        "Already known photos", "New photos", "Thumbnails reused", "Embeddings reused",
        "File checks avoided", "Path processing avoided", "Database queries avoided",
    ):
        assert f"{label}:" in tooltip


def test_import_efficiency_uses_friendly_labels_and_keeps_timing_detail(page):
    widget, _, app, _ = page
    from core.perf_stats import begin_import_performance_session, finish_import_performance_session
    session = begin_import_performance_session("/test")
    for key, value in {
        "processed_photos": 10, "reused_photos": 9, "thumbnail_cache_hits": 10,
        "embedding_cache_hits": 10, "filesystem_stat_calls_avoided": 10,
        "path_resolutions_avoided": 20, "sqlite_queries_avoided": 4,
    }.items():
        session.inc(key, value)
    session.record("SQLite reads", 1.25, 1, "Background thread")
    finish_import_performance_session()
    widget.refresh_developer_diagnostics()
    report = widget.import_performance_report.toPlainText()
    assert "Good reuse" in widget.import_efficiency_status_banner.text()
    assert widget.import_efficiency_values["Photos processed"].text() == "10"
    assert widget.import_efficiency_values["Already known photos"].text() == "9"
    assert widget.import_efficiency_values["New photos"].text() == "1"
    assert widget.import_efficiency_values["Embeddings reused"].text() == "10"
    assert "seconds" in widget.import_performance_summary.text()
    for text in (
        "Photos processed: 10", "Already known photos: 9", "Thumbnails reused: 10",
        "Embeddings reused: 10", "File checks avoided: 10",
        "Path processing avoided: 20", "Database queries avoided: 4",
        "Per-stage timings:", "Developer counters:",
        "SQLite reads:",
    ):
        assert text in report
    assert "filesystem_stat_calls_avoided" not in report
    assert "path_resolutions_avoided" not in report
    assert "sqlite_queries_avoided" not in report
    # QWidget.isVisible() includes ancestor visibility. Exercise the actual UI
    # lifecycle rather than inspecting a child of the intentionally collapsed
    # Developer Diagnostics panel.
    assert not widget.technical_details_toggle.isChecked()
    assert widget.import_performance_report.isHidden()
    assert widget.technical_details_toggle.text() == "▸ Technical Details"
    widget.show()
    widget.developer_diagnostics_toggle.click()
    app.processEvents()
    widget.technical_details_toggle.click()
    app.processEvents()
    assert widget.import_performance_report.isVisible()
    assert widget.technical_details_toggle.text() == "▾ Technical Details"
    widget.technical_details_toggle.click()
    app.processEvents()
    assert widget.import_performance_report.isHidden()
    assert widget.technical_details_toggle.text() == "▸ Technical Details"


def test_import_efficiency_status_levels_are_deterministic(page):
    widget, _, _, _ = page
    assert widget._reuse_status(None) == ("No completed import", 0)
    assert widget._reuse_status({"processed_photos": 10}) == ("Full processing required", 1)
    assert widget._reuse_status({"processed_photos": 10, "reused_photos": 2}) == ("Partial reuse", 3)
    assert widget._reuse_status({"processed_photos": 10, "reused_photos": 8}) == ("Good reuse", 4)
    assert widget._reuse_status({"processed_photos": 10, "reused_photos": 10}) == ("Excellent reuse", 5)


def test_refresh_register_reuse_health_schema_and_source_unchanged(page):
    widget, services, _, tmp_path = page
    source = tmp_path / "empty-test-library"
    source.mkdir()
    before = list(source.iterdir())
    first = widget.register_test_library(source)
    second = widget.register_test_library(source)
    assert first == second
    assert len(services.library_registry.list_libraries()) == 1
    assert list(source.iterdir()) == before
    assert widget.diagnostics_labels["Schema version"].text() == str(SCHEMA_VERSION)
    assert widget.diagnostics_labels["Database health status"].text() == "Healthy"
    widget._run_health_check()
    assert "Database health: Healthy" in widget.diagnostics_report.toPlainText()
    widget._show_schema_summary()
    summary = widget.diagnostics_report.toPlainText()
    assert f"Schema version: {SCHEMA_VERSION}" in summary
    assert "Required tables: 17" in summary
    assert "1: data_001a_foundation" in summary
    assert "2: data_001b_full_schema" in summary
    assert "3: data_001c_import_registration" in summary
    assert "4: data_001d_incremental_photo_sync" in summary
    assert "5: data_001d_classification_snapshot" in summary
    widget.refresh_developer_diagnostics()
    assert widget.diagnostics_labels["Registered library count"].text() == "1"


def test_backup_validate_conflict_invalid_and_clipboard(page):
    widget, _, app, tmp_path = page
    source = tmp_path / "source"; source.mkdir()
    assert widget.register_test_library(source)
    backup = tmp_path / "backup.db"
    assert widget.create_backup(backup)
    assert not widget.create_backup(backup)
    assert "not created" in widget.diagnostics_status_label.text()
    assert widget.validate_backup(backup)
    invalid = tmp_path / "invalid.db"; invalid.write_text("not sqlite")
    assert not widget.validate_backup(invalid)
    widget._copy_diagnostic_report()
    assert app.clipboard().text() == widget.diagnostic_report_text()
    assert "Application data root:" in app.clipboard().text()
    assert "embedding" not in app.clipboard().text().lower()


def test_unavailable_registered_library_is_reported_without_traceback(page):
    widget, services, _, tmp_path = page
    source = tmp_path / "temporary"; source.mkdir()
    record = services.library_registry.register(source)
    source.rmdir()
    widget.refresh_developer_diagnostics()
    index = widget.diagnostics_library_selector.findData(record.library_id)
    widget.diagnostics_library_selector.setCurrentIndex(index)
    widget._open_selected_library()
    assert "could not be opened" in widget.diagnostics_status_label.text()
    assert widget.diagnostics_labels["Active LibraryID"].text() == "No active library"


def test_settings_reopen_and_refresh_preserve_imported_active_context(page):
    widget, services, _, tmp_path = page
    source = tmp_path / "imported"; source.mkdir()
    record = services.open_or_register_library(source)
    widget.refresh_developer_diagnostics()
    assert widget.diagnostics_labels["Active LibraryID"].text() == record.library_id
    assert widget.diagnostics_labels["Schema version"].text() == str(SCHEMA_VERSION)
    assert widget.diagnostics_labels["Database health status"].text() == "Healthy"

    from ui.settings_page import SettingsPage
    reopened = SettingsPage(application_services=services)
    try:
        reopened.refresh_developer_diagnostics()
        assert reopened.diagnostics_labels["Active LibraryID"].text() == record.library_id
        assert reopened.diagnostics_labels["Active database path"].text() != "No active database"
        assert reopened.diagnostics_labels["Schema version"].text() == "5"
    finally:
        reopened.close(); reopened.deleteLater()


def test_ui_uses_storage_services_not_sqlite_directly():
    source = Path("src/ui/settings_page.py").read_text(encoding="utf-8")
    assert "sqlite3" not in source
    assert ".backup(" in source and ".validate_backup(" in source
    assert "Restore" not in source[source.index("def _build_developer_diagnostics"):source.index("def set_evaluation_context_providers")]

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

    monkeypatch.setenv("FAMILY_MEMORY_APP_DATA_ROOT", str(tmp_path / "runtime"))
    paths = ApplicationDataPathService(tmp_path / "app")
    registry = LibraryRegistry(paths)
    services = ApplicationServices(paths, registry, MetadataStore(paths, registry))
    app = QApplication.instance() or QApplication([])
    result = SettingsPage(application_services=services)
    yield result, services, app, tmp_path
    result.close()
    services.close()
    result.deleteLater()


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


def test_ui_uses_storage_services_not_sqlite_directly():
    source = Path("src/ui/settings_page.py").read_text(encoding="utf-8")
    assert "sqlite3" not in source
    assert ".backup(" in source and ".validate_backup(" in source
    assert "Restore" not in source[source.index("def _build_developer_diagnostics"):source.index("def set_evaluation_context_providers")]

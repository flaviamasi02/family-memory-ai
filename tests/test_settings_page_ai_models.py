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

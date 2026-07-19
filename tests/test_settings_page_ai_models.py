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

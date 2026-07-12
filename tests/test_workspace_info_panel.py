import os
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QProgressBar

from ui.components.workspace_info_panel import WorkspaceInfoPanel

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class WorkspaceInfoPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _settings_for_file(self, settings_file: Path) -> QSettings:
        settings = QSettings(str(settings_file), QSettings.Format.IniFormat)
        settings.clear()
        settings.sync()
        return settings

    def test_panel_builds_with_title_purpose_actions_and_tip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = self._settings_for_file(Path(tmpdir) / "panel.ini")
            panel = WorkspaceInfoPanel(
                workspace_id="photo_browser",
                title="Photo Browser",
                purpose="Browse imported media.",
                purpose_details="Inspect details and metadata for each item.",
                typical_actions=["Browse imported photos", "Filter the library"],
                tip="Open Workspace Help for complete details.",
                settings=settings,
            )

            self.assertTrue(panel.is_expanded())
            self.assertEqual(panel.workspace_title_label.text(), "Photo Browser")
            self.assertIn("Browse imported media", panel.purpose_label.text())
            self.assertIn("Inspect details", panel.purpose_details_label.text())
            self.assertIn("Browse imported photos", panel.actions_label.text())
            self.assertIn("Open Workspace Help", panel.tip_label.text())

    def test_collapsing_hides_details_and_keeps_compact_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = self._settings_for_file(Path(tmpdir) / "panel.ini")
            panel = WorkspaceInfoPanel(
                workspace_id="memory_review",
                title="Memory Review",
                purpose="Teach Family Memory AI.",
                purpose_details="Review and correct memory candidates.",
                typical_actions=["Review potential family memories"],
                tip="Open Workspace Help for complete details.",
                settings=settings,
            )

            panel.set_expanded(False)

            self.assertFalse(panel.is_expanded())
            self.assertTrue(panel.details_container.isHidden())
            self.assertIn("Memory Review", panel.toggle_button.text())
            self.assertTrue(panel.toggle_button.text().startswith("▶"))

    def test_expanding_restores_detailed_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = self._settings_for_file(Path(tmpdir) / "panel.ini")
            panel = WorkspaceInfoPanel(
                workspace_id="cleanup_review",
                title="Cleanup Review",
                purpose="Review cleanup candidates.",
                purpose_details="You stay in control of media decisions.",
                typical_actions=["Review cleanup suggestions"],
                tip="Open Workspace Help for complete details.",
                settings=settings,
            )

            panel.set_expanded(False)
            panel.set_expanded(True)

            self.assertTrue(panel.is_expanded())
            self.assertFalse(panel.details_container.isHidden())
            self.assertTrue(panel.toggle_button.text().startswith("▼"))
            self.assertIn("Review cleanup suggestions", panel.actions_label.text())

    def test_state_persists_independently_per_workspace_identifier(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "panel.ini"
            shared_settings = QSettings(str(settings_file), QSettings.Format.IniFormat)
            shared_settings.clear()
            shared_settings.sync()

            panel_a = WorkspaceInfoPanel(
                workspace_id="photo_browser",
                title="Photo Browser",
                purpose="A",
                purpose_details="A details",
                typical_actions=["A action"],
                tip="A tip",
                settings=shared_settings,
            )
            panel_b = WorkspaceInfoPanel(
                workspace_id="settings",
                title="Settings",
                purpose="B",
                purpose_details="B details",
                typical_actions=["B action"],
                tip="B tip",
                settings=shared_settings,
            )
            panel_a.set_expanded(False)
            panel_b.set_expanded(True)

            reloaded_a = WorkspaceInfoPanel(
                workspace_id="photo_browser",
                title="Photo Browser",
                purpose="A",
                purpose_details="A details",
                typical_actions=["A action"],
                tip="A tip",
                settings=QSettings(str(settings_file), QSettings.Format.IniFormat),
            )
            reloaded_b = WorkspaceInfoPanel(
                workspace_id="settings",
                title="Settings",
                purpose="B",
                purpose_details="B details",
                typical_actions=["B action"],
                tip="B tip",
                settings=QSettings(str(settings_file), QSettings.Format.IniFormat),
            )

            self.assertFalse(reloaded_a.is_expanded())
            self.assertTrue(reloaded_b.is_expanded())

    def test_new_workspace_defaults_to_expanded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = self._settings_for_file(Path(tmpdir) / "panel.ini")
            panel = WorkspaceInfoPanel(
                workspace_id="brand_new_workspace",
                title="Brand New",
                purpose="Purpose",
                purpose_details="Purpose details",
                typical_actions=["Action"],
                tip="Tip",
                settings=settings,
            )

            self.assertTrue(panel.is_expanded())

    def test_toggle_button_is_keyboard_accessible(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = self._settings_for_file(Path(tmpdir) / "panel.ini")
            panel = WorkspaceInfoPanel(
                workspace_id="album_draft",
                title="Album Draft",
                purpose="Purpose",
                purpose_details="Purpose details",
                typical_actions=["Action"],
                tip="Tip",
                settings=settings,
            )
            panel.show()
            panel.toggle_button.setFocus()
            self.assertEqual(panel.toggle_button.focusPolicy(), Qt.FocusPolicy.StrongFocus)

            before = panel.is_expanded()
            QTest.keyClick(panel.toggle_button, Qt.Key.Key_Space)
            self.assertNotEqual(before, panel.is_expanded())

    def test_panel_contains_no_progress_widget(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = self._settings_for_file(Path(tmpdir) / "panel.ini")
            panel = WorkspaceInfoPanel(
                workspace_id="memory_review",
                title="Memory Review",
                purpose="Purpose",
                purpose_details="Purpose details",
                typical_actions=["Action"],
                tip="Tip",
                settings=settings,
            )

            self.assertEqual(panel.findChildren(QProgressBar), [])


if __name__ == "__main__":
    unittest.main()

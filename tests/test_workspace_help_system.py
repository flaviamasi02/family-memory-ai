import os
import unittest

from PySide6.QtWidgets import QApplication

from ui.help.workspace_help_registry import WorkspaceHelpRegistry
from ui.main_window import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class WorkspaceHelpRegistryTests(unittest.TestCase):
    def test_registry_returns_all_main_workspace_definitions(self):
        registry = WorkspaceHelpRegistry()

        expected_ids = {
            "photo_browser",
            "memory_review",
            "cleanup_review",
            "album_draft",
            "settings",
        }

        self.assertTrue(expected_ids.issubset(set(registry.all_workspace_ids())))

        for workspace_id in expected_ids:
            definition = registry.get(workspace_id)
            self.assertTrue(definition.title)
            section_keys = {section.key for section in definition.sections}
            self.assertIn("purpose", section_keys)
            self.assertIn("workflow", section_keys)
            self.assertIn("best_practices", section_keys)
            self.assertIn("tips", section_keys)
            self.assertIn("ai_status", section_keys)


class WorkspaceHelpUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_main_window_contains_settings_tab_and_help_dock(self):
        window = MainWindow()

        tab_labels = [window.tabs.tabText(index) for index in range(window.tabs.count())]
        self.assertIn("Settings", tab_labels)
        self.assertEqual(window.tabs.count(), 5)
        self.assertFalse(window.workspace_help_dock.isVisible())

    def test_help_button_opens_contextual_help_dock(self):
        window = MainWindow()

        window.review_page.header.help_button.click()
        self.assertFalse(window.workspace_help_dock.isHidden())
        self.assertIn("Memory Review", window.workspace_help_panel.workspace_title_label.text())

        settings_index = next(
            index for index in range(window.tabs.count()) if window.tabs.tabText(index) == "Settings"
        )
        window.tabs.setCurrentIndex(settings_index)
        self.assertIn("Settings", window.workspace_help_panel.workspace_title_label.text())


if __name__ == "__main__":
    unittest.main()

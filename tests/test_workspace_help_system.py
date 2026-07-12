import os
import unittest

from PySide6.QtWidgets import QApplication

from ui.components.workspace_info_panel import WorkspaceInfoPanel
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

    def test_each_required_workspace_contains_workspace_info_panel(self):
        window = MainWindow()

        required_tabs = {
            "Photo Browser",
            "Memory Review",
            "Cleanup Review",
            "Album Draft",
            "Settings",
        }
        tab_labels = [window.tabs.tabText(index) for index in range(window.tabs.count())]
        self.assertEqual(tab_labels, ["Photo Browser", "Memory Review", "Cleanup Review", "Album Draft", "Settings"])
        self.assertEqual(set(tab_labels), required_tabs)

        panel_instances = window.findChildren(WorkspaceInfoPanel)
        self.assertEqual(len(panel_instances), 5)

        browser_panel = window.tabs.widget(0).findChild(WorkspaceInfoPanel)
        self.assertIsNotNone(browser_panel)
        self.assertEqual(browser_panel.workspace_id, "photo_browser")

        self.assertEqual(window.review_page.info_panel.workspace_id, "memory_review")
        self.assertEqual(window.irrelevant_media_page.info_panel.workspace_id, "cleanup_review")
        self.assertEqual(window.draft_page.info_panel.workspace_id, "album_draft")
        self.assertEqual(window.settings_page.info_panel.workspace_id, "settings")

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

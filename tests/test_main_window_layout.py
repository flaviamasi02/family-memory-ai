import os
import unittest

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class MainWindowLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_main_window_has_larger_minimum_size(self):
        window = MainWindow()
        minimum = window.minimumSize()

        self.assertGreaterEqual(minimum.width(), 1200)
        self.assertGreaterEqual(minimum.height(), 800)


if __name__ == "__main__":
    unittest.main()

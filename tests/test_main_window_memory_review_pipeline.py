import os
import tempfile
import unittest
from pathlib import Path

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from models.photo import Photo
from ui.main_window import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class MainWindowMemoryReviewPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _flush_ui(self, wait_ms: int = 0):
        if wait_ms > 0:
            QTest.qWait(wait_ms)
        for _ in range(12):
            self._app.processEvents()

    def _make_photo(self, root: Path, filename: str, *, date_taken: str | None, relevant: bool = True) -> Photo:
        path = root / filename
        path.write_bytes(b"img")
        photo = Photo.from_path(path)
        if date_taken is not None:
            photo.metadata["date_taken"] = date_taken
        else:
            photo.metadata.pop("date_taken", None)
        photo.metadata["is_album_relevant_candidate"] = bool(relevant)
        photo.sync_intelligence_from_metadata()
        return photo

    def test_valid_dated_imported_photos_produce_visible_rows_and_cards(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            one = self._make_photo(root, "one.jpg", date_taken="2024:01:10 10:00:00")
            two = self._make_photo(root, "two.jpg", date_taken="2024:02:10 10:00:00")

            window = MainWindow()
            window._all_photos = [one, two]
            window._load_album_review_data(relevant_photos=[one, two], imported_photos=[one, two])
            self._flush_ui(wait_ms=80)

            self.assertGreater(window.review_page.all_row_count(), 0)
            self.assertGreater(window.review_page.visible_row_count(), 0)
            self.assertGreater(window.review_page.rendered_card_count(), 0)

    def test_photos_without_usable_dates_show_clear_empty_state_reason(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            one = self._make_photo(root, "undated_1.jpg", date_taken=None)
            two = self._make_photo(root, "undated_2.jpg", date_taken=None)

            one.intelligence.year = None
            two.intelligence.year = None

            window = MainWindow()
            window._all_photos = [one, two]
            window._load_album_review_data(relevant_photos=[one, two], imported_photos=[one, two])
            self._flush_ui(wait_ms=80)

            self.assertEqual(window.review_page.all_row_count(), 0)
            self.assertIn("no photos with usable dates", window.review_page.results_label.text().lower())
            self.assertIn("imported=2", window.review_page.results_label.text().lower())
            self.assertIn("missing_year=2", window.review_page.results_label.text().lower())

    def test_default_filters_show_newly_loaded_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            one = self._make_photo(root, "default_filter.jpg", date_taken="2023:06:01 08:00:00")

            window = MainWindow()
            window._all_photos = [one]
            window._load_album_review_data(relevant_photos=[one], imported_photos=[one])
            self._flush_ui(wait_ms=80)

            self.assertEqual(window.review_page.filter_combo.currentText(), window.review_page.FILTER_ALL)
            self.assertEqual(window.review_page.category_filter_combo.currentText(), window.review_page.CATEGORY_FILTER_ALL)
            self.assertGreater(window.review_page.visible_row_count(), 0)


if __name__ == "__main__":
    unittest.main()

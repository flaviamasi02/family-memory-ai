import os
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from album.album_draft_builder import AlbumDraftBuilder
from album.album_scoring_engine import AlbumScoreBreakdown
from models.photo import Photo
from ui.album_draft_page import AlbumDraftPage
from ui.main_window import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class AlbumDraftPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _flush_ui(self, wait_ms: int = 0):
        if wait_ms > 0:
            QTest.qWait(wait_ms)
        for _ in range(12):
            self._app.processEvents()

    def _make_breakdown(
        self,
        root: Path,
        filename: str,
        score: float,
        date_taken: str | None,
    ) -> AlbumScoreBreakdown:
        path = root / filename
        path.write_bytes(b"image")
        photo = Photo.from_path(path)
        if date_taken is not None:
            photo.metadata["date_taken"] = date_taken
            photo.sync_intelligence_from_metadata()

        return AlbumScoreBreakdown(
            photo=photo,
            total_score=score,
            technical_score=score,
            memory_score=score,
            date_score=score,
            explanation=["score"],
        )

    def test_loading_a_draft_populates_summary_pages_and_details(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            jan = self._make_breakdown(root, "jan.jpg", 90, "2021:01:10 10:00:00")
            feb = self._make_breakdown(root, "feb.jpg", 80, "2021:02:10 10:00:00")

            result = AlbumDraftBuilder().build(
                2021,
                [jan, feb],
                {
                    str(jan.photo.path): "approved",
                    str(feb.photo.path): "approved",
                },
            )

            page = AlbumDraftPage()
            page.set_draft_result(result)
            self._flush_ui(wait_ms=40)

            self.assertFalse(page.is_empty_state_visible())
            self.assertEqual(page.year_value.text(), "2021")
            self.assertEqual(page.total_pages_value.text(), "2")
            self.assertEqual(page.total_included_value.text(), "2")
            self.assertEqual(page.source_photos_value.text(), "2")
            self.assertEqual(page.excluded_photos_value.text(), "0")
            self.assertEqual(page.page_titles(), ["January 2021 (1)", "February 2021 (1)"])
            self.assertEqual(page.current_page_title(), "January 2021")
            self.assertEqual(page.page_photo_count_value.text(), "1")
            self.assertEqual(page.page_type_value.text(), "month")
            self.assertGreater(page.page_explanations_list.count(), 0)

    def test_selecting_pages_refreshes_the_center_grid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            jan = self._make_breakdown(root, "jan.jpg", 90, "2021:01:10 10:00:00")
            feb_a = self._make_breakdown(root, "feb_a.jpg", 80, "2021:02:10 10:00:00")
            feb_b = self._make_breakdown(root, "feb_b.jpg", 70, "2021:02:11 10:00:00")

            result = AlbumDraftBuilder().build(
                2021,
                [jan, feb_a, feb_b],
                {
                    str(jan.photo.path): "approved",
                    str(feb_a.photo.path): "approved",
                    str(feb_b.photo.path): "approved",
                },
            )

            page = AlbumDraftPage()
            page.set_draft_result(result)
            self._flush_ui(wait_ms=40)

            self.assertTrue(page.select_page_by_title("February 2021"))
            self._flush_ui(wait_ms=40)

            self.assertEqual(page.current_page_title(), "February 2021")
            self.assertEqual(page.visible_photo_filenames(), ["feb_a.jpg", "feb_b.jpg"])

    def test_updating_thumbnails_refreshes_visible_photo_cards(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            jan = self._make_breakdown(root, "jan.jpg", 90, "2021:01:10 10:00:00")
            result = AlbumDraftBuilder().build(
                2021,
                [jan],
                {str(jan.photo.path): "approved"},
            )

            page = AlbumDraftPage()
            page.set_draft_result(result)
            self._flush_ui(wait_ms=60)

            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.GlobalColor.red)
            photo = result.draft.pages[0].photos[0]

            page.update_thumbnail(photo, pixmap)
            self._flush_ui(wait_ms=60)

            key = str(photo.path)
            card = page.photo_grid._cards_by_key.get(key)
            self.assertIsNotNone(card)
            self.assertIsNotNone(card.thumbnail_label.pixmap())
            self.assertFalse(card.thumbnail_label.pixmap().isNull())

    def test_statistics_are_updated_from_the_loaded_draft(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            items = [
                self._make_breakdown(root, "jan_a.jpg", 90, "2021:01:10 10:00:00"),
                self._make_breakdown(root, "jan_b.jpg", 85, "2021:01:11 10:00:00"),
                self._make_breakdown(root, "jan_c.jpg", 80, "2021:01:12 10:00:00"),
                self._make_breakdown(root, "feb.jpg", 70, "2021:02:10 10:00:00"),
            ]

            result = AlbumDraftBuilder().build(
                2021,
                items,
                {str(item.photo.path): "approved" for item in items},
            )

            page = AlbumDraftPage()
            page.set_draft_result(result)
            self._flush_ui(wait_ms=40)

            self.assertEqual(page.largest_month_value.text(), "January 2021 (3)")
            self.assertEqual(page.smallest_month_value.text(), "February 2021 (1)")
            self.assertEqual(page.average_per_page_value.text(), "2.0")

    def test_empty_draft_handling_shows_friendly_message(self):
        page = AlbumDraftPage()
        page.set_draft_result(None)
        self._flush_ui()

        self.assertTrue(page.is_empty_state_visible())
        self.assertIn("create an album draft", page.empty_state_label.text().lower())

    def test_main_window_adds_album_draft_tab(self):
        window = MainWindow()
        labels = [window.tabs.tabText(index) for index in range(window.tabs.count())]
        self.assertIn("Album Draft", labels)


if __name__ == "__main__":
    unittest.main()
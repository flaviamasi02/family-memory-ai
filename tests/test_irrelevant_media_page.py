import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from models.photo import Photo
from ui.irrelevant_media_page import IrrelevantMediaPage

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class IrrelevantMediaPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _flush_ui(self, wait_ms: int = 0):
        if wait_ms > 0:
            QTest.qWait(wait_ms)
        for _ in range(12):
            self._app.processEvents()

    def _make_photo(self, root: Path, filename: str, metadata=None, thumb_color: Qt.GlobalColor = Qt.GlobalColor.green) -> Photo:
        path = root / filename
        path.write_bytes(b"img")
        photo = Photo.from_path(path)
        photo.metadata.update(metadata or {})

        thumbnail = QPixmap(120, 120)
        thumbnail.fill(thumb_color)
        photo.thumbnail = thumbnail

        photo.sync_intelligence_from_metadata()
        return photo

    def test_thumbnail_grid_card_shows_compact_badges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._make_photo(
                root,
                "offer_banner.jpg",
                {
                    "relevance_category": "advertisement",
                    "cleanup_confidence": 0.87,
                    "cleanup_recommended_action": "move_to_cleanup_folder",
                    "cleanup_reasons": ["Filename indicates promotional content."],
                },
            )

            page = IrrelevantMediaPage()
            page.set_photos([photo], root, total_imported_count=4)
            self._flush_ui(wait_ms=80)

            summary = page.card_summary_for_filename("offer_banner.jpg")
            self.assertIsNotNone(summary)
            self.assertTrue(summary["category"])
            self.assertEqual(summary["confidence"], "87%")
            self.assertTrue(summary["action"])

    def test_details_panel_updates_with_structured_explanations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._make_photo(
                root,
                "WhatsApp_buongiorno_square.jpg",
                {
                    "relevance_category": "meme_or_graphic",
                    "cleanup_confidence": 0.62,
                    "cleanup_recommended_action": "review",
                    "cleanup_reasons": ["Classified as meme because filename contains buongiorno."],
                    "width": 720,
                    "height": 720,
                },
            )

            page = IrrelevantMediaPage()
            page.set_photos([photo], root, total_imported_count=6)
            self._flush_ui(wait_ms=80)

            self.assertTrue(page.select_photo_by_filename("WhatsApp_buongiorno_square.jpg"))
            self.assertEqual(page.filename_value.text(), "WhatsApp_buongiorno_square.jpg")
            self.assertEqual(page.automatic_category_value.text(), "Memes")
            self.assertEqual(page.confidence_value.text(), "62%")
            self.assertGreaterEqual(page.reasons_list.count(), 2)
            reason_lines = [page.reasons_list.item(i).text().lower() for i in range(page.reasons_list.count())]
            self.assertTrue(any("buongiorno" in line for line in reason_lines))

    def test_grouping_and_statistics_are_visible(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            docs = self._make_photo(
                root,
                "fattura.jpg",
                {
                    "relevance_category": "document_or_scan",
                    "cleanup_confidence": 0.91,
                    "cleanup_recommended_action": "move_to_cleanup_folder",
                },
            )
            meme = self._make_photo(
                root,
                "meme.jpg",
                {
                    "relevance_category": "meme_or_graphic",
                    "cleanup_confidence": 0.58,
                    "cleanup_recommended_action": "review",
                },
            )

            page = IrrelevantMediaPage()
            page.set_photos([docs, meme], root, total_imported_count=10)
            self._flush_ui(wait_ms=100)

            stats = page.stats_label.text()
            self.assertIn("Imported: 10", stats)
            self.assertIn("Cleanup candidates: 2", stats)
            self.assertIn("Documents: 1", stats)
            self.assertIn("Memes: 1", stats)

            groups = [page.group_combo.itemText(i) for i in range(page.group_combo.count())]
            self.assertTrue(any(text.startswith("Documents (") for text in groups))
            self.assertTrue(any(text.startswith("Memes (") for text in groups))

    def test_category_correction_updates_effective_category_chain(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._make_photo(
                root,
                "fix_me.jpg",
                {
                    "relevance_category": "meme_or_graphic",
                    "cleanup_confidence": 0.67,
                    "cleanup_recommended_action": "review",
                },
            )

            page = IrrelevantMediaPage()
            page.set_photos([photo], root, total_imported_count=1)
            self._flush_ui(wait_ms=80)

            self.assertTrue(page.select_photo_by_filename("fix_me.jpg"))
            page._apply_category_to_selected("document_or_scan")
            self._flush_ui(wait_ms=80)

            self.assertEqual(photo.metadata.get("cleanup_automatic_category"), "meme_or_graphic")
            self.assertEqual(photo.metadata.get("cleanup_user_corrected_category"), "document_or_scan")
            self.assertEqual(photo.metadata.get("cleanup_effective_category"), "document_or_scan")
            self.assertEqual(photo.metadata.get("relevance_category"), "document_or_scan")

    def test_possible_alternatives_visibility_depends_on_confidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            low = self._make_photo(
                root,
                "low_conf.jpg",
                {
                    "relevance_category": "unknown",
                    "cleanup_confidence": 0.49,
                    "cleanup_recommended_action": "review",
                },
            )
            high = self._make_photo(
                root,
                "high_conf.jpg",
                {
                    "relevance_category": "document_or_scan",
                    "cleanup_confidence": 0.92,
                    "cleanup_recommended_action": "move_to_cleanup_folder",
                },
                thumb_color=Qt.GlobalColor.blue,
            )

            page = IrrelevantMediaPage()
            page.set_photos([low, high], root, total_imported_count=2)
            self._flush_ui(wait_ms=100)

            self.assertTrue(page.select_photo_by_filename("low_conf.jpg"))
            self.assertTrue(page.possible_alternatives_visible())
            self.assertGreater(page.alternatives_list.count(), 0)

            self.assertTrue(page.select_photo_by_filename("high_conf.jpg"))
            self.assertFalse(page.possible_alternatives_visible())

    def test_selection_and_bulk_category_action(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = self._make_photo(root, "one.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.5})
            second = self._make_photo(root, "two.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.52})

            page = IrrelevantMediaPage()
            page.set_photos([first, second], root, total_imported_count=2)
            self._flush_ui(wait_ms=100)

            page.select_all_visible()
            self.assertEqual(page.selected_count(), 2)

            page._apply_category_to_selected("meme_or_graphic")
            self._flush_ui(wait_ms=100)

            self.assertEqual(first.metadata.get("cleanup_effective_category"), "meme_or_graphic")
            self.assertEqual(second.metadata.get("cleanup_effective_category"), "meme_or_graphic")

            page.clear_selection()
            self.assertEqual(page.selected_count(), 0)

    def test_move_to_cleanup_folder_action_moves_selected_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = self._make_photo(
                root,
                "move_me.jpg",
                {
                    "relevance_category": "advertisement",
                    "cleanup_confidence": 0.9,
                    "cleanup_recommended_action": "move_to_cleanup_folder",
                },
            )

            moved = []
            page = IrrelevantMediaPage()
            page.moved_photos.connect(lambda photos: moved.extend(photos))
            page.set_photos([first], root, total_imported_count=1)
            self._flush_ui(wait_ms=80)
            page.select_all_visible()

            with patch("ui.irrelevant_media_page.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
                page.move_selected_to_quarantine()
                self._flush_ui(wait_ms=80)

            destination = root / "_family_memory_cleanup_review" / "move_me.jpg"
            self.assertTrue(destination.exists())
            self.assertEqual(len(moved), 1)

    def test_double_click_opens_preview_dialog_from_cleanup_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = self._make_photo(root, "one.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.5})
            second = self._make_photo(root, "two.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.52})

            page = IrrelevantMediaPage()
            page.set_photos([first, second], root, total_imported_count=2)
            self._flush_ui(wait_ms=100)

            key = str(first.path)
            page._on_card_double_clicked(key)
            self._flush_ui(wait_ms=60)

            self.assertIsNotNone(page._preview_dialog)
            self.assertTrue(page._preview_dialog.isVisible())
            self.assertEqual(page._preview_dialog.current_filename(), "one.jpg")
            self.assertTrue(page._preview_dialog.position_label.text().endswith("of 2"))


if __name__ == "__main__":
    unittest.main()

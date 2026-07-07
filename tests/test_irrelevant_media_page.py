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
from core.category_registry import get_category_registry, reset_category_registry
from ui.irrelevant_media_page import IrrelevantMediaPage

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class IrrelevantMediaPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self):
        os.environ.pop("FAMILY_MEMORY_CATEGORIES_ROOT", None)
        reset_category_registry()

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

    def _write_image(self, path: Path, color: Qt.GlobalColor = Qt.GlobalColor.green) -> None:
        pixmap = QPixmap(120, 120)
        pixmap.fill(color)
        self.assertTrue(pixmap.save(str(path), "JPG"))

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

    def test_cleanup_review_thumbnail_falls_back_to_original_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "original_only.jpg"
            self._write_image(image_path)
            photo = Photo.from_path(image_path)
            photo.metadata.update({
                "relevance_category": "unknown",
                "cleanup_confidence": 0.50,
                "cleanup_recommended_action": "review",
                "thumbnail_path": "",
            })
            photo.thumbnail_path = ""
            photo.sync_intelligence_from_metadata()

            page = IrrelevantMediaPage()
            page.set_photos([photo], root, total_imported_count=1)
            self._flush_ui(wait_ms=80)

            card = page.thumbnail_grid._cards_by_key.get(str(photo.path))
            self.assertIsNotNone(card)
            self.assertFalse(card.thumbnail_label.pixmap().isNull())

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

    def test_cleanup_review_shows_visual_summary_in_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._make_photo(
                root,
                "visual_cleanup.jpg",
                {
                    "relevance_category": "unknown",
                    "cleanup_confidence": 0.55,
                    "cleanup_recommended_action": "review",
                    "visual_signals_summary": "photo=0.20, document=0.12, graphic=0.66, screenshot=0.14, advertisement=0.21",
                    "visual_evidence": "Large flat color regions detected.",
                },
            )

            page = IrrelevantMediaPage()
            page.set_photos([photo], root, total_imported_count=1)
            self._flush_ui(wait_ms=80)
            self.assertTrue(page.select_photo_by_filename("visual_cleanup.jpg"))

            summary = page.metadata_summary_value.text().lower()
            self.assertIn("visual:", summary)

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

    def test_cleanup_category_change_preserves_scroll_and_selection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photos = [
                self._make_photo(root, f"cleanup_scroll_{index:03d}.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.6})
                for index in range(90)
            ]

            page = IrrelevantMediaPage()
            page.resize(900, 700)
            page.show()
            page.set_photos(photos, root, total_imported_count=len(photos))
            self._flush_ui(wait_ms=140)

            self.assertTrue(page.select_photo_by_filename("cleanup_scroll_030.jpg"))
            scrollbar = page.thumbnail_grid.scroll_area.verticalScrollBar()
            scrollbar.setValue(min(360, scrollbar.maximum()))
            before_scroll = scrollbar.value()
            before_rendered = page.rendered_card_count()

            page._apply_category_to_selected("meme_or_graphic")
            self._flush_ui(wait_ms=140)

            self.assertEqual(page.thumbnail_grid.selected_key(), str(photos[30].path))
            self.assertEqual(scrollbar.value(), before_scroll)
            self.assertEqual(page.rendered_card_count(), before_rendered)
            self.assertEqual(photos[30].metadata.get("cleanup_effective_category"), "meme_or_graphic")

    def test_cleanup_category_change_selects_next_when_current_filter_excludes_modified_photo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photos = [
                self._make_photo(root, f"cleanup_unknown_{index:03d}.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.6})
                for index in range(60)
            ]

            page = IrrelevantMediaPage()
            page.resize(900, 700)
            page.show()
            page.set_photos(photos, root, total_imported_count=len(photos))
            self._flush_ui(wait_ms=120)
            page.category_filter_combo.setCurrentText("Unknown")
            self._flush_ui(wait_ms=80)

            self.assertTrue(page.select_photo_by_filename("cleanup_unknown_005.jpg"))
            scrollbar = page.thumbnail_grid.scroll_area.verticalScrollBar()
            scrollbar.setValue(min(160, scrollbar.maximum()))
            before_scroll = scrollbar.value()

            page._apply_category_to_selected("family_photo")
            self._flush_ui(wait_ms=140)

            self.assertNotIn("cleanup_unknown_005.jpg", page.visible_filenames())
            self.assertEqual(page.thumbnail_grid.selected_key(), str(photos[6].path))
            self.assertEqual(scrollbar.value(), before_scroll)

    def test_cleanup_review_uses_single_category_assignment_workflow(self):
        page = IrrelevantMediaPage()

        self.assertTrue(hasattr(page, "category_selector"))
        self.assertTrue(hasattr(page, "apply_category_button"))
        self.assertTrue(hasattr(page, "keep_button"))
        self.assertTrue(hasattr(page, "move_button"))

        self.assertFalse(hasattr(page, "mark_family_button"))
        self.assertFalse(hasattr(page, "mark_document_button"))
        self.assertFalse(hasattr(page, "mark_ad_button"))
        self.assertFalse(hasattr(page, "mark_meme_button"))
        self.assertFalse(hasattr(page, "mark_screenshot_button"))
        self.assertFalse(hasattr(page, "mark_duplicate_button"))
        self.assertFalse(hasattr(page, "mark_unknown_button"))

    def test_cleanup_review_grid_renders_multiple_columns_when_wide(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            items = [
                self._make_photo(root, f"img_{index}.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.5})
                for index in range(12)
            ]

            page = IrrelevantMediaPage()
            page.resize(1800, 980)
            page.show()
            page.set_photos(items, root, total_imported_count=12)
            self._flush_ui(wait_ms=120)

            self.assertGreaterEqual(page.grid_column_count(), 3)

    def test_cleanup_grid_content_expands_to_viewport_width(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            items = [
                self._make_photo(root, f"expand_{index}.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.6})
                for index in range(10)
            ]

            page = IrrelevantMediaPage()
            page.resize(1800, 980)
            page.show()
            page.set_photos(items, root, total_imported_count=10)
            self._flush_ui(wait_ms=120)

            viewport_width = page.thumbnail_grid.scroll_area.viewport().width()
            self.assertGreater(viewport_width, 400)
            self.assertGreaterEqual(page.thumbnail_grid.content_widget.width(), viewport_width)

    def test_cleanup_cards_are_not_forced_into_single_column_when_wide(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            items = [
                self._make_photo(root, f"cols_{index}.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.7})
                for index in range(20)
            ]

            page = IrrelevantMediaPage()
            page.resize(1800, 980)
            page.show()
            page.set_photos(items, root, total_imported_count=20)
            self._flush_ui(wait_ms=140)

            self.assertGreater(page.grid_column_count(), 1)

            rendered = page.rendered_card_count()
            self.assertGreater(rendered, 1)
            seen_columns = set()
            for index in range(min(rendered, 8)):
                _row, column, _row_span, _column_span = page.thumbnail_grid.grid_layout.getItemPosition(index)
                seen_columns.add(column)
            self.assertGreater(len(seen_columns), 1)

    def test_cleanup_review_filtering_refreshes_shared_grid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            doc = self._make_photo(root, "doc.jpg", {"relevance_category": "document_or_scan", "cleanup_confidence": 0.9})
            meme = self._make_photo(root, "meme.jpg", {"relevance_category": "meme_or_graphic", "cleanup_confidence": 0.7})

            page = IrrelevantMediaPage()
            page.set_photos([doc, meme], root, total_imported_count=2)
            self._flush_ui(wait_ms=80)

            page.category_filter_combo.setCurrentText("Documents")
            self._flush_ui(wait_ms=80)
            self.assertEqual(page.visible_filenames(), ["doc.jpg"])

    def test_custom_category_appears_and_can_be_assigned_in_cleanup_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["FAMILY_MEMORY_CATEGORIES_ROOT"] = tmpdir
            reset_category_registry()
            registry = get_category_registry(force_reload=True)
            registry.create_user_category("To Print")

            root = Path(tmpdir)
            one = self._make_photo(root, "one.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.7})
            two = self._make_photo(root, "two.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.6})

            page = IrrelevantMediaPage()
            page.set_photos([one, two], root, total_imported_count=2)
            self._flush_ui(wait_ms=80)

            self.assertIn("to_print", page.category_selector_values())
            self.assertIn("To Print", page.category_filter_labels())

            page.select_all_visible()
            page._apply_category_to_selected("to_print")
            self._flush_ui(wait_ms=80)

            self.assertEqual(one.metadata.get("cleanup_effective_category"), "to_print")
            self.assertEqual(two.metadata.get("cleanup_effective_category"), "to_print")

            page.category_filter_combo.setCurrentText("To Print")
            self._flush_ui(wait_ms=80)
            self.assertCountEqual(page.visible_filenames(), ["one.jpg", "two.jpg"])

    def test_cleanup_review_multi_selection_ctrl_and_shift(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            one = self._make_photo(root, "one.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.9})
            two = self._make_photo(root, "two.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.8})
            three = self._make_photo(root, "three.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.7})

            page = IrrelevantMediaPage()
            page.set_photos([one, two, three], root, total_imported_count=3)
            self._flush_ui(wait_ms=100)

            k1 = str(one.path)
            k2 = str(two.path)
            k3 = str(three.path)

            # Ctrl adds second item.
            page.thumbnail_grid._on_card_clicked(k1, 0)
            page.thumbnail_grid._on_card_clicked(k2, int(Qt.KeyboardModifier.ControlModifier.value))
            self.assertEqual(page.selected_count(), 2)

            # Shift range-select from first anchor to third item.
            page.thumbnail_grid._on_card_clicked(k1, 0)
            page.thumbnail_grid._on_card_clicked(k3, int(Qt.KeyboardModifier.ShiftModifier.value))
            self.assertEqual(page.selected_count(), 3)

    def test_cleanup_review_lazy_rendering_preserved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            items = [
                self._make_photo(root, f"lazy_{index}.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.6})
                for index in range(260)
            ]

            page = IrrelevantMediaPage()
            page.set_photos(items, root, total_imported_count=260)
            self._flush_ui(wait_ms=120)

            self.assertEqual(len(page.visible_filenames()), 260)
            self.assertLess(page.rendered_card_count(), 260)

    def test_cleanup_review_thumbnail_cache_reused(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._make_photo(root, "cache.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.9})

            page = IrrelevantMediaPage()
            page.set_photos([photo], root, total_imported_count=1)
            self._flush_ui(wait_ms=80)

            row = page._visible_rows[0]
            first = page._get_cached_card_thumbnail(row)
            second = page._get_cached_card_thumbnail(row)
            self.assertIsNotNone(first)
            self.assertIs(first, second)

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

    def test_cleanup_review_preview_uses_centralized_display_loader(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = self._make_photo(root, "one.jpg", {"relevance_category": "unknown", "cleanup_confidence": 0.5})

            page = IrrelevantMediaPage()
            page.set_photos([first], root, total_imported_count=1)
            self._flush_ui(wait_ms=100)

            fake = QPixmap(120, 180)
            fake.fill(Qt.GlobalColor.red)
            with patch("ui.image_preview_dialog.load_display_pixmap", return_value=fake) as mocked:
                page._on_card_double_clicked(str(first.path))
                self._flush_ui(wait_ms=80)

            self.assertTrue(mocked.called)


if __name__ == "__main__":
    unittest.main()

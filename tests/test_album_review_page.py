import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox

from album.album_scoring_engine import AlbumScoreBreakdown
from core.media_classifier import MediaCategory
from models.photo import Photo
from models.photo_intelligence import PhotoIntelligence
from ui.album_review_page import AlbumReviewPage


class AlbumReviewPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _make_breakdown(
        self,
        root: Path,
        filename: str,
        total: float,
        technical: float,
        memory: float,
        date_score: float,
        date_taken: str,
        people=None,
        metadata=None,
    ) -> AlbumScoreBreakdown:
        path = root / filename
        path.write_bytes(b"img")
        photo = Photo.from_path(path)
        photo.metadata.update(metadata or {})
        photo.metadata["date_taken"] = date_taken
        photo.metadata.setdefault("automatic_media_category", MediaCategory.FamilyPhoto.value)
        photo.metadata.setdefault("user_corrected_media_category", "")
        photo.metadata.setdefault("effective_media_category", photo.metadata["automatic_media_category"])
        photo.metadata.setdefault("media_category", photo.metadata["effective_media_category"])
        photo.metadata.setdefault("classification_reason", "Deterministic import-time classification.")
        photo.metadata.setdefault("classification_confidence", 0.8)
        photo.people = list(people or [])
        photo.sync_intelligence_from_metadata()
        photo.intelligence.album_candidate_score = total

        return AlbumScoreBreakdown(
            photo=photo,
            total_score=total,
            technical_score=technical,
            memory_score=memory,
            date_score=date_score,
            explanation=[
                "technical: base + metadata",
                "memory: people detected",
                "date: year match",
            ],
        )

    def _visible_filenames(self, page: AlbumReviewPage):
        self._flush_ui()
        return page.visible_filenames()

    def _flush_ui(self, wait_ms: int = 0):
        if wait_ms > 0:
            QTest.qWait(wait_ms)
        for _ in range(12):
            self._app.processEvents()

    def _make_virtual_breakdown(self, index: int) -> AlbumScoreBreakdown:
        filename = f"photo_{index}.jpg"
        photo = Photo(
            path=Path(f"C:/virtual/{filename}"),
            filename=filename,
            extension=".jpg",
            file_size=1024,
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            modified_at=datetime(2024, 1, 1, 10, 0, 0),
            metadata={"date_taken": "2024:01:01 10:00:00"},
            intelligence=PhotoIntelligence(),
        )
        photo.sync_intelligence_from_metadata()
        score = float(100 - (index % 100))
        return AlbumScoreBreakdown(
            photo=photo,
            total_score=score,
            technical_score=score,
            memory_score=score,
            date_score=score,
            explanation=["line 1", "line 2", "line 3"],
        )

    def _key_for_filename(self, page: AlbumReviewPage, filename: str) -> str:
        for row in page._visible_rows:
            if row.breakdown.photo.display_name() == filename:
                return page._row_key(row)
        raise AssertionError(f"Filename not visible: {filename}")

    def test_sorting_modes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            b1 = self._make_breakdown(root, "a.jpg", 80, 70, 90, 75, "2024:01:10 10:00:00")
            b2 = self._make_breakdown(root, "b.jpg", 55, 50, 60, 55, "2024:03:10 10:00:00")
            b3 = self._make_breakdown(root, "c.jpg", 95, 95, 95, 95, "2023:12:10 10:00:00")

            page = AlbumReviewPage()
            page.set_scored_photos([b1, b2, b3])
            self._flush_ui()

            self.assertEqual(self._visible_filenames(page), ["c.jpg", "a.jpg", "b.jpg"])

            page.sort_combo.setCurrentText(page.SORT_LOWEST)
            self._flush_ui()
            self.assertEqual(self._visible_filenames(page), ["b.jpg", "a.jpg", "c.jpg"])

            page.sort_combo.setCurrentText(page.SORT_DATE)
            self._flush_ui()
            self.assertEqual(self._visible_filenames(page), ["b.jpg", "a.jpg", "c.jpg"])

    def test_filtering_and_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            b1 = self._make_breakdown(root, "trip_rome.jpg", 80, 70, 90, 75, "2024:01:10 10:00:00")
            b2 = self._make_breakdown(root, "family_party.jpg", 55, 50, 60, 55, "2024:03:10 10:00:00")

            page = AlbumReviewPage()
            page.set_scored_photos([b1, b2])
            self._flush_ui()

            self.assertTrue(page.select_photo_by_filename("trip_rome.jpg"))
            page.approve_selected()
            page.filter_combo.setCurrentText(page.FILTER_APPROVED)
            self._flush_ui()
            self.assertEqual(self._visible_filenames(page), ["trip_rome.jpg"])

            page.filter_combo.setCurrentText(page.FILTER_ALL)
            page.search_input.setText("party")
            self._flush_ui(wait_ms=260)
            self.assertEqual(self._visible_filenames(page), ["family_party.jpg"])

    def test_approve_reject_reset_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            b1 = self._make_breakdown(root, "a.jpg", 70, 70, 70, 70, "2024:01:01 00:00:00")
            page = AlbumReviewPage()
            page.set_scored_photos([b1])
            self._flush_ui()

            self.assertTrue(page.select_photo_by_filename("a.jpg"))
            page.approve_selected()
            self.assertEqual(page.review_state_for_filename("a.jpg"), "approved")

            page.reject_selected()
            self.assertEqual(page.review_state_for_filename("a.jpg"), "rejected")

            page.reset_selected()
            self.assertEqual(page.review_state_for_filename("a.jpg"), "pending")

    def test_detail_panel_and_explanations_visible(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            breakdown = self._make_breakdown(
                root,
                "detail.jpg",
                88,
                81,
                92,
                75,
                "2024:04:14 08:30:00",
                people=["Alice"],
                metadata={
                    "location": "Rome",
                    "classification_reason": "Detected as family photo candidate.",
                    "classification_confidence": 0.82,
                },
            )
            breakdown.photo.intelligence.date_taken = datetime(2024, 4, 14, 8, 30, 0)
            breakdown.photo.intelligence.date_source = "EXIF"
            breakdown.photo.intelligence.people_names = ["Bob"]

            page = AlbumReviewPage()
            page.set_scored_photos([breakdown])
            self._flush_ui()
            self.assertTrue(page.select_photo_by_filename("detail.jpg"))

            self.assertEqual(page.filename_value.text(), "detail.jpg")
            self.assertIn("Total 88.00", page.score_value.text())
            self.assertEqual(page.media_category_value.text(), "Family Photo")
            self.assertIn("family photo", page.classification_reason_value.text().lower())
            self.assertEqual(page.confidence_value.text(), "82%")
            self.assertEqual(page.date_source_value.text(), "EXIF")
            self.assertFalse(hasattr(page, "metadata_value"))
            self.assertEqual(page.explanations_list.count(), 3)
            self.assertIn("technical", page.explanations_list.item(0).text())

    def test_automatic_category_visible_on_card(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            breakdown = self._make_breakdown(
                root,
                "category_card.jpg",
                70,
                60,
                70,
                80,
                "2024:06:10 10:00:00",
                metadata={
                    "automatic_media_category": MediaCategory.FamilyPhoto.value,
                    "effective_media_category": MediaCategory.FamilyPhoto.value,
                    "classification_confidence": 0.8,
                },
            )

            page = AlbumReviewPage()
            page.set_scored_photos([breakdown])
            self._flush_ui(wait_ms=40)

            summary = page.card_summary_for_filename("category_card.jpg")
            self.assertIsNotNone(summary)
            self.assertEqual(summary["category"], "Category: Family Photo")
            self.assertEqual(summary["confidence"], "Confidence: 80%")
            self.assertEqual(summary["decision"], "Decision: Pending")

    def test_category_filter_works(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            family = self._make_breakdown(
                root,
                "family_one.jpg",
                80,
                80,
                80,
                80,
                "2024:06:10 10:00:00",
                metadata={
                    "automatic_media_category": MediaCategory.FamilyPhoto.value,
                    "effective_media_category": MediaCategory.FamilyPhoto.value,
                },
            )
            doc = self._make_breakdown(
                root,
                "invoice_one.jpg",
                80,
                80,
                80,
                80,
                "2024:06:10 10:00:00",
                metadata={
                    "automatic_media_category": MediaCategory.Invoice.value,
                    "effective_media_category": MediaCategory.Invoice.value,
                },
            )

            page = AlbumReviewPage()
            page.set_scored_photos([family, doc])
            self._flush_ui(wait_ms=40)

            page.category_filter_combo.setCurrentText("Invoice")
            self._flush_ui(wait_ms=40)
            self.assertEqual(self._visible_filenames(page), ["invoice_one.jpg"])

    def test_user_can_correct_category_and_effective_category_uses_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            breakdown = self._make_breakdown(
                root,
                "correctable.jpg",
                80,
                80,
                80,
                80,
                "2024:06:10 10:00:00",
                metadata={
                    "automatic_media_category": MediaCategory.FamilyPhoto.value,
                    "effective_media_category": MediaCategory.FamilyPhoto.value,
                },
            )

            page = AlbumReviewPage()
            page.set_scored_photos([breakdown])
            self._flush_ui(wait_ms=40)
            self.assertTrue(page.select_photo_by_filename("correctable.jpg"))

            page.category_selector.setCurrentText("Advertisement")
            page._apply_selector_category()
            self._flush_ui(wait_ms=40)

            self.assertEqual(breakdown.photo.automatic_media_category, MediaCategory.FamilyPhoto.value)
            self.assertEqual(breakdown.photo.user_corrected_media_category, MediaCategory.Advertisement.value)
            self.assertEqual(breakdown.photo.effective_media_category, MediaCategory.Advertisement.value)
            self.assertEqual(page.media_category_value.text(), "Advertisement")

            events = page.learning_events()
            self.assertTrue(events)
            self.assertEqual(events[-1].event_type, "category_correction")
            self.assertEqual(events[-1].previous_value, MediaCategory.FamilyPhoto.value)
            self.assertEqual(events[-1].new_value, MediaCategory.Advertisement.value)
            self.assertEqual(events[-1].source, "user")

    def test_pipeline_counts_and_rejection_reason_visible(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selected_breakdown = self._make_breakdown(
                root,
                "selected.jpg",
                90,
                90,
                90,
                90,
                "2024:01:01 00:00:00",
            )
            rejected_breakdown = self._make_breakdown(
                root,
                "rejected.jpg",
                0,
                0,
                0,
                0,
                "2022:01:01 00:00:00",
            )
            rejected_breakdown.photo.intelligence.album_rejection_reason = "year_mismatch"

            imported = [selected_breakdown.photo, rejected_breakdown.photo]
            selected = [selected_breakdown.photo]
            rejected = [rejected_breakdown.photo]
            scored = {str(selected_breakdown.photo.path): selected_breakdown}

            page = AlbumReviewPage()
            page.set_pipeline_data(
                imported_photos=imported,
                candidate_photos=imported,
                selected_photos=selected,
                rejected_photos=rejected,
                scored_breakdowns=scored,
                rejection_reasons={"year_mismatch": 1},
            )
            self._flush_ui()

            self.assertIn("Imported: 2", page.results_label.text())
            self.assertIn("Candidates: 2", page.results_label.text())
            self.assertIn("Selected: 1", page.results_label.text())
            self.assertIn("Rejected: 1", page.results_label.text())
            self.assertIn("Reasons: year_mismatch:1", page.results_label.text())

            self.assertTrue(page.select_photo_by_filename("rejected.jpg"))
            self.assertEqual(page.pipeline_value.text(), "Rejected")
            self.assertEqual(page.rejection_reason_value.text(), "year_mismatch")

    def test_explanations_widget_has_large_minimum_height(self):
        page = AlbumReviewPage()
        self.assertGreaterEqual(page.explanations_list.minimumHeight(), 200)

    def test_setting_4000_scored_photos_uses_lazy_initial_render(self):
        breakdowns = [self._make_virtual_breakdown(index) for index in range(4000)]

        page = AlbumReviewPage()
        page.set_scored_photos(breakdowns)
        self._flush_ui(wait_ms=60)

        self.assertEqual(len(page.visible_filenames()), 4000)
        self.assertLess(len(page._cards_by_key), 4000)
        self.assertLessEqual(len(page._cards_by_key), page._initial_render_count)

    def test_search_refresh_is_debounced_and_keeps_batched_rendering(self):
        breakdowns = [self._make_virtual_breakdown(index) for index in range(1200)]
        page = AlbumReviewPage()
        page.set_scored_photos(breakdowns)
        self._flush_ui(wait_ms=40)

        before_rebuild_count = page._grid_rebuild_count
        page.search_input.setText("photo_11")
        self._flush_ui(wait_ms=40)

        # Debounce should prevent immediate refresh.
        self.assertEqual(page._grid_rebuild_count, before_rebuild_count)

        self._flush_ui(wait_ms=260)
        self.assertGreater(page._grid_rebuild_count, before_rebuild_count)
        self.assertLessEqual(len(page._cards_by_key), page._initial_render_count)

    def test_selecting_photo_updates_details_without_grid_rebuild(self):
        breakdowns = [self._make_virtual_breakdown(index) for index in range(600)]
        page = AlbumReviewPage()
        page.set_scored_photos(breakdowns)
        self._flush_ui(wait_ms=80)

        rebuild_before = page._grid_rebuild_count
        self.assertTrue(page.select_photo_by_filename("photo_5.jpg"))
        self._flush_ui()

        self.assertEqual(page._grid_rebuild_count, rebuild_before)
        self.assertEqual(page.filename_value.text(), "photo_5.jpg")

    def test_cached_thumbnails_are_reused(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            breakdown = self._make_breakdown(
                root,
                "thumb.jpg",
                80,
                80,
                80,
                80,
                "2024:01:01 10:00:00",
            )

            source = QPixmap(64, 64)
            source.fill(Qt.GlobalColor.green)
            breakdown.photo.thumbnail = source

            page = AlbumReviewPage()
            page.set_scored_photos([breakdown])
            self._flush_ui(wait_ms=60)

            row = page._visible_rows[0]
            first = page._get_cached_card_thumbnail(row)
            second = page._get_cached_card_thumbnail(row)

            self.assertIsNotNone(first)
            self.assertIs(first, second)

    def test_multi_select_ctrl_click_adds_and_removes_selection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            b1 = self._make_breakdown(root, "one.jpg", 80, 80, 80, 80, "2024:01:01 00:00:00")
            b2 = self._make_breakdown(root, "two.jpg", 79, 79, 79, 79, "2024:01:02 00:00:00")
            b3 = self._make_breakdown(root, "three.jpg", 78, 78, 78, 78, "2024:01:03 00:00:00")
            page = AlbumReviewPage()
            page.set_scored_photos([b1, b2, b3])
            self._flush_ui(wait_ms=40)

            key_one = self._key_for_filename(page, "one.jpg")
            key_two = self._key_for_filename(page, "two.jpg")

            page._on_card_clicked(key_one, 0)
            page._on_card_clicked(key_two, int(Qt.KeyboardModifier.ControlModifier.value))
            self.assertEqual(page.selected_count(), 2)

            page._on_card_clicked(key_two, int(Qt.KeyboardModifier.ControlModifier.value))
            self.assertEqual(page.selected_count(), 1)
            self.assertIn(key_one, page.selected_file_paths())

    def test_shift_click_selects_visible_range(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            items = [
                self._make_breakdown(root, f"img_{index}.jpg", 100 - index, 80, 80, 80, "2024:01:01 00:00:00")
                for index in range(5)
            ]
            page = AlbumReviewPage()
            page.set_scored_photos(items)
            self._flush_ui(wait_ms=40)

            first_key = self._key_for_filename(page, page.visible_filenames()[0])
            third_key = self._key_for_filename(page, page.visible_filenames()[2])
            page._on_card_clicked(first_key, 0)
            page._on_card_clicked(third_key, int(Qt.KeyboardModifier.ShiftModifier.value))

            self.assertEqual(page.selected_count(), 3)

    def test_clear_selection_and_select_all_visible_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            b1 = self._make_breakdown(root, "a.jpg", 80, 80, 80, 80, "2024:01:01 00:00:00")
            b2 = self._make_breakdown(root, "b.jpg", 79, 79, 79, 79, "2024:01:02 00:00:00")
            page = AlbumReviewPage()
            page.set_scored_photos([b1, b2])
            self._flush_ui(wait_ms=40)

            page.select_all_visible()
            self.assertEqual(page.selected_count(), 2)
            self.assertIn("Selected: 2", page.selection_count_label.text())

            page.clear_selection()
            self.assertEqual(page.selected_count(), 0)
            self.assertIn("Selected: 0", page.selection_count_label.text())

    def test_bulk_category_change_updates_all_selected_and_preserves_automatic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = self._make_breakdown(root, "first.jpg", 80, 80, 80, 80, "2024:01:01 00:00:00")
            second = self._make_breakdown(root, "second.jpg", 79, 79, 79, 79, "2024:01:02 00:00:00")
            page = AlbumReviewPage()
            page.set_scored_photos([first, second])
            self._flush_ui(wait_ms=40)
            page.select_all_visible()

            page.category_selector.setCurrentText("Advertisement")
            page._apply_selector_category()
            self._flush_ui(wait_ms=40)

            for breakdown in (first, second):
                photo = breakdown.photo
                self.assertEqual(photo.automatic_media_category, MediaCategory.FamilyPhoto.value)
                self.assertEqual(photo.user_corrected_media_category, MediaCategory.Advertisement.value)
                self.assertEqual(photo.effective_media_category, MediaCategory.Advertisement.value)

            events = page.learning_events()
            category_events = [event for event in events if event.event_type == "category_correction"]
            self.assertEqual(len(category_events), 2)
            self.assertTrue(all(event.source == "user_bulk" for event in category_events))

    def test_bulk_decision_change_updates_all_selected_and_records_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = self._make_breakdown(root, "first.jpg", 80, 80, 80, 80, "2024:01:01 00:00:00")
            second = self._make_breakdown(root, "second.jpg", 79, 79, 79, 79, "2024:01:02 00:00:00")
            page = AlbumReviewPage()
            page.set_scored_photos([first, second])
            self._flush_ui(wait_ms=40)
            page.select_all_visible()

            page.decision_selector.setCurrentText("reject")
            page._apply_selector_decision()
            self._flush_ui(wait_ms=40)

            self.assertEqual(page.review_state_for_filename("first.jpg"), "rejected")
            self.assertEqual(page.review_state_for_filename("second.jpg"), "rejected")

            decision_events = [event for event in page.learning_events() if event.event_type == "decision_change"]
            self.assertEqual(len(decision_events), 2)
            self.assertTrue(all(event.source == "user_bulk" for event in decision_events))

    def test_bulk_confirmation_triggered_for_large_selection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            items = [
                self._make_breakdown(root, f"big_{index}.jpg", 100 - index, 80, 80, 80, "2024:01:01 00:00:00")
                for index in range(25)
            ]
            page = AlbumReviewPage()
            page.set_scored_photos(items)
            self._flush_ui(wait_ms=40)
            page.select_all_visible()

            with patch("ui.album_review_page.QMessageBox.question", return_value=QMessageBox.StandardButton.No) as mock_question:
                page.category_selector.setCurrentText("Document")
                page._apply_selector_category()
                self._flush_ui(wait_ms=40)
                self.assertTrue(mock_question.called)

            # Cancel keeps previous effective category.
            for item in items:
                self.assertEqual(item.photo.effective_media_category, MediaCategory.FamilyPhoto.value)


if __name__ == "__main__":
    unittest.main()
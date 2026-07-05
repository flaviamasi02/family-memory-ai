import os
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from album.album_builder import AlbumBuilder
from album.album_scoring_engine import AlbumScoringEngine
from album.candidate_selection_engine import CandidateSelectionEngine
from core.date_extraction_service import DateExtractionService
from core.photo_scanner import find_photos
from ui.album_review_page import AlbumReviewPage

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class DateExtractionPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.service = DateExtractionService()

    def test_filename_pattern_20210102_121948(self):
        result = self.service.extract_date("20210102_121948.jpg")
        self.assertEqual(result.date_taken, "2021:01:02 12:19:48")
        self.assertEqual(result.date_source, "Filename")

    def test_filename_pattern_20210102_wa0003(self):
        result = self.service.extract_date("20210102-WA0003.jpg")
        self.assertEqual(result.date_taken, "2021:01:02 00:00:00")
        self.assertEqual(result.date_source, "Filename")

    def test_filename_pattern_img_20210415_182030(self):
        result = self.service.extract_date("IMG_20210415_182030.jpg")
        self.assertEqual(result.date_taken, "2021:04:15 18:20:30")
        self.assertEqual(result.date_source, "Filename")

    def test_filename_pattern_pxl_20231201_101500(self):
        result = self.service.extract_date("PXL_20231201_101500.jpg")
        self.assertEqual(result.date_taken, "2023:12:01 10:15:00")
        self.assertEqual(result.date_source, "Filename")

    def test_filename_pattern_screenshot_2024_05_06(self):
        result = self.service.extract_date("Screenshot_2024-05-06.png")
        self.assertEqual(result.date_taken, "2024:05:06 00:00:00")
        self.assertEqual(result.date_source, "Filename")

    def test_filename_pattern_vid_20240118_093015_mp4(self):
        result = self.service.extract_date("VID_20240118_093015.mp4")
        self.assertEqual(result.date_taken, "2024:01:18 09:30:15")
        self.assertEqual(result.date_source, "Filename")

    def test_import_populates_intelligence_date_parts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "IMG_20210415_182030.jpg"
            path.write_bytes(b"fake")

            photos = find_photos(str(root))

            self.assertEqual(len(photos), 1)
            intelligence = photos[0].intelligence
            self.assertIsNotNone(intelligence.date_taken)
            self.assertIsInstance(intelligence.year, int)
            self.assertIsInstance(intelligence.month, int)
            self.assertIsInstance(intelligence.day, int)
            self.assertIn(intelligence.date_source, {"EXIF", "Filename", "Filesystem", "Unknown"})
            self.assertEqual(intelligence.source_of_date, intelligence.date_source)

    def test_candidate_selection_uses_extracted_year(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "20210102-WA0003.jpg").write_bytes(b"wa")

            photos = find_photos(str(root))
            self.assertEqual(len(photos), 1)

            extracted_year = photos[0].intelligence.year
            self.assertIsNotNone(extracted_year)

            album = AlbumBuilder().create_annual_album(photos, extracted_year)
            result = CandidateSelectionEngine().evaluate(album)

            self.assertEqual(result.selected_count, 1)
            self.assertEqual(result.rejected_count, 0)

    def test_whatsapp_import_produces_scored_photos_for_album_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for name in ["20210102-WA0003.jpg", "20210103-WA0004.jpg", "20210104-WA0005.jpg"]:
                (root / name).write_bytes(b"wa")

            photos = find_photos(str(root))
            self.assertGreaterEqual(len(photos), 3)

            builder = AlbumBuilder()
            by_year = builder.group_photos_by_year(photos)
            self.assertTrue(by_year)

            chosen_year = max(sorted(by_year.keys()), key=lambda year: len(by_year[year]))
            album = builder.create_annual_album(photos, chosen_year)
            selection_result = CandidateSelectionEngine().evaluate(album)
            scoring_result = AlbumScoringEngine().score(album)

            self.assertGreater(scoring_result.scored_count, 0)

            review_page = AlbumReviewPage()
            self.assertTrue(
                all(item.total_score > 0 for item in scoring_result.scored_photos),
                "Expected non-empty positive scores for WhatsApp sample photos",
            )
            scored_by_key = {
                str(getattr(item.photo, "path", "")): item for item in scoring_result.scored_photos
            }
            review_page.set_pipeline_data(
                imported_photos=photos,
                candidate_photos=album.candidate_photos,
                selected_photos=album.selected_photos,
                rejected_photos=album.rejected_photos,
                scored_breakdowns=scored_by_key,
                rejection_reasons=selection_result.rejection_reasons,
            )

            for _ in range(10):
                self._app.processEvents()

            self.assertGreater(len(review_page.visible_filenames()), 0)
            self.assertIn("Selected:", review_page.results_label.text())
            self.assertIn("Reasons:", review_page.results_label.text())


if __name__ == "__main__":
    unittest.main()
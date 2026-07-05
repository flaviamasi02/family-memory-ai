import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from album.album_scoring_engine import AlbumScoreBreakdown
from core.media_classifier import UserDecision
from models.photo import Photo
from ui.album_review_page import AlbumReviewPage


class DecisionHistoryFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _make_breakdown(self, root: Path, filename: str) -> AlbumScoreBreakdown:
        path = root / filename
        path.write_bytes(b"img")
        photo = Photo.from_path(path)
        photo.metadata["date_taken"] = "2024:01:02 03:04:05"
        photo.sync_intelligence_from_metadata()
        return AlbumScoreBreakdown(
            photo=photo,
            total_score=80.0,
            technical_score=80.0,
            memory_score=80.0,
            date_score=80.0,
            explanation=["test"],
        )

    def _flush_ui(self):
        for _ in range(8):
            self._app.processEvents()

    def test_decision_assignment_updates_photo_and_row(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            breakdown = self._make_breakdown(Path(tmpdir), "one.jpg")
            page = AlbumReviewPage()
            page.set_scored_photos([breakdown])
            self._flush_ui()

            self.assertTrue(page.select_photo_by_filename("one.jpg"))
            page.set_selected_decision(UserDecision.Advertisement.value)

            self.assertEqual(page.decision_for_filename("one.jpg"), UserDecision.Advertisement.value)
            self.assertEqual(page.review_state_for_filename("one.jpg"), "pending")
            self.assertEqual(breakdown.photo.user_decision, UserDecision.Advertisement.value)

    def test_decision_persistence_keeps_history_in_memory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            breakdown = self._make_breakdown(Path(tmpdir), "two.jpg")
            page = AlbumReviewPage()
            page.set_scored_photos([breakdown])
            self._flush_ui()

            self.assertTrue(page.select_photo_by_filename("two.jpg"))
            page.set_selected_decision(UserDecision.Keep.value)
            page.set_selected_decision(UserDecision.Reject.value)

            entries = page.decision_history_entries()
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].event_type, "decision_change")
            self.assertEqual(entries[0].new_value, UserDecision.Keep.value)
            self.assertEqual(entries[1].event_type, "decision_change")
            self.assertEqual(entries[1].new_value, UserDecision.Reject.value)
            self.assertEqual(entries[1].file_path, str(breakdown.photo.path))
            self.assertEqual(entries[1].source, "user")


if __name__ == "__main__":
    unittest.main()
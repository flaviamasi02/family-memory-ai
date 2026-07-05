import tempfile
import unittest
from pathlib import Path

from album.annual_album import AnnualAlbum
from album.candidate_selection_engine import CandidateSelectionEngine
from models.photo import Photo


class CandidateSelectionEngineTests(unittest.TestCase):
    def _make_photo(self, root: Path, name: str, date_taken: str | None) -> Photo:
        path = root / name
        path.write_bytes(b"image")
        photo = Photo.from_path(path)
        if date_taken is not None:
            photo.metadata["date_taken"] = date_taken
            photo.sync_intelligence_from_metadata()
        return photo

    def test_valid_same_year_photo_is_selected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._make_photo(root, "a.jpg", "2024:02:01 10:00:00")
            album = AnnualAlbum(year=2024, candidate_photos=[photo])

            result = CandidateSelectionEngine().evaluate(album)

            self.assertEqual(result.selected_count, 1)
            self.assertEqual(result.rejected_count, 0)
            self.assertEqual(album.selected_photos, [photo])
            self.assertEqual(album.rejected_photos, [])
            self.assertTrue(photo.intelligence.album_selected)
            self.assertIsNone(photo.intelligence.album_rejection_reason)

    def test_year_mismatch_photo_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._make_photo(root, "a.jpg", "2023:02:01 10:00:00")
            album = AnnualAlbum(year=2024, candidate_photos=[photo])

            result = CandidateSelectionEngine().evaluate(album)

            self.assertEqual(result.selected_count, 0)
            self.assertEqual(result.rejected_count, 1)
            self.assertEqual(result.rejection_reasons.get("year_mismatch"), 1)
            self.assertEqual(album.rejected_photos, [photo])
            self.assertFalse(photo.intelligence.album_selected)
            self.assertEqual(photo.intelligence.album_rejection_reason, "year_mismatch")

    def test_missing_intelligence_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._make_photo(root, "a.jpg", "2024:05:01 10:00:00")
            photo.intelligence = None

            album = AnnualAlbum(year=2024, candidate_photos=[photo])
            result = CandidateSelectionEngine().evaluate(album)

            self.assertEqual(result.selected_count, 1)
            self.assertIsNotNone(photo.intelligence)
            self.assertTrue(photo.intelligence.album_selected)

    def test_selection_result_counts_are_correct(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selected_photo = self._make_photo(root, "a.jpg", "2024:03:01 10:00:00")
            rejected_photo = self._make_photo(root, "b.jpg", "2022:03:01 10:00:00")
            no_year_photo = self._make_photo(root, "c.jpg", None)

            album = AnnualAlbum(
                year=2024,
                candidate_photos=[selected_photo, rejected_photo, no_year_photo],
            )

            result = CandidateSelectionEngine().evaluate(album)

            self.assertEqual(result.selected_count, 1)
            self.assertEqual(result.rejected_count, 2)
            self.assertEqual(result.rejection_reasons.get("year_mismatch"), 1)
            self.assertEqual(result.rejection_reasons.get("missing_year"), 1)
            self.assertEqual(len(album.selected_photos), 1)
            self.assertEqual(len(album.rejected_photos), 2)
            self.assertEqual(len(album.candidate_photos), 3)


if __name__ == "__main__":
    unittest.main()

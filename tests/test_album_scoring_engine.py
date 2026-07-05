import tempfile
import unittest
from pathlib import Path

from album.album_scoring_engine import AlbumScoringEngine
from album.annual_album import AnnualAlbum
from models.photo import Photo


class AlbumScoringEngineTests(unittest.TestCase):
    def _make_photo(
        self,
        root: Path,
        name: str,
        date_taken: str | None = "2024:01:05 10:00:00",
        width: int | None = 4000,
        height: int | None = 3000,
    ) -> Photo:
        path = root / name
        path.write_bytes(b"image-data")
        photo = Photo.from_path(path)

        if date_taken is not None:
            photo.metadata["date_taken"] = date_taken
        if width is not None:
            photo.metadata["width"] = width
        if height is not None:
            photo.metadata["height"] = height

        photo.sync_intelligence_from_metadata()
        return photo

    def test_scores_selected_photos_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selected = self._make_photo(root, "selected.jpg")
            candidate_only = self._make_photo(root, "candidate.jpg")
            rejected = self._make_photo(root, "rejected.jpg")

            album = AnnualAlbum(
                year=2024,
                candidate_photos=[selected, candidate_only],
                selected_photos=[selected],
                rejected_photos=[rejected],
            )

            result = AlbumScoringEngine().score(album)

            self.assertEqual(result.scored_count, 1)
            self.assertEqual(len(result.scored_photos), 1)
            self.assertIs(result.scored_photos[0].photo, selected)

    def test_candidate_and_rejected_pools_remain_unchanged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selected = self._make_photo(root, "selected.jpg")
            candidate_only = self._make_photo(root, "candidate.jpg")
            rejected = self._make_photo(root, "rejected.jpg")

            album = AnnualAlbum(
                year=2024,
                candidate_photos=[selected, candidate_only],
                selected_photos=[selected],
                rejected_photos=[rejected],
            )

            before_candidates = list(album.candidate_photos)
            before_rejected = list(album.rejected_photos)

            AlbumScoringEngine().score(album)

            self.assertEqual(album.candidate_photos, before_candidates)
            self.assertEqual(album.rejected_photos, before_rejected)

    def test_scores_are_sorted_descending(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            high = self._make_photo(root, "high.jpg")
            low = self._make_photo(root, "low.jpg")

            high.people = ["Alice"]
            high.intelligence.people_names = ["Alice"]
            high.metadata["event"] = "Birthday"

            low.intelligence.is_blurry = True
            low.metadata = {}
            low.sync_intelligence_from_metadata()

            album = AnnualAlbum(year=2024, selected_photos=[low, high])

            result = AlbumScoringEngine().score(album)

            self.assertGreaterEqual(
                result.scored_photos[0].total_score,
                result.scored_photos[1].total_score,
            )

    def test_album_candidate_score_is_written_to_intelligence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._make_photo(root, "a.jpg")
            album = AnnualAlbum(year=2024, selected_photos=[photo])

            result = AlbumScoringEngine().score(album)

            self.assertIsNotNone(photo.intelligence.album_candidate_score)
            self.assertEqual(photo.intelligence.album_candidate_score, result.scored_photos[0].total_score)

    def test_blurry_photo_gets_lower_technical_score(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sharp = self._make_photo(root, "sharp.jpg")
            blurry = self._make_photo(root, "blurry.jpg")

            blurry.intelligence.is_blurry = True

            album = AnnualAlbum(year=2024, selected_photos=[sharp, blurry])
            result = AlbumScoringEngine().score(album)

            by_name = {item.photo.filename: item for item in result.scored_photos}
            self.assertLess(
                by_name["blurry.jpg"].technical_score,
                by_name["sharp.jpg"].technical_score,
            )

    def test_missing_intelligence_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._make_photo(root, "a.jpg")
            photo.intelligence = None

            album = AnnualAlbum(year=2024, selected_photos=[photo])
            result = AlbumScoringEngine().score(album)

            self.assertEqual(result.scored_count, 1)
            self.assertIsNotNone(photo.intelligence)
            self.assertIsNotNone(photo.intelligence.album_candidate_score)

    def test_explanations_are_produced(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._make_photo(root, "a.jpg")
            photo.intelligence.is_blurry = True
            photo.people = ["Bob"]
            photo.intelligence.people_names = ["Bob"]
            photo.metadata["location"] = "Rome"

            album = AnnualAlbum(year=2024, selected_photos=[photo])
            result = AlbumScoringEngine().score(album)

            explanation = result.scored_photos[0].explanation
            self.assertTrue(explanation)
            self.assertTrue(any("technical" in line.lower() for line in explanation))
            self.assertTrue(any("memory" in line.lower() for line in explanation))
            self.assertTrue(any("date" in line.lower() for line in explanation))


if __name__ == "__main__":
    unittest.main()

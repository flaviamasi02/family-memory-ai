import tempfile
import unittest
from pathlib import Path

from models.photo import Photo
from models.photo_intelligence import PhotoIntelligence


class PhotoIntelligenceTests(unittest.TestCase):
    def test_photo_intelligence_defaults_are_safe(self):
        intelligence = PhotoIntelligence()

        self.assertIsNone(intelligence.year)
        self.assertIsNone(intelligence.month)
        self.assertIsNone(intelligence.date_taken)
        self.assertFalse(intelligence.has_metadata)

        self.assertIsNone(intelligence.quality_score)
        self.assertIsNone(intelligence.blur_score)
        self.assertIsNone(intelligence.exposure_score)
        self.assertFalse(intelligence.is_blurry)

        self.assertEqual(intelligence.faces_count, 0)
        self.assertEqual(intelligence.people_names, [])

        self.assertIsNone(intelligence.duplicate_group_id)
        self.assertFalse(intelligence.is_duplicate_candidate)

        self.assertIsNone(intelligence.album_candidate_score)
        self.assertFalse(intelligence.album_selected)
        self.assertIsNone(intelligence.album_rejection_reason)

        self.assertIsNone(intelligence.ai_score)
        self.assertEqual(intelligence.ai_tags, [])
        self.assertIsNone(intelligence.ai_explanation)

    def test_photo_from_path_includes_intelligence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.jpg"
            path.write_bytes(b"fake jpg")

            photo = Photo.from_path(path)

            self.assertIsNotNone(photo.intelligence)
            self.assertFalse(photo.intelligence.has_metadata)
            self.assertIsNone(photo.intelligence.year)
            self.assertIsNone(photo.intelligence.month)

    def test_year_month_are_derived_from_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.jpg"
            path.write_bytes(b"fake jpg")

            photo = Photo.from_path(path)
            photo.metadata = {"date_taken": "2024:07:15 11:30:00"}
            photo.sync_intelligence_from_metadata()

            self.assertTrue(photo.intelligence.has_metadata)
            self.assertEqual(photo.intelligence.year, 2024)
            self.assertEqual(photo.intelligence.month, 7)
            self.assertEqual(photo.intelligence.date_taken, "2024:07:15 11:30:00")


if __name__ == "__main__":
    unittest.main()

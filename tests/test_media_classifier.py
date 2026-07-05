import tempfile
import unittest
from pathlib import Path

from core.media_classifier import MediaCategory, MediaClassifier, UserDecision
from models.photo import Photo


class MediaClassifierTests(unittest.TestCase):
    def setUp(self):
        self.classifier = MediaClassifier()

    def _make_photo(self, root: Path, filename: str, metadata=None) -> Photo:
        path = root / filename
        path.write_bytes(b"img")
        photo = Photo.from_path(path)
        photo.metadata.update(metadata or {})
        photo.sync_intelligence_from_metadata()
        return photo

    def test_classifies_screenshot_and_populates_photo_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            photo = self._make_photo(
                Path(tmpdir),
                "Screenshot_2026-01-01.png",
                {"width": 1280, "height": 720},
            )

            result = self.classifier.classify_photo(photo)

            self.assertEqual(result.media_category, MediaCategory.Screenshot)
            self.assertEqual(photo.media_category, MediaCategory.Screenshot.value)
            self.assertTrue(photo.classification_reason)
            self.assertGreater(photo.classification_confidence, 0.9)
            self.assertEqual(photo.user_decision, UserDecision.Pending.value)

    def test_classifies_invoice_from_filename(self):
        result = self.classifier.classify("invoice_2026_07.jpg", {"width": 1400, "height": 1000})
        self.assertEqual(result.media_category, MediaCategory.Invoice)

    def test_classifies_low_quality_from_dimensions(self):
        result = self.classifier.classify("tiny_photo.jpg", {"width": 240, "height": 180})
        self.assertEqual(result.media_category, MediaCategory.LowQuality)

    def test_whatsapp_meme_like_image_is_meme_or_graphic(self):
        result = self.classifier.classify(
            "WhatsApp Image 2026-07-05 funny sticker.jpg",
            {"width": 512, "height": 512, "camera_make": "", "camera_model": "", "date_taken": ""},
        )

        self.assertIn(result.media_category, {MediaCategory.Meme, MediaCategory.Graphic})
        self.assertIn("sticker", result.classification_reason.lower())

    def test_downloaded_funny_image_is_meme_or_graphic(self):
        result = self.classifier.classify(
            "downloaded_funny_lol_imgflip.jpg",
            {"width": 600, "height": 600, "camera_make": "", "camera_model": "", "date_taken": ""},
        )

        self.assertIn(result.media_category, {MediaCategory.Meme, MediaCategory.Graphic, MediaCategory.Unknown})
        self.assertTrue(result.classification_reason)

    def test_banner_image_is_advertisement_or_graphic(self):
        result = self.classifier.classify(
            "summer_banner_sale.jpg",
            {"width": 1600, "height": 300, "camera_make": "", "camera_model": "", "date_taken": ""},
        )

        self.assertIn(result.media_category, {MediaCategory.Advertisement, MediaCategory.Graphic})

    def test_small_square_without_camera_metadata_is_graphic_or_unknown(self):
        result = self.classifier.classify(
            "shared_square.jpg",
            {"width": 400, "height": 400, "camera_make": "", "camera_model": "", "date_taken": "", "has_gps": False},
        )

        self.assertIn(result.media_category, {MediaCategory.Graphic, MediaCategory.Unknown})

    def test_normal_camera_photo_remains_family_photo(self):
        result = self.classifier.classify(
            "family_trip.jpg",
            {
                "width": 4032,
                "height": 3024,
                "camera_make": "Canon",
                "camera_model": "EOS",
                "date_taken": "2026:06:10 10:00:00",
                "has_gps": True,
            },
        )

        self.assertEqual(result.media_category, MediaCategory.FamilyPhoto)
        self.assertGreaterEqual(result.classification_confidence, 0.8)

    def test_screenshot_remains_screenshot(self):
        result = self.classifier.classify(
            "IMG_1234.png",
            {"width": 1080, "height": 2340, "camera_make": "", "camera_model": "", "date_taken": ""},
        )
        self.assertEqual(result.media_category, MediaCategory.Screenshot)

    def test_document_remains_document(self):
        result = self.classifier.classify(
            "school_document_scan.jpg",
            {"width": 2400, "height": 3400, "camera_make": "", "camera_model": "", "date_taken": ""},
        )
        self.assertEqual(result.media_category, MediaCategory.Document)


if __name__ == "__main__":
    unittest.main()
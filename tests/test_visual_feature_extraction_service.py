import json
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication

from core.user_metadata_service import UserMetadataService
from core.visual_feature_extraction_service import VisualFeatureExtractionService
from learning.category_learning_engine import CategoryLearningEngine
from models.photo import Photo
from models.visual_feature_profile import VisualFeatureProfile


class VisualFeatureExtractionServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _write_image(self, path: Path, width=800, height=1200, color=QColor("white")):
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(color)
        for y in range(100, height - 100, 80):
            for x in range(80, width - 80):
                if x % 3:
                    image.setPixelColor(x, y, QColor("black"))
        self.assertTrue(image.save(str(path)))

    def test_safe_default_when_image_loading_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "broken.jpg"
            path.write_bytes(b"not an image")
            profile = VisualFeatureExtractionService().extract(path)
            self.assertEqual(profile.extraction_status, "unavailable")
            self.assertFalse(profile.has_content_evidence())

    def test_metadata_fields_are_not_visual_features(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "Screenshot_meme_document.jpg"
            self._write_image(path, 500, 500, QColor("blue"))
            profile = VisualFeatureExtractionService().extract(
                path,
                {
                    "camera_make": "Camera",
                    "date_source": "EXIF",
                    "file_size": 123,
                    "extension": ".jpg",
                },
            )
            self.assertNotIn("Screenshot_meme_document.jpg", " ".join(profile.evidence_summary))
            self.assertNotIn("camera", " ".join(profile.evidence_summary).lower())

    def test_existing_face_evidence_is_represented(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "photo.jpg"
            self._write_image(path)
            profile = VisualFeatureExtractionService().extract(
                path,
                {"has_faces": True, "face_count": 2, "face_detection_confidence": 0.82},
            )
            self.assertTrue(profile.has_faces)
            self.assertEqual(profile.face_count, 2)
            self.assertIn("faces", profile.visual_tags)

    def test_content_evidence_is_derived_from_pixels(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plain_name.jpg"
            self._write_image(path)
            profile = VisualFeatureExtractionService().extract(path)
            self.assertTrue(profile.has_text_like_regions or profile.looks_like_document)
            self.assertTrue(profile.confidence_by_feature)

    def test_sidecar_persistence_is_backward_compatible_and_corruption_safe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "photo.jpg"
            self._write_image(path)
            photo = Photo.from_path(path)
            profile = VisualFeatureProfile(has_faces=True, face_count=1, visual_tags=["faces"], extraction_status="extracted")
            photo.metadata["visual_feature_profile"] = profile.to_dict()
            photo.sync_visual_features_from_metadata()
            service = UserMetadataService(app_version="test")
            sidecar = service.save_for_photo(photo)
            data = json.loads(sidecar.read_text())
            self.assertIn("visual_feature_profile", data)

            loaded = Photo.from_path(path)
            service.apply_for_photo(loaded)
            self.assertTrue(loaded.visual_features.has_faces)

            sidecar.write_text('{bad json', encoding='utf-8')
            loaded_again = Photo.from_path(path)
            result = service.apply_for_photo(loaded_again)
            self.assertFalse(result.loaded)
            self.assertEqual(loaded_again.visual_features.extraction_status, "missing")

    def test_category_learning_consumes_visual_profile_and_ignores_metadata_only_rules(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            engine = CategoryLearningEngine(storage_root=root)
            for index in range(5):
                path = root / f"metadata_only_{index}.jpg"
                path.write_bytes(b"img")
                photo = Photo.from_path(path)
                photo.metadata.update({"width": 640, "height": 640, "camera_make": "", "date_taken": ""})
                engine.record_category_correction(photo, "unknown", "meme", "user")
            self.assertEqual(len(engine.profile.rules), 0)

            for index in range(5):
                path = root / f"visual_{index}.jpg"
                path.write_bytes(b"img")
                photo = Photo.from_path(path)
                photo.metadata["visual_feature_profile"] = VisualFeatureProfile(
                    looks_like_graphic_or_meme=True,
                    visual_tags=["graphic-like"],
                    extraction_status="extracted",
                ).to_dict()
                photo.sync_visual_features_from_metadata()
                engine.record_category_correction(photo, "unknown", "meme", "user")
            self.assertGreaterEqual(len(engine.profile.rules), 1)
            self.assertIn("visual", engine.profile.rules[0].explanation.lower())


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.category_registry import get_category_registry, reset_category_registry
from core.media_classifier import MediaClassifier
from learning.category_learning_engine import (
    get_category_learning_engine,
    reset_category_learning_engine,
)
from models.photo import Photo
from models.visual_feature_profile import VisualFeatureProfile


class CategoryLearningEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self):
        os.environ.pop("FAMILY_MEMORY_LEARNING_ROOT", None)
        os.environ.pop("FAMILY_MEMORY_CATEGORIES_ROOT", None)
        reset_category_learning_engine()
        reset_category_registry()

    def _configure_env(self, root: Path):
        os.environ["FAMILY_MEMORY_LEARNING_ROOT"] = str(root)
        os.environ["FAMILY_MEMORY_CATEGORIES_ROOT"] = str(root)
        reset_category_learning_engine()
        reset_category_registry()

    def _make_photo(self, root: Path, filename: str, metadata=None, payload: bytes = b"img") -> Photo:
        path = root / filename
        path.write_bytes(payload)
        photo = Photo.from_path(path)
        photo.metadata.update(metadata or {})
        photo.sync_intelligence_from_metadata()
        return photo

    def test_learning_event_created_from_category_correction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)
            engine = get_category_learning_engine(force_reload=True)

            photo = self._make_photo(
                root,
                "WhatsApp Image 2026-01-01 buongiorno.jpg",
                {
                    "width": 640,
                    "height": 640,
                    "camera_make": "",
                    "camera_model": "",
                    "date_taken": "",
                    "has_gps": False,
                    "date_source": "Unknown",
                },
            )

            event = engine.record_category_correction(
                photo=photo,
                previous_category="unknown",
                corrected_category="meme",
                source="user",
            )

            self.assertEqual(event.previous_category, "unknown")
            self.assertEqual(event.corrected_category, "meme")
            self.assertTrue(event.extracted_signals)
            self.assertEqual(engine.profile.total_events, 1)

    def test_signals_extracted_from_filename_dimensions_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)
            engine = get_category_learning_engine(force_reload=True)

            photo = self._make_photo(
                root,
                "WhatsApp_download_tenor_meme.jpg",
                {
                    "width": 512,
                    "height": 512,
                    "camera_make": "",
                    "camera_model": "",
                    "date_taken": "",
                    "has_gps": False,
                    "date_source": "Filename",
                },
                payload=b"x" * 50000,
            )

            signals = engine.extract_signals(photo.path, photo.metadata)

            self.assertTrue(signals.get("contains_whatsapp"))
            self.assertTrue(signals.get("contains_download"))
            self.assertTrue(signals.get("contains_tenor"))
            self.assertTrue(signals.get("contains_meme"))
            self.assertTrue(signals.get("is_small_image"))
            self.assertTrue(signals.get("is_square"))
            self.assertFalse(signals.get("has_camera_metadata"))
            self.assertIn(signals.get("file_size_bucket"), {"tiny", "small", "medium", "large"})

    def test_no_rule_created_before_minimum_support(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)
            engine = get_category_learning_engine(force_reload=True)

            for index in range(4):
                photo = self._make_photo(
                    root,
                    f"WhatsApp Image {index} meme.jpg",
                    {
                        "width": 600,
                        "height": 600,
                        "camera_make": "",
                        "camera_model": "",
                        "date_taken": "",
                        "has_gps": False,
                        "date_source": "Unknown",
                    },
                )
                engine.record_category_correction(photo, "unknown", "meme", "user")

            self.assertEqual(engine.profile.total_events, 4)
            self.assertEqual(len(engine.profile.rules), 0)

    def test_rule_created_after_repeated_similar_corrections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)
            engine = get_category_learning_engine(force_reload=True)

            for index in range(5):
                photo = self._make_photo(
                    root,
                    f"WhatsApp Image {index} buongiorno.jpg",
                    {
                        "width": 640,
                        "height": 640,
                        "camera_make": "",
                        "camera_model": "",
                        "date_taken": "",
                        "has_gps": False,
                        "date_source": "Unknown",
                    },
                )
                photo.metadata["visual_feature_profile"] = VisualFeatureProfile(
                    looks_like_graphic_or_meme=True,
                    visual_tags=["graphic-like"],
                    extraction_status="extracted",
                ).to_dict()
                photo.sync_visual_features_from_metadata()
                engine.record_category_correction(photo, "unknown", "meme", "user")

            self.assertGreaterEqual(len(engine.profile.rules), 1)
            first_rule = engine.profile.rules[0]
            self.assertEqual(first_rule.target_category, "meme")
            self.assertGreaterEqual(first_rule.support_count, 5)

    def test_learned_rule_applies_to_new_similar_image_and_reason_mentions_learning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)
            engine = get_category_learning_engine(force_reload=True)

            for index in range(5):
                photo = self._make_photo(
                    root,
                    f"WhatsApp Image {index} meme.jpg",
                    {
                        "width": 640,
                        "height": 640,
                        "camera_make": "",
                        "camera_model": "",
                        "date_taken": "",
                        "has_gps": False,
                        "date_source": "Unknown",
                    },
                )
                photo.metadata["visual_feature_profile"] = VisualFeatureProfile(
                    looks_like_graphic_or_meme=True,
                    visual_tags=["graphic-like"],
                    extraction_status="extracted",
                ).to_dict()
                photo.sync_visual_features_from_metadata()
                engine.record_category_correction(photo, "unknown", "meme", "user")

            classifier = MediaClassifier()
            target_photo = self._make_photo(
                root,
                "WhatsApp Image new meme sample.jpg",
                {
                    "width": 620,
                    "height": 620,
                    "camera_make": "",
                    "camera_model": "",
                    "date_taken": "",
                    "has_gps": False,
                    "date_source": "Unknown",
                },
            )

            target_photo.metadata["visual_feature_profile"] = VisualFeatureProfile(
                looks_like_graphic_or_meme=True,
                visual_tags=["graphic-like"],
                extraction_status="extracted",
            ).to_dict()
            target_photo.sync_visual_features_from_metadata()

            classification = classifier.classify_photo(target_photo)

            self.assertEqual(target_photo.media_category, "meme")
            self.assertIn("learned user rule", target_photo.classification_reason.lower())
            self.assertIn("learned", classification.classification_reason.lower())

    def test_profile_persisted_and_loaded_on_next_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)

            engine = get_category_learning_engine(force_reload=True)
            for index in range(5):
                photo = self._make_photo(
                    root,
                    f"WhatsApp Image {index} meme.jpg",
                    {
                        "width": 640,
                        "height": 640,
                        "camera_make": "",
                        "camera_model": "",
                        "date_taken": "",
                        "has_gps": False,
                        "date_source": "Unknown",
                    },
                )
                photo.metadata["visual_feature_profile"] = VisualFeatureProfile(
                    looks_like_graphic_or_meme=True,
                    visual_tags=["graphic-like"],
                    extraction_status="extracted",
                ).to_dict()
                photo.sync_visual_features_from_metadata()
                engine.record_category_correction(photo, "unknown", "meme", "user")

            storage = engine.storage_path
            self.assertTrue(storage.exists())

            reset_category_learning_engine()
            loaded = get_category_learning_engine(force_reload=True)
            self.assertGreaterEqual(loaded.profile.total_events, 5)
            self.assertGreaterEqual(len(loaded.profile.rules), 1)

    def test_bulk_category_correction_creates_multiple_learning_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)
            engine = get_category_learning_engine(force_reload=True)

            photos = [
                self._make_photo(
                    root,
                    f"bulk_{idx}_whatsapp.jpg",
                    {
                        "width": 700,
                        "height": 700,
                        "camera_make": "",
                        "camera_model": "",
                        "date_taken": "",
                        "has_gps": False,
                        "date_source": "Unknown",
                    },
                )
                for idx in range(3)
            ]

            for photo in photos:
                engine.record_category_correction(photo, "unknown", "meme", "user_bulk")

            self.assertEqual(engine.profile.total_events, 3)
            self.assertEqual(engine.profile.category_event_counts.get("meme"), 3)

    def test_custom_category_minimum_support_is_three(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)

            registry = get_category_registry(force_reload=True)
            registry.create_user_category("Travel")

            engine = get_category_learning_engine(force_reload=True)
            for index in range(3):
                photo = self._make_photo(
                    root,
                    f"travel_{index}.jpg",
                    {
                        "width": 1024,
                        "height": 768,
                        "camera_make": "Canon",
                        "camera_model": "EOS",
                        "date_taken": "2024:01:01 10:00:00",
                        "has_gps": False,
                        "date_source": "EXIF",
                    },
                )
                photo.metadata["visual_feature_profile"] = VisualFeatureProfile(
                    has_faces=True,
                    face_count=2,
                    visual_tags=["faces"],
                    extraction_status="extracted",
                ).to_dict()
                photo.sync_visual_features_from_metadata()
                engine.record_category_correction(photo, "family_photo", "travel", "user")

            self.assertEqual(engine.profile.total_events, 3)
            self.assertTrue(any(rule.target_category == "travel" for rule in engine.profile.rules))


if __name__ == "__main__":
    unittest.main()

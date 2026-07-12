import os
import tempfile
import unittest
from pathlib import Path

from core.category_registry import reset_category_registry
from learning.category_learning_engine import CategoryLearningEngine
from models.visual_feature_profile import VisualFeatureProfile


class ContentBasedLearningEngineTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("FAMILY_MEMORY_LEARNING_ROOT", None)
        os.environ.pop("FAMILY_MEMORY_CATEGORIES_ROOT", None)
        reset_category_registry()

    def _photo(self, root: Path, name: str, profile: VisualFeatureProfile | None = None):
        path = root / name; path.write_bytes(b"fake")
        class DummyPhoto:
            pass
        photo = DummyPhoto()
        photo.path = path
        photo.file_size = path.stat().st_size
        photo.metadata = {}
        photo.visual_features = profile or VisualFeatureProfile()
        if profile is not None:
            photo.metadata["visual_feature_profile"] = profile.to_dict()
        return photo

    def test_existing_visual_profile_updates_category_visual_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); os.environ["FAMILY_MEMORY_LEARNING_ROOT"] = str(root); os.environ["FAMILY_MEMORY_CATEGORIES_ROOT"] = str(root)
            engine = CategoryLearningEngine(root)
            profile = VisualFeatureProfile(has_text_like_regions=True, looks_like_graphic_or_meme=True, dominant_orientation="landscape", visual_tags=["text-like-regions", "graphic-like"], extraction_status="extracted")
            for i in range(3):
                engine.record_category_correction(self._photo(root, f"ad{i}.jpg", profile), "unknown", "advertisement", "user")
            summary = engine.learning_summary()
            learned = summary["visual_profiles"]["advertisement"]
            self.assertEqual(learned["visual_examples"], 3)
            self.assertIn("high text density", learned["explanation_summaries"])
            self.assertIn("flat graphic structure", learned["explanation_summaries"])

    def test_missing_visual_features_are_queued_and_completed_later(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); os.environ["FAMILY_MEMORY_LEARNING_ROOT"] = str(root); os.environ["FAMILY_MEMORY_CATEGORIES_ROOT"] = str(root)
            engine = CategoryLearningEngine(root)
            event = engine.record_category_correction(self._photo(root, "doc.jpg"), "unknown", "document", "user")
            self.assertEqual(engine.learning_summary()["pending_visual_analyses"], 1)
            visual = VisualFeatureProfile(has_text_like_regions=True, looks_like_document=True, dominant_orientation="portrait", visual_tags=["document-like"], extraction_status="extracted")
            self.assertTrue(engine.record_completed_visual_analysis(event.event_id, visual))
            summary = engine.learning_summary()
            self.assertEqual(summary["pending_visual_analyses"], 0)
            self.assertEqual(summary["visual_profiles"]["document"]["visual_examples"], 1)


    def test_background_worker_executes_queue_and_refreshes_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); os.environ["FAMILY_MEMORY_LEARNING_ROOT"] = str(root); os.environ["FAMILY_MEMORY_CATEGORIES_ROOT"] = str(root)
            engine = CategoryLearningEngine(root)

            class Extractor:
                def __init__(self):
                    self.calls = []
                def extract(self, path):
                    self.calls.append(Path(path).name)
                    return VisualFeatureProfile(has_text_like_regions=True, looks_like_document=True, dominant_orientation="portrait", visual_tags=["document-like"], extraction_status="extracted")
                def apply_profile_to_photo(self, photo, profile):
                    photo.visual_features = profile
                    photo.metadata["visual_feature_profile"] = profile.to_dict()

            extractor = Extractor()
            for i in range(3):
                engine.record_category_correction(self._photo(root, f"doc_worker_{i}.jpg"), "unknown", "document", f"user_{i}")

            self.assertEqual(engine.learning_summary()["pending_visual_analyses"], 3)
            self.assertTrue(engine.start_pending_visual_analysis_worker(limit=2, extractor=extractor))
            self.assertTrue(engine.wait_for_pending_visual_analysis(timeout=5.0))

            summary = engine.learning_summary()
            self.assertEqual(len(extractor.calls), 3)
            self.assertEqual(summary["pending_visual_analyses"], 0)
            self.assertEqual(summary["visual_profiles"]["document"]["visual_examples"], 3)
            self.assertIn("document-like page structure", summary["visual_profiles"]["document"]["explanation_summaries"])
            self.assertGreaterEqual(summary["diagnostics"]["visual_analysis_workers_started"], 1)
            self.assertGreaterEqual(summary["diagnostics"]["visual_profiles_completed"], 3)

            reloaded = CategoryLearningEngine(root)
            reloaded_summary = reloaded.learning_summary()
            self.assertEqual(reloaded_summary["pending_visual_analyses"], 0)
            self.assertEqual(reloaded_summary["visual_profiles"]["document"]["visual_examples"], 3)

    def test_repeated_same_correction_is_idempotent_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); os.environ["FAMILY_MEMORY_LEARNING_ROOT"] = str(root); os.environ["FAMILY_MEMORY_CATEGORIES_ROOT"] = str(root)
            engine = CategoryLearningEngine(root)
            visual = VisualFeatureProfile(looks_like_screenshot=True, dominant_orientation="portrait", visual_tags=["screenshot-like"], extraction_status="extracted")
            photo = self._photo(root, "screen.jpg", visual)
            engine.record_category_correction(photo, "unknown", "screenshot", "user")
            engine.record_category_correction(photo, "unknown", "screenshot", "user")
            self.assertEqual(engine.learning_summary()["total_events"], 1)
            reloaded = CategoryLearningEngine(root)
            self.assertEqual(reloaded.learning_summary()["visual_profiles"]["screenshot"]["visual_examples"], 1)
            self.assertGreater(reloaded.storage_path.stat().st_size, 0)

    def test_metadata_or_filename_only_does_not_create_visual_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); os.environ["FAMILY_MEMORY_LEARNING_ROOT"] = str(root); os.environ["FAMILY_MEMORY_CATEGORIES_ROOT"] = str(root)
            engine = CategoryLearningEngine(root)
            for i in range(6):
                engine.record_category_correction(self._photo(root, f"advertisement_{i}.jpg"), "unknown", "advertisement", "user")
            summary = engine.learning_summary()
            self.assertNotIn("advertisement", summary["visual_profiles"])
            self.assertEqual(summary["rules"], [])

    def test_workflow_category_does_not_create_visual_profile_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); os.environ["FAMILY_MEMORY_LEARNING_ROOT"] = str(root); os.environ["FAMILY_MEMORY_CATEGORIES_ROOT"] = str(root)
            engine = CategoryLearningEngine(root)
            visual = VisualFeatureProfile(has_text_like_regions=True, extraction_status="extracted", visual_tags=["text-like-regions"])
            engine.record_category_correction(self._photo(root, "low.jpg", visual), "unknown", "low_quality", "user")
            self.assertNotIn("low_quality", engine.learning_summary()["visual_profiles"])

    def test_malformed_old_profile_fails_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = root / ".familymemory"; path.mkdir(); (path / "category_learning_profile.json").write_text("{bad", encoding="utf-8")
            engine = CategoryLearningEngine(root)
            self.assertEqual(engine.learning_summary()["total_events"], 0)

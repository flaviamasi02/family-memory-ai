import json
import os
import tempfile
import unittest
from pathlib import Path

from core.category_registry import reset_category_registry
from learning.preference_learning_engine import (
    PreferenceLearningEngine,
    get_preference_learning_engine,
    reset_preference_learning_engine,
)
from models.photo import Photo


class PreferenceLearningEngineTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("FAMILY_MEMORY_LEARNING_ROOT", None)
        os.environ.pop("FAMILY_MEMORY_CATEGORIES_ROOT", None)
        reset_preference_learning_engine()
        reset_category_registry()

    def _configure_env(self, root: Path):
        os.environ["FAMILY_MEMORY_LEARNING_ROOT"] = str(root)
        os.environ["FAMILY_MEMORY_CATEGORIES_ROOT"] = str(root)
        reset_preference_learning_engine()
        reset_category_registry()

    def _make_photo(self, root: Path, filename: str, metadata=None) -> Photo:
        path = root / filename
        path.write_bytes(b"img")
        photo = Photo.from_path(path)
        photo.metadata.update(metadata or {})
        photo.sync_intelligence_from_metadata()
        return photo

    def test_empty_profile_creation_is_safe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)

            engine = get_preference_learning_engine(force_reload=True)

            self.assertEqual(engine.profile.total_events, 0)
            self.assertEqual(engine.profile.signals, [])
            self.assertEqual(engine.profile.signal_counts, {})
            self.assertEqual(engine.learning_summary()["total_events"], 0)

    def test_event_recording_creates_preference_signal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)
            engine = get_preference_learning_engine(force_reload=True)
            photo = self._make_photo(
                root,
                "family.jpg",
                {
                    "effective_media_category": "family_photo",
                    "automatic_media_category": "family_photo",
                    "classification_confidence": 0.9,
                },
            )

            event = engine.record_decision(photo, "pending", "approve_for_album", "user")

            self.assertEqual(event.decision, "approve_for_album")
            self.assertEqual(engine.profile.total_events, 1)
            self.assertTrue(any(signal.signal_type == "decision_preference" for signal in engine.profile.signals))
            self.assertTrue(any(signal.signal_type == "positive_memory_preference" for signal in engine.profile.signals))

    def test_signal_aggregation_counts_repeated_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)
            engine = get_preference_learning_engine(force_reload=True)

            for index in range(3):
                photo = self._make_photo(
                    root,
                    f"doc_{index}.jpg",
                    {
                        "effective_media_category": "document",
                        "automatic_media_category": "document",
                    },
                )
                engine.record_decision(photo, "pending", "document", "user")

            cleanup_signals = [
                signal
                for signal in engine.profile.signals
                if signal.signal_type == "cleanup_preference" and signal.target == "document"
            ]
            self.assertEqual(len(cleanup_signals), 1)
            self.assertEqual(cleanup_signals[0].support_count, 3)
            self.assertGreater(cleanup_signals[0].strength, 0.35)
            self.assertEqual(engine.profile.signal_counts["cleanup_preference"], 3)

    def test_profile_persists_and_reloads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)
            engine = get_preference_learning_engine(force_reload=True)
            photo = self._make_photo(root, "meme.jpg", {"effective_media_category": "meme"})

            engine.record_category_correction(photo, "unknown", "meme", "user")

            self.assertTrue(engine.storage_path.exists())
            reset_preference_learning_engine()
            loaded = get_preference_learning_engine(force_reload=True)

            self.assertEqual(loaded.profile.total_events, 1)
            self.assertTrue(any(signal.target == "meme" for signal in loaded.profile.signals))

    def test_corrupted_profile_falls_back_to_empty_profile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)
            storage = root / ".familymemory" / "preference_learning_profile.json"
            storage.parent.mkdir(parents=True, exist_ok=True)
            storage.write_text("{not json", encoding="utf-8")

            engine = PreferenceLearningEngine(storage_root=root)

            self.assertEqual(engine.profile.total_events, 0)
            self.assertEqual(engine.profile.signals, [])

    def test_explainability_text_present_in_signals_and_persisted_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)
            engine = get_preference_learning_engine(force_reload=True)
            photo = self._make_photo(root, "screen.jpg", {"effective_media_category": "screenshot"})

            engine.record_category_correction(photo, "unknown", "screenshot", "user")

            self.assertTrue(all(signal.explanation for signal in engine.profile.signals))
            data = json.loads(engine.storage_path.read_text(encoding="utf-8"))
            explanations = [signal["explanation"] for signal in data["signals"]]
            self.assertTrue(all("User" in explanation for explanation in explanations))

    def test_summary_includes_strongest_signals_and_last_updated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._configure_env(root)
            engine = get_preference_learning_engine(force_reload=True)
            photo = self._make_photo(root, "keep.jpg", {"effective_media_category": "family_photo"})

            engine.record_decision(photo, "pending", "keep", "user")
            summary = engine.learning_summary()

            self.assertEqual(summary["total_events"], 1)
            self.assertTrue(summary["signal_counts"])
            self.assertTrue(summary["strongest_preference_signals"])
            self.assertTrue(summary["last_updated_at"])


if __name__ == "__main__":
    unittest.main()

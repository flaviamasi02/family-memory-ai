import os
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from learning.category_learning_engine import (
    get_category_learning_engine,
    reset_category_learning_engine,
)
from learning.preference_learning_engine import (
    get_preference_learning_engine,
    reset_preference_learning_engine,
)
from models.photo import Photo
from ui.learning_summary_dialog import LearningSummaryDialog


class LearningSummaryDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self):
        os.environ.pop("FAMILY_MEMORY_LEARNING_ROOT", None)
        reset_category_learning_engine()
        reset_preference_learning_engine()

    def _make_photo(self, root: Path, filename: str) -> Photo:
        path = root / filename
        path.write_bytes(b"img")
        photo = Photo.from_path(path)
        photo.metadata.update(
            {
                "effective_media_category": "unknown",
                "automatic_media_category": "unknown",
                "classification_confidence": 0.5,
            }
        )
        photo.sync_intelligence_from_metadata()
        return photo

    def test_learning_summary_displays_stored_event_timestamps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            os.environ["FAMILY_MEMORY_LEARNING_ROOT"] = str(root)
            reset_category_learning_engine()
            reset_preference_learning_engine()

            category_engine = get_category_learning_engine(force_reload=True)
            preference_engine = get_preference_learning_engine(force_reload=True)
            event = None
            for index in range(5):
                photo = self._make_photo(root, f"learned_{index}.jpg")
                event = category_engine.record_category_correction(photo, "unknown", "meme", "user")
                preference_engine.record_category_correction(photo, "unknown", "meme", "user")

            dialog = LearningSummaryDialog(
                category_engine,
                preference_engine=preference_engine,
            )

            self.assertIsNotNone(event)
            expected_date = event.timestamp[:10]
            category_event_text = " ".join(
                dialog.events_list.item(index).text()
                for index in range(dialog.events_list.count())
            )
            rule_text = " ".join(
                dialog.rules_list.item(index).text()
                for index in range(dialog.rules_list.count())
            )
            preference_text = " ".join(
                dialog.preference_list.item(index).text()
                for index in range(dialog.preference_list.count())
            )

            self.assertIn(expected_date, category_event_text)
            self.assertIn("learned", rule_text.lower())
            self.assertIn(expected_date, preference_text)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
import os
from pathlib import Path

from core.category_registry import get_category_registry, reset_category_registry
from core.photo_cleanup_engine import PhotoCleanupEngine
from core.photo_cleanup_engine import PhotoCleanupClassification
from models.photo import Photo
from models.photo_intelligence import PhotoIntelligence


class PhotoCleanupEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = PhotoCleanupEngine()

    def tearDown(self):
        os.environ.pop("FAMILY_MEMORY_CATEGORIES_ROOT", None)
        reset_category_registry()

    def _make_photo(
        self,
        root: Path,
        filename: str,
        content: bytes,
        metadata=None,
    ) -> Photo:
        path = root / filename
        path.write_bytes(content)
        photo = Photo.from_path(path)
        photo.metadata.update(metadata or {})
        photo.intelligence = photo.intelligence or PhotoIntelligence()
        photo.sync_intelligence_from_metadata()
        return photo

    def test_document_classification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            photo = self._make_photo(Path(tmpdir), "contratto_scan.jpg", b"x" * 2048)
            result = self.engine.classify_photos([photo])

            self.assertEqual(result.classifications[0].category, "document_or_scan")

    def test_advertisement_classification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            photo = self._make_photo(Path(tmpdir), "summer_sale_banner.jpg", b"x" * 2048)
            result = self.engine.classify_photos([photo])

            self.assertEqual(result.classifications[0].category, "advertisement")

    def test_screenshot_classification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            photo = self._make_photo(Path(tmpdir), "Screenshot_2024-07-05.png", b"x" * 2048)
            result = self.engine.classify_photos([photo])

            self.assertEqual(result.classifications[0].category, "screenshot")

    def test_video_classification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            photo = self._make_photo(Path(tmpdir), "clip.mp4", b"x" * 2048)
            result = self.engine.classify_photos([photo])

            self.assertEqual(result.classifications[0].category, "video")

    def test_family_photo_candidate_classification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            photo = self._make_photo(
                Path(tmpdir),
                "family.jpg",
                b"x" * 4096,
                {"width": 2048, "height": 1536},
            )
            result = self.engine.classify_photos([photo])

            self.assertEqual(result.classifications[0].category, "family_photo_candidate")
            self.assertEqual(result.classifications[0].recommended_action, "keep")

    def test_low_quality_classification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            photo = self._make_photo(
                Path(tmpdir),
                "tiny.jpg",
                b"x" * 4096,
                {"width": 160, "height": 120},
            )
            result = self.engine.classify_photos([photo])

            self.assertEqual(result.classifications[0].category, "low_quality_photo")

    def test_exact_duplicate_hash_classification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = self._make_photo(root, "dup_a.jpg", b"z" * 4096, {"width": 800, "height": 600})
            second = self._make_photo(root, "dup_b.jpg", b"z" * 4096, {"width": 640, "height": 480})
            result = self.engine.classify_photos([first, second])

            categories = {item.photo.display_name(): item.category for item in result.classifications}
            self.assertIn("duplicate_candidate", categories.values())

    def test_duplicate_keeps_largest_or_better_quality_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            keeper = self._make_photo(root, "keeper.jpg", b"a" * 4096, {"width": 2000, "height": 1500})
            duplicate = self._make_photo(root, "duplicate.jpg", b"a" * 4096, {"width": 640, "height": 480})
            result = self.engine.classify_photos([keeper, duplicate])

            by_name = {item.photo.display_name(): item for item in result.classifications}
            self.assertEqual(by_name["keeper.jpg"].category, "family_photo_candidate")
            self.assertEqual(by_name["duplicate.jpg"].category, "duplicate_candidate")

    def test_cleanup_flag_controls_default_action(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["FAMILY_MEMORY_CATEGORIES_ROOT"] = tmpdir
            reset_category_registry()
            registry = get_category_registry(force_reload=True)
            registry.create_user_category("Receipts To Delete", is_cleanup_category=True, is_album_candidate=False)

            action = self.engine._default_recommended_action("receipts_to_delete", registry)
            self.assertEqual(action, "move_to_cleanup_review")

    def test_album_candidate_flag_controls_photo_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["FAMILY_MEMORY_CATEGORIES_ROOT"] = tmpdir
            reset_category_registry()
            registry = get_category_registry(force_reload=True)
            registry.create_user_category("To Print", is_cleanup_category=False, is_album_candidate=True)

            photo = self._make_photo(Path(tmpdir), "sample.jpg", b"x" * 4096, {"width": 1600, "height": 1200})
            classification = PhotoCleanupClassification(
                photo=photo,
                category="to_print",
                confidence=0.81,
                reasons=["Manual category assignment."],
                recommended_action="keep",
            )
            self.engine._apply_classification_to_photo(classification)

            self.assertTrue(bool(photo.metadata.get("is_album_relevant_candidate", False)))

    def test_system_category_flag_update_changes_cleanup_action_without_changing_id_logic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["FAMILY_MEMORY_CATEGORIES_ROOT"] = tmpdir
            reset_category_registry()
            registry = get_category_registry(force_reload=True)
            registry.update_category_properties(
                "meme_or_graphic",
                display_name="Funny Images",
                is_cleanup_category=False,
            )

            photo = self._make_photo(Path(tmpdir), "meme_funny.jpg", b"x" * 4096, {"width": 600, "height": 600})
            result = self.engine.classify_photos([photo])
            cls = result.classifications[0]

            self.assertEqual(cls.category, "meme_or_graphic")
            self.assertEqual(cls.recommended_action, "review")


if __name__ == "__main__":
    unittest.main()
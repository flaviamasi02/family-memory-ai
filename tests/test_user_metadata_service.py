import tempfile
import unittest
from pathlib import Path
import json

from core.photo_scanner import find_photos
from core.user_metadata_service import UserMetadataService
from models.photo import Photo


class UserMetadataServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = UserMetadataService(app_version="test-1.0")

    def _make_photo(self, path: Path) -> Photo:
        path.write_bytes(b"img-bytes")
        photo = Photo.from_path(path)
        photo.automatic_media_category = "family_photo"
        photo.user_corrected_media_category = "advertisement"
        photo.effective_media_category = "advertisement"
        photo.media_category = "advertisement"
        photo.user_decision = "keep"
        photo.classification_reason = "Manual override by user"
        photo.metadata.update(
            {
                "automatic_media_category": "family_photo",
                "user_corrected_media_category": "advertisement",
                "effective_media_category": "advertisement",
                "media_category": "advertisement",
                "user_decision": "keep",
                "classification_reason": "Manual override by user",
            }
        )
        photo.sync_intelligence_from_metadata()
        return photo

    def test_sidecar_file_created_with_expected_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "photo.jpg"
            photo = self._make_photo(image_path)

            sidecar = self.service.save_for_photo(photo)

            self.assertIsNotNone(sidecar)
            self.assertTrue(sidecar.exists())
            self.assertEqual(sidecar.name, "photo.familymemory.json")

    def test_category_correction_saved_to_sidecar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "photo.jpg"
            photo = self._make_photo(image_path)

            sidecar = self.service.save_for_photo(photo)
            data = json.loads(sidecar.read_text(encoding="utf-8"))

            self.assertEqual(data["automatic_media_category"], "family_photo")
            self.assertEqual(data["user_corrected_media_category"], "advertisement")
            self.assertEqual(data["effective_media_category"], "advertisement")

    def test_decision_saved_to_sidecar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "photo.jpg"
            photo = self._make_photo(image_path)
            photo.user_decision = "approve_for_album"
            photo.metadata["user_decision"] = "approve_for_album"

            sidecar = self.service.save_for_photo(photo)
            data = json.loads(sidecar.read_text(encoding="utf-8"))

            self.assertEqual(data["user_decision"], "approve_for_album")
            self.assertEqual(data["app_version"], "test-1.0")

    def test_sidecar_loaded_on_next_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "family.jpg"
            photo = self._make_photo(image_path)
            self.service.save_for_photo(photo)

            imported = find_photos(str(root))
            self.assertEqual(len(imported), 1)
            loaded = imported[0]

            self.assertEqual(loaded.user_corrected_media_category, "advertisement")
            self.assertEqual(loaded.user_decision, "keep")

    def test_effective_category_uses_saved_correction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "family.jpg"
            photo = self._make_photo(image_path)
            self.service.save_for_photo(photo)

            loaded_photo = Photo.from_path(image_path)
            loaded_photo.metadata = {"automatic_media_category": "family_photo"}
            loaded_photo.sync_intelligence_from_metadata()
            self.service.apply_for_photo(loaded_photo)

            self.assertEqual(loaded_photo.effective_media_category, "advertisement")
            self.assertEqual(loaded_photo.media_category, "advertisement")

    def test_missing_sidecar_is_safe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "family.jpg"
            image_path.write_bytes(b"img")
            photo = Photo.from_path(image_path)
            photo.metadata = {"automatic_media_category": "family_photo"}
            photo.sync_intelligence_from_metadata()

            result = self.service.apply_for_photo(photo)

            self.assertFalse(result.loaded)
            self.assertFalse(result.identity_match)
            self.assertFalse(result.identity_mismatch_warning)
            self.assertEqual(photo.user_corrected_media_category, "")

    def test_changed_file_metadata_is_loaded_cautiously(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "family.jpg"
            photo = self._make_photo(image_path)
            self.service.save_for_photo(photo)

            image_path.write_bytes(b"changed-and-larger-image-bytes")
            changed_photo = Photo.from_path(image_path)
            changed_photo.metadata = {"automatic_media_category": "family_photo"}
            changed_photo.sync_intelligence_from_metadata()

            result = self.service.apply_for_photo(changed_photo)

            self.assertTrue(result.loaded)
            self.assertFalse(result.identity_match)
            self.assertTrue(result.identity_mismatch_warning)
            self.assertEqual(changed_photo.user_corrected_media_category, "advertisement")
            self.assertEqual(changed_photo.user_decision, "keep")
            self.assertEqual(changed_photo.metadata.get("user_metadata_warning"), "identity_mismatch")


if __name__ == "__main__":
    unittest.main()

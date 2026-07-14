import os
import tempfile
import unittest
from pathlib import Path

from vision.evaluation_sources import another_folder_source, current_library_source, selected_photos_source

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class MobileCLIPEvaluationSourceTests(unittest.TestCase):
    def _photo(self, root: Path, name: str):
        path = root / name
        path.write_bytes(b"img")
        return type("LoadedPhoto", (), {"path": path})()

    def test_current_imported_library_returns_loaded_photo_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photos = [self._photo(root, "a.jpg"), self._photo(root, "b.jpg")]
            result = current_library_source(photos, 100)
            self.assertTrue(result.available)
            self.assertEqual(list(result.paths), [photos[0].path, photos[1].path])

    def test_current_imported_library_unavailable_before_import(self):
        result = current_library_source([], 100)
        self.assertFalse(result.available)
        self.assertIn("Import a photo library first", result.message)

    def test_selected_photos_returns_only_selected_paths_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selected = [self._photo(root, "a.jpg"), self._photo(root, "b.jpg")]
            result = selected_photos_source([selected[0], selected[1], selected[0]], 100)
            self.assertTrue(result.available)
            self.assertEqual(list(result.paths), [selected[0].path, selected[1].path])

    def test_selected_photos_with_no_selection_is_clear_unavailable_state(self):
        result = selected_photos_source([], 100)
        self.assertFalse(result.available)
        self.assertEqual(result.message, "Select one or more photos first.")

    def test_maximum_sample_cap_is_respected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photos = [self._photo(root, f"{idx}.jpg") for idx in range(5)]
            result = current_library_source(photos, 3)
            self.assertEqual(result.available_count, 5)
            self.assertEqual(result.sample_count, 3)
            self.assertEqual(len(result.paths), 3)

    def test_another_folder_preserves_bounded_folder_behavior(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for name in ["a.jpg", "b.png", "c.txt", "d.heic"]:
                (root / name).write_bytes(b"x")
            result = another_folder_source(root, 2)
            self.assertTrue(result.available)
            self.assertEqual(result.sample_count, 2)
            self.assertEqual(len(result.paths), 2)
            self.assertTrue(all(path.suffix.lower() in {".jpg", ".png", ".heic"} for path in result.paths))

    def test_source_resolution_is_preview_only_until_caller_uses_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._photo(root, "a.jpg")
            result = current_library_source([photo], 100)
            self.assertEqual(result.sample_count, 1)
            self.assertEqual(list(result.paths), [photo.path])
            self.assertNotIn("report_path", result.__dict__)

    def test_switching_source_resolution_does_not_analyze_images(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._photo(root, "a.jpg")
            library = current_library_source([photo], 100)
            selected = selected_photos_source([photo], 100)
            self.assertEqual(library.paths, selected.paths)
            self.assertEqual(library.source_label, "Current imported library")
            self.assertEqual(selected.source_label, "Selected photos")


if __name__ == "__main__":
    unittest.main()

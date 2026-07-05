import tempfile
import unittest
from pathlib import Path

from core.safe_bulk_delete import QUARANTINE_FOLDER_NAME, move_files_to_quarantine


class SafeBulkDeleteTests(unittest.TestCase):
    def test_files_moved_to_quarantine_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            original = root / "family.jpg"
            original.write_bytes(b"image")

            result = move_files_to_quarantine([original], root)

            self.assertEqual(result.moved_count, 1)
            self.assertFalse(original.exists())
            self.assertTrue((root / QUARANTINE_FOLDER_NAME / "family.jpg").exists())

    def test_duplicate_filenames_handled_safely(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            nested = root / "nested"
            nested.mkdir()
            first = root / "photo.jpg"
            second = nested / "photo.jpg"
            first.write_bytes(b"first")
            second.write_bytes(b"second")

            result = move_files_to_quarantine([first, second], root)

            quarantine = root / QUARANTINE_FOLDER_NAME
            self.assertEqual(result.moved_count, 2)
            self.assertTrue((quarantine / "photo.jpg").exists())
            self.assertTrue((quarantine / "photo_1.jpg").exists())

    def test_missing_files_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            missing = root / "missing.jpg"

            result = move_files_to_quarantine([missing], root)

            self.assertEqual(result.moved_count, 0)
            self.assertEqual(result.skipped_count, 1)
            self.assertIn(str(missing), result.skipped_files)

    def test_no_permanent_deletion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            original = root / "keep_safe.jpg"
            original.write_bytes(b"image")

            result = move_files_to_quarantine([original], root)

            moved = result.moved_files[0]
            self.assertTrue(moved.exists())
            self.assertEqual(moved.read_bytes(), b"image")


if __name__ == "__main__":
    unittest.main()
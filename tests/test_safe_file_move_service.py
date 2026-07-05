import tempfile
import unittest
from pathlib import Path

from core.safe_file_move_service import CLEANUP_REVIEW_FOLDER_NAME, move_files_to_cleanup_review


class SafeFileMoveServiceTests(unittest.TestCase):
    def test_safe_move_creates_cleanup_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            original = root / "family.jpg"
            original.write_bytes(b"image")

            result = move_files_to_cleanup_review([original], root)

            self.assertEqual(result.moved_count, 1)
            self.assertTrue((root / CLEANUP_REVIEW_FOLDER_NAME).exists())

    def test_duplicate_destination_filenames_handled_safely(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            nested = root / "nested"
            nested.mkdir()
            first = root / "same.jpg"
            second = nested / "same.jpg"
            first.write_bytes(b"first")
            second.write_bytes(b"second")

            result = move_files_to_cleanup_review([first, second], root)

            destination = root / CLEANUP_REVIEW_FOLDER_NAME
            self.assertEqual(result.moved_count, 2)
            self.assertTrue((destination / "same.jpg").exists())
            self.assertTrue((destination / "same_1.jpg").exists())

    def test_missing_files_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            missing = root / "missing.jpg"

            result = move_files_to_cleanup_review([missing], root)

            self.assertEqual(result.skipped_count, 1)
            self.assertIn(str(missing), result.skipped_files)

    def test_no_permanent_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            original = root / "keep_safe.jpg"
            original.write_bytes(b"image")

            result = move_files_to_cleanup_review([original], root)

            self.assertEqual(result.failed_count, 0)
            self.assertTrue(result.moved_files[0].exists())
            self.assertEqual(result.moved_files[0].read_bytes(), b"image")


if __name__ == "__main__":
    unittest.main()
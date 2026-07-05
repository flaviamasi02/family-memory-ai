import os
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from models.photo import Photo
from models.photo_intelligence import PhotoIntelligence
from ui.image_preview_dialog import ImagePreviewDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class ImagePreviewDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _flush_ui(self, wait_ms: int = 0):
        if wait_ms > 0:
            QTest.qWait(wait_ms)
        for _ in range(10):
            self._app.processEvents()

    def _make_photo(self, path: Path, with_file: bool = True) -> Photo:
        if with_file:
            pix = QPixmap(420, 300)
            pix.fill(Qt.GlobalColor.red)
            self.assertTrue(pix.save(str(path), "JPG"))

        photo = Photo(
            path=path,
            filename=path.name,
            extension=path.suffix.lower(),
            file_size=1024,
            created_at=None,
            modified_at=None,
            intelligence=PhotoIntelligence(),
            metadata={},
        )
        return photo

    def test_preview_uses_original_file_when_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._make_photo(root / "original.jpg", with_file=True)
            photo.metadata["effective_media_category"] = "family_photo"
            photo.metadata["user_decision"] = "approve_for_album"
            photo.metadata["classification_confidence"] = 0.88
            photo.sync_intelligence_from_metadata()

            dialog = ImagePreviewDialog()
            dialog.set_items([photo], start_index=0)
            dialog.show()
            self._flush_ui(wait_ms=60)

            self.assertEqual(dialog.current_filename(), "original.jpg")
            self.assertEqual(dialog.position_label.text(), "1 of 1")
            self.assertIsNotNone(dialog.image_label.pixmap())
            self.assertFalse(dialog.image_label.pixmap().isNull())

    def test_preview_fallback_to_thumbnail_when_original_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            missing_path = root / "missing.jpg"
            photo = self._make_photo(missing_path, with_file=False)
            thumb = QPixmap(120, 120)
            thumb.fill(Qt.GlobalColor.blue)
            photo.thumbnail = thumb

            dialog = ImagePreviewDialog()
            dialog.set_items([photo], start_index=0)
            dialog.show()
            self._flush_ui(wait_ms=60)

            self.assertIsNotNone(dialog.image_label.pixmap())
            self.assertFalse(dialog.image_label.pixmap().isNull())
            self.assertEqual(dialog.current_filename(), "missing.jpg")

    def test_next_previous_navigation_and_position(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = self._make_photo(root / "first.jpg", with_file=True)
            second = self._make_photo(root / "second.jpg", with_file=True)

            dialog = ImagePreviewDialog()
            dialog.set_items([first, second], start_index=0)
            dialog.show()
            self._flush_ui(wait_ms=60)

            self.assertEqual(dialog.current_filename(), "first.jpg")
            self.assertEqual(dialog.position_label.text(), "1 of 2")

            dialog.show_next()
            self._flush_ui(wait_ms=40)
            self.assertEqual(dialog.current_filename(), "second.jpg")
            self.assertEqual(dialog.position_label.text(), "2 of 2")

            dialog.show_previous()
            self._flush_ui(wait_ms=40)
            self.assertEqual(dialog.current_filename(), "first.jpg")
            self.assertEqual(dialog.position_label.text(), "1 of 2")

    def test_escape_closes_dialog(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo = self._make_photo(root / "esc.jpg", with_file=True)

            dialog = ImagePreviewDialog()
            dialog.set_items([photo], start_index=0)
            dialog.show()
            self._flush_ui(wait_ms=40)
            self.assertTrue(dialog.isVisible())

            QTest.keyClick(dialog, Qt.Key.Key_Escape)
            self._flush_ui(wait_ms=40)
            self.assertFalse(dialog.isVisible())


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from core.metadata_extractor import extract_basic_metadata
from core.photo_scanner import find_photos
from models.photo import Photo
from ui.photo_grid_widget import PhotoGridWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class PhotoMetadataTests(unittest.TestCase):
    def test_photo_from_path_populates_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.jpg"
            path.write_bytes(b"fake jpg")

            photo = Photo.from_path(path)

            self.assertEqual(photo.path, path)
            self.assertEqual(photo.filename, "sample.jpg")
            self.assertEqual(photo.extension, ".jpg")
            self.assertEqual(photo.file_size, path.stat().st_size)
            self.assertIsNotNone(photo.modified_at)
            self.assertEqual(photo.status, "pending")

    def test_photo_scanner_returns_photo_objects_with_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            nested = root / "nested"
            nested.mkdir()
            photo_path = nested / "family.png"
            photo_path.write_bytes(b"fake png")

            photos = find_photos(str(root))

            self.assertEqual(len(photos), 1)
            self.assertEqual(photos[0].path, photo_path)
            self.assertEqual(photos[0].filename, "family.png")
            self.assertEqual(photos[0].extension, ".png")
            self.assertEqual(photos[0].file_size, photo_path.stat().st_size)

    def test_extract_basic_metadata_from_sample_image(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.jpg"
            image = Image.new("RGB", (120, 80), color="red")
            exif = Image.Exif()
            exif[36867] = "2024:01:02 03:04:05"
            exif[271] = "Canon"
            exif[272] = "EOS 80D"
            exif[274] = 6
            image.save(path, exif=exif)

            metadata = extract_basic_metadata(path)

            self.assertEqual(metadata["width"], 120)
            self.assertEqual(metadata["height"], 80)
            self.assertEqual(metadata["date_taken"], "2024:01:02 03:04:05")
            self.assertEqual(metadata["camera_make"], "Canon")
            self.assertEqual(metadata["camera_model"], "EOS 80D")
            self.assertEqual(metadata["orientation"], 6)
            self.assertFalse(metadata["has_gps"])

    def test_photo_grid_applies_pending_thumbnail_using_path_key(self):
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "card.jpg"
            path.write_bytes(b"fake jpg")

            photo = Photo.from_path(path)
            grid = PhotoGridWidget()
            pixmap = QPixmap(20, 20)
            pixmap.fill(Qt.GlobalColor.red)

            grid.update_thumbnail(photo, pixmap)
            self.assertIn(grid._photo_key(photo), grid._pending_thumbnail_updates)

            grid.set_photos([photo])
            app.processEvents()

            self.assertEqual(len(grid._cards), 1)
            self.assertFalse(grid._cards[0].thumbnail_label.pixmap().isNull())

    def test_photo_grid_applies_qimage_thumbnail_immediately(self):
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "card_qimage.jpg"
            path.write_bytes(b"fake jpg")

            photo = Photo.from_path(path)
            grid = PhotoGridWidget()
            grid.set_photos([photo])
            app.processEvents()

            image = QImage(20, 20, QImage.Format.Format_RGB32)
            image.fill(Qt.GlobalColor.red)

            grid.update_thumbnail(photo, image)
            app.processEvents()

            self.assertEqual(len(grid._cards), 1)
            self.assertFalse(grid._cards[0].thumbnail_label.pixmap().isNull())

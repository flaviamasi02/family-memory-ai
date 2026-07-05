import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from core.image_display_loader import load_display_pixmap, load_display_thumbnail, load_display_thumbnail_image


class ImageLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _make_oriented_jpeg(self, path: Path, orientation: int, with_exif: bool = True) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not available")

        image = Image.new("RGB", (120, 80), color=(20, 20, 20))

        for x in range(0, 60):
            for y in range(0, 40):
                image.putpixel((x, y), (255, 0, 0))
        for x in range(60, 120):
            for y in range(0, 40):
                image.putpixel((x, y), (0, 255, 0))
        for x in range(0, 60):
            for y in range(40, 80):
                image.putpixel((x, y), (0, 0, 255))
        for x in range(60, 120):
            for y in range(40, 80):
                image.putpixel((x, y), (255, 255, 0))

        if with_exif:
            exif = Image.Exif()
            exif[274] = int(orientation)
            image.save(path, format="JPEG", exif=exif)
        else:
            image.save(path, format="JPEG")

    def _pixel_rgb(self, pixmap, x: int, y: int) -> tuple[int, int, int]:
        qimage = pixmap.toImage()
        color = qimage.pixelColor(x, y)
        return color.red(), color.green(), color.blue()

    def test_orientation_6_rotates_image_to_portrait(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rot6.jpg"
            self._make_oriented_jpeg(path, orientation=6)

            pixmap = load_display_pixmap(path)

            self.assertIsNotNone(pixmap)
            self.assertFalse(pixmap.isNull())
            self.assertLess(pixmap.width(), pixmap.height())

            r, g, b = self._pixel_rgb(pixmap, 10, 10)
            self.assertGreater(b, r)
            self.assertGreater(b, g)

    def test_orientation_3_rotates_image_180(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rot3.jpg"
            self._make_oriented_jpeg(path, orientation=3)

            pixmap = load_display_pixmap(path)

            self.assertIsNotNone(pixmap)
            self.assertFalse(pixmap.isNull())
            self.assertEqual(pixmap.width(), 120)
            self.assertEqual(pixmap.height(), 80)

            r, g, b = self._pixel_rgb(pixmap, 10, 10)
            self.assertGreater(r, 120)
            self.assertGreater(g, 120)
            self.assertLess(b, 100)

    def test_orientation_8_rotates_image_to_portrait(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rot8.jpg"
            self._make_oriented_jpeg(path, orientation=8)

            pixmap = load_display_pixmap(path)

            self.assertIsNotNone(pixmap)
            self.assertFalse(pixmap.isNull())
            self.assertLess(pixmap.width(), pixmap.height())

            r, g, b = self._pixel_rgb(pixmap, 10, 10)
            self.assertGreater(g, r)
            self.assertGreater(g, b)

    def test_missing_exif_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "no_exif.jpg"
            self._make_oriented_jpeg(path, orientation=1, with_exif=False)

            full = load_display_pixmap(path)
            thumb = load_display_thumbnail(path, QSize(64, 64))

            self.assertIsNotNone(full)
            self.assertFalse(full.isNull())
            self.assertIsNotNone(thumb)
            self.assertFalse(thumb.isNull())

    def test_corrupt_image_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "corrupt.jpg"
            path.write_bytes(b"not-a-valid-image")

            full = load_display_pixmap(path)
            thumb = load_display_thumbnail(path, QSize(64, 64))

            self.assertIsNone(full)
            self.assertIsNone(thumb)

    def test_thumbnail_loader_matches_preview_orientation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rot6_thumb.jpg"
            self._make_oriented_jpeg(path, orientation=6)

            full = load_display_pixmap(path)
            thumb = load_display_thumbnail(path, QSize(64, 64))

            self.assertIsNotNone(full)
            self.assertIsNotNone(thumb)
            self.assertLess(full.width(), full.height())
            self.assertLess(thumb.width(), thumb.height())

            full_r, full_g, full_b = self._pixel_rgb(full, 10, 10)
            thumb_r, thumb_g, thumb_b = self._pixel_rgb(thumb, 5, 5)
            self.assertGreater(full_b, max(full_r, full_g))
            self.assertGreater(thumb_b, max(thumb_r, thumb_g))

    def test_thumbnail_image_loader_returns_qimage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "thumb_image.jpg"
            self._make_oriented_jpeg(path, orientation=1)

            image = load_display_thumbnail_image(path, QSize(64, 64))

            self.assertIsNotNone(image)
            self.assertIsInstance(image, QImage)
            self.assertFalse(image.isNull())


if __name__ == "__main__":
    unittest.main()

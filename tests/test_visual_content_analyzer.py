import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QColor, QImage, QPainter

from core.visual_content_analyzer import VisualContentAnalyzer


class VisualContentAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = VisualContentAnalyzer(max_dimension=512)

    def _save_photo_like(self, path: Path) -> None:
        image = QImage(320, 220, QImage.Format.Format_RGB32)
        for y in range(image.height()):
            for x in range(image.width()):
                r = (x * 7 + y * 3) % 256
                g = (x * 5 + y * 11) % 256
                b = (x * 13 + y * 9) % 256
                image.setPixelColor(x, y, QColor(r, g, b))
        self.assertTrue(image.save(str(path), "PNG"))

    def _save_document_like(self, path: Path) -> None:
        image = QImage(850, 1200, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.setPen(QColor("black"))
        painter.setBrush(QColor("black"))
        y = 120
        for _ in range(18):
            painter.drawRect(110, y, 620, 18)
            y += 42
        painter.end()
        self.assertTrue(image.save(str(path), "PNG"))

    def _save_graphic_like(self, path: Path) -> None:
        image = QImage(280, 280, QImage.Format.Format_RGB32)
        image.fill(QColor("#ffea00"))
        painter = QPainter(image)
        painter.setBrush(QColor("#2d2d2d"))
        painter.setPen(QColor("#2d2d2d"))
        painter.drawRect(40, 40, 200, 80)
        painter.drawRect(40, 150, 200, 90)
        painter.end()
        self.assertTrue(image.save(str(path), "PNG"))

    def _save_tall_screenshot_like(self, path: Path) -> None:
        image = QImage(420, 980, QImage.Format.Format_RGB32)
        image.fill(QColor("#f2f2f2"))
        painter = QPainter(image)
        painter.setBrush(QColor("#d9d9d9"))
        painter.setPen(QColor("#d9d9d9"))
        y = 40
        for _ in range(14):
            painter.drawRect(24, y, 372, 48)
            y += 62
        painter.setPen(QColor("#555555"))
        for x in range(24, 396, 24):
            painter.drawLine(x, 0, x, 979)
        painter.end()
        self.assertTrue(image.save(str(path), "PNG"))

    def _save_wide_ad_like(self, path: Path) -> None:
        image = QImage(1400, 300, QImage.Format.Format_RGB32)
        image.fill(QColor("#ffefd5"))
        painter = QPainter(image)
        painter.setBrush(QColor("#ff4500"))
        painter.setPen(QColor("#ff4500"))
        painter.drawRect(40, 40, 1320, 90)
        painter.setBrush(QColor("#222222"))
        painter.setPen(QColor("#222222"))
        painter.drawRect(60, 170, 1240, 70)
        painter.end()
        self.assertTrue(image.save(str(path), "PNG"))

    def test_photo_like_image_has_higher_photo_likelihood(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "photo_like.png"
            self._save_photo_like(path)
            signals = self.analyzer.analyze(str(path))

            self.assertGreater(signals.photo_likelihood, 0.5)
            self.assertGreater(signals.photo_likelihood, signals.graphic_likelihood)

    def test_document_like_image_has_document_likelihood(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "document_scan.png"
            self._save_document_like(path)
            signals = self.analyzer.analyze(str(path))

            self.assertGreater(signals.document_likelihood, 0.55)
            self.assertGreater(signals.document_likelihood, signals.photo_likelihood)

    def test_graphic_like_image_has_graphic_likelihood(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "meme_square.png"
            self._save_graphic_like(path)
            signals = self.analyzer.analyze(str(path))

            self.assertGreater(signals.graphic_likelihood, 0.55)
            self.assertGreater(signals.graphic_likelihood, signals.photo_likelihood)

    def test_tall_image_has_screenshot_likelihood(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "screenshot_like.png"
            self._save_tall_screenshot_like(path)
            signals = self.analyzer.analyze(str(path))

            self.assertGreater(signals.screenshot_likelihood, 0.55)
            self.assertEqual(signals.dominant_layout, "tall_mobile")

    def test_wide_image_has_advertisement_likelihood(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "promo_banner.png"
            self._save_wide_ad_like(path)
            signals = self.analyzer.analyze(str(path))

            self.assertGreater(signals.advertisement_likelihood, 0.55)
            self.assertEqual(signals.dominant_layout, "wide_banner")

    def test_corrupt_image_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "broken.png"
            path.write_bytes(b"not-an-image")
            signals = self.analyzer.analyze(str(path))

            self.assertIsNone(signals.width)
            self.assertEqual(signals.photo_likelihood, 0.0)
            self.assertTrue(signals.explanation)


if __name__ == "__main__":
    unittest.main()

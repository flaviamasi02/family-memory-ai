import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from core.image_display_loader import _decode_failed_paths, is_decode_failed
from core.metadata_extractor import extract_basic_metadata
from core.photo_scanner import find_photos
from models.photo import Photo
from ui.photo_grid_widget import PhotoGridWidget
from workers.thumbnail_worker import ThumbnailWorker
from cache.thumbnail_cache import get_thumbnail_cache_path

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

    def test_photo_grid_batches_initial_render_for_large_collections(self):
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            photos = []
            for index in range(90):
                path = Path(tmpdir) / f"card_{index}.jpg"
                path.write_bytes(b"fake jpg")
                photos.append(Photo.from_path(path))

            grid = PhotoGridWidget()
            grid.set_photos(photos)
            for _ in range(10):
                app.processEvents()

            self.assertEqual(grid.rendered_card_count(), grid._initial_render_count)
            self.assertLess(grid.rendered_card_count(), len(photos))

    def test_thumbnail_worker_reuses_existing_cache_before_generating(self):
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                source_path = Path(tmpdir) / "cached.jpg"
                source_image = QImage(32, 32, QImage.Format.Format_RGB32)
                source_image.fill(Qt.GlobalColor.blue)
                self.assertTrue(source_image.save(str(source_path), "JPG"))
                photo = Photo.from_path(source_path)

                cache_path = get_thumbnail_cache_path(str(source_path))
                cached_image = QImage(16, 16, QImage.Format.Format_RGB32)
                cached_image.fill(Qt.GlobalColor.red)
                self.assertTrue(cached_image.save(str(cache_path), "JPG"))

                worker = ThumbnailWorker([photo], delay_ms=0)
                emitted = []
                worker.thumbnail_ready.connect(lambda ready_photo, image: emitted.append((ready_photo, image)))

                with patch.object(worker, "_load_thumbnail_image", side_effect=AssertionError("regenerated cached thumbnail")):
                    worker.run()
                app.processEvents()

                self.assertEqual(photo.status, "thumbnail_ready")
                self.assertEqual(photo.thumbnail_path, str(cache_path))
                self.assertEqual(photo.metadata.get("thumbnail_path"), str(cache_path))
                self.assertEqual(len(emitted), 1)
                self.assertFalse(emitted[0][1].isNull())
            finally:
                os.chdir(old_cwd)

    def test_corrupted_jpeg_is_skipped_after_first_failure(self):
        """Worker marks corrupted files as error and does not retry them this session."""
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                # Write a file that looks like a JPEG but contains garbage data.
                corrupted_path = Path(tmpdir) / "corrupted.jpg"
                corrupted_path.write_bytes(b"\xff\xd8\xff\xe0garbage invalid jpeg content")
                photo = Photo.from_path(corrupted_path)

                worker = ThumbnailWorker([photo], delay_ms=0)
                status_updates = []
                worker.thumbnail_status_updated.connect(lambda p: status_updates.append(p.status))

                worker.run()
                app.processEvents()

                self.assertEqual(photo.status, "error")
                # The path must now be recorded so subsequent workers skip it immediately.
                self.assertTrue(is_decode_failed(str(corrupted_path)))
            finally:
                os.chdir(old_cwd)

    def test_worker_skips_known_failed_path_without_decoding(self):
        """Worker skips decode for paths already in the failed-path set."""
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                source_path = Path(tmpdir) / "skip_me.jpg"
                source_path.write_bytes(b"\xff\xd8\xff garbage")
                photo = Photo.from_path(source_path)

                # Pre-populate the failed set so the worker should skip immediately.
                _decode_failed_paths.add(str(source_path))
                try:
                    worker = ThumbnailWorker([photo], delay_ms=0)
                    emitted = []
                    worker.thumbnail_ready.connect(lambda p, img: emitted.append(p))

                    with patch.object(worker, "_load_thumbnail_image", side_effect=AssertionError("should not decode")):
                        worker.run()
                    app.processEvents()

                    self.assertEqual(photo.status, "error")
                    self.assertEqual(len(emitted), 0)
                finally:
                    _decode_failed_paths.discard(str(source_path))
            finally:
                os.chdir(old_cwd)

    def test_photo_card_widget_shows_placeholder_before_thumbnail(self):
        """PhotoCardWidget shows a non-null placeholder pixmap before any thumbnail is set."""
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "placeholder_test.jpg"
            path.write_bytes(b"fake jpg")
            photo = Photo.from_path(path)

            from ui.photo_card_widget import PhotoCardWidget
            card = PhotoCardWidget(photo)

            # Before any thumbnail is loaded the label should already show the
            # grey placeholder pixmap (not an empty / null pixmap).
            self.assertFalse(card.thumbnail_label.pixmap().isNull())

    def test_photo_grid_dynamic_columns_adapt_to_width(self):
        """PhotoGridWidget adjusts column count based on viewport width."""
        app = QApplication.instance() or QApplication([])

        grid = PhotoGridWidget()
        # Force the viewport to a known width so we can verify column calculation.
        grid.scroll_area.viewport().resize(600, 400)
        expected_columns = max(1, 600 // 192)
        self.assertEqual(grid._calculate_grid_columns(), expected_columns)

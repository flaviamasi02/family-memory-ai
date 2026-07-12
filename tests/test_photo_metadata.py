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
from core.perf_stats import PerfStats, get_session_stats, reset_session_stats
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
                # Use the same corrupted-JPEG byte pattern as the other test.
                source_path = Path(tmpdir) / "skip_me.jpg"
                source_path.write_bytes(b"\xff\xd8\xff\xe0garbage invalid jpeg content")
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


class PerfStatsTests(unittest.TestCase):
    def setUp(self):
        self._stats = PerfStats()

    def test_record_and_summary_contains_label(self):
        self._stats.record("test_phase", 123.4)
        summary = self._stats.summary()
        self.assertIn("test_phase", summary)
        self.assertIn("123", summary)

    def test_start_stop_records_elapsed(self):
        self._stats.start("my_phase")
        elapsed = self._stats.stop("my_phase")
        self.assertGreaterEqual(elapsed, 0)
        summary = self._stats.summary()
        self.assertIn("my_phase", summary)

    def test_inc_and_get_counter(self):
        self._stats.inc("cache_hits", 5)
        self._stats.inc("cache_hits", 3)
        self.assertEqual(self._stats.get_counter("cache_hits"), 8)

    def test_identify_bottleneck_returns_slowest(self):
        self._stats.record("fast_phase", 10.0)
        self._stats.record("slow_phase", 500.0)
        self._stats.record("medium_phase", 50.0)
        self.assertEqual(self._stats.identify_bottleneck(), "slow_phase")

    def test_reset_clears_all_data(self):
        self._stats.record("phase", 99.9)
        self._stats.inc("count", 7)
        self._stats.reset()
        self.assertNotIn("phase", self._stats.summary())
        self.assertEqual(self._stats.get_counter("count"), 0)

    def test_bottleneck_marked_in_summary(self):
        self._stats.record("phase_a", 50.0)
        self._stats.record("phase_b", 200.0)
        summary = self._stats.summary()
        self.assertIn("BOTTLENECK", summary)
        # The bottleneck label should appear near the marker.
        self.assertIn("phase_b", summary)

    def test_session_stats_singleton_reset(self):
        reset_session_stats()
        stats = get_session_stats()
        stats.record("singleton_test", 42.0)
        summary = stats.summary()
        self.assertIn("singleton_test", summary)
        reset_session_stats()
        summary_after = get_session_stats().summary()
        self.assertNotIn("singleton_test", summary_after)


class PhotoScannerPerfInstrumentationTests(unittest.TestCase):
    def test_find_photos_records_scan_and_metadata_timings(self):
        """find_photos() must record folder_scan and metadata_extraction into session stats."""
        reset_session_stats()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.jpg"
            path.write_bytes(b"fake jpg data")
            find_photos(tmpdir)

        stats = get_session_stats()
        summary = stats.summary()
        self.assertIn("folder_scan", summary)
        self.assertIn("metadata_extraction", summary)
        self.assertGreater(stats.get_counter("files_scanned"), 0)


class ThumbnailWorkerPerfInstrumentationTests(unittest.TestCase):
    def test_worker_records_cache_hits_in_session_stats(self):
        """ThumbnailWorker increments thumbnail_cache_hits for cached thumbnails."""
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                reset_session_stats()
                source_path = Path(tmpdir) / "img.jpg"
                img = QImage(16, 16, QImage.Format.Format_RGB32)
                img.fill(Qt.GlobalColor.blue)
                img.save(str(source_path), "JPG")
                photo = Photo.from_path(source_path)

                cache_path = get_thumbnail_cache_path(str(source_path))
                cached = QImage(8, 8, QImage.Format.Format_RGB32)
                cached.fill(Qt.GlobalColor.red)
                cached.save(str(cache_path), "JPG")

                worker = ThumbnailWorker([photo], delay_ms=0)
                with patch.object(worker, "_load_thumbnail_image",
                                  side_effect=AssertionError("should not generate")):
                    worker.run()

                stats = get_session_stats()
                self.assertEqual(stats.get_counter("thumbnail_cache_hits"), 1)
                self.assertEqual(stats.get_counter("thumbnail_cache_misses"), 0)
            finally:
                os.chdir(old_cwd)

    def test_worker_records_cache_miss_and_generation_stats(self):
        """ThumbnailWorker increments thumbnails_generated for new thumbnails."""
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                reset_session_stats()
                source_path = Path(tmpdir) / "gen.jpg"
                img = QImage(32, 32, QImage.Format.Format_RGB32)
                img.fill(Qt.GlobalColor.green)
                img.save(str(source_path), "JPG")
                photo = Photo.from_path(source_path)

                worker = ThumbnailWorker([photo], delay_ms=0)
                worker.run()

                stats = get_session_stats()
                self.assertEqual(stats.get_counter("thumbnail_cache_misses"), 1)
                self.assertEqual(stats.get_counter("thumbnails_generated"), 1)
                self.assertEqual(stats.get_counter("thumbnail_cache_hits"), 0)
            finally:
                os.chdir(old_cwd)


class GridInitialRenderPerfTests(unittest.TestCase):
    def test_grid_records_initial_render_stats(self):
        """PhotoGridWidget must record grid_initial_render timing and card count."""
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            reset_session_stats()
            photos = []
            for i in range(10):
                p = Path(tmpdir) / f"img_{i}.jpg"
                p.write_bytes(b"fake")
                photos.append(Photo.from_path(p))

            grid = PhotoGridWidget()
            grid.set_photos(photos)
            for _ in range(20):
                app.processEvents()

            stats = get_session_stats()
            summary = stats.summary()
            self.assertIn("grid_initial_render", summary)
            self.assertGreater(stats.get_counter("grid_initial_cards_created"), 0)


class StagedLoadRegressionTests(unittest.TestCase):
    """Regression tests for the staged on_scan_complete fix (PERF-004).

    These tests verify that the Photo Browser is usable immediately after scan
    completion and that Cleanup Review / Memory Review setup is deferred so that
    the UI thread is not blocked before the first thumbnails appear.
    """

    def test_cleanup_review_set_photos_does_not_decode_original_files(self):
        """IrrelevantMediaPage.set_photos() must not call load_display_thumbnail
        on the original image paths — only on pre-existing cached thumbnail paths.

        Decoding originals on the UI thread for every photo in a large library
        was the root cause of the 'Not Responding' freeze and repeated JPEG
        warnings reported in PR #9.
        """
        from unittest.mock import patch, MagicMock
        from ui.irrelevant_media_page import IrrelevantMediaPage

        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake photo objects — no real image content needed.
            photos = []
            original_paths = set()
            for i in range(5):
                path = Path(tmpdir) / f"orig_{i}.jpg"
                path.write_bytes(b"\xff\xd8\xff fake jpeg content")
                photo = Photo.from_path(path)
                photos.append(photo)
                original_paths.add(str(path))

            decoded_paths: list[str] = []

            import core.image_display_loader as idl

            original_fn = idl.load_display_thumbnail

            def spy_load(file_path, target_size):
                decoded_paths.append(str(file_path))
                return original_fn(file_path, target_size)

            page = IrrelevantMediaPage()
            with patch.object(idl, "load_display_thumbnail", side_effect=spy_load):
                page.set_photos(photos, tmpdir, total_imported_count=len(photos))
                for _ in range(10):
                    app.processEvents()

            # No original file path should have been decoded during set_photos.
            decoded_originals = [p for p in decoded_paths if p in original_paths]
            self.assertEqual(
                decoded_originals,
                [],
                msg=(
                    "set_photos() decoded original image files on the UI thread: "
                    + ", ".join(decoded_originals)
                ),
            )

    def test_cleanup_review_thumbnail_uses_cached_path_over_original(self):
        """_thumbnail_for_photo must prefer an existing cached thumbnail over the
        original file path, and must not decode the original when allow_original_decode
        is False (the default used during grid population).
        """
        from unittest.mock import MagicMock
        from ui.irrelevant_media_page import IrrelevantMediaPage, CleanupReviewRow

        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            # Build a minimal photo with a valid cached thumbnail.
            path = Path(tmpdir) / "photo.jpg"
            path.write_bytes(b"\xff\xd8\xff fake")
            thumb_path = Path(tmpdir) / "thumb.jpg"

            # Write a tiny but valid JPEG thumbnail using QImage.
            from PySide6.QtGui import QImage
            img = QImage(8, 8, QImage.Format.Format_RGB32)
            img.fill(Qt.GlobalColor.green)
            img.save(str(thumb_path), "JPG")

            photo = Photo.from_path(path)
            photo.thumbnail_path = str(thumb_path)

            page = IrrelevantMediaPage()
            # allow_original_decode=False: must return the cached thumb, not None.
            pixmap = page._thumbnail_for_photo(photo, (140, 140), allow_original_decode=False)

            self.assertIsNotNone(pixmap, "Expected cached thumbnail to be returned")
            self.assertFalse(pixmap.isNull(), "Returned pixmap must not be null")

    def test_cleanup_review_thumbnail_returns_none_without_cache_and_no_decode(self):
        """When no thumbnail is cached and allow_original_decode is False,
        _thumbnail_for_photo must return None rather than decoding the original.
        """
        from ui.irrelevant_media_page import IrrelevantMediaPage

        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nocache.jpg"
            path.write_bytes(b"\xff\xd8\xff fake")
            photo = Photo.from_path(path)
            # No thumbnail_path set — only original file available.

            page = IrrelevantMediaPage()
            pixmap = page._thumbnail_for_photo(photo, (140, 140), allow_original_decode=False)

            self.assertIsNone(
                pixmap,
                "Expected None when no cache exists and original decode is not allowed",
            )

    def test_on_scan_complete_thumbnail_worker_starts_before_secondary_views(self):
        """After _on_scan_complete the thumbnail worker must be running before
        Cleanup Review and Memory Review are fully populated.

        We verify this by patching start_thumbnail_loading and the secondary
        setup methods, then confirming call order: thumbnail loading starts
        first, secondary setup is deferred (called after processEvents).
        """
        from unittest.mock import MagicMock, call, patch
        from ui.main_window import MainWindow

        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmpdir:
            photos = []
            for i in range(3):
                p = Path(tmpdir) / f"t_{i}.jpg"
                p.write_bytes(b"fake")
                photos.append(Photo.from_path(p))

            window = MainWindow()
            call_log: list[str] = []

            original_start = window.start_thumbnail_loading
            original_cleanup = window._load_irrelevant_media_data
            original_review = window._load_album_review_data

            def fake_start(ph):
                call_log.append("thumbnails_started")

            def fake_cleanup(ph):
                call_log.append("cleanup_setup")

            def fake_review(*_args, **_kwargs):
                call_log.append("memory_review_setup")

            window.start_thumbnail_loading = fake_start
            window._load_irrelevant_media_data = fake_cleanup
            window._load_album_review_data = fake_review

            # Simulate scan completion.
            window._on_scan_complete(photos)

            # At this point only the browser + thumbnails should be done; the
            # deferred secondary views have not fired yet.
            self.assertIn("thumbnails_started", call_log)
            self.assertNotIn("cleanup_setup", call_log)
            self.assertNotIn("memory_review_setup", call_log)

            # Process the deferred QTimer callbacks.
            for _ in range(20):
                app.processEvents()

            self.assertIn("cleanup_setup", call_log)
            self.assertIn("memory_review_setup", call_log)

            # Verify ordering: thumbnails must start before secondary setup.
            thumb_idx = call_log.index("thumbnails_started")
            cleanup_idx = call_log.index("cleanup_setup")
            self.assertLess(thumb_idx, cleanup_idx)

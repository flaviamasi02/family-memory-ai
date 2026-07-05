import tempfile
import unittest
from pathlib import Path

from album.album_builder import AlbumBuilder
from models.photo import Photo


class AlbumBuilderTests(unittest.TestCase):
    def _make_photo(self, root: Path, name: str, date_taken: str | None) -> Photo:
        path = root / name
        path.write_bytes(b"image")
        photo = Photo.from_path(path)
        if date_taken is not None:
            photo.metadata["date_taken"] = date_taken
        return photo

    def test_group_photos_by_year_uses_date_taken(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            p2024_a = self._make_photo(root, "a.jpg", "2024:01:05 10:00:00")
            p2024_b = self._make_photo(root, "b.jpg", "2024:12:31 23:59:59")
            p2023 = self._make_photo(root, "c.jpg", "2023:06:01 12:00:00")
            p_unknown = self._make_photo(root, "d.jpg", None)

            builder = AlbumBuilder()
            grouped = builder.group_photos_by_year([p2024_a, p2024_b, p2023, p_unknown])

            self.assertEqual(set(grouped.keys()), {2023, 2024})
            self.assertEqual(grouped[2024], [p2024_a, p2024_b])
            self.assertEqual(grouped[2023], [p2023])

    def test_create_annual_album_initializes_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            p2024 = self._make_photo(root, "a.jpg", "2024:01:05 10:00:00")
            p2023 = self._make_photo(root, "b.jpg", "2023:01:05 10:00:00")

            builder = AlbumBuilder()
            album = builder.create_annual_album([p2024, p2023], year=2024)

            self.assertEqual(album.year, 2024)
            self.assertEqual(album.photos, [p2024])
            self.assertEqual(album.candidate_photos, [p2024])
            self.assertEqual(album.selected_photos, [])
            self.assertEqual(album.rejected_photos, [])
            self.assertEqual(album.status, "candidate_selection")


if __name__ == "__main__":
    unittest.main()

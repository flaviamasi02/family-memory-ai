import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from album.album_draft_builder import AlbumDraftBuilder
from album.album_scoring_engine import AlbumScoreBreakdown
from models.photo import Photo


class AlbumDraftBuilderTests(unittest.TestCase):
    def _make_breakdown(
        self,
        root: Path,
        filename: str,
        score: float,
        date_taken: str | None = "2021:01:10 10:00:00",
    ) -> AlbumScoreBreakdown:
        path = root / filename
        path.write_bytes(b"image")
        photo = Photo.from_path(path)

        if date_taken is not None:
            photo.metadata["date_taken"] = date_taken
            photo.sync_intelligence_from_metadata()

        return AlbumScoreBreakdown(
            photo=photo,
            total_score=score,
            technical_score=score,
            memory_score=score,
            date_score=score,
            explanation=["score"],
        )

    def test_approved_photos_are_included(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            approved = self._make_breakdown(root, "approved.jpg", 80)
            pending = self._make_breakdown(root, "pending.jpg", 99)

            result = AlbumDraftBuilder().build(
                year=2021,
                scored_photos=[approved, pending],
                review_status_by_path={
                    str(approved.photo.path): "approved",
                    str(pending.photo.path): "pending",
                },
            )

            included_names = [photo.filename for page in result.draft.pages for photo in page.photos]
            self.assertEqual(included_names, ["approved.jpg"])

    def test_rejected_photos_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            rejected = self._make_breakdown(root, "rejected.jpg", 95)

            result = AlbumDraftBuilder().build(
                year=2021,
                scored_photos=[rejected],
                review_status_by_path={str(rejected.photo.path): "rejected"},
            )

            self.assertEqual(result.included_photo_count, 0)
            self.assertEqual(result.exclusion_reasons.get("rejected_by_user"), 1)

    def test_pending_photos_used_when_no_approved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            high = self._make_breakdown(root, "high.jpg", 99)
            low = self._make_breakdown(root, "low.jpg", 40)

            result = AlbumDraftBuilder().build(
                year=2021,
                scored_photos=[low, high],
                review_status_by_path={
                    str(high.photo.path): "pending",
                    str(low.photo.path): "pending",
                },
            )

            included_names = [photo.filename for page in result.draft.pages for photo in page.photos]
            self.assertEqual(set(included_names), {"high.jpg", "low.jpg"})
            self.assertTrue(any("No approved photos" in line for line in result.draft.explanation))

    def test_draft_is_limited_to_120_photos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scored = []
            status = {}
            for index in range(150):
                item = self._make_breakdown(root, f"p_{index:03}.jpg", float(150 - index))
                scored.append(item)
                status[str(item.photo.path)] = "pending"

            result = AlbumDraftBuilder().build(2021, scored, status)

            self.assertEqual(result.included_photo_count, 120)
            self.assertEqual(result.excluded_photo_count, 30)
            self.assertEqual(result.exclusion_reasons.get("below_selection_cutoff"), 30)

    def test_photos_grouped_by_month(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            jan = self._make_breakdown(root, "jan.jpg", 70, "2021:01:05 10:00:00")
            feb = self._make_breakdown(root, "feb.jpg", 70, "2021:02:07 10:00:00")

            result = AlbumDraftBuilder().build(2021, [jan, feb], {
                str(jan.photo.path): "approved",
                str(feb.photo.path): "approved",
            })

            titles = [page.title for page in result.draft.pages]
            self.assertIn("January 2021", titles)
            self.assertIn("February 2021", titles)
            self.assertTrue(all(page.page_type == "month" for page in result.draft.pages))

    def test_undated_photos_go_to_undated_memories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            undated = self._make_breakdown(root, "undated.jpg", 80, None)
            undated.photo.metadata = {}
            undated.photo.sync_intelligence_from_metadata()
            undated.photo.intelligence.date_taken = None
            undated.photo.intelligence.year = None
            undated.photo.intelligence.month = None
            undated.photo.intelligence.day = None

            result = AlbumDraftBuilder().build(
                2021,
                [undated],
                {str(undated.photo.path): "approved"},
            )

            self.assertEqual(result.draft.pages[0].title, "Undated Memories")
            self.assertEqual(result.draft.pages[0].page_type, "undated")

    def test_result_counts_are_correct(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            included = self._make_breakdown(root, "included.jpg", 80)
            rejected = self._make_breakdown(root, "rejected.jpg", 50)
            missing_path = self._make_breakdown(root, "missing_path.jpg", 60)
            missing_path.photo.path = None
            missing_photo = AlbumScoreBreakdown(
                photo=None,
                total_score=0,
                technical_score=0,
                memory_score=0,
                date_score=0,
                explanation=[],
            )

            result = AlbumDraftBuilder().build(
                2021,
                [included, rejected, missing_path, missing_photo],
                {
                    str(included.photo.path): "approved",
                    str(rejected.photo.path): "rejected",
                },
            )

            self.assertEqual(result.source_photo_count, 4)
            self.assertEqual(result.included_photo_count, 1)
            self.assertEqual(result.excluded_photo_count, 3)
            self.assertEqual(result.exclusion_reasons.get("rejected_by_user"), 1)
            self.assertEqual(result.exclusion_reasons.get("missing_file_path"), 1)
            self.assertEqual(result.exclusion_reasons.get("missing_photo"), 1)

    def test_explanations_are_produced(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            a = self._make_breakdown(root, "a.jpg", 80)

            result = AlbumDraftBuilder().build(2021, [a], {str(a.photo.path): "approved"})

            self.assertTrue(result.draft.explanation)
            self.assertTrue(any("Approved photos" in line for line in result.draft.explanation))
            self.assertTrue(any("Rejected photos" in line for line in result.draft.explanation))
            self.assertTrue(any("grouped by month" in line for line in result.draft.explanation))
            self.assertTrue(any("120 photos" in line for line in result.draft.explanation))

    def test_sorting_by_date_then_score_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            early = self._make_breakdown(root, "early.jpg", 10, "2021:01:01 10:00:00")
            same_day_high = self._make_breakdown(root, "same_day_high.jpg", 90, "2021:01:02 10:00:00")
            same_day_low = self._make_breakdown(root, "same_day_low.jpg", 30, "2021:01:02 10:00:00")

            result = AlbumDraftBuilder().build(
                2021,
                [same_day_low, same_day_high, early],
                {
                    str(early.photo.path): "approved",
                    str(same_day_high.photo.path): "approved",
                    str(same_day_low.photo.path): "approved",
                },
            )

            ordered = [photo.filename for page in result.draft.pages for photo in page.photos]
            self.assertEqual(ordered, ["early.jpg", "same_day_high.jpg", "same_day_low.jpg"])


if __name__ == "__main__":
    unittest.main()

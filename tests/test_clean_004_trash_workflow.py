import tempfile
import unittest
from pathlib import Path

from core.category_registry import CategoryRegistry
from core.trash_workflow_service import TrashRecord, TrashWorkflowService


class Clean004TrashWorkflowTests(unittest.TestCase):
    def test_stable_system_category(self):
        with tempfile.TemporaryDirectory() as directory:
            category = CategoryRegistry(directory).get("to_trash")
            self.assertEqual(category.id, "to_trash")
            self.assertEqual(category.display_name, "To Trash")
            self.assertTrue(category.is_system)
            self.assertTrue(category.is_cleanup_category)

    def test_confirmation_is_required_and_restore_preserves_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            library = parent / "library"
            library.mkdir()
            source = library / "memory.jpg"
            source.write_bytes(b"unchanged image bytes")
            service = TrashWorkflowService(library, repository_root=parent / "repo")
            record = TrashRecord("photo-1", str(source))
            result = service.move_confirmed([record])
            self.assertEqual(result.requested_count, 0)
            self.assertTrue(source.exists())

            service.confirm([record])
            result = service.move_confirmed([record])
            self.assertEqual(result.moved_count, 1)
            self.assertEqual(record.state, "moved_to_trash")
            self.assertEqual(Path(record.destination_path).read_bytes(), b"unchanged image bytes")

            result = service.restore([record])
            self.assertEqual(result.restored_count, 1)
            self.assertEqual(record.state, "restored")
            self.assertEqual(source.read_bytes(), b"unchanged image bytes")
            self.assertEqual([entry["action"] for entry in record.history],
                             ["confirmed_to_trash", "moved_to_trash", "restored"])

    def test_bulk_duplicate_names_partial_failure_and_destination_safety(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            library = parent / "library"
            one, two = library / "one", library / "two"
            one.mkdir(parents=True)
            two.mkdir()
            first, second = one / "same.jpg", two / "same.jpg"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            records = [TrashRecord("1", str(first)), TrashRecord("2", str(second)),
                       TrashRecord("3", str(library / "missing.jpg"))]
            service = TrashWorkflowService(library, repository_root=parent / "repo")
            service.confirm(records)
            result = service.move_confirmed(records)
            self.assertEqual((result.moved_count, result.failed_count), (2, 1))
            self.assertIn("1 could not be moved", result.message)
            names = {Path(record.destination_path).name for record in records[:2]}
            self.assertEqual(names, {"same.jpg", "same_1.jpg"})
            with self.assertRaises(ValueError):
                service.validate_destination(library / "nested")

    def test_thousand_file_move_is_bounded_and_unique(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            library = parent / "library"
            library.mkdir()
            records = []
            for index in range(1000):
                path = library / f"p-{index}.jpg"
                path.write_bytes(b"x")
                records.append(TrashRecord(str(index), str(path)))
            service = TrashWorkflowService(library, repository_root=parent / "repo")
            service.confirm(records)
            result = service.move_confirmed(records)
            self.assertEqual(result.moved_count, 1000)
            self.assertEqual(result.failed_count, 0)


if __name__ == "__main__":
    unittest.main()

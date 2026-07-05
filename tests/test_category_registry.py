import json
import os
import tempfile
import unittest

from core.category_registry import get_category_registry, reset_category_registry


class CategoryRegistryTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("FAMILY_MEMORY_CATEGORIES_ROOT", None)
        reset_category_registry()

    def _new_registry(self, root: str):
        os.environ["FAMILY_MEMORY_CATEGORIES_ROOT"] = root
        reset_category_registry()
        return get_category_registry(force_reload=True)

    def test_create_custom_category(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = self._new_registry(tmpdir)
            created = registry.create_user_category(
                "Travel",
                description="Vacation memories.",
                ai_description="Beaches, airports, hotels, cities.",
                color="#3B82F6",
                icon="travel",
                is_album_candidate=True,
                is_cleanup_category=False,
            )

            self.assertEqual(created.id, "travel")
            self.assertEqual(created.display_name, "Travel")
            self.assertEqual(created.type, "user")
            self.assertFalse(created.is_system)
            self.assertEqual(created.ai_description, "Beaches, airports, hotels, cities.")
            self.assertEqual(created.icon, "travel")
            self.assertTrue(created.is_album_candidate)
            self.assertFalse(created.is_cleanup_category)
            self.assertTrue(registry.has_category("travel"))

    def test_rename_custom_category(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = self._new_registry(tmpdir)
            created = registry.create_user_category("Work")
            updated = registry.rename_user_category(created.id, "Work Docs")

            self.assertEqual(updated.display_name, "Work Docs")
            self.assertEqual(registry.get(created.id).display_name, "Work Docs")

    def test_system_category_cannot_be_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = self._new_registry(tmpdir)
            deleted, reason = registry.delete_user_category("family_photo")

            self.assertFalse(deleted)
            self.assertIn("cannot", reason.lower())

    def test_user_category_delete_requires_reassignment_when_used(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = self._new_registry(tmpdir)
            created = registry.create_user_category("School")

            deleted, reason = registry.delete_user_category(created.id, used_count=2, reassign_to="")
            self.assertFalse(deleted)
            self.assertIn("reassign", reason.lower())

            deleted2, reason2 = registry.delete_user_category(created.id, used_count=2, reassign_to="family_photo")
            self.assertTrue(deleted2)
            self.assertEqual(reason2, "")

    def test_categories_persist_to_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = self._new_registry(tmpdir)
            created = registry.create_user_category(
                "Pets",
                ai_description="Dogs, cats, animals at home.",
                icon="pets",
                is_album_candidate=True,
                is_cleanup_category=False,
            )

            storage = registry.storage_path
            self.assertTrue(storage.exists())

            data = json.loads(storage.read_text(encoding="utf-8"))
            entries = data.get("categories", [])
            ids = [item.get("id") for item in entries]
            self.assertIn(created.id, ids)
            pets = next(item for item in entries if item.get("id") == created.id)
            self.assertIn("ai_description", pets)
            self.assertIn("icon", pets)
            self.assertIn("is_system", pets)
            self.assertIn("is_album_candidate", pets)
            self.assertEqual(pets.get("ai_description"), "Dogs, cats, animals at home.")
            self.assertFalse(bool(pets.get("is_cleanup_category", True)))
            self.assertTrue(bool(pets.get("is_album_candidate", False)))

            reset_category_registry()
            loaded = get_category_registry(force_reload=True)
            self.assertTrue(loaded.has_category(created.id))
            loaded_item = loaded.get(created.id)
            self.assertIsNotNone(loaded_item)
            self.assertEqual(loaded_item.ai_description, "Dogs, cats, animals at home.")
            self.assertEqual(loaded_item.icon, "pets")

    def test_cleanup_and_album_flags_drive_helpers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = self._new_registry(tmpdir)
            created = registry.create_user_category(
                "To Print",
                is_album_candidate=True,
                is_cleanup_category=False,
            )

            self.assertTrue(registry.is_album_candidate_category(created.id))
            self.assertFalse(registry.is_cleanup_category(created.id))

            registry.update_user_category_flags(
                created.id,
                is_cleanup_category=True,
                is_album_candidate=False,
            )
            self.assertFalse(registry.is_album_candidate_category(created.id))
            self.assertTrue(registry.is_cleanup_category(created.id))

    def test_duplicate_category_names_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = self._new_registry(tmpdir)
            registry.create_user_category("Nature")

            with self.assertRaises(ValueError):
                registry.create_user_category("nature")

    def test_system_category_display_name_can_be_edited(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = self._new_registry(tmpdir)
            updated = registry.update_category_properties("meme", display_name="Funny Images")

            self.assertTrue(updated.is_system)
            self.assertEqual(updated.id, "meme")
            self.assertEqual(updated.display_name, "Funny Images")
            self.assertEqual(registry.label_for("meme"), "Funny Images")

    def test_system_category_ai_description_can_be_edited(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = self._new_registry(tmpdir)
            updated = registry.update_category_properties(
                "meme",
                ai_description="Funny images, joke overlays, reaction memes.",
            )
            self.assertEqual(updated.id, "meme")
            self.assertEqual(updated.ai_description, "Funny images, joke overlays, reaction memes.")

    def test_system_category_flags_can_be_edited(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = self._new_registry(tmpdir)
            registry.update_category_properties("meme", is_cleanup_category=False, is_album_candidate=True)

            self.assertFalse(registry.is_cleanup_category("meme"))
            self.assertTrue(registry.is_album_candidate_category("meme"))

    def test_system_category_id_remains_stable_after_edit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = self._new_registry(tmpdir)
            before = registry.get("meme")
            self.assertIsNotNone(before)

            updated = registry.update_category_properties("meme", display_name="Funny Images")
            self.assertEqual(updated.id, "meme")
            self.assertTrue(registry.has_category("meme"))
            self.assertFalse(registry.has_category("funny_images"))

    def test_system_category_reset_restores_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = self._new_registry(tmpdir)
            registry.update_category_properties(
                "meme",
                display_name="Funny Images",
                description="Custom description",
                ai_description="Custom AI description",
                color="#FF00FF",
                icon="funny",
                is_cleanup_category=False,
                is_album_candidate=True,
            )

            reset = registry.reset_system_category_to_default("meme")
            self.assertEqual(reset.display_name, "Meme")
            self.assertEqual(reset.description, "Meme-like media.")
            self.assertEqual(reset.ai_description, "")
            self.assertEqual(reset.color, "")
            self.assertEqual(reset.icon, "")
            self.assertTrue(reset.is_cleanup_category)
            self.assertFalse(reset.is_album_candidate)

    def test_customized_system_category_persists_after_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = self._new_registry(tmpdir)
            registry.update_category_properties(
                "meme",
                display_name="Funny Images",
                ai_description="Funny content",
                is_cleanup_category=False,
                is_album_candidate=True,
            )

            reset_category_registry()
            loaded = get_category_registry(force_reload=True)
            loaded_item = loaded.get("meme")

            self.assertIsNotNone(loaded_item)
            self.assertEqual(loaded_item.display_name, "Funny Images")
            self.assertEqual(loaded_item.ai_description, "Funny content")
            self.assertFalse(loaded_item.is_cleanup_category)
            self.assertTrue(loaded_item.is_album_candidate)

    def test_duplicate_display_name_rejected_when_editing_system_category(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = self._new_registry(tmpdir)
            with self.assertRaises(ValueError):
                registry.update_category_properties("meme", display_name="Document")


if __name__ == "__main__":
    unittest.main()

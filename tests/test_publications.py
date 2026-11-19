import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from publications import (
    PublicationStore,
    SlugConflictError,
    content_revision,
    referenced_attachments,
)


class PublicationStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = PublicationStore(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_random_slug_is_stable_and_secure(self):
        initial = self.store.set("Example", "random", "read", None, "")
        self.assertEqual(len(initial["slug"]), 32)
        self.assertEqual(initial["permission"], "read")
        again = self.store.set("Example", "random", "edit", None, "")
        self.assertEqual(initial["slug"], again["slug"])
        self.assertEqual(again["permission"], "edit")
        reopened = PublicationStore(self.directory.name)
        self.assertEqual(reopened.get_by_slug(initial["slug"])["note_title"], "Example")

    def test_title_custom_and_conflict(self):
        first = self.store.set("Café Notes", "title", "read", None, "")
        self.assertEqual(first["slug"], "cafe-notes")
        with self.assertRaises(SlugConflictError):
            self.store.set("Another", "custom", "read", "cafe-notes", "")
        changed = self.store.set("Café Notes", "custom", "edit", "Custom-Link", "")
        self.assertEqual(changed["slug"], "custom-link")
        self.assertIsNone(self.store.get_by_slug("cafe-notes"))

    def test_reject_invalid_slugs(self):
        for slug in ("../secret", "two words", "-invalid", "a" * 81):
            with self.subTest(slug=slug):
                with self.assertRaises(ValueError):
                    self.store.set("Note", "custom", "read", slug, "")

    def test_rename_and_revoke(self):
        created = self.store.set("Old", "random", "read", None, "")
        with self.store.connection(write=True) as db:
            self.store.rename("Old", "New", db)
        self.assertEqual(self.store.get_by_slug(created["slug"])["note_title"], "New")
        with self.store.connection(write=True) as db:
            self.store.remove("New", db)
        self.assertIsNone(self.store.get_by_slug(created["slug"]))

    def test_attachment_allowlist(self):
        created = self.store.set(
            "Example", "random", "read", None,
            "![Image](attachments/public.png) and [file](/attachments/guide.pdf)",
        )
        self.assertTrue(self.store.has_attachment(created["id"], "public.png"))
        self.assertTrue(self.store.has_attachment(created["id"], "guide.pdf"))
        self.assertFalse(self.store.has_attachment(created["id"], "private.png"))
        with self.store.connection(write=True) as db:
            self.store.sync_attachments(created["id"], "![x](attachments/updated.png)", db)
        self.assertTrue(self.store.has_attachment(created["id"], "updated.png"))
        self.assertFalse(self.store.has_attachment(created["id"], "public.png"))

    def test_content_revisions(self):
        self.assertEqual(len(content_revision("example")), 64)
        self.assertNotEqual(content_revision("first"), content_revision("second"))
        self.assertIn("photo 1.png", referenced_attachments("![x](attachments/photo%201.png)"))


if __name__ == "__main__":
    unittest.main()

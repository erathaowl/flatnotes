"""Tests for opaque encrypted-note storage and sharing controls."""

import tempfile
import unittest
from pathlib import Path

from flatnotes.encrypted_storage import EncryptedNoteStore, EncryptedPublicationStore
from flatnotes.publications import PublicationStore, SlugConflictError


class EncryptedStoreTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = EncryptedNoteStore(self.folder.name)
        self.publications = PublicationStore(self.folder.name)
        self.encrypted_publications = EncryptedPublicationStore(self.publications)
        self.note_id = "12ab" * 8

    def tearDown(self):
        self.folder.cleanup()

    def test_ciphertext_file_only_and_revision_checks(self):
        first = b'{"version":1,"data":"opaque-ciphertext"}'
        revision = self.store.save(self.note_id, first, "*")
        self.assertEqual(self.store.read(self.note_id), first)
        path = Path(self.folder.name) / f"{self.note_id}.md.enc"
        self.assertTrue(path.is_file())
        self.assertEqual(list(Path(self.folder.name).glob("*.md")), [])
        self.assertEqual(self.store.list()[0]["id"], self.note_id)
        with self.assertRaises(FileExistsError):
            self.store.save(self.note_id, first, "*")
        with self.assertRaises(FileExistsError):
            self.store.save(self.note_id, first, "wrong-revision")
        second = b'{"version":1,"data":"updated-ciphertext"}'
        self.assertNotEqual(self.store.save(self.note_id, second, revision), revision)
        self.store.delete(self.note_id)
        self.assertFalse(path.exists())

    def test_invalid_identifiers_and_size(self):
        for identifier in ("../secret", "a" * 31, "g" * 32, ""):
            with self.subTest(identifier=identifier):
                with self.assertRaises(ValueError):
                    self.store.path(identifier)
        with self.assertRaises(ValueError):
            self.store.save(self.note_id, b"", "*")

    def test_cross_public_slug_collision(self):
        self.publications.set("Normal", "custom", "read", "shared", "body")
        with self.assertRaises(SlugConflictError):
            self.encrypted_publications.save(self.note_id, "custom", "read", "shared")
        result = self.encrypted_publications.save(self.note_id, "random", "read", None)
        self.assertEqual(result["permission"], "read")
        self.assertEqual(len(result["slug"]), 32)
        self.assertEqual(self.encrypted_publications.get(slug=result["slug"])["note_id"], self.note_id)
        self.encrypted_publications.delete(self.note_id)
        self.assertIsNone(self.encrypted_publications.get(slug=result["slug"]))


if __name__ == "__main__":
    unittest.main()

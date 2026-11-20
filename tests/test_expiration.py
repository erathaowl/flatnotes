"""Publication expiration, migration, cleanup and single-view concurrency."""

import hashlib
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flatnotes.encrypted_storage import EncryptedPublicationStore
from flatnotes.expiration import ExpirationError, ExpirationStore, ensure_active, parse_policy
from flatnotes.publications import PublicationStore


class PublicationExpirationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.publications = PublicationStore(self.directory.name)
        self.encrypted_publications = EncryptedPublicationStore(self.publications)
        self.expiration = ExpirationStore(self.publications)

    def tearDown(self):
        self.directory.cleanup()

    def publish(self, title, policy="none", auto_delete=False, permission="read"):
        return self.publications.set(
            title, "random", permission, None, "Some Markdown",
            policy, auto_delete,
        )

    def test_policy_validation(self):
        self.assertEqual(parse_policy("none"), ("none", None))
        self.assertEqual(parse_policy("once"), ("once", None))
        self.assertEqual(parse_policy("2h"), ("time", 7200))
        self.assertEqual(parse_policy("7d"), ("time", 7 * 86400))
        for invalid in ("", "0h", "5m", "5000d", "-1d", None):
            with self.subTest(policy=invalid), self.assertRaises(ValueError):
                parse_policy(invalid)

    def test_default_and_auto_delete_validation(self):
        plain = self.publish("PrivateByDefault")
        self.assertEqual(plain["expiration"], "none")
        self.assertFalse(plain["auto_delete_note"])
        with self.assertRaises(ValueError):
            self.publish("Invalid", "none", True)
        with self.assertRaises(ValueError):
            self.publish("InvalidOnceEdit", "once", False, "edit")

    def test_timed_public_expiry_and_renewal(self):
        published = self.publish("Timed", "2h")
        self.assertAlmostEqual(published["expires_at"], int(time.time()) + 7200, delta=2)
        # Ordinary content edits do not extend a publication deadline.
        updated = self.publish("Timed", "2h")
        self.assertEqual(updated["expires_at"], published["expires_at"])
        with self.publications.connection(write=True) as db:
            db.execute(
                "UPDATE publications SET expires_at=? WHERE note_title='Timed'",
                (int(time.time()) - 1,),
            )
        with self.assertRaises(ExpirationError):
            ensure_active(self.publications.get_by_title("Timed"))
        renewed = self.publish("Timed", "2h")
        self.assertNotEqual(renewed["slug"], published["slug"])
        self.assertFalse(renewed["expired"])

    def test_single_view_atomic_claim(self):
        published = self.publish("Single", "once")
        def claim(_):
            try:
                with self.publications.connection(write=True) as db:
                    current = self.publications.get_by_title("Single", db)
                    return self.expiration.consume(current, db=db, allow_session=True)
            except ExpirationError:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            claimed = list(pool.map(claim, range(8)))
        tokens = [value for value in claimed if value]
        self.assertEqual(len(tokens), 1)
        self.assertTrue(self.expiration.view_session_valid(published["slug"], tokens[0]))
        self.assertTrue(self.publications.get_by_title("Single")["expired"])

    def test_encrypted_proof(self):
        proof = bytes.fromhex("ab" * 32)
        verifier = hashlib.sha256(proof).hexdigest()
        note_id = "e" * 32
        with self.assertRaises(ValueError):
            self.encrypted_publications.save(note_id, "random", "read", None, "once")
        self.encrypted_publications.save(note_id, "random", "read", None, "once", False, verifier)
        with self.publications.connection(write=True) as db:
            current = self.encrypted_publications.get(note_id=note_id, db=db)
            with self.assertRaises(PermissionError):
                self.expiration.consume(current, proof="00" * 32, db=db)
            self.expiration.consume(current, proof=proof.hex(), db=db)
        with self.assertRaises(ExpirationError):
            ensure_active(self.encrypted_publications.get(note_id=note_id))

    def test_cleanup_revokes_share_but_preserves_note(self):
        (self.root / "Preserved.md").write_text("important")
        published = self.publish("Preserved", "1h")
        with self.publications.connection(write=True) as db:
            db.execute(
                "UPDATE publications SET expires_at=? WHERE note_title='Preserved'",
                (int(time.time()) - 1,),
            )
        self.cleanup()
        self.assertTrue((self.root / "Preserved.md").exists())
        self.assertIsNone(self.publications.get_by_title("Preserved"))
        self.assertFalse(self.publications.get_by_slug(published["slug"]))

    def test_auto_delete_removes_only_orphaned_attachments(self):
        from flatnotes.notes.models import Note

        attachments = self.root / "attachments"
        attachments.mkdir()
        (attachments / "orphan.png").write_bytes(b"one")
        (attachments / "shared.png").write_bytes(b"two")
        (self.root / "Disposable.md").write_text(
            "![orphan](attachments/orphan.png)\n![shared](attachments/shared.png)"
        )
        (self.root / "Other.md").write_text("![shared](attachments/shared.png)")
        self.publish("Disposable", "1h", True)
        with self.publications.connection(write=True) as db:
            db.execute(
                "UPDATE publications SET expires_at=? WHERE note_title='Disposable'",
                (int(time.time()) - 1,),
            )
        self.cleanup()
        self.assertFalse((self.root / "Disposable.md").exists())
        self.assertFalse((attachments / "orphan.png").exists())
        self.assertTrue((attachments / "shared.png").exists())
        self.assertTrue((self.root / "Other.md").exists())

    def test_manual_unpublish_never_deletes_note(self):
        (self.root / "KeepMe.md").write_text("keep")
        self.publish("KeepMe", "once", True)
        with self.publications.connection(write=True) as db:
            self.publications.remove("KeepMe", db)
        self.cleanup()
        self.assertTrue((self.root / "KeepMe.md").exists())

    def test_migration_preserves_published_and_clears_private(self):
        with self.publications.connection(write=True) as db:
            db.execute(
                """CREATE TABLE note_expirations (
                    note_type TEXT, note_id TEXT, policy TEXT, mode TEXT,
                    created_at INTEGER, expires_at INTEGER, consumed_at INTEGER,
                    status TEXT, view_verifier TEXT, purged_at INTEGER
                )"""
            )
            deadline = int(time.time()) + 7200
            db.execute(
                """INSERT INTO note_expirations VALUES
                   ('plain','PrivateLegacy','2h','time',?, ?, NULL,'active',NULL,NULL)""",
                (int(time.time()), deadline),
            )
            db.execute(
                """INSERT INTO note_expirations VALUES
                   ('plain','PublishedLegacy','2h','time',?, ?, NULL,'active',NULL,NULL)""",
                (int(time.time()), deadline),
            )
        (self.root / "PrivateLegacy.md").write_text("must survive")
        (self.root / "AlreadyConsumed.md").write_text("delete old terminal")
        with self.publications.connection(write=True) as db:
            db.execute(
                """INSERT INTO note_expirations VALUES
                   ('plain','AlreadyConsumed','once','once',?,NULL,?,
                    'consumed',NULL,NULL)""",
                (int(time.time()), int(time.time())),
            )
            db.execute(
                "UPDATE note_expirations SET expires_at=? WHERE note_id='PrivateLegacy'",
                (int(time.time()) - 7200,),
            )
        self.publish("PublishedLegacy")
        upgraded = ExpirationStore(self.publications)
        published = self.publications.get_by_title("PublishedLegacy")
        self.assertEqual(published["expiration"], "2h")
        self.assertEqual(published["expires_at"], deadline)
        self.assertTrue(published["auto_delete_note"])
        self.assertTrue(
            (self.root / "PrivateLegacy.md").exists()
        )  # Active private expiry is discarded while the file is preserved.
        with self.publications.connection() as db:
            self.assertFalse(db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='note_expirations'"
            ).fetchone())
        ExpirationStore(self.publications)  # Repeated startup is idempotent.
        self.cleanup()
        self.assertEqual((self.root / "PrivateLegacy.md").read_text(), "must survive")
        self.assertFalse((self.root / "AlreadyConsumed.md").exists())
        self.assertEqual(
            self.publications.get_by_title("PublishedLegacy")["expiration"], "2h"
        )

    def test_legacy_schema_without_purged_at(self):
        with self.publications.connection(write=True) as db:
            db.execute(
                """CREATE TABLE note_expirations (
                    note_type TEXT, note_id TEXT, policy TEXT, mode TEXT,
                    created_at INTEGER, expires_at INTEGER, consumed_at INTEGER,
                    status TEXT, view_verifier TEXT
                )"""
            )
            db.execute(
                """INSERT INTO note_expirations VALUES
                   ('plain','LegacyPrivate','1h','time',?,NULL,NULL,'active',NULL)""",
                (int(time.time()),),
            )
        (self.root / "LegacyPrivate.md").write_text("keep original")
        ExpirationStore(self.publications)
        self.cleanup()
        self.assertEqual((self.root / "LegacyPrivate.md").read_text(), "keep original")

    def cleanup(self):
        from flatnotes.notes.models import Note

        root = self.root
        class Ordinary:
            storage_path = str(root)

            def get(self, title):
                path = root / (title + ".md")
                if not path.exists():
                    raise FileNotFoundError(title)
                return Note(title=title, content=path.read_text(), last_modified=0)

            def delete(self, title):
                (root / (title + ".md")).unlink()

            def _sync_index_with_retry(self):
                pass

        class Encrypted:
            def delete(self, note_id):
                (root / (note_id + ".md.enc")).unlink()

        self.expiration.cleanup(Ordinary(), Encrypted())


if __name__ == "__main__":
    unittest.main()

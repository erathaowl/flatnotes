"""Expiration parsing, atomic single-view claims, and metadata lifecycle."""

import hashlib
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flatnotes.expiration import ExpirationError, ExpirationStore, parse_policy
from flatnotes.publications import PublicationStore


class ExpirationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.publications = PublicationStore(self.directory.name)
        self.store = ExpirationStore(self.publications)

    def tearDown(self):
        self.directory.cleanup()

    def test_policy_validation(self):
        self.assertEqual(parse_policy("none"), ("none", None))
        self.assertEqual(parse_policy("once"), ("once", None))
        self.assertEqual(parse_policy("2h"), ("time", 7200))
        self.assertEqual(parse_policy("7d"), ("time", 7 * 86400))
        for value in ("0h", "-1d", "5m", "30", "", "5000d", "NaN", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_policy(value)

    def test_timed_expiration_and_reset(self):
        item = self.store.set("plain", "Example", "2h")
        self.assertEqual(item["mode"], "time")
        self.assertAlmostEqual(item["expiresAt"], int(time.time()) + 7200, delta=2)
        self.assertTrue(self.store.is_available("plain", "Example"))
        with self.publications.connection(write=True) as db:
            db.execute(
                "UPDATE note_expirations SET expires_at=? WHERE note_type='plain'",
                (int(time.time()) - 1,),
            )
        with self.assertRaises(ExpirationError):
            self.store.ensure_available("plain", "Example")
        with self.assertRaises(ExpirationError):
            self.store.set("plain", "Example", "none")

    def test_one_view_claim_is_atomic(self):
        self.store.set("plain", "single", "once")
        def claim(_):
            try:
                return self.store.consume("plain", "single", allow_session=True)
            except ExpirationError:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            values = list(pool.map(claim, range(8)))
        self.assertEqual(len([v for v in values if v]), 1)
        self.assertEqual(self.store.get("plain", "single")["status"], "consumed")
        self.assertTrue(self.store.view_session_valid("plain", "single", next(v for v in values if v)))

    def test_encrypted_one_view_requires_valid_proof(self):
        proof = bytes.fromhex("ab" * 32)
        digest = hashlib.sha256(proof).hexdigest()
        with self.assertRaises(ValueError):
            self.store.set("encrypted", "1" * 32, "once")
        self.store.set("encrypted", "1" * 32, "once", digest)
        with self.assertRaises(PermissionError):
            self.store.consume("encrypted", "1" * 32, proof="00" * 32)
        self.assertEqual(
            self.store.consume("encrypted", "1" * 32, proof=proof.hex()), None
        )
        with self.assertRaises(ExpirationError):
            self.store.consume("encrypted", "1" * 32, proof=proof.hex())

    def test_transfer_and_rename(self):
        self.store.set("plain", "draft", "4h")
        with self.publications.connection(write=True) as db:
            self.store.rename("plain", "draft", "renamed", db)
        self.assertEqual(self.store.get("plain", "renamed")["policy"], "4h")
        with self.publications.connection(write=True) as db:
            self.store.transfer("plain", "renamed", "encrypted", "c" * 32, db)
        self.assertEqual(self.store.get("encrypted", "c" * 32)["policy"], "4h")
        self.assertEqual(self.store.get("plain", "renamed")["policy"], "none")


if __name__ == "__main__":
    unittest.main()

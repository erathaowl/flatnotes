"""Opaque ciphertext storage and public-link metadata.

This module never receives, interprets, logs, or indexes plaintext note content.
"""

import hashlib
import os
import re
import secrets
import sqlite3
import tempfile
from pathlib import Path

from flatnotes.publications import SLUG_PATTERN, SlugConflictError, note_slug

NOTE_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_ENVELOPE_BYTES = 4 * 1024 * 1024


class EncryptedNoteStore:
    def __init__(self, directory: str):
        self.directory = Path(directory)

    def path(self, note_id: str) -> Path:
        if not NOTE_ID.fullmatch(note_id):
            raise ValueError("Invalid encrypted note ID")
        return self.directory / f"{note_id}.md.enc"

    def read(self, note_id: str) -> bytes:
        return self.path(note_id).read_bytes()

    def revision(self, note_id: str) -> str:
        return hashlib.sha256(self.read(note_id)).hexdigest()

    def save(self, note_id: str, data: bytes, expected: str | None = None):
        if not data or len(data) > MAX_ENVELOPE_BYTES:
            raise ValueError("Invalid encrypted note size")
        destination = self.path(note_id)
        if expected == "*":
            if destination.exists():
                raise FileExistsError("Encrypted note already exists")
        elif expected is None or expected != self.revision(note_id):
            raise FileExistsError("Encrypted note revision mismatch")
        # Always replace the ciphertext using an atomic file rename.
        fd, temporary = tempfile.mkstemp(dir=self.directory, prefix=".encrypted-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)
        return hashlib.sha256(data).hexdigest()

    def list(self):
        return [
            {"id": path.name[:-7], "lastModified": path.stat().st_mtime}
            for path in self.directory.glob("*.md.enc")
            if NOTE_ID.fullmatch(path.name[:-7])
        ]

    def delete(self, note_id: str):
        self.path(note_id).unlink()


class EncryptedPublicationStore:
    def __init__(self, publication_store):
        self.store = publication_store
        with self.store.connection(write=True) as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS encrypted_publications (
                    note_id TEXT PRIMARY KEY,
                    slug TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    slug_mode TEXT NOT NULL CHECK(slug_mode IN ('random','title','custom')),
                    permission TEXT NOT NULL CHECK(permission IN ('read','edit'))
                )"""
            )

    def get(self, note_id=None, slug=None, db=None):
        if db is None:
            with self.store.connection() as connection:
                return self.get(note_id, slug, connection)
        if note_id:
            row = db.execute(
                "SELECT * FROM encrypted_publications WHERE note_id=?", (note_id,)
            ).fetchone()
        else:
            row = db.execute(
                "SELECT * FROM encrypted_publications WHERE slug=?", (slug,)
            ).fetchone()
        return dict(row) if row else None

    def save(self, note_id, mode, permission, requested_slug):
        with self.store.connection(write=True) as db:
            current = self.get(note_id=note_id, db=db)
            if mode == "random":
                slug = current["slug"] if current and current["slug_mode"] == mode else secrets.token_hex(16)
            elif mode == "title":
                # Encrypted titles are never sent to the server.
                raise ValueError("Encrypted notes require a random or custom URL suffix")
            else:
                slug = (requested_slug or "").strip().lower()
            if not SLUG_PATTERN.fullmatch(slug):
                raise ValueError("Invalid public URL suffix")
            if db.execute("SELECT 1 FROM publications WHERE slug=? COLLATE NOCASE", (slug,)).fetchone():
                raise SlugConflictError("Public URL already exists")
            try:
                db.execute(
                    """INSERT INTO encrypted_publications (note_id, slug, slug_mode, permission)
                    VALUES (?, ?, ?, ?) ON CONFLICT(note_id) DO UPDATE SET
                    slug=excluded.slug, slug_mode=excluded.slug_mode, permission=excluded.permission""",
                    (note_id, slug, mode, permission),
                )
            except sqlite3.IntegrityError as error:
                raise SlugConflictError("Public URL already exists") from error
            return self.get(note_id=note_id, db=db)

    def delete(self, note_id, db=None):
        if db is None:
            with self.store.connection(write=True) as connection:
                self.delete(note_id, connection)
            return
        db.execute("DELETE FROM encrypted_publications WHERE note_id=?", (note_id,))

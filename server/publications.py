"""SQLite-backed publication settings for selectively shared notes."""

import hashlib
import re
import secrets
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote

from helpers import is_valid_filename

SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")
ATTACHMENT_PATTERN = re.compile(
    r"(?<![\w/])/?attachments/([^\s<>\)\]\[\"'?#]+)"
)


class SlugConflictError(ValueError):
    pass


def content_revision(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def note_slug(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")[:80]
    return slug.rstrip("-")


def referenced_attachments(content: str) -> set[str]:
    names = set()
    for match in ATTACHMENT_PATTERN.finditer(content):
        filename = unquote(match.group(1))
        try:
            is_valid_filename(filename)
        except ValueError:
            continue
        if filename not in (".", ".."):
            names.add(filename)
    return names


class PublicationStore:
    def __init__(self, data_path: str):
        self.path = Path(data_path) / ".flatnotes-publications.db"
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS publications (
                    id INTEGER PRIMARY KEY,
                    note_title TEXT NOT NULL UNIQUE,
                    slug TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    slug_mode TEXT NOT NULL CHECK(slug_mode IN ('random','title','custom')),
                    permission TEXT NOT NULL CHECK(permission IN ('read','edit')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS public_attachments (
                    publication_id INTEGER NOT NULL
                        REFERENCES publications(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    PRIMARY KEY (publication_id, filename)
                );
                PRAGMA user_version=1;
                """
            )

    @contextmanager
    def connection(self, write=False):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except Exception:
            if write:
                db.rollback()
            raise
        finally:
            db.close()

    def get_by_title(self, title, db=None):
        if db is None:
            with self.connection() as connection:
                return self.get_by_title(title, connection)
        row = db.execute(
            "SELECT * FROM publications WHERE note_title = ?", (title,)
        ).fetchone()
        return dict(row) if row else None

    def get_by_slug(self, slug, db=None):
        if db is None:
            with self.connection() as connection:
                return self.get_by_slug(slug, connection)
        row = db.execute(
            "SELECT * FROM publications WHERE slug = ?", (slug,)
        ).fetchone()
        return dict(row) if row else None

    def set(self, title, slug_mode, permission, requested_slug, content):
        with self.connection(write=True) as db:
            current = self.get_by_title(title, db)
            if slug_mode == "random":
                slug = (
                    current["slug"]
                    if current and current["slug_mode"] == slug_mode
                    else secrets.token_hex(16)
                )
            elif slug_mode == "title":
                slug = (
                    current["slug"]
                    if current and current["slug_mode"] == slug_mode
                    else note_slug(title)
                )
            else:
                slug = (requested_slug or "").strip().lower()

            if not SLUG_PATTERN.fullmatch(slug):
                raise ValueError(
                    "Invalid slug. Use 1-80 lowercase letters, digits or hyphens."
                )

            try:
                if current:
                    db.execute(
                        """UPDATE publications
                           SET slug=?, slug_mode=?, permission=?,
                               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                        (slug, slug_mode, permission, current["id"]),
                    )
                    publication_id = current["id"]
                else:
                    publication_id = db.execute(
                        """INSERT INTO publications
                           (note_title, slug, slug_mode, permission)
                           VALUES (?, ?, ?, ?)""",
                        (title, slug, slug_mode, permission),
                    ).lastrowid
            except sqlite3.IntegrityError as error:
                raise SlugConflictError("Public URL is already in use.") from error

            # Only owner-controlled operations may expand the attachment allowlist.
            if not current:
                self.sync_attachments(publication_id, content, db)
            return self.get_by_title(title, db)

    def sync_attachments(self, publication_id, content, db):
        db.execute(
            "DELETE FROM public_attachments WHERE publication_id = ?",
            (publication_id,),
        )
        for filename in referenced_attachments(content):
            db.execute(
                """INSERT INTO public_attachments
                   (publication_id, filename) VALUES (?, ?)""",
                (publication_id, filename),
            )

    def has_attachment(self, publication_id, filename):
        with self.connection() as db:
            return db.execute(
                """SELECT 1 FROM public_attachments
                   WHERE publication_id=? AND filename=?""",
                (publication_id, filename),
            ).fetchone() is not None

    def rename(self, old_title, new_title, db):
        db.execute(
            """UPDATE publications
               SET note_title=?, updated_at=CURRENT_TIMESTAMP
               WHERE note_title=?""",
            (new_title, old_title),
        )

    def remove(self, title, db):
        db.execute("DELETE FROM publications WHERE note_title=?", (title,))

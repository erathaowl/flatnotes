"""Expiration policies, atomic single-view claims and deletion state.

This module manages metadata only. Protected note ciphertext stays opaque.
"""

import hashlib
import hmac
import re
import secrets
import time

from flatnotes.publications import PublicationStore, referenced_attachments
from pathlib import Path

DURATION_PATTERN = re.compile(r"^([1-9][0-9]{0,5})([hd])$")
VERIFIER_PATTERN = re.compile(r"^[a-f0-9]{64}$")
MAX_SECONDS = 3650 * 86400
VIEW_SESSION_SECONDS = 180


class ExpirationError(Exception):
    """An unavailable, consumed or expired note."""


def parse_policy(value):
    if value == "none":
        return "none", None
    if value == "once":
        return "once", None
    match = DURATION_PATTERN.fullmatch(value or "")
    if not match:
        raise ValueError("Use none, once, or a positive number followed by h or d")
    seconds = int(match.group(1)) * (3600 if match.group(2) == "h" else 86400)
    if seconds > MAX_SECONDS:
        raise ValueError("Expiration duration exceeds 3650 days")
    return "time", seconds


class ExpirationStore:
    def __init__(self, publications: PublicationStore):
        self.publications = publications
        with publications.connection(write=True) as db:
            db.executescript(
                """CREATE TABLE IF NOT EXISTS note_expirations (
                    note_type TEXT NOT NULL CHECK(note_type IN ('plain', 'encrypted')),
                    note_id TEXT NOT NULL,
                    policy TEXT NOT NULL,
                    mode TEXT NOT NULL CHECK(mode IN ('time', 'once')),
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER,
                    consumed_at INTEGER,
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active', 'consumed', 'expired')),
                    view_verifier TEXT,
                    purged_at INTEGER,
                    PRIMARY KEY (note_type, note_id)
                );
                CREATE INDEX IF NOT EXISTS expiration_cleanup_idx
                    ON note_expirations (status, expires_at);
                CREATE TABLE IF NOT EXISTS note_view_sessions (
                    token_hash TEXT PRIMARY KEY,
                    note_type TEXT NOT NULL,
                    note_id TEXT NOT NULL,
                    expires_at INTEGER NOT NULL
                );"""
            )

        with publications.connection(write=True) as db:
            columns = {
                row["name"] for row in db.execute("PRAGMA table_info(note_expirations)")
            }
            if "purged_at" not in columns:
                db.execute("ALTER TABLE note_expirations ADD COLUMN purged_at INTEGER")

    def get(self, kind, note_id, db=None):
        if db is None:
            with self.publications.connection() as connection:
                return self.get(kind, note_id, connection)
        row = db.execute(
            "SELECT * FROM note_expirations WHERE note_type=? AND note_id=?",
            (kind, note_id),
        ).fetchone()
        if not row:
            return {"policy": "none", "mode": "none", "expiresAt": None, "status": "active"}
        result = dict(row)
        status = result["status"]
        if status == "active" and result["expires_at"] is not None:
            if result["expires_at"] <= int(time.time()):
                status = "expired"
        return {
            "policy": result["policy"],
            "mode": result["mode"],
            "expiresAt": result["expires_at"],
            "status": status,
        }

    def is_available(self, kind, note_id, db=None):
        return self.get(kind, note_id, db)["status"] == "active"

    def ensure_available(self, kind, note_id, db=None):
        if not self.is_available(kind, note_id, db):
            raise ExpirationError("Note is no longer available")

    def is_indexable(self, title):
        value = self.get("plain", title)
        return value["status"] == "active" and value["mode"] != "once"

    def set(self, kind, note_id, policy, verifier=None, db=None):
        if db is None:
            with self.publications.connection(write=True) as connection:
                return self.set(kind, note_id, policy, verifier, connection)
        self.ensure_available(kind, note_id, db)
        mode, seconds = parse_policy(policy)
        if mode == "none":
            db.execute(
                "DELETE FROM note_expirations WHERE note_type=? AND note_id=?",
                (kind, note_id),
            )
            return self.get(kind, note_id, db)
        if mode == "once" and kind == "encrypted":
            if not verifier or not VERIFIER_PATTERN.fullmatch(verifier):
                raise ValueError("Encrypted single-view notes require a browser-generated verifier")
        else:
            verifier = None
        now = int(time.time())
        expires_at = now + seconds if seconds is not None else None
        db.execute(
            """INSERT INTO note_expirations
               (note_type, note_id, policy, mode, created_at, expires_at, view_verifier)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(note_type, note_id) DO UPDATE SET
               policy=excluded.policy, mode=excluded.mode,
               created_at=excluded.created_at, expires_at=excluded.expires_at,
               view_verifier=excluded.view_verifier,
               consumed_at=NULL, purged_at=NULL, status='active'""",
            (kind, note_id, policy, mode, now, expires_at, verifier),
        )
        return self.get(kind, note_id, db)

    def transfer(self, src_kind, src_id, dst_kind, dst_id, db, verifier=None):
        self.ensure_available(src_kind, src_id, db)
        row = db.execute(
            "SELECT * FROM note_expirations WHERE note_type=? AND note_id=?",
            (src_kind, src_id),
        ).fetchone()
        if row:
            if row["mode"] == "once" and dst_kind == "encrypted":
                if not verifier or not VERIFIER_PATTERN.fullmatch(verifier):
                    raise ValueError("Encrypted single-view conversion requires a verifier")
            db.execute(
                """UPDATE note_expirations SET note_type=?, note_id=?, view_verifier=?
                   WHERE note_type=? AND note_id=?""",
                (dst_kind, dst_id, verifier if dst_kind == "encrypted" else None,
                 src_kind, src_id),
            )

    def rename(self, kind, old_id, new_id, db):
        db.execute(
            "UPDATE note_expirations SET note_id=? WHERE note_type=? AND note_id=?",
            (new_id, kind, old_id),
        )

    def remove(self, kind, note_id, db):
        db.execute(
            "DELETE FROM note_expirations WHERE note_type=? AND note_id=?",
            (kind, note_id),
        )
        db.execute(
            "DELETE FROM note_view_sessions WHERE note_type=? AND note_id=?",
            (kind, note_id),
        )

    def consume(self, kind, note_id, proof=None, db=None, allow_session=False):
        if db is None:
            with self.publications.connection(write=True) as connection:
                return self.consume(kind, note_id, proof, connection, allow_session)
        self.ensure_available(kind, note_id, db)
        row = db.execute(
            "SELECT mode, view_verifier FROM note_expirations WHERE note_type=? AND note_id=?",
            (kind, note_id),
        ).fetchone()
        if not row or row["mode"] != "once":
            return None
        if kind == "encrypted":
            if not proof or not isinstance(proof, str) or len(proof) != 64:
                raise PermissionError("A browser unlock proof is required")
            try:
                digest = hashlib.sha256(bytes.fromhex(proof)).hexdigest()
            except ValueError as error:
                raise PermissionError("Invalid unlock proof") from error
            if not hmac.compare_digest(digest, row["view_verifier"] or ""):
                raise PermissionError("Invalid unlock proof")
        now = int(time.time())
        token = secrets.token_urlsafe(32) if allow_session and kind == "plain" else None
        result = db.execute(
            """UPDATE note_expirations SET status='consumed', consumed_at=?
               WHERE note_type=? AND note_id=? AND status='active'""",
            (now, kind, note_id),
        )
        if result.rowcount != 1:
            raise ExpirationError("Note has already been consumed")
        if token:
            db.execute(
                """INSERT INTO note_view_sessions
                   (token_hash, note_type, note_id, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (hashlib.sha256(token.encode()).hexdigest(), kind, note_id, now + VIEW_SESSION_SECONDS),
            )
        return token

    def view_session_valid(self, kind, note_id, token, db=None):
        if not token or len(token) > 200:
            return False
        if db is None:
            with self.publications.connection() as connection:
                return self.view_session_valid(kind, note_id, token, connection)
        return db.execute(
            """SELECT 1 FROM note_view_sessions
               WHERE token_hash=? AND note_type=? AND note_id=? AND expires_at>?""",
            (hashlib.sha256(token.encode()).hexdigest(), kind, note_id, int(time.time())),
        ).fetchone() is not None

    def list_active(self):
        with self.publications.connection() as db:
            rows = db.execute(
                """SELECT note_type, note_id FROM note_expirations
                   WHERE status='active' ORDER BY expires_at IS NULL, expires_at, note_id"""
            ).fetchall()
            return [
                {"type": row["note_type"], "id": row["note_id"],
                 **self.get(row["note_type"], row["note_id"], db)}
                for row in rows
                if self.is_available(row["note_type"], row["note_id"], db)
            ]

    def terminal(self, db):
        now = int(time.time())
        db.execute(
            """UPDATE note_expirations SET status='expired'
               WHERE status='active' AND expires_at IS NOT NULL AND expires_at<=?""",
            (now,),
        )
        db.execute("DELETE FROM note_view_sessions WHERE expires_at<=?", (now,))
        return [
            (r["note_type"], r["note_id"])
            for r in db.execute(
                """SELECT note_type, note_id FROM note_expirations e
                   WHERE status IN ('consumed', 'expired') AND purged_at IS NULL
                   AND NOT EXISTS (
                     SELECT 1 FROM note_view_sessions v
                     WHERE v.note_type=e.note_type AND v.note_id=e.note_id
                   )"""
            )
        ]

    @staticmethod
    def delete_orphaned_attachments(ordinary, candidate_names):
        """Keep shared and uncertain attachments; remove only verified orphans."""
        if not candidate_names:
            return
        directory = Path(ordinary.storage_path)
        referenced = set()
        try:
            for path in directory.glob("*.md"):
                referenced.update(referenced_attachments(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeError):
            # A failed scan must never cause accidental file deletion.
            return
        attachment_dir = directory / "attachments"
        for name in candidate_names - referenced:
            path = attachment_dir / name
            if path.parent == attachment_dir:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass

    def cleanup(self, ordinary, encrypted, encrypted_publications):
        """Delete terminal files and publications; retain tombstones for HTTP 410."""
        needs_reindex = False
        with self.publications.connection(write=True) as db:
            for kind, note_id in self.terminal(db):
                try:
                    if kind == "plain":
                        try:
                            candidate_names = referenced_attachments(ordinary.get(note_id).content or "")
                        except (FileNotFoundError, ValueError, UnicodeError):
                            candidate_names = set()
                        try:
                            ordinary.delete(note_id)
                        except FileNotFoundError:
                            pass
                        self.publications.remove(note_id, db)
                        self.delete_orphaned_attachments(ordinary, candidate_names)
                        needs_reindex = True
                    else:
                        try:
                            encrypted.delete(note_id)
                        except FileNotFoundError:
                            pass
                        encrypted_publications.delete(note_id, db)
                    db.execute(
                        "UPDATE note_expirations SET purged_at=? WHERE note_type=? AND note_id=?",
                        (int(time.time()), kind, note_id),
                    )
                except OSError:
                    # Keep terminal state and retry deletion at the next pass.
                    continue
        if needs_reindex:
            ordinary._sync_index_with_retry()

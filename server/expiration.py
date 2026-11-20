"""Public-link expiration, one-view claims, cleanup, and 6.3 migration."""

import hashlib
import hmac
import logging
from pathlib import Path
import re
import secrets
import time

DURATION_PATTERN = re.compile(r"^([1-9][0-9]{0,5})([hd])$")
VERIFIER_PATTERN = re.compile(r"^[a-f0-9]{64}$")
MAX_SECONDS = 3650 * 86400
VIEW_SESSION_SECONDS = 180
logger = logging.getLogger(__name__)

TABLES = {"plain": ("publications", "note_title"), "encrypted": ("encrypted_publications", "note_id")}
COLUMNS = {
    "expiration_policy": "TEXT NOT NULL DEFAULT 'none'",
    "expires_at": "INTEGER",
    "consumed_at": "INTEGER",
    "auto_delete_note": "INTEGER NOT NULL DEFAULT 0",
    "view_verifier": "TEXT",
}


class ExpirationError(Exception):
    """The public link is expired or its single view was consumed."""


def parse_policy(policy):
    if policy in ("none", "once"):
        return policy, None
    match = DURATION_PATTERN.fullmatch(policy or "")
    if not match:
        raise ValueError("Use none, once, or a positive number followed by h or d")
    seconds = int(match.group(1)) * (3600 if match.group(2) == "h" else 86400)
    if seconds > MAX_SECONDS:
        raise ValueError("Expiration duration exceeds 3650 days")
    return "time", seconds


def ensure_columns(db):
    """Upgrade publication tables without dropping user data."""
    for table, _ in TABLES.values():
        existing = {item["name"] for item in db.execute(f"PRAGMA table_info({table})")}
        for name, definition in COLUMNS.items():
            if name not in existing:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def is_expired(publication):
    return bool(
        publication and (
            publication.get("consumed_at") is not None
            or (
                publication.get("expires_at") is not None
                and publication["expires_at"] <= int(time.time())
            )
        )
    )


def ensure_active(publication):
    if is_expired(publication):
        raise ExpirationError("Public link expired or already viewed")


def public_info(row):
    if row is None:
        return None
    data = dict(row)
    data["expiration"] = data.get("expiration_policy", "none")
    data["auto_delete_note"] = bool(data.get("auto_delete_note", False))
    data["expired"] = is_expired(data)
    return data


def configure(db, kind, note_id, policy="none", auto_delete=False, verifier=None, previous=None):
    """Save link expiry in the same transaction as publication settings."""
    mode, seconds = parse_policy(policy)
    table, column = TABLES[kind]
    access = db.execute(
        f"SELECT permission FROM {table} WHERE {column}=?", (note_id,),
    ).fetchone()
    if not access:
        raise ValueError("Publication not found")
    if mode == "once" and access["permission"] != "read":
        raise ValueError("Single-view links must be read-only")
    if mode == "none" and auto_delete:
        raise ValueError("Auto-delete requires a configured expiration")
    if mode == "once" and kind == "encrypted":
        if verifier is None and previous and previous.get("expiration_policy") == "once":
            verifier = previous.get("view_verifier")
        if not verifier or not VERIFIER_PATTERN.fullmatch(verifier):
            raise ValueError("An encrypted single-view link needs an unlock verifier")
    else:
        verifier = None
    same = previous and previous.get("expiration_policy", "none") == policy
    # Changing only the access permission does not extend the deadline.
    deadline = previous["expires_at"] if same else int(time.time()) + seconds if seconds else None
    consumed = previous["consumed_at"] if same else None
    table, column = TABLES[kind]
    db.execute(
        f"""UPDATE {table} SET expiration_policy=?, expires_at=?,
            consumed_at=?, auto_delete_note=?, view_verifier=?
            WHERE {column}=?""",
        (policy, deadline, consumed, int(bool(auto_delete)), verifier, note_id),
    )


class ExpirationStore:
    def __init__(self, publication_store):
        self.store = publication_store
        with self.store.connection(write=True) as db:
            ensure_columns(db)
            db.execute(
                """CREATE TABLE IF NOT EXISTS publication_view_sessions (
                    token_hash TEXT PRIMARY KEY,
                    slug TEXT NOT NULL,
                    expires_at INTEGER NOT NULL
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS legacy_pending_deletions (
                    note_type TEXT NOT NULL,
                    note_id TEXT NOT NULL,
                    delete_after INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(note_type, note_id)
                )"""
            )
            self._migrate_legacy(db)

    @staticmethod
    def _migrate_legacy(db):
        has_legacy = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='note_expirations'"
        ).fetchone()
        if not has_legacy:
            return
        old_sessions = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='note_view_sessions'"
        ).fetchone()
        migrated = 0
        discarded = 0
        pending = 0
        rows = db.execute("SELECT * FROM note_expirations").fetchall()
        for row in rows:
            kind, note_id = row["note_type"], row["note_id"]
            table, column = TABLES[kind]
            published = db.execute(
                f"SELECT * FROM {table} WHERE {column}=?", (note_id,)
            ).fetchone()
            terminal = row["status"] != "active" or (
                row["expires_at"] is not None and row["expires_at"] <= int(time.time())
            )
            if published and row["purged_at"] is None:
                # Legacy note expiry deleted the underlying file; retain that
                # behavior for migrated published links only.
                db.execute(
                    f"""UPDATE {table} SET expiration_policy=?, expires_at=?,
                        consumed_at=?, auto_delete_note=1, view_verifier=?
                        WHERE {column}=?""",
                    (row["policy"], row["expires_at"],
                     row["consumed_at"] if row["consumed_at"] is not None
                     else int(time.time()) if terminal else None,
                     row["view_verifier"], note_id),
                )
                if old_sessions and kind == "plain":
                    for session in db.execute(
                        "SELECT * FROM note_view_sessions WHERE note_type='plain' AND note_id=?",
                        (note_id,),
                    ):
                        db.execute(
                            """INSERT OR IGNORE INTO publication_view_sessions
                               (token_hash, slug, expires_at) VALUES (?, ?, ?)""",
                            (session["token_hash"], published["slug"], session["expires_at"]),
                        )
                migrated += 1
            elif terminal and row["purged_at"] is None:
                delay = 0
                if old_sessions:
                    session = db.execute(
                        """SELECT MAX(expires_at) AS deadline FROM note_view_sessions
                           WHERE note_type=? AND note_id=?""", (kind, note_id),
                    ).fetchone()
                    delay = session["deadline"] or 0
                db.execute(
                    """INSERT OR IGNORE INTO legacy_pending_deletions
                       (note_type, note_id, delete_after) VALUES (?, ?, ?)""",
                    (kind, note_id, delay),
                )
                pending += 1
            else:
                discarded += 1
        db.execute("DROP TABLE IF EXISTS note_view_sessions")
        db.execute("DROP TABLE note_expirations")
        logger.info(
            "Expiration migration: %d published rules, %d discarded private rules, "
            "%d previously terminal notes pending cleanup", migrated, discarded, pending,
        )

    def consume(self, publication, proof=None, db=None, allow_session=False):
        if db is None:
            with self.store.connection(write=True) as connection:
                return self.consume(publication, proof, connection, allow_session)
        ensure_active(publication)
        if publication.get("expiration_policy") != "once":
            return None
        if publication.get("view_verifier"):
            if not isinstance(proof, str) or not VERIFIER_PATTERN.fullmatch(proof):
                raise PermissionError("Unlock proof required")
            try:
                digest = hashlib.sha256(bytes.fromhex(proof)).hexdigest()
            except ValueError as error:
                raise PermissionError("Invalid unlock proof") from error
            if not hmac.compare_digest(digest, publication["view_verifier"]):
                raise PermissionError("Invalid unlock proof")
        elif proof is not None:
            raise PermissionError("Unexpected unlock proof")
        table, column = TABLES["encrypted" if "note_id" in publication else "plain"]
        identifier = publication["note_id"] if "note_id" in publication else publication["note_title"]
        changed = db.execute(
            f"""UPDATE {table} SET consumed_at=?
               WHERE {column}=? AND consumed_at IS NULL
               AND (expires_at IS NULL OR expires_at>?)""",
            (int(time.time()), identifier, int(time.time())),
        )
        if changed.rowcount != 1:
            raise ExpirationError("Public link already viewed")
        token = secrets.token_urlsafe(32) if allow_session else None
        if token:
            db.execute(
                "INSERT INTO publication_view_sessions (token_hash, slug, expires_at) VALUES (?, ?, ?)",
                (hashlib.sha256(token.encode()).hexdigest(), publication["slug"],
                 int(time.time()) + VIEW_SESSION_SECONDS),
            )
        return token

    def view_session_valid(self, slug, token):
        if not token or len(token) > 200:
            return False
        with self.store.connection() as db:
            return db.execute(
                """SELECT 1 FROM publication_view_sessions
                   WHERE token_hash=? AND slug=? AND expires_at>?""",
                (hashlib.sha256(token.encode()).hexdigest(), slug, int(time.time())),
            ).fetchone() is not None

    @staticmethod
    def delete_orphaned_attachments(ordinary, names):
        if not names:
            return
        from flatnotes.publications import referenced_attachments

        directory = Path(ordinary.storage_path)
        remaining = set()
        try:
            for path in directory.glob("*.md"):
                remaining.update(referenced_attachments(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeError):
            return
        for name in names - remaining:
            path = directory / "attachments" / name
            if path.parent == directory / "attachments":
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass

    def cleanup(self, ordinary, encrypted):
        """Revoke expired shares; remove the note only with explicit opt-in."""
        from flatnotes.publications import referenced_attachments

        reindex = False
        now = int(time.time())
        with self.store.connection(write=True) as db:
            db.execute("DELETE FROM publication_view_sessions WHERE expires_at<=?", (now,))
            for kind, (table, column) in TABLES.items():
                rows = db.execute(
                    f"""SELECT * FROM {table} WHERE consumed_at IS NOT NULL
                       OR (expires_at IS NOT NULL AND expires_at<=?)""", (now,),
                ).fetchall()
                for record in rows:
                    pub = dict(record)
                    slug = pub["slug"]
                    if db.execute(
                        "SELECT 1 FROM publication_view_sessions WHERE slug=?", (slug,),
                    ).fetchone():
                        continue
                    note_id = pub[column]
                    if pub["auto_delete_note"]:
                        try:
                            if kind == "plain":
                                try:
                                    names = referenced_attachments(ordinary.get(note_id).content or "")
                                    ordinary.delete(note_id)
                                except FileNotFoundError:
                                    names = set()
                                self.delete_orphaned_attachments(ordinary, names)
                                reindex = True
                            else:
                                try:
                                    encrypted.delete(note_id)
                                except FileNotFoundError:
                                    pass
                        except (OSError, ValueError):
                            logger.exception("Expiration cleanup will retry %s %s", kind, note_id)
                            continue
                    db.execute(f"DELETE FROM {table} WHERE {column}=?", (note_id,))
            for legacy in db.execute(
                "SELECT * FROM legacy_pending_deletions WHERE delete_after<=?", (now,),
            ).fetchall():
                kind, note_id = legacy["note_type"], legacy["note_id"]
                try:
                    if kind == "plain":
                        try:
                            names = referenced_attachments(ordinary.get(note_id).content or "")
                            ordinary.delete(note_id)
                        except FileNotFoundError:
                            names = set()
                        self.delete_orphaned_attachments(ordinary, names)
                        reindex = True
                    else:
                        try:
                            encrypted.delete(note_id)
                        except FileNotFoundError:
                            pass
                    db.execute(
                        "DELETE FROM legacy_pending_deletions WHERE note_type=? AND note_id=?",
                        (kind, note_id),
                    )
                except (OSError, ValueError):
                    logger.exception("Legacy expiration cleanup will retry %s %s", kind, note_id)
        if reindex:
            ordinary._sync_index_with_retry()

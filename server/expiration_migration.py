"""One-time migration of publication expiration data from flatnotes 6.3."""

import logging
import time

logger = logging.getLogger(__name__)


def migrate_legacy(db, tables):
    has_legacy = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='note_expirations'"
    ).fetchone()
    if not has_legacy:
        return
    old_sessions = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='note_view_sessions'"
    ).fetchone()
    has_purged = any(
        column["name"] == "purged_at"
        for column in db.execute("PRAGMA table_info(note_expirations)")
    )
    migrated = 0
    discarded = 0
    pending = 0
    rows = db.execute("SELECT * FROM note_expirations").fetchall()
    for row in rows:
        kind, note_id = row["note_type"], row["note_id"]
        table, column = tables[kind]
        published = db.execute(
            f"SELECT * FROM {table} WHERE {column}=?", (note_id,)
        ).fetchone()
        # An active private legacy rule is discarded even if its deadline
        # passed while the application was stopped. Only terminal rules
        # already recorded by 6.3 may still trigger pending deletion.
        terminal = row["status"] != "active"
        purged_at = row["purged_at"] if has_purged else None
        if published and purged_at is None:
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
        elif terminal and purged_at is None:
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


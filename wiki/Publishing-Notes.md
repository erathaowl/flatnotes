# Publishing Notes

flatnotes 6.5.0 supports public links for ordinary Markdown and browser-encrypted notes. **Expiration belongs to the public link**, leaving the original note accessible to its owner.

## Configuring a share

Open **Share** for a normal or unlocked protected note, including a new unsaved note. Choose **Private**, **Public: read-only**, or **Public: anyone with the link can edit** for ordinary Markdown notes. Encrypted notes allow read-only public links exclusively. Select a random URL (recommended), a title-derived URL (ordinary notes only), or a custom suffix.

Inside the same dialog, choose **Expiration**: Never (default), After N hours, After N days, or Single view. Single view is available only for read-only links. Durations are limited to 3650 days and each day is 24 hours.

**Automatically delete this note when the share expires** is unchecked by default and is shown only when an expiration exists. When unchecked, the link expires and the original note survives. When checked, cleanup permanently removes the original Markdown or encrypted note after expiration. **Manually unpublishing always preserves the note**, even with auto-delete enabled.

On saved notes, click **Save** to apply the share settings. On new notes, click **Apply** to stage them locally, then Save the note: creation precedes publication. If publication fails, the note remains saved.

The Share action uses the normal foreground color when a live publication exists and is muted when the note is private or the link has expired. On narrow mobile screens, the Share dialog scrolls within the available viewport, and its action buttons stay accessible in a fixed-position footer.

A public `edit` link acts as an editing credential: anyone who obtains the
URL can change the ordinary Markdown content without logging in. Use random
slugs and share such links only with recipients you trust. Public editing does
not grant access to account settings, private search or other private notes.

## Deadline, renewal and deletion

The deadline is computed by the server at publication time and stored in UTC. Changes to the expiration policy or link create a new deadline; editing the note's body or changing an unrelated Share setting leaves the deadline unchanged.

Expired or consumed public links are rejected immediately, typically with HTTP 410 before cleanup and HTTP 404 after removal. The worker runs on startup and approximately every 60 seconds, removing expired publications. Only links with auto-delete enabled remove the underlying note.

While an expired publication record still exists, the same public URL cannot be renewed. Save with a new random slug or choose a different custom suffix. Once cleanup removes the old record, that slug can be reused. A manual Unpublish removes the share metadata without deleting the note.

Auto-delete does not securely erase storage snapshots, backups, files already downloaded or encrypted ciphertext copies. Ordinary attached files are removed conservatively only when not referenced by other notes.

## Known architectural limitation and possible improvement (SEC-02)

The cleanup worker permanently deletes expired publication records. After cleanup, the server forgets their slugs, so a newly created share can reuse an old public URL and make previously distributed links point to new content. This limitation is accepted for the current small/personal deployment; the cleanup behavior is unchanged.

**Possible improvement:** persist retired public slugs in a dedicated SQLite table with a unique slug key and retirement timestamp. Check both active and retired slugs when creating ordinary or encrypted publications, within the same write transaction. Preserve the retired entries indefinitely to guarantee that expired URLs cannot be reactivated. Existing deleted records cannot be reconstructed without historic metadata or backups.

## Single-view ordinary links

The first authorized public content request atomically consumes the link and returns Markdown. Another request cannot retrieve the note through that link. Private owner views and normal search do not consume it. Public attachment URLs listed in the allowlist can use the returned `viewToken` for up to 180 seconds; the token cannot grant another note-content read.

## Single-view encrypted links

The recipient downloads ciphertext and enters the password in the browser. After successful local AES-GCM decryption, the browser derives a separate HMAC-SHA256 unlock proof and submits it to the public claim endpoint. SQLite accepts only the first valid claim before the browser displays plaintext.

Private unlocking via `/e/{id}` does not consume the public link. The note password and encryption key never reach the server. A recipient who has downloaded ciphertext can retain it for offline decryption if they know the password.

## Global sharing configuration

`FLATNOTES_SHARING_ENABLED` (default true) controls public sharing. When disabled, public APIs reject requests and the Share control is hidden, while existing publication metadata remains stored.

There is no separate expiration master switch or default variable. Every new share uses `expiration: none` and `autoDeleteNote: false` until configured.

## Migration from 6.3.0

The persistent SQLite database `.flatnotes-publications.db` receives expiration fields in `publications` and `encrypted_publications`: `expiration_policy`, `expires_at`, `consumed_at`, `auto_delete_note` and `view_verifier`. The `publication_view_sessions` table holds temporary attachment-session hashes.

A one-time transactional migration converts the old `note_expirations` table. Active rules for published notes move to their publication record, preserving deadlines and enabling auto-delete to match the legacy deletion semantics. Active rules for private unpublished notes are discarded while retaining the note. Already-terminal legacy records preserve pending cleanup and active attachment download sessions. Obsolete note-expiration tables are dropped.

Back up the full data directory and SQLite database before upgrading. Downgrading to 6.3.0 requires restoring a pre-migration backup.

## Publication API

Authenticated endpoints: `GET/PUT/DELETE /api/notes/{title}/publication` and `GET/PUT/DELETE /api/encrypted-notes/{id}/publication`. Public endpoints: `GET/PATCH /api/public/notes/{slug}`, `GET /api/public/encrypted-notes/{slug}` and `POST /api/public/encrypted-notes/{slug}/view`.

Example request body:

```json
{
  "slugMode": "random",
  "permission": "read",
  "expiration": "7d",
  "autoDeleteNote": false
}
```

Encrypted single-view publications also require a browser-generated `viewVerifier`. The public claim sends only `proof`, never the password. A response includes `expiresAt` and `expired` when relevant.

See [API Reference](https://github.com/erathaowl/flatnotes/wiki/API-Reference) and [Security and Cryptography](https://github.com/erathaowl/flatnotes/wiki/Security-and-Cryptography).

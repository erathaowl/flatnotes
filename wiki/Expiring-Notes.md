# Expiring Notes

flatnotes 6.2.0 supports optional note-level expiration for both ordinary
Markdown and password-protected notes. The expiration rule belongs to the
note itself, not just its public link. When it expires, private and public
access are both revoked and the active note file is removed by cleanup.

## Configuration

Two environment variables control the feature:

| Variable | Default | Description |
| --- | --- | --- |
| `FLATNOTES_EXPIRATION_ENABLED` | `false` | Enables creation or modification of expiration policies |
| `FLATNOTES_EXPIRATION_DEFAULT` | `none` | Default applied to new notes |

Supported values: `none`, `once`, `1h`, `12h`, `48h`,
`1d`, `7d` or any positive integer followed by `h` or `d`,
up to 3650 days. Each day is exactly 24 hours. Invalid defaults
prevent the application from starting.

Example:

```yaml
environment:
  FLATNOTES_EXPIRATION_ENABLED: "true"
  FLATNOTES_EXPIRATION_DEFAULT: "7d"
```

With the master switch disabled, existing rules **remain enforced** and
users cannot configure new ones. Changing the default affects new notes
only. Existing notes and their deadlines remain unchanged.

## Choosing an expiration

- **Never:** the note remains available until manually deleted.
- **After N hours:** the note expires after the selected number of hours.
- **After N days:** the note expires after N periods of 24 hours.
- **Single view:** only one successful content opening is allowed.

New ordinary notes show the **Expiration** selector in their edit
form; new protected notes show it alongside their password form.
The default comes from the environment. Existing notes can use
the **Expiration** toolbar action while the feature is enabled.

Timing starts when a new note is first saved, or when the owner
saves a changed expiration policy. Normal content edits do not
reset the timer. All deadlines are stored as UTC Unix timestamps
and displayed using the browser's local time zone.

Open **Expiring Notes** in the main menu, or visit
`/expiring`, to see active notes with expiration policies.
Single-view ordinary notes are excluded from global full-text
search, to avoid exposing their contents through search snippets.
Protected-note titles stay encrypted, so this list shows only
their opaque identifiers.

## Single view for ordinary notes

The first authenticated or authorized request for the note's
content consumes the view. This includes the owner's private
`/n/{title}` opening and public `/p/{slug}` openings.
Creating the note and saving its first content do not consume it.

Once consumed, subsequent content requests and edits return
HTTP 410 Gone. The initial response still contains the
Markdown so that the authorized reader can display it.

For published ordinary notes with linked attachments, the initial
view also returns a short-lived, random attachment token. The
browser uses it to load allowlisted attachment resources for
up to three minutes. The token does not permit another note view.
Attachments shared by other notes are preserved.

## Single view for encrypted notes

Protected notes remain end-to-end encrypted in the browser.

1. The server delivers the encrypted envelope. This download
   does **not** consume the single view.
2. The browser derives the encryption key using Argon2id and
   authenticates the decrypted content using AES-256-GCM.
3. The browser derives a separate HMAC-SHA256 unlock proof with
   a domain-separated label containing the note ID.
4. Only a SHA-256 digest of this proof is stored as a verifier in
   SQLite when the one-view policy is created.
5. The browser submits the proof through the dedicated view
   endpoint. SQLite atomically verifies and consumes the view.
6. The browser displays plaintext only after the server accepts
   the claim. Passwords and plaintext never reach the backend.

A wrong password cannot generate the accepted proof. Concurrent
claims produce only one success, whether from an authenticated
or publicly shared encrypted note.

**Limit:** ciphertext downloaded before a successful claim can be
copied and decrypted offline later if the password is known. The
application enforces a single **authorized browser viewing**,
not cryptographic revocation of data already delivered. Similarly,
the initial viewer of an ordinary note can retain its content.

## Server lifecycle and cleanup

Expiration rules are stored in
`FLATNOTES_PATH/.flatnotes-publications.db`, in a separate
`note_expirations` table. The database stores the note type,
opaque ID or ordinary title, policy, deadline, terminal status and,
for protected single-view notes, the proof verifier hash.
No note passwords or decryption keys are stored.

FastAPI checks the lifecycle state on read, edit, publish and
shared-content requests. Expired or consumed notes are rejected
immediately, even before cleanup deletes the file.

Cleanup runs at service startup and periodically (approximately
every 60 seconds). It removes expired `.md` or `.md.enc`
files, revokes publications and updates the Whoosh index.
Single-view ordinary files are kept long enough for their
short-lived attachment token to expire. Terminal records are
retained to distinguish HTTP 410 from a missing note.

Orphaned ordinary attachments referenced by an expired note
are removed conservatively only when no remaining Markdown note
references them. Shared or uncertain files are retained to
avoid accidental deletion.

## Migration, backup and security

Protecting an ordinary note transfers its timed deadline to the
new encrypted note without restarting it. A consumed single-view
note cannot be migrated. Existing notes without a policy remain
unchanged after upgrading from 6.1.0.

Expiration removes active files and publication links. It does
not securely erase old filesystem blocks, snapshots, backups,
downloaded files or copies already in browser memory. Backups
must be managed according to their own retention policy.

The implementation uses SQLite transactions to serialize
concurrent single-view claims. A periodic cleanup retry
handles interrupted deletion operations.

See [Security and Cryptography](https://github.com/erathaowl/flatnotes/wiki/Security-and-Cryptography),
[API Reference](https://github.com/erathaowl/flatnotes/wiki/API-Reference)
and [Operations and Backup](https://github.com/erathaowl/flatnotes/wiki/Operations-and-Backup).

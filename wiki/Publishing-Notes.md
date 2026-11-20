# Publishing Notes

The [erathaowl/flatnotes](https://github.com/erathaowl/flatnotes) fork supports sharing a single note without granting visitors access to the rest of the instance.

## Publish a note

1. Open an ordinary note, or unlock an encrypted note. The Share dialog
   is also available before a new note has been saved.
2. Click **Share**.
3. Choose **Public: read-only** or **Public: anyone with the link can edit**.
4. Choose a public URL suffix:
   - **Random** (recommended): 32 hexadecimal characters generated cryptographically.
   - **Use note title**: lowercase URL slug derived from the title of
     an ordinary note only; encrypted notes never disclose their title
     through public slug generation.
   - **Custom**: your own URL suffix, with letters, digits, and hyphens.
5. On an existing note, click **Save** to apply the setting. For an
   unsaved new note, click **Apply** to stage the setting locally;
   the public link is created only after the note's first **Save**.

Reopen Share to copy the active URL, change permissions, or unpublish.
If the note saves but creating the public link fails, the note remains
saved; reopen Share to retry. A note has one active public link at a time. All slugs are unique and case-insensitive.

Example: `https://notes.example.com/p/my-shared-note`.

## Sharing protected notes

Encrypted notes also support `/p/{slug}`, but the public API sends
ciphertext rather than readable Markdown. A visitor enters the
encryption password into a browser form and decrypts locally.
A public read-only link permits viewing after unlock; a public
editable link permits ciphertext updates after unlock.

For protected notes only **Random** and **Custom** slugs are
available. The **Use note title** option is hidden because the
title is encrypted. When protecting a new ordinary draft whose
staged share choice used a title-based slug, the application
switches that choice to a random slug instead.
Encrypted attachments remain inside the encrypted note envelope.

Both ordinary and encrypted publications are controlled by
`FLATNOTES_SHARING_ENABLED` (default `true`). Setting it to
`false` causes public endpoints to return HTTP 404, hides
the Share controls and retains publication records for later
re-enabling. This flag is enforced by the backend.

See [Encrypted Notes](https://github.com/erathaowl/flatnotes/wiki/Encrypted-Notes)
and [Security and Cryptography](https://github.com/erathaowl/flatnotes/wiki/Security-and-Cryptography).

## Expiration of published notes

Note expiration applies to the source note as well as the
public link. An expired or consumed publication returns HTTP 410
through content APIs, and cleanup later revokes its publication
metadata.

For a public ordinary single-view note, the first content
request claims the view. A temporary attachment token permits
allowlisted files to load for three minutes after that request.
For a public encrypted single-view note, an unlock proof is
required before the view is consumed.

See [Expiring Notes](https://github.com/erathaowl/flatnotes/wiki/Expiring-Notes).

## Public permissions

| Operation | Private note | Published read-only | Published editable |
| --- | --- | --- | --- |
| Read without login | No | Yes | Yes |
| Modify content without login | No | No | Yes |
| Rename/delete without login | No | No | No |
| Publish or change sharing settings without login | No | No | No |
| Browse private search and notes without login | No | No | No |

This selective access guarantee requires instance authentication with `FLATNOTES_AUTH_TYPE=password` or `totp`. With global `none` and `read_only` modes, all notes are already anonymously accessible by design.

**Editable links:** anyone who knows the public link can change the note content without an identity check or attribution. Use a reverse proxy rate limit when exposing anonymous write access on the Internet. Title-derived and custom links can be guessed; a random URL adds resistance to casual discovery but is not a substitute for authentication.

## Link lifecycle

- Unpublishing revokes anonymous access immediately.
- Changing the slug invalidates the previous URL.
- Renaming the note **inside flatnotes** preserves the currently published URL, regardless of how the slug was initially selected.
- Deleting the note inside flatnotes removes its publication metadata.
- If a Markdown file is renamed or removed directly on disk, the old public URL returns a not-found result until the metadata is updated by republishing through the application.

When the selected suffix conflicts with an existing publication, the server returns HTTP 409. An invalid custom suffix returns HTTP 422.

## Concurrent changes

Anonymous users can edit only the Markdown content. The editor sends a content revision alongside the update. If the note has changed since it was loaded, the server responds with HTTP 409 to prevent silent overwriting. Refreshing and merging changes is the visitor's responsibility.

## Attachments

The regular `/attachments/{filename}` API remains authenticated in password/TOTP mode. A published note can load attachments through its own URL:

```text
/api/public/notes/{slug}/attachments/{filename}
```

Only filenames in that note's allowlist can be loaded. Publishing a note records referenced attachments; authenticated owner edits synchronize its allowlist. Anonymous editing cannot authorize an additional private attachment by referencing its name, and anonymous upload is not offered. Deleting a note does not automatically delete uploaded files.

## Metadata and backups

Markdown note content remains in `FLATNOTES_PATH`. Public URL slugs, permission mode (`read` or `edit`), slug mode, and allowed attachment names are stored in SQLite:

```text
/data/.flatnotes-publications.db
```

This file is separate from the rebuildable Whoosh search index in `/data/.flatnotes/`. Back up the publication DB using a SQLite-consistent method for live instances (or stop the container before copying DB files).

## Slugs and security

Slugs consist of 1–80 lowercase ASCII letters, digits or hyphens,
starting and ending with a letter or digit. A random slug consists
of 32 hex characters. Custom slugs are predictable; a public edit
link must be treated as granting write access to anyone possessing
it. No editor identity is attached to anonymous edits.

When a source ordinary note is converted to encryption, its
old public link is revoked. A protected note must be published
again through its own Share dialog.

## API

Authenticated management endpoints:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/notes/{title}/publication` | Read sharing settings |
| `PUT` | `/api/notes/{title}/publication` | Publish or modify sharing |
| `DELETE` | `/api/notes/{title}/publication` | Revoke sharing |

Public endpoints:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/public/notes/{slug}` | Read a published note |
| `PATCH` | `/api/public/notes/{slug}` | Change content if public editing is enabled |
| `GET` | `/api/public/notes/{slug}/attachments/{filename}` | Read an allowed attachment |

The `PATCH` payload contains `newContent` and the `revision` returned by `GET`. The `PUT` payload contains `slugMode`, `permission`, and optional `slug` for a custom suffix. Consult your instance's `/docs` endpoint for the generated OpenAPI schema.

Related: [Environment Variables](https://github.com/erathaowl/flatnotes/wiki/Environment-Variables) and [Image Support](https://github.com/erathaowl/flatnotes/wiki/Image-Support).

# Image Support

## Adding images

When editing a note, add images by:

- Using the editor's **Insert image** button.
- Dragging an image file into the editor.
- Copying and pasting an image into the editor.

The application stores uploaded files in `FLATNOTES_PATH/attachments/` (by default `/data/attachments/` in Docker). It creates this directory on startup if needed.

For authenticated users, attachments are served at `/attachments/{filename}` or `/api/attachments/{filename}`. An uploaded file is independent of the Markdown note: deleting a note does not remove its attachments automatically.

## Images in published notes

Selectively published notes are accessed with `/p/{slug}`. For anonymous visitors, the publication API uses a **note-scoped allowlist**:

```text
/api/public/notes/{slug}/attachments/{filename}
```

Attachments referenced by the note when first published are included in its allowlist. When the authenticated owner changes the note, the allowlist is updated. An anonymous user editing a public note cannot add previously private attachments to the allowlist, and cannot upload new files through the public editor.

A filename absent from the note's allowlist returns HTTP 404. Published attachment access is revoked when the publication is removed.

## Attachments inside encrypted notes

Protected-note attachments follow a different workflow:

1. Unlock the note in the browser, select **Edit** and **Attach file**.
2. The browser reads the file as a data URL and includes it in the
   protected note's encrypted content.
3. **Save** encrypts the note and embedded attachment data together.
4. Open the note later, unlock it and select an attachment to
   download the plaintext locally.

The total embedded attachment limit in the editor is **2 MiB**;
the complete encrypted envelope may not exceed **4 MiB** at the
backend. There is no separate unencrypted attachment API for
protected-note files. Inline pasted images can be embedded as
data URLs in Markdown and encrypted with it.

Before protecting an ordinary note, including a new unsaved draft,
remove or embed plaintext attachment references or externally
hosted images. The Protect dialog blocks recognized external attachment
references. A plain attachment file left on disk is not
automatically encrypted by converting the note itself.

For the complete threat model, see
[Security and Cryptography](https://github.com/erathaowl/flatnotes/wiki/Security-and-Cryptography).

## Backup

Back up `attachments/` for ordinary notes, all `*.md.enc` files
for protected notes and the SQLite publication database
`/data/.flatnotes-publications.db`. A protected file can only
be recovered with its encryption password. See [Publishing Notes](https://github.com/erathaowl/flatnotes/wiki/Publishing-Notes).

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

## Backup

Include the `attachments/` directory in backups. Publication attachment permissions are stored in the SQLite database at `/data/.flatnotes-publications.db`. See [Publishing Notes](https://github.com/erathaowl/flatnotes/wiki/Publishing-Notes).

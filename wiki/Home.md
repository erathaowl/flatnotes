# flatnotes Wiki

Documentation for [erathaowl/flatnotes](https://github.com/erathaowl/flatnotes), a self-hosted Markdown notes application with per-note sharing and optional branding.

## Pages

- [Environment Variables](https://github.com/erathaowl/flatnotes/wiki/Environment-Variables) — Docker configuration, authentication, TOTP, and branding.
- [Docker and Releases](https://github.com/erathaowl/flatnotes/wiki/Docker-and-Releases) — installation, GHCR images, and CI/CD.
- [Publishing Notes](https://github.com/erathaowl/flatnotes/wiki/Publishing-Notes) — share links, access modes, SQLite metadata, attachments, and API.
- [Custom Branding](https://github.com/erathaowl/flatnotes/wiki/Custom-Branding) — custom title, logo, and favicon.
- [Advanced Searching](https://github.com/erathaowl/flatnotes/wiki/Advanced-Searching) — query syntax and search fields.
- [Tagging](https://github.com/erathaowl/flatnotes/wiki/Tagging) — assigning and finding tags.
- [Image Support](https://github.com/erathaowl/flatnotes/wiki/Image-Support) — attachments and public note limitations.
- [Keyboard Shortcuts](https://github.com/erathaowl/flatnotes/wiki/Keyboard-Shortcuts) — editor and navigation shortcuts.

## FAQ

### Where are my notes stored?

As Markdown files in the configured `FLATNOTES_PATH` directory (`/data` in Docker). Your note content is portable.

### Why is there a database?

The fork stores publication settings, public URL slugs, and public attachment permissions in the SQLite file `/data/.flatnotes-publications.db`. Note content remains in Markdown files.

### What is `.flatnotes/`?

It contains the regenerable Whoosh full-text search index. With the application stopped, you can remove this folder and let the application rebuild it at startup. Do not confuse it with `.flatnotes-publications.db`, which must be backed up.

### Can I edit Markdown files externally?

Yes. The search index is synchronized when flatnotes starts and during searches. Public links reference existing note titles; renames or deletions performed directly on disk are not synchronized with publication metadata. An externally renamed note becomes unavailable through its former public link until it is republished.

### Can visitors read only specific notes without logging in?

Yes. Use authentication mode `password` or `totp` and publish selected notes individually through **Share**. Unpublished notes and the private search API still require authentication. The `none` and `read_only` modes are instance-wide and already allow anonymous note access.

### How do read-only and public editing differ?

Published notes default to read-only. The owner can allow anonymous content edits, but visitors cannot rename, delete, or change sharing settings. Anyone who knows an editable link can modify its contents.

### What happens when I change a note's public URL?

The previous link stops working. The owner can unpublish the note at any time. Renaming a note inside flatnotes keeps the current link stable.

### Can a public visitor open every attachment?

No. Public note attachment endpoints use a per-note allowlist. Anonymous edits cannot expose additional private files by adding their names to Markdown. Owner edits can update the allowlist.

### How do I back up my notes?

Preserve the Markdown notes, attachments, and publication SQLite database. For a running application, use a SQLite-consistent backup or stop the container first.

### Is there an API?

Yes. Open `/docs` on your deployed flatnotes instance. The public note endpoints use `/api/public/notes/{slug}`; owner publication management uses `/api/notes/{title}/publication`.

### Are folders supported?

Notes are stored in a flat directory. Use full-text search and hashtags such as `#work` to organize them. Cross-note links use `[[Note Title]]`.

## Documentation source

These pages are maintained under [`wiki/`](https://github.com/erathaowl/flatnotes/tree/develop/wiki) in this repository. The [English README](https://github.com/erathaowl/flatnotes/blob/develop/README.md) and [Italian README](https://github.com/erathaowl/flatnotes/blob/develop/readme-it.md) summarize the application.

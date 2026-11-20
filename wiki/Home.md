# flatnotes Wiki

Complete documentation for
[erathaowl/flatnotes](https://github.com/erathaowl/flatnotes),
a self-hosted Markdown note-taking application with optional
browser-only encryption, selected-note publication, attachments,
full-text search and custom branding.

**Current release:** [v6.1.0](https://github.com/erathaowl/flatnotes/releases/tag/v6.1.0).
[English README](https://github.com/erathaowl/flatnotes/blob/develop/README.md) ·
[README italiano](https://github.com/erathaowl/flatnotes/blob/develop/readme-it.md) ·
[GitHub Actions](https://github.com/erathaowl/flatnotes/actions)

## Start here

1. [Docker and Releases](https://github.com/erathaowl/flatnotes/wiki/Docker-and-Releases):
   install with Docker Compose, wheel or an application archive.
2. [Environment Variables](https://github.com/erathaowl/flatnotes/wiki/Environment-Variables):
   authentication, optional encryption, password policies and sharing flags.
3. [Notes and Editor](https://github.com/erathaowl/flatnotes/wiki/Notes-and-Editor):
   create, edit, search, protect and export notes.
4. [Encrypted Notes](https://github.com/erathaowl/flatnotes/wiki/Encrypted-Notes):
   protect an existing note, unlock, share, attach files and delete.
5. [Publishing Notes](https://github.com/erathaowl/flatnotes/wiki/Publishing-Notes):
   publish read-only or anonymous-editable links.
6. [Operations and Backup](https://github.com/erathaowl/flatnotes/wiki/Operations-and-Backup):
   upgrade safely and preserve persistent files.

## Reference and advanced topics

| Page | Description |
| --- | --- |
| [Security and Cryptography](https://github.com/erathaowl/flatnotes/wiki/Security-and-Cryptography) | Threat model, key hierarchy, Argon2id, AES-GCM and encrypted envelope |
| [API Reference](https://github.com/erathaowl/flatnotes/wiki/API-Reference) | REST routes for ordinary, public and encrypted notes |
| [Image Support](https://github.com/erathaowl/flatnotes/wiki/Image-Support) | Ordinary attachments, encrypted embedded files and limits |
| [Advanced Searching](https://github.com/erathaowl/flatnotes/wiki/Advanced-Searching) | Whoosh query syntax and fields |
| [Tagging](https://github.com/erathaowl/flatnotes/wiki/Tagging) | Hashtags, filtering and encrypted-note limitations |
| [Keyboard Shortcuts](https://github.com/erathaowl/flatnotes/wiki/Keyboard-Shortcuts) | Navigation and editor key combinations |
| [Custom Branding](https://github.com/erathaowl/flatnotes/wiki/Custom-Branding) | Site title, logo and favicon |
| [Troubleshooting](https://github.com/erathaowl/flatnotes/wiki/Troubleshooting) | Direct URLs, browser crypto, passwords, sharing and saves |

## How the application stores notes

| Kind | Storage | Visibility to server | Search |
| --- | --- | --- | --- |
| Ordinary note | `FLATNOTES_PATH/{title}.md` | Title and plaintext content | Indexed by Whoosh |
| Protected note | `FLATNOTES_PATH/{random-id}.md.enc` | Opaque ID, ciphertext and timestamps | Excluded |
| Ordinary attachments | `FLATNOTES_PATH/attachments/` | Plaintext files | Not full-text indexed |
| Encrypted attachments | Embedded in the `.md.enc` envelope | Ciphertext only | Excluded |
| Public link metadata | `FLATNOTES_PATH/.flatnotes-publications.db` | Slug, note reference, access rules | Not the note content |

The `.flatnotes/` folder contains the regenerable Whoosh index.
The publication database must be backed up; it is a separate
persistent SQLite file.

## URLs and access

- `/n/{title}`: ordinary note.
- `/encrypted`: list and manage protected notes.
- `/e/{id}`: private protected note, unlocked with a separate password.
- `/p/{slug}`: publicly shared note, with read or edit permission.
- `/note/{title}`: legacy route, redirected in the client.

With `password` or `totp` authentication, only explicitly published
notes can be accessed anonymously. Publicly shared encrypted notes
still require a note password to decrypt locally.

## Frequently asked questions

**Can I recover a protected note's password?** No. flatnotes
does not know or store the note password. An account-authorized user
can delete the ciphertext through `/encrypted` without unlocking it.

**Is a protected note searchable?** No. Its title, Markdown and tags
are encrypted. The list displays opaque identifiers.

**Can I change the password-complexity policy?** Yes. Set the
environment variables for minimum length and minimum number of
character categories; they govern new passwords in the browser.
Existing encrypted notes continue to unlock with their original
passwords.

**Can I share protected notes?** Yes, when sharing is enabled.
Visitors receive ciphertext through `/p/{slug}` and enter
the encryption password into the browser.

**Does locking a note protect historical plaintext?** A note
originally stored as `.md` may still exist in old backups,
snapshots or deleted disk blocks. Existing encrypted files remain
encrypted while stored.

**Can I restore from backup?** Yes, if you preserve `.md`,
`.md.enc`, ordinary attachments, the SQLite publication database
and the note passwords needed for encrypted data.

## Documentation maintenance

The authoritative Markdown source for these pages lives in
[`wiki/` on develop](https://github.com/erathaowl/flatnotes/tree/develop/wiki).
The [Publish Wiki workflow](https://github.com/erathaowl/flatnotes/actions/workflows/publish-wiki.yml)
synchronizes the repository directory with this GitHub Wiki.

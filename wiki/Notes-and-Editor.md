# Notes, Editor and Navigation

This guide describes the everyday workflows available in
[erathaowl/flatnotes](https://github.com/erathaowl/flatnotes).

## Navigating the application

| URL | Purpose | Data storage |
| --- | --- | --- |
| `/` | Home, quick-access notes and search | Whoosh for ordinary notes |
| `/new` | Create an ordinary Markdown note | `{title}.md` |
| `/n/{title}` | View or edit an ordinary note | `{title}.md` |
| `/note/{title}` | Legacy URL, redirected by the Vue router | Ordinary note |
| `/encrypted` | List protected note identifiers and delete them | `{id}.md.enc` |
| `/e/new` | Create a protected note | Created on first successful save |
| `/e/{id}` | Unlock, view or edit a protected note | `{id}.md.enc` |
| `/p/{slug}` | Public link, for Markdown or encrypted notes | Depends on source note |

Direct URL navigation and refresh are supported, including `/encrypted`.
Private routes require normal application authentication in
`password` and `totp` modes. The public route uses its own access rules.

## Ordinary Markdown notes

1. Select **New Note**, enter a title in the *Title* field and write Markdown
   or use the WYSIWYG editor.
2. Save the note. It is stored as a `.md` file in `FLATNOTES_PATH`.
3. Open it later from search, recent notes or a direct `/n/{title}` link.
4. Use **Edit** to change the title or body. Save or leave edit mode.
5. Use **Share** to publish selectively, **Protect** to encrypt a saved
   ordinary note, or **Delete** to remove it.

The **Protect** action appears on a saved ordinary note in view mode
when `FLATNOTES_ENCRYPTION_ENABLED=true`. An unsaved draft must be handled
before protection. Protection is a conversion, not a server-side file
permission: the browser encrypts the title and body before sending
ciphertext to the server. See [Encrypted Notes](https://github.com/erathaowl/flatnotes/wiki/Encrypted-Notes).

Draft recovery exists for the ordinary editor. These local browser drafts
are not an encrypted-note backup. Protected-note editing intentionally does
not use plaintext draft persistence. Save or export before leaving
an unlocked edit session to avoid losing unsaved edits.

## Protected notes

Select **New Protected** or visit **Protected Notes** and select
**New protected note**. The initial page requests a protection password,
then opens the editor. The note file is not stored until **Save** succeeds
with a nonempty title.

An existing protected note is listed by a random identifier, because its
human-readable title is encrypted. Select the identifier, enter the password
in the browser, and choose **Unlock**. The toolbar provides **Lock**,
**Share**, **Export Markdown**, **Delete**, **Edit**, **Attach file**,
**Cancel** and **Save** as applicable.

- **Lock** clears the unlocked view and terminates the cryptographic worker.
  Reloading or revisiting the page requires the password again.
- **Save** re-encrypts the title, Markdown and encrypted attachments locally.
  It checks the current server revision to avoid overwriting newer changes.
- **Export Markdown** downloads plaintext directly in the browser. Protect
  exported files separately; they are no longer encrypted.
- **Attach file** embeds the file in the encrypted note envelope, subject
  to the 2 MiB total attachment limit.
- **Delete** permanently removes the encrypted note and its publication.
- If the password has been lost, open `/encrypted` and use the red deletion
  icon next to the opaque identifier. Account authorization is still needed.

The password cannot be recovered. Automatic **Remove protection** is not
implemented because writing a plaintext `.md` file on the server would
contradict the ciphertext-only requirement.

## Expiration controls

When `FLATNOTES_EXPIRATION_ENABLED=true`, new ordinary notes
and new encrypted notes offer an **Expiration** selector. On
existing unlocked notes, the **Expiration** toolbar action
opens the setting dialog. Available choices are never,
a positive number of hours, a positive number of days or
single view.

The main Menu includes **Expiring Notes**, opening `/expiring`.
This page lists active timed notes and single-view notes; encrypted
notes remain identified by their opaque IDs.

A timed note expires without resetting its timer on content edits.
A single-view note is consumed by the first content opening,
including the owner. Plaintext single-view notes are intentionally
excluded from full-text search.

See [Expiring Notes](https://github.com/erathaowl/flatnotes/wiki/Expiring-Notes).

## Search, tags and links

Ordinary notes are indexed by Whoosh and can be found by title, content,
tags and last-modified date. Use `#work` in Markdown to tag a note and
`[[Another Note]]` to link to it. Tags are case-insensitive.

Encrypted titles, tags and Markdown are excluded from server-side search.
The protected-notes list shows identifiers rather than decrypted titles.

See [Advanced Searching](https://github.com/erathaowl/flatnotes/wiki/Advanced-Searching) and [Tagging](https://github.com/erathaowl/flatnotes/wiki/Tagging).

## Images and attachments

Ordinary notes upload attachments to `FLATNOTES_PATH/attachments/`.
Published ordinary notes can expose only the attachments explicitly
allowlisted for that publication.

Protected notes can embed images as data URLs; arbitrary files are bundled
inside the encrypted envelope and downloaded after browser-side decryption.
The server-side attachment API cannot be used for plaintext uploads from
the protected editor. See [Image Support](https://github.com/erathaowl/flatnotes/wiki/Image-Support).

## Keyboard use and mobile layout

The title input occupies its own row above the editor commands on narrow
screens, with a muted italic *Title* placeholder. The toolbar wraps on
smaller devices and uses matching light outline icons.

Consult [Keyboard Shortcuts](https://github.com/erathaowl/flatnotes/wiki/Keyboard-Shortcuts) for the available
navigation and editor shortcuts. Browser secure-context requirements still
apply to cryptography on phones and tablets.

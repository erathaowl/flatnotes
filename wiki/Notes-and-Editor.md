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

## Shared note header and controls

Both note types use the same responsive title field and **Edit** toggle. The **Share** button opens one modal containing public access, URL, expiration and optional auto-delete settings. Its icon and label are bright for an active publication and muted for a private or expired link. **Delete** is red. A protected note also exposes **Lock**, which confirms before discarding unsaved edits.

For a new note, Share stages settings locally. Saving the note creates it first and then attempts to publish the configured link. A failed publication leaves the saved note intact. On a saved note, updating Share applies immediately.

**Protect** can encrypt a newly created ordinary draft or unsaved edits directly in the browser, without an intermediate plaintext upload. Its existing source publication is revoked when converting a saved Markdown note.

See [Publishing Notes](https://github.com/erathaowl/flatnotes/wiki/Publishing-Notes).


## Ordinary Markdown notes

1. Select **New Note**, enter a title in the *Title* field and write Markdown
   or use the WYSIWYG editor.
2. Save the note. It is stored as a `.md` file in `FLATNOTES_PATH`.
3. Open it later from search, recent notes or a direct `/n/{title}` link.
4. Use **Edit** to change the title or body. Save or leave edit mode.
5. Use **Share** to publish selectively, **Protect** to encrypt the
   current note, or **Delete** to remove it.

**Protect** is available in both viewing and editing modes when
`FLATNOTES_ENCRYPTION_ENABLED=true` and writing is allowed. It also
works for an unsaved new note: the browser encrypts the current title
and Markdown, and the first server-side copy is ciphertext. On an
existing note with unsaved edits, protection encrypts those edits
directly and replaces the original plaintext file only after a
successful encryption and conflict check. Any previous publication
of that original note is revoked.

References to external images and plaintext attachment paths must
be removed or embedded before protection. Protect is conversion to
a separate encrypted note, rather than an access-control flag on a
plaintext note. See [Encrypted Notes](https://github.com/erathaowl/flatnotes/wiki/Encrypted-Notes).

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

## Expiring public links

Expiration is available exclusively inside **Share**, with Never, hours, days and read-only Single view modes. Owner access and search are unaffected by public-link expiration. The original note is deleted only if the user explicitly selects **Automatically delete this note when the share expires**.

The former standalone Expiration button, per-note expiration API and expired-notes page are removed. See [Publishing Notes](https://github.com/erathaowl/flatnotes/wiki/Publishing-Notes).


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

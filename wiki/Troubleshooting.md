# Troubleshooting

Use this checklist for flatnotes 6.3.0. Avoid sharing passwords,
authenticated tokens, or decrypted note contents when reporting bugs.

## Refreshing `/encrypted` shows JSON 404

The application uses Vue history-mode routes and needs FastAPI (or
your reverse proxy) to serve the frontend shell for direct navigation.
The backend in 6.3.0 registers `/encrypted` as a page URL.

If you still receive `{"detail":"Not Found"}`, verify that your
container really runs the updated image and that the reverse proxy
is forwarding the route to flatnotes, rather than to another app.
`:master` and `:v6.3.0` are separate image tags.

## Encryption does not work from a phone

Web Crypto and its associated APIs require a secure browser
context. Open flatnotes via HTTPS on mobile or another remote
device. HTTP on a private LAN address is typically insufficient.
`http://localhost` is a browser exception only for the local
device itself.

Check that your reverse proxy serves the application and its
bundled JavaScript, Web Worker and WebAssembly assets from the
same origin. A restrictive external CSP might block those assets.

## “Incorrect password or damaged encrypted note”

The browser cannot unlock the wrapped data key or authenticate
the encrypted payload. Check the password, the correct note link
and the integrity of the backed-up `.md.enc` file.

The server does not possess a recovery key. If the password is
lost, an authenticated user can still delete the opaque note
from `/encrypted`, but cannot recover its contents.

## Protected note cannot be saved

- Give the note a nonempty title. The *Title* placeholder appears
  above the toolbar, and a missing-title error appears under it.
- Check `FLATNOTES_ENCRYPTION_ENABLED=true` for new saves.
- Check that the total encrypted envelope is below 4 MiB and
  embedded attachments total at most 2 MiB.
- HTTP 409 means the ciphertext revision changed, or the new
  note ID already exists. Avoid overwriting edits from another tab.
- HTTP 401/403 indicates an authentication or write-permission issue.
- Update to a build that includes the fix for Vue reactive
  attachment proxies before troubleshooting missing network requests.

The encrypted editor never sends plaintext Markdown or the
protection password through its save API.

## Cannot protect an ordinary note

- Select **Protect** from the ordinary editor. It works with a new draft and with an existing note, including unsaved edits. A new draft is encrypted without first saving a plaintext `.md` file on the server.
- Ensure the feature flag allows encryption and the account can edit.
- Remove or embed plaintext external attachments; conversion blocks
  the recognized external attachment patterns.
- The protection password must satisfy the browser's configured
  length and character-category requirements.
- For an existing note, HTTP 409 indicates the underlying Markdown file changed after it was opened. Reload before converting. For an unsaved draft, confirm that the title is present and the current editor content is available.

Old plaintext data may remain in backups or snapshots even after a
successful conversion.

## New note: Share or Expiration settings appear unchanged

For a new ordinary or encrypted note, both buttons open a modal.
**Apply** in Share and **Save** in Expiration stage changes locally.
The note must then be saved with its own **Save** button.
A new encrypted note does not exist on the server before that save,
so the expiration modal makes no API request until then.

If saving the note succeeds but creating the public link fails,
the note remains stored. Open Share and retry. The active-state
button reflects whether the publication succeeded.

## Public sharing stopped working

Check `FLATNOTES_SHARING_ENABLED`, the note's Share settings
and its public slug. Revocation or slug changes invalidate the old
link. For protected notes, the recipient also needs the encryption
password delivered separately from the URL.

A public edit link permits anonymous modification and should be
handled as a bearer capability. Avoid predictable custom slugs
for sensitive sharing.

## Changes to the password policy

The two policy variables affect the **creation** of new protection
passwords, including converting an ordinary note. They do not
change existing cryptographic envelopes, and unlocking a previously
encrypted note does not revalidate the password against new rules.

The minimum character-category value is 0–4, and the minimum
length is 0–1024. A value of 0 disables the corresponding policy
check, though the user still must enter a nonempty password.

## Expiring notes and HTTP 410

HTTP 410 Gone indicates that a timed note expired or a
single-view note was already consumed. The server will reject
all further content requests even if the file has not yet
been removed by the periodic cleanup.

The first opening of an ordinary one-view note, including
by its owner, consumes the view. For protected one-view notes,
a correct password is needed to generate the browser proof
before the server consumes it. An incorrect password does not
consume the view.

If a note no longer appears in global search, check
`/expiring`: ordinary single-view notes are intentionally
excluded from Whoosh. If policies are no longer editable,
check `FLATNOTES_EXPIRATION_ENABLED`; disabling this
switch does not cancel previously configured expirations.

See [Expiring Notes](https://github.com/erathaowl/flatnotes/wiki/Expiring-Notes).

## TOTP login fails

Account TOTP is independent from protected-note passwords.
Check `FLATNOTES_TOTP_KEY`, device time synchronization and that
the current six-digit code is entered with the account password
in the login UI. Startup logs include the TOTP enrollment key:
restrict access to those logs.

## Finding documentation and reports

- [Environment Variables](https://github.com/erathaowl/flatnotes/wiki/Environment-Variables)
- [Notes and Editor](https://github.com/erathaowl/flatnotes/wiki/Notes-and-Editor)
- [Encrypted Notes](https://github.com/erathaowl/flatnotes/wiki/Encrypted-Notes)
- [API Reference](https://github.com/erathaowl/flatnotes/wiki/API-Reference)
- [Operations and Backup](https://github.com/erathaowl/flatnotes/wiki/Operations-and-Backup)

For reproducible bug reports, include the deployed version/tag,
browser platform, operation performed, and HTTP status codes.
Exclude secrets and note plaintext.

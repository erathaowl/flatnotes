# Troubleshooting

Use this checklist for flatnotes 6.4.0. Avoid sharing passwords,
authenticated tokens, or decrypted note contents when reporting bugs.

## Refreshing `/encrypted` shows JSON 404

The application uses Vue history-mode routes and needs FastAPI (or
your reverse proxy) to serve the frontend shell for direct navigation.
The backend in 6.4.0 registers `/encrypted` as a page URL.

If you still receive `{"detail":"Not Found"}`, verify that your
container really runs the updated image and that the reverse proxy
is forwarding the route to flatnotes, rather than to another app.
`:master` and `:v6.4.0` are separate image tags.

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

## New note: Share or expiration settings do not appear immediately

For a new ordinary or encrypted note, the Share modal stages its access level, URL, expiration and auto-delete settings locally using **Apply**. Save the **note itself** to create the publication and start the timer. A publication failure leaves the note intact; reopen Share to retry.

Existing notes apply Share changes when you click Save. The former standalone Expiration modal and expired-notes page have been removed.


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

## Public links and HTTP 410

HTTP 410 on a public link indicates its time limit expired or its single public view was consumed. Cleanup later removes the publication; the link may then return HTTP 404. The original note remains accessible privately unless **Automatically delete this note when the share expires** was selected.

Opening the private note does not consume its public link. The first public single-view Markdown response includes an attachment token valid for up to 180 seconds. Encrypted single-view links require successful browser decryption followed by a valid unlock proof.

No expiration-specific environment variables are required. Configure expiration from Share. A failed publication can be retried without deleting the saved note.

See [Publishing Notes](https://github.com/erathaowl/flatnotes/wiki/Publishing-Notes).


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

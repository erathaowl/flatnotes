# Troubleshooting

Use this checklist for flatnotes 6.1.0. Avoid sharing passwords,
authenticated tokens, or decrypted note contents when reporting bugs.

## Refreshing `/encrypted` shows JSON 404

The application uses Vue history-mode routes and needs FastAPI (or
your reverse proxy) to serve the frontend shell for direct navigation.
The backend in 6.1.0 registers `/encrypted` as a page URL.

If you still receive `{"detail":"Not Found"}`, verify that your
container really runs the updated image and that the reverse proxy
is forwarding the route to flatnotes, rather than to another app.
`:develop` and `:v6.1.0` are separate image tags.

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

- Save it first, leave Edit mode, and select **Protect**.
- Ensure the feature flag allows encryption and the account can edit.
- Remove or embed plaintext external attachments; conversion blocks
  the recognized external attachment patterns.
- The protection password must satisfy the browser's configured
  length and character-category requirements.
- If the original note changed during conversion, the API responds
  with HTTP 409 to prevent deleting a newer revision.

Old plaintext data may remain in backups or snapshots even after a
successful conversion.

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

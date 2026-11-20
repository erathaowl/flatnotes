# Encrypted Notes

This fork supports password-protected notes whose encryption and decryption
take place exclusively in the browser. All encrypted-note API payloads and
stored files remain ciphertext.

## Enabling encryption

```yaml
environment:
  FLATNOTES_ENCRYPTION_ENABLED: "true"
  FLATNOTES_SHARING_ENABLED: "true"
```

Encryption is disabled by default. Disabling it later prevents new encryption
and protected-note updates but preserves the ability to unlock existing
protected notes. Sharing defaults to enabled; disabling it immediately
suspends public access without erasing publication settings.

## Password requirements

The administrator can configure the minimum password length with
`FLATNOTES_ENCRYPTION_PASSWORD_MIN_LENGTH` (default `12`, permitted 0–1024;
`0` disables the length requirement), and the minimum number of character
types with `FLATNOTES_ENCRYPTION_PASSWORD_MIN_CLASSES` (default `0`,
permitted 0–4). Types are lowercase letters, uppercase letters, numbers
and symbols. For example, `3` means three types out of four.

The browser applies this policy only when protecting or creating a note.
The server sends the settings through `/api/config` without receiving
the user's protection password. Existing encrypted notes remain
unlockable after a policy change.

An authenticated user can permanently delete a protected note from the
`/encrypted` list without its encryption password. The confirmation
dialog warns that deleted ciphertext cannot be recovered.

## URLs

| Type | Route |
| --- | --- |
| Normal Markdown note | `/n/{title}` |
| Publicly shared note | `/p/{slug}` |
| Encrypted protected note | `/e/{id}` |

The legacy `/note/{title}` route redirects in the browser to `/n/{title}`.
Protected note identifiers are randomly generated opaque 128-bit values.
Encrypted notes that are published also have a public `/p/{slug}` link,
and the browser prompts for a password before rendering the content.

Passwords are entered in browser forms. They are never passed by URL query
string or fragment. The password is never sent in an encrypted-note API
request.

## Cryptography

- Password-based KDF: **Argon2id**, 64 MiB, three iterations, parallelism 1.
- Password salt: random 128-bit per note.
- Encrypted content key: 256-bit random per-note key, wrapped with AES-256-GCM.
- Note contents: AES-256-GCM with a random 96-bit nonce and 128-bit tag.
- AES: browser Web Crypto API. Argon2id: bundled `hash-wasm` WebAssembly,
  executed in a Web Worker.
- Associated authenticated data binds wrapped keys and ciphertext to the
  note ID and file-format version.

The envelope is a versioned JSON serialization of ciphertext and the
cryptographic header, stored in `/data/{id}.md.enc`. The header contains
KDF parameters, salt, nonces and wrapped key; the encrypted payload contains
the title and Markdown content. The server does not inspect the encrypted
payload and does not derive keys or decrypt it.

Each edit produces fresh AES-GCM nonces. The browser retains the nonextractable
data key only during the unlocked session. Locking or closing the page
terminates the Web Worker. Changing a browser session requires the password
again.

## Storage, notes and attachments

- Encrypted files are excluded from Whoosh indexing.
- Their titles and tags are not available in server-side search.
- The protected note list displays opaque identifiers while locked.
- Images can be embedded as data URLs and encrypted with the note.
- Other attachments are stored inside the encrypted note envelope as browser
  data URLs, with a combined 2 MiB attachment limit. Files are downloaded and
  decrypted only by the browser.
- Normal attachments and external images must be removed or embedded
  before protecting an existing plain note.
- The application does not upload unencrypted attachments from the
  protected-note editor.
- The password cannot be recovered. The server has no master decryption key.

An unlocked note can be exported as a local Markdown file. An automatic
"remove protection" action is intentionally absent: writing plaintext
Markdown back to the server would violate the ciphertext-only requirement.

Converting an existing `.md` file to `.md.enc` removes the active plaintext
file and invalidates its previous publication. It cannot guarantee erasure
of historical plaintext from backups, filesystem snapshots, browser caches,
or deleted search-index blocks. For previously sensitive plain notes,
review historic backups separately.

## Public encrypted sharing

Use **Share** in an unlocked protected note. The server saves only the
opaque note ID, chosen link suffix and `read`/`edit` permission.
A public viewer downloads ciphertext, requests a local password and
decrypts it in the browser. Anonymous editing, when explicitly enabled,
uploads only new encrypted bytes.

For encrypted notes, choose **Random** or **Custom** public slugs.
Generating a slug from the decrypted title is deliberately disabled:
it would disclose title information to the server.

Publication settings survive disabling the sharing feature flag.
Anonymous public routes return HTTP 404 while sharing is disabled.

## Threat model and limitations

The server can learn that a protected note exists, when it was accessed
or modified, its ciphertext length, and whether it was published.
It cannot extract the content or title from ciphertext without the
password. Offline guessing remains possible against stolen ciphertext:
strong unique passwords are essential.

Browser execution relies on trusted JavaScript supplied by the server.
A compromised server that serves modified application scripts can
capture keys or plaintext at the browser boundary. Use HTTPS, trusted
software updates, and up-to-date browsers.

The Argon2id WASM bundle must be served from the same origin as the app.
An encrypted-note page uses restrictive CSP rules, including blocking
external images and frames. Encrypted plaintext drafts are not written to
localStorage or sessionStorage.

## API

Authenticated endpoints include `GET /api/encrypted-notes`,
`GET/PUT/DELETE /api/encrypted-notes/{id}`, and
`POST /api/encrypted-notes/protect/{title}/{id}`.
GET returns ciphertext. PUT requires an `X-Revision` checksum for
optimistic concurrency, or `*` when creating a new note.

Encrypted publication management uses
`/api/encrypted-notes/{id}/publication`.
Anonymous ciphertext endpoints use `/api/public/encrypted-notes/{slug}`,
return ciphertext and accept writes only for explicitly editable links.

See the [environment reference](https://github.com/erathaowl/flatnotes/wiki/Environment-Variables)
and the [README](https://github.com/erathaowl/flatnotes/blob/develop/README.md).

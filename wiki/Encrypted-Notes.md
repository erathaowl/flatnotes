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

## Create, protect and unlock notes

**Create a new protected note:** choose **New Protected** in the
navigation bar (or open `/encrypted` and select **New protected note**).
Enter and confirm the protection password, then provide a title and
content in the editor. The file is created only when the first
**Save** succeeds. The filename uses a random 128-bit ID.

**Protect an ordinary note:** choose **Protect** from an ordinary
note's toolbar, in Edit or view mode. This includes new unsaved notes
and previously saved notes with current unsaved changes. The browser
encrypts the title and the *current editor content* directly, with
no intermediate plaintext save. For a new draft, this creates a new
encrypted file without ever creating a plaintext note on the server.
For an existing note, the server checks the original file's
modification time, writes ciphertext, removes the original `.md`
file, revokes its old publication and updates the search index.
Before conversion, remove or embed external plaintext attachments.
Any old backups or snapshots may still contain plaintext.

**Unlock:** navigate to `/e/{id}`, enter the protection password
in the browser prompt and choose **Unlock**. The browser downloads
ciphertext and derives its own decryption key. The password never
appears in the URL or encrypted-note API.

**Edit and lock:** once unlocked, choose **Edit**, modify the title,
Markdown or attachments, and save. **Lock** clears the active
browser view and closes the worker, requiring a password next time.
The editor uses outline icons and puts the title on its own row
above the commands on mobile screens.

**Delete without a password:** choose **Protected Notes** from the
menu, locate the opaque ID on `/encrypted`, select its red
Delete icon and confirm. The encrypted file and publication record
are removed by the account-authorized operation. The encryption
password is not needed to delete ciphertext.

## Public-link expiration and single-view encrypted sharing

Encrypted notes support public-link expiration through **Share**. Its Expiration selector offers Never, hours, days and Single view (read-only). Auto-delete is unchecked by default. When selected, the original encrypted note is deleted when the public link expires; otherwise it survives privately.

For a single-view encrypted link, the browser first authenticates and decrypts ciphertext. Then it submits an independent unlock proof, derived from the note's key material, to the public claim endpoint. SQLite grants only the first successful public claim. Private unlocking via `/e/{id}` does not consume a view.

The server never receives plaintext, the protection password or the data key. A downloaded encrypted file may be retained and decrypted offline by a recipient who knows the password.

### Shared editor and pre-save sharing

Both encrypted and ordinary notes use the same toolbar and Edit toggle. Share can stage publication settings on an unsaved encrypted note. The first Save creates ciphertext; afterward the client attempts to create the public link and its expiration. A failure to publish does not discard the encrypted note.

The standalone Expiration action and separate modal have been removed. See [Publishing Notes](https://github.com/erathaowl/flatnotes/wiki/Publishing-Notes).


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

## What is stored and what is not

The format version 1 envelope is a **JSON serialization**, with
fields for `version`, `noteId`, Argon2id parameters, the random
salt, a wrapped data key, a data nonce and ciphertext. The server
has no decryption key or plaintext title.

- A random note ID is visible to the server and used in the filename.
- An encrypted file has a **4 MiB** maximum size.
- Normal Whoosh search excludes encrypted titles and Markdown.
- The browser's unlocked editor can show decrypted text; the
  plaintext is not persisted in the ordinary draft store.
- All encrypted files and their required passwords must be preserved
  when migrating or backing up an instance.

For the exact envelope and threat model, see
[Security and Cryptography](https://github.com/erathaowl/flatnotes/wiki/Security-and-Cryptography).

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
opaque note ID, chosen link suffix and read-only access.
A public viewer downloads ciphertext, requests a local password and
decrypts it in the browser. Public encrypted notes cannot be edited by link holders.
Existing encrypted publications previously configured with edit permission
are migrated to read-only without changing their URLs.

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

## Recovery, compatibility and current limitations

- **Password recovery:** not available. Deleting a note without its
  password is possible, but decrypting it is not.
- **Change password:** not implemented in 6.4.0.
- **Remove protection:** not implemented; exporting unlocked Markdown
  produces a local plaintext copy instead.
- **Password policy:** affects newly created protection passwords,
  not the ability to unlock existing notes after configuration changes.
- **Mobile compatibility:** requires HTTPS when accessing the app
  from another phone or machine; Web Crypto and WebAssembly run
  inside the browser.
- **Historic plaintext:** protecting a previous ordinary note
  cannot securely erase snapshots, old backups or disk remnants.

## API

Authenticated endpoints include `GET /api/encrypted-notes`,
`GET/PUT/DELETE /api/encrypted-notes/{id}`, and
`POST /api/encrypted-notes/protect/{title}/{id}`.
GET returns ciphertext. PUT requires an `X-Revision` checksum for
optimistic concurrency, or `*` when creating a new note.

Encrypted publication management uses
`/api/encrypted-notes/{id}/publication`.
Anonymous ciphertext endpoints use `/api/public/encrypted-notes/{slug}`,
return ciphertext in read-only mode. The public PUT endpoint is unavailable
(HTTP 405); only the private authenticated PUT endpoint can modify a protected note.

See the [environment reference](https://github.com/erathaowl/flatnotes/wiki/Environment-Variables)
and the [README](https://github.com/erathaowl/flatnotes/blob/master/README.md).

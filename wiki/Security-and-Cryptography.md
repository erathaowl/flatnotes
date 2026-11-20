# Security Model and Cryptography

This document describes the implemented security boundary for protected
notes in flatnotes 6.1.0. It is a technical design reference, not a formal
third-party security audit.

## Trust boundary

The browser receives encrypted note bytes over HTTPS and performs all
password-based key derivation, encryption and decryption within its own
Web Worker. FastAPI stores opaque bytes, note identifiers, revisions and
publication permissions; it has no routine that can decrypt an encrypted
note and never receives that note's decryption password.

A protected note's **title, Markdown, tags and embedded attachments**
are encrypted. The server can still observe ciphertext length, note ID,
modification time, requests, client IP addresses and public sharing state.

**Critical limitation:** the application server delivers the JavaScript
that executes in the browser. A compromised server or malicious
application update can supply code that captures plaintext or passwords.
Client-side cryptography does not protect against untrusted client code
delivered by the server.

## Version 1 envelope

Protected notes are stored as UTF-8 serialized JSON, named
`{32-hex-character-id}.md.enc` under `FLATNOTES_PATH`.
They are not binary-serialized files.

Illustrative envelope structure (placeholders are not valid ciphertext):

```json
{
  "version": 1,
  "noteId": "a1b2c3d4e5f60123456789abcdef0123",
  "kdf": {
    "name": "argon2id",
    "memorySize": 65536,
    "iterations": 3,
    "parallelism": 1,
    "salt": "<base64>"
  },
  "wrappedKey": {
    "nonce": "<base64>",
    "ciphertext": "<base64>"
  },
  "data": {
    "nonce": "<base64>",
    "ciphertext": "<base64>"
  }
}
```

The `data` ciphertext contains a JSON object with `title`, `content` and
`attachments`. These fields are never included in the unencrypted header.

### Key derivation and encryption

| Item | Implemented choice |
| --- | --- |
| Password KDF | Argon2id via bundled `hash-wasm` |
| Memory | 65,536 KiB (64 MiB) |
| Iterations / parallelism | 3 / 1 |
| Random salt | 16 bytes, per note |
| Derived wrapping key | 32 bytes (256 bits) |
| Data encryption key | Fresh random 32 bytes, per note |
| Data and key wrapping | AES-256-GCM using Web Crypto |
| Nonces | Random 12 bytes per AES-GCM encryption |
| Authentication | AES-GCM 128-bit tag |
| Randomness | `crypto.getRandomValues()` |
| Authenticated associated data | `flatnotes:key:v1:{id}` and `flatnotes:data:v1:{id}` |

Each content save creates a new data nonce and encrypts the updated
content. The data encryption key is wrapped with a key derived from the
note password. The worker imports the data key as nonextractable.
The implementation currently uses a fixed KDF profile for version 1.

`FLATNOTES_ENCRYPTION_PASSWORD_MIN_LENGTH` and
`FLATNOTES_ENCRYPTION_PASSWORD_MIN_CLASSES` govern **new passwords** at
the UI level. They do **not** change Argon2id parameters or prevent
offline dictionary attacks against a copied file. They are not validated
by the server because the server never receives the password.

## Password and session lifecycle

A protection password is entered only in a browser form, never in the
query string, URL fragment or encrypted-note API request. Unlocking
uses the salt and encrypted key stored in the envelope. Incorrect
passwords or corrupted authentication tags fail decryption.

The note remains unlocked for the life of the active worker. **Lock**
terminates that worker; leaving the page also terminates it.
JavaScript cannot guarantee that all copies of data are physically
overwritten in browser memory. The plaintext may appear in the browser
DOM, rendered editor, clipboard (when copied) or local downloaded
exports while the note is unlocked.

There is no password recovery, user-based key escrow or implemented
password-change operation.

## Public sharing of encrypted notes

A private encrypted note uses `/e/{id}` and regular flatnotes
authentication. An explicitly published encrypted note uses `/p/{slug}`,
which delivers ciphertext anonymously; the visitor still needs the
note password to decrypt it locally. Public-edit permission permits
uploading new ciphertext after decryption in the visitor's browser.

Publication metadata is **not** encrypted: the server knows the
public slug, opaque note ID and read/edit permission. A random slug is
recommended; custom slugs can be guessed. Using the encrypted title as
a public slug is deliberately unsupported.

## Security boundaries and limitations

- Normal `.md` notes and their published versions are plaintext on the
  server. Do not confuse normal account authentication with encryption.
- Converting a previously plaintext note removes its current file and
  publication record. Deleted blocks, backups, browser drafts, logs and
  filesystem snapshots may retain historic plaintext. Secure erasure is
  not guaranteed.
- External Markdown resources can initiate browser requests; do not
  embed third-party resources into confidential notes. Encrypted page
  responses use CSP restrictions, but extension scripts and malicious
  browser software remain outside the protection guarantee.
- All encrypted-note API updates use ciphertext and a revision
  checksum, detecting concurrent modifications, rather than
  automatically resolving them.
- Encrypted files are limited to 4 MiB by backend storage; embedded
  attachments are limited to 2 MiB total by the editor.
- The encryption password must be strong enough to resist offline
  guessing, even if an administrator reduces the UI minimum.
- Client-side encryption requires Web Crypto and WebAssembly in a secure
  browser context. Use HTTPS for mobile and remote hosts. The browser
  treats its own `localhost` specially, but an HTTP LAN IP is generally
  not a secure context.

See [Encrypted Notes](https://github.com/erathaowl/flatnotes/wiki/Encrypted-Notes), [Operations and Backup](https://github.com/erathaowl/flatnotes/wiki/Operations-and-Backup)
and [API Reference](https://github.com/erathaowl/flatnotes/wiki/API-Reference).

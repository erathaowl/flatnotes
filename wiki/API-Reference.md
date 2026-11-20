# API Reference

flatnotes exposes OpenAPI documentation at `/docs` and the schema at
`/openapi.json`. Prefixes follow `FLATNOTES_PATH_PREFIX` when configured.
This page explains the note, publishing and encrypted-byte routes used by
the 6.4.0 frontend. See the generated schema for exact response models.

## Authentication

In `password` and `totp` modes, authenticated endpoints require a JWT
in the `Authorization: Bearer ...` header or the supported authentication
cookie. The login endpoint is `POST /api/token`.

For TOTP login, the client combines the configured account password
with the current six-digit one-time code **for account authentication**.
This is completely independent of each protected note's encryption
password, which is never sent to the API.

`none` and `read_only` are instance-wide anonymous access modes; use
`password` or `totp` to keep unshared notes private.

## General endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/config` | Public UI flags, branding, auth type and password-policy settings |
| GET | `/api/auth-check` | Check current authentication |
| GET | `/api/search` | Search ordinary Markdown notes |
| GET | `/api/tags` | Read ordinary-note tags |
| POST | `/api/notes` | Create ordinary note (authenticated write) |
| GET | `/api/notes/{title}` | Read ordinary note |
| PATCH | `/api/notes/{title}` | Update title and/or body |
| DELETE | `/api/notes/{title}` | Delete ordinary note |
| POST | `/api/attachments` | Upload ordinary-note attachment |
| GET | `/api/attachments/{filename}` | Read ordinary-note attachment |

The ordinary-note API operates on plaintext Markdown. Use the
encrypted-note API when plaintext must never reach the server.

## Public ordinary-note endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/notes/{title}/publication` | Read publication state |
| PUT | `/api/notes/{title}/publication` | Create or update publication |
| DELETE | `/api/notes/{title}/publication` | Revoke publication |
| GET | `/api/public/notes/{slug}` | Retrieve a published ordinary note |
| PATCH | `/api/public/notes/{slug}` | Edit it when permission is `edit` |
| GET | `/api/public/notes/{slug}/attachments/{filename}` | Read an allowlisted attachment |

Publication settings are expressed as:

```json
{
  "slugMode": "random",
  "permission": "read",
  "slug": null
}
```

Available `slugMode` values are `random`, `title` and `custom`.
Permissions are `read` and `edit`. Changing the slug revokes the
old URL. Anonymous edits use a returned `revision` value and
`newContent` in the PATCH payload.

## Authenticated encrypted-note API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/encrypted-notes` | List opaque note IDs and modified times |
| GET | `/api/encrypted-notes/{id}` | Download raw encrypted envelope |
| PUT | `/api/encrypted-notes/{id}` | Create or replace encrypted envelope |
| DELETE | `/api/encrypted-notes/{id}` | Delete ciphertext and publication, no note password required |
| POST | `/api/encrypted-notes/protect/{title}/{id}` | Convert an existing plain note to ciphertext, including unsaved editor changes |
| GET | `/api/encrypted-notes/{id}/publication` | Read encrypted-note publication |
| PUT | `/api/encrypted-notes/{id}/publication` | Create/update encrypted-note publication |
| DELETE | `/api/encrypted-notes/{id}/publication` | Revoke encrypted-note publication |

The `id` is a 32-character lowercase hexadecimal identifier. The
`GET` response body is raw encrypted bytes with
`Content-Type: application/octet-stream`. It includes the headers
`X-Revision` (SHA-256 of ciphertext) and `X-Note-Id`.

`PUT` sends ciphertext as the body and `X-Revision` as a header.
Use `X-Revision: *` when creating a new note; subsequent updates
must provide the previously returned revision, or HTTP 409 is returned.

The conversion endpoint requires `X-Source-Modified` matching
the original `.md` file's last-modified timestamp. HTTP 409
prevents replacing a newer source. The browser can encrypt current
unsaved editor changes directly; the server writes ciphertext and
removes the old plaintext file and publication.

**Protect for a new unsaved ordinary note** uses
`PUT /api/encrypted-notes/{id}` and `X-Revision: *`,
because the source `.md` file does not exist. The first
server-side copy is ciphertext; the UI can then publish it
using `PUT /api/encrypted-notes/{id}/publication` if requested.

## Public encrypted-note API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/public/encrypted-notes/{slug}` | Download ciphertext, without login |
| PUT | `/api/public/encrypted-notes/{slug}` | Update ciphertext only when public editing is enabled |

`GET` includes `X-Edit-Permission` (`read` or `edit`). Like
authenticated PUT, public PUT supplies `X-Revision` to detect changes.
No endpoint requests or accepts the note's encryption password.

Encrypted publications support **random** and **custom** slugs only.
The `title` slug mode is rejected to avoid disclosing the title.

## Sharing expiration API

Sharing expiration is configured through publication endpoints, using the same payload for ordinary and encrypted shares.

| Method | Path | Purpose |
| --- | --- | --- |
| GET/PUT | `/api/notes/{title}/publication` | Read/create/update Markdown share and expiration |
| DELETE | `/api/notes/{title}/publication` | Unpublish while preserving the original note |
| GET/PUT | `/api/encrypted-notes/{id}/publication` | Read/create/update encrypted share and expiration |
| DELETE | `/api/encrypted-notes/{id}/publication` | Unpublish while preserving the encrypted note |
| POST | `/api/public/encrypted-notes/{slug}/view` | Claim a public encrypted single view |

The PUT payload accepts `expiration`: `none` (default), `once`, positive `Nh` or `Nd`, and `autoDeleteNote` (default false). A single-view publication must be read-only. Auto-delete is valid only with a configured expiration.

```json
{
  "slugMode": "random",
  "permission": "read",
  "expiration": "7d",
  "autoDeleteNote": false
}
```

For an encrypted `once` share, an additional `viewVerifier` is required: the SHA-256 digest of the browser-generated unlock proof. The public claim submits `{"proof":"<64-hex>"}` after local decryption.

Publication responses include `expiration`, `expiresAt` (UTC Unix timestamp), `autoDeleteNote` and `expired`. A publication may return 410 immediately after expiry, then 404 when its metadata has been cleaned up.

The owner's authenticated `GET /api/notes/{title}` and `GET /api/encrypted-notes/{id}` do not consume or check the public-link expiration. Notes remain privately searchable and editable until explicitly deleted or auto-deleted.

The Share dialog stages new-note settings in the browser until the first successful note Save. The first note is created without an expiration policy; its publication is saved afterward. The former note-level expiration endpoints have been removed in 6.4.0.


## Feature flags and errors

`FLATNOTES_ENCRYPTION_ENABLED=false` disables new encryption and
encrypted writes. Existing ciphertext remains readable; deletion by
an authorized account remains available.

`FLATNOTES_SHARING_ENABLED=false` suspends encrypted-note publication
endpoints. Publication flags are exposed through `/api/config`.
The switch is enforced by both ordinary-note and encrypted-note
publication endpoints, including anonymous GET and write routes.
Existing publication settings remain in SQLite and are restored
when the switch is enabled again.

Common responses: HTTP 401 for missing account authentication, 403
for disallowed writes, 404 for unavailable notes/publications, 409
for revision or slug collisions, and 422 for invalid values.

## API cautions

A successful encrypted PUT confirms the server saved bytes. It does
not prove they are decryptable: the server cannot validate ciphertext
cryptographically. The browser must round-trip-test encryption,
passwords and files. Never send a note password in URL parameters,
request headers or request bodies.

# Environment Variables

This is the configuration reference for [erathaowl/flatnotes](https://github.com/erathaowl/flatnotes). Most settings are optional. The Docker image sets `FLATNOTES_PATH=/data`, listens on port 8080, and defaults to user/group ID 1000.

## Storage and networking

| Variable | Default | Description |
| --- | --- | --- |
| `FLATNOTES_PATH` | `/data` in Docker | Directory containing Markdown notes and attachments; required outside Docker |
| `FLATNOTES_PATH_PREFIX` | empty | Serve the app at a subpath, e.g. `/flatnotes` (leading slash, no trailing slash) |
| `FLATNOTES_HOST` | `0.0.0.0` in Docker | Listening address inside the container |
| `FLATNOTES_PORT` | `8080` in Docker | Listening port inside the container |
| `PUID` / `PGID` | `1000` | UID/GID for file permissions when container starts as root |

The configured directory must be writable. Ordinary notes are plaintext
`.md` files, while protected notes use encrypted `.md.enc` envelopes.
Ordinary attachments live in `attachments/`; `.flatnotes/` is the regenerable
Whoosh index for ordinary notes. See [Operations and Backup](https://github.com/erathaowl/flatnotes/wiki/Operations-and-Backup).

Published note metadata is stored independently in `.flatnotes-publications.db`, under `FLATNOTES_PATH`. There is no separate database configuration variable. Preserve this SQLite database when backing up or migrating.

## Authentication

| Variable | Default | Description |
| --- | --- | --- |
| `FLATNOTES_AUTH_TYPE` | `password` | `none`, `read_only`, `password`, or `totp` |
| `FLATNOTES_USERNAME` | required for password/TOTP | Login username |
| `FLATNOTES_PASSWORD` | required for password/TOTP | Login password |
| `FLATNOTES_SECRET_KEY` | required for password/TOTP | JWT signing secret; changing it invalidates existing sessions |
| `FLATNOTES_SESSION_EXPIRY_DAYS` | `30` | JWT session lifetime in days |
| `FLATNOTES_TOTP_KEY` | required for TOTP | Secret used for time-based one-time codes |

### Authentication modes

- **`none`**: unrestricted anonymous reading and editing.
- **`read_only`**: anonymous reading of all notes, with changes disabled.
- **`password`**: username and password needed for private pages and APIs.
- **`totp`**: adds a six-digit time-based code to password authentication.

To expose *only individual published notes* without login, use `password` or `totp`, then enable public sharing on selected notes. The two anonymous global modes cannot enforce this isolation.

### TOTP setup

Set the following variables, using unique, long secrets for the signing and TOTP keys:

```yaml
environment:
  FLATNOTES_AUTH_TYPE: "totp"
  FLATNOTES_USERNAME: "admin"
  FLATNOTES_PASSWORD: "${FLATNOTES_PASSWORD}"
  FLATNOTES_SECRET_KEY: "${FLATNOTES_SECRET_KEY}"
  FLATNOTES_TOTP_KEY: "${FLATNOTES_TOTP_KEY}"
  FLATNOTES_SESSION_EXPIRY_DAYS: "1"
```

Generate each secret independently (e.g. `openssl rand -hex 32`), store the values securely, then restart:

```bash
docker compose up -d
docker compose logs flatnotes
```

At startup, flatnotes prints a QR code and a manual key. Scan the QR code using an authenticator app. On login, enter the username, password, and current six-digit code in their separate fields.

**Important:** The container logs contain TOTP enrollment information. Restrict log access and preserve `FLATNOTES_TOTP_KEY` so enrolled authenticators remain valid. For direct API use, concatenate the current six-digit TOTP code to the password in the `/api/token` request.

## Encryption and sharing feature switches

| Variable | Default | Behavior |
| --- | --- | --- |
| `FLATNOTES_ENCRYPTION_ENABLED` | `false` | Enable creation and protection of notes. Already encrypted notes remain readable when disabled. |
| `FLATNOTES_SHARING_ENABLED` | `true` | Enable the Share dialog and public endpoints. Disabling it suspends all public links without deleting their metadata. |

### Protected-note password policy

| Variable | Default | Description |
| --- | --- | --- |
| `FLATNOTES_ENCRYPTION_PASSWORD_MIN_LENGTH` | `12` | Minimum length for newly created passwords (0 to 1024; 0 disables minimum length) |
| `FLATNOTES_ENCRYPTION_PASSWORD_MIN_CLASSES` | `0` | Minimum number of distinct character categories (0 to 4; 0 disables complexity enforcement) |

The four categories are **lowercase**, **uppercase**, **numbers** and
**symbols**. For example, `MIN_CLASSES=3` requires any three different
categories, without requiring one specific combination. The `0` value
disables the corresponding complexity check, but the protection password
field still requires a nonempty value. Policies are enforced by the
browser during note creation/conversion, rather than by inspecting
passwords on the server.

Example:

```yaml
environment:
  FLATNOTES_ENCRYPTION_PASSWORD_MIN_LENGTH: "8"
  FLATNOTES_ENCRYPTION_PASSWORD_MIN_CLASSES: "3"
```

Both parameters are exposed by `/api/config` so the browser can enforce
them when creating a protected note or encrypting an existing Markdown
note. The protection password itself remains in the browser. Existing
encrypted notes can always be unlocked with their previous password.
Account-authenticated users can delete an encrypted note without
unlocking it.

Normal notes are stored as `.md` files. Protected notes use opaque
filenames ending in `.md.enc`. Encryption keys, passwords, titles and
protected content are handled by the browser. The server stores ciphertext
and does not index encrypted notes.

See [Encrypted Notes](https://github.com/erathaowl/flatnotes/wiki/Encrypted-Notes).

## Quick access on the home page

| Variable | Default | Description |
| --- | --- | --- |
| `FLATNOTES_QUICK_ACCESS_HIDE` | `false` | `true` hides quick-access notes |
| `FLATNOTES_QUICK_ACCESS_TITLE` | `RECENTLY MODIFIED` | Quick-access section heading |
| `FLATNOTES_QUICK_ACCESS_TERM` | `*` | Search expression, e.g. `#pinned` |
| `FLATNOTES_QUICK_ACCESS_SORT` | `lastModified` | One of `score`, `title`, `lastModified` |
| `FLATNOTES_QUICK_ACCESS_LIMIT` | `4` | Maximum number of quick-access notes |

The legacy `FLATNOTES_HIDE_RECENTLY_MODIFIED` variable is deprecated and supported for compatibility.

## Optional branding

| Variable | Default | Description |
| --- | --- | --- |
| `FLATNOTES_SITE_TITLE` | `flatnotes` | Application wordmark and browser tab title |
| `FLATNOTES_LOGO_PATH` | unset | Absolute path inside the container to a custom logo (SVG, PNG, JPEG, WebP) |
| `FLATNOTES_FAVICON_PATH` | unset | Absolute path inside the container to a custom favicon (ICO, SVG, PNG, JPEG, WebP) |

Example when `./data:/data` is mounted:

```yaml
environment:
  FLATNOTES_SITE_TITLE: "Team Notes"
  FLATNOTES_LOGO_PATH: "/data/branding/logo.svg"
  FLATNOTES_FAVICON_PATH: "/data/branding/favicon.ico"
```

Place the files on the host under `./data/branding/`. Files must exist at startup; unsupported extensions and invalid paths cause a startup error. Unset variables retain the original branding. A custom logo replaces both the default icon and wordmark. See [Custom Branding](https://github.com/erathaowl/flatnotes/wiki/Custom-Branding).

## Sharing settings

The global switch `FLATNOTES_SHARING_ENABLED` controls whether
publication is available (default `true`). Per-note **Share**
settings choose `private`, `read` or `edit`; public links are
read-only when first enabled. Disabling sharing suspends the
public ordinary-note and encrypted-note API endpoints with HTTP 404
and hides the Share controls. Existing SQLite publication records
are preserved for later re-enabling.

Publication settings, link identifiers, and attachment permissions persist in `/data/.flatnotes-publications.db`. See [Publishing Notes](https://github.com/erathaowl/flatnotes/wiki/Publishing-Notes).

All environment variables are read at startup. Update your
Compose or service configuration and restart the process to apply
changes. Feature flags cannot be used to recover a forgotten
encryption password.

## More information

- [Docker and Releases](https://github.com/erathaowl/flatnotes/wiki/Docker-and-Releases)
- [README](https://github.com/erathaowl/flatnotes/blob/develop/README.md)

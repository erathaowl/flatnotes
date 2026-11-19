<p align="center">
  <img src="docs/logo.svg" alt="flatnotes" width="300">
</p>
<p align="center">
  <a href="https://github.com/erathaowl/flatnotes/pkgs/container/flatnotes"><img alt="GHCR image" src="https://img.shields.io/badge/GHCR-flatnotes-blue?style=for-the-badge&logo=github"></a>
</p>

# flatnotes

A lightweight, self-hosted Markdown note-taking application with search, tags, configurable branding, and selective note sharing. Notes remain ordinary `.md` files. A Whoosh index supports search; a small SQLite database stores **only publication metadata**.

[Documentazione in italiano](readme-it.md) · [Documentation / Wiki sources](wiki/Home.md) · [Container images](https://github.com/erathaowl/flatnotes/pkgs/container/flatnotes) · [Releases](https://github.com/erathaowl/flatnotes/releases)

## Features

- Responsive Vue interface with Markdown and WYSIWYG editing, light/dark themes, and full-text search.
- Tags, wiki-style links (`[[Note Title]]`), image attachments, and configurable quick-access notes.
- Authentication modes: `none`, `read_only`, `password`, and `totp`.
- **Per-note publication** with anonymous read-only access or optional anonymous editing. Each published note has a random, title-derived, or custom URL.
- Custom application title, logo, and favicon through environment variables.
- REST API, Docker image hosted on GHCR, automated builds and versioned releases.

## Python wheel (without Docker)

Release assets include a standalone Python wheel containing the FastAPI backend,
the complete compiled Vue frontend, and the `flatnotes` command-line launcher.
The target machine needs **Python 3.13**, but **does not need Node.js**.

Download `flatnotes-6.0.0-py3-none-any.whl` from the
[GitHub Release](https://github.com/erathaowl/flatnotes/releases/tag/v6.0.0), then run:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install flatnotes-6.0.0-py3-none-any.whl

mkdir -p ./data
export FLATNOTES_PATH="$(pwd)/data"
export FLATNOTES_AUTH_TYPE=password
export FLATNOTES_USERNAME=admin
export FLATNOTES_PASSWORD="change-this-password"
export FLATNOTES_SECRET_KEY="replace-with-a-long-random-secret"

flatnotes --host 0.0.0.0 --port 8080
```

The wheel contains all static frontend files and works independently of the
current working directory. The CLI accepts `--host`, `--port`, and
`--forwarded-allow-ips`. Use your preferred service manager (for example,
systemd) for production deployments; configure an HTTPS reverse proxy for
Internet access. The `FLATNOTES_PATH` directory remains external to the
installed package so that notes, attachments and SQLite publication settings
survive application upgrades.

To build from source, run `npm ci && npm run build`,
`bash scripts/prepare-web-assets.sh`, then `uv build --wheel`. The wheel is
validated in CI by installing it into a clean virtual environment from outside
the repository, then exercising the CLI, health endpoint, HTML page, API and
compiled JavaScript assets.

## Quick start with Docker Compose

Create a `compose.yaml` file:

```yaml
services:
  flatnotes:
    image: ghcr.io/erathaowl/flatnotes:develop
    container_name: flatnotes
    ports:
      - "8080:8080"
    environment:
      PUID: "1000"
      PGID: "1000"
      FLATNOTES_AUTH_TYPE: "password"
      FLATNOTES_USERNAME: "admin"
      FLATNOTES_PASSWORD: "${FLATNOTES_PASSWORD}"
      FLATNOTES_SECRET_KEY: "${FLATNOTES_SECRET_KEY}"
    volumes:
      - ./data:/data
    restart: unless-stopped
```

Set `FLATNOTES_PASSWORD` and `FLATNOTES_SECRET_KEY` in a local `.env` file, using strong independent values (for example, generate a secret with `openssl rand -hex 32`), then run:

```bash
docker compose up -d
```

Open `http://localhost:8080`. Data and publication settings persist in the `./data` directory. Use `:develop` for the current development build; `:latest` refers to the latest tagged release (and is only available once a release has been published).

See [Docker and Releases](wiki/Docker-and-Releases.md) and [Environment Variables](wiki/Environment-Variables.md) for a complete configuration reference.

## Protected notes (browser-only encryption)

Set `FLATNOTES_ENCRYPTION_ENABLED=true` to enable the **Protect** action for
normal notes and creation of protected notes. Protection uses **Argon2id**
(64 MiB, three iterations, one lane) to derive a wrapping key from your
password and **AES-256-GCM** to encrypt a random per-note data key and
the note content. Cryptographic operations execute in a browser Web Worker.
Passwords and decrypted note content are never sent to the server by
protected-note APIs.

The supported URL scheme is:

- `/n/{title}`: normal Markdown note, subject to the usual login.
- `/p/{slug}`: published note, optionally encrypted and unlocked in-browser.
- `/e/{id}`: protected note, addressed by a random opaque identifier.

Protected files are stored as `/data/{id}.md.enc` and do not enter
the server-side search index. Their titles and tags are encrypted, so the
protected notes list shows opaque identifiers until the browser unlocks them.
Passwords are entered only in a browser form, **never in URL query strings
or fragments**. Losing a password means losing the ability to decrypt its note.

Protected images can be embedded directly into encrypted Markdown as data
URLs. Existing plaintext attachments must be removed or embedded before a
note can be protected. A protected note can be exported as Markdown directly
from the browser. Converting that export into an ordinary server-stored Markdown
note would necessarily transmit plaintext, so automatic unprotection is
intentionally unsupported.

Set `FLATNOTES_SHARING_ENABLED=false` to disable publication controls
and all public publication APIs while retaining publication metadata.
This flag defaults to `true`. Encryption defaults to `false`; existing
encrypted notes remain readable even when new encryption is disabled.

**Security considerations:** Use HTTPS, a trusted instance, strong unique
passphrases, and a current browser. Protecting an existing plaintext note
cannot erase historical plaintext backups, filesystem snapshots, or old
search index blocks. The server delivers the JavaScript used for encryption;
a compromised server able to replace that JavaScript could compromise the
browser's security boundary.

Read the [Encrypted Notes](wiki/Encrypted-Notes.md) guide for the file
format, threat model, permissions, and backup details.

## Publish a note

Open an existing note and click **Share**. Notes are private by default; choose **Public: read-only** or **Public: anyone with the link can edit**. Select a URL identifier:

- **Random** (default): a hard-to-guess identifier, such as `/p/82eace7f63bc824b35a44dfb2958cdb0`.
- **Note title**: a readable slug derived from the current title.
- **Custom**: your own suffix containing lowercase letters, numbers, or hyphens.

Click **Save** to apply the settings and close the Share dialog. You can reopen it to copy the resulting link or unpublish the note. Existing public links stop working after revocation or a URL change. Renaming a note inside flatnotes preserves its existing public URL.

Anonymous users can view only published notes and cannot access the private note list or search when using `password` or `totp`. Public editors can change note **content only**; they cannot rename, delete, upload attachments, or change sharing settings. Concurrent edits use a revision check and may return HTTP 409.

**Security:** A public editable link grants editing permission to anyone who knows it. Title-based and custom URLs are predictable. For selective publication, use `FLATNOTES_AUTH_TYPE=password` or `totp`; the `none` and `read_only` modes expose broader note access by design.

See [Publishing Notes](wiki/Publishing-Notes.md) for API details, attachment restrictions, and revocation behavior.

## Custom branding

Three optional environment variables change the application branding:

| Variable | Example | Behavior |
| --- | --- | --- |
| `FLATNOTES_SITE_TITLE` | `My Notes` | Browser title and displayed wordmark |
| `FLATNOTES_LOGO_PATH` | `/data/branding/logo.svg` | Replaces the complete default logo |
| `FLATNOTES_FAVICON_PATH` | `/data/branding/favicon.ico` | Replaces the browser favicon |

For Docker, place your assets in `./data/branding/` when using the volume shown above. File paths must be absolute **inside the container**. Omit any variable to keep the corresponding default. Supported logo formats: SVG, PNG, JPEG, WebP; supported favicon formats also include ICO.

See [Custom Branding](wiki/Custom-Branding.md).

## TOTP authentication

Change `FLATNOTES_AUTH_TYPE` to `totp` and add `FLATNOTES_TOTP_KEY` with a random, persistent secret. Restart the container and inspect `docker compose logs flatnotes`: the startup output includes a QR code and a manual enrollment secret for your authenticator app. Login requires username, password, and the current six-digit code. Treat the startup logs as sensitive.

The default JWT session lifetime is 30 days, configurable with `FLATNOTES_SESSION_EXPIRY_DAYS`. See [Environment Variables](wiki/Environment-Variables.md#totp-setup).

## Data and backups

- `/data/*.md`: note files, portable to other Markdown editors.
- `/data/attachments/`: uploaded images and other attachments.
- `/data/.flatnotes/`: regenerable Whoosh search index.
- `/data/.flatnotes-publications.db`: persistent SQLite publication settings and public attachment permissions.

Back up the Markdown files, attachments, and SQLite database. For a running container, use a SQLite-consistent backup (or stop the container before copying SQLite files). Removing the Whoosh index is safe while the application is stopped; keep the publication database.

## Builds and releases

GitHub Actions on `develop` run frontend compilation and Python tests, produce an application `.tar.gz` and a Python `.whl` artifact, and publish `ghcr.io/erathaowl/flatnotes:develop` and `:sha-<commit>`. Pull requests validate builds without publishing images.

Pushing a version tag `vX.Y.Z` (or `vX.Y`, normalized to `vX.Y.0`) builds and publishes `ghcr.io/erathaowl/flatnotes:vX.Y.Z`, updates `:latest`, and creates a [GitHub Release](https://github.com/erathaowl/flatnotes/releases) containing a compiled frontend/backend archive and an installable wheel. This archive is a source bundle, not a Python wheel.

## Documentation

The wiki sources live in [`wiki/`](wiki/Home.md) and are version-controlled alongside the application. They can also be published to the [GitHub Wiki](https://github.com/erathaowl/flatnotes/wiki) when the wiki is initialized. Consult [Home](wiki/Home.md) for links to search syntax, tagging, attachments, authentication, publishing, branding, and CI/CD.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) and [LICENSE](LICENSE). This fork is based on [flatnotes](https://github.com/dullage/flatnotes). It uses [Whoosh](https://whoosh.readthedocs.io/) and [TOAST UI Editor](https://ui.toast.com/tui-editor).

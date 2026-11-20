# Docker and Releases

## Python wheel

Download the `flatnotes-6.3.0-py3-none-any.whl` asset from the
[GitHub Release](https://github.com/erathaowl/flatnotes/releases/tag/v6.3.0).
It includes the FastAPI backend and compiled Vue frontend. Installation requires
Python 3.13, but neither Node.js nor Docker:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install flatnotes-6.3.0-py3-none-any.whl
export FLATNOTES_PATH="/var/lib/flatnotes"
export FLATNOTES_AUTH_TYPE="password"
export FLATNOTES_USERNAME="admin"
export FLATNOTES_PASSWORD="your-password"
export FLATNOTES_SECRET_KEY="your-secret"
flatnotes --host 0.0.0.0 --port 8080
```

The wheel can be installed and run outside the repository, with site data
persisted externally under `FLATNOTES_PATH`. The CLI supports
`--forwarded-allow-ips` for trusted reverse proxies. A smoke test in GitHub
Actions verifies the wheel installation and frontend files.

## Optional browser encryption

Add these variables to the Docker Compose service:

```yaml
environment:
  FLATNOTES_ENCRYPTION_ENABLED: "true"
  FLATNOTES_SHARING_ENABLED: "true"
  FLATNOTES_EXPIRATION_ENABLED: "false"
  FLATNOTES_EXPIRATION_DEFAULT: "none"
  FLATNOTES_ENCRYPTION_PASSWORD_MIN_LENGTH: "12"
  FLATNOTES_ENCRYPTION_PASSWORD_MIN_CLASSES: "0"
```

Encrypted notes use `/data/{id}.md.enc` and are not indexed by Whoosh.
Passwords never reach the encrypted-note APIs. The build includes a bundled
Argon2id WebAssembly module for in-browser key derivation.

See [Encrypted Notes](https://github.com/erathaowl/flatnotes/wiki/Encrypted-Notes).

## Container image

This fork publishes images in GitHub Container Registry:

```text
ghcr.io/erathaowl/flatnotes
```

The `master` tag is updated after pushes to the primary branch. Tagged Git releases generate versioned images and update `latest`. Versioned images are preferable for reproducible deployments once releases exist.

## Docker Compose installation

```yaml
services:
  flatnotes:
    image: ghcr.io/erathaowl/flatnotes:v6.3.0
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
      FLATNOTES_ENCRYPTION_ENABLED: "true"
      FLATNOTES_SHARING_ENABLED: "true"
      FLATNOTES_ENCRYPTION_PASSWORD_MIN_LENGTH: "12"
      FLATNOTES_ENCRYPTION_PASSWORD_MIN_CLASSES: "0"
      FLATNOTES_EXPIRATION_ENABLED: "false"
      FLATNOTES_EXPIRATION_DEFAULT: "none"
    volumes:
      - ./data:/data
    restart: unless-stopped
```

Configure the two required secrets in a local `.env` file, then run `docker compose up -d`. Open `http://localhost:8080`.

The volume contains Markdown notes, encrypted `.md.enc` notes,
ordinary attachments, the search index and SQLite publication metadata.
Keep it mounted across upgrades. Add your password and JWT secret to
a local `.env` file (avoid committing it). Use HTTPS when opening
protected notes from phones or other remote devices.

## Docker run alternative

```bash
docker run -d --name flatnotes \
  -p 8080:8080 \
  -e PUID=1000 -e PGID=1000 \
  -e FLATNOTES_AUTH_TYPE=password \
  -e FLATNOTES_USERNAME=admin \
  -e FLATNOTES_PASSWORD="$FLATNOTES_PASSWORD" \
  -e FLATNOTES_SECRET_KEY="$FLATNOTES_SECRET_KEY" \
  -v "$(pwd)/data:/data" \
  --restart unless-stopped \
  ghcr.io/erathaowl/flatnotes:v6.3.0
```

## CI/CD

| Workflow | Trigger | Output |
| --- | --- | --- |
| Build | Push to `master`, pull request targeting `master`, manual run | Compiled frontend, Python tests, application archive and Python wheel; Docker image for pushes |
| Release | Version tag or release-request file update on `master` | GitHub Release archive, Python wheel, and GHCR image |

Build pushes create image tags `:master` and `:sha-<commit>`. Pull requests do not push to GHCR.

Release tags `vX.Y` are normalized to `vX.Y.0` for the published image and release name. The release workflow builds and tests the code, pushes `:vX.Y.Z` and `:latest` to GHCR, and attaches a `.tar.gz` application bundle and installable Python wheel to the GitHub Release. The bundle includes compiled frontend assets, Python backend sources,
English and Italian READMEs, branding reference files and the complete
`wiki/` documentation directory. It can be installed using the locked
`uv` dependencies. It is not a Python wheel.

See [GitHub Actions](https://github.com/erathaowl/flatnotes/actions), [GHCR image](https://github.com/erathaowl/flatnotes/pkgs/container/flatnotes), and [Releases](https://github.com/erathaowl/flatnotes/releases).

## Editor behavior

The current application uses a shared toolbar for ordinary and
encrypted notes. Share and Expiration are available in modal dialogs
before the first save; their options are staged locally until the
note exists. Protect can encrypt a new or modified ordinary draft
without storing an intermediate plaintext note on the server.

Production deployments should pin the released Docker image
instead of using `:master`. The wheel and application archive
are published after the release workflow's tests succeed.

## Updating

```bash
docker compose pull
docker compose up -d
```

Public note sharing is enabled by default and can be suspended by
setting `FLATNOTES_SHARING_ENABLED=false`. Encryption is disabled by
default and can be enabled with `FLATNOTES_ENCRYPTION_ENABLED=true`.
Publication state persists in `/data/.flatnotes-publications.db`,
including across feature-flag changes.

A consistent backup must include `*.md`, `*.md.enc`,
`attachments/` and the SQLite publication database. Use
[Operations and Backup](https://github.com/erathaowl/flatnotes/wiki/Operations-and-Backup)
for a safe upgrade and restore checklist.

Related: [Environment Variables](https://github.com/erathaowl/flatnotes/wiki/Environment-Variables), [Publishing Notes](https://github.com/erathaowl/flatnotes/wiki/Publishing-Notes), and [Custom Branding](https://github.com/erathaowl/flatnotes/wiki/Custom-Branding).

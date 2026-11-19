# Docker and Releases

## Container image

This fork publishes images in GitHub Container Registry:

```text
ghcr.io/erathaowl/flatnotes
```

The `develop` tag is updated after pushes to the development branch. Tagged Git releases generate versioned images and update `latest`. Versioned images are preferable for reproducible deployments once releases exist.

## Docker Compose installation

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

Configure the two required secrets in a local `.env` file, then run `docker compose up -d`. Open `http://localhost:8080`.

The volume contains Markdown notes, attachments, search index, and SQLite publication metadata. Keep the volume when upgrading.

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
  ghcr.io/erathaowl/flatnotes:develop
```

## CI/CD

| Workflow | Trigger | Output |
| --- | --- | --- |
| Build | Push to `develop`, pull request targeting `develop`, manual run | Compiled frontend, Python tests, application archive; Docker image for pushes |
| Release | Push of `vX.Y.Z` or `vX.Y` tag | GitHub Release archive and GHCR image |

Build pushes create image tags `:develop` and `:sha-<commit>`. Pull requests do not push to GHCR.

Release tags `vX.Y` are normalized to `vX.Y.0` for the published image and release name. The release workflow builds and tests the code, pushes `:vX.Y.Z` and `:latest` to GHCR, and attaches a `.tar.gz` application bundle to the GitHub Release. The bundle includes compiled frontend assets and Python backend sources and can be installed using the locked `uv` dependencies. It is not a Python wheel.

See [GitHub Actions](https://github.com/erathaowl/flatnotes/actions), [GHCR image](https://github.com/erathaowl/flatnotes/pkgs/container/flatnotes), and [Releases](https://github.com/erathaowl/flatnotes/releases).

## Updating

```bash
docker compose pull
docker compose up -d
```

No environment variables are required for public note sharing beyond normal authentication setup. Publication state persists in `/data/.flatnotes-publications.db`.

Related: [Environment Variables](https://github.com/erathaowl/flatnotes/wiki/Environment-Variables), [Publishing Notes](https://github.com/erathaowl/flatnotes/wiki/Publishing-Notes), and [Custom Branding](https://github.com/erathaowl/flatnotes/wiki/Custom-Branding).

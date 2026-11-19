<p align="center">
  <img src="docs/logo.svg" width="300px"></img>
</p>
<p align="center">
  <a href="https://github.com/erathaowl/flatnotes/pkgs/container/flatnotes"><img alt="GHCR image" src="https://img.shields.io/badge/GHCR-flatnotes-blue?style=for-the-badge&logo=github"></a>
</p>

A self-hosted, database-less note-taking web app that utilises a flat folder of markdown files for storage.

Log into the [demo site](https://demo.flatnotes.io) and take a look around. *Note: This site resets every 15 minutes.*

## Contents

* [Design Principle](#design-principle)
* [Features](#features)
* [Getting Started](#getting-started)
  * [Hosted](#hosted)
  * [Self Hosted](#self-hosted)
* [Roadmap](#roadmap)
* [Contributing](#contributing)
* [Sponsorship](#sponsorship)
* [Thanks](#thanks)

## Design Principle

flatnotes is designed to be a distraction-free note-taking app that puts your note content first. This means:

* A clean and simple user interface.
* No folders, notebooks or anything like that. Just all of your notes, backed by powerful search and tagging functionality.
* Quick access to a full-text search from anywhere in the app (keyboard shortcut "/").

Another key design principle is not to take your notes hostage. Your notes are just markdown files. There's no database, proprietary formatting, complicated folder structures or anything like that. You're free at any point to just move the files elsewhere and use another app.

Equally, the only thing flatnotes caches is the search index and that's incrementally synced on every search (and when flatnotes first starts). This means that you're free to add, edit & delete the markdown files outside of flatnotes even whilst flatnotes is running.

## Features

* Mobile responsive web interface.
* Raw/WYSIWYG markdown editor modes.
* Advanced search functionality.
* Note "tagging" functionality.
* Customisable home page.
* Wikilink support to easily link to other notes (`[[My Other Note]]`).
* Light/dark themes.
* Multiple authentication options (none, read-only, username/password, 2FA).
* Restful API.
* Per-note public sharing with read-only or optional anonymous editing.

See [the wiki](https://github.com/dullage/flatnotes/wiki) for more details.

## Getting Started

### Hosted

A quick and easy way to get started with flatnotes is to host it on PikaPods. Just click the button below and follow the instructions.

[![PikaPods](https://www.pikapods.com/static/run-button-34.svg)](https://www.pikapods.com/pods?run=flatnotes)


### Self Hosted

If you'd prefer to host flatnotes yourself then the recommendation is to use Docker.

Images for this fork are published to [GitHub Container Registry](https://github.com/erathaowl/flatnotes/pkgs/container/flatnotes). The `latest` image tracks published releases, while `develop` follows the development branch. Each release also has a `vX.Y.Z` image tag.

### Example Docker Run Command

```shell
docker run -d \
  -e "PUID=1000" \
  -e "PGID=1000" \
  -e "FLATNOTES_AUTH_TYPE=password" \
  -e "FLATNOTES_USERNAME=user" \
  -e 'FLATNOTES_PASSWORD=changeMe!' \
  -e "FLATNOTES_SECRET_KEY=aLongRandomSeriesOfCharacters" \
  -v "$(pwd)/data:/data" \
  -p "8080:8080" \
  ghcr.io/erathaowl/flatnotes:latest
```

### Example Docker Compose
```yaml
version: "3"

services:
  flatnotes:
    container_name: flatnotes
    image: ghcr.io/erathaowl/flatnotes:latest
    environment:
      PUID: 1000
      PGID: 1000
      FLATNOTES_AUTH_TYPE: "password"
      FLATNOTES_USERNAME: "user"
      FLATNOTES_PASSWORD: "changeMe!"
      FLATNOTES_SECRET_KEY: "aLongRandomSeriesOfCharacters"
    volumes:
      - "./data:/data"
      # Optional. Allows you to save the search index in a different location: 
      # - "./index:/data/.flatnotes"
    ports:
      - "8080:8080"
    restart: unless-stopped
```

See the [Environment Variables](https://github.com/dullage/flatnotes/wiki/Environment-Variables) article in the wiki for a full list of configuration options.


### Publishing individual notes

Authenticated owners can open a note and select **Share**. Each note is private by
default. Published notes receive a link such as
https://notes.example.com/p/82eace7f63bc824b35a44dfb2958cdb0.
Choose one of three URL suffix modes:

- **Random** (default): a cryptographically random link identifier.
- **Title**: a slug derived from the note title.
- **Custom**: a manually entered URL suffix (lowercase letters, numbers and hyphens).

Each note can have one active public URL. Public notes are **read-only by default**.
The owner can enable **anyone with the link can edit**, allowing anonymous visitors
to modify the Markdown content. Public visitors cannot rename, delete or publish
notes, upload attachments, or use private search. Concurrent edits require matching
content revisions and otherwise return HTTP 409.

Changing the public URL revokes the previous one. Renaming the note in flatnotes
preserves its active URL. Unpublishing or deleting the note revokes access. The
random URL is harder to guess; custom and title-based URLs are predictable.
Treat publicly editable links as shared editing permissions.

Publication metadata is kept in the SQLite database at
/data/.flatnotes-publications.db, separately from Markdown notes and the Whoosh
search index. Include this database and its WAL/SHM files, if present, in backups,
or use the SQLite backup API to produce a consistent live snapshot. The existing
Docker volume mounted at /data preserves metadata between restarts.

Attachments referenced by a note at publication time may be viewed through
a note-scoped public endpoint. Changes made by the authenticated owner update
the attachment allowlist. Anonymous edits cannot grant access to additional private
attachments, and public editing does not support file uploads.

The existing FLATNOTES_AUTH_TYPE=none and read_only authentication modes already
allow broad unauthenticated access to notes. Use password or totp to ensure
unpublished notes remain private.

### Builds and Releases

Pushes to `develop` build an application archive (available from the Actions run artifacts) and publish `ghcr.io/erathaowl/flatnotes:develop` plus a commit-specific `sha-` image tag. Pull requests build the archive without publishing an image.

Pushing a version tag such as `v5.6.0` builds the archive and Docker image, publishes the image as `:v5.6.0` and `:latest`, and attaches the archive to a [GitHub Release](https://github.com/erathaowl/flatnotes/releases). A shortened tag like `v5.6` is normalized to `v5.6.0` for the release and image tags.

The archive includes the Python backend and compiled frontend, together with the files needed to install Python dependencies using `uv sync --locked --no-dev`. It is a ready-to-run source bundle, not a Python wheel.

## Roadmap

I want to keep flatnotes as simple and distraction-free as possible which means limiting new features. This said, I welcome feedback and suggestions.

## Contributing

If you're interested in contributing to flatnotes, then please read the [CONTRIBUTING.md](CONTRIBUTING.md) file.

## Sponsorship

If you find this project useful, please consider buying me a beer. It would genuinely make my day.

[![Sponsor](https://img.shields.io/static/v1?label=Sponsor&message=%E2%9D%A4&logo=GitHub&color=%23fe8e86)](https://github.com/sponsors/Dullage)

## Thanks

A special thanks to 2 fantastic open-source projects that make flatnotes possible.

* [Whoosh](https://whoosh.readthedocs.io/en/latest/intro.html) - A fast, pure Python search engine library.
* [TOAST UI Editor](https://ui.toast.com/tui-editor) - A GFM Markdown and WYSIWYG editor for the browser.

# Custom Branding

The application title, logo, and favicon can be customized independently through environment variables. Each setting is optional.

## Supported variables

| Variable | Default | Effect |
| --- | --- | --- |
| `FLATNOTES_SITE_TITLE` | `flatnotes` | Browser tab title and the text displayed with the default logo icon |
| `FLATNOTES_LOGO_PATH` | unset | Absolute path to an image replacing the entire icon and wordmark |
| `FLATNOTES_FAVICON_PATH` | unset | Absolute path to the browser favicon |

All three settings are applied when the container starts and made available to the frontend through `/api/config`. The configured images are served at public endpoints `/api/branding/logo` and `/api/branding/favicon`, so they work on the login page.

## Docker Compose example

With a persistent volume at `./data:/data`, store the files in `./data/branding/`.

```yaml
services:
  flatnotes:
    image: ghcr.io/erathaowl/flatnotes:develop
    environment:
      FLATNOTES_SITE_TITLE: "My Notes"
      FLATNOTES_LOGO_PATH: "/data/branding/logo.svg"
      FLATNOTES_FAVICON_PATH: "/data/branding/favicon.ico"
    volumes:
      - ./data:/data
```

Restart after editing settings:

```bash
docker compose up -d
```

Paths must be absolute paths **inside the container**, not host paths. The application validates each file at startup. Invalid or missing files cause an explicit startup error.

## Formats and layout

- Logo: SVG, PNG, JPEG, WebP.
- Favicon: ICO, SVG, PNG, JPEG, WebP.
- A custom logo replaces the complete original mark, including the wordmark.
- A custom title without a custom logo preserves the original icon and changes the text beside it.
- Omitting all variables preserves the original appearance.

For a transparent logo, prefer SVG or transparent PNG. The frontend sizes the logo to fit the existing header without distortion. If your browser keeps an old favicon, clear its cache or reload the page.

Related: [Environment Variables](https://github.com/erathaowl/flatnotes/wiki/Environment-Variables) and [Docker and Releases](https://github.com/erathaowl/flatnotes/wiki/Docker-and-Releases).

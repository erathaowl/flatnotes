# Custom Branding

The application title, logo, and favicon can be customized independently through environment variables. Each setting is optional.

## Where branding appears

The site title is used in the browser tab and the default text
wordmark. A custom logo replaces the entire original icon and
wordmark; it is shown on application pages, including the login
screen. A custom favicon is served from the configured path and
used by the browser.

The backend exposes branding settings through `/api/config` and
the images through `/api/branding/logo` and
`/api/branding/favicon`. These public resources do not contain
note content. Brand assets are checked at startup: missing files
or unsupported extensions prevent the service from starting.

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
    image: ghcr.io/erathaowl/flatnotes:v6.5.0
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

A restart is required after changing the environment variables.
On Docker, keep assets in a persistent mounted volume and specify
their absolute *container* paths; host-only paths are not visible
to the container. See [Operations and Backup](https://github.com/erathaowl/flatnotes/wiki/Operations-and-Backup)
for the deployment directory layout.

Related: [Environment Variables](https://github.com/erathaowl/flatnotes/wiki/Environment-Variables) and [Docker and Releases](https://github.com/erathaowl/flatnotes/wiki/Docker-and-Releases).

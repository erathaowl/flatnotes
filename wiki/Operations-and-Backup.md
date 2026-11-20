# Operations, Upgrades and Backups

## Deployment options

flatnotes 6.3.0 ships with three deployment artifacts:

- GHCR images `ghcr.io/erathaowl/flatnotes:v6.3.0` and `:latest`;
  `:master` tracks the development branch.
- An installable Python 3.13 wheel,
  `flatnotes-6.3.0-py3-none-any.whl`, including the FastAPI
  backend, compiled Vue frontend and `flatnotes` CLI.
- `flatnotes-6.3.0.tar.gz`, an application archive with Python
  backend sources and compiled frontend files.

A production deployment needs a writable data directory, application
authentication, controlled backups and HTTPS for mobile Web Crypto.

## Persistent data layout

```text
/data/
  Meeting Notes.md            # Plaintext note, searchable by Whoosh
  a1b2...32-hex...ff.md.enc   # Protected note: ciphertext envelope
  attachments/                # Ordinary-note attachments
  .flatnotes/                 # Regenerable Whoosh search index
  .flatnotes-publications.db  # SQLite publication settings
```

An encrypted note can contain embedded encrypted attachments within
its `.md.enc` envelope. This does not create a second plaintext
attachment directory for that protected note.

The SQLite database is **not** an encryption-key store. It contains
public sharing state and permitted attachment names, including
encrypted-note publication slugs and permissions.

## Before upgrading

1. Record the currently deployed image digest or wheel version.
2. Back up the entire persistent data directory, especially `*.md`,
   `*.md.enc`, `attachments/` and `.flatnotes-publications.db`.
3. Preserve `FLATNOTES_SECRET_KEY` for account JWT compatibility,
   `FLATNOTES_TOTP_KEY` for TOTP enrollment and the independent
   passwords needed to decrypt protected notes.
4. Pull a specific versioned image, ideally testing against a copy
   of the data before upgrading the production instance.
5. Verify login, ordinary-note search, protected-note unlocking,
   note editing and active public links after updating.

The deployment preserves existing notes when updating the executable
or image. Avoid using the source repository as the data directory.

## Docker update

```bash
docker compose pull flatnotes
docker compose up -d flatnotes
docker compose logs --tail=100 flatnotes
```

Use a pinned tag `v6.3.0` for reproducible deployments. The
`:master` tag is for testing and changes with each successful
development build.

A reverse proxy can expose HTTPS and forward to the container
on port 8080. Bind the Docker port to `127.0.0.1` when the proxy
runs on the same host:

```yaml
ports:
  - "127.0.0.1:18080:8080"
```

The host-side Nginx can then use
`proxy_pass http://127.0.0.1:18080;`. Configure the proxy's
Host, forwarded-proto and forwarded-for headers according to your
network design. See [Docker and Releases](https://github.com/erathaowl/flatnotes/wiki/Docker-and-Releases).

## Python wheel update

Install the new wheel into the target virtual environment and
restart the service:

```bash
python3.13 -m venv .venv
. .venv/bin/activate
pip install --upgrade ./flatnotes-6.3.0-py3-none-any.whl
flatnotes --host 127.0.0.1 --port 8080
```

Provide `FLATNOTES_PATH` and the authentication environment variables
through your process supervisor (for example, systemd).

## Consistent backups

Stop the application for a simple, consistent filesystem copy,
particularly because SQLite can have transient journal/WAL files.
An online backup requires a SQLite-aware backup procedure or
filesystem snapshot with appropriate database consistency.

Back up:

- Ordinary Markdown files and all `.md.enc` encrypted notes.
- The full `attachments/` directory for ordinary notes.
- `.flatnotes-publications.db` with a SQLite-consistent method.
- The deployment configuration and **separately secured** secrets.

`.flatnotes/` contains a regenerable Whoosh index. You can omit it
from a stopped-instance backup and let the application regenerate it.
Never confuse it with the persistent `.flatnotes-publications.db`.

Restore into a writable `FLATNOTES_PATH` with permissions matching
`PUID`/`PGID`, start the application and verify both a known
ordinary note and a known encrypted note using its real password.
A copied encrypted file is useless if its password was lost.

## Migration to encryption

**Protect** is available in the ordinary editor during both editing
and viewing, even for a new unsaved note. A new draft is encrypted
locally and written directly to a `.md.enc` file; no plaintext
`.md` file is created on the server. A staged expiration policy
is applied and any staged publication is attempted after saving.

For an existing ordinary note, Protect can encrypt the current unsaved
editor changes. The server verifies the original file's modification
time, saves ciphertext, removes the existing plaintext file,
revokes the old public link and updates the search index.
An existing timed expiration is transferred without restarting its
deadline. Conversion does not securely erase historical plaintext
from browser drafts, backups or storage snapshots.

Test on a disposable note before migrating confidential material.

## Expiration cleanup and recovery

When `FLATNOTES_EXPIRATION_ENABLED=true`, notes can be configured
to expire after hours, days or one authorized view. Previously
configured rules remain enforced even if the switch is turned off.
SQLite stores the rules in `note_expirations`, inside
`.flatnotes-publications.db`. The `note_view_sessions`
table retains short-lived attachment tokens for consumed
ordinary notes.

The server checks policies synchronously on API access.
At startup and about every 60 seconds, a cleanup pass
deletes terminal note files, revokes publications, updates
the search index and conservatively removes orphaned
ordinary attachments. Terminal metadata is retained to
distinguish consumed or expired notes.

For safe backups, stop the service or take a consistent
SQLite snapshot. Expiration is not secure erasure of old
backups, snapshots, previously downloaded content or
filesystem blocks. Apply backup retention independently.

See [Expiring Notes](https://github.com/erathaowl/flatnotes/wiki/Expiring-Notes).

## Monitoring and troubleshooting

Use `docker compose logs` for application startup diagnostics.
Never post live credentials or TOTP enrollment secrets from logs.

Relevant problems: [Troubleshooting](https://github.com/erathaowl/flatnotes/wiki/Troubleshooting).
Implementation boundaries: [Security and Cryptography](https://github.com/erathaowl/flatnotes/wiki/Security-and-Cryptography).

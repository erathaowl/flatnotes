#!/usr/bin/env bash
set -euo pipefail

archive="$(find dist -maxdepth 1 -name 'flatnotes-*.tar.gz' -print -quit)"
if [[ -z "$archive" ]]; then
  echo "Application archive not found." >&2
  exit 1
fi

archive_contents="$(tar -tzf "$archive")"

for file in \
  "flatnotes/README.md" \
  "flatnotes/readme-it.md" \
  "flatnotes/wiki/Home.md" \
  "flatnotes/wiki/Encrypted-Notes.md" \
  "flatnotes/wiki/API-Reference.md" \
  "flatnotes/wiki/Security-and-Cryptography.md" \
  "flatnotes/wiki/Operations-and-Backup.md"; do
  if ! grep -Fxq "$file" <<< "$archive_contents"; then
    echo "Missing release documentation: $file" >&2
    exit 1
  fi
done

echo "Application archive includes English, Italian and wiki documentation."

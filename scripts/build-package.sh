#!/usr/bin/env bash
set -euo pipefail

version="${1:?Usage: build-package.sh VERSION}"
output_dir="${2:-dist}"
staging_dir="$(mktemp -d)"
trap 'rm -rf "$staging_dir"' EXIT

if [[ ! -f client/dist/index.html ]]; then
  echo "Build the frontend with 'npm run build' first." >&2
  exit 1
fi

mkdir -p "$staging_dir/flatnotes/client" "$output_dir"
cp -R server "$staging_dir/flatnotes/server"
cp -R client/dist "$staging_dir/flatnotes/client/dist"
cp pyproject.toml uv.lock .python-version README.md readme-it.md LICENSE "$staging_dir/flatnotes/"
cp -R wiki docs "$staging_dir/flatnotes/"

tar -czf "$output_dir/flatnotes-${version}.tar.gz" -C "$staging_dir" flatnotes

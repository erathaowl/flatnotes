#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f client/dist/index.html ]]; then
  echo "Build the frontend with 'npm run build' first." >&2
  exit 1
fi

mkdir -p server/web
rm -rf server/web/dist
cp -a client/dist server/web/dist

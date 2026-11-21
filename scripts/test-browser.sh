#!/usr/bin/env bash
set -euo pipefail

npm install --no-save --package-lock=false playwright@1.56.1
npx playwright install --with-deps chromium

export FLATNOTES_PATH="$(mktemp -d)"
export FLATNOTES_AUTH_TYPE=password
export FLATNOTES_USERNAME=smoke-user
export FLATNOTES_PASSWORD=smoke-password
export FLATNOTES_SECRET_KEY=smoke-test-only-signing-key
export FLATNOTES_ENCRYPTION_ENABLED=true
export FLATNOTES_SHARING_ENABLED=true
export FLATNOTES_TEST_URL=http://127.0.0.1:18080

uv run --locked --no-dev python -m uvicorn flatnotes.main:app --host 127.0.0.1 --port 18080 > browser-server.log 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true; rm -rf "$FLATNOTES_PATH"' EXIT

for attempt in $(seq 1 40); do
    if curl --fail --silent "$FLATNOTES_TEST_URL/health" > /dev/null; then
        node scripts/test-browser.mjs
        exit 0
    fi
    sleep 1
done

cat browser-server.log >&2
exit 1

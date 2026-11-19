#!/usr/bin/env bash
set -euo pipefail

wheel="$(find dist -maxdepth 1 -name 'flatnotes-*.whl' -print -quit)"
if [[ -z "$wheel" ]]; then
  echo "Build the flatnotes wheel first." >&2
  exit 1
fi
wheel="$(realpath "$wheel")"

test_dir="$(mktemp -d)"
trap 'rm -rf "$test_dir"' EXIT

uv venv --python 3.13 "$test_dir/venv"
uv pip install --python "$test_dir/venv/bin/python" "$wheel" httpx

# Import the installed package from outside the repository.
mkdir -p "$test_dir/data"
(
  cd "$test_dir"
  export FLATNOTES_PATH="$test_dir/data"
  export FLATNOTES_AUTH_TYPE=none
  "$test_dir/venv/bin/flatnotes" --help >/dev/null

  "$test_dir/venv/bin/python" - <<'PY'
from importlib.metadata import version

from fastapi.testclient import TestClient

from flatnotes.main import FRONTEND_DIR, app

assert version("flatnotes") == "6.0.0"
assert (FRONTEND_DIR / "index.html").is_file()
assets = list((FRONTEND_DIR / "assets").rglob("*.js"))
assert assets, "The wheel does not contain compiled frontend assets"

client = TestClient(app)
assert client.get("/health").status_code == 200
assert client.get("/").status_code == 200
assert client.get("/login").status_code == 200
assert client.get("/api/config").status_code == 200
asset_path = assets[0].relative_to(FRONTEND_DIR).as_posix()
assert client.get("/" + asset_path).status_code == 200
print("Wheel install, CLI, API, and static frontend smoke tests passed.")
PY
)

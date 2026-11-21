#!/usr/bin/env bash
set -euo pipefail

tag="${1:-}"

# Keep the tag compatible with the seven-day GHCR cleanup marker.
if [[ ! "$tag" =~ ^[a-z0-9_][a-z0-9_.-]{0,79}$ ]]; then
    echo "Invalid custom tag: use 1-80 lowercase letters, digits, dots, hyphens or underscores." >&2
    exit 1
fi

# Release and production tags belong to their dedicated workflows.
case "$tag" in
    master|latest|sha-*|dev-*|v[0-9]*)
        echo "Reserved Docker tag: $tag" >&2
        exit 1
        ;;
esac

printf '%s\n' "$tag"

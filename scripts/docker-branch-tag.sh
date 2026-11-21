#!/usr/bin/env bash
set -euo pipefail

branch="${1:?Branch name is required}"
tag="$(printf '%s' "$branch" | LC_ALL=C tr '[:upper:]' '[:lower:]' |
    sed -E 's/[^a-z0-9_.-]+/-/g; s/^[^a-z0-9_]+//; s/[-.]+$//')"
tag="${tag:0:70}"
[[ -n "$tag" ]] || tag="branch"

# Keep simple names intact, and disambiguate names requiring normalization.
if [[ "$branch" != "$tag" ]]; then
    suffix="$(printf '%s' "$branch" | sha256sum | cut -c1-8)"
    tag="${tag:0:60}-$suffix"
fi

# Development branches must never overwrite production or release tags.
case "$tag" in
    master|latest|sha-*|dev-*|v[0-9]*) tag="branch-$tag" ;;
esac

printf '%s\n' "$tag"

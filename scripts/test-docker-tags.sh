#!/usr/bin/env bash
set -euo pipefail

tag() {
    bash scripts/docker-branch-tag.sh "$1"
}

[[ "$(tag refactor)" == "refactor" ]]
[[ "$(tag feature/login)" =~ ^feature-login-[0-9a-f]{8}$ ]]
[[ "$(tag FEATURE/Login)" =~ ^feature-login-[0-9a-f]{8}$ ]]
[[ "$(tag latest)" == "branch-latest" ]]
[[ "$(tag sha-abc)" == "branch-sha-abc" ]]
[[ "$(tag dev-branch)" == "branch-dev-branch" ]]
[[ "$(tag v6.5.0)" == "branch-v6.5.0" ]]
[[ "$(tag 'x/y')" != "$(tag 'x-y')" ]]

long_name="$(printf 'a%.0s' {1..150})"
[[ "${#long_name}" -gt 128 ]]
[[ "$(tag "$long_name")" =~ ^[a-z0-9_.-]{1,128}$ ]]

echo "Docker branch tag rules passed."

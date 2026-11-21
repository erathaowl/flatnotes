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

custom_tag() {
    bash scripts/docker-custom-tag.sh "$1"
}

[[ "$(custom_tag refactor-test)" == "refactor-test" ]]
[[ "$(custom_tag test_1.2)" == "test_1.2" ]]
[[ "$(custom_tag "$(printf 'a%.0s' {1..80})")" == "$(printf 'a%.0s' {1..80})" ]]

for invalid in "" "feature/test" "Test" "two words" "master" "latest" "sha-abc" "dev-test" "v6.4.0" "$(printf 'a%.0s' {1..81})"; do
    if custom_tag "$invalid" > /dev/null 2>&1; then
        echo "Unexpectedly accepted an invalid or reserved Docker tag: $invalid" >&2
        exit 1
    fi
done

echo "Docker branch and custom tag rules passed."

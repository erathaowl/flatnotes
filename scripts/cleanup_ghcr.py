"""Remove GHCR development image versions older than seven days."""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

DEV_TAG = re.compile(r"^dev-([a-z0-9_][a-z0-9_.-]{0,79})-([0-9a-f]{40})$")
RETENTION_DAYS = 7


def is_expired_development_version(version, cutoff):
    tags = version.get("metadata", {}).get("container", {}).get("tags", [])
    if not isinstance(tags, list):
        return False

    markers = [(tag, DEV_TAG.fullmatch(tag)) for tag in tags]
    markers = [(tag, match) for tag, match in markers if match]
    if len(markers) != 1:
        return False

    marker, match = markers[0]
    branch_tag = match.group(1)
    if any(tag not in (marker, branch_tag) for tag in tags):
        return False

    created_at = version.get("created_at", "")
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return created.tzinfo is not None and created <= cutoff


def request_api(url, token, method="GET"):
    request = Request(
        url,
        method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=30) as response:
        body = response.read()
        links = response.headers.get("Link", "")
    return json.loads(body) if body else None, links


def list_versions(package_url, token):
    url = package_url + "/versions?per_page=100"
    while url:
        versions, links = request_api(url, token)
        yield from versions
        url = None
        for part in links.split(","):
            match = re.search(r'<([^>]+)>;\s*rel="next"', part)
            if match:
                if not match.group(1).startswith(package_url + "/versions?"):
                    raise ValueError("Unexpected package pagination URL")
                url = match.group(1)
                break


def main():
    token = os.environ["GH_TOKEN"]
    owner, package = os.environ["GITHUB_REPOSITORY"].split("/", 1)
    owner_type = os.environ["GHCR_OWNER_TYPE"]
    if owner_type not in ("User", "Organization"):
        raise ValueError("Unknown GitHub package owner type")
    prefix = "users" if owner_type == "User" else "orgs"
    package_url = (
        "https://api.github.com/" + prefix + "/" + quote(owner, safe="")
        + "/packages/container/" + quote(package, safe="")
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    removed = 0
    for version in list_versions(package_url, token):
        if not is_expired_development_version(version, cutoff):
            continue
        tags = version["metadata"]["container"]["tags"]
        identifier = version["id"]
        print(f"{'Would delete' if dry_run else 'Deleting'} GHCR version {identifier}: {tags}", flush=True)
        if not dry_run:
            request_api(package_url + f"/versions/{identifier}", token, method="DELETE")
        removed += 1

    print(f"{removed} expired development image versions {'matched' if dry_run else 'deleted'}.")


if __name__ == "__main__":
    main()

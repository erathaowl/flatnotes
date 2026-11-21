"""Safety checks for GitHub Container Registry development-image cleanup."""

import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path


script_path = Path(__file__).resolve().parents[1] / "scripts" / "cleanup_ghcr.py"
spec = importlib.util.spec_from_file_location("cleanup_ghcr", script_path)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class DevelopmentImageCleanupTests(unittest.TestCase):
    cutoff = datetime(2026, 11, 14, tzinfo=timezone.utc)
    marker = "dev-refactor-" + "a" * 40

    def version(self, tags, created_at="2026-11-10T00:00:00Z"):
        return {
            "created_at": created_at,
            "metadata": {"container": {"tags": tags}},
        }

    def test_expired_branch_version_is_selected(self):
        for tags in ([self.marker], ["refactor", self.marker]):
            with self.subTest(tags=tags):
                self.assertTrue(cleanup.is_expired_development_version(
                    self.version(tags), self.cutoff
                ))

    def test_recent_branch_version_is_kept(self):
        self.assertFalse(cleanup.is_expired_development_version(
            self.version([self.marker], "2026-11-20T00:00:00Z"),
            self.cutoff,
        ))

    def test_production_and_release_tags_are_never_deleted(self):
        for protected in ("master", "latest", "sha-" + "b" * 7, "v6.4.0"):
            with self.subTest(protected=protected):
                self.assertFalse(cleanup.is_expired_development_version(
                    self.version(["refactor", self.marker, protected]),
                    self.cutoff,
                ))

    def test_versions_without_unique_dev_marker_are_kept(self):
        for tags in (
            [],
            ["refactor"],
            ["latest"],
            ["sha-" + "a" * 7],
            ["dev-refactor-short"],
            [self.marker, "different-branch"],
            [self.marker, "dev-other-" + "b" * 40],
        ):
            with self.subTest(tags=tags):
                self.assertFalse(cleanup.is_expired_development_version(
                    self.version(tags), self.cutoff,
                ))

    def test_unknown_or_unreliable_age_is_kept(self):
        for created in ("invalid", "", "2026-11-10T00:00:00"):
            with self.subTest(created=created):
                self.assertFalse(cleanup.is_expired_development_version(
                    self.version([self.marker], created),
                    self.cutoff,
                ))


if __name__ == "__main__":
    unittest.main()

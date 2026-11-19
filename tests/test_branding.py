import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flatnotes.global_config import GlobalConfig


class BrandingConfigTests(unittest.TestCase):
    def test_defaults_preserve_existing_branding(self):
        with patch.dict(os.environ, {}, clear=True):
            config = GlobalConfig()
        self.assertEqual(config.site_title, "flatnotes")
        self.assertIsNone(config.logo_path)
        self.assertIsNone(config.favicon_path)

    def test_custom_title_and_image_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            logo = Path(directory) / "logo.svg"
            favicon = Path(directory) / "favicon.ico"
            logo.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            favicon.write_bytes(b"test-icon")
            with patch.dict(os.environ, {
                "FLATNOTES_SITE_TITLE": "My Notes",
                "FLATNOTES_LOGO_PATH": str(logo),
                "FLATNOTES_FAVICON_PATH": str(favicon),
            }, clear=True):
                config = GlobalConfig()
            self.assertEqual(config.site_title, "My Notes")
            self.assertEqual(config.logo_path, str(logo))
            self.assertEqual(config.favicon_path, str(favicon))

    def test_invalid_logo_path_fails_at_startup(self):
        with patch.dict(os.environ, {
            "FLATNOTES_LOGO_PATH": "relative-logo.svg",
        }, clear=True):
            with self.assertRaises(SystemExit):
                GlobalConfig()

    def test_unsupported_favicon_format_fails_at_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            icon = Path(directory) / "favicon.html"
            icon.write_text("<html></html>")
            with patch.dict(os.environ, {
                "FLATNOTES_FAVICON_PATH": str(icon),
            }, clear=True):
                with self.assertRaises(SystemExit):
                    GlobalConfig()


if __name__ == "__main__":
    unittest.main()

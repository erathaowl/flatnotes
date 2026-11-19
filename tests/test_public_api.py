import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))


class PublicApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.previous_directory = os.getcwd()
        os.chdir(cls.directory.name)
        Path("client/dist").mkdir(parents=True)
        Path("client/dist/index.html").write_text(
            '<html><head><base href="/"></head><body>flatnotes</body></html>',
            encoding="utf-8",
        )
        Path("data").mkdir()
        os.environ.update({
            "FLATNOTES_PATH": str(Path("data").resolve()),
            "FLATNOTES_AUTH_TYPE": "password",
            "FLATNOTES_USERNAME": "test-user",
            "FLATNOTES_PASSWORD": "test-password",
            "FLATNOTES_SECRET_KEY": "test-only-secret-key",
        })

        import main

        cls.client = TestClient(main.app)
        token = cls.client.post(
            "/api/token",
            json={"username": "test-user", "password": "test-password"},
        )
        assert token.status_code == 200, token.text
        cls.headers = {"Authorization": "Bearer " + token.json()["access_token"]}

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        os.chdir(cls.previous_directory)
        cls.directory.cleanup()

    def create_note(self, title, content):
        result = self.client.post(
            "/api/notes",
            json={"title": title, "content": content},
            headers=self.headers,
        )
        self.assertEqual(result.status_code, 200, result.text)

    def publish(self, title, mode="random", permission="read", slug=None):
        result = self.client.put(
            "/api/notes/" + title + "/publication",
            json={"slugMode": mode, "permission": permission, "slug": slug},
            headers=self.headers,
        )
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_branding_defaults_and_custom_assets(self):
        import main

        default_config = self.client.get("/api/config")
        self.assertEqual(default_config.status_code, 200)
        self.assertEqual(default_config.json()["siteTitle"], "flatnotes")
        self.assertIsNone(default_config.json()["logoUrl"])
        self.assertIsNone(default_config.json()["faviconUrl"])
        self.assertEqual(self.client.get("/api/branding/logo").status_code, 404)
        self.assertEqual(self.client.get("/api/branding/favicon").status_code, 404)

        logo = Path("data/custom-logo.svg")
        icon = Path("data/custom-icon.png")
        logo.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        icon.write_bytes(b"png-content")
        with (
            patch.object(main.global_config, "site_title", "Fabio's <Notes>"),
            patch.object(main.global_config, "logo_path", str(logo.resolve())),
            patch.object(main.global_config, "favicon_path", str(icon.resolve())),
        ):
            config = self.client.get("/api/config").json()
            self.assertEqual(config["siteTitle"], "Fabio's <Notes>")
            self.assertEqual(config["logoUrl"], "api/branding/logo")
            self.assertEqual(config["faviconUrl"], "api/branding/favicon")

            page = self.client.get("/")
            self.assertIn("<title>Fabio&#x27;s &lt;Notes&gt;</title>", page.text)

            image = self.client.get("/api/branding/logo")
            self.assertEqual(image.status_code, 200)
            self.assertEqual(image.headers["content-type"], "image/svg+xml")
            self.assertEqual(image.headers["x-content-type-options"], "nosniff")
            self.assertEqual(image.content, logo.read_bytes())

            favicon = self.client.get("/api/branding/favicon")
            self.assertEqual(favicon.status_code, 200)
            self.assertEqual(favicon.headers["content-type"], "image/png")
            self.assertEqual(favicon.content, icon.read_bytes())

    def test_private_note_is_not_public(self):
        self.create_note("Private", "Private content")
        self.assertEqual(self.client.get("/api/notes/Private").status_code, 401)
        self.assertEqual(self.client.get("/api/search?term=Private").status_code, 401)
        self.assertEqual(self.client.get("/api/public/notes/private").status_code, 404)
        page = self.client.get("/p/example")
        self.assertEqual(page.status_code, 200)
        self.assertIn("script-src 'self'", page.headers["content-security-policy"])
        self.assertEqual(page.headers["referrer-policy"], "no-referrer")

    def test_public_read_edit_conflicts_and_revocation(self):
        self.create_note("Shared", "Initial")
        publication = self.publish("Shared", mode="custom", slug="hello-world")
        self.assertEqual(publication["slug"], "hello-world")
        response = self.client.get("/api/public/notes/hello-world")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "Initial")
        self.assertEqual(response.headers["cache-control"], "no-store")
        revision = response.json()["revision"]

        readonly = self.client.patch(
            "/api/public/notes/hello-world",
            json={"newContent": "Changed", "revision": revision},
        )
        self.assertEqual(readonly.status_code, 403)

        self.publish("Shared", mode="custom", permission="edit", slug="hello-world")
        update = self.client.patch(
            "/api/public/notes/hello-world",
            json={"newContent": "Changed", "revision": revision},
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["content"], "Changed")
        stale = self.client.patch(
            "/api/public/notes/hello-world",
            json={"newContent": "Stale", "revision": revision},
        )
        self.assertEqual(stale.status_code, 409)

        renamed = self.client.patch(
            "/api/notes/Shared",
            json={"newTitle": "Renamed"},
            headers=self.headers,
        )
        self.assertEqual(renamed.status_code, 200, renamed.text)
        current = self.client.get("/api/public/notes/hello-world")
        self.assertEqual(current.json()["title"], "Renamed")
        self.assertEqual(self.client.get("/api/notes/Renamed").status_code, 401)

        revoked = self.client.delete(
            "/api/notes/Renamed/publication", headers=self.headers
        )
        self.assertEqual(revoked.status_code, 204)
        self.assertEqual(self.client.get("/api/public/notes/hello-world").status_code, 404)

    def test_attachments_cannot_be_exposed_by_public_edits(self):
        Path("data/attachments").mkdir(exist_ok=True)
        Path("data/attachments/public.png").write_bytes(b"public image")
        Path("data/attachments/secret.png").write_bytes(b"private image")
        self.create_note("WithImages", "![x](attachments/public.png)")
        self.publish("WithImages", mode="custom", permission="edit", slug="images")

        self.assertEqual(
            self.client.get("/api/public/notes/images/attachments/public.png").status_code,
            200,
        )
        self.assertEqual(
            self.client.get("/api/public/notes/images/attachments/secret.png").status_code,
            404,
        )
        current = self.client.get("/api/public/notes/images").json()
        changed = self.client.patch(
            "/api/public/notes/images",
            json={
                "newContent": "![x](attachments/secret.png)",
                "revision": current["revision"],
            },
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(
            self.client.get("/api/public/notes/images/attachments/secret.png").status_code,
            404,
        )
        self.assertEqual(
            self.client.get("/api/attachments/secret.png").status_code, 401
        )

    def test_duplicate_slugs_rejected(self):
        self.create_note("First", "first")
        self.create_note("Second", "second")
        self.publish("First", mode="custom", slug="unique")
        duplicate = self.client.put(
            "/api/notes/Second/publication",
            json={"slugMode": "custom", "slug": "unique", "permission": "read"},
            headers=self.headers,
        )
        self.assertEqual(duplicate.status_code, 409)


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


class PublicApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.previous_directory = os.getcwd()
        os.chdir(cls.directory.name)
        Path("client/dist").mkdir(parents=True)
        Path("client/dist/index.html").write_text(
            '<html><head><base href="/"><title>flatnotes</title></head><body>flatnotes</body></html>',
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

        from flatnotes import main

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
        from flatnotes import main

        default_config = self.client.get("/api/config")
        self.assertEqual(default_config.status_code, 200)
        self.assertEqual(default_config.json()["siteTitle"], "flatnotes")
        self.assertEqual(default_config.json()["encryptionPasswordMinLength"], 12)
        self.assertEqual(default_config.json()["encryptionPasswordMinClasses"], 0)
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

    def test_feature_flags_and_opaque_encrypted_routes(self):
        from flatnotes import main

        note_id = "a1b2" * 8
        data = b'{"version":1,"wrappedKey":"ciphertext-only"}'
        with (
            patch.object(main.global_config, "encryption_enabled", False),
            patch.object(main.global_config, "sharing_enabled", False),
        ):
            config = self.client.get("/api/config").json()
            self.assertFalse(config["encryptionEnabled"])
            self.assertFalse(config["sharingEnabled"])
            self.assertEqual(self.client.get("/api/public/notes/not-found").status_code, 404)
            self.assertEqual(
                self.client.put(
                    "/api/encrypted-notes/" + note_id,
                    content=data,
                    headers={**self.headers, "X-Revision": "*"},
                ).status_code,
                403,
            )

        with patch.object(main.global_config, "encryption_enabled", True):
            created = self.client.put(
                "/api/encrypted-notes/" + note_id,
                content=data,
                headers={**self.headers, "X-Revision": "*"},
            )
            self.assertEqual(created.status_code, 200, created.text)
            self.assertNotIn("password", created.text.lower())
            self.assertTrue(Path("data/" + note_id + ".md.enc").is_file())
            self.assertEqual(
                self.client.get("/api/encrypted-notes/" + note_id).status_code,
                401,
            )
            fetched = self.client.get(
                "/api/encrypted-notes/" + note_id, headers=self.headers
            )
            self.assertEqual(fetched.content, data)
            self.assertEqual(fetched.headers["x-revision"], created.json()["revision"])
            self.assertEqual(fetched.headers["cache-control"], "no-store")
            self.assertEqual(
                self.client.put(
                    "/api/encrypted-notes/" + note_id,
                    content=b"modified",
                    headers={**self.headers, "X-Revision": "old"},
                ).status_code,
                409,
            )
            self.assertEqual(
                self.client.put(
                    "/api/encrypted-notes/" + note_id + "/publication",
                    json={"slugMode": "random", "permission": "read"},
                    headers=self.headers,
                ).status_code,
                200,
            )
            publication = self.client.get(
                "/api/encrypted-notes/" + note_id + "/publication",
                headers=self.headers,
            ).json()
            slug = publication["slug"]
            public = self.client.get("/api/public/encrypted-notes/" + slug)
            self.assertEqual(public.content, data)
            self.assertEqual(public.headers["x-edit-permission"], "read")
            self.assertEqual(
                self.client.put(
                    "/api/public/encrypted-notes/" + slug,
                    content=b"malicious",
                    headers={"X-Revision": created.json()["revision"]},
                ).status_code,
                405,
            )
            with patch.object(main.global_config, "sharing_enabled", False):
                self.assertEqual(
                    self.client.get("/api/public/encrypted-notes/" + slug).status_code,
                    404,
                )

        self.assertEqual(
            self.client.delete(
                "/api/encrypted-notes/" + note_id, headers=self.headers
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.get("/api/public/encrypted-notes/" + slug).status_code,
            404,
        )

    def test_protection_migration_removes_plaintext_and_revokes_link(self):
        from flatnotes import main

        title = "ConvertExisting"
        secret = "Sensitive project document"
        self.create_note(title, secret)
        initial = self.client.get("/api/notes/" + title, headers=self.headers).json()
        publication = self.publish(title, "custom", "read", "converted-note")
        note_id = "fe12" * 8

        with patch.object(main.global_config, "encryption_enabled", True):
            stale = self.client.post(
                "/api/encrypted-notes/protect/" + title + "/" + note_id,
                content=b"encrypted-document",
                headers={**self.headers, "X-Source-Modified": "0"},
            )
            self.assertEqual(stale.status_code, 409)
            self.assertTrue(Path("data/" + title + ".md").exists())

            protected = self.client.post(
                "/api/encrypted-notes/protect/" + title + "/" + note_id,
                content=b"encrypted-document",
                headers={
                    **self.headers,
                    "X-Source-Modified": str(initial["lastModified"]),
                },
            )
            self.assertEqual(protected.status_code, 200, protected.text)

        encrypted_path = Path("data/" + note_id + ".md.enc")
        self.assertEqual(encrypted_path.read_bytes(), b"encrypted-document")
        self.assertNotIn(secret.encode(), encrypted_path.read_bytes())
        self.assertFalse(Path("data/" + title + ".md").exists())
        self.assertEqual(
            self.client.get("/api/notes/" + title, headers=self.headers).status_code,
            404,
        )
        self.assertEqual(
            self.client.get("/api/public/notes/" + publication["slug"]).status_code,
            404,
        )
        self.assertFalse(
            any(result["title"] == title for result in self.client.get(
                "/api/search?term=Sensitive", headers=self.headers
            ).json())
        )

    def test_sharing_flag_blocks_all_plaintext_publication_routes(self):
        from flatnotes import main

        self.create_note("PrivateWhenDisabled", "Secret markdown")
        publication = self.publish(
            "PrivateWhenDisabled", "custom", "edit", "sharing-toggle",
        )
        slug = publication["slug"]
        with patch.object(main.global_config, "sharing_enabled", False):
            self.assertEqual(
                self.client.get("/api/notes/PrivateWhenDisabled/publication", headers=self.headers).status_code,
                404,
            )
            self.assertEqual(
                self.client.put(
                    "/api/notes/PrivateWhenDisabled/publication",
                    json={"slugMode": "random", "permission": "read"},
                    headers=self.headers,
                ).status_code,
                404,
            )
            self.assertEqual(
                self.client.delete(
                    "/api/notes/PrivateWhenDisabled/publication", headers=self.headers,
                ).status_code,
                404,
            )
            self.assertEqual(self.client.get("/api/public/notes/" + slug).status_code, 404)
            self.assertEqual(
                self.client.patch(
                    "/api/public/notes/" + slug,
                    json={"newContent": "changed", "revision": "0" * 64},
                ).status_code,
                404,
            )
            self.assertEqual(
                self.client.get("/api/public/notes/" + slug + "/attachments/example.png").status_code,
                404,
            )
        self.assertEqual(self.client.get("/api/public/notes/" + slug).status_code, 200)

    def test_public_edit_respects_instance_read_only(self):
        from flatnotes import main

        title = "ReadOnlyPublicWrite"
        self.create_note(title, "original content")
        slug = self.publish(title, permission="edit")["slug"]
        url = "/api/public/notes/" + slug
        original = self.client.get(url)
        self.assertEqual(original.status_code, 200, original.text)
        self.assertEqual(original.json()["permission"], "edit")

        with patch.object(main.global_config, "auth_type", main.AuthType.READ_ONLY):
            public = self.client.get(url)
            self.assertEqual(public.status_code, 200, public.text)
            self.assertEqual(public.json()["permission"], "read")
            blocked = self.client.patch(
                url,
                json={
                    "newContent": "unauthorized content",
                    "revision": original.json()["revision"],
                },
            )
            self.assertEqual(blocked.status_code, 403, blocked.text)
            unchanged = self.client.get("/api/notes/" + title, headers=self.headers)
            self.assertEqual(unchanged.json()["content"], "original content")

        allowed = self.client.patch(
            url,
            json={"newContent": "authorized public edit", "revision": original.json()["revision"]},
        )
        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertEqual(allowed.json()["content"], "authorized public edit")

    def test_encrypted_public_edit_is_not_available(self):
        from flatnotes import main

        note_id = "aabb" * 8
        original = b"opaque encrypted envelope"
        with patch.object(main.global_config, "encryption_enabled", True):
            created = self.client.put(
                "/api/encrypted-notes/" + note_id,
                content=original,
                headers={**self.headers, "X-Revision": "*"},
            )
            self.assertEqual(created.status_code, 200, created.text)
            denied = self.client.put(
                "/api/encrypted-notes/" + note_id + "/publication",
                json={"slugMode": "random", "permission": "edit"},
                headers=self.headers,
            )
            self.assertEqual(denied.status_code, 422, denied.text)
            self.assertIsNone(self.client.get(
                "/api/encrypted-notes/" + note_id + "/publication",
                headers=self.headers,
            ).json())
            published = self.client.put(
                "/api/encrypted-notes/" + note_id + "/publication",
                json={"slugMode": "random", "permission": "read"},
                headers=self.headers,
            )
            self.assertEqual(published.status_code, 200, published.text)
            slug = published.json()["slug"]
            url = "/api/public/encrypted-notes/" + slug
            public = self.client.get(url)
            self.assertEqual(public.status_code, 200, public.text)
            self.assertEqual(public.headers["x-edit-permission"], "read")
            with patch.object(main.global_config, "auth_type", main.AuthType.READ_ONLY):
                rejected = self.client.put(
                    url, content=b"malicious",
                    headers={"X-Revision": created.json()["revision"]},
                )
                self.assertEqual(rejected.status_code, 405, rejected.text)
                self.assertEqual(self.client.get(url).content, original)
            updated = self.client.put(
                "/api/encrypted-notes/" + note_id,
                content=b"owner update",
                headers={**self.headers, "X-Revision": created.json()["revision"]},
            )
            self.assertEqual(updated.status_code, 200, updated.text)
            self.assertEqual(self.client.get(url).content, b"owner update")

    def test_private_read_does_not_consume_public_single_view(self):
        self.create_note("OneViewPlain", "sensitive text")
        published = self.client.put(
            "/api/notes/OneViewPlain/publication",
            json={"expiration": "once", "slugMode": "random", "permission": "read"},
            headers=self.headers,
        )
        self.assertEqual(published.status_code, 200, published.text)
        slug = published.json()["slug"]
        private = self.client.get("/api/notes/OneViewPlain", headers=self.headers)
        self.assertEqual(private.status_code, 200)
        self.assertEqual(private.json()["content"], "sensitive text")
        search = self.client.get(
            "/api/search", params={"term": "sensitive"}, headers=self.headers
        ).json()
        self.assertIn("OneViewPlain", [item["title"] for item in search])
        first = self.client.get("/api/public/notes/" + slug)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertTrue(first.json()["viewToken"])
        self.assertEqual(self.client.get("/api/public/notes/" + slug).status_code, 410)
        self.assertEqual(
            self.client.get("/api/notes/OneViewPlain", headers=self.headers).status_code,
            200,
        )

    def test_public_plain_single_view_and_attachment_guard(self):
        self.create_note("PublicOnce", "public single view")
        publication = self.client.put(
            "/api/notes/PublicOnce/publication",
            json={
                "slugMode": "custom", "permission": "read", "slug": "public-once",
                "expiration": "once", "autoDeleteNote": False,
            },
            headers=self.headers,
        )
        self.assertEqual(publication.status_code, 200, publication.text)
        slug = publication.json()["slug"]
        self.assertEqual(
            self.client.get(
                "/api/public/notes/" + slug + "/attachments/file.png"
            ).status_code, 410
        )
        first = self.client.get("/api/public/notes/" + slug)
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["viewToken"])
        self.assertEqual(self.client.get("/api/public/notes/" + slug).status_code, 410)
        self.assertEqual(self.client.get("/api/notes/PublicOnce", headers=self.headers).status_code, 200)

    def test_encrypted_public_single_view_proof_without_private_consumption(self):
        from flatnotes import main
        import hashlib

        note_id = "3f2b" * 8
        proof = bytes.fromhex("42" * 32)
        verifier = hashlib.sha256(proof).hexdigest()
        with patch.object(main.global_config, "encryption_enabled", True):
            created = self.client.put(
                "/api/encrypted-notes/" + note_id,
                content=b"opaque ciphertext bytes",
                headers={**self.headers, "X-Revision": "*"},
            )
            self.assertEqual(created.status_code, 200, created.text)
            published = self.client.put(
                "/api/encrypted-notes/" + note_id + "/publication",
                json={
                    "slugMode": "random", "permission": "read",
                    "expiration": "once", "viewVerifier": verifier,
                },
                headers=self.headers,
            )
            self.assertEqual(published.status_code, 200, published.text)
            slug = published.json()["slug"]
            private = self.client.get(
                "/api/encrypted-notes/" + note_id, headers=self.headers
            )
            self.assertEqual(private.status_code, 200)
            self.assertNotIn("x-expiration-mode", private.headers)
            public = self.client.get("/api/public/encrypted-notes/" + slug)
            self.assertEqual(public.status_code, 200)
            self.assertEqual(public.headers["x-expiration-mode"], "once")
            invalid = self.client.post(
                "/api/public/encrypted-notes/" + slug + "/view",
                json={"proof": "00" * 32},
            )
            self.assertEqual(invalid.status_code, 403)
            with patch.object(main.global_config, "auth_type", main.AuthType.READ_ONLY):
                consumed = self.client.post(
                    "/api/public/encrypted-notes/" + slug + "/view",
                    json={"proof": proof.hex()},
                )
            self.assertEqual(consumed.status_code, 200, consumed.text)
            self.assertEqual(
                self.client.get("/api/public/encrypted-notes/" + slug).status_code,
                410,
            )
            self.assertEqual(
                self.client.get(
                    "/api/encrypted-notes/" + note_id, headers=self.headers
                ).status_code, 200,
            )

    def test_encrypted_listing_direct_url(self):
        response = self.client.get("/encrypted")
        self.assertEqual(response.status_code, 200)
        self.assertIn('<div id="app"', response.text)

    def test_delete_encrypted_note_without_unlocking(self):
        from flatnotes import main

        note_id = "9abc" * 8
        with patch.object(main.global_config, "encryption_enabled", True):
            created = self.client.put(
                "/api/encrypted-notes/" + note_id,
                content=b"opaque encrypted data",
                headers={**self.headers, "X-Revision": "*"},
            )
            self.assertEqual(created.status_code, 200, created.text)

        # Deletion needs the account token, but never a note password.
        self.assertEqual(
            self.client.delete("/api/encrypted-notes/" + note_id).status_code, 401
        )
        deleted = self.client.delete(
            "/api/encrypted-notes/" + note_id, headers=self.headers
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(
            self.client.get("/api/encrypted-notes/" + note_id, headers=self.headers).status_code,
            404,
        )

    def test_encrypted_html_security_headers(self):
        response = self.client.get("/e/" + "ab12" * 8)
        self.assertEqual(response.status_code, 200)
        policy = response.headers["content-security-policy"]
        self.assertIn("wasm-unsafe-eval", policy)
        self.assertNotIn("'unsafe-inline'", policy.split("script-src ", 1)[1].split(";", 1)[0])
        self.assertIn("img-src 'self' data: blob:", policy)

    def test_anonymous_access_to_private_endpoints_is_rejected(self):
        for method, url, options in (
            ("GET", "/api/notes/PrivateAccess", {}),
            ("GET", "/api/search?term=PrivateAccess", {}),
            ("GET", "/api/tags", {}),
            ("GET", "/api/encrypted-notes", {}),
            ("GET", "/api/encrypted-notes/" + "ab12" * 8, {}),
            ("GET", "/api/attachments/private.svg", {}),
            ("POST", "/api/notes", {"json": {"title": "Unauthorized"}}),
            ("PATCH", "/api/notes/PrivateAccess", {"json": {"newContent": "bad"}}),
            ("DELETE", "/api/notes/PrivateAccess", {}),
            ("POST", "/api/attachments", {"files": {"file": ("bad.txt", b"bad")}}),
            ("PUT", "/api/encrypted-notes/" + "ab12" * 8, {"content": b"bad"}),
            ("DELETE", "/api/encrypted-notes/" + "ab12" * 8, {}),
        ):
            with self.subTest(method=method, url=url):
                response = self.client.request(method, url, **options)
                self.assertEqual(response.status_code, 401, response.text)

    def test_private_attachments_are_sandboxed(self):
        attachments = Path("data/attachments")
        attachments.mkdir(exist_ok=True)
        for name, content, inline in (
            ("private.svg", b'<svg onload="alert(1)"/>', False),
            ("private.html", b"<script>alert(1)</script>", False),
            ("private.png", b"test image", True),
        ):
            with self.subTest(name=name):
                (attachments / name).write_bytes(content)
                self.assertEqual(self.client.get("/api/attachments/" + name).status_code, 401)
                response = self.client.get("/api/attachments/" + name, headers=self.headers)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.headers["x-content-type-options"], "nosniff")
                self.assertIn("sandbox", response.headers["content-security-policy"])
                if inline:
                    self.assertNotIn("attachment", response.headers.get("content-disposition", ""))
                else:
                    self.assertIn("attachment", response.headers["content-disposition"])

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

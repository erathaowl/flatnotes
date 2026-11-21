"""Authentication and API-route smoke tests for the single-user deployment."""

import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from jose import JWTError, jwt

from flatnotes.auth.local import LocalAuth
from flatnotes.auth.local import local as auth_module
from flatnotes.auth.models import Login
from flatnotes.global_config import AuthType


class AuthenticationTests(unittest.TestCase):
    def build_auth(self, mode):
        environment = {
            "FLATNOTES_USERNAME": "owner",
            "FLATNOTES_PASSWORD": "account-password",
            "FLATNOTES_SECRET_KEY": "test-only-session-secret",
            "FLATNOTES_TOTP_KEY": "test-only-totp-secret",
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(auth_module.global_config, "auth_type", mode),
            patch.object(LocalAuth, "_display_totp_enrolment"),
        ):
            return LocalAuth()

    def test_password_login_and_signed_token(self):
        auth = self.build_auth(AuthType.PASSWORD)
        token = auth.login(Login(username="OWNER", password="account-password")).access_token
        self.assertIsNone(auth._validate_token(token))
        with self.assertRaises(ValueError):
            auth.login(Login(username="owner", password="wrong"))
        with self.assertRaises(JWTError):
            auth._validate_token(token + "invalid")

    def test_invalid_subject_and_expired_token(self):
        auth = self.build_auth(AuthType.PASSWORD)
        for payload in (
            {"sub": "intruder"},
            {"sub": "owner", "exp": 1},
        ):
            with self.subTest(payload=payload):
                token = jwt.encode(payload, auth.secret_key, algorithm="HS256")
                with self.assertRaises((ValueError, JWTError)):
                    auth._validate_token(token)

    def test_totp_code_is_required_and_not_reusable(self):
        auth = self.build_auth(AuthType.TOTP)
        valid = Login(
            username="owner",
            password="account-password" + auth.totp.now(),
        )
        token = auth.login(valid).access_token
        self.assertIsNone(auth._validate_token(token))
        with self.assertRaises(ValueError):
            auth.login(valid)
        with self.assertRaises(ValueError):
            auth.login(Login(username="owner", password="account-password"))

    def test_missing_token_is_rejected(self):
        auth = self.build_auth(AuthType.PASSWORD)
        with self.assertRaises(ValueError):
            auth._validate_token(None)


if __name__ == "__main__":
    unittest.main()

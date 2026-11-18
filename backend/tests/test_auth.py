import hashlib
import time
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.api.v1 import dashboard, login
from app.config import settings
from app.core.auth import auth_cache
from app.core.tenant_resolver import TenantResolver
from app.models.auth import AuthenticatedUser


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        auth_cache.clear()
        app = FastAPI()
        app.include_router(login.router, prefix="/api/v1")
        app.include_router(dashboard.router, prefix="/api/v1")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        auth_cache.clear()

    def token(self, **claims):
        payload = {
            "id": "test-user", "email": "sunset@propertyflow.com",
            "aud": "authenticated", "exp": int(time.time()) + 60,
            "app_metadata": {"tenant_id": "tenant-a"},
        }
        return jwt.encode({**payload, **claims}, settings.secret_key, algorithm="HS256")

    def summary(self, token=None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.get("/api/v1/dashboard/summary?property_id=prop-001", headers=headers)

    def test_missing_and_static_mock_tokens_are_rejected(self):
        self.assertEqual(self.summary().status_code, 401)
        self.assertEqual(self.summary("mock-token-123").status_code, 401)

    def test_wrong_signature_is_rejected(self):
        header, payload, signature = self.token().split(".")
        forged = f"{header}.{payload}.{'x' * len(signature)}"
        self.assertEqual(self.summary(forged).status_code, 401)

    def test_expired_token_is_rejected(self):
        self.assertEqual(self.summary(self.token(exp=int(time.time()) - 1)).status_code, 401)

    def test_cached_authentication_does_not_outlive_token(self):
        token = self.token(exp=int(time.time()) - 1)
        key = hashlib.sha256(token.encode()).hexdigest()[:16]
        auth_cache[key] = {
            "user": AuthenticatedUser(
                id="test-user", email="sunset@propertyflow.com", tenant_id="tenant-a",
                permissions=[], cities=[], is_admin=False,
            ),
            "timestamp": time.time(), "expires_at": time.time() - 1,
        }
        self.assertEqual(self.summary(token).status_code, 401)

    def test_unassigned_user_does_not_inherit_default_tenant(self):
        self.assertEqual(self.summary(self.token(app_metadata={}, email="unassigned@example.com")).status_code, 403)

    def test_user_metadata_cannot_override_tenant(self):
        claims = {"app_metadata": {"tenant_id": "tenant-a"}, "user_metadata": {"tenant_id": "tenant-b"}}
        self.assertEqual(TenantResolver.resolve_tenant_from_token(claims), "tenant-a")
        self.assertIsNone(TenantResolver.resolve_tenant_from_token({"user_metadata": {"tenant_id": "tenant-b"}}))

    def test_provided_accounts_accept_correct_password_only(self):
        for email, password, tenant in [
            ("sunset@propertyflow.com", "client_a_2024", "tenant-a"),
            ("ocean@propertyflow.com", "client_b_2024", "tenant-b"),
        ]:
            with self.subTest(email=email):
                response = self.client.post("/api/v1/auth/login", json={"email": email, "password": password})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["user"]["tenant_id"], tenant)
                invalid = self.client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
                self.assertEqual(invalid.status_code, 401)

    def test_legacy_account_cannot_login_with_arbitrary_password(self):
        response = self.client.post(
            "/api/v1/auth/login", json={"email": "candidate@propertyflow.com", "password": "anything"}
        )
        self.assertEqual(response.status_code, 401)

import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1 import dashboard
from app.core.auth import authenticate_request
from app.models.auth import AuthenticatedUser
from app.services.reservations import MixedCurrencyError, PropertyNotFoundError


class DashboardAPITests(unittest.TestCase):
    def setUp(self):
        self.user = AuthenticatedUser(
            id="test-user", email="sunset@propertyflow.com", tenant_id="tenant-a",
            permissions=[], cities=[], is_admin=False,
        )
        app = FastAPI()
        app.include_router(dashboard.router, prefix="/api/v1")
        app.dependency_overrides[authenticate_request] = lambda: self.user
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.summary = {
            "property_id": "prop-001", "tenant_id": "tenant-a",
            "total": "1.01", "currency": "USD", "count": 1,
            "timezone": "Europe/Paris", "month": 3, "year": 2024,
        }
        self.service = AsyncMock(return_value=self.summary)
        service_patch = patch.object(dashboard, "get_revenue_summary", self.service)
        service_patch.start()
        self.addCleanup(service_patch.stop)
        self.url = "/api/v1/dashboard/summary?property_id=prop-001&month=3&year=2024"

    def test_decimal_amount_is_returned_as_an_exact_string(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_revenue"], "1.01")
        self.assertEqual(response.json()["reservations_count"], 1)

    def test_client_header_cannot_choose_another_tenant(self):
        response = self.client.get(self.url, headers={"X-Simulated-Tenant": "tenant-b"})
        self.assertEqual(response.status_code, 200)
        self.service.assert_awaited_once_with("prop-001", "tenant-a", month=3, year=2024)

    def test_missing_tenant_is_rejected_before_query(self):
        self.user.tenant_id = None
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.service.assert_not_awaited()

    def test_invalid_reporting_periods_are_rejected(self):
        for query in ("month=13&year=2024", "month=3", "year=10000", "month=0&year=2024"):
            with self.subTest(query=query):
                response = self.client.get("/api/v1/dashboard/summary?property_id=prop-001&" + query)
                self.assertEqual(response.status_code, 422)
        self.service.assert_not_awaited()

    def test_foreign_or_missing_property_returns_not_found(self):
        self.service.side_effect = PropertyNotFoundError()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Property not found")

    def test_database_failure_returns_unavailable_instead_of_fake_revenue(self):
        self.service.side_effect = SQLAlchemyError("Database unavailable")
        with patch.object(dashboard.logger, "exception"):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("total_revenue", response.json())

    def test_mixed_currencies_return_an_explicit_error(self):
        self.service.side_effect = MixedCurrencyError("Cannot combine USD and EUR")
        self.assertEqual(self.client.get(self.url).status_code, 422)

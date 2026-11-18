"""PostgreSQL regression tests; each test rolls back its own fixture data."""
import os
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

from app.core.database_pool import DatabasePool
from app.services.reservations import (
    MixedCurrencyError, PropertyNotFoundError, calculate_total_revenue,
)


@unittest.skipUnless(os.getenv("RUN_DATABASE_TESTS") == "1", "Requires PostgreSQL")
class RevenueDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pool = DatabasePool()
        await self.pool.initialize()
        self.session = self.pool.get_session()
        self.addAsyncCleanup(self.pool.close)
        self.addAsyncCleanup(self.session.close)
        await self.session.begin()
        self.addAsyncCleanup(self.session.rollback)
        self.tenant_a, self.tenant_b = str(uuid4()), str(uuid4())
        for tenant in (self.tenant_a, self.tenant_b):
            await self.session.execute(
                text("INSERT INTO tenants (id, name) VALUES (:id, :name)"),
                {"id": tenant, "name": "Regression test"},
            )
            await self.session.execute(
                text("""INSERT INTO properties (id, tenant_id, name, timezone)
                        VALUES ('shared-property', :tenant, 'Test property', 'Europe/Paris')"""),
                {"tenant": tenant},
            )

    async def add_reservation(self, amount, check_in="2024-03-15T10:00:00+00:00", tenant=None, currency="USD"):
        check_in = datetime.fromisoformat(check_in)
        await self.session.execute(
            text("""INSERT INTO reservations
                    (id, property_id, tenant_id, check_in_date, check_out_date, total_amount, currency)
                    VALUES (:id, 'shared-property', :tenant, :check_in, :check_out, :amount, :currency)"""),
            {
                "id": str(uuid4()), "tenant": tenant or self.tenant_a,
                "check_in": check_in, "check_out": check_in + timedelta(days=1),
                "amount": Decimal(amount), "currency": currency,
            },
        )

    async def summary(self, tenant=None, **period):
        return await calculate_total_revenue(
            "shared-property", tenant or self.tenant_a,
            db_session=self.session, **period,
        )

    async def test_month_uses_local_check_in_and_half_open_boundaries(self):
        await self.add_reservation("1250", "2024-02-29T23:30:00+00:00")
        await self.add_reservation("10", "2024-02-29T23:00:00+00:00")
        await self.add_reservation("99", "2024-02-29T22:59:59+00:00")
        await self.add_reservation("99", "2024-03-31T22:00:00+00:00")
        result = await self.summary(month=3, year=2024)
        self.assertEqual(Decimal(result["total"]), Decimal("1260"))
        self.assertEqual(result["count"], 2)

    async def test_same_property_id_has_different_totals_for_each_tenant(self):
        await self.add_reservation("2250")
        await self.add_reservation("80.25", tenant=self.tenant_b)
        self.assertEqual(Decimal((await self.summary())["total"]), Decimal("2250"))
        self.assertEqual(Decimal((await self.summary(self.tenant_b))["total"]), Decimal("80.25"))

    async def test_foreign_property_and_unknown_property_are_both_rejected(self):
        await self.session.execute(
            text("""INSERT INTO properties (id, tenant_id, name)
                    VALUES ('foreign-property', :tenant, 'Private property')"""),
            {"tenant": self.tenant_b},
        )
        for property_id in ("foreign-property", "missing-property"):
            with self.subTest(property_id=property_id):
                with self.assertRaises(PropertyNotFoundError):
                    await calculate_total_revenue(
                        property_id, self.tenant_a, db_session=self.session
                    )

    async def test_empty_period_returns_zero(self):
        await self.add_reservation("1250")
        result = await self.summary(month=2, year=2024)
        self.assertEqual(Decimal(result["total"]), Decimal("0"))
        self.assertEqual(result["count"], 0)

    async def test_annual_totals_use_local_calendar_year(self):
        await self.add_reservation("50", "2023-12-31T23:30:00+00:00")
        await self.add_reservation("99", "2024-12-31T23:00:00+00:00")
        result = await self.summary(year=2024)
        self.assertEqual(Decimal(result["total"]), Decimal("50"))
        self.assertEqual(result["count"], 1)

    async def test_different_currencies_are_not_added_together(self):
        await self.add_reservation("10", currency="USD")
        await self.add_reservation("20", currency="EUR")
        with self.assertRaises(MixedCurrencyError):
            await self.summary()

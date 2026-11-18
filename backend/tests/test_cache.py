import json
import unittest
from unittest.mock import AsyncMock, patch

from redis.exceptions import ConnectionError

from app.services import cache


class RevenueCacheTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.entries = {}

        async def get(key):
            return self.entries.get(key)

        async def setex(key, ttl, value):
            self.entries[key] = value

        self.redis = AsyncMock()
        self.redis.get.side_effect = get
        self.redis.setex.side_effect = setex
        self.redis_patch = patch.object(cache, "redis_client", self.redis)
        self.redis_patch.start()
        self.addCleanup(self.redis_patch.stop)

    @staticmethod
    def summary(tenant_id, total):
        return {
            "tenant_id": tenant_id, "property_id": "prop-001",
            "total": total, "currency": "USD", "count": 1,
        }

    async def test_shared_property_id_remains_isolated_in_both_request_orders(self):
        for tenants in [("tenant-a", "tenant-b"), ("tenant-b", "tenant-a")]:
            with self.subTest(first=tenants[0]):
                self.entries.clear()
                totals = {"tenant-a": "2250.00", "tenant-b": "0.00"}

                async def calculate(property_id, tenant_id):
                    return self.summary(tenant_id, totals[tenant_id])

                with patch.object(cache, "calculate_total_revenue", side_effect=calculate) as calc:
                    for tenant in tenants + tenants:
                        result = await cache.get_revenue_summary("prop-001", tenant)
                        self.assertEqual(result["tenant_id"], tenant)
                        self.assertEqual(result["total"], totals[tenant])
                    self.assertEqual(calc.call_count, 2)
                    self.assertEqual(len(self.entries), 2)

    async def test_foreign_cached_payload_is_recalculated(self):
        foreign = self.summary("tenant-b", "99.00")
        self.redis.get.side_effect = None
        self.redis.get.return_value = json.dumps(foreign)
        expected = self.summary("tenant-a", "2250.00")
        with patch.object(cache, "calculate_total_revenue", return_value=expected) as calc:
            self.assertEqual(await cache.get_revenue_summary("prop-001", "tenant-a"), expected)
            calc.assert_awaited_once()

    async def test_cache_outage_still_returns_database_result(self):
        self.redis.get.side_effect = ConnectionError("offline")
        self.redis.setex.side_effect = ConnectionError("offline")
        expected = self.summary("tenant-a", "2250.00")
        with patch.object(cache, "calculate_total_revenue", return_value=expected):
            self.assertEqual(await cache.get_revenue_summary("prop-001", "tenant-a"), expected)

    async def test_database_error_is_not_cached(self):
        with patch.object(cache, "calculate_total_revenue", side_effect=RuntimeError("offline")):
            with self.assertRaises(RuntimeError):
                await cache.get_revenue_summary("prop-001", "tenant-a")
        self.redis.setex.assert_not_awaited()

    async def test_missing_tenant_is_rejected_before_cache_access(self):
        with self.assertRaises(ValueError):
            await cache.get_revenue_summary("prop-001", "")
        self.redis.get.assert_not_awaited()

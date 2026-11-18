"""Tenant-scoped caching for revenue summaries."""
import json
import logging

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.config import settings
from app.services.reservations import calculate_total_revenue

logger = logging.getLogger(__name__)
redis_client = redis.Redis.from_url(
    settings.redis_url, socket_connect_timeout=1, socket_timeout=1
)


async def get_revenue_summary(
    property_id: str, tenant_id: str, month: int | None = None, year: int | None = None,
) -> dict:
    if not tenant_id:
        raise ValueError("A tenant is required")

    # JSON prevents ambiguous keys; v3 ignores entries created before period-aware reporting.
    cache_key = "revenue:v3:" + json.dumps([tenant_id, property_id, year, month])
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            result = json.loads(cached)
            if (
                isinstance(result, dict)
                and result.get("tenant_id") == tenant_id
                and result.get("property_id") == property_id
                and result.get("month") == month
                and result.get("year") == year
            ):
                return result
    except (RedisError, ValueError, TypeError):
        logger.warning("Revenue cache unavailable or invalid; querying database")

    result = await calculate_total_revenue(property_id, tenant_id, month=month, year=year)
    try:
        await redis_client.setex(cache_key, 300, json.dumps(result))
    except RedisError:
        logger.warning("Revenue cache write failed; returning database result")
    return result

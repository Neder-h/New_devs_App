"""Revenue is recognized in full on check-in, in the property's local period."""
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.database_pool import db_pool


class PropertyNotFoundError(Exception):
    pass


class MixedCurrencyError(Exception):
    pass


def reporting_bounds(year: int, month: int | None, timezone_name: str):
    """Return UTC bounds for a local calendar month or year, including DST."""
    local_zone = ZoneInfo(timezone_name)
    start = datetime(year, month or 1, 1, tzinfo=local_zone)
    if month is None or month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=local_zone)
    else:
        end = datetime(year, month + 1, 1, tzinfo=local_zone)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


async def calculate_monthly_revenue(
    property_id: str, month: int, year: int, tenant_id: str, db_session=None
) -> Decimal:
    summary = await calculate_total_revenue(
        property_id, tenant_id, month=month, year=year, db_session=db_session
    )
    return Decimal(summary["total"])


async def calculate_total_revenue(
    property_id: str, tenant_id: str, month: int | None = None,
    year: int | None = None, db_session=None,
) -> dict:
    if not tenant_id:
        raise ValueError("A tenant is required")
    if month is not None and year is None:
        raise ValueError("A year is required when selecting a month")
    if year is not None and not 1 <= year <= 9998:
        raise ValueError("Year must be between 1 and 9998")
    if month is not None and not 1 <= month <= 12:
        raise ValueError("Month must be between 1 and 12")

    if db_session is not None:
        return await _calculate_revenue(db_session, property_id, tenant_id, month, year)

    await db_pool.initialize()
    async with db_pool.get_session() as session:
        return await _calculate_revenue(session, property_id, tenant_id, month, year)


async def _calculate_revenue(session, property_id, tenant_id, month, year):
    result = await session.execute(
        text("SELECT timezone FROM properties WHERE id = :property_id AND tenant_id = :tenant_id"),
        {"property_id": property_id, "tenant_id": tenant_id},
    )
    timezone_name = result.scalar_one_or_none()
    if timezone_name is None:
        # A foreign property is indistinguishable from a nonexistent one.
        raise PropertyNotFoundError()

    params = {"property_id": property_id, "tenant_id": tenant_id}
    period_filter = ""
    if year is not None:
        params["start"], params["end"] = reporting_bounds(year, month, timezone_name)
        period_filter = "AND check_in_date >= :start AND check_in_date < :end"

    result = await session.execute(
        text(f"""
            SELECT currency, SUM(total_amount) AS total, COUNT(*) AS count
            FROM reservations
            WHERE property_id = :property_id AND tenant_id = :tenant_id
            {period_filter}
            GROUP BY currency
        """),
        params,
    )
    rows = result.mappings().all()
    if len(rows) > 1:
        raise MixedCurrencyError("Cannot add different currencies without an exchange-rate policy")

    row = rows[0] if rows else None
    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": str(row["total"] if row else Decimal("0.00")),
        "currency": row["currency"] if row else "USD",
        "count": row["count"] if row else 0,
        "timezone": timezone_name,
        "month": month,
        "year": year,
    }

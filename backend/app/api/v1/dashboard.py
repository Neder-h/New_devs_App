import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import authenticate_request
from app.core.database_pool import db_pool
from app.models.auth import AuthenticatedUser
from app.services.cache import get_revenue_summary
from app.services.reservations import MixedCurrencyError, PropertyNotFoundError

logger = logging.getLogger(__name__)
router = APIRouter()


def require_tenant(user: AuthenticatedUser = Depends(authenticate_request)) -> str:
    if not user.tenant_id:
        raise HTTPException(status_code=403, detail="No tenant assigned")
    return user.tenant_id


@router.get("/dashboard/properties")
async def get_dashboard_properties(tenant_id: str = Depends(require_tenant)):
    try:
        await db_pool.initialize()
        async with db_pool.get_session() as session:
            result = await session.execute(
                text("SELECT id, name, timezone FROM properties WHERE tenant_id = :tenant_id ORDER BY name"),
                {"tenant_id": tenant_id},
            )
            return [dict(row) for row in result.mappings()]
    except (SQLAlchemyError, OSError):
        logger.exception("Property lookup failed")
        raise HTTPException(status_code=503, detail="Property data temporarily unavailable")


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str = Query(min_length=1),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=1, le=9998),
    tenant_id: str = Depends(require_tenant),
) -> dict:
    if month is not None and year is None:
        raise HTTPException(status_code=422, detail="A year is required when selecting a month")
    try:
        revenue = await get_revenue_summary(property_id, tenant_id, month=month, year=year)
    except PropertyNotFoundError:
        raise HTTPException(status_code=404, detail="Property not found")
    except MixedCurrencyError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except (SQLAlchemyError, OSError):
        logger.exception("Revenue calculation failed")
        raise HTTPException(status_code=503, detail="Revenue data temporarily unavailable")

    return {
        "property_id": revenue["property_id"],
        "total_revenue": revenue["total"],
        "currency": revenue["currency"],
        "reservations_count": revenue["count"],
        "timezone": revenue["timezone"],
        "month": revenue["month"],
        "year": revenue["year"],
    }

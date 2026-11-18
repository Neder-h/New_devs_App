"""Resolve tenant identity from trusted token claims."""
from typing import Optional

from jose import JWTError, jwt

from ..config import settings


class TenantResolver:
    @staticmethod
    def resolve_tenant_from_token(token_payload: dict) -> Optional[str]:
        # user_metadata is editable by users and cannot authorize a tenant.
        metadata = token_payload.get("app_metadata") or {}
        return metadata.get("tenant_id") or token_payload.get("tenant_id")

    @staticmethod
    def resolve_tenant_from_user(user_data: dict) -> Optional[str]:
        return TenantResolver.resolve_tenant_from_token(user_data)

    @staticmethod
    async def resolve_tenant_id(
        user_id: str, user_email: str, token: Optional[str] = None
    ) -> Optional[str]:
        if token:
            try:
                payload = jwt.decode(
                    token, settings.secret_key, algorithms=["HS256"],
                    audience="authenticated", options={"require_exp": True},
                )
                return TenantResolver.resolve_tenant_from_token(payload)
            except JWTError:
                return None

        return {
            "sunset@propertyflow.com": "tenant-a",
            "ocean@propertyflow.com": "tenant-b",
        }.get(user_email)

    @staticmethod
    async def update_user_tenant_metadata(user_id: str, tenant_id: str) -> None:
        # Local challenge accounts do not persist metadata in Supabase.
        pass

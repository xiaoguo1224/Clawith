"""Resolve OAuth redirect_uri for authorize + token exchange (per-tenant IdP config)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.services.platform_service import platform_service


def resolve_oauth_redirect_uri(config: dict | None, public_base: str, provider_type: str) -> str:
    """Use `oauth_redirect_uri` from IdP config when set; else `{public_base}/api/auth/{type}/callback`."""
    cfg = config or {}
    raw = (cfg.get("oauth_redirect_uri") or cfg.get("redirect_uri") or "").strip()
    if raw:
        return raw.rstrip("/")
    base = (public_base or "").rstrip("/")
    return f"{base}/api/auth/{provider_type}/callback"


async def resolve_oauth_redirect_uri_for_tenant(
    db: AsyncSession,
    config: dict | None,
    tenant_id: uuid.UUID | None,
    provider_type: str,
) -> str:
    public_base = await platform_service.get_public_base_url(db, None)
    if tenant_id:
        tr = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant_obj = tr.scalar_one_or_none()
        if tenant_obj:
            public_base = await platform_service.get_tenant_sso_base_url(db, tenant_obj, None)
    return resolve_oauth_redirect_uri(config, public_base, provider_type)

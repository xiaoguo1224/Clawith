"""Public OAuth (QR / browser) login — authorization URLs per tenant.

Legacy SSO scan session and /sso/entry flows have been removed; IdPs redirect
back to /api/auth/*/callback with state = tenant id, then the SPA completes
login via /login?oauth_complete=1.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tenant import Tenant
from app.services.platform_service import platform_service
from app.services.tenant_oauth_urls import build_oauth_login_urls_for_tenant

router = APIRouter(tags=["oauth"])


@router.get("/oauth/login-options")
async def get_oauth_login_options(
    tenant_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """OAuth / IdP sign-in links for a tenant (`state` = tenant id)."""
    t_res = await db.execute(select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active == True))
    tenant_obj = t_res.scalar_one_or_none()
    if not tenant_obj or not tenant_obj.sso_enabled:
        raise HTTPException(status_code=404, detail="Tenant not found or OAuth login not enabled")

    public_base = await platform_service.get_tenant_sso_base_url(db, tenant_obj, request)
    return await build_oauth_login_urls_for_tenant(
        db,
        tenant_id=tenant_id,
        public_base=public_base,
        state=str(tenant_id),
    )

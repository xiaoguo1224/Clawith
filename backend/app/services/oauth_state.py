"""Resolve OAuth `state` for web login: SSO scan session id or tenant id."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import SSOScanSession
from app.models.tenant import Tenant


async def resolve_oauth_login_state(
    db: AsyncSession, state: str | None
) -> tuple[uuid.UUID | None, SSOScanSession | None]:
    """Return (tenant_id, sso_session).

    If `state` is a valid UUID:
    1) Prefer an active SSOScanSession with that id (legacy scan flow).
    2) Else treat as tenant id when an active tenant exists.
    """
    if not state:
        return None, None
    try:
        uid = uuid.UUID(state)
    except (ValueError, AttributeError):
        return None, None

    s_res = await db.execute(select(SSOScanSession).where(SSOScanSession.id == uid))
    session = s_res.scalar_one_or_none()
    if session:
        return session.tenant_id, session

    t_res = await db.execute(select(Tenant).where(Tenant.id == uid, Tenant.is_active == True))
    if t_res.scalar_one_or_none():
        return uid, None

    return None, None

"""Resolve OAuth `state` for web login: must be an active tenant id (UUID)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant


async def resolve_oauth_tenant_id(db: AsyncSession, state: str | None) -> uuid.UUID | None:
    """If `state` is a valid UUID of an active tenant, return it; else None."""
    if not state:
        return None
    try:
        uid = uuid.UUID(state)
    except (ValueError, AttributeError):
        return None

    t_res = await db.execute(select(Tenant).where(Tenant.id == uid, Tenant.is_active == True))
    if t_res.scalar_one_or_none():
        return uid
    return None

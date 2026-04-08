"""Build per-tenant OAuth / IdP authorization URLs for web login (Feishu, DingTalk, WeCom, generic OAuth2)."""

from __future__ import annotations

import uuid
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import IdentityProvider


async def build_oauth_login_urls_for_tenant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    public_base: str,
    state: str,
) -> list[dict]:
    """Return [{provider_type, name, url}, ...] for active SSO-enabled identity providers."""
    query = select(IdentityProvider).where(
        IdentityProvider.is_active == True,
        IdentityProvider.sso_login_enabled == True,
    )
    if tenant_id:
        query = query.where(IdentityProvider.tenant_id == tenant_id)
    else:
        query = query.where(IdentityProvider.tenant_id.is_(None))

    result = await db.execute(query)
    providers = result.scalars().all()

    auth_urls: list[dict] = []
    tid = str(tenant_id) if tenant_id else None

    for p in providers:
        if p.provider_type == "feishu":
            app_id = (p.config or {}).get("app_id")
            if app_id:
                redir = f"{public_base}/api/auth/feishu/callback"
                url = f"https://open.feishu.cn/open-apis/authen/v1/index?app_id={app_id}&redirect_uri={quote(redir)}&state={state}"
                auth_urls.append({"provider_type": "feishu", "name": p.name, "url": url})

        elif p.provider_type == "dingtalk":
            from app.services.auth_registry import auth_provider_registry

            auth_provider = await auth_provider_registry.get_provider(db, "dingtalk", tid)
            if auth_provider:
                redir = f"{public_base}/api/auth/dingtalk/callback"
                url = await auth_provider.get_authorization_url(redir, state)
                auth_urls.append({"provider_type": "dingtalk", "name": p.name, "url": url})

        elif p.provider_type == "wecom":
            cfg = p.config or {}
            corp_id = cfg.get("corp_id")
            agent_id = cfg.get("agent_id")
            if corp_id and agent_id:
                redir = f"{public_base}/api/auth/wecom/callback"
                url = f"https://open.work.weixin.qq.com/wwopen/sso/qrConnect?appid={corp_id}&agentid={agent_id}&redirect_uri={quote(redir)}&state={state}"
                auth_urls.append({"provider_type": "wecom", "name": p.name, "url": url})

        elif p.provider_type == "oauth2":
            cfg = p.config or {}
            cid = cfg.get("app_id") or cfg.get("client_id")
            if cfg.get("authorize_url") and cfg.get("token_url") and cfg.get("user_info_url") and cid:
                from app.services.auth_registry import auth_provider_registry

                auth_provider = await auth_provider_registry.get_provider(db, "oauth2", tid)
                if auth_provider:
                    redir = f"{public_base}/api/auth/oauth2/callback"
                    url = await auth_provider.get_authorization_url(redir, state)
                    auth_urls.append({"provider_type": "oauth2", "name": p.name, "url": url})

    return auth_urls

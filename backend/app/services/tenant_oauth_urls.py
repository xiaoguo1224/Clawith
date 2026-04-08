"""Build per-tenant OAuth / IdP authorization URLs for web login (Feishu, DingTalk, WeCom, generic OAuth2)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import IdentityProvider

from app.services.oauth_redirect_uri import resolve_oauth_redirect_uri


def _dedupe_identity_providers_for_login_urls(providers: list) -> list:
    """One login button per vendor channel (feishu / dingtalk / wecom).

    Tenants may accidentally have duplicate rows (e.g. old platform default + new config);
    all oauth2 rows are kept so multiple generic IdPs remain possible.
    """
    feishu = [p for p in providers if p.provider_type == "feishu"]
    dingtalk = [p for p in providers if p.provider_type == "dingtalk"]
    wecom = [p for p in providers if p.provider_type == "wecom"]
    oauth2 = [p for p in providers if p.provider_type == "oauth2"]
    rest = [
        p
        for p in providers
        if p.provider_type not in ("feishu", "dingtalk", "wecom", "oauth2")
    ]

    def pick_one(candidates: list):
        if not candidates:
            return []
        if len(candidates) == 1:
            return candidates

        _epoch = datetime.min.replace(tzinfo=timezone.utc)

        def sort_key(p):
            cfg = p.config or {}
            has_custom = bool((cfg.get("oauth_redirect_uri") or cfg.get("redirect_uri") or "").strip())
            ua = p.updated_at or p.created_at or _epoch
            return (has_custom, ua, str(p.id))

        return [max(candidates, key=sort_key)]

    return pick_one(feishu) + pick_one(dingtalk) + pick_one(wecom) + oauth2 + rest


async def build_oauth_login_urls_for_tenant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    public_base: str,
    state: str,
) -> list[dict]:
    """Return [{provider_type, name, url}, ...] for IdPs with OAuth/scan login enabled."""
    query = select(IdentityProvider).where(
        IdentityProvider.is_active == True,
        IdentityProvider.sso_login_enabled == True,
    )
    if tenant_id:
        query = query.where(IdentityProvider.tenant_id == tenant_id)
    else:
        query = query.where(IdentityProvider.tenant_id.is_(None))

    result = await db.execute(query)
    providers = _dedupe_identity_providers_for_login_urls(list(result.scalars().all()))

    auth_urls: list[dict] = []
    tid = str(tenant_id) if tenant_id else None

    for p in providers:
        cfg = p.config or {}
        if p.provider_type == "feishu":
            app_id = cfg.get("app_id")
            if app_id:
                redir = resolve_oauth_redirect_uri(cfg, public_base, "feishu")
                url = f"https://open.feishu.cn/open-apis/authen/v1/index?app_id={app_id}&redirect_uri={quote(redir)}&state={state}"
                auth_urls.append({"provider_type": "feishu", "name": p.name, "url": url})

        elif p.provider_type == "dingtalk":
            from app.services.auth_registry import auth_provider_registry

            auth_provider = await auth_provider_registry.get_provider(db, "dingtalk", tid)
            if auth_provider:
                redir = resolve_oauth_redirect_uri(auth_provider.config, public_base, "dingtalk")
                url = await auth_provider.get_authorization_url(redir, state)
                auth_urls.append({"provider_type": "dingtalk", "name": p.name, "url": url})

        elif p.provider_type == "wecom":
            corp_id = cfg.get("corp_id")
            agent_id = cfg.get("agent_id")
            if corp_id and agent_id:
                redir = resolve_oauth_redirect_uri(cfg, public_base, "wecom")
                url = f"https://open.work.weixin.qq.com/wwopen/sso/qrConnect?appid={corp_id}&agentid={agent_id}&redirect_uri={quote(redir)}&state={state}"
                auth_urls.append({"provider_type": "wecom", "name": p.name, "url": url})

        elif p.provider_type == "oauth2":
            cid = cfg.get("app_id") or cfg.get("client_id")
            if cfg.get("authorize_url") and cfg.get("token_url") and cfg.get("user_info_url") and cid:
                from app.services.auth_registry import auth_provider_registry

                auth_provider = await auth_provider_registry.get_provider(db, "oauth2", tid)
                if auth_provider:
                    redir = resolve_oauth_redirect_uri(auth_provider.config, public_base, "oauth2")
                    url = await auth_provider.get_authorization_url(redir, state)
                    auth_urls.append({"provider_type": "oauth2", "name": p.name, "url": url})

    return auth_urls
